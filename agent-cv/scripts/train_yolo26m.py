#!/usr/bin/env python3
"""Train YOLO26m on augmented dataset.

YOLO26 has Small-Target-Aware Label Assignment (STAL) which is ideal for
small grocery products on shelves. Released Jan 2026.

Usage (on GCP VM):
    source ~/cv-train/venv/bin/activate
    python3 train_yolo26m.py
"""

from pathlib import Path
from ultralytics import YOLO

DATASET_YAML = "/home/jcfrugaard/augmented_yolo/dataset.yaml"
OUTPUT_DIR = "/home/jcfrugaard/retrain"
RUN_NAME = "yolo26m_aggressive"

TRAIN_CONFIG = {
    "data": DATASET_YAML,
    "epochs": 120,
    "batch": 4,
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
    print("  YOLO26m Aggressive Retrain (STAL for small products)")
    print("=" * 55)

    if not Path(DATASET_YAML).exists():
        print(f"ERROR: {DATASET_YAML} not found")
        return 1

    # YOLO26m: try to download, fall back to yolo11m if not available
    try:
        model = YOLO("yolo26m.pt")
        print("Using YOLO26m")
    except Exception as e:
        print(f"YOLO26m not available ({e}), trying yolov10m...")
        try:
            model = YOLO("yolov10m.pt")
            print("Using YOLOv10m")
        except Exception:
            print("Falling back to yolo11m.pt")
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
