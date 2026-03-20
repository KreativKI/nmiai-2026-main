# tripletex_bot_v4 Plan

## Architecture Change
FROM: LLM agent loop with function calling (unreliable JSON generation)
TO: LLM extracts fields once, Python executes deterministic API sequences

## Flow
```
POST /solve (prompt, files, credentials)
    |
    v
LLM call (ONE call, no tools):
  "Given this prompt, return JSON with:
   task_type, and all field values"
    |
    v
Python task router:
  match task_type -> execute_create_customer(), execute_create_invoice(), etc.
    |
    v
Deterministic API calls (no LLM involvement)
    |
    v
{"status": "completed"}
```

## LLM Prompt (extraction only)
System: "You are a task classifier for Norwegian accounting. Extract the task type and all field values from the prompt. Return valid JSON only."

User: the actual task prompt + any file content

Response format:
```json
{
  "task_type": "create_customer",
  "fields": {
    "name": "Ola Nordmann AS",
    "email": "post@ola.no",
    "phone": "22334455",
    "org_number": "912345678"
  }
}
```

## Task Types to Implement (priority order)
1. create_customer - POST /customer
2. create_employee - POST /employee (+ dept if needed)
3. create_product - POST /product
4. create_department - POST /department
5. create_project - GET whoAmI + POST /project
6. create_invoice - POST /customer + PUT bank acct + POST /invoice
7. register_payment - GET customer + GET invoice + GET paymentType + PUT payment
8. create_travel_expense - POST employee + GET paymentType + POST travelExpense + POST cost
9. create_credit_note - GET customer + GET invoice + PUT createCreditNote
10. create_employment - POST dept + POST employee + POST employment + POST details
11. update_customer - GET customer + PUT customer
12. update_employee - GET employee + PUT employee
13. delete_employee - GET employee + DELETE employee
14. delete_travel_expense - GET travelExpense + DELETE
15. create_contact - GET/POST customer + POST contact

## Key Design Decisions
- Keep call_tripletex() as-is (proven reliable)
- Keep validate_and_fix_body() as safety net
- Keep truncate_result() for logging
- Keep file handling (base64 decode for PDFs)
- Gemini still used for field extraction (ONE call, no function calling)
- Fallback: if task_type is "unknown", fall back to the v3 agent loop
