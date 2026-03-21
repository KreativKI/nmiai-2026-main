#!/bin/bash
# Quick submission assembly line.
# Usage: bash quick_submit.sh <vm-name> <zone> <retrain-dir> <submission-name>
# Example: bash quick_submit.sh cv-train-3 europe-west1-b /home/jcfrugaard/retrain/yolo11l_aggressive submission_yolo11l
#
# Steps: export ONNX on GCP -> download -> build ZIP -> pipeline -> canary -> READY
set -e

VM="${1:?Usage: quick_submit.sh <vm-name> <zone> <retrain-dir> <submission-name>}"
ZONE="${2:?Missing zone}"
RETRAIN_DIR="${3:?Missing retrain dir on GCP}"
SUB_NAME="${4:?Missing submission name}"
PROJECT="ai-nm26osl-1779"

WORKTREE="/Volumes/devdrive/github_dev/nmiai-worktree-cv"
TOOLS="/Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools"
RUN_PY="$WORKTREE/agent-cv/solutions/run_yolo_only.py"
ZIP_PATH="$WORKTREE/agent-cv/${SUB_NAME}.zip"

echo "============================================"
echo " Quick Submit Pipeline"
echo " VM: $VM ($ZONE)"
echo " Model: $RETRAIN_DIR"
echo " Output: $ZIP_PATH"
echo "============================================"

# Step 1: Export ONNX on GCP (if not already done)
echo ""
echo "--- Step 1: Export ONNX ---"
gcloud compute ssh "$VM" --zone="$ZONE" --project="$PROJECT" --command="
if [ -f '$RETRAIN_DIR/weights/best.onnx' ]; then
    echo 'ONNX already exists'
    ls -la '$RETRAIN_DIR/weights/best.onnx'
else
    echo 'Exporting ONNX...'
    source ~/cv-train/venv/bin/activate
    python3 -c \"
from ultralytics import YOLO
model = YOLO('$RETRAIN_DIR/weights/best.pt')
model.export(format='onnx', imgsz=1280, simplify=True, opset=17)
print('Done')
\"
fi
"

# Step 2: Download ONNX
echo ""
echo "--- Step 2: Download ONNX ---"
ONNX_LOCAL="/tmp/${SUB_NAME}_best.onnx"
gcloud compute scp "$VM:$RETRAIN_DIR/weights/best.onnx" "$ONNX_LOCAL" \
    --zone="$ZONE" --project="$PROJECT"
ls -la "$ONNX_LOCAL"

# Step 3: Build ZIP
echo ""
echo "--- Step 3: Build ZIP ---"
TMPDIR="/tmp/${SUB_NAME}_build"
rm -rf "$TMPDIR"
mkdir -p "$TMPDIR"
cp "$RUN_PY" "$TMPDIR/run.py"
cp "$ONNX_LOCAL" "$TMPDIR/best.onnx"
cd "$TMPDIR"
zip -r "$ZIP_PATH" run.py best.onnx
ls -la "$ZIP_PATH"

# Step 4: Pipeline validation
echo ""
echo "--- Step 4: Pipeline Validation ---"
bash "$TOOLS/cv_pipeline.sh" "$ZIP_PATH"

echo ""
echo "============================================"
echo " ZIP READY: $ZIP_PATH"
echo " Run canary agent manually, then hand to JC."
echo "============================================"
