#!/bin/bash
# Setup GitHub Actions for automated Cloud Run deployments
# This script creates the necessary service account and Workload Identity Federation

set -e

PROJECT_ID="onboarding-karol-prod"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
SERVICE_ACCOUNT_NAME="github-actions-deployer"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
GITHUB_REPO="mikaelzzzz/OnboardingKarol"  # Update if needed
WORKLOAD_IDENTITY_POOL="github-pool"
WORKLOAD_IDENTITY_PROVIDER="github-provider"

echo "🔧 Setting up GitHub Actions for Cloud Run"
echo "==========================================="
echo ""
echo "Project: $PROJECT_ID"
echo "Project Number: $PROJECT_NUMBER"
echo "GitHub Repo: $GITHUB_REPO"
echo ""

# Create service account
echo "👤 Creating service account..."
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
  --display-name="GitHub Actions Deployer" \
  --description="Service account for GitHub Actions to deploy to Cloud Run" \
  --project=$PROJECT_ID \
  || echo "Service account already exists"

# Grant necessary roles
echo "🔐 Granting IAM roles..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/run.admin" \
  --condition=None

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/artifactregistry.writer" \
  --condition=None

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/iam.serviceAccountUser" \
  --condition=None

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None

# Create Workload Identity Pool
echo "🏊 Creating Workload Identity Pool..."
gcloud iam workload-identity-pools create $WORKLOAD_IDENTITY_POOL \
  --project=$PROJECT_ID \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  || echo "Pool already exists"

# Create Workload Identity Provider
echo "🔑 Creating Workload Identity Provider..."
gcloud iam workload-identity-pools providers create-oidc $WORKLOAD_IDENTITY_PROVIDER \
  --project=$PROJECT_ID \
  --location="global" \
  --workload-identity-pool=$WORKLOAD_IDENTITY_POOL \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner == '${GITHUB_REPO%%/*}'" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  || echo "Provider already exists"

# Allow GitHub Actions to impersonate the service account
echo "🎭 Configuring service account impersonation..."
gcloud iam service-accounts add-iam-policy-binding $SERVICE_ACCOUNT_EMAIL \
  --project=$PROJECT_ID \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WORKLOAD_IDENTITY_POOL}/attribute.repository/${GITHUB_REPO}"

# Get the Workload Identity Provider resource name
WORKLOAD_IDENTITY_PROVIDER_PATH="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WORKLOAD_IDENTITY_POOL}/providers/${WORKLOAD_IDENTITY_PROVIDER}"

echo ""
echo "✅ GitHub Actions setup complete!"
echo ""
echo "📝 Add these secrets to your GitHub repository:"
echo "   (Settings > Secrets and variables > Actions > New repository secret)"
echo ""
echo "GCP_WORKLOAD_IDENTITY_PROVIDER:"
echo "$WORKLOAD_IDENTITY_PROVIDER_PATH"
echo ""
echo "GCP_SERVICE_ACCOUNT:"
echo "$SERVICE_ACCOUNT_EMAIL"
echo ""
echo "🔗 GitHub Secrets URL:"
echo "https://github.com/${GITHUB_REPO}/settings/secrets/actions"
echo ""

