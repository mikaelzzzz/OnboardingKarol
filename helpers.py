# ~/Downloads/OnboardingKarol/helpers.py
# Versão 2025-06-05 e — cache de WhatsApp por número (TTL 5 min),
# grava Data de Nascimento, Plano robusto, upsert idêntico.

import re
import time
import unicodedata
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

# ──────────────────────── NORMALIZAÇÃO AUXILIAR ─────────────────────
def _norm(text: str | None) -> str:
    if not text:
        return ""
    txt = unicodedata.normalize("NFD", text)
    return "".join(c for c in txt if unicodedata.category(c) != "Mn").lower().strip()


# ─────────────────────────── MAPAS DE SELECT ────────────────────────
PLANOS: Dict[str, str] = {
    "vip": "VIP",
    "light": "Light",
    "flexge": "Flexge",
    "flexge + conversacao": "Conversacao com nativos + Flexge",
    "conversacao com nativos + flexge": "Conversacao com nativos + Flexge",
}
DURACOES: Dict[str, str] = {"anual": "anual", "semestral": "semestral"}


def map_plano(raw: str | None) -> Optional[str]:
    chave = _norm(raw)
    for alias, nome in PLANOS.items():
        if alias in chave:
            return nome
    return None


def map_duracao(raw: str | None) -> Optional[str]:
    chave = _norm(raw)
    for alias, nome in DURACOES.items():
        if alias in chave:
            return nome
    return None


# ───────────────────── FUNÇÕES DE FORMATAÇÃO ───────────────────────
def limpar_telefone(numero: str) -> str:
    return re.sub(r"\D", "", numero)[-11:]


def formatar_data(data: str | None) -> str:
    try:
        return datetime.strptime((data or "").strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return ""


# ──────────────────────────── NOTION ────────────────────────────────
def _headers_notion() -> dict:
    return {
        "Authorization": f"Bearer {settings.NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


async def notion_search_by_email(email: str) -> List[dict]:
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


def _build_props(data: dict) -> dict:
    props = {
        "Student Name": {"title": [{"text": {"content": data["name"]}}]},
        "Telefone":     {"rich_text": [{"text": {"content": data["telefone"]}}]},
        "CPF":          {"rich_text": [{"text": {"content": data["cpf"]}}]},
        "Plano":        {"select":   {"name": data["pacote"] or "—"}},
        "Inicio do contrato": {"date": {"start": data["inicio"]}},
        "Fim do contrato":    {"date": {"start": data["fim"]}},
        "Endereço Completo":  {"rich_text": [{"text": {"content": data.get("endereco", "")}}]},
        **(
            {"Data de Nascimento": {"date": {"start": data["nascimento"]}}}
            if data.get("nascimento")
            else {}
        ),
        **(
            {"Tempo de contrato": {"status": {"name": data["duracao"]}}}
            if data.get("duracao")
            else {}
        ),
    }
    return {k: v for k, v in props.items() if v}


async def notion_create_page(data: dict) -> None:
    payload = {
        "parent": {"database_id": settings.NOTION_DB_ID},
        "properties": {"Email": {"email": data["email"]}, **_build_props(data)},
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post("https://api.notion.com/v1/pages", headers=_headers_notion(), json=payload)
        if r.status_code != 200:
            print("❌ Notion create error:", r.text)
        r.raise_for_status()


async def notion_update_page(page_id: str, data: dict) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=_headers_notion(),
            json={"properties": _build_props(data)},
        )
        if r.status_code != 200:
            print("❌ Notion update error:", r.text)
        r.raise_for_status()


async def upsert_student(data: dict) -> str:
    resultado = await notion_search_by_email(data["email"])
    if resultado:
        page_id = resultado[0]["id"]
        await notion_update_page(page_id, data)
        return page_id
    await notion_create_page(data)
    return ""


# ─────────── Anti-duplicação de WhatsApp (TTL 5 min por número) ─────
_MSG_CACHE: Dict[str, float] = {}
_CACHE_TTL = 300  # segundos


def _can_send(numero: str) -> bool:
    now = time.time()
    _MSG_CACHE.update({k: v for k, v in _MSG_CACHE.items() if now - v <= _CACHE_TTL})
    if numero in _MSG_CACHE:
        return False
    _MSG_CACHE[numero] = now
    return True


# ─────────────────────── Z-API / WHATSAPP ───────────────────────────
async def send_whatsapp_message(name: str, email: str, phone: str, novo: bool) -> None:
    numero = limpar_telefone(phone)
    if len(numero) != 11:
        print(f"⚠️ Telefone inválido: {numero}")
        return

    msg = (
        f"Welcome {name}! 🎉 Parabéns pela excelente decisão!\n\n"
        "Sou Marcello, seu ponto de contato para qualquer dúvida.\n"
        f"Seu e-mail cadastrado é {email}. Prefere usar outro?"
        if novo
        else (
            f"Olá {name}, obrigado por renovar conosco! "
            "Qualquer coisa é só chamar. Rumo à fluência! 🚀"
        )
    )

    if not _can_send(numero):
        print("ℹ️ WhatsApp já enviado recentemente – ignorado")
        return

    payload = {"phone": numero, "message": msg}
    url = f"https://api.z-api.io/instances/{settings.ZAPI_INSTANCE_ID}/token/{settings.ZAPI_TOKEN}/send-text"
    headers = {"Content-Type": "application/json", "Client-Token": settings.ZAPI_SECURITY_TOKEN}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code == 200:
            print("✅ WhatsApp enviado")
        else:
            print("❌ WhatsApp erro:", r.text)


# ───────────────────────────── ASAAS ────────────────────────────────
async def criar_assinatura_asaas(data: dict):
    headers = {"Content-Type": "application/json", "access-token": settings.ASAAS_API_KEY}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{settings.ASAAS_BASE}/customers", headers=headers, params={"email": data["email"]})
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

        r = await client.get(
            f"{settings.ASAAS_BASE}/subscriptions",
            headers=headers,
            params={"customer": customer_id, "status": "ACTIVE"},
        )
        r.raise_for_status()
        if r.json().get("data"):
            print("ℹ️ Assinatura já existe — nada a criar.")
            return r.json()["data"][0]

        assinatura = {
            "customer": customer_id,
            "billingType": "UNDEFINED",
            "cycle": "MONTHLY",
            "value": float(data["valor"].replace("R$", "").replace(".", "").replace(",", ".").strip() or 0),
            "description": "Aulas de Inglês",
            "nextDueDate": formatar_data(data.get("vencimento")),
            "endDate": formatar_data(data.get("fim_pagamento")),
            "fine": {"value": 2, "type": "PERCENTAGE"},
            "interest": {"value": 1},
            "notificationDisabled": False,
            "externalReference": f"{data['email']}-{data.get('vencimento','')}",
        }
        r = await client.post(f"{settings.ASAAS_BASE}/subscriptions", headers=headers, json=assinatura)
        if r.status_code != 200:
            print("❌ Asaas erro:", r.text)
        r.raise_for_status()
        print("✅ Assinatura criada")
        return r.json()
