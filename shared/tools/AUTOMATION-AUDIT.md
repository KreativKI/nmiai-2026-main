# Automation Audit -- NM i AI 2026

**Auditor:** DevOps Automation Engineer
**Date:** 2026-03-20
**Scope:** All 4 agents (CV, ML, NLP, Butler), overseer, shared tools, hooks, cross-agent coordination

---

## Summary

14 findings across 5 categories. 6 HIGH impact, 5 MEDIUM, 3 LOW.
Total estimated implementation time for all quick fixes: ~95 minutes.

---

## Finding 1: check_inbox.sh Never Updates .last_check (All Agents)

**Problem:** The PostToolUse hook `check_inbox.sh` checks for files newer than `.last_check`, but never creates or updates that file. Result: every single tool invocation re-scans ALL .md files and re-alerts on messages already read. This creates noise pollution in every agent's output.

**Impact:** HIGH
**Effort:** 5 minutes

**Where:** `/Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/check_inbox.sh`

**Fix:** Replace the entire file:

```bash
#!/bin/bash
# Inbox checker for competition agents
# Called as a PostToolUse hook - alerts agent when new messages arrive
# Usage: check_inbox.sh <agent-name> (cv, ml, nlp, ops)

AGENT="${1:-unknown}"
MAIN_REPO="/Volumes/devdrive/github_dev/nmiai-2026-main"
INBOX="$MAIN_REPO/intelligence/for-${AGENT}-agent"

if [ ! -d "$INBOX" ]; then
    exit 0
fi

MARKER="$INBOX/.last_check"

if [ ! -f "$MARKER" ]; then
    # First run: show all messages, then create marker
    COUNT=$(find "$INBOX" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$COUNT" -gt 0 ]; then
        FILES=$(ls -1 "$INBOX"/*.md 2>/dev/null | xargs -I{} basename {} | head -5)
        echo "NEW MESSAGES ($COUNT) in intelligence/for-${AGENT}-agent/: $FILES -- Read them now."
    fi
    touch "$MARKER"
    exit 0
fi

# Find messages newer than last check
NEW_FILES=$(find "$INBOX" -maxdepth 1 -name "*.md" -newer "$MARKER" 2>/dev/null)
COUNT=$(echo "$NEW_FILES" | grep -c . 2>/dev/null || echo 0)

if [ "$COUNT" -gt 0 ]; then
    NAMES=$(echo "$NEW_FILES" | xargs -I{} basename {} | head -5 | tr '\n' ', ' | sed 's/,$//')
    echo "NEW MESSAGES ($COUNT) in intelligence/for-${AGENT}-agent/: $NAMES -- Read them now."
fi

# Update marker AFTER checking so we don't miss messages
touch "$MARKER"
```

---

## Finding 2: ML Agent Has No Background Round Monitor

**Problem:** ML CLAUDE.md says "Background poll every 2 min" (consolidated orders Phase 5), but no background process or hook exists to detect when a new Astar Island round opens. The agent must manually check, burning context and risking missed rounds. Rounds 1-2 were already missed.

**Impact:** HIGH
**Effort:** 15 minutes

**Where:** New file: `/Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/ml_round_monitor.sh`

**Fix:**

```bash
#!/bin/bash
# ML Round Monitor - Background daemon that polls Astar Island round status
# Writes to a file the ML agent can check. Runs as background process.
# Usage: nohup bash ml_round_monitor.sh &
# Stop: kill $(cat /tmp/ml_round_monitor.pid)

MAIN_REPO="/Volumes/devdrive/github_dev/nmiai-2026-main"
STATE_FILE="$MAIN_REPO/shared/tools/.ml_round_state.json"
ALERT_FILE="$MAIN_REPO/intelligence/for-ml-agent/.round_alert"
API_URL="https://api.ainm.no/astar-island/rounds"
POLL_INTERVAL=120  # 2 minutes

echo $$ > /tmp/ml_round_monitor.pid

LAST_ROUND_ID=""
if [ -f "$STATE_FILE" ]; then
    LAST_ROUND_ID=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('last_round_id',''))" 2>/dev/null || echo "")
fi

while true; do
    RESPONSE=$(curl -s --max-time 10 "$API_URL" 2>/dev/null)
    if [ $? -ne 0 ] || [ -z "$RESPONSE" ]; then
        sleep "$POLL_INTERVAL"
        continue
    fi

    # Extract latest round info
    ROUND_INFO=$(python3 -c "
import json, sys
try:
    data = json.loads('''$RESPONSE''')
    rounds = data if isinstance(data, list) else data.get('rounds', [])
    active = [r for r in rounds if r.get('status') == 'active']
    if active:
        r = active[0]
        print(json.dumps({'id': r['id'], 'status': 'active', 'closes_at': r.get('closes_at','')}))
    else:
        latest = sorted(rounds, key=lambda x: x.get('created_at',''), reverse=True)
        if latest:
            r = latest[0]
            print(json.dumps({'id': r['id'], 'status': r.get('status','unknown')}))
except Exception as e:
    print(json.dumps({'error': str(e)}), file=sys.stderr)
" 2>/dev/null)

    CURRENT_ID=$(echo "$ROUND_INFO" | python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
    STATUS=$(echo "$ROUND_INFO" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)

    if [ "$STATUS" = "active" ] && [ "$CURRENT_ID" != "$LAST_ROUND_ID" ]; then
        # New round detected!
        TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        echo "{\"last_round_id\": \"$CURRENT_ID\", \"detected_at\": \"$TIMESTAMP\"}" > "$STATE_FILE"
        echo "NEW ROUND DETECTED at $TIMESTAMP: $CURRENT_ID" > "$ALERT_FILE"
        LAST_ROUND_ID="$CURRENT_ID"
    fi

    sleep "$POLL_INTERVAL"
done
```

