# ~/Downloads/OnboardingKarol/helpers.py

import re
import httpx
from datetime import datetime
from pydantic_settings import BaseSettings


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


# ─────── Helpers de formatação ───────
def limpar_telefone(numero: str) -> str:
    """Mantém apenas últimos 11 dígitos (DDD+celular)."""
    return re.sub(r"\D", "", numero)[-11:]


def formatar_data(data: str) -> str:
    """
    Converte 'dd/mm/YYYY' → 'YYYY-MM-DD'.
    Se falhar, retorna string vazia (omitida pelo Notion).
    """
    try:
        return datetime.strptime(data.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except Exception:
        return ""


# ─────── Notion ───────
def get_headers_notion():
    return {
        "Authorization": f"Bearer {settings.NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


async def notion_search_by_email(email: str):
    async with httpx.AsyncClient(timeout=10) as client:
        payload = {"filter": {"property": "Email", "email": {"equals": email}}}
        r = await client.post(
            f"https://api.notion.com/v1/databases/{settings.NOTION_DB_ID}/query",
            headers=get_headers_notion(),
            json=payload,
        )
        r.raise_for_status()
        return r.json().get("results", [])


async def notion_create_page(data: dict):
    """
    data deve ter as chaves:
      - name, email, telefone, cpf, pacote, inicio, fim, endereco
    """
    payload = {
        "parent": {"database_id": settings.NOTION_DB_ID},
        "properties": {
            "Student Name": {
                "title": [{"text": {"content": data["name"]}}]
            },
            "Email": {"email": data["email"]},
            "Telefone": {
                "rich_text": [{"text": {"content": data["telefone"]}}]
            },
            "CPF": {
                "rich_text": [{"text": {"content": data["cpf"]}}]
            },
            "Plano": {"select": {"name": data["pacote"] or "—"}},
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


# ─────── Z-API / WhatsApp ───────
async def send_whatsapp_message(name: str, email: str, phone: str, novo: bool):
    numero = limpar_telefone(phone)
    if len(numero) != 11:
        print(f"⚠️ Telefone inválido após limpeza: {numero}")
        return

    if novo:
        msg = (
            f"Welcome {name}! 🎉 Parabéns pela excelente decisão!\n\n"
            "Tenho certeza de que será uma experiência incrível para você!\n"
            "Sou Marcello, seu ponto de contato para tudo o que precisar.\n\n"
            f"Vi que seu e-mail cadastrado é {email}. Você deseja usá-lo para tudo ou prefere trocar?"
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


# ─────── Asaas ───────
async def get_or_create_customer(data: dict) -> str:
    """
    Tenta buscar cliente por e-mail; se não encontrar, cria novo.
    Retorna o customer_id.
    """
    headers = {
        "Content-Type": "application/json",
        "access-token": settings.ASAAS_API_KEY,
    }
    # busca
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{settings.ASAAS_BASE}/customers",
            params={"email": data["email"]},
            headers=headers,
        )
        r.raise_for_status()
        items = r.json().get("data", [])
        if items:
            return items[0]["id"]
        # cria novo
        payload = {
            "name": data["nome"],
            "email": data["email"],
            "mobilePhone": limpar_telefone(data["telefone"]),
            "cpfCnpj": re.sub(r"\D", "", data["cpf"]),
        }
        r2 = await client.post(
            f"{settings.ASAAS_BASE}/customers", json=payload, headers=headers
        )
        if r2.status_code != 200:
            print("❌ Erro ao criar cliente:", r2.text)
        r2.raise_for_status()
        return r2.json()["id"]


async def criar_assinatura_asaas(data: dict):
    """
    data deve ter as chaves:
      - nome, email, telefone, cpf,
      - valor (string "R$ 123,45"),
      - vencimento ("dd/mm/YYYY"),
      - fim_pagamento ("dd/mm/YYYY")
    """
    headers = {
        "Content-Type": "application/json",
        "access-token": settings.ASAAS_API_KEY,
    }

    customer_id = await get_or_create_customer(data)

    assinatura_payload = {
        "customer": customer_id,
        "billingType": "UNDEFINED",
        "cycle": "MONTHLY",
        "value": float(
            data["valor"].replace("R$", "").replace(".", "").replace(",", ".").strip()
            or 0
        ),
        "description": "Aulas de Inglês",
        "nextDueDate": formatar_data(data.get("vencimento", "")),
        "endDate": formatar_data(data.get("fim_pagamento", "")),
        "fine": {"value": 2, "type": "PERCENTAGE"},
        "interest": {"value": 1},
        "notificationDisabled": False,
    }

    async with httpx.AsyncClient(timeout=10) as client:
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
