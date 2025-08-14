# ~/Downloads/OnboardingKarol/main.py
# Versão 2025-06-06 — revisada, envia datas brutas ao Asaas.

import re
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
        r"data\s+(?:do\s+)?último\s+pagamento": "data último pagamento",   # ← melhoria
        r"r\$valor das parcelas": "r$valor da parcela",
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
    # Pagamento (para Asaas)
    vencimento_pagamento_raw = respostas.get("data do primeiro pagamento", "")
    fim_pagamento_raw = respostas.get("data último pagamento", "")

    # Contrato (para Notion), com fallback para data de pagamento
    inicio_contrato_raw = respostas.get("data inicio do contrato", vencimento_pagamento_raw)
    fim_contrato_raw = respostas.get("data do término do contrato", fim_pagamento_raw)

    inicio_contrato = formatar_data(inicio_contrato_raw)
    fim_contrato = formatar_data(fim_contrato_raw)

    if not inicio_contrato:
        print(f"❌ Início de contrato (Notion) faltando ou inválido: '{inicio_contrato_raw}'")
    if not fim_contrato:
        print(f"❌ Fim de contrato (Notion) faltando ou inválido: '{fim_contrato_raw}'")

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
        "inicio":     inicio_contrato,
        "fim":        fim_contrato,
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
            "valor":         respostas.get("r$valor da parcela", "0"),
            "vencimento":    vencimento_pagamento_raw,
            "fim_pagamento": fim_pagamento_raw,
        }
    )