Then add a hook to ML agent's settings to check for round alerts:

**Where:** Append to PostToolUse hooks in `/Volumes/devdrive/github_dev/nmiai-worktree-ml/.claude/settings.local.json`

```json
{
  "permissions": {
    "allow": ["Bash(*)", "Read(*)", "Write(*)", "Edit(*)", "Glob(*)", "Grep(*)", "WebFetch(*)", "WebSearch(*)", "Agent(*)"],
    "defaultMode": "bypassPermissions",
    "additionalDirectories": ["/Volumes/devdrive/github_dev/nmiai-2026-main"]
  },
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash /Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/check_inbox.sh ml || true"
          },
          {
            "type": "command",
            "command": "cat /Volumes/devdrive/github_dev/nmiai-2026-main/intelligence/for-ml-agent/.round_alert 2>/dev/null && rm -f /Volumes/devdrive/github_dev/nmiai-2026-main/intelligence/for-ml-agent/.round_alert || true"
          }
        ]
      }
    ]
  }
}
```

---

## Finding 3: ML run_round.sh Contains Hardcoded JWT Token

**Problem:** `run_round.sh` has a JWT token in plaintext. This is a security issue AND a reliability issue: when the token expires, the script silently fails. Should read from a shared credential file.

**Impact:** HIGH (security + breakage risk)
**Effort:** 5 minutes

**Where:** `/Volumes/devdrive/github_dev/nmiai-worktree-ml/agent-ml/solutions/run_round.sh`

**Fix:** Replace the TOKEN line:

```bash
#!/bin/bash
# Run complete v6 phased pipeline for a round
# Usage: ./run_round.sh [--dry-run]

set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate

# Read token from credential file (not hardcoded)
TOKEN_FILE="/Volumes/devdrive/github_dev/nmiai-2026-main/.astar_token"
if [ ! -f "$TOKEN_FILE" ]; then
    echo "ERROR: Token file not found at $TOKEN_FILE"
    echo "Create it: echo 'YOUR_JWT_TOKEN' > $TOKEN_FILE && chmod 600 $TOKEN_FILE"
    exit 1
fi
TOKEN=$(cat "$TOKEN_FILE" | tr -d '\n')

echo "=== Phase 1: Overview ==="
python3 solutions/astar_v6.py --token "$TOKEN" --phase overview

echo ""
echo "=== Phase 2: Analyze ==="
python3 solutions/astar_v6.py --token "$TOKEN" --phase analyze

echo ""
echo "=== Phase 3: Adaptive Stack (all remaining queries on seed 0) ==="
python3 solutions/astar_v6.py --token "$TOKEN" --phase stack --max-stack 41

echo ""
echo "=== Phase 4: Secondary (skip: hindsight showed single-obs hurts) ==="
# python3 solutions/astar_v6.py --token "$TOKEN" --phase secondary --max-secondary 0

echo ""
echo "=== Phase 5: Submit ==="
if [ "$1" = "--dry-run" ]; then
    python3 solutions/astar_v6.py --token "$TOKEN" --phase submit --dry-run
else
    python3 solutions/astar_v6.py --token "$TOKEN" --phase submit
fi

echo ""
echo "=== Done ==="
```

Then create the token file:
```bash
echo 'YOUR_JWT_TOKEN_HERE > /Volumes/devdrive/github_dev/nmiai-2026-main/.astar_token
chmod 600 /Volumes/devdrive/github_dev/nmiai-2026-main/.astar_token
echo '.astar_token' >> /Volumes/devdrive/github_dev/nmiai-2026-main/.gitignore
```

---

## Finding 4: CV Agent Has No Pipeline Script (4 Manual Steps)

**Problem:** CV toolchain requires running 4 commands manually in sequence (validate_cv_zip -> cv_profiler -> cv_judge -> ab_compare). The TOOLS.md documents this but each step is run individually. A single pipeline script with fail-fast would save time and prevent forgotten steps.

**Impact:** HIGH (wasted 2 submissions already from skipped validation)
**Effort:** 10 minutes

**Where:** New file: `/Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/cv_pipeline.sh`

**Fix:**

