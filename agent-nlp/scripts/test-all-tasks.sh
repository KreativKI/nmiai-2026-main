#!/bin/bash
# Test all task types against local or remote endpoint
# Usage: ./scripts/test-all-tasks.sh [endpoint]
# Default endpoint: http://localhost:8080

set -e

ENDPOINT="${1:-http://localhost:8080}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$(dirname "$(dirname "$SCRIPT_DIR")")/.env"

# Load sandbox credentials
if [ -f "$ENV_FILE" ]; then
  export $(grep -E "^TRIPLETEX_" "$ENV_FILE" | xargs)
else
  echo "ERROR: .env not found at $ENV_FILE"
  exit 1
fi

TX_BASE="$TRIPLETEX_BASE_URL"
TX_TOKEN="$TRIPLETEX_SESSION_TOKEN"

if [ -z "$TX_BASE" ] || [ -z "$TX_TOKEN" ]; then
  echo "ERROR: TRIPLETEX_BASE_URL or TRIPLETEX_SESSION_TOKEN not set"
  exit 1
fi

echo "Endpoint: $ENDPOINT"
echo "Sandbox: $TX_BASE"
echo "================================"

PASS=0
FAIL=0
RESULTS=""

run_test() {
  local name="$1"
  local prompt="$2"
  local timeout="${3:-60}"

  echo -n "Testing: $name... "

  RESPONSE=$(curl -s -w "\n%{http_code}\n%{time_total}" --max-time "$timeout" \
    -X POST "$ENDPOINT/solve" \
    -H "Content-Type: application/json" \
    -d "{
      \"prompt\": \"$prompt\",
      \"files\": [],
      \"tripletex_credentials\": {\"base_url\": \"$TX_BASE\", \"session_token\": \"$TX_TOKEN\"}
    }" 2>&1)

  HTTP_CODE=$(echo "$RESPONSE" | tail -1)
  TIME=$(echo "$RESPONSE" | tail -2 | head -1)
  BODY=$(echo "$RESPONSE" | head -1)

  if echo "$BODY" | grep -q '"status":"completed"'; then
    echo "PASS (${TIME}s)"
    PASS=$((PASS + 1))
    RESULTS="$RESULTS\n| $name | PASS | ${TIME}s |"
  else
    echo "FAIL (HTTP $HTTP_CODE, ${TIME}s)"
    FAIL=$((FAIL + 1))
    RESULTS="$RESULTS\n| $name | FAIL | ${TIME}s | $BODY |"
  fi
}

# A. Employees
run_test "A1: Create Employee" \
  "Opprett en ansatt med navn Lars Berg, e-post lars@test.no, mobilnummer 98765432."

run_test "A2: Employee + Admin Role" \
  "Create an employee named Anna Smith, email anna@company.no. She should be an account administrator."

# B. Customers & Products
run_test "B1: Create Customer" \
  "Registrer en kunde med navn Havgull AS, org.nr 967890123, e-post post@havgull.no, telefon 55443322."

run_test "B2: Create Product" \
  "Opprett et produkt med navn Programvarelisens, produktnummer 3001, pris 2500 kr eks. mva. Standard mva-sats."

# C. Invoicing
run_test "C1: Create Invoice" \
  "Opprett en faktura til kunde Sjostjerna AS (org.nr 978901234) pa 45000 kr eks. mva for Prosjektledelse. Standard mva." 90

# D. Travel Expenses
run_test "D1: Travel Expense" \
  "Registrer en reiseregning for en ansatt. Tittel: Seminar Oslo. Togbillett 800 kr inkl. mva." 90

# E. Projects
run_test "E1: Create Project" \
  "Opprett et prosjekt med navn Databasemigrering, prosjektnummer 6001."

# F. Delete
run_test "F1: Delete Entity" \
  "Slett ansatt Lars Berg fra systemet."

# G. Department
run_test "G1: Create Department" \
  "Opprett en avdeling med navn Kundeservice og avdelingsnummer 401."

echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed"
echo ""
echo "| Task | Status | Time |"
echo "|------|--------|------|"
echo -e "$RESULTS"
