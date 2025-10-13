# ~/Downloads/OnboardingKarol/main.py
# Versão 2025-06-06 — revisada, envia datas brutas ao Asaas.

import re
import os
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Any, Dict, Union
import httpx
import requests
from dotenv import load_dotenv
# APScheduler removido - usando Cloud Scheduler externo
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from apscheduler.triggers.cron import CronTrigger
# import pytz

# Carrega variáveis de ambiente do .env
load_dotenv()

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

# ───────────────────── NOTA: SCHEDULER AGORA É EXTERNO ─────────────────────
# APScheduler interno foi removido. Agora usamos Cloud Scheduler (Google Cloud)
# Para configurar: execute ./setup-cloud-scheduler.sh
# Cloud Scheduler chama POST /lista-flexge-semanal/ toda segunda às 08:00

# ─────────────────────────── HEALTHCHECK ────────────────────────────
@app.get("/")
async def health():
    return {"status": "ok"}

# ───────────────────── SCHEDULER REMOVIDO ─────────────────────
# APScheduler interno foi substituído por Cloud Scheduler (Google Cloud)
# O Cloud Scheduler chama POST /lista-flexge-semanal/ automaticamente
# Para configurar, execute: ./setup-cloud-scheduler.sh

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

class WhatsAppRequest(BaseModel):
    phone_number: str

# ─────────────────────────── WEBHOOK ────────────────────────────────
@app.get("/webhook/zapsign")
async def zapsign_webhook_health():
    """Endpoint para o Zapsign verificar se o webhook está funcionando"""
    return {"status": "ok", "message": "Webhook Zapsign está funcionando"}

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
    # Para renovações, enviar mensagem específica com o fim do contrato vindo do Zapsign
    fim_contrato_text = fim_contrato_raw
    await send_whatsapp_message(name, email, phone, novo=is_novo, fim_contrato_text=fim_contrato_text)

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

# ───────────────────── CONFIGURAÇÃO FLEXGE ─────────────────────
# Configuração da API Flexge
api_key_flexge = os.getenv('FLEXGE_API_KEY')
url_flexge = 'https://partner-api.flexge.com/external/students'

# Headers Flexge
headers_flexge = {
    'accept': 'application/json',
    'x-api-key': api_key_flexge
}

# ───────────────────── FUNÇÕES FLEXGE ─────────────────────
def get_last_week_dates():
    """Pega o intervalo da semana anterior (segunda 00:01 até domingo 23:59)"""
    today = datetime.now(timezone.utc)
    last_monday = (today - timedelta(days=today.weekday() + 7)).replace(
        hour=0, minute=1, second=0, microsecond=0
    )
    next_sunday = (last_monday + timedelta(days=6)).replace(
        hour=23, minute=59, second=59, microsecond=0
    )
    return last_monday, next_sunday