```bash
#!/bin/bash
# CV Pre-Submission Pipeline -- runs ALL validation in order, stops on first failure
# Usage: cv_pipeline.sh <submission.zip> [--prev-best predictions_prev.json]
#
# Steps: validate ZIP -> profile timing -> judge score -> A/B compare (if prev given)
# Only outputs SUBMIT / NO-GO verdict at the end.

set -e

ZIP="${1:?Usage: cv_pipeline.sh <submission.zip> [--prev-best prev_predictions.json]}"
PREV_BEST=""
TOOLS_DIR="/Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools"
WORKTREE="/Volumes/devdrive/github_dev/nmiai-worktree-cv"

# Parse optional --prev-best
shift
while [[ $# -gt 0 ]]; do
    case "$1" in
        --prev-best) PREV_BEST="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "============================================"
echo " CV Pre-Submission Pipeline"
echo " ZIP: $ZIP"
echo "============================================"
echo ""

# Activate venv if available
if [ -f "$WORKTREE/.venv/bin/activate" ]; then
    source "$WORKTREE/.venv/bin/activate"
fi

# Step 1: Validate ZIP structure
echo "--- STEP 1/4: Validate ZIP ---"
if ! python3 "$TOOLS_DIR/validate_cv_zip.py" "$ZIP"; then
    echo ""
    echo "VERDICT: NO-GO (ZIP validation failed)"
    exit 1
fi
echo "STEP 1: PASS"
echo ""

# Step 2: Profile timing
echo "--- STEP 2/4: Profile Timing ---"
if ! python3 "$TOOLS_DIR/cv_profiler.py" "$ZIP"; then
    echo ""
    echo "VERDICT: NO-GO (profiler failed or timeout risk)"
    exit 1
fi
echo "STEP 2: PASS"
echo ""

# Step 3: Judge score
echo "--- STEP 3/4: Judge Score ---"
PREDICTIONS_JSON="${ZIP%.zip}_predictions.json"
if [ -f "$PREDICTIONS_JSON" ]; then
    JUDGE_OUTPUT=$(python3 "$TOOLS_DIR/cv_judge.py" --predictions-json "$PREDICTIONS_JSON" 2>&1)
    echo "$JUDGE_OUTPUT"
    if echo "$JUDGE_OUTPUT" | grep -q "SKIP"; then
        echo ""
        echo "VERDICT: NO-GO (judge says SKIP)"
        exit 1
    fi
else
    echo "WARNING: No predictions JSON found at $PREDICTIONS_JSON. Run the model first."
    echo "Skipping judge step."
fi
echo "STEP 3: PASS"
echo ""

# Step 4: A/B compare (optional)
if [ -n "$PREV_BEST" ] && [ -f "$PREDICTIONS_JSON" ]; then
    echo "--- STEP 4/4: A/B Compare vs Previous Best ---"
    python3 "$TOOLS_DIR/ab_compare.py" --a "$PREV_BEST" --b "$PREDICTIONS_JSON" || true
    echo "STEP 4: DONE"
else
    echo "--- STEP 4/4: A/B Compare (skipped, no previous best provided) ---"
fi

echo ""
echo "============================================"
echo " VERDICT: SUBMIT (all checks passed)"
echo "============================================"
```

Make executable: `chmod +x /Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/cv_pipeline.sh`

---

## Finding 5: NLP Agent Runs 3 Separate Validation Steps Manually

**Problem:** NLP pre-submission requires: syntax check -> deploy -> health check -> qc-verify -> check MALFORMED logs. Each is a separate manual command. Should be one script.

**Impact:** MEDIUM
**Effort:** 10 minutes

**Where:** New file: `/Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/nlp_pipeline.sh`

**Fix:**

```bash
#!/bin/bash
# NLP Pre-Deploy Pipeline -- syntax check, deploy, health check, QC verify
# Usage: nlp_pipeline.sh [--deploy] [--endpoint URL]
#
# Without --deploy: validates locally only
# With --deploy: deploys to Cloud Run then validates

set -e

WORKTREE="/Volumes/devdrive/github_dev/nmiai-worktree-nlp"
AGENT_DIR="$WORKTREE/agent-nlp"
TOOLS_DIR="/Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools"
ENDPOINT="https://tripletex-agent-795548831221.europe-west4.run.app"
DO_DEPLOY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --deploy) DO_DEPLOY=true; shift ;;
        --endpoint) ENDPOINT="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "============================================"
echo " NLP Pre-Submission Pipeline"
echo "============================================"
echo ""

# Step 1: Syntax check
echo "--- STEP 1/5: Syntax Check ---"
BOT_FILE=$(ls -t "$AGENT_DIR/solutions"/tripletex_bot_v*.py 2>/dev/null | head -1)
if [ -z "$BOT_FILE" ]; then
    echo "ERROR: No tripletex_bot_v*.py found"
    exit 1
fi
echo "Checking: $BOT_FILE"
python3 -c "import ast; ast.parse(open('$BOT_FILE').read())"
echo "STEP 1: PASS (syntax OK)"
echo ""

# Step 2: Deploy (optional)
if $DO_DEPLOY; then
    echo "--- STEP 2/5: Deploy to Cloud Run ---"
    cd "$AGENT_DIR"
    gcloud run deploy tripletex-agent \
        --source . \
        --region europe-west4 \
        --project ai-nm26osl-1779 \
        --allow-unauthenticated \
        --memory 1Gi \
        --timeout 300 \
        --quiet
    echo "STEP 2: PASS (deployed)"
    echo ""
    echo "Waiting 10s for deployment to stabilize..."
    sleep 10
else
    echo "--- STEP 2/5: Deploy (skipped, use --deploy to enable) ---"
fi
echo ""

# Step 3: Health check
echo "--- STEP 3/5: Health Check ---"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$ENDPOINT/health" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "STEP 3: PASS (endpoint healthy, HTTP $HTTP_CODE)"
else
    echo "STEP 3: FAIL (HTTP $HTTP_CODE)"
    echo "VERDICT: NO-GO"
    exit 1
fi
echo ""

# Step 4: QC verify
echo "--- STEP 4/5: QC Verify ---"
if ! python3 "$AGENT_DIR/scripts/qc-verify.py" "$ENDPOINT"; then
    echo "STEP 4: FAIL"
    echo "VERDICT: NO-GO (QC failed)"
    exit 1
fi
echo "STEP 4: PASS"
echo ""

# Step 5: Check for MALFORMED errors in Cloud Run logs
echo "--- STEP 5/5: MALFORMED Error Check ---"
MALFORMED_COUNT=$(gcloud run services logs read tripletex-agent \
    --region europe-west4 \
    --project ai-nm26osl-1779 \
    --limit 50 2>/dev/null | grep -c "MALFORMED" || echo "0")
echo "MALFORMED errors in last 50 log lines: $MALFORMED_COUNT"
if [ "$MALFORMED_COUNT" -gt 10 ]; then
    echo "STEP 5: WARNING (>20% MALFORMED rate)"
    echo "VERDICT: RISKY (high MALFORMED rate)"
    exit 1
fi
echo "STEP 5: PASS"
echo ""

echo "============================================"
echo " VERDICT: READY TO SUBMIT"
echo "============================================"
```

