# FIXES QUEUE -- Ranked Efficiency Improvements

Generated: 2026-03-21 12:03:16

Priority: Fix errors first (each 4xx hurts efficiency), then reduce writes.

## 1. create_project_invoice (impact: 17.0)
- Runs observed: 12
- Avg writes: 1.5 (optimal: 3, waste: -1.5)
- Success rate: 92%
- **4xx errors:**
  - `POST /employee -> 422`: 10x
  - `POST /project -> 422`: 3x
  - `POST /invoice -> 422`: 1x
  - `PUT /employee/18224966 -> 422`: 1x
  - `PUT /employee/18225326 -> 422`: 1x
  - `PUT /employee/18225432 -> 422`: 1x
  - `PUT /employee/18225591 -> 422`: 1x
- **Known fix:** Inherits create_project PM creation issues + bank PUT
  - How: Fix PM creation and bank account setup
  - Saves: ~2 write(s)/run
  - Look at: `exec_create_project_invoice`

## 2. create_project (impact: 13.0)
- Runs observed: 9
- Avg writes: 1.2 (optimal: 2, waste: -0.8)
- Success rate: 89%
- **4xx errors:**
  - `POST /employee -> 422`: 8x
  - `POST /project -> 422`: 1x
  - `PUT /employee/18225372 -> 422`: 1x
  - `PUT /employee/18225397 -> 422`: 1x
- **Known fix:** POST /employee for PM may fail (422 email conflict), then PUT to rename admin
  - How: Check admin name first; if PM matches admin, skip employee creation entirely
  - Saves: ~2 write(s)/run
  - Look at: `exec_create_project`

## 3. create_department (impact: 12.0)
- Runs observed: 10
- Avg writes: 0.2 (optimal: 1, waste: -0.8)
- Success rate: 100%
- **4xx errors:**
  - `GET /token/session/>whoAmI -> 403`: 1x
  - `GET /department -> 403`: 1x
  - `POST /department -> 403`: 1x
  - `POST /employee -> 403`: 1x

## 4. process_salary (impact: 12.0)
- Runs observed: 10
- Avg writes: 0.7 (optimal: 3, waste: -2.3)
- Success rate: 100%
- **4xx errors:**
  - `POST /salary/payslip -> 422`: 1x
  - `POST /salary/paymentSpecification -> 404`: 1x
  - `POST /employee/employment/details -> 422`: 1x
  - `GET /employee -> 403`: 1x
  - `GET /department -> 403`: 1x
  - `POST /department -> 403`: 1x
  - `POST /employee -> 403`: 1x
- **Known fix:** PUT /employee to set dateOfBirth on EXISTING employees unconditionally
  - How: GET employee first, check if dateOfBirth is already set before PUT
  - Saves: ~1 write(s)/run
  - Look at: `exec_process_salary`

## 5. create_invoice (impact: 8.0)
- Runs observed: 31
- Avg writes: 0.3 (optimal: 1, waste: -0.7)
- Success rate: 90%
- **4xx errors:**
  - `GET /customer -> 403`: 9x
  - `POST /customer -> 403`: 3x
  - `POST /product -> 422`: 2x
  - `POST /invoice -> 422`: 2x
  - `POST /employee -> 422`: 1x
  - `PUT /employee/18225877 -> 422`: 1x
- **Known fix:** PUT /ledger/account to set bankAccountNumber may be unnecessary if already set
  - How: Check if account 1920 already has bankAccountNumber before PUT
  - Saves: ~1 write(s)/run
  - Look at: `exec_create_invoice`

## 6. create_travel_expense (impact: 2.0)
- Runs observed: 7
- Avg writes: 0.4 (optimal: 3, waste: -2.6)
- Success rate: 100%
- **4xx errors:**
  - `POST /travelExpense/perDiemCompensation -> 422`: 1x
  - `GET /department -> 403`: 1x
  - `POST /department -> 403`: 1x
  - `POST /employee -> 422`: 1x
- **Known fix:** Always creates new employee even if one with same name exists
  - How: GET /employee by name first; if exists, use existing ID
  - Saves: ~2 write(s)/run
  - Look at: `exec_create_travel_expense`

## 7. create_employee (impact: 0.0)
- Runs observed: 11
- Avg writes: 0.1 (optimal: 1, waste: -0.9)
- Success rate: 100%
- **4xx errors:**
  - `GET /department -> 403`: 1x
  - `POST /department -> 403`: 1x

## 8. register_payment (impact: -4.0)
- Runs observed: 9
- Avg writes: 0.0 (optimal: 1, waste: -1.0)
- Success rate: 100%
- **4xx errors:**
  - `GET /customer -> 403`: 3x

## 9. register_supplier_invoice (impact: -6.0)
- Runs observed: 10
- Avg writes: 0.4 (optimal: 2, waste: -1.6)
- Success rate: 60%
- **4xx errors:**
  - `POST /ledger/voucher -> 422`: 3x
  - `POST /supplierInvoice -> 422`: 1x

## 10. create_credit_note (impact: -8.0)
- Runs observed: 21
- Avg writes: 0.1 (optimal: 1, waste: -0.9)
- Success rate: 95%
- **4xx errors:**
  - `POST /department -> 403`: 3x
  - `GET /customer -> 403`: 3x

## 11. create_dimension (impact: -11.0)
- Runs observed: 10
- Avg writes: 0.4 (optimal: 2, waste: -1.6)
- Success rate: 60%
- **4xx errors:**
  - `POST /ledger/voucher -> 422`: 4x
