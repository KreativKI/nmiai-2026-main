#!/bin/bash
# Generation Watcher: monitors Gemini shelf generation, then preps label batches.
# Runs on GCP VM alongside a generation script (gemini_shelf_gen*.py).
#
# Usage:
#   # First, start generation in background:
#   nohup ~/cv-train/venv/bin/python ~/scripts/gemini_shelf_gen_v3_angles.py 2>&1 | tee ~/gen.log &
#   GEN_PID=$!
#
#   # Then start the watcher:
#   bash ~/scripts/gen_watcher.sh $GEN_PID
#
#   # Or without a PID (watches progress.json only, runs batch prep when stable):
#   bash ~/scripts/gen_watcher.sh
#
# What it does:
#   1. Polls progress.json for generation progress
#   2. Waits for the generation process to exit (if PID given)
#      OR waits for progress.json to stabilize (no changes for 5 min)
#   3. Runs prepare_label_batches.py
#   4. Writes gen_complete.json marker

set -euo pipefail

# --- Configuration ---
VENV="$HOME/cv-train/venv/bin"
PYTHON="$VENV/python"
SCRIPTS_DIR="$HOME/scripts"
GEN_DIR="$HOME/gemini_shelf_gen"
PROGRESS_FILE="$GEN_DIR/progress.json"
MARKER_FILE="$HOME/gen_complete.json"
POLL_INTERVAL=60         # Check every 60 seconds
STABLE_THRESHOLD=300     # 5 minutes with no progress.json change = done

GEN_PID="${1:-}"

# --- Helpers ---
ts() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]"
}

write_marker() {
    local state="$1"
    local msg="${2:-}"
    local img_count="${3:-0}"
    cat > "$MARKER_FILE" << MARKEREOF
{
  "state": "$state",
  "message": "$msg",
  "image_count": $img_count,
  "gen_dir": "$GEN_DIR",
  "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
}
MARKEREOF
}

get_image_count() {
    find "$GEN_DIR" -name "*.jpg" 2>/dev/null | wc -l | tr -d ' '
}

get_progress_mtime() {
    if [ -f "$PROGRESS_FILE" ]; then
        stat -c%Y "$PROGRESS_FILE" 2>/dev/null || stat -f%m "$PROGRESS_FILE" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

# --- Main ---
echo "$(ts) === Generation Watcher ==="
echo "$(ts) Watching: $GEN_DIR"
echo "$(ts) Progress file: $PROGRESS_FILE"
if [ -n "$GEN_PID" ]; then
    echo "$(ts) Tracking PID: $GEN_PID"
    if ! kill -0 "$GEN_PID" 2>/dev/null; then
        echo "$(ts) WARNING: PID $GEN_PID is not running. Will watch progress.json only."
        GEN_PID=""
    fi
else
    echo "$(ts) No PID given. Watching progress.json stability."
fi

write_marker "watching" "Monitoring generation progress"

LAST_MTIME=$(get_progress_mtime)
STABLE_SINCE=$(date +%s)
DONE=false

while [ "$DONE" = false ]; do
    sleep "$POLL_INTERVAL"

    IMG_COUNT=$(get_image_count)
    CURRENT_MTIME=$(get_progress_mtime)
    NOW=$(date +%s)

    # Report progress
    if [ -f "$PROGRESS_FILE" ]; then
        # Count completed categories from progress.json
        CAT_DONE=$("$PYTHON" -c "
import json
try:
    p = json.load(open('$PROGRESS_FILE'))
    print(len(p) if isinstance(p, dict) else 0)
except Exception:
    print(0)
" 2>/dev/null || echo "?")
        echo "$(ts) Progress: $IMG_COUNT images, $CAT_DONE categories done"
    else
        echo "$(ts) Progress: $IMG_COUNT images (no progress.json yet)"
    fi

    # Check if generation process exited (if we have a PID)
    if [ -n "$GEN_PID" ]; then
        if ! kill -0 "$GEN_PID" 2>/dev/null; then
            echo "$(ts) Generation process (PID $GEN_PID) has exited."
            # Verify generation produced images (not a crash with 0 output)
            FINAL_COUNT=$(get_image_count)
            if [ "$FINAL_COUNT" -eq 0 ]; then
                echo "$(ts) WARNING: Process exited but 0 images generated. Possible crash."
                echo "$(ts) Check generation log for errors."
            fi
            DONE=true
            continue
        fi
    fi

    # Check progress.json stability (no PID, or as a secondary signal)
    if [ "$CURRENT_MTIME" != "$LAST_MTIME" ]; then
        LAST_MTIME="$CURRENT_MTIME"
        STABLE_SINCE=$NOW
    else
        ELAPSED=$((NOW - STABLE_SINCE))
        if [ "$ELAPSED" -ge "$STABLE_THRESHOLD" ] && [ -z "$GEN_PID" ]; then
            echo "$(ts) progress.json unchanged for $((ELAPSED))s. Generation appears complete."
            DONE=true
        fi
    fi
done

echo ""
IMG_COUNT=$(get_image_count)
echo "$(ts) Generation finished. Total images: $IMG_COUNT"
write_marker "gen_done" "Generation complete, preparing batches" "$IMG_COUNT"

# ============================================================
# Run prepare_label_batches.py
# ============================================================
echo ""
echo "$(ts) === Running prepare_label_batches.py ==="

if [ -f "$SCRIPTS_DIR/prepare_label_batches.py" ]; then
    "$PYTHON" "$SCRIPTS_DIR/prepare_label_batches.py"
    echo "$(ts) Label batches prepared."
    BATCH_COUNT=$(find "$HOME/label_batches" -name "batch_*" -type d 2>/dev/null | wc -l | tr -d ' ')
    echo "$(ts) Batches created: $BATCH_COUNT"
    write_marker "complete" "Generation done, $BATCH_COUNT label batches ready" "$IMG_COUNT"
else
    echo "$(ts) WARNING: prepare_label_batches.py not found at $SCRIPTS_DIR"
    echo "$(ts) Skipping batch preparation."
    write_marker "complete" "Generation done, batch prep skipped (script not found)" "$IMG_COUNT"
fi

echo ""
echo "$(ts) ============================================"
echo "$(ts)  GENERATION WATCHER COMPLETE"
echo "$(ts)  Images: $IMG_COUNT"
echo "$(ts)  Marker: $MARKER_FILE"
echo "$(ts) ============================================"
