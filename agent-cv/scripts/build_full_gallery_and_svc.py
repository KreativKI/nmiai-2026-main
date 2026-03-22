"""Build UNCAPPED gallery from ALL training annotations and train SVC on it."""
import json
import time
import numpy as np
import cv2
import onnxruntime as ort
from pathlib import Path
from sklearn.svm import LinearSVC

DINO_INPUT_SIZE = 518

def preprocess_crop(crop_bgr, size=518):
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    r = cv2.resize(crop_rgb, (size, size), interpolation=cv2.INTER_LINEAR)
    f = r.astype(np.float32) / 255.0
    m = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    s = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    return np.transpose((f - m) / s, (2, 0, 1))[np.newaxis, ...].astype(np.float32)

# Load annotations
coco = json.load(open("trainingdata/train/annotations.json"))
img_dir = Path("trainingdata/train/images/")
img_lookup = {img["id"]: img["file_name"] for img in coco["images"]}

# Load DINOv2
providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
dino = ort.InferenceSession("dinov2_vits.onnx", providers=providers)
din = dino.get_inputs()[0].name

# Embed ALL annotations (no cap)
anns = [a for a in coco["annotations"] if a["bbox"][2] >= 10 and a["bbox"][3] >= 10]
print(f"Embedding {len(anns)} crops (ALL, no cap)...")

img_cache = {}
embeddings = []
labels = []
t0 = time.time()

for i, ann in enumerate(anns):
    img_id = ann["image_id"]
    cat_id = ann["category_id"]
    x, y, w, h = int(ann["bbox"][0]), int(ann["bbox"][1]), int(ann["bbox"][2]), int(ann["bbox"][3])

    if img_id not in img_cache:
        fname = img_lookup.get(img_id)
        if not fname:
            continue
        p = img_dir / fname
        if not p.exists():
            continue
        img_cache[img_id] = cv2.imread(str(p))

    img = img_cache[img_id]
    if img is None:
        continue
    ih, iw = img.shape[:2]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(iw, x + w), min(ih, y + h)
    if x2 - x1 < 10 or y2 - y1 < 10:
        continue

    crop = img[y1:y2, x1:x2]
    inp = preprocess_crop(crop, DINO_INPUT_SIZE)
    emb = dino.run(None, {din: inp})[0].flatten()
    emb = emb / (np.linalg.norm(emb) + 1e-8)
    embeddings.append(emb)
    labels.append(cat_id)

    if (i + 1) % 2000 == 0:
        print(f"  {i+1}/{len(anns)} ({time.time()-t0:.0f}s)")

embeddings = np.array(embeddings, dtype=np.float32)
labels = np.array(labels, dtype=np.int32)
print(f"Full gallery: {embeddings.shape} in {time.time()-t0:.0f}s")

from collections import Counter
c = Counter(labels.tolist())
print(f"Categories: {len(c)}, min={min(c.values())}, max={max(c.values())}, mean={sum(c.values())/len(c):.1f}")

# PCA whiten
print("PCA whitening...")
mean = embeddings.mean(axis=0)
centered = embeddings - mean
cov = (centered.T @ centered) / len(centered)
ev, evec = np.linalg.eigh(cov)
idx = np.argsort(ev)[::-1][:320]
wm = evec[:, idx].T / np.sqrt(ev[idx][:, None] + 1e-8)
gallery_pca = centered @ wm.T
gallery_pca = gallery_pca / (np.linalg.norm(gallery_pca, axis=1, keepdims=True) + 1e-8)

# Train SVC
print("Training LinearSVC on full data...")
t0 = time.time()
svc = LinearSVC(C=1.0, max_iter=1000, dual=False, tol=1e-3)
svc.fit(gallery_pca, labels)
print(f"SVC trained in {time.time()-t0:.1f}s, classes: {len(svc.classes_)}")

# Save as JSON
params = {
    "svc_coef": svc.coef_.astype(np.float32).tolist(),
    "svc_intercept": svc.intercept_.astype(np.float32).tolist(),
    "svc_classes": svc.classes_.astype(np.int32).tolist(),
    "pca_mean": mean.astype(np.float32).tolist(),
    "pca_wm": wm.astype(np.float32).tolist(),
}
with open("classifier_params_full.json", "w") as f:
    json.dump(params, f)

sz = Path("classifier_params_full.json").stat().st_size / 1024 / 1024
print(f"Saved classifier_params_full.json ({sz:.2f} MB)")
