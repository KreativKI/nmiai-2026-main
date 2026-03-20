# NLP Response to Competition Alert (403 + Timeout)

**Time:** 2026-03-21 00:40 CET

## Actions taken

### 1. Timeout fixed: 280s -> 110s
Cloudflare tunnel cuts at 120s. Our deadline was 280s. Fixed to 110s (10s safety margin). Rev 43 deployed.

### 2. BETA endpoints checked
Our recent logs show NO 403s from Tripletex API endpoints (only from expired proxy tokens on concurrent requests). Potentially risky endpoints we use:
- `/salary/type`, `/salary/payslip`, `/salary/transaction` (new, may be BETA)
- `/supplier`, `/supplierInvoice` (new, may be BETA)
- `/travelExpense/cost` (used since v2, no 403s seen)

Core endpoints confirmed working: `/customer`, `/employee`, `/department`, `/product`, `/invoice`, `/project`, `/ledger/account`, `/ledger/vatType`

### 3. Session token handling confirmed
Each submission gets fresh credentials via `tripletex_credentials` in the POST body. We don't cache or reuse tokens between submissions. Token is used only during the single request lifecycle.

## Status
- Rev 43 deployed with timeout fix + new executors
- 180 submissions used (cap hit)
- Waiting for 01:00 CET reset to test if limit refreshes
- Score: 24.5, Rank: #107/307
