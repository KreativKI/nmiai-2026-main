#!/bin/bash
# Local Orchestrator: polls GCP VM for pipeline completion, downloads ZIP, validates locally.
# Runs on JC's Mac.
#
# Usage:
#   bash agent-cv/scripts/local_orchestrator.sh cv-train-1 europe-west1-c
#   bash agent-cv/scripts/local_orchestrator.sh cv-train-4 europe-west3-a
#
# What it does:
#   1. Polls GCP VM for ~/pipeline_status.json with state "complete"
#   2. Downloads the submission ZIP
#   3. Runs cv_pipeline.sh locally to validate
#   4. Sends macOS notification when ready

set -euo pipefail

# --- Arguments ---
VM="${1:?Usage: local_orchestrator.sh <vm-name> <zone>}"
ZONE="${2:?Usage: local_orchestrator.sh <vm-name> <zone>}"
PROJECT="ai-nm26osl-1779"

# --- Configuration ---
WORKTREE="/Volumes/devdrive/github_dev/nmiai-worktree-cv"
TOOLS_DIR="/Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools"
DOWNLOAD_DIR="$WORKTREE/agent-cv/submissions"
POLL_INTERVAL=120    # Check every 2 minutes
MAX_POLLS=180        # 180 * 2min = 6 hours max wait

# --- Helpers ---
ts() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]"
}

notify() {
    local title="$1"
    local msg="$2"
    # macOS notification
    osascript -e "display notification \"$msg\" with title \"$title\" sound name \"Glass\"" 2>/dev/null || true
}

# --- Preflight ---
echo "$(ts) === Local Orchestrator ==="
echo "$(ts) VM: $VM ($ZONE)"
echo "$(ts) Project: $PROJECT"
echo "$(ts) Polling every ${POLL_INTERVAL}s (max ${MAX_POLLS} attempts = $((MAX_POLLS * POLL_INTERVAL / 3600))h)"
echo ""

mkdir -p "$DOWNLOAD_DIR"

# Verify gcloud works
if ! gcloud compute instances describe "$VM" --zone="$ZONE" --project="$PROJECT" --format="value(status)" > /dev/null 2>&1; then
    echo "$(ts) ERROR: Cannot reach VM $VM in $ZONE. Check if it is running."
    echo "$(ts) Try: gcloud compute instances start $VM --zone=$ZONE --project=$PROJECT"
    exit 1
fi

VM_STATUS=$(gcloud compute instances describe "$VM" --zone="$ZONE" --project="$PROJECT" --format="value(status)")
echo "$(ts) VM status: $VM_STATUS"
if [ "$VM_STATUS" != "RUNNING" ]; then
    echo "$(ts) ERROR: VM is not running (status: $VM_STATUS)"
    exit 1
fi

echo "$(ts) Starting to poll for pipeline_status.json..."
echo ""

# ============================================================
# PHASE 1: Poll for completion
# ============================================================
POLL_COUNT=0
PIPELINE_DONE=false

while [ "$PIPELINE_DONE" = false ] && [ "$POLL_COUNT" -lt "$MAX_POLLS" ]; do
    POLL_COUNT=$((POLL_COUNT + 1))

    # Read pipeline_status.json from the VM
    STATUS_JSON=$(gcloud compute ssh "$VM" --zone="$ZONE" --project="$PROJECT" \
        --command="cat ~/pipeline_status.json 2>/dev/null || echo '{\"state\":\"not_found\"}'" 2>/dev/null) || {
        echo "$(ts) [Poll $POLL_COUNT] SSH failed, retrying..."
        sleep "$POLL_INTERVAL"
        continue
    }

    # Parse state, phase, message from JSON in a single python3 call
    PARSED=$(echo "$STATUS_JSON" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('state', 'unknown'))
    print(d.get('phase', '?'))
    print(d.get('message', '')[:80])
except:
    print('parse_error')
    print('?')
    print('')
