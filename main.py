# ~/Downloads/OnboardingKarol/main.py
# Versão 2025-06-05 d — agora preenche Plano robusto, Tempo de contrato,


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
    phone = f"{payload.signer_who_signed.phone_country}{payload.signer_who_signed.phone_number}"

    # coloca respostas em dict minúsculo
    respostas = {a.variable.lower(): a.value for a in payload.answers}

    # ── PLANOS & DURAÇÃO (captura flexível) ─────────────────────────
    pacote_raw = (
        next((v for k, v in respostas.items() if "tipo do pacote" in k), "")  # campo normal
        or next((v for v in respostas.values() if map_plano(v)), "")          # valor detectado
    )
    duracao_raw = (
        next((v for k, v in respostas.items() if "tempo de contrato" in k), "")
        or next((v for v in respostas.values() if map_duracao(v)), "")
    )

    # ── DATA DE NASCIMENTO ──────────────────────────────────────────
    nascimento_raw = respostas.get("data de nascimento", "")

    # ── aluno já existe? ────────────────────────────────────────────
    is_novo = not (await notion_search_by_email(email))

    # ── monta propriedades para Notion / Asaas ──────────────────────
    props = {
        "name":       name,
        "email":      email,
        "telefone":   phone,
        "cpf":        respostas.get("cpf", ""),
        "pacote":     map_plano(pacote_raw),
        "duracao":    map_duracao(duracao_raw),
        "inicio":     formatar_data(respostas.get("data do primeiro  pagamento", "")),
        "fim":        formatar_data(respostas.get("data último pagamento", "")),
        "nascimento": formatar_data(nascimento_raw),
        "endereco":   respostas.get("endereço completo", ""),
    }

    # ── WhatsApp ────────────────────────────────────────────────────
    await send_whatsapp_message(name, email, phone, novo=is_novo)

    # ── Notion (upsert) ────────────────────────────────────────────
    await upsert_student(props)

    # ── Asaas (cliente + assinatura idempotente) ───────────────────
    await criar_assinatura_asaas(
        {
            "nome":          name,
            "email":         email,
            "telefone":      phone,
            "cpf":           props["cpf"],
            "valor":         respostas.get("r$valor das parcelas", "0"),
            "vencimento":    props["inicio"],
            "fim_pagamento": props["fim"],
        }
    )
