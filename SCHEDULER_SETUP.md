# Configuração do Scheduler Semanal Flexge

## Por Que Mudamos de APScheduler para Cloud Scheduler?

### Problema com APScheduler Interno
- ❌ Cloud Run escala para zero (min instances = 0)
- ❌ Se o container não está rodando às 08:00, o job não executa
- ❌ Não é confiável em ambientes serverless

### Solução: Cloud Scheduler
- ✅ Serviço externo do Google Cloud
- ✅ Chama seu endpoint HTTP automaticamente
- ✅ Garante execução mesmo com scale-to-zero
- ✅ Monitora tentativas e falhas
- ✅ Funciona perfeitamente com Cloud Run

## Configuração (5 minutos)

### Passo 1: Execute o Script de Setup

```bash
cd /Users/mikaelzzzz/Downloads/OnboardingKarol
./setup-cloud-scheduler.sh
```

Isso vai:
1. Habilitar Cloud Scheduler API
2. Criar um job agendado para toda segunda-feira às 08:00 (São Paulo)
3. Configurar para chamar: `POST /lista-flexge-semanal/`
4. Usar o número do WhatsApp do secret `WHATSAPP_AUTO_NUMBER`

### Passo 2: Verificar Criação

```bash
gcloud scheduler jobs describe flexge-lista-semanal \
  --location=southamerica-east1 \
  --project=onboarding-karol-prod
```

## Testar Manualmente

### Executar Agora (Sem Esperar Segunda-feira)

```bash
gcloud scheduler jobs run flexge-lista-semanal \
  --location=southamerica-east1 \
  --project=onboarding-karol-prod
```

### Ou via curl

```bash
curl -X POST https://onboarding-karol-526882424199.southamerica-east1.run.app/lista-flexge-semanal/ \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "5511999999999"}'
```

## Monitoramento

### Ver Histórico de Execuções

**Console:**
https://console.cloud.google.com/cloudscheduler?project=onboarding-karol-prod

**CLI:**
```bash
gcloud scheduler jobs describe flexge-lista-semanal \
  --location=southamerica-east1 \
  --project=onboarding-karol-prod
```

### Ver Logs de Execução

```bash
gcloud run services logs read onboarding-karol \
  --region=southamerica-east1 \
  --limit=50 | grep -i flexge
```

## Modificar o Agendamento

### Alterar Horário

```bash
gcloud scheduler jobs update http flexge-lista-semanal \
  --location=southamerica-east1 \
  --project=onboarding-karol-prod \
  --schedule="0 9 * * 1"  # Muda para 09:00 segunda-feira
```

### Alterar Frequência

```bash
# Duas vezes por semana (segunda e quinta às 08:00)
gcloud scheduler jobs update http flexge-lista-semanal \
  --location=southamerica-east1 \
  --project=onboarding-karol-prod \
  --schedule="0 8 * * 1,4"

# Todo dia útil às 08:00
gcloud scheduler jobs update http flexge-lista-semanal \
  --location=southamerica-east1 \
  --project=onboarding-karol-prod \
  --schedule="0 8 * * 1-5"
```

### Pausar Temporariamente

```bash
gcloud scheduler jobs pause flexge-lista-semanal \
  --location=southamerica-east1 \
  --project=onboarding-karol-prod
```

### Reativar

```bash
gcloud scheduler jobs resume flexge-lista-semanal \
  --location=southamerica-east1 \
  --project=onboarding-karol-prod
```

## Formato de Schedule (Cron)

```
* * * * *
│ │ │ │ │
│ │ │ │ └─── Dia da semana (0-6, 0=Domingo, 1=Segunda)
│ │ │ └───── Mês (1-12)
│ │ └─────── Dia do mês (1-31)
│ └───────── Hora (0-23)
└─────────── Minuto (0-59)
```

**Exemplos:**
- `0 8 * * 1` - Segunda-feira às 08:00
- `0 8 * * 1,5` - Segunda e Sexta às 08:00
- `30 9 * * 1-5` - Todo dia útil às 09:30
- `0 8 1 * *` - Todo dia 1º de cada mês às 08:00

## Custo

### Cloud Scheduler Pricing (2025)
- **Free tier**: 3 jobs gratuitos
- **Após free tier**: $0.10 por job/mês

**Seu caso:**
- 1 job (Flexge semanal)
- **Custo: $0.00/mês** (dentro do free tier)

## Solução de Problemas

### Job Não Executa

1. **Verificar status:**
```bash
gcloud scheduler jobs describe flexge-lista-semanal \
  --location=southamerica-east1 \
  --project=onboarding-karol-prod
```

2. **Ver logs de erro:**
```bash
gcloud logging read "resource.type=cloud_scheduler_job AND resource.labels.job_id=flexge-lista-semanal" \
  --limit=10 \
  --project=onboarding-karol-prod
```

3. **Testar manualmente:**
```bash
gcloud scheduler jobs run flexge-lista-semanal \
  --location=southamerica-east1 \
  --project=onboarding-karol-prod
```

### Erro 403/401 no Endpoint

O Cloud Scheduler precisa de permissão para chamar seu Cloud Run service:

```bash
# Cloud Scheduler usa uma service account padrão que já tem permissões
# Se necessário, adicionar:
gcloud run services add-iam-policy-binding onboarding-karol \
  --region=southamerica-east1 \
  --member=serviceAccount:service-526882424199@gcp-sa-cloudscheduler.iam.gserviceaccount.com \
  --role=roles/run.invoker
```

## Próxima Execução

Para saber quando o job vai executar pela próxima vez:

```bash
gcloud scheduler jobs describe flexge-lista-semanal \
  --location=southamerica-east1 \
  --project=onboarding-karol-prod \
  --format="value(schedule, timeZone)"
```

Será toda **segunda-feira às 08:00** horário de **São Paulo** (America/Sao_Paulo).

