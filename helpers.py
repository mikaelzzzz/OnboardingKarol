# ~/Downloads/OnboardingKarol/helpers.py
# Versão 2025-06-05 — revisada: upsert idempotente, selects preenchidas,
# datas normalizadas, sem funções faltantes.

import re
from datetime import datetime
from typing import Dict, List, Optional

import httpx
from pydantic_settings import BaseSettings

# ───────────────────────────── SETTINGS ─────────────────────────────
class Settings(BaseSettings):
    NOTION_TOKEN: str
    NOTION_DB_ID: str
    ZAPI_INSTANCE_ID: str
    ZAPI_TOKEN: str
    ZAPI_SECURITY_TOKEN: str | None = ""
    ASAAS_API_KEY: str
    ASAAS_BASE: str = "https://api.asaas.com/v3"

    class Config:
        env_file = ".env"


settings = Settings()

# ─────────────────────────── MAPAS DE SELECT ────────────────────────
PLANOS: Dict[str, str] = {
    "flexge": "Flexge",
    "português": "Português",
    "vip": "VIP",
    "light": "Light",
    "conversação com nativos + flexge": "Conversação com nativos + Flexge",
}
DURACOES: Dict[str, str] = {"anual": "anual", "semestral": "semestral"}


def map_plano(raw: str | None) -> Optional[str]:
    raw = (raw or "").strip().lower()
    for chave, nome in PLANOS.items():
        if chave in raw:
            return nome
    return None


def map_duracao(raw: str | None) -> Optional[str]:
    raw = (raw or "").strip().lower()
    for chave, nome in DURACOES.items():
        if chave in raw:
            return nome
    return None


# ───────────────────── FUNÇÕES DE FORMATAÇÃO ───────────────────────
def limpar_telefone(numero: str) -> str:
    """Remove caracteres não numéricos e devolve os 11 últimos dígitos (DDD+cel)."""
    return re.sub(r"\D", "", numero)[-11:]


