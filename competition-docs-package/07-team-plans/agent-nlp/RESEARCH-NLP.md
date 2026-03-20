# RESEARCH-NLP.md — Tripletex AI Accounting Agent

**Track:** NLP (Task 1)
**Agent:** agent-nlp
**Date:** 2026-03-19 (Opus refresh at T+2.5h)
**Status:** Phase 2 RESEARCH — OPUS VALIDATED

---

## Problem Type
Build an HTTPS API endpoint that receives accounting task prompts (text + optional PDF/image attachments) in 7 languages and executes them against the Tripletex API. Field-by-field scoring + efficiency bonus. 30 task types × 56 variants = 1,680 total.

## Key Parameters
| Parameter | Value |
|-----------|-------|
| Task types | 30 |
| Variants per task | 56 (7 languages × 8 datasets) |
| Languages | Norwegian, English, Spanish, Portuguese, Nynorsk, German, French |
| Timeout | 300s (5 min) per submission |
| Score range | 0.0 (failed) to 6.0 (perfect Tier 3 + best efficiency) |
| Scoring | Field-by-field accuracy + efficiency bonus |
| API | Tripletex v2 REST via authenticated proxy |
| Sandbox | Fresh Tripletex account per submission |

## Architecture: Agent Pipeline

```
[Platform] → POST /solve (task prompt + attachments)
    ↓
[1. Parse] Extract task intent, entities, language
    ↓
[2. Plan] Map to Tripletex API sequence
    ↓
[3. Execute] Call Tripletex API endpoints
    ↓
[4. Verify] Read back created data, confirm fields
    ↓
[5. Respond] Return completion status
```

## SOTA Resources

### 1. Official Tripletex API v2 ⭐
- **Source:** https://github.com/Tripletex/tripletex-api2
- **Docs:** https://tripletex.no/v2-docs/ (or per-sandbox URL)
- **Match:** 100% — Official examples, auth patterns, all endpoints
- **License:** MIT
- **Key endpoints:**
  - `/v2/employee` — Create/update employees
  - `/v2/customer` — Register customers
  - `/v2/product` — Create products
  - `/v2/invoice` — Create invoices, register payments
  - `/v2/travelExpense` — Travel expense reports
  - `/v2/project` — Create projects
  - `/v2/department` — Department management

### 2. PyPI `tripletex` Package
- **Package:** `pip install tripletex`
- **Features:** Higher-level abstractions, PostingService
- **Match:** 90% — handles auth + common CRUD
- **Risk:** May not cover all 30 task types; check coverage

### 3. MCP Docs Server (Competition-Provided)
- **Setup:** `claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp`
- **Purpose:** AI-assisted development with competition docs
- **Use for:** Exploring exact API schemas, task format, scoring details

## Task Categories (30 Types)

### Employees (5-6 task types)
- Create employee with personal details
- Set employment type/role
- Update contact info (email, phone, address)
- Add bank account details
- Set holiday allowance / working hours

### Customers & Products (4-5 task types)
- Register new customer (company/person)
- Create product with pricing
- Set customer credit terms
- Link products to categories

### Invoicing (6-8 task types)
- Create invoice for customer
- Add invoice lines (products, quantities, VAT)
- Register payment on invoice
- Issue credit note
- Create recurring invoice

### Travel Expenses (3-4 task types)
- Register travel expense report
- Add expense items (transport, meals, accommodation)
- Delete expense reports
- Set per diem rates

### Projects (3-4 task types)
- Create project linked to customer
- Set project budget/timeline
- Add project members
- Configure project invoicing

### Corrections (2-3 task types)
- Delete incorrect entries
- Reverse/credit existing transactions
- Correct employee/customer data

### Departments (2-3 task types)
- Create departments
- Enable accounting modules
- Set department manager

## Approach Recommendations

