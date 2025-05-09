# ~/Downloads/OnboardingKarol/main.py

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from helpers import (
    notion_search_by_email,
    notion_create_page,
    send_whatsapp_message,
    criar_assinatura_asaas,
)

app = FastAPI()

@app.get("/")
async def health():
    return {"status": "ok"}

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

@app.post("/webhook/zapsign", status_code=204)
async def zapsign_webhook(payload: WebhookPayload):
    if payload.status != "signed":
        return

    email = payload.signer_who_signed.email
    name = payload.signer_who_signed.name
    phone = f"{payload.signer_who_signed.phone_country}{payload.signer_who_signed.phone_number}"

    # Transforma respostas em dicionário
    respostas = {a.variable.lower().strip(): a.value.strip() for a in payload.answers}

    aluno_ja_existe = await notion_search_by_email(email)
    print("Aluno já existe no Notion:", bool(aluno_ja_existe))

    await send_whatsapp_message(name, email, phone, not aluno_ja_existe)

    if not aluno_ja_existe:
        plano_convertido = {
            "vip": "VIP",
            "light": "Light",
            "flexge + conversação com nativos": "Conversação com nativos e Flexge"
        }.get(respostas.get("tipo do pacote, escrever “vip” ou “light” ou “flexge + conversação com nativos", "").lower(), "—")

        await notion_create_page({
            "name": name,
            "email": email,
            "telefone": phone,
            "cpf": respostas.get("cpf", ""),
            "pacote": plano_convertido,
            "inicio": respostas.get("data do primeiro  pagamento", ""),
            "fim": respostas.get("data último pagamento", "")
        })

    await criar_assinatura_asaas({
        "nome": name,
        "email": email,
        "telefone": phone,
        "cpf": respostas.get("cpf", ""),
        "valor": respostas.get("r$valor das parcelas", "0"),
        "vencimento": respostas.get("data do primeiro  pagamento", ""),
        "fim_pagamento": respostas.get("data último pagamento", "")
    })
