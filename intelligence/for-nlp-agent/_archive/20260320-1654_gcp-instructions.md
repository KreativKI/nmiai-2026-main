---
priority: HIGH
from: overseer
timestamp: 2026-03-20 02:10 CET
self-destruct: delete after deploying to Cloud Run and confirming in intelligence/for-overseer/
---

## Deploy Your /solve Endpoint to GCP Cloud Run

The competition platform POSTs to your HTTPS endpoint. Cloud Run is the recommended deployment: free-tier eligible, auto-scaling, built-in HTTPS.

## GCP Details
- Project: `ai-nm26osl-1779`
- Account: `devstar17791@gcplab.me`
- Region: `europe-west1` (recommended, closest to competition servers)
- ADC is set up: use `gcloud` normally
- APIs enabled: aiplatform, compute, generativelanguage, storage

## Deployment Steps
1. Build your FastAPI app into a Docker container
2. Push to Artifact Registry or build with Cloud Build
3. Deploy to Cloud Run:
```
gcloud run deploy tripletex-agent \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --timeout 300
```
4. Register the Cloud Run URL on the competition platform
5. Confirm deployment by writing to intelligence/for-overseer/nlp-deployed.md

## Important
- Endpoint must handle POST /solve within 300 seconds
- Must return {"status": "completed"} with HTTP 200
- Cloud Run auto-scales to zero when idle (cost-efficient)
- Set environment variables for LLM API keys via Cloud Run secrets
