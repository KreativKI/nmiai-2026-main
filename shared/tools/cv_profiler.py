#!/usr/bin/env python3
"""Profile a CV submission ZIP: extract, load models, run inference, time each stage.

Runs against test_images/ to measure wall time per stage vs 300s competition timeout.
Prefers Docker (mirrors competition sandbox). Falls back to native Python if Docker unavailable.

Usage: python3 shared/tools/cv_profiler.py agent-cv/submissions/submission_dinov2_classify_v1.zip
"""
import argparse
import json
import tempfile
import time
import zipfile
from pathlib import Path

TIMEOUT_SECONDS = 300


def main():
    parser = argparse.ArgumentParser(description="Profile CV submission timing")
    parser.add_argument("zip_path", help="Path to submission ZIP")
    parser.add_argument("--images", default="agent-cv/test_images",
                        help="Test images directory (default: agent-cv/test_images)")
    args = parser.parse_args()

    zip_path = Path(args.zip_path)
    images_dir = Path(args.images)

    if not zip_path.exists():
        print(f"FAIL: ZIP not found: {zip_path}")
        raise SystemExit(1)

    if not images_dir.exists():
        print(f"FAIL: Images dir not found: {images_dir}")
        raise SystemExit(1)

    image_files = sorted(images_dir.glob("*.jpg"))
    if not image_files:
        print(f"FAIL: No .jpg images in {images_dir}")
        raise SystemExit(1)

    print(f"=== CV Profiler: {zip_path.name} ===")
    print(f"Test images: {len(image_files)} in {images_dir}")
    print(f"Timeout: {TIMEOUT_SECONDS}s\n")

    # Extract ZIP
    ALLOWED_EXTS = {".py", ".json", ".yaml", ".yml", ".cfg", ".pt", ".pth", ".onnx", ".safetensors", ".npy"}

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path) as zf:
            # Check for disallowed file types BEFORE profiling
            bad = [n for n in zf.namelist() if Path(n).suffix.lower() and Path(n).suffix.lower() not in ALLOWED_EXTS]
            if bad:
                print(f"FAIL: Disallowed file types: {bad}")
                print(f"Allowed: {', '.join(sorted(ALLOWED_EXTS))}")
                raise SystemExit(1)
            zf.extractall(tmpdir)
        t_extract = time.time() - t0
        print(f"[1] Extract ZIP:       {t_extract:6.2f}s")

        # Check for model files
        tmppath = Path(tmpdir)
        model_files = list(tmppath.glob("*.onnx"))
        print(f"    Models found: {[f.name for f in model_files]}")

        # Try to load models with onnxruntime
        try:
            import onnxruntime as ort

            t1 = time.time()
            sessions = []
            for mf in sorted(tmppath.glob("*.onnx")):
                if mf.suffix == ".data":
                    continue
                sess = ort.InferenceSession(
                    str(mf), providers=["CPUExecutionProvider"])
                sessions.append((mf.name, sess))
            t_load = time.time() - t1
            print(f"[2] Load models:       {t_load:6.2f}s ({len(sessions)} model(s))")

            for name, sess in sessions:
                inputs = sess.get_inputs()
                outputs = sess.get_outputs()
                print(f"    {name}: input={inputs[0].shape}, output shapes={[o.shape for o in outputs]}")

        except ImportError:
            t_load = 0
            print("[2] Load models:       SKIPPED (onnxruntime not available)")
            print("    Install onnxruntime to profile inference timing")

        # Run inference: prefer Docker, fall back to native
        import subprocess

        # Check if Docker is available and ng-sandbox image exists
        docker_available = False
        try:
            check = subprocess.run(
                ["docker", "image", "inspect", "ng-sandbox"],
                capture_output=True, timeout=10)
            docker_available = check.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        t2 = time.time()
        output_json = Path(tmpdir) / "predictions.json"
        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir(exist_ok=True)

        if docker_available:
            print("[3] Inference (Docker): ", end="", flush=True)
            result = subprocess.run(
                ["docker", "run", "--rm",
                 "-v", f"{images_dir.resolve()}:/data/images:ro",
                 "-v", f"{output_dir}:/tmp:rw",
                 "ng-sandbox"],
                capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
            output_json = output_dir / "predictions.json"
        else:
            print("[3] Inference (native): ", end="", flush=True)
            result = subprocess.run(
                ["python3", str(tmppath / "run.py"),
                 "--images", str(images_dir),
                 "--output", str(output_json)],
                capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
                cwd=str(tmppath))

        t_inference = time.time() - t2

        if result.returncode != 0:
            print(f"FAILED (exit {result.returncode})")
            print(f"    stderr: {result.stderr[:500]}")
            if not docker_available:
                print("    TIP: Build Docker image first: docker build -t ng-sandbox agent-cv/")
                print("    Or install deps: pip install opencv-python-headless onnxruntime numpy")
            raise SystemExit(1)

        print(f"{t_inference:6.2f}s")
        if result.stdout.strip():
            print(f"    stdout: {result.stdout.strip()}")

        # Check output
        if output_json.exists():
            preds = json.loads(output_json.read_text())
            print(f"    Predictions: {len(preds)}")
        else:
            print("    WARNING: No predictions.json produced")

        # Summary
        total = t_extract + t_inference
        print(f"\n{'='*50}")
        print(f"Total wall time:       {total:6.2f}s / {TIMEOUT_SECONDS}s")
        print(f"Headroom:              {TIMEOUT_SECONDS - total:6.2f}s")

        # Estimate for N images
        if len(image_files) > 0:
            per_image = t_inference / len(image_files)
            est_100_cpu = per_image * 100
            # L4 GPU is ~20-40x faster than CPU for ONNX inference
            gpu_speedup = 25  # Conservative estimate
            est_100_gpu = est_100_cpu / gpu_speedup

            print(f"\nPer-image (CPU):       {per_image:6.2f}s")
            print(f"CPU est 100 images:    {est_100_cpu:6.1f}s")
            print(f"GPU est 100 images:    {est_100_gpu:6.1f}s (assuming {gpu_speedup}x speedup)")

            if est_100_gpu > TIMEOUT_SECONDS:
                print(f"\nFAIL: Would likely exceed {TIMEOUT_SECONDS}s even on GPU!")
                raise SystemExit(1)
            elif est_100_gpu > TIMEOUT_SECONDS * 0.7:
                print(f"\nWARNING: Tight on GPU. Monitor actual submission timing.")
            elif est_100_cpu > TIMEOUT_SECONDS:
                print(f"\nPASS (GPU): CPU too slow, but L4 GPU should handle it.")
                print(f"    CPU exceeds timeout, but competition runs on CUDA L4.")
            else:
                print(f"\nPASS: Well within timeout on both CPU and GPU.")


if __name__ == "__main__":
    main()
