# helpers.py
# Versão consolidada sem duplicidades e com preenchimento automático
# das selects “Plano” e “Tempo de contrato”

import re
from datetime import datetime
from typing import Dict, List, Optional

import httpx
from pydantic_settings import BaseSettings

# ──────────────────────────── SETTINGS ──────────────────────────────
class Settings(BaseSettings):
    NOTION_TOKEN: str
    NOTION_DB_ID: str
    ZAPI_INSTANCE_ID: str
    ZAPI_TOKEN: str
    ZAPI_SECURITY_TOKEN: str = ""
    ASAAS_API_KEY: str
    ASAAS_BASE: str = "https://api.asaas.com/v3"

    class Config:
        env_file = ".env"


settings = Settings()

# ──────────────────────────── MAPAS SELECT ──────────────────────────
PLANOS: Dict[str, str] = {
    "flexge": "Flexge",
    "português": "Português",
    "vip": "VIP",
    "light": "Light",
    "conversação com nativos + flexge": "Conversação com nativos + Flexge",
}

DURACOES: Dict[str, str] = {
    "anual": "anual",
    "semestral": "semestral",
}


def map_plano(raw: str) -> Optional[str]:
    raw = (raw or "").strip().lower()
    for chave, nome in PLANOS.items():
        if chave in raw:
            return nome
    return None


def map_duracao(raw: str) -> Optional[str]:
    raw = (raw or "").strip().lower()
    for chave, nome in DURACOES.items():
        if chave in raw:
            return nome
    return None


# ─────────────────────── HELPERS DE FORMATAÇÃO ──────────────────────
def limpar_telefone(numero: str) -> str:
    """Mantém apenas os últimos 11 dígitos (DDD + celular)."""
    return re.sub(r"\D", "", numero)[-11:]


