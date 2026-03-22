#!/bin/bash
set -euo pipefail
ts() { echo "[$(date '+%Y-%m-%d %H:%M:%S')]"; }

echo "$(ts) === ROUND 3: 199 JC labels + auto-labeled rest ==="

PYTHON="$HOME/cv-train/venv/bin/python"
R2_WEIGHTS="$HOME/retrain_round2/yolo11m_gemini/weights/best.pt"
AUTOLABEL_DIR="$HOME/gemini_autolabels_r3"
MERGED_DIR="$HOME/gemini_labels_r3_merged"
JC_LABELS="$HOME/gemini_labels"

# Phase 1: Auto-label with round 2 model
echo "$(ts) Phase 1: Auto-labeling with round 2 model..."
mkdir -p "$AUTOLABEL_DIR"
"$PYTHON" "$HOME/scripts/auto_label_r3.py" "$R2_WEIGHTS" "$AUTOLABEL_DIR"

# Phase 2: Merge (JC labels override auto)
echo "$(ts) Phase 2: Merging labels (JC overrides auto)..."
mkdir -p "$MERGED_DIR"
cp "$AUTOLABEL_DIR"/*.txt "$MERGED_DIR/" 2>/dev/null || true
JC_COUNT=$(find "$JC_LABELS" -name "*.txt" | wc -l | tr -d ' ')
cp "$JC_LABELS"/*.txt "$MERGED_DIR/"
TOTAL=$(find "$MERGED_DIR" -name "*.txt" | wc -l | tr -d ' ')
echo "$(ts) Merged: $TOTAL total ($JC_COUNT JC overrides)"

# Phase 3: Retrain fine-tuning from round 2
echo "$(ts) Phase 3: Retrain round 3..."
"$PYTHON" "$HOME/scripts/retrain_with_gemini.py" \
    --real-annotations "$HOME/trainingdata/train/annotations.json" \
    --real-images "$HOME/trainingdata/train/images" \
    --gemini-images "$HOME/gemini_shelf_gen" \
    --gemini-labels "$MERGED_DIR" \
    --output "$HOME/retrain_round3" \
    --epochs 50 \
    --model "$R2_WEIGHTS"

# Phase 4: Export + ZIP
echo "$(ts) Phase 4: Build ZIP..."
R3_ONNX="$HOME/retrain_round3/yolo11m_gemini/weights/best.onnx"
R3_PT="$HOME/retrain_round3/yolo11m_gemini/weights/best.pt"
if [ ! -f "$R3_ONNX" ]; then
    "$PYTHON" -c "from ultralytics import YOLO; m=YOLO('$R3_PT'); m.export(format='onnx',imgsz=1280,opset=17,simplify=True)"
fi
if [ ! -f "$R3_ONNX" ]; then echo "$(ts) ONNX FAILED"; exit 1; fi

TMPDIR=$(mktemp -d)
cp "$R3_ONNX" "$TMPDIR/best.onnx"
cp "$HOME/run_canonical.py" "$TMPDIR/run.py"
cd "$TMPDIR" && zip "$HOME/submission_round3.zip" run.py best.onnx
rm -rf "$TMPDIR"

echo "$(ts) ZIP: ~/submission_round3.zip"
ls -lh "$HOME/submission_round3.zip"

# Write status
printf '{"phase":"complete","state":"done","message":"Round 3 complete (199 JC labels)","timestamp":"%s","submission_name":"submission_round3","zip_path":"%s/submission_round3.zip"}\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$HOME" > "$HOME/pipeline_status.json"

echo "$(ts) === ROUND 3 COMPLETE ==="