" 2>/dev/null || printf 'parse_error\n?\n\n')

    STATE=$(echo "$PARSED" | sed -n '1p')
    PHASE=$(echo "$PARSED" | sed -n '2p')
    MSG=$(echo "$PARSED" | sed -n '3p')

    case "$STATE" in
        "done")
            if [ "$PHASE" = "complete" ]; then
                echo "$(ts) [Poll $POLL_COUNT] Pipeline COMPLETE: $MSG"
                PIPELINE_DONE=true
                ZIP_REMOTE=$(echo "$STATUS_JSON" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(d.get('zip_path', ''))
" 2>/dev/null || echo "")
                SUB_NAME=$(echo "$STATUS_JSON" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(d.get('submission_name', 'submission'))
" 2>/dev/null || echo "submission")
            else
                echo "$(ts) [Poll $POLL_COUNT] Phase '$PHASE' done: $MSG"
                sleep "$POLL_INTERVAL"
            fi
            ;;
        "failed")
            echo "$(ts) [Poll $POLL_COUNT] Pipeline FAILED at phase '$PHASE': $MSG"
            notify "CV Pipeline FAILED" "Phase: $PHASE. Check pipeline.log on $VM."
            exit 1
            ;;
        "running")
            echo "$(ts) [Poll $POLL_COUNT] Running phase '$PHASE': $MSG"
            sleep "$POLL_INTERVAL"
            ;;
        "not_found")
            echo "$(ts) [Poll $POLL_COUNT] No pipeline_status.json yet (pipeline not started?)"
            sleep "$POLL_INTERVAL"
            ;;
        *)
            echo "$(ts) [Poll $POLL_COUNT] Unknown state: $STATE (phase: $PHASE)"
            sleep "$POLL_INTERVAL"
            ;;
    esac
done

if [ "$PIPELINE_DONE" = false ]; then
    echo "$(ts) Timed out after $MAX_POLLS polls ($((MAX_POLLS * POLL_INTERVAL / 60)) minutes)."
    notify "CV Pipeline Timeout" "No completion after $((MAX_POLLS * POLL_INTERVAL / 3600))h of polling."
    exit 1
fi

echo ""

# ============================================================
# PHASE 2: Download the ZIP
# ============================================================
echo "$(ts) === Downloading submission ZIP ==="

if [ -z "$ZIP_REMOTE" ]; then
    echo "$(ts) ERROR: No zip_path in pipeline_status.json"
    exit 1
fi

ZIP_LOCAL="$DOWNLOAD_DIR/${SUB_NAME}.zip"

gcloud compute scp "$VM:$ZIP_REMOTE" "$ZIP_LOCAL" \
    --zone="$ZONE" --project="$PROJECT"

if [ ! -f "$ZIP_LOCAL" ]; then
    echo "$(ts) ERROR: Download failed, $ZIP_LOCAL not found"
    notify "CV Pipeline" "ZIP download failed"
    exit 1
fi

ZIP_SIZE=$(stat -f%z "$ZIP_LOCAL" 2>/dev/null || stat -c%s "$ZIP_LOCAL" 2>/dev/null)
ZIP_MB=$((ZIP_SIZE / 1024 / 1024))
echo "$(ts) Downloaded: $ZIP_LOCAL (${ZIP_MB}MB)"
echo ""

# ============================================================
# PHASE 3: Local validation with cv_pipeline.sh
# ============================================================
echo "$(ts) === Local Validation ==="

if [ -f "$TOOLS_DIR/cv_pipeline.sh" ]; then
    echo "$(ts) Running cv_pipeline.sh..."
    if bash "$TOOLS_DIR/cv_pipeline.sh" "$ZIP_LOCAL"; then
        VERDICT="PASS"
        echo "$(ts) Local validation PASSED."
    else
        VERDICT="FAIL"
        echo "$(ts) Local validation FAILED. Check output above."
    fi
else
    echo "$(ts) WARNING: cv_pipeline.sh not found at $TOOLS_DIR"
    echo "$(ts) Falling back to validate_cv_zip.py..."
    if python3 "$TOOLS_DIR/validate_cv_zip.py" "$ZIP_LOCAL"; then
        VERDICT="PASS"
    else
        VERDICT="FAIL"
    fi
fi

echo ""

# ============================================================
# DONE
# ============================================================
echo "$(ts) ============================================"
echo "$(ts)  LOCAL ORCHESTRATOR COMPLETE"
echo "$(ts)  ZIP: $ZIP_LOCAL (${ZIP_MB}MB)"
echo "$(ts)  Validation: $VERDICT"
echo "$(ts) ============================================"

if [ "$VERDICT" = "PASS" ]; then
    notify "CV Submission Ready" "$SUB_NAME (${ZIP_MB}MB) validated. Upload when ready."
    echo ""
    echo "$(ts) Ready for JC to upload to competition."
    echo "$(ts) Path: $ZIP_LOCAL"
else
    notify "CV Submission FAILED validation" "$SUB_NAME failed local checks. Review needed."
    echo ""
    echo "$(ts) Submission failed local validation. Review errors above before uploading."
    exit 1
fi
