#!/usr/bin/env python3
"""Train YOLO11m on maximum data with 200 epochs.

Uses all available training data: real + synth v1 + synth v2 + Gemini.
Longer training (200 epochs) with aggressive augmentation.

Usage (on GCP VM):
    source ~/cv-train/venv/bin/activate
    python3 train_yolo11m_maxdata.py
"""

from pathlib import Path
from ultralytics import YOLO

DATASET_YAML = "/home/jcfrugaard/maxdata_yolo/dataset.yaml"
OUTPUT_DIR = "/home/jcfrugaard/retrain"
RUN_NAME = "yolo11m_maxdata_200ep"

TRAIN_CONFIG = {
    "data": DATASET_YAML,
    "epochs": 200,
    "batch": 4,
    "imgsz": 1280,
    "device": 0,
    "project": OUTPUT_DIR,
    "name": RUN_NAME,
    "exist_ok": True,
    "pretrained": True,
    "patience": 30,
    # Aggressive augmentation
    "mosaic": 1.0,
    "mixup": 0.3,
    "copy_paste": 0.5,  # Heavier copy-paste
    "hsv_h": 0.02,
    "hsv_s": 0.7,
    "hsv_v": 0.4,
    "degrees": 10.0,     # More rotation
    "translate": 0.2,    # More translation
    "scale": 0.5,
    "fliplr": 0.5,
    "erasing": 0.4,
    "optimizer": "auto",
    "lr0": 0.01,
    "cos_lr": True,
    "close_mosaic": 20,
    "amp": True,
    "workers": 4,
}


def main():
    print("=" * 55)
    print("  YOLO11m MaxData 200-Epoch Retrain")
    print("=" * 55)

    if not Path(DATASET_YAML).exists():
        print(f"ERROR: {DATASET_YAML} not found")
        print("Run prepare_maxdata_dataset.py first")
        return 1

    model = YOLO("yolo11m.pt")
    model.train(**TRAIN_CONFIG)

    # Export to ONNX
    best_pt = Path(OUTPUT_DIR) / RUN_NAME / "weights" / "best.pt"
    if best_pt.exists():
        best_model = YOLO(str(best_pt))
        best_model.export(format="onnx", imgsz=1280, simplify=True, opset=17)
        print("ONNX export complete")

    return 0


if __name__ == "__main__":
    exit(main())
