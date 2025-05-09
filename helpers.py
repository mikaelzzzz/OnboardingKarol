import re
import httpx
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


def get_headers_notion():
    return {
        "Authorization": f"Bearer {settings.NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }


async def notion_search_by_email(email: str):
    async with httpx.AsyncClient(timeout=10) as client:
        payload = {
            "filter": {
                "property": "Email",
                "email": {
                    "equals": email
                }
            }
        }
        resp = await client.post(
            f"https://api.notion.com/v1/databases/{settings.NOTION_DB_ID}/query",
            headers=get_headers_notion(),
            json=payload
        )
        resp.raise_for_status()
        return resp.json()["results"]


async def send_whatsapp_message(name: str, email: str, phone: str, novo: bool):
    msg = (
        f"Welcome {name}! 🎉 Parabéns pela excelente decisão!\n\n"
        f"Tenho certeza de que será uma experiência incrível para você!\n"
        f"Sou Marcello, seu ponto de contato para tudo o que precisar.\n\n"
        f"Vi que seu e-mail cadastrado é {email}. Você deseja usá-lo para tudo ou prefere trocar?"
    ) if novo else (
        f"Olá {name}, parabéns pela escolha de continuar seus estudos. "
        "Tenho certeza de que a continuação dessa jornada será incrível. "
        "Se precisar de algo, pode contar com a gente! Rumo à fluência!"
    )

    cleaned_phone = re.sub(r"\D", "", phone)

    payload = {
        "phone": cleaned_phone,
        "message": msg
    }

    url = f"https://api.z-api.io/instances/{settings.ZAPI_INSTANCE_ID}/token/{settings.ZAPI_TOKEN}/send-message"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            print("✅ Mensagem enviada com sucesso")
    except Exception as e:
        print(f"❌ Erro ao enviar mensagem via Z-API: {e}")


async def criar_assinatura_asaas(data: dict):
    raw_phone = re.sub(r"\D", "", data["telefone"])

    # Valida o celular: 11 dígitos esperados (ex: 11999999999)
    if len(raw_phone) != 11:
        print(f"⚠️ Telefone inválido: {raw_phone}")
        raise ValueError("Telefone inválido. Deve conter 11 dígitos (DDD + número).")

    customer_payload = {
        "name": data["nome"],
        "email": data["email"],
        "mobilePhone": raw_phone,
        "cpfCnpj": re.sub(r"\D", "", data["cpf"])
    }

    headers = {
        "Content-Type": "application/json",
        "access-token": settings.ASAAS_API_KEY
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(f"{settings.ASAAS_BASE}/customers", json=customer_payload, headers=headers)
            r.raise_for_status()
            customer_id = r.json()["id"]
        except Exception as e:
            print(f"❌ Erro ao criar cliente: {r.text}")
            raise e

        assinatura_payload = {
            "customer": customer_id,
            "billingType": "BOLETO",
            "cycle": "MONTHLY",
            "value": float(data["valor"].replace("R$", "").replace(",", ".").strip()),
            "description": "Aulas de Inglês",
            "nextDueDate": data["vencimento"],
            "endDate": data["fim_pagamento"],
            "fine": {"value": 2, "type": "PERCENTAGE"},
            "interest": {"value": 1},
            "notificationDisabled": False
        }

        try:
            assinatura = await client.post(f"{settings.ASAAS_BASE}/subscriptions", json=assinatura_payload, headers=headers)
            assinatura.raise_for_status()
            print("✅ Assinatura criada com sucesso")
            return assinatura.json()
        except Exception as e:
            print(f"❌ Erro ao criar assinatura: {assinatura.text}")
            raise e
