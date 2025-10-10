# Migration Status: Render → Google Cloud Run

## ✅ Completed Steps

### 1. Google Cloud Project Created
- **Project ID**: `onboarding-karol-prod`
- **Project Number**: 526882424199
- **Status**: Created and configured

### 2. Containerization Complete
- ✅ `Dockerfile` created with Python 3.11
- ✅ `.dockerignore` configured
- ✅ Application optimized for Cloud Run (port 8080)

### 3. Deployment Scripts Created
- ✅ `deploy-setup.sh` - Infrastructure setup
- ✅ `create-secrets.sh` - Secret Manager configuration
- ✅ `deploy.sh` - Manual deployment
- ✅ `setup-github-actions.sh` - CI/CD automation

### 4. GitHub Actions Workflow
- ✅ `.github/workflows/deploy-cloudrun.yml` created
- ✅ Configured for automatic deployments on push to main
- ✅ Workload Identity Federation setup script ready

### 5. Documentation
- ✅ `CLOUD_RUN_DEPLOYMENT.md` - Full deployment guide
- ✅ `QUICK_START.md` - Quick reference
- ✅ All files committed and pushed to GitHub

## ⏳ Pending Steps (Requires User Action)

### Step 1: Enable Billing ⚠️ REQUIRED
**Why it's blocked**: Google Cloud APIs cannot be enabled without an active billing account.

**Action Required**:
1. Go to https://console.cloud.google.com/billing
2. Select or create a billing account
3. Link it to project: `onboarding-karol-prod`
4. Verify with: `gcloud beta billing projects describe onboarding-karol-prod`

**Cost Estimate**: ~$5-20/month depending on usage (Free tier covers first 2M requests)

### Step 2: Run Infrastructure Setup
Once billing is enabled, run:
```bash
cd /Users/mikaelzzzz/Downloads/OnboardingKarol
./deploy-setup.sh
```

This will:
- Enable required APIs (Cloud Run, Build, Artifact Registry, Secret Manager)
- Create Artifact Registry repository
- Configure Docker authentication

### Step 3: Configure Secrets
Run the secrets creation script:
```bash
./create-secrets.sh
```

You'll need these values from your Render environment:
- NOTION_TOKEN
- NOTION_DB_ID  
- NOTION_DATA_SOURCE_ID
- NOTION_API_VERSION (2025-09-03)
- ZAPI_INSTANCE_ID
- ZAPI_TOKEN
- ZAPI_SECURITY_TOKEN
- ASAAS_API_KEY
- ASAAS_BASE
- CALC_DATABASE_ID
- FLEXGE_API_KEY
- WHATSAPP_AUTO_NUMBER

### Step 4: Initial Deployment
Deploy the application:
```bash
./deploy.sh
```

Expected output:
- Service URL (e.g., https://onboarding-karol-xxxxx.run.app)
- Deployment confirmation

### Step 5: Setup GitHub Actions (Optional but Recommended)
For automated deployments:
```bash
./setup-github-actions.sh
```

Then add the output secrets to GitHub:
https://github.com/mikaelzzzz/OnboardingKarol/settings/secrets/actions

### Step 6: Update Webhooks
Update Zapsign webhook URL to the new Cloud Run service URL:
- Old: https://onboardingkarol.onrender.com/webhook/zapsign
- New: https://[SERVICE-URL]/webhook/zapsign

### Step 7: Test All Endpoints
```bash
SERVICE_URL="https://your-service-url.run.app"

# Health check
curl $SERVICE_URL/

# Webhook health
curl $SERVICE_URL/webhook/zapsign

# Test Flexge (with valid phone number)
curl -X POST $SERVICE_URL/lista-flexge-semanal/ \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "5511975578651"}'
```

### Step 8: Monitor Initial Traffic
- Check Cloud Run logs: https://console.cloud.google.com/run/detail/southamerica-east1/onboarding-karol/logs
- Verify scheduled job runs (Monday 8AM São Paulo time)
- Monitor for any errors in first 24 hours

### Step 9: Decommission Render (After Verification)
Once Cloud Run is stable:
1. Verify all webhooks are working
2. Verify scheduled jobs are running
3. Check logs for 1 week
4. Delete Render service to avoid double billing

## 🔍 Key Differences: Render vs Cloud Run

| Feature | Render | Google Cloud Run |
|---------|--------|------------------|
| Region | US (Oregon) | Brazil (São Paulo) |
| Auto-scaling | Yes | Yes (0 to 10 instances) |
| Cold starts | ~5s | ~2-3s |
| Pricing | $7+/month | $0-20/month (2M free requests) |
| Logs | 7 days | 30 days |
| Secrets | Environment | Secret Manager |
| CI/CD | Auto from Git | GitHub Actions |
| Custom domains | Free | Free |
| Monitoring | Basic | Google Cloud Monitoring |

## 📊 Expected Benefits

1. **Lower Latency**: São Paulo region reduces latency for Brazilian users
2. **Cost Savings**: Free tier + pay-per-use vs fixed monthly cost
3. **Better Scaling**: True serverless with scale-to-zero
4. **Enhanced Monitoring**: Cloud Logging and Monitoring
5. **Improved Security**: Secret Manager integration
6. **Professional CI/CD**: GitHub Actions with Workload Identity

## 🆘 Need Help?

1. **Billing Issues**: Check [CLOUD_RUN_DEPLOYMENT.md](./CLOUD_RUN_DEPLOYMENT.md#troubleshooting)
2. **Deployment Errors**: Run `gcloud run services logs tail onboarding-karol`
3. **Secret Issues**: Verify with `gcloud secrets list`

## 📝 Next Immediate Action

**Enable billing on the Google Cloud project to proceed with deployment.**

Once billing is enabled, the entire deployment can be completed in ~15 minutes by running the provided scripts sequentially.