def formatar_data(data: str | None) -> str:
    """
    Converte 'dd/mm/YYYY' → 'YYYY-MM-DD'.
    Retorna string vazia se `data` for falsy ou inválida.
    """
    try:
        return datetime.strptime((data or "").strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return ""


# ───────────────────────────── NOTION ───────────────────────────────
def _headers_notion() -> dict:
    return {
        "Authorization": f"Bearer {settings.NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


async def notion_search_by_email(email: str) -> List[dict]:
    """Busca página pelo e-mail exato (máximo 1 resultado)."""
    payload = {
        "filter": {"property": "Email", "email": {"equals": email.strip().lower()}},
        "page_size": 1,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"https://api.notion.com/v1/databases/{settings.NOTION_DB_ID}/query",
            headers=_headers_notion(),
            json=payload,
        )
        r.raise_for_status()
        return r.json().get("results", [])


async def notion_create_page(data: dict) -> None:
    """Cria novo registro de aluno."""
    payload = {
        "parent": {"database_id": settings.NOTION_DB_ID},
        "properties": {
            "Student Name": {"title": [{"text": {"content": data["name"]}}]},
            "Email": {"email": data["email"]},
            "Telefone": {"rich_text": [{"text": {"content": data["telefone"]}}]},
            "CPF": {"rich_text": [{"text": {"content": data["cpf"]}}]},
            "Plano": {"select": {"name": data["pacote"] or "—"}},
            "Tempo de contrato": {"select": {"name": data.get("duracao") or "—"}},
            "Inicio do contrato": {"date": {"start": data["inicio"]}},
            "Fim do contrato": {"date": {"start": data["fim"]}},
            "Endereço Completo": {
                "rich_text": [{"text": {"content": data.get("endereco", "")}}]
            },
        },
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://api.notion.com/v1/pages",
            headers=_headers_notion(),
            json=payload,
        )
        if r.status_code != 200:
            print("❌ Notion create error:", r.text)
        r.raise_for_status()


async def notion_update_page(page_id: str, props: dict) -> None:
    """Atualiza somente as props fornecidas."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=_headers_notion(),
            json={"properties": props},
        )
        if r.status_code != 200:
            print("❌ Notion update error:", r.text)
        r.raise_for_status()


async def upsert_student(data: dict) -> str:
    """
    Atualiza registro existente (mesmo e-mail) ou cria um novo.
    Retorna o page_id do registro encontrado/criado.
    """
    resultado = await notion_search_by_email(data["email"])
    if resultado:
        page_id = resultado[0]["id"]
        props = {
            "Student Name": {"title": [{"text": {"content": data["name"]}}]},
            "Telefone": {"rich_text": [{"text": {"content": data["telefone"]}}]},
            "CPF": {"rich_text": [{"text": {"content": data["cpf"]}}]},
            "Plano": {"select": {"name": data["pacote"] or "—"}},
            "Tempo de contrato": {"select": {"name": data.get("duracao") or "—"}},
            "Inicio do contrato": {"date": {"start": data["inicio"]}},
            "Fim do contrato": {"date": {"start": data["fim"]}},
            "Endereço Completo": {
                "rich_text": [{"text": {"content": data.get("endereco", "")}}]
            },
        }
        props = {k: v for k, v in props.items() if v}  # remove vazios
        await notion_update_page(page_id, props)
        return page_id
    else:
        await notion_create_page(data)
        return ""


# ─────────────────────────── Z-API / WHATSAPP ───────────────────────
async def send_whatsapp_message(name: str, email: str, phone: str, novo: bool) -> None:
    numero = limpar_telefone(phone)
    if len(numero) != 11:
        print(f"⚠️ Telefone inválido: {numero}")
        return

    if novo:
        msg = (
            f"Welcome {name}! 🎉 Parabéns pela excelente decisão!\n\n"
            "Sou Marcello, seu ponto de contato para qualquer dúvida.\n"
            f"Seu e-mail cadastrado é {email}. Prefere usar outro?"
        )
    else:
        msg = (
            f"Olá {name}, obrigado por renovar conosco! "
            "Qualquer coisa é só chamar. Rumo à fluência! 🚀"
        )

    payload = {"phone": numero, "message": msg}
    url = (
        f"https://api.z-api.io/instances/{settings.ZAPI_INSTANCE_ID}"
        f"/token/{settings.ZAPI_TOKEN}/send-text"
    )
    headers = {
        "Content-Type": "application/json",
        "Client-Token": settings.ZAPI_SECURITY_TOKEN,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code == 200:
            print("✅ WhatsApp enviado")
        else:
            print("❌ WhatsApp erro:", r.text)


# ───────────────────────────── ASAAS ────────────────────────────────
async def criar_assinatura_asaas(data: dict):
    """
    Cria assinatura mensal no Asaas se não existir uma ativa.
    Campos obrigatórios em `data`:
      nome, email, telefone, cpf, valor, vencimento, fim_pagamento
    """
    headers = {"Content-Type": "application/json", "access-token": settings.ASAAS_API_KEY}

    async with httpx.AsyncClient(timeout=10) as client:
        # 1) cliente
        r = await client.get(
            f"{settings.ASAAS_BASE}/customers", headers=headers, params={"email": data["email"]}
        )
        r.raise_for_status()
        clientes = r.json().get("data", [])
        if clientes:
            customer_id = clientes[0]["id"]
        else:
            payload = {
                "name": data["nome"],
                "email": data["email"],
                "mobilePhone": limpar_telefone(data["telefone"]),
                "cpfCnpj": re.sub(r"\D", "", data["cpf"]),
            }
            r = await client.post(f"{settings.ASAAS_BASE}/customers", headers=headers, json=payload)
            r.raise_for_status()
            customer_id = r.json()["id"]

        # 2) assinatura ativa?
        r = await client.get(
            f"{settings.ASAAS_BASE}/subscriptions",
            headers=headers,
            params={"customer": customer_id, "status": "ACTIVE"},
        )
        r.raise_for_status()
        if r.json().get("data"):
            print("ℹ️ Assinatura já existe — nada a criar.")
            return r.json()["data"][0]

        # 3) cria assinatura
        assinatura = {
            "customer": customer_id,
            "billingType": "UNDEFINED",
            "cycle": "MONTHLY",
            "value": float(
                data["valor"].replace("R$", "").replace(".", "").replace(",", ".").strip() or 0
            ),
            "description": "Aulas de Inglês",
            "nextDueDate": formatar_data(data.get("vencimento")),
            "endDate": formatar_data(data.get("fim_pagamento")),
            "fine": {"value": 2, "type": "PERCENTAGE"},
            "interest": {"value": 1},
            "notificationDisabled": False,
            "externalReference": f"{data['email']}-{data.get('vencimento','')}",
        }
        r = await client.post(
            f"{settings.ASAAS_BASE}/subscriptions", headers=headers, json=assinatura
        )
        if r.status_code != 200:
            print("❌ Asaas erro:", r.text)
        r.raise_for_status()
        print("✅ Assinatura criada")
        return r.json()
