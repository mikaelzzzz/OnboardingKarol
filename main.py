# ~/Downloads/OnboardingKarol/main.py
# Versão 2025-06-06 — normaliza nomes de variáveis do ZapSign,
# valida datas antes de chamar o Asaas e evita erro de “data de hoje”

import re                                       # ← NOVO
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
    if payload.status != "signed":
        return

    # ── dados principais ────────────────────────────────────────────
    email = payload.signer_who_signed.email.strip().lower()
    name = payload.signer_who_signed.name.strip()
    phone = f"{payload.signer_who_signed.phone_country}{payload.signer_who_signed.phone_number}"

    # respostas → dict minúsculo
    respostas = {a.variable.lower(): a.value for a in payload.answers}

    # ── NORMALIZA ALIAS DAS VARIÁVEIS ───────────────────────────────
    alias_regex = {
        r"data\s+do\s+primeiro\s+pagamento": "data do primeiro pagamento",
        r"data\s+último\s+pagamento":        "data último pagamento",
    }
    for pattern, canonical in alias_regex.items():
        for key in list(respostas):
            if re.fullmatch(pattern, key):
                respostas[canonical] = respostas[key]

    # ── captura plano e duração ─────────────────────────────────────
    pacote_raw = (
        next((v for k, v in respostas.items() if "tipo do pacote" in k), "") or
        next((v for v in respostas.values() if map_plano(v)), "")
    )
    duracao_raw = (
        next((v for k, v in respostas.items() if "tempo de contrato" in k), "") or
        next((v for v in respostas.values() if map_duracao(v)), "")
    )

    # ── datas ───────────────────────────────────────────────────────
    venc_raw = respostas.get("data do primeiro pagamento", "")
    fim_raw  = respostas.get("data último pagamento", "")
    inicio   = formatar_data(venc_raw)
    fim      = formatar_data(fim_raw)

    if not inicio:
        print(f"❌ Vencimento faltando ou inválido: '{venc_raw}'")
    if not fim:
        print(f"❌ Fim de pagamento faltando ou inválido: '{fim_raw}'")

    nascimento_raw = respostas.get("data de nascimento", "")

    # ── aluno já existe? ────────────────────────────────────────────
    is_novo = not (await notion_search_by_email(email))

    # ── monta propriedades (Notion) ─────────────────────────────────
    props = {
        "name":       name,
        "email":      email,
        "telefone":   phone,
        "cpf":        respostas.get("cpf", ""),
        "pacote":     map_plano(pacote_raw),
        "duracao":    map_duracao(duracao_raw),
        "inicio":     inicio,
        "fim":        fim,
        "nascimento": formatar_data(nascimento_raw),
        "endereco":   respostas.get("endereço completo", ""),
    }

    # ── WhatsApp ────────────────────────────────────────────────────
    await send_whatsapp_message(name, email, phone, novo=is_novo)

    # ── Notion (upsert) ────────────────────────────────────────────
    await upsert_student(props)

    # ── Asaas (cliente + assinatura) ───────────────────────────────
    await criar_assinatura_asaas(
        {
            "nome":          name,
            "email":         email,
            "telefone":      phone,
            "cpf":           props["cpf"],
            "valor":         respostas.get("r$valor das parcelas", "0"),
            "vencimento":    inicio,   # já validado; pode estar ""
            "fim_pagamento": fim,      # idem
        }
    )
