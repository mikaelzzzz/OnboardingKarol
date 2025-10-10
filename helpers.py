# ~/Downloads/OnboardingKarol/helpers.py
# Versão 2025-06-06 f — inclui iso_or_brazil() para corrigir nextDueDate/endDate

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
    NOTION_DATA_SOURCE_ID: str | None = ""
    NOTION_API_VERSION: str = "2025-09-03"
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


def iso_or_brazil(date_str: str | None) -> str:     # ← NOVA função
    """
    Aceita 'YYYY-MM-DD' ou 'dd/mm/YYYY' e converte para ISO.
    Retorna '' se inválido.
    """
    if not date_str:
        return ""
    txt = date_str.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", txt):
        return txt
    return formatar_data(txt)


# ──────────────────────────── NOTION ────────────────────────────────
def _headers_notion() -> dict:
    return {
        "Authorization": f"Bearer {settings.NOTION_TOKEN}",
        "Notion-Version": settings.NOTION_API_VERSION,
        "Content-Type": "application/json",
    }


_CACHED_DATA_SOURCE_ID: str | None = None


async def _get_data_source_id() -> str | None:
    global _CACHED_DATA_SOURCE_ID
    if settings.NOTION_DATA_SOURCE_ID:
        _CACHED_DATA_SOURCE_ID = settings.NOTION_DATA_SOURCE_ID.strip()
        return _CACHED_DATA_SOURCE_ID or None

    if _CACHED_DATA_SOURCE_ID:
        return _CACHED_DATA_SOURCE_ID

    # Descobre data_source_id via GET /v1/databases/{db}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://api.notion.com/v1/databases/{settings.NOTION_DB_ID.strip()}",
                headers=_headers_notion(),
            )
            r.raise_for_status()
            data_sources = (r.json() or {}).get("data_sources", [])
            if data_sources:
                _CACHED_DATA_SOURCE_ID = data_sources[0].get("id")
                return _CACHED_DATA_SOURCE_ID
    except Exception as e:
        print("⚠️ Notion data_source discovery failed:", e)
    return None


async def notion_search_by_email(email: str) -> List[dict]:
    payload = {
        "filter": {"property": "Email", "email": {"equals": email.strip().lower()}},
        "page_size": 1,
    }
    data_source_id = await _get_data_source_id()
    async with httpx.AsyncClient(timeout=10) as client:
        if data_source_id:
            r = await client.post(
                f"https://api.notion.com/v1/data_sources/{data_source_id.strip()}/query",
                headers=_headers_notion(),
                json=payload,
            )
        else:
            # Fallback legacy (single-source dbs may still work)
            r = await client.post(
                f"https://api.notion.com/v1/databases/{settings.NOTION_DB_ID.strip()}/query",
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
    data_source_id = await _get_data_source_id()
    parent: dict
    if data_source_id:
        parent = {"data_source_id": data_source_id.strip()}
    else:
        parent = {"database_id": settings.NOTION_DB_ID.strip()}

    payload = {
        "parent": parent,
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
async def send_whatsapp_message(name: str, email: str, phone: str, novo: bool, fim_contrato_text: str | None = None) -> None:
    numero = limpar_telefone(phone)
    if len(numero) != 11:
        print(f"⚠️ Telefone inválido: {numero}")
        return

    first_name = (name or "").strip().split(" ")[0] if name else ""

    if novo:
        msg = (
            f"Welcome {first_name}! 🎉 Parabéns pela excelente decisão!\n\n"
            "Sou Marcelo, seu ponto de contato para qualquer dúvida.\n"
            f"Seu e-mail cadastrado é {email}. Prefere usar outro?\n\n"
            "Vou precisar de duas fotos suas...\n\n"
            "Uma foto de perfil (somente o rosto) "
            "e uma foto inspiração. Essa foto inspiração pode ser algo que represente "
            "o motivo de você querer aprender inglês. Vamos usar essa foto no seu espaço do aluno em nosso aplicativo."
        )
    else:
        corpo_base = (
            f"Hey, {first_name}. Parabéns pela excelente decisão de renovar seu contrato rumo a meta de atingir a fluência. "
            "Lembre-se que apenas 3% da população brasileira falam Inglês fluente e você está mostrando que é capaz de entrar para essa estatistica. "
            "Conte com a gente nesse trajetória."
        )
        if (fim_contrato_text or "").strip():
            msg = (
                f"{corpo_base} "
                f"Seu novo contrato se encerra no dia: {fim_contrato_text.strip()}. "
                "See you!"
            )
        else:
            msg = corpo_base + " See you!"

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
        print(f"🔍 Buscando cliente no Asaas: {data['email']}")
        r = await client.get(f"{settings.ASAAS_BASE}/customers", headers=headers, params={"email": data["email"]})
        print(f"📡 Status busca cliente: {r.status_code}")
        if r.status_code != 200:
            print(f"❌ Erro ao buscar cliente: {r.text}")
        r.raise_for_status()
        clientes = r.json().get("data", [])
        if clientes:
            customer_id = clientes[0]["id"]
            print(f"✅ Cliente encontrado: {customer_id}")
        else:
            payload = {
                "name": data["nome"],
                "email": data["email"],
                "mobilePhone": limpar_telefone(data["telefone"]),
                "cpfCnpj": re.sub(r"\D", "", data["cpf"]),
            }
            print(f"👤 Criando cliente: {payload}")
            r = await client.post(f"{settings.ASAAS_BASE}/customers", headers=headers, json=payload)
            print(f"📡 Status criação cliente: {r.status_code}")
            if r.status_code != 200:
                print(f"❌ Erro ao criar cliente: {r.text}")
            r.raise_for_status()
            customer_id = r.json()["id"]
            print(f"✅ Cliente criado: {customer_id}")

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
            "nextDueDate": iso_or_brazil(data.get("vencimento")),   # ← Corrigido aqui
            "endDate":     iso_or_brazil(data.get("fim_pagamento")),# ← Corrigido aqui
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
