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

    email = payload.signer_who_signed.email.strip().lower()
    name  = payload.signer_who_signed.name.strip()
    phone = f"{payload.signer_who_signed.phone_country}{payload.signer_who_signed.phone_number}"

    respostas = {a.variable.lower(): a.value for a in payload.answers}

    # procura aluno
    alunos = await notion_search_by_email(email)
    page_id = alunos[0]["id"] if alunos else None

    # monta propriedades
    props = {
        "name":     name,
        "email":    email,
        "telefone": phone,
        "cpf":      respostas.get("cpf", ""),
        "plano":    map_plano(respostas.get("tipo do pacote", "")),
        "duracao":  map_duracao(respostas.get("tempo de contrato", "")),
        "inicio":   parse_date(respostas.get("data do primeiro  pagamento", "")),
        "fim":      parse_date(respostas.get("data último pagamento", "")),
        "endereco": respostas.get("endereço completo", ""),
    }

    # WhatsApp
    await send_whatsapp_message(name, email, phone, novo=page_id is None)

    # upsert Notion
    await upsert_student(props, page_id)

    # Asaas (mantém como estava)
    await criar_assinatura_asaas({
        "nome":          name,
        "email":         email,
        "telefone":      phone,
        "cpf":           props["cpf"],
        "valor":         respostas.get("r$valor das parcelas", "0"),
        "vencimento":    props["inicio"],
        "fim_pagamento": props["fim"]
    })

