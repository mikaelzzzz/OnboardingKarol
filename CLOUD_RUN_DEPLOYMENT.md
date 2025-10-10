# Google Cloud Run Deployment Guide

## Overview

This guide covers deploying the OnboardingKarol FastAPI application to Google Cloud Run in the São Paulo region (southamerica-east1).

## Prerequisites

1. Google Cloud SDK (`gcloud`) installed
2. Docker installed locally
3. Google Cloud project with billing enabled
4. GitHub repository access (for CI/CD)

## Project Setup

### Project Information
- **Project ID**: `onboarding-karol-prod`
- **Region**: `southamerica-east1` (São Paulo, Brazil)
- **Service Name**: `onboarding-karol`
- **Repository**: `onboarding-karol` (Artifact Registry)

### Required APIs
- Cloud Run API
- Cloud Build API
- Artifact Registry API
- Secret Manager API

## Deployment Methods

### Option 1: Manual Deployment (Recommended for First Time)

#### Step 1: Enable Billing

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select project `onboarding-karol-prod`
3. Go to **Billing** and link a billing account
4. Verify billing is enabled:
   ```bash
   gcloud beta billing projects describe onboarding-karol-prod
   ```

#### Step 2: Run Infrastructure Setup

```bash
./deploy-setup.sh
```

This script will:
- Set the project as default
- Enable required APIs
- Create Artifact Registry repository
- Configure Docker authentication

#### Step 3: Create Secrets

```bash
./create-secrets.sh
```

You'll be prompted to enter values for:
- `NOTION_TOKEN` - Notion API integration token
- `NOTION_DB_ID` - Notion database ID
- `NOTION_DATA_SOURCE_ID` - Notion data source ID
- `NOTION_API_VERSION` - API version (e.g., 2025-09-03)
- `ZAPI_INSTANCE_ID` - Z-API instance ID
- `ZAPI_TOKEN` - Z-API token
- `ZAPI_SECURITY_TOKEN` - Z-API security token
- `ASAAS_API_KEY` - Asaas API key
- `ASAAS_BASE` - Asaas base URL
- `CALC_DATABASE_ID` - Calculation database ID
- `FLEXGE_API_KEY` - Flexge API key
- `WHATSAPP_AUTO_NUMBER` - WhatsApp number for weekly reports

#### Step 4: Deploy the Application

```bash
./deploy.sh
```

This will:
- Build Docker image
- Push to Artifact Registry
- Deploy to Cloud Run
- Output the service URL

### Option 2: Automated Deployment with GitHub Actions

#### Step 1: Setup Workload Identity Federation

```bash
./setup-github-actions.sh
```

This script creates:
- Service account for GitHub Actions
- Workload Identity Pool
- Workload Identity Provider
- Necessary IAM bindings

#### Step 2: Add GitHub Secrets

The script will output two secrets. Add them to your GitHub repository:

1. Go to: `https://github.com/mikaelzzzz/OnboardingKarol/settings/secrets/actions`
2. Click **New repository secret**
3. Add:
   - `GCP_WORKLOAD_IDENTITY_PROVIDER` (from script output)
   - `GCP_SERVICE_ACCOUNT` (from script output)

#### Step 3: Push to Main Branch

Once secrets are configured, any push to the `main` branch will automatically:
1. Build the Docker image
2. Push to Artifact Registry
3. Deploy to Cloud Run
4. Output the service URL in the workflow logs

## Post-Deployment

### Update Webhooks

After deployment, update your Zapsign webhook URL:

1. Get your service URL from deployment output
2. Update Zapsign webhook to: `https://[SERVICE-URL]/webhook/zapsign`

### Test Endpoints

```bash
# Health check
curl https://[SERVICE-URL]/

# Webhook health check
curl https://[SERVICE-URL]/webhook/zapsign

# Test Flexge endpoint (requires authentication)
curl -X POST https://[SERVICE-URL]/lista-flexge-semanal/ \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "5511999999999"}'
```

### View Logs

```bash
# Stream logs
gcloud run services logs tail onboarding-karol --region=southamerica-east1

# View logs in console
# https://console.cloud.google.com/run/detail/southamerica-east1/onboarding-karol/logs
```

### Update Service Configuration

```bash
# Update memory
gcloud run services update onboarding-karol \
  --region=southamerica-east1 \
  --memory=1Gi

# Update max instances
gcloud run services update onboarding-karol \
  --region=southamerica-east1 \
  --max-instances=20

# Update environment variable
gcloud run services update onboarding-karol \
  --region=southamerica-east1 \
  --update-secrets=NEW_SECRET=NEW_SECRET:latest
```

## Monitoring

### Cloud Console
- **Service Dashboard**: https://console.cloud.google.com/run/detail/southamerica-east1/onboarding-karol
- **Logs**: https://console.cloud.google.com/logs
- **Metrics**: https://console.cloud.google.com/monitoring

### Key Metrics to Monitor
- Request count
- Request latency
- Error rate
- Instance count
- Memory usage
- CPU usage

## Cost Optimization

### Current Configuration
- **Min instances**: 0 (scales to zero when idle)
- **Max instances**: 10
- **Memory**: 512Mi
- **CPU**: 1

### Pricing (as of 2025)
- Free tier: 2 million requests/month
- After free tier: ~$0.00002400 per request
- Memory: $0.00000250 per GB-second
- CPU: $0.00002400 per vCPU-second

### Tips
1. Keep min instances at 0 for cost savings
2. Use Secret Manager for sensitive data (first 6 secret versions are free)
3. Enable Cloud Run request logs only when debugging
4. Monitor usage in Billing dashboard

## Troubleshooting

### Build Fails
```bash
# Check build logs
gcloud builds list --limit=5
gcloud builds log [BUILD_ID]
```

### Deployment Fails
```bash
# Check service status
gcloud run services describe onboarding-karol --region=southamerica-east1

# Check IAM permissions
gcloud projects get-iam-policy onboarding-karol-prod
```

### Secret Access Issues
```bash
# Verify secret exists
gcloud secrets list

# Check secret permissions
gcloud secrets get-iam-policy [SECRET_NAME]
```

### Container Issues
```bash
# Test locally
docker build -t test-image .
docker run -p 8080:8080 -e NOTION_TOKEN=xxx test-image

# Check container logs
gcloud run services logs read onboarding-karol --region=southamerica-east1 --limit=50
```

## Rollback

If a deployment fails, rollback to previous revision:

```bash
# List revisions
gcloud run revisions list --service=onboarding-karol --region=southamerica-east1

# Rollback to specific revision
gcloud run services update-traffic onboarding-karol \
  --region=southamerica-east1 \
  --to-revisions=[REVISION_NAME]=100
```

## Security Best Practices

1. **Secrets**: Always use Secret Manager, never commit secrets to Git
2. **IAM**: Follow principle of least privilege
3. **Authentication**: Enable IAM authentication for internal services
4. **HTTPS**: Cloud Run provides automatic HTTPS
5. **Audit Logs**: Enable and monitor audit logs

## Support

- **Google Cloud Support**: https://cloud.google.com/support
- **Cloud Run Documentation**: https://cloud.google.com/run/docs
- **GitHub Issues**: https://github.com/mikaelzzzz/OnboardingKarol/issues

