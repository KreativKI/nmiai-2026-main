#!/usr/bin/env python3
"""Retrain YOLO11m with aggressive augmentation on properly-split dataset.

Battle plan Phase 3: aggressive augmentation to fight overfitting.

Usage (on GCP cv-train-1):
    source ~/cv-train/venv/bin/activate
    python3 retrain_aggressive.py
"""

from pathlib import Path

from ultralytics import YOLO

DATASET_YAML = "/home/jcfrugaard/augmented_yolo/dataset.yaml"
OUTPUT_DIR = "/home/jcfrugaard/retrain"
RUN_NAME = "yolo11m_aggressive_v2"

# Battle plan augmentation config
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
    # Aggressive augmentation (battle plan)
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
    # Keep good defaults
    "optimizer": "auto",
    "lr0": 0.01,
    "cos_lr": True,
    "close_mosaic": 15,
    "amp": True,
    "workers": 4,
}


def main():
    print("=" * 55)
    print("  YOLO11m Aggressive Retrain (Battle Plan Phase 3)")
    print("=" * 55)
    print(f"  Dataset: {DATASET_YAML}")
    print(f"  Output: {OUTPUT_DIR}/{RUN_NAME}")
    print(f"  Epochs: {TRAIN_CONFIG['epochs']}")
    print(f"  Key augmentation: mosaic={TRAIN_CONFIG['mosaic']}, "
          f"mixup={TRAIN_CONFIG['mixup']}, copy_paste={TRAIN_CONFIG['copy_paste']}, "
          f"scale={TRAIN_CONFIG['scale']}")
    print()

    # Verify dataset exists
    if not Path(DATASET_YAML).exists():
        print(f"ERROR: Dataset not found at {DATASET_YAML}")
        print("Run prepare_augmented_dataset.py first")
        return 1

    model = YOLO("yolo11m.pt")
    results = model.train(**TRAIN_CONFIG)

    # Export to ONNX
    print("\nExporting to ONNX...")
    best_pt = Path(OUTPUT_DIR) / RUN_NAME / "weights" / "best.pt"
    if best_pt.exists():
        best_model = YOLO(str(best_pt))
        best_model.export(format="onnx", imgsz=1280, simplify=True, opset=17)
        print("ONNX export complete")
    else:
        print(f"WARNING: best.pt not found at {best_pt}")

    print("\nDone! Check results at:")
    print(f"  {OUTPUT_DIR}/{RUN_NAME}/")

    return 0


if __name__ == "__main__":
    exit(main())
