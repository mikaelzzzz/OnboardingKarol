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

# Planos válidos no Notion (propriedade 'Plano' - tipo Select)
PLANOS_VALIDOS = [
    "Flexge + Conversação com nativos",
    "VIP",
    "Light",
    "Anual"
]

def limpar_telefone(numero: str) -> str:
    return re.sub(r"\D", "", numero)[-11:]

def formatar_data(data: str) -> str:
    try:
        return datetime.strptime(data.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except Exception:
        return ""

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
        return r.json()["results"]

async def notion_create_page(data: dict):
    plano = data.get("pacote", "").strip()
    if plano not in PLANOS_VALIDOS:
        plano = "Flexge + Conversação com nativos"

    payload = {
        "parent": {"database_id": settings.NOTION_DB_ID},
        "properties": {
            "Student Name": {"title": [{"text": {"content": data["name"]}}]},
            "Email": {"email": data["email"]},
            "Telefone": {"rich_text": [{"text": {"content": data["telefone"]}}]},
            "CPF": {"rich_text": [{"text": {"content": data["cpf"]}}]},
            "Plano": {"select": {"name": plano}},
            "Inicio do contrato": {
                "date": {"start": formatar_data(data.get("inicio", ""))}
            },
            "Fim do contrato": {
                "date": {"start": formatar_data(data.get("fim", ""))}
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

async def send_whatsapp_message(name: str, email: str, phone: str, novo: bool):
    numero = limpar_telefone(phone)
    if len(numero) != 11:
        print(f"⚠️ Telefone inválido após limpeza: {numero}")
        return

    msg = (
        f"Welcome {name}! 🎉 Parabéns pela excelente decisão!\n\n"
        "Tenho certeza de que será uma experiência incrível para você!\n"
        "Sou Marcello, seu ponto de contato para tudo o que precisar.\n\n"
        f"Vi que seu e-mail cadastrado é {email}. Você deseja usá-lo para tudo ou prefere trocar?"
    ) if novo else (
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
        "X-Security-Token": settings.ZAPI_SECURITY_TOKEN
    }

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code == 200:
            print("✅ Mensagem enviada com sucesso")
        else:
            print("❌ Falha ao enviar mensagem:", r.text)

async def criar_assinatura_asaas(data: dict):
    headers = {
        "Content-Type": "application/json",
        "access-token": settings.ASAAS_API_KEY,
    }

    customer_payload = {
        "name": data["nome"],
        "email": data["email"],
        "mobilePhone": limpar_telefone(data["telefone"]),
        "cpfCnpj": re.sub(r"\D", "", data["cpf"]),
    }

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{settings.ASAAS_BASE}/customers", json=customer_payload, headers=headers
        )
        if r.status_code != 200:
            print("❌ Erro ao criar cliente:", r.text)
            r.raise_for_status()
        customer_id = r.json()["id"]

        assinatura_payload = {
            "customer": customer_id,
            "billingType": "BOLETO",
            "cycle": "MONTHLY",
            "value": float(
                data["valor"].replace("R$", "").replace(".", "").replace(",", ".").strip() or 0
            ),
            "description": "Aulas de Inglês",
            "nextDueDate": formatar_data(data.get("vencimento", "")),
            "endDate": formatar_data(data.get("fim_pagamento", "")),
            "fine": {"value": 2, "type": "PERCENTAGE"},
            "interest": {"value": 1},
            "notificationDisabled": False,
        }

        assinatura = await client.post(
            f"{settings.ASAAS_BASE}/subscriptions",
            json=assinatura_payload,
            headers=headers,
        )
        if assinatura.status_code != 200:
            print("❌ Erro ao criar assinatura:", assinatura.text)
        assinatura.raise_for_status()
        print("✅ Assinatura criada com sucesso")
        return assinatura.json()
