# Rules — Tripletex AI Accounting Agent (NLP Track)

**Task:** AI accounting automation via API  
**Metric:** Field-by-field accuracy + efficiency bonus (0.0-6.0)  
**Deadline:** Sunday 22 March 2026, 15:00 CET  

---

## Mandatory Fields

### Input
- **Task Types:** 30 different accounting tasks
- **Variants:** 56 per task (7 languages × 8 datasets)
- **Languages:** Norwegian, English, Spanish, Portuguese, Nynorsk, German, French
- **Attachments:** Some tasks include PDF/image files
- **Sandbox:** Fresh Tripletex sandbox per submission

### Output
- **Format:** JSON API responses
- **Endpoint:** /solve (HTTPS POST)
- **Delivery:** Platform provisions sandbox, calls our endpoint
- **Timeout:** 300 seconds (5 minutes) per submission

### Scoring
- **Primary:** Field-by-field checks (did we set correct values?)
- **Bonus:** Efficiency (fewer API calls = higher score)
- **Range:** 0.0 (failed) to 6.0 (perfect Tier 3 + best efficiency)
- **Aggregation:** Best score per task kept across submissions

### Task Categories
1. **Employees** — Create, set roles, contact info
2. **Customers & Products** — Register customers, create products
3. **Invoicing** — Create invoices, register payments, credit notes
4. **Travel Expenses** — Register or delete expense reports
5. **Projects** — Create projects linked to customers
6. **Corrections** — Delete or reverse incorrect entries
7. **Departments** — Create, enable accounting modules

### Constraints
- **API Rate:** Respect Tripletex API limits
- **Sandbox:** Clean slate each time, no persistence
- **Language:** Handle all 7 languages correctly
- **PDFs:** OCR required for some tasks

---

## Approach Summary

### Approach C (Baseline): Rule-Based API Client
- Hardcode mappings for 5 most common tasks
- Direct API calls, no LLM
- Expected: 2.0-3.0 score (basic completion)

### Approach B (Primary): LLM + API Hybrid
- Use Gemini/Claude for task classification (30 types)
- LLM extracts parameters from natural language
- Structured API calls
- Expected: 4.0-5.0 score

### Approach A (Stretch): Agent with Memory
- LangChain agent with Tripletex API tools
- Maintain state across sub-tasks
- Self-correction loop
- PDF parsing with Gemini Vision
- Expected: 5.0-6.0 score

---

## Validation Strategy
- Use Tripletex sandbox API for testing
- Validate each task type independently
- Check field-by-field accuracy against expected output
- Test with all 7 languages

## Submission Loop
```python
@app.post("/solve")
def solve(task: TaskRequest):
    # 1. Classify task type (30 categories)
    # 2. Extract parameters from task.description
    # 3. Handle PDF attachments if present (OCR)
    # 4. Call Tripletex API endpoints
    # 5. Return result
    return {"status": "success", "actions": [...]}
```

## API Documentation
- Tripletex API v2: https://tripletex.no/v2-docs/
- Sandbox: https://kkpqfuj-amager.tripletex.dev/v2-docs/

## Rules Last Read
2026-03-19 20:30 CET (Gunnar)