### Approach A (Primary): LLM Router + Structured API Calls
1. **Task Classifier:** Use Gemini 1.5 Pro to parse prompt → identify task type + extract fields
2. **Field Extractor:** Structured output (JSON) from LLM with all required fields
3. **API Executor:** Hardcoded API call templates per task type, fill with extracted fields
4. **Language Handling:** Gemini handles all 7 languages natively
5. **PDF/Image:** Use Gemini Vision for attachment processing
6. **Verification:** Read-back created resources, compare to expected fields
7. **Time:** 4-6 hours
8. **Expected Score:** 4.0-5.0 (out of 6.0)

### Approach B (Fallback): Rule-Based + LLM Hybrid
1. Regex/keyword matching for top 15 task types (Norwegian + English)
2. LLM fallback for remaining types and non-English/Norwegian languages
3. Simpler but covers most common cases
4. **Time:** 2-3 hours
5. **Expected Score:** 2.5-3.5

### Approach C (Baseline — MUST SHIP FIRST): Top-5 Tasks Only
1. Implement only: Create Employee, Create Customer, Create Product, Create Invoice, Register Payment
2. Simple prompt parsing (look for keywords)
3. Hardcoded API call sequence
4. Norwegian + English only
5. **Time:** 1-2 hours
6. **Expected Score:** 1.0-2.0
7. **Purpose:** Valid submission, guaranteed points

## Scoring Deep Dive

### Field-by-Field Accuracy
- Each task has expected output fields (e.g., employee name, email, salary)
- Score based on how many fields match expected values
- **Precision > Recall:** Incorrect fields penalized more than missing fields
- **Implication:** Better to skip uncertain fields than guess wrong

### Efficiency Bonus
- Faster completion = higher score
- Tier system: completing more complex tasks correctly → higher tier → higher max score
- **Implication:** Simple task done perfectly > complex task done poorly

### Score Tiers
- **Tier 1:** Basic CRUD (employees, customers) — max ~2.0
- **Tier 2:** Intermediate (invoicing, projects) — max ~4.0
- **Tier 3:** Advanced (corrections, multi-step) — max ~6.0

## Critical Implementation Notes

### Authentication
```python
# Tripletex API auth via proxy
# Platform provides session token in /solve request
# Use token in Authorization header for all API calls
```

### Norwegian-Specific
- Norwegian uses comma as decimal separator (1.000,50 = 1000.50)
- Dates: DD.MM.YYYY format in Norwegian
- VAT rates: 25% (standard), 15% (food), 12% (transport), 0% (exempt)
- Nynorsk vs Bokmål: different vocabularies for same concepts

### PDF/Image Attachments
- Some tasks include scanned receipts, invoices, or documents
- Need OCR capability: Gemini Vision (preferred) or pytesseract
- Extract amounts, dates, vendor names from documents
- **Budget:** Gemini API calls — track token usage

### Endpoint Deployment
- Must deploy HTTPS endpoint accessible from competition platform
- Options: GCP Cloud Run, ngrok tunnel, or direct public IP
- **Recommendation:** GCP Cloud Run (free with competition GCP account)
- **Alternative:** Flask/FastAPI + ngrok if faster to set up

## Ceiling Analysis
- **What separates good from #1:**
  - Coverage of all 30 task types (not just common ones)
  - Accurate field extraction across all 7 languages
  - Correct Norwegian accounting conventions (VAT, date formats)
  - PDF/image processing for attachment-based tasks
  - Fast execution for efficiency bonus
- **Theoretical ceiling:** 5.5-6.0
- **Realistic ceiling:** 4.0-5.0

## Next Steps (Priority Order)
1. Set up HTTPS endpoint (Cloud Run or ngrok + FastAPI)
2. Connect to Tripletex sandbox API, verify authentication
3. Implement Approach C (top 5 task types) — submit within 2h
4. Add Gemini-powered task classifier + field extractor
5. Expand to all 30 task types systematically
6. Add PDF/image processing for attachment tasks
7. Add remaining 5 languages (after Norwegian + English work)

## References
- [Tripletex API v2 Docs](https://tripletex.no/v2-docs/)
- [Tripletex GitHub Examples](https://github.com/Tripletex/tripletex-api2)
- [PyPI tripletex](https://pypi.org/project/tripletex/)
- [MCP Docs Server](https://mcp-docs.ainm.no/mcp)
