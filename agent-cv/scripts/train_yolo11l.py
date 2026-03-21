#!/usr/bin/env python3
"""Train YOLO11l (larger backbone) on augmented dataset.

25.3M params vs 20.1M for YOLO11m. Same aggressive augmentation.
Run on a separate GCP VM (cv-train-3) in parallel.

Usage (on GCP VM):
    source ~/cv-train/venv/bin/activate
    python3 train_yolo11l.py
"""

from pathlib import Path
from ultralytics import YOLO

DATASET_YAML = "/home/jcfrugaard/augmented_yolo/dataset.yaml"
OUTPUT_DIR = "/home/jcfrugaard/retrain"
RUN_NAME = "yolo11l_aggressive"

TRAIN_CONFIG = {
    "data": DATASET_YAML,
    "epochs": 120,
    "batch": 2,  # Smaller batch for larger model
    "imgsz": 1280,
    "device": 0,
    "project": OUTPUT_DIR,
    "name": RUN_NAME,
    "exist_ok": True,
    "pretrained": True,
    "patience": 25,
    "mosaic": 1.0,
    "mixup": 0.3,
    "copy_paste": 0.3,
    "hsv_h": 0.02,
    "hsv_s": 0.7,
    "hsv_v": 0.4,
    "degrees": 5.0,
    "translate": 0.15,
    "scale": 0.5,
    "fliplr": 0.5,
    "erasing": 0.3,
    "optimizer": "auto",
    "lr0": 0.01,
    "cos_lr": True,
    "close_mosaic": 15,
    "amp": True,
    "workers": 4,
}


def main():
    print("=" * 55)
    print("  YOLO11l Aggressive Retrain")
    print("=" * 55)

    if not Path(DATASET_YAML).exists():
        print(f"ERROR: Dataset not found at {DATASET_YAML}")
        return 1

    model = YOLO("yolo11l.pt")
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
