#!/bin/bash
# GCP Full Pipeline: auto-label -> retrain -> ONNX -> build ZIP -> validate
# Runs UNATTENDED on GCP VM (cv-train-1 or cv-train-4).
#
# Usage:
#   nohup bash ~/scripts/gcp_full_pipeline.sh 2>&1 | tee ~/pipeline.log &
#
# Prerequisites:
#   - ~/cv-train/venv/ with ultralytics, PIL, etc.
#   - ~/retrain/yolo11m_maxdata_200ep/weights/best.pt (base weights)
#   - ~/trainingdata/train/ (real images + annotations.json)
#   - ~/gemini_shelf_gen/ (generated images)
#   - ~/gemini_labels/ (JC's labels + auto-labels)
#   - ~/shared/tools/cv_pipeline.sh + validate_cv_zip.py
#   - ~/scripts/ containing yolo_second_pass.py, retrain_with_gemini.py, build_submission.sh

set -euo pipefail

# --- Configuration ---
VENV="$HOME/cv-train/venv/bin"
PYTHON="$VENV/python"
SCRIPTS_DIR="$HOME/scripts"
TOOLS_DIR="$HOME/shared/tools"

# Paths
BASE_WEIGHTS="$HOME/retrain/yolo11m_maxdata_200ep/weights/best.pt"
IMAGES_DIR="$HOME/gemini_shelf_gen"
LABELS_DIR="$HOME/gemini_labels"
REAL_ANNOTATIONS="$HOME/trainingdata/train/annotations.json"
REAL_IMAGES="$HOME/trainingdata/train/images"
RETRAIN_OUTPUT="$HOME/retrain_gemini"
SUBMISSION_NAME="submission_gemini_$(date +%Y%m%d_%H%M)"

# Status file (local_orchestrator.sh polls this)
STATUS_FILE="$HOME/pipeline_status.json"

# --- Helpers ---
ts() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]"
}

write_status() {
    local phase="$1"
    local state="$2"
    local msg="${3:-}"
    cat > "$STATUS_FILE" << STATUSEOF
{
  "phase": "$phase",
  "state": "$state",
  "message": "$msg",
  "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "submission_name": "$SUBMISSION_NAME",
  "zip_path": "$HOME/${SUBMISSION_NAME}.zip"
}
STATUSEOF
}

cleanup_on_error() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo ""
        echo "$(ts) PIPELINE FAILED at phase: ${CURRENT_PHASE:-unknown}"
        echo "$(ts) Exit code: $exit_code"
        write_status "${CURRENT_PHASE:-unknown}" "failed" "Exit code $exit_code"
    fi
}
trap cleanup_on_error EXIT

CURRENT_PHASE="init"

# --- Preflight checks ---
echo "$(ts) === GCP Full Pipeline ==="
echo "$(ts) Submission: $SUBMISSION_NAME"
echo ""

echo "$(ts) Preflight checks..."
for f in "$PYTHON" "$BASE_WEIGHTS" "$REAL_ANNOTATIONS" "$SCRIPTS_DIR/yolo_second_pass.py" \
         "$SCRIPTS_DIR/retrain_with_gemini.py" "$SCRIPTS_DIR/build_submission.sh"; do
    if [ ! -f "$f" ]; then
        echo "$(ts) MISSING: $f"
        exit 1
    fi
done

if [ ! -d "$IMAGES_DIR" ]; then
    echo "$(ts) MISSING directory: $IMAGES_DIR"
    exit 1
fi

if [ ! -d "$LABELS_DIR" ]; then
    echo "$(ts) MISSING directory: $LABELS_DIR"
    exit 1
fi

LABEL_COUNT=$(find "$LABELS_DIR" -name "*.txt" | wc -l | tr -d ' ')
echo "$(ts) Labels found: $LABEL_COUNT"
if [ "$LABEL_COUNT" -eq 0 ]; then
    echo "$(ts) WARNING: No label files in $LABELS_DIR. Auto-label will have nothing to augment."
    echo "$(ts) Continuing anyway (retrain will use real data only)."
fi

echo "$(ts) All preflight checks passed."
write_status "init" "running" "Preflight passed, starting pipeline"
echo ""

# ============================================================
# PHASE 1: Auto-label (YOLO second pass)
# ============================================================
CURRENT_PHASE="auto_label"
echo "$(ts) === PHASE 1: Auto-Label (YOLO Second Pass) ==="
write_status "auto_label" "running" "Running YOLO second pass on labeled images"

if [ "$LABEL_COUNT" -gt 0 ]; then
    "$PYTHON" "$SCRIPTS_DIR/yolo_second_pass.py" \
        --images-dir "$IMAGES_DIR" \
        --labels-dir "$LABELS_DIR" \
        --model "$BASE_WEIGHTS" \
        --conf 0.30
    echo "$(ts) Auto-label complete."
else
    echo "$(ts) Skipping auto-label (no label files to augment)."
fi

LABEL_COUNT_AFTER=$(find "$LABELS_DIR" -name "*.txt" | wc -l | tr -d ' ')
echo "$(ts) Labels after auto-label: $LABEL_COUNT_AFTER"
write_status "auto_label" "done" "Labels: $LABEL_COUNT -> $LABEL_COUNT_AFTER"
echo ""

# ============================================================
# PHASE 2: Retrain (fine-tune from best weights, 50 epochs)
# ============================================================
CURRENT_PHASE="retrain"
echo "$(ts) === PHASE 2: Retrain (50 epochs from best weights) ==="
write_status "retrain" "running" "Fine-tuning YOLO11m, 50 epochs"

