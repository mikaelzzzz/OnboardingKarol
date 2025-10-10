#!/bin/bash
# Deploy OnboardingKarol to Google Cloud Run

set -e

PROJECT_ID="onboarding-karol-prod"
REGION="southamerica-east1"
SERVICE_NAME="onboarding-karol"
REPOSITORY="onboarding-karol"
IMAGE_TAG=$(git rev-parse --short HEAD)

echo "🚀 Deploying OnboardingKarol to Google Cloud Run"
echo "================================================="
echo ""
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo "Image Tag: $IMAGE_TAG"
echo ""

# Build the Docker image
echo "🏗️  Building Docker image..."
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:${IMAGE_TAG} \
             -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:latest \
             .

# Push to Artifact Registry
echo "📤 Pushing image to Artifact Registry..."
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:${IMAGE_TAG}
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:latest

# Deploy to Cloud Run
echo "🚢 Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:${IMAGE_TAG} \
  --platform=managed \
  --region=${REGION} \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=10 \
  --memory=512Mi \
  --cpu=1 \
  --set-secrets=NOTION_TOKEN=NOTION_TOKEN:latest,\
NOTION_DB_ID=NOTION_DB_ID:latest,\
NOTION_DATA_SOURCE_ID=NOTION_DATA_SOURCE_ID:latest,\
NOTION_API_VERSION=NOTION_API_VERSION:latest,\
ZAPI_INSTANCE_ID=ZAPI_INSTANCE_ID:latest,\
ZAPI_TOKEN=ZAPI_TOKEN:latest,\
ZAPI_SECURITY_TOKEN=ZAPI_SECURITY_TOKEN:latest,\
ASAAS_API_KEY=ASAAS_API_KEY:latest,\
ASAAS_BASE=ASAAS_BASE:latest,\
CALC_DATABASE_ID=CALC_DATABASE_ID:latest,\
FLEXGE_API_KEY=FLEXGE_API_KEY:latest,\
WHATSAPP_AUTO_NUMBER=WHATSAPP_AUTO_NUMBER:latest

# Get service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
  --platform=managed \
  --region=${REGION} \
  --format='value(status.url)')

echo ""
echo "✅ Deployment successful!"
echo ""
echo "🌐 Service URL: $SERVICE_URL"
echo ""
echo "📝 Update your Zapsign webhook to:"
echo "   ${SERVICE_URL}/webhook/zapsign"
echo ""
echo "🧪 Test endpoints:"
echo "   GET  ${SERVICE_URL}/"
echo "   GET  ${SERVICE_URL}/webhook/zapsign"
echo "   POST ${SERVICE_URL}/lista-flexge-semanal/"
echo "   POST ${SERVICE_URL}/calculo/executar"
echo ""

