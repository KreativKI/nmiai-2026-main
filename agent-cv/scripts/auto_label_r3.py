"""Auto-label all generated images with a given model."""
import sys
from pathlib import Path
from PIL import Image
from ultralytics import YOLO

model_path = sys.argv[1]
out_dir = Path(sys.argv[2])
gen_dir = Path.home() / "gemini_shelf_gen"

model = YOLO(model_path)
total = 0

for cat_dir in sorted(gen_dir.iterdir()):
    if not cat_dir.is_dir() or not cat_dir.name.startswith("cat_"):
        continue
    cat_id = int(cat_dir.name.split("_")[1])
    for img_path in sorted(cat_dir.glob("*.jpg")):
        total += 1
        img = Image.open(img_path)
        iw, ih = img.size
        results = model(str(img_path), conf=0.15, verbose=False)
        lines = []
        if results and results[0].boxes is not None:
            for box in results[0].boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cx = (x1 + x2) / 2 / iw
                cy = (y1 + y2) / 2 / ih
                bw = (x2 - x1) / iw
                bh = (y2 - y1) / ih
                if cls == cat_id and conf >= 0.15:
                    lines.append(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                elif conf >= 0.3:
                    lines.append(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
        if not any(l.startswith(f"{cat_id} ") for l in lines):
            lines.insert(0, f"{cat_id} 0.500000 0.500000 0.400000 0.400000")
        (out_dir / (img_path.stem + ".txt")).write_text("\n".join(lines) + "\n")
        if total % 100 == 0:
            print(f"  {total} images...")

print(f"Done: {total} auto-labeled")