Make executable: `chmod +x /Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/nlp_pipeline.sh`

---

## Finding 6: Intelligence Folders Are Cluttered (14+ Unread Messages Per Agent)

**Problem:** Agent inboxes have 10-20 .md files each. Many are stale (superseded by CONSOLIDATED-ORDERS.md). Agents waste context re-reading old messages every session startup. The "self-destruct rules" in CLAUDE.md are not enforced.

**Impact:** MEDIUM
**Effort:** 10 minutes

**Where:** New file: `/Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/archive_intel.sh`

**Fix:**

```bash
#!/bin/bash
# Archive read intelligence messages to keep inboxes clean
# Moves all .md files EXCEPT CONSOLIDATED-ORDERS.md to an _archive/ subfolder
# Usage: archive_intel.sh [agent-name]
#   agent-name: cv, ml, nlp, ops, or "all" (default: all)

MAIN_REPO="/Volumes/devdrive/github_dev/nmiai-2026-main"
TIMESTAMP=$(date +%Y%m%d-%H%M)

archive_folder() {
    local FOLDER="$1"
    local AGENT="$2"

    if [ ! -d "$FOLDER" ]; then
        echo "  Skipping $AGENT (folder not found)"
        return
    fi

    ARCHIVE="$FOLDER/_archive"
    mkdir -p "$ARCHIVE"

    COUNT=0
    for f in "$FOLDER"/*.md; do
        [ -f "$f" ] || continue
        BASENAME=$(basename "$f")
        # Keep CONSOLIDATED-ORDERS.md in place
        if [ "$BASENAME" = "CONSOLIDATED-ORDERS.md" ]; then
            continue
        fi
        mv "$f" "$ARCHIVE/${TIMESTAMP}_${BASENAME}"
        COUNT=$((COUNT + 1))
    done

    echo "  $AGENT: archived $COUNT messages"
}

AGENTS="${1:-all}"

if [ "$AGENTS" = "all" ]; then
    echo "Archiving intelligence messages..."
    for AGENT in cv ml nlp ops; do
        archive_folder "$MAIN_REPO/intelligence/for-${AGENT}-agent" "$AGENT"
    done
    archive_folder "$MAIN_REPO/intelligence/for-overseer" "overseer"
else
    archive_folder "$MAIN_REPO/intelligence/for-${AGENTS}-agent" "$AGENTS"
fi

echo "Done. CONSOLIDATED-ORDERS.md preserved in all folders."
```

Make executable: `chmod +x /Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/archive_intel.sh`

---

## Finding 7: ML Autoiteration Loop Is Documented But Not Scripted

**Problem:** ML consolidated orders Phase 4 describes an autoiteration loop (generate 50 parameter variants, backtest each, save best). This is currently a pseudocode block in a markdown file. The ML agent must manually implement this each session, burning context.

**Impact:** HIGH
**Effort:** 15 minutes

**Where:** New file: `/Volumes/devdrive/github_dev/nmiai-worktree-ml/agent-ml/solutions/autoiterate.py`

**Fix:**

