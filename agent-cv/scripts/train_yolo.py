"""Fine-tune YOLO11m on NorgesGruppen grocery shelf dataset."""
from pathlib import Path
from ultralytics import YOLO


def train():
    dataset_yaml = Path(__file__).parent.parent / "data" / "yolo_dataset" / "dataset.yaml"
    output_dir = Path(__file__).parent.parent / "models"

    model = YOLO("yolo11m.pt")

    results = model.train(
        data=str(dataset_yaml),
        epochs=80,
        imgsz=1280,            # Large images, dense objects - use high resolution
        batch=4,               # Conservative for Mac M3 Pro 36GB
        patience=15,           # Early stopping
        device="mps",          # Mac GPU
        workers=4,
        project=str(output_dir),
        name="yolo11m_ng",
        exist_ok=True,
        # Augmentation for dense shelf scenes
        mosaic=1.0,            # Good for dense detection
        mixup=0.1,             # Light mixup
        scale=0.5,             # Scale jitter
        fliplr=0.5,            # Horizontal flip (shelves are symmetric)
        flipud=0.0,            # NO vertical flip (shelves have gravity)
        hsv_h=0.015,           # Slight color shift
        hsv_s=0.4,             # Saturation variation
        hsv_v=0.3,             # Brightness variation
        degrees=5.0,           # Slight rotation
        translate=0.1,
        # Optimizer
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,              # Cosine decay to 1% of lr0
        weight_decay=0.0005,
        warmup_epochs=5,
        # Loss tuning for dense detection
        box=7.5,               # Box loss weight
        cls=1.5,               # Classification loss weight
        dfl=1.5,               # DFL loss weight
        # Save
        save=True,
        save_period=10,
        plots=True,
        verbose=True,
    )

    print(f"\nTraining complete. Best model: {output_dir}/yolo11m_ng/weights/best.pt")
    return results


if __name__ == "__main__":
    train()
