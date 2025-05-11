# ~/Downloads/OnboardingKarol/main.py

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from helpers import (
    notion_search_by_email,
    notion_create_page,
    send_whatsapp_message,
    criar_assinatura_asaas,
    map_pacote,
)

app = FastAPI()
processed_tokens: set[str] = set()


class Answer(BaseModel):
    variable: str
    value: str


class Signer(BaseModel):
    name: str
    email: str
    phone_country: str
    phone_number: str


class WebhookPayload(BaseModel):
    token: str
    status: str
    answers: List[Answer]
    signer_who_signed: Signer


@app.get("/")
async def health():
    return {"status": "ok"}


@app.post("/webhook/zapsign", status_code=204)
async def zapsign_webhook(payload: WebhookPayload):
    # idempotência
    if payload.token in processed_tokens:
        return
    processed_tokens.add(payload.token)

    if payload.status != "signed":
        return

    email = payload.signer_who_signed.email.strip().lower()
    name = payload.signer_who_signed.name.strip()
    phone = f"{payload.signer_who_signed.phone_country}{payload.signer_who_signed.phone_number}"

    respostas = {a.variable.lower(): a.value for a in payload.answers}

    encontrados = await notion_search_by_email(email)
    aluno_existe = bool(encontrados)
    print("Aluno já existe no Notion:", aluno_existe)

    await send_whatsapp_message(name, email, phone, not aluno_existe)

    if not aluno_existe:
        pacote = map_pacote(respostas)
        await notion_create_page({
            "name": name,
            "email": email,
            "telefone": phone,
            "cpf": respostas.get("cpf", ""),
            "pacote": pacote,
            "inicio": respostas.get("data do primeiro  pagamento", ""),
            "fim": respostas.get("data último pagamento", ""),
        })

    await criar_assinatura_asaas({
        "nome": name,
        "email": email,
        "telefone": phone,
        "cpf": respostas.get("cpf", ""),
        "valor": respostas.get("r$valor das parcelas", "0"),
        "vencimento": respostas.get("data do primeiro  pagamento", ""),
        "fim_pagamento": respostas.get("data último pagamento", ""),
    })
