#!/bin/bash
# Google Cloud Run Setup Script for OnboardingKarol
# Run this script after enabling billing on the project

set -e

PROJECT_ID="onboarding-karol-prod"
REGION="southamerica-east1"
SERVICE_NAME="onboarding-karol"
REPOSITORY="onboarding-karol"

echo "🚀 Setting up Google Cloud Run for OnboardingKarol"
echo "=================================================="

# Set project
echo "📦 Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com

# Create Artifact Registry repository
echo "📦 Creating Artifact Registry repository..."
gcloud artifacts repositories create $REPOSITORY \
  --repository-format=docker \
  --location=$REGION \
  --description="Docker repository for OnboardingKarol" \
  || echo "Repository already exists, skipping..."

# Configure Docker authentication
echo "🔐 Configuring Docker authentication..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev

echo ""
echo "✅ Infrastructure setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Create secrets in Secret Manager (run: ./create-secrets.sh)"
echo "2. Deploy the service (run: ./deploy.sh)"
echo "3. Or set up GitHub Actions for automatic deployments"
echo ""

