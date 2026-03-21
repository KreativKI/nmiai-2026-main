#!/usr/bin/env python3
"""
Pre-detect bounding boxes using Grounding DINO.
Runs once before labeling session to generate suggested boxes.

Output: synthetic_shelf/pre_detections.json
Format: {"filename.jpg": {"cx": 0.5, "cy": 0.5, "w": 0.3, "h": 0.4, "confidence": 0.92}}

Requirements (install in venv):
  pip install torch torchvision groundingdino-py Pillow

Usage:
  python3 predetect.py                          # Use product names as prompts
  python3 predetect.py --prompt "product"       # Use generic prompt for all
"""

import argparse
import json
from pathlib import Path

SYNTHETIC = Path(__file__).resolve().parent.parent.parent / "synthetic_shelf"
IMAGES_DIR = SYNTHETIC / "images"
MANIFEST_PATH = SYNTHETIC / "manifest.json"
OUTPUT_PATH = SYNTHETIC / "pre_detections.json"


def run_groundingdino(manifest, prompt_override=None):
    try:
        from groundingdino.util.inference import load_model, load_image, predict
    except ImportError:
        print("ERROR: groundingdino not installed.")
        print("Install with: pip install groundingdino-py")
        print("")
        print("Falling back to center-box defaults.")
        return generate_center_defaults(manifest)

    model = load_model(
        "groundingdino/config/GroundingDINO_SwinT_OGC.py",
        "weights/groundingdino_swint_ogc.pth",
    )

    detections = {}
    total = len(manifest)

    for i, (filename, info) in enumerate(sorted(manifest.items()), 1):
        img_path = IMAGES_DIR / filename
        if not img_path.exists():
            print(f"  [{i}/{total}] SKIP (missing): {filename}")
            continue

        prompt = prompt_override or info["product_name"]
        image_source, image = load_image(str(img_path))

        boxes, logits, phrases = predict(
            model=model,
            image=image,
            caption=prompt,
            box_threshold=0.2,
            text_threshold=0.2,
        )

        if len(boxes) > 0:
            best_idx = logits.argmax().item()
            box = boxes[best_idx]
            cx, cy, w, h = box.tolist()
            conf = logits[best_idx].item()
            detections[filename] = {
                "cx": round(cx, 6),
                "cy": round(cy, 6),
                "w": round(w, 6),
                "h": round(h, 6),
                "confidence": round(conf, 4),
            }
            print(f"  [{i}/{total}] {filename}: bbox=[{cx:.3f},{cy:.3f},{w:.3f},{h:.3f}] conf={conf:.3f}")
        else:
            print(f"  [{i}/{total}] {filename}: no detection, using center default")
            detections[filename] = {"cx": 0.5, "cy": 0.5, "w": 0.5, "h": 0.5, "confidence": 0.0}

    return detections


def generate_center_defaults(manifest):
    detections = {}
    for filename in manifest:
        detections[filename] = {"cx": 0.5, "cy": 0.5, "w": 0.5, "h": 0.5, "confidence": 0.0}
    print(f"Generated {len(detections)} center-box defaults.")
    return detections


def main():
    parser = argparse.ArgumentParser(description="Pre-detect bboxes with Grounding DINO")
    parser.add_argument("--prompt", type=str, default=None, help="Override prompt for all images")
    parser.add_argument("--fallback", action="store_true", help="Skip DINO, just generate center defaults")
    args = parser.parse_args()

    if not MANIFEST_PATH.exists():
        print(f"ERROR: No manifest.json at {MANIFEST_PATH}")
        raise SystemExit(1)

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    print(f"=== Pre-detection: {len(manifest)} images ===")

    if args.fallback:
        detections = generate_center_defaults(manifest)
    else:
        detections = run_groundingdino(manifest, args.prompt)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(detections, f, indent=2)

    detected = sum(1 for d in detections.values() if d["confidence"] > 0)
    print(f"\nSaved to {OUTPUT_PATH}")
    print(f"Detected: {detected}/{len(detections)}, Defaults: {len(detections) - detected}")


if __name__ == "__main__":
    main()
