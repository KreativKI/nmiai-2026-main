#!/usr/bin/env python3
"""
NM i AI 2026 — CV Submission Profiler (shared/tools/cv_profiler.py)

Profiles a CV submission ZIP to predict if it will stay under the 300s
competition timeout on an L4 GPU. Critical for last-submission decisions.

Measures per-image timing breakdown (YOLO, NMS, crop, DINOv2, kNN),
counts detections per image, and extrapolates to full test set.

Usage:
    # Profile against training images (default: 10 images)
    python3 shared/tools/cv_profiler.py submission.zip

    # Profile with specific sample size
    python3 shared/tools/cv_profiler.py submission.zip --sample 25

    # Profile against specific images directory
    python3 shared/tools/cv_profiler.py submission.zip --images-dir /path/to/images

    # Specify expected test set size for extrapolation
    python3 shared/tools/cv_profiler.py submission.zip --test-set-size 500

    # JSON output
    python3 shared/tools/cv_profiler.py submission.zip --json

Dependencies: onnxruntime, opencv-python, numpy (all in competition sandbox)
"""

import argparse
import json
import re
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    import cv2
    import numpy as np
    import onnxruntime as ort
except ImportError:
    print("ERROR: Requires onnxruntime, opencv-python, numpy")
    print("  pip install onnxruntime opencv-python-headless numpy")
    raise SystemExit(1)


# Competition constraints
TIMEOUT_SECONDS = 300
SAFETY_MARGIN = 0.80  # Recommend GO only if estimated time < 80% of timeout

# L4 GPU vs CPU speedup estimates for ONNX inference
# Based on published ONNX benchmarks: L4 is ~5-8x faster than M-series CPU for vision models
# Using conservative 5x to avoid false GO verdicts
L4_SPEEDUP_FACTOR = 5.0


def extract_image_id(filename: str) -> int:
    m = re.search(r"img_(\d+)", Path(filename).stem)
    return int(m.group(1)) if m else hash(filename) % (10**6)