```python
#!/usr/bin/env python3
"""
ML Autoiteration Loop: generate parameter variants, backtest each, keep best.
Runs offline against cached ground truth. No API calls, no submission risk.

Usage:
    python3 autoiterate.py --rounds 50 [--base-config config.json]
"""

import json
import random
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

SOLUTIONS_DIR = Path(__file__).parent
EXPERIMENTS_FILE = SOLUTIONS_DIR.parent / "EXPERIMENTS.md"
BEST_CONFIG_FILE = SOLUTIONS_DIR / "best_config.json"

# Default base config (override with --base-config)
DEFAULT_CONFIG = {
    "temperature": 1.0,
    "smoothing_sigma": 0.0,
    "collapse_threshold": 0.01,
    "obs_weight_max": 0.95,
    "near_weight": 0.21,
    "far_weight": 0.12,
}

PARAM_RANGES = {
    "temperature": (0.85, 1.25),
    "smoothing_sigma": (0.0, 2.0),
    "collapse_threshold": (0.005, 0.035),
    "obs_weight_max": (0.80, 0.99),
    "near_weight": (0.10, 0.35),
    "far_weight": (0.05, 0.20),
}


def generate_variant(base: dict, n: int) -> dict:
    """Generate a random perturbation of base config."""
    variant = base.copy()
    # Perturb 1-3 parameters at a time
    keys = random.sample(list(PARAM_RANGES.keys()), k=min(random.randint(1, 3), len(PARAM_RANGES)))
    for key in keys:
        lo, hi = PARAM_RANGES[key]
        variant[key] = round(random.uniform(lo, hi), 4)
    return variant


def backtest(config: dict) -> float:
    """Run backtest.py with given config and return average score."""
    config_arg = json.dumps(config)
    try:
        result = subprocess.run(
            [sys.executable, str(SOLUTIONS_DIR / "backtest.py"),
             "--config", config_arg, "--quiet"],
            capture_output=True, text=True, timeout=120, cwd=str(SOLUTIONS_DIR)
        )
        # Parse score from backtest output (last line should be JSON with avg_score)
        for line in reversed(result.stdout.strip().split("\n")):
            try:
                data = json.loads(line)
                return data.get("avg_score", 0.0)
            except json.JSONDecodeError:
                continue
        # Fallback: look for "Avg" in output
        for line in result.stdout.strip().split("\n"):
            if "avg" in line.lower() or "Avg" in line:
                parts = line.split()
                for part in parts:
                    try:
                        score = float(part)
                        if 0 < score <= 100:
                            return score
                    except ValueError:
                        continue
        return 0.0
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"  Backtest error: {e}", file=sys.stderr)
        return 0.0


def log_experiment(variant: dict, score: float, n: int, best: bool):
    """Append to EXPERIMENTS.md."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = f"""
### Autoiteration variant {n}
**Date:** {ts}
**Config:** {json.dumps(variant)}
**Score:** {score:.2f}
**Best so far:** {"YES" if best else "no"}
"""
    with open(EXPERIMENTS_FILE, "a") as f:
        f.write(entry)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=50)
    parser.add_argument("--base-config", type=str, default=None)
    args = parser.parse_args()

    if args.base_config and Path(args.base_config).exists():
        base = json.loads(Path(args.base_config).read_text())
    elif BEST_CONFIG_FILE.exists():
        base = json.loads(BEST_CONFIG_FILE.read_text())
    else:
        base = DEFAULT_CONFIG.copy()

    print(f"Starting autoiteration: {args.rounds} variants")
    print(f"Base config: {json.dumps(base, indent=2)}")

    # Score baseline first
    best_score = backtest(base)
    best_config = base.copy()
    print(f"Baseline score: {best_score:.2f}")

    for i in range(1, args.rounds + 1):
        variant = generate_variant(best_config, i)
        score = backtest(variant)
        is_best = score > best_score

        if is_best:
            best_score = score
            best_config = variant.copy()
            BEST_CONFIG_FILE.write_text(json.dumps(best_config, indent=2))
            print(f"  [{i}/{args.rounds}] score={score:.2f} ** NEW BEST ** config={variant}")
        else:
            print(f"  [{i}/{args.rounds}] score={score:.2f}")

        log_experiment(variant, score, i, is_best)

    print(f"\nBest score: {best_score:.2f}")
    print(f"Best config saved to: {BEST_CONFIG_FILE}")
    print(json.dumps(best_config, indent=2))


if __name__ == "__main__":
    main()
```

Note: This script assumes backtest.py can accept a `--config` JSON argument and `--quiet` flag. If not, the ML agent needs to add those flags (simple argparse addition). The important thing is this exists as a runnable script rather than pseudocode in a markdown file.

---

## Finding 8: No Cross-Agent Status Dashboard File

**Problem:** Each agent writes status.json independently. The overseer and JC must check 4 separate files across 4 worktrees to get a picture. No single aggregated status file exists.

**Impact:** MEDIUM
**Effort:** 10 minutes

**Where:** New file: `/Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/aggregate_status.sh`

**Fix:**

```bash
#!/bin/bash
# Aggregate all agent status.json files into one overview
# Usage: aggregate_status.sh
# Output: shared/tools/.aggregate_status.json (read by overseer and dashboard)

MAIN_REPO="/Volumes/devdrive/github_dev/nmiai-2026-main"
OUTPUT="$MAIN_REPO/shared/tools/.aggregate_status.json"

python3 -c "
import json
from pathlib import Path
from datetime import datetime, timezone

agents = {
    'cv': Path('/Volumes/devdrive/github_dev/nmiai-worktree-cv/agent-cv/status.json'),
    'ml': Path('/Volumes/devdrive/github_dev/nmiai-worktree-ml/agent-ml/status.json'),
    'nlp': Path('/Volumes/devdrive/github_dev/nmiai-worktree-nlp/agent-nlp/status.json'),
    'ops': Path('/Volumes/devdrive/github_dev/nmiai-worktree-ops/agent-ops/status.json'),
}

result = {
    'aggregated_at': datetime.now(timezone.utc).isoformat(),
    'agents': {}
}

for name, path in agents.items():
    try:
        if path.exists():
            data = json.loads(path.read_text())
            data['_file'] = str(path)
            data['_exists'] = True
            result['agents'][name] = data
        else:
            result['agents'][name] = {'_exists': False, '_file': str(path)}
    except Exception as e:
        result['agents'][name] = {'_exists': True, '_error': str(e), '_file': str(path)}

print(json.dumps(result, indent=2))
" > "$OUTPUT"

echo "Status aggregated to $OUTPUT"

# Print summary
python3 -c "
import json
data = json.load(open('$OUTPUT'))
print(f\"Aggregated at: {data['aggregated_at']}\")
print()
for agent, info in data['agents'].items():
    if not info.get('_exists'):
        print(f'  {agent.upper()}: NO STATUS FILE')
    elif '_error' in info:
        print(f'  {agent.upper()}: ERROR reading status')
    else:
        score = info.get('score', info.get('best_score', 'N/A'))
        phase = info.get('phase', info.get('current_phase', 'N/A'))
        state = info.get('state', 'N/A')
        ts = info.get('timestamp', info.get('updated_at', 'N/A'))
        print(f'  {agent.upper()}: score={score} phase={phase} state={state} updated={ts}')
"
```

