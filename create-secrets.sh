#!/bin/bash
# Create secrets in Google Secret Manager
# This script prompts for each secret value and creates it in Secret Manager

set -e

PROJECT_ID="onboarding-karol-prod"

echo "🔐 Creating secrets in Google Secret Manager"
echo "============================================="
echo ""
echo "You will be prompted to enter each secret value."
echo "Press Ctrl+C to cancel at any time."
echo ""

# Function to create a secret
create_secret() {
  local secret_name=$1
  local secret_description=$2
  
  echo ""
  echo "Creating secret: $secret_name"
  echo "Description: $secret_description"
  read -p "Enter value for $secret_name: " secret_value
  
  # Create secret if it doesn't exist
  if ! gcloud secrets describe $secret_name --project=$PROJECT_ID &>/dev/null; then
    echo "$secret_value" | gcloud secrets create $secret_name \
      --project=$PROJECT_ID \
      --replication-policy="automatic" \
      --data-file=-
    echo "✅ Secret $secret_name created"
  else
    # Add new version if secret exists
    echo "$secret_value" | gcloud secrets versions add $secret_name \
      --project=$PROJECT_ID \
      --data-file=-
    echo "✅ New version added to secret $secret_name"
  fi
}

# Create all required secrets
create_secret "NOTION_TOKEN" "Notion API integration token"
create_secret "NOTION_DB_ID" "Notion database ID for student records"
create_secret "NOTION_DATA_SOURCE_ID" "Notion data source ID (optional)"
create_secret "NOTION_API_VERSION" "Notion API version (e.g., 2025-09-03)"
create_secret "ZAPI_INSTANCE_ID" "Z-API WhatsApp instance ID"
create_secret "ZAPI_TOKEN" "Z-API authentication token"
create_secret "ZAPI_SECURITY_TOKEN" "Z-API security token"
create_secret "ASAAS_API_KEY" "Asaas payment platform API key"
create_secret "ASAAS_BASE" "Asaas API base URL"
create_secret "CALC_DATABASE_ID" "Notion database ID for contract calculations"
create_secret "FLEXGE_API_KEY" "Flexge API key for student data"
create_secret "WHATSAPP_AUTO_NUMBER" "WhatsApp number for automatic weekly reports"

echo ""
echo "✅ All secrets created successfully!"
echo ""
echo "📝 Next step: Deploy the service (run: ./deploy.sh)"
echo ""

