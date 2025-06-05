# ~/Downloads/OnboardingKarol/main.py
# Versão corrigida — sem duplicidade, com Plano/Tempo e datas normalizadas

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

from helpers import (
    send_whatsapp_message,
    criar_assinatura_asaas,
    map_plano,
    map_duracao,
    formatar_data,
    notion_search_by_email,
    upsert_student,
)

app = FastAPI()


# ─────────────────────────── HEALTHCHECK ────────────────────────────
@app.get("/")
async def health():
    return {"status": "ok"}


# ─────────────────────────── Pydantic Models ────────────────────────
class Answer(BaseModel):
    variable: str
    value: str


class Signer(BaseModel):
    name: str
    email: str
    phone_country: str
    phone_number: str


class WebhookPayload(BaseModel):
    status: str
    answers: List[Answer]
    signer_who_signed: Signer


# ─────────────────────────── WEBHOOK ────────────────────────────────
@app.post("/webhook/zapsign", status_code=204)
async def zapsign_webhook(payload: WebhookPayload):
    # processa só quando o documento estiver assinado
    if payload.status != "signed":
        return

    # ── dados principais ────────────────────────────────────────────
    email = payload.signer_who_signed.email.strip().lower()
    name = payload.signer_who_signed.name.strip()
    phone = (
        f"{payload.signer_who_signed.phone_country}"
        f"{payload.signer_who_signed.phone_number}"
    )

    # respostas do ZapSign → dict em lowercase
    respostas = {a.variable.lower(): a.value for a in payload.answers}

    # ── aluno já existe? ────────────────────────────────────────────
    alunos = await notion_search_by_email(email)
    is_novo = len(alunos) == 0

    # ── monta propriedades para Notion / Asaas ──────────────────────
    props = {
        "name": name,
        "email": email,
        "telefone": phone,
        "cpf": respostas.get("cpf", ""),
        "pacote": map_plano(respostas.get("tipo do pacote", "")),
        "duracao": map_duracao(respostas.get("tempo de contrato", "")),
        "inicio": formatar_data(respostas.get("data do primeiro  pagamento", "")),
        "fim": formatar_data(respostas.get("data último pagamento", "")),
        "endereco": respostas.get("endereço completo", ""),
    }

    # ── WhatsApp ────────────────────────────────────────────────────
    await send_whatsapp_message(name, email, phone, novo=is_novo)

    # ── Notion (upsert) ────────────────────────────────────────────
    await upsert_student(props)

    # ── Asaas (cliente + assinatura idempotente) ───────────────────
    await criar_assinatura_asaas(
        {
            "nome": name,
            "email": email,
            "telefone": phone,
            "cpf": props["cpf"],
            "valor": respostas.get("r$valor das parcelas", "0"),
            "vencimento": props["inicio"],
            "fim_pagamento": props["fim"],
        }
    )