def profile_submission(zip_path: Path, images_dir: Path, sample_size: int,
                       test_set_size: int) -> dict:
    """Profile a submission ZIP and return timing data."""
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "zip": str(zip_path),
        "sample_size": sample_size,
        "test_set_size": test_set_size,
        "timings": {},
        "per_image": [],
        "models": {},
        "verdict": "",
    }

    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Extract ZIP
        t0 = time.perf_counter()
        with zipfile.ZipFile(str(zip_path), "r") as zf:
            zf.extractall(tmpdir)
        result["timings"]["zip_extract"] = round(time.perf_counter() - t0, 3)

        # Discover models
        onnx_files = sorted(tmpdir.glob("*.onnx"))
        npz_files = sorted(tmpdir.glob("*.npz"))
        result["models"]["onnx_count"] = len(onnx_files)
        result["models"]["onnx_files"] = [
            {"name": f.name, "size_mb": round(f.stat().st_size / (1024*1024), 1)}
            for f in onnx_files
        ]
        result["models"]["npz_files"] = [f.name for f in npz_files]

        # Load ONNX sessions
        providers = ["CPUExecutionProvider"]
        sessions = {}
        load_times = {}
        for f in onnx_files:
            t0 = time.perf_counter()
            sess = ort.InferenceSession(str(f), providers=providers)
            load_times[f.name] = round(time.perf_counter() - t0, 3)
            inp = sess.get_inputs()[0]
            sessions[f.name] = {
                "session": sess,
                "input_name": inp.name,
                "input_shape": inp.shape,
            }
        result["timings"]["model_load"] = load_times

        # Identify YOLO vs classifier by input shape
        yolo_name = None
        dino_name = None
        for name, info in sessions.items():
            shape = info["input_shape"]
            # YOLO typically has larger input (1280) vs DINOv2 (518)
            if isinstance(shape[-1], int) and shape[-1] >= 1000:
                yolo_name = name
            else:
                dino_name = name

        if not yolo_name and not dino_name:
            # Fallback: larger file is YOLO (detection model)
            sorted_by_size = sorted(onnx_files, key=lambda f: f.stat().st_size, reverse=True)
            if len(sorted_by_size) >= 2:
                yolo_name = sorted_by_size[0].name
                dino_name = sorted_by_size[1].name
            elif len(sorted_by_size) == 1:
                yolo_name = sorted_by_size[0].name

        result["models"]["yolo"] = yolo_name
        result["models"]["classifier"] = dino_name

        # Load gallery if present
        gallery = None
        gallery_labels = None
        if npz_files:
            gallery_data = np.load(str(npz_files[0]))
            if "embeddings" in gallery_data:
                gallery = gallery_data["embeddings"]
                gallery_labels = gallery_data.get("labels")
                result["models"]["gallery_size"] = gallery.shape[0] if gallery is not None else 0

        # Select sample images
        all_images = sorted([
            p for p in images_dir.iterdir()
            if p.suffix.lower() in (".jpg", ".jpeg", ".png")
        ])
        sample_images = all_images[:sample_size]
        result["sample_size"] = len(sample_images)

        # Profile each image
        total_detections = 0
        total_crops = 0

        for img_path in sample_images:
            img_result = {
                "file": img_path.name,
                "image_id": extract_image_id(img_path.name),
                "detections": 0,
                "timings": {},
            }

            # Read image
            t0 = time.perf_counter()
            img = cv2.imread(str(img_path))
            img_result["timings"]["read"] = round(time.perf_counter() - t0, 4)

            if img is None:
                img_result["error"] = "Failed to read"
                result["per_image"].append(img_result)
                continue

            orig_h, orig_w = img.shape[:2]
            img_result["resolution"] = f"{orig_w}x{orig_h}"

            # Stage 1: YOLO preprocessing + inference
            if yolo_name:
                yolo_info = sessions[yolo_name]
                yolo_shape = yolo_info["input_shape"]
                # Determine input size from model shape
                input_size = yolo_shape[-1] if isinstance(yolo_shape[-1], int) else 1280

                t0 = time.perf_counter()
                # Letterbox
                h, w = img.shape[:2]
                scale = min(input_size / h, input_size / w)
                new_h, new_w = int(h * scale), int(w * scale)
                resized = cv2.resize(img, (new_w, new_h))
                padded = np.full((input_size, input_size, 3), 114, dtype=np.uint8)
                top = (input_size - new_h) // 2
                left = (input_size - new_w) // 2
                padded[top:top+new_h, left:left+new_w] = resized
                img_rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
                img_norm = img_rgb.astype(np.float32) / 255.0
                img_batch = np.transpose(img_norm, (2, 0, 1))[np.newaxis, ...]
                img_result["timings"]["yolo_preprocess"] = round(time.perf_counter() - t0, 4)

                t0 = time.perf_counter()
                yolo_out = yolo_info["session"].run(
                    None, {yolo_info["input_name"]: img_batch}
                )
                img_result["timings"]["yolo_inference"] = round(time.perf_counter() - t0, 4)

                # Decode + NMS (approximate timing)
                t0 = time.perf_counter()
                preds = yolo_out[0][0].T if len(yolo_out[0].shape) == 3 else yolo_out[0].T
                if preds.shape[1] > 4:
                    scores = preds[:, 4:]
                    confidences = np.max(scores, axis=1)
                    mask = confidences >= 0.05
                    num_detections = int(np.sum(mask))
                else:
                    num_detections = 0
                img_result["timings"]["yolo_decode_nms"] = round(time.perf_counter() - t0, 4)
                img_result["detections"] = num_detections
                total_detections += num_detections

            # Stage 2: DINOv2 classification (if classifier present)
            if dino_name and num_detections > 0:
                dino_info = sessions[dino_name]
                dino_shape = dino_info["input_shape"]
                dino_size = dino_shape[-1] if isinstance(dino_shape[-1], int) else 518

                # Time a representative crop (first detection)
                t0 = time.perf_counter()
                # Create a dummy crop of realistic size
                crop_h = max(50, orig_h // 10)
                crop_w = max(50, orig_w // 10)
                crop = img[:crop_h, :crop_w]
                crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                crop_resized = cv2.resize(crop_rgb, (dino_size, dino_size))
                crop_float = crop_resized.astype(np.float32) / 255.0
                mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
                std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
                crop_norm = (crop_float - mean) / std
                crop_batch = np.transpose(crop_norm, (2, 0, 1))[np.newaxis, ...].astype(np.float32)
                img_result["timings"]["dino_preprocess_one"] = round(time.perf_counter() - t0, 4)

                t0 = time.perf_counter()
                emb = dino_info["session"].run(
                    None, {dino_info["input_name"]: crop_batch}
                )[0].flatten()
                single_dino_time = time.perf_counter() - t0
                img_result["timings"]["dino_inference_one"] = round(single_dino_time, 4)

                # Extrapolate for all detections
                img_result["timings"]["dino_estimated_total"] = round(
                    single_dino_time * num_detections, 4
                )
                total_crops += num_detections

                # Gallery kNN time
                if gallery is not None:
                    t0 = time.perf_counter()
                    emb_norm = emb / (np.linalg.norm(emb) + 1e-8)
                    sims = emb_norm @ gallery.T
                    _ = np.argmax(sims)
                    img_result["timings"]["knn_one"] = round(time.perf_counter() - t0, 4)

            result["per_image"].append(img_result)

    # Aggregate statistics
    n = len(result["per_image"])
    if n == 0:
        result["verdict"] = "NO_DATA"
        return result

    # Per-image timing aggregation
    avg_timings = {}
    for key in ["read", "yolo_preprocess", "yolo_inference", "yolo_decode_nms",
                "dino_preprocess_one", "dino_inference_one", "dino_estimated_total", "knn_one"]:
        vals = [img["timings"].get(key, 0) for img in result["per_image"]]
        if any(v > 0 for v in vals):
            avg_timings[key] = {
                "mean": round(sum(vals) / n, 4),
                "max": round(max(vals), 4),
                "min": round(min(v for v in vals if v > 0) if any(v > 0 for v in vals) else 0, 4),
            }
    result["timings"]["per_image_avg"] = avg_timings

    avg_detections = total_detections / n
    result["timings"]["avg_detections_per_image"] = round(avg_detections, 1)

    # Per-image total time (sum of all stages)
    per_image_totals = []
    for img in result["per_image"]:
        total = sum(img["timings"].get(k, 0) for k in [
            "read", "yolo_preprocess", "yolo_inference", "yolo_decode_nms",
            "dino_estimated_total", "knn_one"
        ])
        per_image_totals.append(total)

    cpu_per_image = sum(per_image_totals) / n
    cpu_total_estimated = cpu_per_image * test_set_size

    # GPU estimate: ONNX inference is ~5x faster on L4, but I/O stays same
    # Split into compute (YOLO + DINOv2 inference) vs overhead (read, preprocess, NMS, kNN)
    compute_keys = ["yolo_inference", "dino_estimated_total"]
    overhead_keys = ["read", "yolo_preprocess", "yolo_decode_nms", "dino_preprocess_one", "knn_one"]

    avg_compute = sum(
        sum(img["timings"].get(k, 0) for k in compute_keys)
        for img in result["per_image"]
    ) / n
    avg_overhead = sum(
        sum(img["timings"].get(k, 0) for k in overhead_keys)
        for img in result["per_image"]
    ) / n

    gpu_per_image = (avg_compute / L4_SPEEDUP_FACTOR) + avg_overhead
    gpu_total_estimated = gpu_per_image * test_set_size

    # Add model load time (one-time cost, same on GPU)
    model_load_total = sum(result["timings"]["model_load"].values())
    gpu_total_with_load = gpu_total_estimated + model_load_total

    result["timings"]["cpu_per_image"] = round(cpu_per_image, 4)
    result["timings"]["cpu_total_estimated"] = round(cpu_total_estimated, 1)
    result["timings"]["gpu_per_image_estimated"] = round(gpu_per_image, 4)
    result["timings"]["gpu_total_estimated"] = round(gpu_total_estimated, 1)
    result["timings"]["gpu_total_with_model_load"] = round(gpu_total_with_load, 1)
    result["timings"]["model_load_total"] = round(model_load_total, 1)
    result["timings"]["l4_speedup_factor"] = L4_SPEEDUP_FACTOR
    result["timings"]["timeout"] = TIMEOUT_SECONDS

    # Verdict
    if gpu_total_with_load <= TIMEOUT_SECONDS * SAFETY_MARGIN:
        result["verdict"] = "GO"
    elif gpu_total_with_load <= TIMEOUT_SECONDS:
        result["verdict"] = "RISKY"
    else:
        result["verdict"] = "NO-GO"

    result["timings"]["margin_used"] = round(
        gpu_total_with_load / TIMEOUT_SECONDS * 100, 1
    )

    return result


def find_repo_root() -> Path:
    cwd = Path.cwd()
    for p in [cwd] + list(cwd.parents):
        if (p / "CLAUDE.md").exists() or (p / "shared").exists():
            return p
    return cwd


def main():
    parser = argparse.ArgumentParser(
        description="CV Submission Profiler: predict if submission stays under 300s timeout"
    )
    parser.add_argument("zip_path", help="Path to submission ZIP")
    parser.add_argument("--sample", type=int, default=10,
                        help="Number of images to profile (default: 10)")
    parser.add_argument("--images-dir", help="Path to test images")
    parser.add_argument("--test-set-size", type=int, default=248,
                        help="Expected test set size for extrapolation (default: 248)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    zip_path = Path(args.zip_path)
    if not zip_path.exists():
        print(f"ERROR: ZIP not found: {zip_path}")
        raise SystemExit(1)

    repo_root = find_repo_root()
    if args.images_dir:
        images_dir = Path(args.images_dir)
    else:
        images_dir = repo_root / "agent-cv/data/yolo_dataset/images/train"

    if not images_dir.exists():
        print(f"ERROR: Images directory not found: {images_dir}")
        raise SystemExit(1)

    print(f"Profiling: {zip_path.name}")
    print(f"Sample: {args.sample} images from {images_dir}")
    print(f"Extrapolating to: {args.test_set_size} images")
    print(f"Timeout: {TIMEOUT_SECONDS}s (L4 GPU)\n")

    result = profile_submission(zip_path, images_dir, args.sample, args.test_set_size)

    if args.json:
        # Remove session objects before JSON serialization
        print(json.dumps(result, indent=2, default=str))
    else:
        t = result["timings"]
        print(f"{'='*60}")
        print(f"  CV Submission Profiler Results")
        print(f"{'='*60}")

        # Models
        print(f"\n  Models:")
        for m in result["models"].get("onnx_files", []):
            role = ""
            if m["name"] == result["models"].get("yolo"):
                role = " (YOLO detector)"
            elif m["name"] == result["models"].get("classifier"):
                role = " (DINOv2 classifier)"
            print(f"    {m['name']}: {m['size_mb']} MB{role}")
        if result["models"].get("gallery_size"):
            print(f"    Gallery: {result['models']['gallery_size']} embeddings")

        # Model load
        print(f"\n  Model load time:")
        for name, secs in t.get("model_load", {}).items():
            print(f"    {name}: {secs:.1f}s")
        print(f"    Total: {t.get('model_load_total', 0):.1f}s")

        # Per-image breakdown
        print(f"\n  Per-image timing (CPU, {result['sample_size']} images):")
        for key, stats in t.get("per_image_avg", {}).items():
            label = key.replace("_", " ").title()
            print(f"    {label:30s} avg={stats['mean']:.4f}s  max={stats['max']:.4f}s")

        print(f"\n  Detections per image: {t.get('avg_detections_per_image', 0):.0f} avg")

        # Totals
        print(f"\n  Extrapolation to {args.test_set_size} images:")
        print(f"    CPU total:     {t.get('cpu_total_estimated', 0):>7.1f}s")
        print(f"    L4 GPU est:    {t.get('gpu_total_estimated', 0):>7.1f}s  (compute /{L4_SPEEDUP_FACTOR:.0f}x, overhead same)")
        print(f"    + model load:  {t.get('gpu_total_with_model_load', 0):>7.1f}s")
        print(f"    Timeout:       {TIMEOUT_SECONDS:>7.1f}s")
        print(f"    Budget used:   {t.get('margin_used', 0):>6.1f}%")

        # Verdict
        v = result["verdict"]
        print(f"\n  Verdict: {v}")
        if v == "GO":
            print(f"  Estimated time is under {SAFETY_MARGIN*100:.0f}% of timeout. Safe to submit.")
        elif v == "RISKY":
            print(f"  Estimated time is between {SAFETY_MARGIN*100:.0f}%-100% of timeout. Tight.")
        else:
            print(f"  Estimated time EXCEEDS {TIMEOUT_SECONDS}s timeout. Do NOT submit.")

        print(f"\n  Note: L4 speedup factor {L4_SPEEDUP_FACTOR}x is conservative.")
        print(f"  Actual L4 may be faster. Profile on GCP VM for exact numbers.")
        print(f"{'='*60}\n")

    raise SystemExit(0 if result["verdict"] != "NO-GO" else 1)


if __name__ == "__main__":
    main()