"$PYTHON" "$SCRIPTS_DIR/retrain_with_gemini.py" \
    --real-annotations "$REAL_ANNOTATIONS" \
    --real-images "$REAL_IMAGES" \
    --gemini-images "$IMAGES_DIR" \
    --gemini-labels "$LABELS_DIR" \
    --output "$RETRAIN_OUTPUT" \
    --epochs 50 \
    --model "$BASE_WEIGHTS"

# Find the best weights from this training run
NEW_WEIGHTS="$RETRAIN_OUTPUT/yolo11m_gemini/weights/best.pt"
if [ ! -f "$NEW_WEIGHTS" ]; then
    echo "$(ts) ERROR: Training did not produce best.pt at $NEW_WEIGHTS"
    exit 1
fi

NEW_ONNX="$RETRAIN_OUTPUT/yolo11m_gemini/weights/best.onnx"
if [ ! -f "$NEW_ONNX" ]; then
    echo "$(ts) WARNING: ONNX not found, retrain script should have exported it."
    echo "$(ts) Exporting manually..."
    "$PYTHON" -c "
from ultralytics import YOLO
m = YOLO('$NEW_WEIGHTS')
m.export(format='onnx', imgsz=1280, opset=17, simplify=True)
print('ONNX exported')
"
fi

echo "$(ts) Retrain complete."
echo "$(ts) Best weights: $NEW_WEIGHTS"
echo "$(ts) ONNX: $NEW_ONNX"
write_status "retrain" "done" "Weights at $NEW_WEIGHTS"
echo ""

# ============================================================
# PHASE 3: Build submission ZIP
# ============================================================
CURRENT_PHASE="build_zip"
echo "$(ts) === PHASE 3: Build Submission ZIP ==="
write_status "build_zip" "running" "Building $SUBMISSION_NAME.zip"

bash "$SCRIPTS_DIR/build_submission.sh" "$NEW_WEIGHTS" "$SUBMISSION_NAME"

ZIP_PATH="$HOME/${SUBMISSION_NAME}.zip"
if [ ! -f "$ZIP_PATH" ]; then
    echo "$(ts) ERROR: ZIP not found at $ZIP_PATH"
    exit 1
fi

ZIP_SIZE=$(stat -c%s "$ZIP_PATH" 2>/dev/null || stat -f%z "$ZIP_PATH" 2>/dev/null)
ZIP_MB=$((ZIP_SIZE / 1024 / 1024))
echo "$(ts) ZIP created: $ZIP_PATH (${ZIP_MB}MB)"
write_status "build_zip" "done" "ZIP: ${ZIP_MB}MB"
echo ""

# ============================================================
# PHASE 4: Validate with cv_pipeline.sh
# ============================================================
CURRENT_PHASE="validate"
echo "$(ts) === PHASE 4: Validate with cv_pipeline.sh ==="
write_status "validate" "running" "Running cv_pipeline.sh validation"

# cv_pipeline.sh uses a hardcoded TOOLS_DIR for the main repo.
# On GCP, we call validate_cv_zip.py directly since the full pipeline
# tools (profiler, judge) may not be available.
if [ -f "$TOOLS_DIR/cv_pipeline.sh" ]; then
    bash "$TOOLS_DIR/cv_pipeline.sh" "$ZIP_PATH" && VALID=true || VALID=false
elif [ -f "$TOOLS_DIR/validate_cv_zip.py" ]; then
    echo "$(ts) cv_pipeline.sh not found, falling back to validate_cv_zip.py"
    "$PYTHON" "$TOOLS_DIR/validate_cv_zip.py" "$ZIP_PATH" && VALID=true || VALID=false
else
    echo "$(ts) WARNING: No validation tools found at $TOOLS_DIR"
    echo "$(ts) Running basic blocked-import check..."
    TMPDIR=$(mktemp -d)
    unzip -q "$ZIP_PATH" -d "$TMPDIR"
    if grep -rn "import os\b\|import sys\b\|import subprocess\|import socket\|import pickle" "$TMPDIR/run.py"; then
        echo "$(ts) BLOCKED IMPORT FOUND"
        VALID=false
    else
        echo "$(ts) No blocked imports found (basic check)"
        VALID=true
    fi
    rm -rf "$TMPDIR"
fi

if [ "$VALID" = true ]; then
    echo "$(ts) Validation PASSED."
    write_status "validate" "done" "Validation passed"
else
    echo "$(ts) Validation FAILED. ZIP may still be useful, check errors above."
    write_status "validate" "failed" "Validation failed, check pipeline.log"
    exit 1
fi
echo ""

# ============================================================
# DONE
# ============================================================
CURRENT_PHASE="complete"
echo "$(ts) ============================================"
echo "$(ts)  PIPELINE COMPLETE"
echo "$(ts)  ZIP: $ZIP_PATH (${ZIP_MB}MB)"
echo "$(ts)  Validation: PASSED"
echo "$(ts) ============================================"
write_status "complete" "done" "Ready for download. ZIP: $ZIP_PATH (${ZIP_MB}MB)"

echo ""
echo "$(ts) local_orchestrator.sh will pick this up automatically."
echo "$(ts) Or download manually:"
echo "$(ts)   gcloud compute scp \$(hostname):$ZIP_PATH ./ --zone=\$(curl -s -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4) --project=ai-nm26osl-1779"
