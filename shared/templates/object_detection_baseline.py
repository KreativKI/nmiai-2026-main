"""
Object Detection Baseline -- NM i AI 2026
YOLO inference wrapper for detection/segmentation tasks.

Prerequisites: pip install ultralytics
Pre-download models to shared/models/ before competition.

Usage:
    1. Copy to agent-cv/solutions/bot_v1.py
    2. Update IMAGE_DIR, MODEL_SIZE, CLASSES
    3. Run: python bot_v1.py
"""

import json
import os
from pathlib import Path
from ultralytics import YOLO

# === CONFIGURE THESE ===
IMAGE_DIR = "data/test_images/"         # Directory with test images
MODEL_SIZE = "yolov8n"                  # yolov8n / yolov8s / yolov8m / yolov8l
CONFIDENCE_THRESHOLD = 0.25
IOU_THRESHOLD = 0.45
CLASSES = None                          # None = all classes, or [0, 1, 2] for specific
TASK = "detect"                         # detect / segment / classify
OUTPUT_PATH = "predictions.json"
# ========================


def load_model():
    """Load YOLO model. Checks shared/models/ cache first."""
    cache_path = f"../shared/models/{MODEL_SIZE}.pt"
    if os.path.exists(cache_path):
        print(f"Loading from cache: {cache_path}")
        model = YOLO(cache_path)
    else:
        print(f"Downloading {MODEL_SIZE}...")
        model = YOLO(f"{MODEL_SIZE}.pt")

    return model


def run_inference(model):
    """Run detection on all images."""
    image_dir = Path(IMAGE_DIR)
    image_files = sorted(
        [f for f in image_dir.iterdir()
         if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".tiff")]
    )

    print(f"Found {len(image_files)} images in {IMAGE_DIR}")

    all_predictions = []

    for img_path in image_files:
        results = model(
            str(img_path),
            conf=CONFIDENCE_THRESHOLD,
            iou=IOU_THRESHOLD,
            classes=CLASSES,
            verbose=False,
        )

        result = results[0]
        image_preds = {
            "image": img_path.name,
            "detections": [],
        }

        if result.boxes is not None:
            for box in result.boxes:
                det = {
                    "class_id": int(box.cls[0]),
                    "class_name": result.names[int(box.cls[0])],
                    "confidence": float(box.conf[0]),
                    "bbox": [float(x) for x in box.xyxy[0].tolist()],
                }
                image_preds["detections"].append(det)

        all_predictions.append(image_preds)

    return all_predictions


def save_predictions(predictions):
    """Save predictions to JSON."""
    with open(OUTPUT_PATH, "w") as f:
        json.dump(predictions, f, indent=2)
    print(f"Predictions saved to {OUTPUT_PATH}")

    total_dets = sum(len(p["detections"]) for p in predictions)
    print(f"Total detections: {total_dets} across {len(predictions)} images")
    print(f"Avg detections per image: {total_dets / max(len(predictions), 1):.1f}")


def main():
    model = load_model()
    predictions = run_inference(model)
    save_predictions(predictions)

    total_dets = sum(len(p["detections"]) for p in predictions)
    print(f"\n--- For MEMORY.md ---")
    print(f"Approach: {MODEL_SIZE} ({TASK})")
    print(f"Confidence threshold: {CONFIDENCE_THRESHOLD}")
    print(f"Images processed: {len(predictions)}")
    print(f"Total detections: {total_dets}")


if __name__ == "__main__":
    main()