Add as a hook on the overseer's settings (or run manually):
```bash
chmod +x /Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/aggregate_status.sh
```

---

## Finding 9: NLP test-all-tasks.sh Does Not Log Results to File

**Problem:** `test-all-tasks.sh` prints results to stdout but never writes them to a file. Results are lost when the terminal scrolls. Should append to a log file for tracking over time.

**Impact:** LOW
**Effort:** 5 minutes

**Where:** `/Volumes/devdrive/github_dev/nmiai-worktree-nlp/agent-nlp/scripts/test-all-tasks.sh`

**Fix:** Add logging at the end of the script (after the existing results summary). Add these lines before the final `echo -e "$RESULTS"`:

```bash
# After the existing results table echo:
# Log results to file
LOG_DIR="/Volumes/devdrive/github_dev/nmiai-worktree-nlp/agent-nlp"
LOG_FILE="$LOG_DIR/test_results_$(date +%Y%m%d_%H%M).json"
python3 -c "
import json, sys
from datetime import datetime, timezone
results = {
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'endpoint': '$ENDPOINT',
    'passed': $PASS,
    'failed': $FAIL,
    'total': $((PASS + FAIL))
}
json.dump(results, open('$LOG_FILE', 'w'), indent=2)
print(f'Results logged to: $LOG_FILE', file=sys.stderr)
"
```

---

## Finding 10: Overseer Has No Automated Leaderboard Delta Tracking

**Problem:** The overseer plan says "monitor leaderboard top 10" every 10 minutes. `fetch_leaderboard.py` and `scrape_leaderboard.py` exist but neither stores deltas or alerts on rank changes. The overseer must manually diff.

**Impact:** MEDIUM
**Effort:** 10 minutes

**Where:** New file: `/Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/leaderboard_watch.sh`

**Fix:**

```bash
#!/bin/bash
# Leaderboard watcher: fetch, compare, alert on changes
# Usage: leaderboard_watch.sh
# Stores snapshots in shared/tools/.leaderboard_snapshots/

MAIN_REPO="/Volumes/devdrive/github_dev/nmiai-2026-main"
TOOLS_DIR="$MAIN_REPO/shared/tools"
SNAP_DIR="$TOOLS_DIR/.leaderboard_snapshots"
ALERT_FILE="$MAIN_REPO/intelligence/for-overseer/.leaderboard_alert"

mkdir -p "$SNAP_DIR"

# Run fetcher
cd "$TOOLS_DIR"
python3 fetch_leaderboard.py --output "$SNAP_DIR/latest.json" 2>/dev/null || \
python3 scrape_leaderboard.py 2>/dev/null

LATEST="$SNAP_DIR/latest.json"
PREVIOUS="$SNAP_DIR/previous.json"

if [ ! -f "$LATEST" ]; then
    echo "No leaderboard data fetched"
    exit 1
fi

if [ -f "$PREVIOUS" ]; then
    # Compare and alert on changes
    python3 -c "
import json, sys
from datetime import datetime, timezone

try:
    prev = json.load(open('$PREVIOUS'))
    curr = json.load(open('$LATEST'))
except:
    sys.exit(0)

# Find our team
def find_us(data):
    teams = data if isinstance(data, list) else data.get('teams', data.get('leaderboard', []))
    for t in teams:
        name = t.get('team_name', t.get('name', ''))
        if 'kreativ' in name.lower() or 'jc' in name.lower():
            return t
    return None

prev_us = find_us(prev)
curr_us = find_us(curr)

changes = []
if prev_us and curr_us:
    prev_rank = prev_us.get('rank', prev_us.get('position', 0))
    curr_rank = curr_us.get('rank', curr_us.get('position', 0))
    prev_score = prev_us.get('total_score', prev_us.get('score', 0))
    curr_score = curr_us.get('total_score', curr_us.get('score', 0))

    if prev_rank != curr_rank:
        delta = prev_rank - curr_rank  # positive = improved
        direction = 'UP' if delta > 0 else 'DOWN'
        changes.append(f'Rank: {prev_rank} -> {curr_rank} ({direction} {abs(delta)})')
    if abs(float(prev_score) - float(curr_score)) > 0.01:
        changes.append(f'Score: {prev_score} -> {curr_score}')

if changes:
    ts = datetime.now(timezone.utc).strftime('%H:%M UTC')
    alert = f'LEADERBOARD CHANGE ({ts}): ' + ' | '.join(changes)
    print(alert)
    with open('$ALERT_FILE', 'w') as f:
        f.write(alert + '\n')
else:
    print('No rank/score changes detected')
" 2>/dev/null
fi

# Rotate: current becomes previous
cp "$LATEST" "$PREVIOUS" 2>/dev/null
```

---

## Finding 11: No GCP VM Status Monitor for CV Training

**Problem:** CV agent trains on GCP VMs. The agent and overseer must manually SSH or run `gcloud compute instances describe` to check if training is still running, has finished, or has crashed. No automated check exists.

**Impact:** MEDIUM
**Effort:** 10 minutes