def format_time(seconds):
    """Converte segundos em horas e minutos"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{int(hours)}h {int(minutes)}m"

def calcular_tempo_total(aluno):
    """Calcula o tempo total de estudo do aluno"""
    total_studied_time = aluno.get('weekTime', {}).get('studiedTime', 0)
    for execution in aluno.get('executions', []):
        total_studied_time += execution.get('studiedTime', 0)
    return total_studied_time

def obter_dados_alunos():
    """Busca dados dos alunos no intervalo da semana passada"""
    page = 1
    start_date, end_date = get_last_week_dates()
    total_students_data = []

    print(f"🔍 Buscando alunos de {start_date.strftime('%Y-%m-%d %H:%M:%S')} até {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 API Key Flexge: {'✅ Configurada' if api_key_flexge else '❌ Não configurada'}")
    print(f"🌐 URL Flexge: {url_flexge}")

    while True:
        params = {
            'page': page,
            'isPlacementTestOnly': 'false',
            'studiedTimeRange[from]': start_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'studiedTimeRange[to]': end_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
        }
        
        print(f"📄 Página {page} - Parâmetros: {params}")
        response = requests.get(url_flexge, headers=headers_flexge, params=params)
        print(f"📡 Status da resposta: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            students = data.get('docs', [])
            total_docs = data.get('totalDocs', 0)
            
            print(f"📊 Total de docs na resposta: {total_docs}")
            print(f"👥 Alunos nesta página: {len(students)}")
            
            if students:
                for aluno in students:
                    nome = aluno.get('name')
                    total_time_seconds = calcular_tempo_total(aluno)
                    print(f"👤 {nome}: {format_time(total_time_seconds)} ({total_time_seconds}s)")
                    
                    if total_time_seconds >= 3600:
                        total_students_data.append((nome, total_time_seconds))
                        print(f"✅ Adicionado: {nome} - {format_time(total_time_seconds)}")
                    else:
                        print(f"⏰ Tempo insuficiente: {nome} - {format_time(total_time_seconds)}")
                page += 1
            else:
                print("📭 Nenhum aluno nesta página - parando busca")
                break
        else:
            print(f"❌ Erro na API Flexge: {response.status_code}")
            print(f"📝 Resposta: {response.text}")
            break
    
    print(f"🎯 Total de alunos encontrados com +1h: {len(total_students_data)}")
    return total_students_data

def check_student_exists(notion_data, name):
    """Verifica se o aluno já está no Notion"""
    for result in notion_data:
        if result["properties"]["Nome"]["title"][0]["text"]["content"] == name:
            return result["id"]
    return None

def atualizar_ou_criar_notion(alunos):
    """Atualiza ou cria registros no Notion"""
    from helpers import settings, _headers_notion
    
    notion_search_url = f"https://api.notion.com/v1/databases/{settings.NOTION_DB_ID}/query"
    notion_url = 'https://api.notion.com/v1/pages'
    
    response = requests.post(notion_search_url, headers=_headers_notion())
    notion_data = response.json().get("results", [])

    for nome, tempo in alunos:
        page_id = check_student_exists(notion_data, nome)
        formatted_time = format_time(tempo)

        if page_id:
            update_url = f"https://api.notion.com/v1/pages/{page_id}"
            data = {
                "properties": {
                    "Horas de Estudo": {"rich_text": [{"text": {"content": formatted_time}}]}
                }
            }
            response = requests.patch(update_url, headers=_headers_notion(), json=data)
        else:
            data = {
                "parent": {"database_id": settings.NOTION_DB_ID},
                "properties": {
                    "Nome": {"title": [{"text": {"content": nome}}]},
                    "Horas de Estudo": {"rich_text": [{"text": {"content": formatted_time}}]},
                }
            }
            response = requests.post(notion_url, headers=_headers_notion(), json=data)

def enviar_mensagem_whatsapp(alunos, start_date, end_date, phone_number):
    """Envia a mensagem no WhatsApp com a lista de alunos"""
    from helpers import settings
    
    if not alunos:
        return {"status": "Nenhum aluno encontrado para enviar."}

    alunos_ordenados = sorted(alunos, key=lambda x: x[1], reverse=True)
    periodo_formatado = f"{start_date.strftime('%d/%m/%Y')} até {end_date.strftime('%d/%m/%Y')}"
    mensagem = (
        f"📚 Lista de Alunos que estudaram mais de 1 hora no Flexge "
        f"(Semana de {periodo_formatado}):\n\n"
    )
    for i, (nome, tempo) in enumerate(alunos_ordenados, start=1):
        mensagem += f"{i}. {nome} - {format_time(tempo)}\n"

    payload = {
        "phone": phone_number,
        "message": mensagem
    }
    headers_zapi = {
        "Content-Type": "application/json",
        "Client-Token": settings.ZAPI_SECURITY_TOKEN
    }
    zapi_url = f"https://api.z-api.io/instances/{settings.ZAPI_INSTANCE_ID}/token/{settings.ZAPI_TOKEN}/send-text"
    response = requests.post(zapi_url, headers=headers_zapi, json=payload)
    if response.status_code == 200:
        return {"status": "Mensagem enviada com sucesso via WhatsApp!", "response": response.json()}
    else:
        return {"status": "Erro ao enviar mensagem", "details": response.text}

# ───────────────────── ROTAS: CÁLCULO/ATUALIZAÇÃO NO NOTION ─────────────────────

class NotionProp(BaseModel):
    type: str
    value: Union[str, int, float, bool, List[str], None]


class PreencherRequest(BaseModel):
    page_id: str
    properties: Dict[str, NotionProp]


def _montar_props_notion(props: Dict[str, NotionProp]) -> Dict[str, Any]:
    saida: Dict[str, Any] = {}
    for nome, p in props.items():
        t = (p.type or "").lower()
        v = p.value
        if t == "title":
            saida[nome] = {"title": [{"text": {"content": str(v or "")}}]}
        elif t == "rich_text":
            saida[nome] = {"rich_text": [{"text": {"content": str(v or "")}}]}
        elif t == "date":
            saida[nome] = {"date": {"start": str(v or "")}}
        elif t == "number":
            saida[nome] = {"number": float(v) if v is not None else None}
        elif t == "select":
            saida[nome] = {"select": {"name": str(v or "")}}
        elif t == "multi_select":
            nomes = v if isinstance(v, list) else []
            saida[nome] = {"multi_select": [{"name": str(x)} for x in nomes]}
        elif t == "checkbox":
            saida[nome] = {"checkbox": bool(v)}
        elif t == "status":
            saida[nome] = {"status": {"name": str(v or "")}}
        elif t == "url":
            saida[nome] = {"url": str(v or "")}
        elif t == "email":
            saida[nome] = {"email": str(v or "")}
        elif t == "phone_number":
            saida[nome] = {"phone_number": str(v or "")}
        else:
            saida[nome] = {"rich_text": [{"text": {"content": str(v or "")}}]}
    return saida


@app.post("/calculo/preencher")
async def preencher_propriedades(req: PreencherRequest):
    from helpers import _headers_notion  # lazy import para reutilizar versão/token

    body = {"properties": _montar_props_notion(req.properties)}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.patch(
            f"https://api.notion.com/v1/pages/{req.page_id}",
            headers=_headers_notion(),
            json=body,
        )
        if r.status_code == 200:
            return {"status": "ok", "page_id": req.page_id}
        raise HTTPException(status_code=r.status_code, detail=r.text)


class CriarRequest(BaseModel):
    parent_database_id: Union[str, None] = None
    parent_data_source_id: Union[str, None] = None
    properties: Dict[str, NotionProp]


@app.post("/calculo/criar")
async def criar_pagina(req: CriarRequest):
    from helpers import _headers_notion  # reutiliza cabeçalhos/versão

    if not req.parent_data_source_id and not req.parent_database_id:
        raise HTTPException(status_code=400, detail="Informe parent_data_source_id ou parent_database_id")

    parent: Dict[str, str]
    if req.parent_data_source_id:
        parent = {"data_source_id": req.parent_data_source_id}
    else:
        parent = {"database_id": req.parent_database_id or ""}

    body = {
        "parent": parent,
        "properties": _montar_props_notion(req.properties),
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://api.notion.com/v1/pages",
            headers=_headers_notion(),
            json=body,
        )
        if r.status_code == 200:
            data = r.json()
            return {"status": "ok", "page_id": data.get("id")}
        raise HTTPException(status_code=r.status_code, detail=r.text)


# ───────────────────── CÁLCULO DE CONTRATOS (PAUSAS/FERIADOS) ─────────────────────

# Database de cálculo de contratos (separado):
CALC_DATABASE_ID = os.getenv("CALC_DATABASE_ID")

# Pausas (férias) e feriados
pausas = [
    ("2025-07-14", "2025-07-31", "Férias Meio do Ano"),
    ("2025-12-17", "2026-01-09", "Férias Fim de Ano"),
    ("2026-02-16", "2026-02-20", "Carnaval 2026"),
    ("2026-07-15", "2026-07-31", "Férias Meio do Ano"),
    ("2026-12-16", "2027-01-08", "Férias Fim de Ano"),
    ("2027-07-15", "2027-07-31", "Férias Meio do Ano"),
    ("2027-12-15", "2028-01-07", "Férias Fim de Ano"),
    ("2027-02-08", "2027-02-12", "Carnaval 2027"),
]

feriados = [
    ("2025-04-21", "Feriado Tiradentes"),
    ("2025-05-01", "Feriado Dia do Trabalho"),
    ("2025-06-19", "Feriado Corpus Christi"),
    ("2025-11-20", "Feriado Consciência Negra"),
    ("2026-04-21", "Feriado Tiradentes"),
    ("2026-05-01", "Feriado Dia do Trabalho"),
    ("2026-06-19", "Feriado Corpus Christi"),
    ("2026-09-07", "Feriado Dia da Independência"),
    ("2026-10-12", "Feriado Nossa Senhora Aparecida"),
    ("2026-11-02", "Feriado Dia de Finados"),
    ("2026-11-20", "Feriado Consciência Negra"),
    ("2027-04-21", "Feriado Tiradentes"),
    ("2027-09-07", "Feriado Dia da Independência"),
    ("2027-10-12", "Feriado Nossa Senhora Aparecida"),
    ("2027-11-02", "Feriado Dia de Finados"),
    ("2027-11-15", "Feriado Proclamação da República"),
]


async def _get_first_data_source_id(db_id: str) -> str | None:
    from helpers import _headers_notion
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"https://api.notion.com/v1/databases/{db_id}",
            headers=_headers_notion(),
        )
        if r.status_code != 200:
            return None
        return (r.json() or {}).get("data_sources", [{}])[0].get("id")


async def _query_database(db_id: str, payload: Dict[str, Any]) -> List[dict]:
    from helpers import _headers_notion
    ds_id = await _get_first_data_source_id(db_id)
    async with httpx.AsyncClient(timeout=15) as client:
        if ds_id:
            r = await client.post(
                f"https://api.notion.com/v1/data_sources/{ds_id}/query",
                headers=_headers_notion(),
                json=payload,
            )
        else:
            r = await client.post(
                f"https://api.notion.com/v1/databases/{db_id}/query",
                headers=_headers_notion(),
                json=payload,
            )
        if r.status_code != 200:
            print("Erro ao buscar contratos:", r.text)
            return []
        return r.json().get("results", [])


async def buscar_contratos_pendentes() -> List[dict]:
    if not CALC_DATABASE_ID:
        print("⚠️ CALC_DATABASE_ID não definido no ambiente")
        return []
    return await _query_database(CALC_DATABASE_ID, payload={})


def chunk_text_rich_text(long_text: str, chunk_size: int = 2000) -> List[Dict[str, Any]]:
    chunks = [long_text[i : i + chunk_size] for i in range(0, len(long_text), chunk_size)]
    return [{"text": {"content": chunk}} for chunk in chunks]


def calcular_fim_contrato(data_inicio_str: str, duracao_meses: int, dia_aula_str: str):
    data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d")
    data_fim_base = data_inicio + timedelta(days=30 * duracao_meses)
    dias_a_mais = 7

    pausas_consideradas: List[str] = []
    feriados_considerados: List[str] = []

    dias_semana = {"Segunda": 0, "Terça": 1, "Quarta": 2, "Quinta": 3, "Sexta": 4}
    dia_aula_num = dias_semana.get(dia_aula_str, -1)

    for ini_str, fim_str, desc in pausas:
        ini_dt = datetime.strptime(ini_str, "%Y-%m-%d")
        fim_dt = datetime.strptime(fim_str, "%Y-%m-%d")
        overlap_ini = max(data_inicio, ini_dt)
        overlap_fim = min(data_fim_base, fim_dt)
        if overlap_ini <= overlap_fim:
            delta = (overlap_fim - overlap_ini).days + 1
            dias_a_mais += delta
            legenda = f"{ini_dt.strftime('%d/%m/%Y')} a {fim_dt.strftime('%d/%m/%Y')} ({desc})"
            pausas_consideradas.append(legenda)

    for feriado_str, feriado_desc in feriados:
        feriado_dt = datetime.strptime(feriado_str, "%Y-%m-%d")
        if data_inicio <= feriado_dt <= data_fim_base:
            if feriado_dt.weekday() == dia_aula_num:
                dias_a_mais += 1
                feriados_considerados.append(f"{feriado_dt.strftime('%d/%m/%Y')} ({feriado_desc})")

    data_fim = data_fim_base + timedelta(days=dias_a_mais)
    pausas_consideradas.sort()
    feriados_considerados.sort()
    return data_fim.strftime("%Y-%m-%d"), dias_a_mais, pausas_consideradas, feriados_considerados


async def atualizar_notion(page_id: str, data_fim: str, dias_a_mais: int, pausas_consideradas: List[str], feriados_considerados: List[str]):
    from helpers import _headers_notion
    pausas_str = ", ".join(pausas_consideradas)
    feriados_str = ", ".join(feriados_considerados)
    pausas_rich = chunk_text_rich_text(pausas_str)
    feriados_rich = chunk_text_rich_text(feriados_str)

    body = {
        "properties": {
            "Data de Fim do Contrato": {"date": {"start": data_fim}},
            "Dias a mais": {"number": dias_a_mais},
            "Pausas Consideradas": {"rich_text": pausas_rich},
            "Feriados Considerados": {"rich_text": feriados_rich},
            "Calcular data": {"select": {"name": "Finalizado"}},
        }
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=_headers_notion(),
            json=body,
        )
        if r.status_code != 200:
            print("Erro ao atualizar Notion:", r.text)


@app.post("/calculo/executar")
async def executar_calculo():
    contratos = await buscar_contratos_pendentes()
    for contrato in contratos:
        page_id = contrato.get("id")
        prop = contrato.get("properties", {})
        try:
            data_inicio = prop["Data de Início"]["date"]["start"]
            duracao_meses = int(prop["Duração em meses"]["number"])  # type: ignore[arg-type]
            dia_aula = prop["Dia da Semana das aulas"]["select"]["name"]

            data_fim, dias_a_mais, pausas_consideradas, feriados_considerados = calcular_fim_contrato(
                data_inicio, duracao_meses, dia_aula
            )
            await atualizar_notion(page_id, data_fim, dias_a_mais, pausas_consideradas, feriados_considerados)
        except Exception as e:
            print(f"Erro ao processar contrato {page_id}: {e}")
    return {"status": "ok", "message": "Contratos processados com sucesso"}

# ───────────────────── ROTA FLEXGE SEMANAL ─────────────────────
@app.post("/lista-flexge-semanal/")
async def lista_flexge_semanal(request: WhatsAppRequest):
    start_date, end_date = get_last_week_dates()
    alunos = obter_dados_alunos()
    if alunos:
        atualizar_ou_criar_notion(alunos)
        result = enviar_mensagem_whatsapp(alunos, start_date, end_date, request.phone_number)
        return {"notion": "Tabela semanal atualizada.", "whatsapp": result}
    else:
        raise HTTPException(status_code=404, detail="Nenhum aluno com mais de 1 hora de estudo.")

@app.get("/teste-flexge/")
async def teste_flexge():
    """Rota de teste para debugar a API do Flexge"""
    start_date, end_date = get_last_week_dates()
    alunos = obter_dados_alunos()
    
    return {
        "periodo": f"{start_date.strftime('%Y-%m-%d %H:%M:%S')} até {end_date.strftime('%Y-%m-%d %H:%M:%S')}",
        "total_alunos": len(alunos),
        "alunos": [(nome, format_time(tempo)) for nome, tempo in alunos[:10]],  # Primeiros 10
        "api_key_configurada": bool(api_key_flexge),
        "url_flexge": url_flexge
    }
