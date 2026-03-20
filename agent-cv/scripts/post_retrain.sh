#!/bin/bash
# Post-retrain pipeline: export ONNX, run honest eval, prepare for download
# Run on GCP cv-train-1 after retrain_aggressive.py completes

set -e

RETRAIN_DIR="/home/jcfrugaard/retrain/yolo11m_aggressive_v2"
DATASET_DIR="/home/jcfrugaard/augmented_yolo"
ANNOTATIONS="/home/jcfrugaard/trainingdata/train/annotations.json"

echo "============================================"
echo " Post-Retrain Pipeline"
echo "============================================"

# Check if training completed
if [ ! -f "$RETRAIN_DIR/weights/best.pt" ]; then
    echo "ERROR: $RETRAIN_DIR/weights/best.pt not found"
    echo "Training may still be running. Check: tail -5 ~/retrain_aggressive.log"
    exit 1
fi

# Check if ONNX already exported
if [ -f "$RETRAIN_DIR/weights/best.onnx" ]; then
    echo "ONNX already exported"
else
    echo "Exporting ONNX..."
    source ~/cv-train/venv/bin/activate
    python3 -c "
from ultralytics import YOLO
model = YOLO('$RETRAIN_DIR/weights/best.pt')
model.export(format='onnx', imgsz=1280, simplify=True, opset=17)
print('ONNX export complete')
"
fi

echo ""
echo "Running honest evaluation on proper val split..."
source ~/cv-train/venv/bin/activate
python3 ~/honest_eval.py \
    --model "$RETRAIN_DIR/weights/best.onnx" \
    --dataset-dir "$DATASET_DIR" \
    --annotations "$ANNOTATIONS" \
    --conf-threshold 0.15

echo ""
echo "============================================"
echo " Results ready for download:"
echo "   ONNX: $RETRAIN_DIR/weights/best.onnx"
echo "   Eval: $DATASET_DIR/honest_eval_results.json"
echo "============================================"
echo ""
echo "To download:"
echo "  gcloud compute scp cv-train-1:$RETRAIN_DIR/weights/best.onnx ./best_aggressive.onnx --zone=europe-west1-c --project=ai-nm26osl-1779"