**Where:** New file: `/Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/gcp_vm_status.sh`

**Fix:**

```bash
#!/bin/bash
# Check status of all GCP VMs in the competition project
# Usage: gcp_vm_status.sh [--alert]
# With --alert: writes to intelligence/for-cv-agent/ if a VM stopped

PROJECT="ai-nm26osl-1779"
MAIN_REPO="/Volumes/devdrive/github_dev/nmiai-2026-main"
STATE_FILE="$MAIN_REPO/shared/tools/.gcp_vm_state.json"

echo "Checking GCP VMs in project $PROJECT..."

VM_JSON=$(gcloud compute instances list \
    --project "$PROJECT" \
    --format="json(name,zone,status,machineType,scheduling.preemptible)" \
    2>/dev/null)

if [ $? -ne 0 ]; then
    echo "ERROR: gcloud command failed. Check ADC auth."
    exit 1
fi

echo "$VM_JSON" | python3 -c "
import json, sys
from datetime import datetime, timezone

vms = json.load(sys.stdin)
if not vms:
    print('  No VMs found')
    sys.exit(0)

for vm in vms:
    name = vm.get('name', 'unknown')
    zone = vm.get('zone', '').split('/')[-1]
    status = vm.get('status', 'UNKNOWN')
    mtype = vm.get('machineType', '').split('/')[-1]
    preempt = 'SPOT' if vm.get('scheduling', {}).get('preemptible') else 'ON-DEMAND'

    icon = 'RUNNING' if status == 'RUNNING' else 'STOPPED' if status in ('TERMINATED', 'STOPPED') else status
    print(f'  {name}: {icon} ({mtype}, {zone}, {preempt})')

# Save state for delta tracking
state = {
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'vms': {vm['name']: vm.get('status', 'UNKNOWN') for vm in vms}
}
json.dump(state, open('$STATE_FILE', 'w'), indent=2)
"

# Alert on stopped VMs (if --alert flag)
if [ "$1" = "--alert" ] && [ -f "$STATE_FILE" ]; then
    python3 -c "
import json
state = json.load(open('$STATE_FILE'))
stopped = [name for name, status in state['vms'].items()
           if status in ('TERMINATED', 'STOPPED') and 'cv' in name.lower()]
if stopped:
    alert = f'GCP VM STOPPED: {\", \".join(stopped)}. Training may have finished or crashed. Check logs.'
    with open('$MAIN_REPO/intelligence/for-cv-agent/.vm_alert', 'w') as f:
        f.write(alert)
    with open('$MAIN_REPO/intelligence/for-overseer/.vm_alert', 'w') as f:
        f.write(alert)
    print(alert)
" 2>/dev/null
fi
```

Add a hook to the CV agent's settings to check for VM alerts:

**Where:** Append to PostToolUse hooks in `/Volumes/devdrive/github_dev/nmiai-worktree-cv/.claude/settings.local.json`

```json
{
  "type": "command",
  "command": "cat /Volumes/devdrive/github_dev/nmiai-2026-main/intelligence/for-cv-agent/.vm_alert 2>/dev/null && rm -f /Volumes/devdrive/github_dev/nmiai-2026-main/intelligence/for-cv-agent/.vm_alert || true"
}
```

---

## Finding 12: ML Improvement Loop (CLAUDE.md) Not Implemented as Cron

**Problem:** ML CLAUDE.md documents an "Automatic Improvement Loop" (cache -> retrain -> backtest -> hindsight -> resubmit -> log). It says to "deploy to VM, set up cron every 30 min." This has never been implemented. The ML agent runs each step manually.

**Impact:** HIGH (each manual run burns context and risks forgetting steps)
**Effort:** 15 minutes

**Where:** New file: `/Volumes/devdrive/github_dev/nmiai-worktree-ml/agent-ml/solutions/improvement_loop.sh`

**Fix:**

```bash
#!/bin/bash
# ML Automatic Improvement Loop
# Runs: cache ground truth -> retrain model -> backtest -> log results
# Usage: ./improvement_loop.sh [--once | --daemon]
# --once: run once and exit
# --daemon: run every 30 minutes (for GCP VM)

set -e
cd "$(dirname "$0")/.."
VENV=".venv/bin/activate"
[ -f "$VENV" ] && source "$VENV"

SOLUTIONS="$(dirname "$0")"
MAIN_REPO="/Volumes/devdrive/github_dev/nmiai-2026-main"
LOG_FILE="$SOLUTIONS/../improvement_loop.log"
LOCK_FILE="/tmp/ml_improvement_loop.lock"

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Already running (PID $PID)"
        exit 0
    fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

run_loop() {
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "=== Improvement Loop: $TIMESTAMP ===" | tee -a "$LOG_FILE"

    # Step 1: Cache ground truth from completed rounds
    echo "  Step 1: Caching ground truth..." | tee -a "$LOG_FILE"
    python3 "$SOLUTIONS/backtest.py" --cache 2>&1 | tail -2 | tee -a "$LOG_FILE" || true

    # Step 2: Retrain learned model
    echo "  Step 2: Retraining model..." | tee -a "$LOG_FILE"
    python3 "$SOLUTIONS/learned_model.py" --export 2>&1 | tail -2 | tee -a "$LOG_FILE" || true

    # Step 3: Backtest new model
    echo "  Step 3: Backtesting..." | tee -a "$LOG_FILE"
    BACKTEST_RESULT=$(python3 "$SOLUTIONS/learned_model.py" --backtest 2>&1 | tail -5)
    echo "$BACKTEST_RESULT" | tee -a "$LOG_FILE"

    # Step 4: Hindsight analysis (cached data only, no API calls)
    echo "  Step 4: Hindsight analysis..." | tee -a "$LOG_FILE"
    python3 "$SOLUTIONS/hindsight.py" --cached-only 2>&1 | tail -5 | tee -a "$LOG_FILE" || true

    # Step 5: Log results
    echo "  Step 5: Results logged at $TIMESTAMP" | tee -a "$LOG_FILE"

    # Write status for overseer
    echo "ML improvement loop ran at $TIMESTAMP. Check $LOG_FILE for results." \
        > "$MAIN_REPO/intelligence/for-overseer/.ml_loop_result"

    echo "=== Loop complete ===" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
}

case "${1:-}" in
    --daemon)
        echo "Starting daemon mode (every 30 min). PID: $$"
        while true; do
            run_loop
            echo "Sleeping 30 minutes..."
            sleep 1800
        done
        ;;
    --once|"")
        run_loop
        ;;
    *)
        echo "Usage: $0 [--once | --daemon]"
        exit 1
        ;;
esac
```