def formatar_data(data: str) -> str:
    """
    Converte 'dd/mm/YYYY' → 'YYYY-MM-DD'.
    Se falhar, retorna string vazia (omitida pelo Notion/Asaas).
    """
    try:
        return datetime.strptime(data.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except Exception:
        return ""


# ───────────────────────────── NOTION ───────────────────────────────
def get_headers_notion() -> dict:
    return {
        "Authorization": f"Bearer {settings.NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


async def notion_search_by_email(email: str) -> List[dict]:
    """Retorna no máximo 1 página que tenha o e-mail exato."""
    email = email.strip().lower()
    payload = {
        "filter": {"property": "Email", "email": {"equals": email}},
        "page_size": 1,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"https://api.notion.com/v1/databases/{settings.NOTION_DB_ID}/query",
            headers=get_headers_notion(),
            json=payload,
        )
        r.raise_for_status()
        return r.json().get("results", [])


async def notion_create_page(data: dict) -> None:
    """
    Cria um novo aluno. `data` deve conter:
      name, email, telefone, cpf, pacote, duracao, inicio, fim, endereco
    """
    payload = {
        "parent": {"database_id": settings.NOTION_DB_ID},
        "properties": {
            "Student Name": {"title": [{"text": {"content": data["name"]}}]},
            "Email": {"email": data["email"]},
            "Telefone": {"rich_text": [{"text": {"content": data["telefone"]}}]},
            "CPF": {"rich_text": [{"text": {"content": data["cpf"]}}]},
            "Plano": {"select": {"name": data["pacote"] or "—"}},
            "Tempo de contrato": {"select": {"name": data.get("duracao") or "—"}},
            "Inicio do contrato": {
                "date": {"start": formatar_data(data.get("inicio", ""))}
            },
            "Fim do contrato": {
                "date": {"start": formatar_data(data.get("fim", ""))}
            },
            "Endereço Completo": {
                "rich_text": [{"text": {"content": data.get("endereco", "")}}]
            },
        },
    }

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://api.notion.com/v1/pages",
            headers=get_headers_notion(),
            json=payload,
        )
        if r.status_code != 200:
            print("❌ Notion payload rejeitado:", r.text)
        r.raise_for_status()


async def notion_update_page(page_id: str, props: dict) -> None:
    """Atualiza apenas as propriedades passadas em `props`."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=get_headers_notion(),
            json={"properties": props},
        )
        if r.status_code != 200:
            print("❌ Notion update error:", r.text)
        r.raise_for_status()


async def upsert_student(data: dict) -> str:
    """
    Se o aluno existir (pelo e-mail), atualiza;
    senão, cria e retorna o page_id (ou string vazia).
    """
    resultados = await notion_search_by_email(data["email"])
    if resultados:
        page_id = resultados[0]["id"]
        props = {
            "Student Name": {
                "title": [{"text": {"content": data["name"]}}],
            },
            "Telefone": {
                "rich_text": [{"text": {"content": data["telefone"]}}],
            },
            "CPF": {
                "rich_text": [{"text": {"content": data["cpf"]}}],
            },
            "Plano": {
                "select": {"name": data["pacote"] or "—"},
            },
            "Tempo de contrato": {
                "select": {"name": data.get("duracao") or "—"},
            },
            "Inicio do contrato": {
                "date": {"start": formatar_data(data.get("inicio", ""))},
            },
            "Fim do contrato": {
                "date": {"start": formatar_data(data.get("fim", ""))},
            },
            "Endereço Completo": {
                "rich_text": [{"text": {"content": data.get("endereco", "")}}],
            },
        }
        # remove campos vazios
        props = {k: v for k, v in props.items() if v}
        await notion_update_page(page_id, props)
        return page_id
    else:
        await notion_create_page(data)
        return ""


# ──────────────────────── Z-API / WHATSAPP ──────────────────────────
async def send_whatsapp_message(name: str, email: str, phone: str, novo: bool) -> None:
    numero = limpar_telefone(phone)
    if len(numero) != 11:
        print(f"⚠️ Telefone inválido após limpeza: {numero}")
        return

    if novo:
        msg = (
            f"Welcome {name}! 🎉 Parabéns pela excelente decisão!\n\n"
            "Tenho certeza de que será uma experiência incrível para você!\n"
            "Sou Marcello, seu ponto de contato para tudo o que precisar.\n\n"
            f"Vi que seu e-mail cadastrado é {email}. Você deseja usá-lo para tudo "
            "ou prefere trocar?"
        )
    else:
        msg = (
            f"Olá {name}, parabéns pela escolha de continuar seus estudos. "
            "Tenho certeza de que a continuação dessa jornada será incrível. "
            "Se precisar de algo, pode contar com a gente! Rumo à fluência!"
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
            print("✅ Mensagem enviada com sucesso")
        else:
            print("❌ Falha ao enviar mensagem:", r.text)


# ───────────────────────────── ASAAS ────────────────────────────────
async def criar_assinatura_asaas(data: dict):
    """
    `data` requer:
      nome, email, telefone, cpf,
      valor (ex.: "R$ 123,45"),
      vencimento ("dd/mm/YYYY"),
      fim_pagamento ("dd/mm/YYYY")
    """
    headers = {
        "Content-Type": "application/json",
        "access-token": settings.ASAAS_API_KEY,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        # 1) ─── BUSCA ou CRIA cliente ────────────────────────────────
        r = await client.get(
            f"{settings.ASAAS_BASE}/customers",
            headers=headers,
            params={"email": data["email"]},
        )
        r.raise_for_status()
        clientes = r.json().get("data", [])

        if clientes:
            customer_id = clientes[0]["id"]
        else:
            customer_payload = {
                "name": data["nome"],
                "email": data["email"],
                "mobilePhone": limpar_telefone(data["telefone"]),
                "cpfCnpj": re.sub(r"\D", "", data["cpf"]),
            }
            r = await client.post(
                f"{settings.ASAAS_BASE}/customers",
                json=customer_payload,
                headers=headers,
            )
            r.raise_for_status()
            customer_id = r.json()["id"]

        # 2) ─── VERIFICA assinatura ativa ───────────────────────────
        r = await client.get(
            f"{settings.ASAAS_BASE}/subscriptions",
            headers=headers,
            params={"customer": customer_id, "status": "ACTIVE"},
        )
        r.raise_for_status()
        ativas = r.json().get("data", [])

        if ativas:
            print("ℹ️ Já existe assinatura ativa; não será criada outra.")
            return ativas[0]

        # 3) ─── CRIA assinatura ─────────────────────────────────────
        assinatura_payload = {
            "customer": customer_id,
            "billingType": "UNDEFINED",  # definido depois pelo cliente
            "cycle": "MONTHLY",
            "value": float(
                data["valor"]
                .replace("R$", "")
                .replace(".", "")
                .replace(",", ".")
                .strip()
                or 0
            ),
            "description": "Aulas de Inglês",
            "nextDueDate": formatar_data(data.get("vencimento", "")),
            "endDate": formatar_data(data.get("fim_pagamento", "")),
            "fine": {"value": 2, "type": "PERCENTAGE"},
            "interest": {"value": 1},
            "notificationDisabled": False,
            # evita duplicação
            "externalReference": f"{data['email']}-{data.get('vencimento', '')}",
        }

        r = await client.post(
            f"{settings.ASAAS_BASE}/subscriptions",
            json=assinatura_payload,
            headers=headers,
        )
        if r.status_code != 200:
            print("❌ Erro ao criar assinatura:", r.text)
        r.raise_for_status()
        print("✅ Assinatura criada com sucesso")
        return r.json()
