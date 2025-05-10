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
    # só seguimos quando assinado
    if payload.status != "signed":
        return

    name = payload.signer_who_signed.name
    email = payload.signer_who_signed.email
    phone = f"{payload.signer_who_signed.phone_country}{payload.signer_who_signed.phone_number}"

    # converte lista de Answer em dict
    respostas = {a.variable.lower(): a.value for a in payload.answers}

    # 1) Verifica no Notion
    existe = await notion_search_by_email(email)
    print("Aluno já existe no Notion:", bool(existe))

    # 2) Envia mensagem de boas-vindas ou renovação
    await send_whatsapp_message(name, email, phone, not existe)

    # 3) Se for novo aluno, cria página no Notion
    if not existe:
        await notion_create_page({
            "name": name,
            "email": email,
            "telefone": phone,
            "cpf": respostas.get("cpf", ""),
            "inicio": respostas.get("data do primeiro  pagamento", ""),
            "fim": respostas.get("data último pagamento", "")
        })

    # 4) Cria assinatura no Asaas
    await criar_assinatura_asaas({
        "nome": name,
        "email": email,
        "telefone": phone,
        "cpf": respostas.get("cpf", ""),
        "valor": respostas.get("r$valor das parcelas", "0"),
        "vencimento": respostas.get("data do primeiro  pagamento", ""),
        "fim_pagamento": respostas.get("data último pagamento", "")
    })
