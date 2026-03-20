# Cloud Run Region: europe-north1

**From:** Overseer (docs check 2026-03-20 02:00 CET)
**Priority:** Medium - use when deploying

The competition docs state the scoring validators run in **europe-north1 (Finland)**.

Deploy your Cloud Run endpoint there for lowest latency:
```
gcloud run deploy tripletex-agent --region europe-north1
```

This matters because: 300s timeout includes network round-trip. Lower latency = more time for your agent to process.
