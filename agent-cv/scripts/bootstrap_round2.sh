#!/bin/bash
set -euo pipefail

ts() { echo "[$(date '+%Y-%m-%d %H:%M:%S')]"; }

echo "$(ts) === BOOTSTRAP ROUND 2 ==="
echo "$(ts) Waiting for round 1 to finish..."

# Wait for round 1 training to complete
while ! [ -f ~/retrain_gemini/yolo11m_gemini/weights/best.pt ]; do
    sleep 60
    echo "$(ts) Waiting for round 1 best.pt..."
done

# Wait for round 1 pipeline to fully finish
while pgrep -f gcp_full_pipeline > /dev/null 2>&1; do
    sleep 30
done

ROUND1_WEIGHTS="$HOME/retrain_gemini/yolo11m_gemini/weights/best.pt"
echo "$(ts) Round 1 done. Model: $ROUND1_WEIGHTS"

PYTHON="$HOME/cv-train/venv/bin/python"

# Phase 1: Auto-label ALL generated images with the improved round 1 model
echo "$(ts) === Phase 1: Auto-label with round 1 model ==="
AUTOLABEL_DIR="$HOME/gemini_autolabels"
mkdir -p "$AUTOLABEL_DIR"

"$PYTHON" << 'PYEOF'
from ultralytics import YOLO
from pathlib import Path
from PIL import Image
import os

model_path = os.path.expanduser("~/retrain_gemini/yolo11m_gemini/weights/best.pt")
gen_dir = Path.home() / "gemini_shelf_gen"
out_dir = Path.home() / "gemini_autolabels"

model = YOLO(model_path)
total = 0
labeled = 0

for cat_dir in sorted(gen_dir.iterdir()):
    if not cat_dir.is_dir() or not cat_dir.name.startswith("cat_"):
        continue
    cat_id = int(cat_dir.name.split("_")[1])

    for img_path in sorted(cat_dir.glob("*.jpg")):
        total += 1
        img = Image.open(img_path)
        img_w, img_h = img.size

        results = model(str(img_path), conf=0.15, verbose=False)
        lines = []

        if results and results[0].boxes is not None:
            for box in results[0].boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cx = (x1 + x2) / 2 / img_w
                cy = (y1 + y2) / 2 / img_h
                bw = (x2 - x1) / img_w
                bh = (y2 - y1) / img_h

                if cls == cat_id and conf >= 0.15:
                    lines.append(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                elif conf >= 0.3:
                    lines.append(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

        # If target product not detected, add center crop fallback
        if not any(line.startswith(f"{cat_id} ") for line in lines):
            lines.insert(0, f"{cat_id} 0.500000 0.500000 0.400000 0.400000")

        label_path = out_dir / (img_path.stem + ".txt")
        label_path.write_text("\n".join(lines) + "\n")
        labeled += 1

        if total % 100 == 0:
            print(f"  Labeled {total} images...")

print(f"Done: {labeled}/{total} images auto-labeled")
PYEOF

echo "$(ts) Auto-labeling complete"

# Phase 2: Merge JC labels (override) + auto labels
echo "$(ts) === Phase 2: Merge labels ==="
MERGED_DIR="$HOME/gemini_labels_merged"
mkdir -p "$MERGED_DIR"

# Copy all auto labels first
cp "$AUTOLABEL_DIR"/*.txt "$MERGED_DIR/" 2>/dev/null || true

# JC's manual labels override auto labels
if [ -d "$HOME/gemini_labels" ]; then
    JC_COUNT=$(find "$HOME/gemini_labels" -name "*.txt" | wc -l | tr -d ' ')
    if [ "$JC_COUNT" -gt 0 ]; then
        cp "$HOME/gemini_labels"/*.txt "$MERGED_DIR/"
        echo "$(ts) JC labels override: $JC_COUNT files"
    fi
fi

MERGED_COUNT=$(find "$MERGED_DIR" -name "*.txt" | wc -l | tr -d ' ')
echo "$(ts) Total merged labels: $MERGED_COUNT"

# Phase 3: Retrain with ALL data (fine-tune from round 1 model)
echo "$(ts) === Phase 3: Retrain round 2 ==="
"$PYTHON" "$HOME/scripts/retrain_with_gemini.py" \
    --real-annotations "$HOME/trainingdata/train/annotations.json" \
    --real-images "$HOME/trainingdata/train/images" \
    --gemini-images "$HOME/gemini_shelf_gen" \
    --gemini-labels "$MERGED_DIR" \
    --output "$HOME/retrain_round2" \
    --epochs 50 \
    --model "$ROUND1_WEIGHTS"

# Phase 4: Export ONNX + Build ZIP
echo "$(ts) === Phase 4: Build ZIP ==="
ROUND2_PT="$HOME/retrain_round2/yolo11m_gemini/weights/best.pt"
ROUND2_ONNX="$HOME/retrain_round2/yolo11m_gemini/weights/best.onnx"

if [ ! -f "$ROUND2_ONNX" ]; then
    "$PYTHON" -c "
from ultralytics import YOLO
m = YOLO('$ROUND2_PT')
m.export(format='onnx', imgsz=1280, opset=17, simplify=True)
"
fi

if [ ! -f "$ROUND2_ONNX" ]; then
    echo "$(ts) CRITICAL: ONNX export failed"
    exit 1
fi

bash "$HOME/scripts/build_submission.sh" "$ROUND2_ONNX" "submission_bootstrap_r2"

# Phase 5: Validate
echo "$(ts) === Phase 5: Validate ==="
if [ -f "$HOME/shared/tools/cv_pipeline.sh" ]; then
    bash "$HOME/shared/tools/cv_pipeline.sh" "$HOME/submission_bootstrap_r2.zip" && echo "$(ts) VALIDATION PASSED" || echo "$(ts) VALIDATION FAILED"
else
    echo "$(ts) CRITICAL: cv_pipeline.sh not found, cannot validate"
    exit 1
fi

# Write status for local orchestrator
printf '{"phase":"complete","state":"done","message":"Bootstrap round 2 complete","timestamp":"%s","submission_name":"submission_bootstrap_r2","zip_path":"%s/submission_bootstrap_r2.zip"}\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$HOME" > "$HOME/pipeline_status.json"

echo "$(ts) === BOOTSTRAP ROUND 2 COMPLETE ==="
echo "$(ts) ZIP: ~/submission_bootstrap_r2.zip"
