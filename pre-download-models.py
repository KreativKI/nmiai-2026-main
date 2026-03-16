"""
Pre-download model weights to shared/models/ and HuggingFace cache.
Run this before competition day so models are cached locally.

Usage:
    source agent-cv/.venv/bin/activate
    python pre-download-models.py
"""

from pathlib import Path

SHARED_MODELS = Path(__file__).parent / "shared" / "models"
SHARED_MODELS.mkdir(parents=True, exist_ok=True)


def download_torchvision_models():
    """Pre-download torchvision model weights."""
    print("\n=== Torchvision Models ===")
    import torch
    from torchvision import models

    print("  Downloading ResNet50...")
    models.resnet50(weights=models.ResNet50_Weights.DEFAULT)

    print("  Downloading EfficientNet-B0...")
    models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)

    print("  Downloading MobileNet-V3-Small...")
    models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)

    print("  All torchvision models cached in ~/.cache/torch/")


def download_yolo_models():
    """Pre-download YOLO models to shared/models/."""
    print("\n=== YOLO Models ===")
    from ultralytics import YOLO

    for size in ["yolov8n", "yolov8s"]:
        dest = SHARED_MODELS / f"{size}.pt"
        if dest.exists():
            print(f"  {size}: already cached at {dest}")
            continue
        print(f"  Downloading {size}...")
        model = YOLO(f"{size}.pt")
        # Move the downloaded model to shared/models/
        downloaded = Path(f"{size}.pt")
        if downloaded.exists():
            downloaded.rename(dest)
            print(f"  {size}: saved to {dest}")
        else:
            print(f"  {size}: downloaded (check ultralytics cache)")


def download_sentence_transformers():
    """Pre-download sentence-transformer models."""
    print("\n=== Sentence Transformers ===")
    from sentence_transformers import SentenceTransformer

    models_to_cache = [
        "all-MiniLM-L6-v2",        # Fast, good general purpose
        "all-mpnet-base-v2",        # Higher quality, slower
    ]

    for model_name in models_to_cache:
        print(f"  Downloading {model_name}...")
        SentenceTransformer(model_name)
        print(f"  {model_name}: cached in ~/.cache/huggingface/")


def download_multilingual_models():
    """Pre-download multilingual models for potential Norwegian text tasks."""
    print("\n=== Multilingual Models (for Norwegian) ===")
    from sentence_transformers import SentenceTransformer

    print("  Downloading multilingual-e5-large...")
    SentenceTransformer("intfloat/multilingual-e5-large")
    print("  multilingual-e5-large: cached")


def verify_downloads():
    """Verify all models are accessible."""
    print("\n=== Verification ===")
    import torch
    from torchvision import models

    # Torchvision
    m = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
    print(f"  ResNet50: OK ({sum(p.numel() for p in m.parameters())/1e6:.1f}M params)")

    # YOLO
    yolo_path = SHARED_MODELS / "yolov8n.pt"
    if yolo_path.exists():
        print(f"  YOLOv8n: OK ({yolo_path.stat().st_size / 1e6:.1f} MB)")
    else:
        print(f"  YOLOv8n: check ultralytics cache")

    # Sentence transformers
    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer("all-MiniLM-L6-v2")
    emb = st.encode(["test"])
    print(f"  all-MiniLM-L6-v2: OK (dim={emb.shape[1]})")

    print("\nAll models ready.")


if __name__ == "__main__":
    print("Pre-downloading models for NM i AI 2026...")
    print(f"Shared models dir: {SHARED_MODELS}")

    download_torchvision_models()
    download_yolo_models()
    download_sentence_transformers()

    # Multilingual models are large (~2.3 GB). Uncomment if needed:
    # download_multilingual_models()

    verify_downloads()
