# Quick Start: Google Cloud Run Deployment

## First Time Setup (5 Steps)

### 1. Enable Billing
```bash
# Go to: https://console.cloud.google.com/billing
# Link billing account to project: onboarding-karol-prod
```

### 2. Setup Infrastructure
```bash
./deploy-setup.sh
```

### 3. Create Secrets
```bash
./create-secrets.sh
```
Enter your environment variables when prompted.

### 4. Deploy
```bash
./deploy.sh
```

### 5. Update Webhooks
Use the service URL from deploy output to update:
- Zapsign webhook: `https://[SERVICE-URL]/webhook/zapsign`

## GitHub Actions Automation

### One-Time Setup
```bash
./setup-github-actions.sh
```

Copy the two secrets shown and add them to GitHub:
- Settings > Secrets > Actions > New repository secret

### Automatic Deployments
After setup, every push to `main` deploys automatically!

## Common Commands

### View Logs
```bash
gcloud run services logs tail onboarding-karol --region=southamerica-east1
```

### Get Service URL
```bash
gcloud run services describe onboarding-karol \
  --region=southamerica-east1 \
  --format='value(status.url)'
```

### Update Secret
```bash
echo "NEW_VALUE" | gcloud secrets versions add SECRET_NAME --data-file=-
```

### Redeploy
```bash
./deploy.sh
```

## Monitoring

- **Dashboard**: https://console.cloud.google.com/run/detail/southamerica-east1/onboarding-karol
- **Logs**: https://console.cloud.google.com/logs
- **Billing**: https://console.cloud.google.com/billing

## Need Help?

See full documentation: [CLOUD_RUN_DEPLOYMENT.md](./CLOUD_RUN_DEPLOYMENT.md)