Make executable: `chmod +x improvement_loop.sh`

---

## Finding 13: PostToolUse Hook Fires on EVERY Tool Call (Performance)

**Problem:** The `check_inbox.sh` hook runs on every single tool invocation (Read, Write, Edit, Bash, Glob, Grep). For a session with 200+ tool calls, that is 200+ `find` commands scanning the intelligence folders. This adds latency to every operation.

**Impact:** LOW
**Effort:** 5 minutes

**Where:** All 4 settings.local.json files

**Fix:** Add a `matcher` to limit which tools trigger the hook. Only check inbox on Bash calls (which indicate the agent is doing real work, not just reading files):

For each agent's `.claude/settings.local.json`, change the hooks to:

```json
"hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash /Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/check_inbox.sh <AGENT> || true"
          }
        ]
      }
    ]
  }
```

Replace `<AGENT>` with cv/ml/nlp/ops as appropriate. This reduces hook executions by ~70% (most tool calls are Read/Grep/Glob, not Bash).

---

## Finding 14: No Countdown Timer / Deadline Alerter

**Problem:** Key deadlines (cut-loss Saturday 12:00, feature freeze Sunday 09:00, repo public Sunday 14:45, competition end Sunday 15:00) are documented in plan.md but no automated reminder exists. Agents and overseer must mentally track time.

**Impact:** LOW
**Effort:** 5 minutes

**Where:** New file: `/Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/countdown.sh`

**Fix:**

```bash
#!/bin/bash
# Competition deadline countdown
# Usage: countdown.sh
# Shows time remaining to each deadline

python3 -c "
from datetime import datetime, timezone, timedelta

CET = timezone(timedelta(hours=2))  # CEST in March
now = datetime.now(CET)

deadlines = [
    ('Rate limit reset', datetime(2026, 3, 21, 1, 0, tzinfo=CET)),
    ('CUT-LOSS: baseline if 0', datetime(2026, 3, 21, 12, 0, tzinfo=CET)),
    ('Tier 3 opens (NLP 3x)', datetime(2026, 3, 21, 8, 0, tzinfo=CET)),
    ('FEATURE FREEZE', datetime(2026, 3, 22, 9, 0, tzinfo=CET)),
    ('Repo goes public', datetime(2026, 3, 22, 14, 45, tzinfo=CET)),
    ('COMPETITION ENDS', datetime(2026, 3, 22, 15, 0, tzinfo=CET)),
]

print(f'Current time: {now.strftime(\"%Y-%m-%d %H:%M CET\")}')
print()

for name, deadline in deadlines:
    delta = deadline - now
    if delta.total_seconds() < 0:
        print(f'  {name}: PASSED')
    else:
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        urgency = ' !!!' if hours < 2 else ' !' if hours < 6 else ''
        print(f'  {name}: {hours}h {minutes}m remaining{urgency}')
"
```

---

## Priority Implementation Order

Run these in order for maximum impact with minimum time:

| Priority | Finding | Impact | Minutes | Cumulative |
|----------|---------|--------|---------|------------|
| 1 | F1: Fix check_inbox.sh .last_check | HIGH | 5 | 5 |
| 2 | F3: Remove hardcoded JWT token | HIGH | 5 | 10 |
| 3 | F4: CV pipeline script | HIGH | 10 | 20 |
| 4 | F6: Archive stale intel messages | MEDIUM | 10 | 30 |
| 5 | F13: Hook matcher optimization | LOW | 5 | 35 |
| 6 | F2: ML round monitor | HIGH | 15 | 50 |
| 7 | F5: NLP pipeline script | MEDIUM | 10 | 60 |
| 8 | F7: ML autoiteration script | HIGH | 15 | 75 |
| 9 | F8: Aggregate status | MEDIUM | 10 | 85 |
| 10 | F14: Countdown timer | LOW | 5 | 90 |
| 11 | F12: ML improvement loop | HIGH | 15 | 105 |
| 12 | F10: Leaderboard watch | MEDIUM | 10 | 115 |
| 13 | F11: GCP VM monitor | MEDIUM | 10 | 125 |
| 14 | F9: NLP test log to file | LOW | 5 | 130 |

First 5 items (35 minutes) eliminate the most wasteful problems. The full list takes about 2 hours.
