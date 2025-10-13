#!/bin/bash
# Setup Cloud Scheduler for weekly Flexge list execution
# Executes every Monday at 8:00 AM São Paulo time

set -e

PROJECT_ID="onboarding-karol-prod"
REGION="southamerica-east1"
SERVICE_URL="https://onboarding-karol-526882424199.southamerica-east1.run.app"
SCHEDULER_LOCATION="southamerica-east1"
JOB_NAME="flexge-lista-semanal"

# Read WhatsApp number from secret
WHATSAPP_NUMBER=$(gcloud secrets versions access latest --secret=WHATSAPP_AUTO_NUMBER --project=$PROJECT_ID)

echo "🕐 Configurando Cloud Scheduler para Lista Flexge Semanal"
echo "=========================================================="
echo ""

# Enable Cloud Scheduler API
echo "🔧 Habilitando Cloud Scheduler API..."
gcloud services enable cloudscheduler.googleapis.com --project=$PROJECT_ID

# Create scheduler job
echo "📅 Criando job agendado..."
gcloud scheduler jobs create http $JOB_NAME \
  --project=$PROJECT_ID \
  --location=$SCHEDULER_LOCATION \
  --schedule="0 8 * * 1" \
  --time-zone="America/Sao_Paulo" \
  --uri="${SERVICE_URL}/lista-flexge-semanal/" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body="{\"phone_number\": \"${WHATSAPP_NUMBER}\"}" \
  --description="Executa lista semanal Flexge toda segunda-feira às 08:00" \
  --attempt-deadline=300s \
  || echo "Job já existe - atualizando..."

# Update existing job if it already exists
gcloud scheduler jobs update http $JOB_NAME \
  --project=$PROJECT_ID \
  --location=$SCHEDULER_LOCATION \
  --schedule="0 8 * * 1" \
  --time-zone="America/Sao_Paulo" \
  --uri="${SERVICE_URL}/lista-flexge-semanal/" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body="{\"phone_number\": \"${WHATSAPP_NUMBER}\"}" \
  --description="Executa lista semanal Flexge toda segunda-feira às 08:00" \
  --attempt-deadline=300s \
  2>/dev/null || true

echo ""
echo "✅ Cloud Scheduler configurado com sucesso!"
echo ""
echo "📋 Detalhes do job:"
echo "   Nome: $JOB_NAME"
echo "   Horário: Toda segunda-feira às 08:00 (São Paulo)"
echo "   URL: ${SERVICE_URL}/lista-flexge-semanal/"
echo "   WhatsApp: ${WHATSAPP_NUMBER}"
echo ""
echo "🧪 Para testar manualmente:"
echo "   gcloud scheduler jobs run $JOB_NAME --location=$SCHEDULER_LOCATION --project=$PROJECT_ID"
echo ""
echo "📊 Ver histórico de execuções:"
echo "   https://console.cloud.google.com/cloudscheduler?project=$PROJECT_ID"
echo ""

