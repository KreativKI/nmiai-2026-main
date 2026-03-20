"""Export trained YOLO model to ONNX for competition sandbox."""
from pathlib import Path
from ultralytics import YOLO


def export(model_path: str = None):
    models_dir = Path(__file__).parent.parent / "models"

    if model_path is None:
        # Find best.pt from training
        best = models_dir / "yolo11m_ng" / "weights" / "best.pt"
        if not best.exists():
            print(f"ERROR: {best} not found. Train first.")
            return
        model_path = str(best)

    print(f"Loading model: {model_path}")
    model = YOLO(model_path)

    # Export to ONNX with FP16 quantization
    output = model.export(
        format="onnx",
        imgsz=1280,
        half=False,          # FP16 on export (may not work on CPU, try FP32 first)
        simplify=True,       # Simplify ONNX graph
        opset=17,            # Compatible with onnxruntime 1.20.0
        dynamic=False,       # Fixed input size for faster inference
    )

    print(f"ONNX exported: {output}")

    # Check file size
    onnx_path = Path(output)
    size_mb = onnx_path.stat().st_size / (1024 * 1024)
    print(f"Size: {size_mb:.1f} MB (limit: 420 MB)")

    if size_mb > 420:
        print("WARNING: Exceeds 420 MB limit! Consider FP16 quantization or smaller model.")

    return output


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default=None, help="Path to .pt model")
    args = parser.parse_args()
    export(args.model)
