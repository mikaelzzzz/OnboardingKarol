from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List
from helpers import (
    notion_search_by_email,
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

    try:
        email = payload.signer_who_signed.email
        name = payload.signer_who_signed.name
        phone = f"{payload.signer_who_signed.phone_country}{payload.signer_who_signed.phone_number}"

        respostas = {a.variable.lower(): a.value for a in payload.answers}

        # 1️⃣ Verifica se o aluno já existe no Notion
        aluno_ja_existe = await notion_search_by_email(email)
        print("Aluno já existe no Notion:", bool(aluno_ja_existe))

        # 2️⃣ Envia mensagem via Z-API
        await send_whatsapp_message(name, email, phone, not aluno_ja_existe)
        print("Mensagem enviada")

        # 3️⃣ Cria assinatura no Asaas
        await criar_assinatura_asaas({
            "nome": name,
            "email": email,
            "telefone": phone,
            "cpf": respostas.get("cpf", ""),
            "valor": respostas.get("r$valor das parcelas", "0"),
            "vencimento": respostas.get("data do primeiro  pagamento", ""),
            "fim_pagamento": respostas.get("data último pagamento", "")
        })
        print("Assinatura criada")

    except Exception as e:
        print("Erro no webhook:", e)
        # Não retorna erro para o ZapSign
        return
