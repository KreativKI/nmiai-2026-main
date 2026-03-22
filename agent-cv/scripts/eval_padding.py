"""Quick A/B test: kNN with vs without 10% crop padding."""
import json, random, numpy as np, cv2, onnxruntime as ort
from pathlib import Path
from collections import defaultdict

DINO_INPUT_SIZE = 518

def preprocess_crop(crop_bgr, size=518):
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    crop_resized = cv2.resize(crop_rgb, (size, size), interpolation=cv2.INTER_LINEAR)
    crop_float = crop_resized.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    return np.transpose((crop_float - mean) / std, (2, 0, 1))[np.newaxis, ...].astype(np.float32)

def pca_whiten_fit(embs, n):
    mean = embs.mean(axis=0)
    c = embs - mean
    cov = (c.T @ c) / len(c)
    ev, evec = np.linalg.eigh(cov)
    idx = np.argsort(ev)[::-1][:n]
    wm = evec[:, idx].T / np.sqrt(ev[idx][:, None] + 1e-8)
    t = c @ wm.T
    return t / (np.linalg.norm(t, axis=1, keepdims=True) + 1e-8), mean, wm

def pca_transform(embs, mean, wm):
    t = (embs - mean) @ wm.T
    return t / (np.linalg.norm(t, axis=1, keepdims=True) + 1e-8)

def knn(q, gallery, labels, k=10):
    sims = q @ gallery.T
    top = np.argsort(sims)[-k:]
    votes = {}
    for l, s in zip(labels[top], sims[top]):
        w = max(0.0, float(s)) ** 2
        votes[int(l)] = votes.get(int(l), 0.0) + w
    return max(votes, key=votes.get)

coco = json.load(open("trainingdata/train/annotations.json"))
img_dir = Path("trainingdata/train/images/")
img_lookup = {i["id"]: i["file_name"] for i in coco["images"]}
gallery = np.load("gallery_output/gallery_rich.npy")
gallery_labels = np.array(json.load(open("gallery_output/gallery_rich_labels.json")), dtype=np.int32)
gallery_pca, pca_mean, pca_matrix = pca_whiten_fit(gallery, 320)

dino = ort.InferenceSession("dinov2_vits.onnx", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
din = dino.get_inputs()[0].name

anns = [a for a in coco["annotations"] if a["bbox"][2] >= 10 and a["bbox"][3] >= 10]
random.seed(42)
anns = random.sample(anns, 2000)
img_cache = {}
correct_nopad = 0
correct_pad = 0
total = 0

for i, ann in enumerate(anns):
    img_id = ann["image_id"]
    gt = ann["category_id"]
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

    # No padding
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(iw, x + w), min(ih, y + h)
    if x2 - x1 < 10 or y2 - y1 < 10:
        continue
    crop = img[y1:y2, x1:x2]
    emb = dino.run(None, {din: preprocess_crop(crop)})[0].flatten()
    emb = emb / (np.linalg.norm(emb) + 1e-8)
    emb_pca = pca_transform(emb.reshape(1, -1), pca_mean, pca_matrix)[0]
    if knn(emb_pca, gallery_pca, gallery_labels, 10) == gt:
        correct_nopad += 1

    # With 10% padding
    px, py = int(w * 0.1), int(h * 0.1)
    x1p, y1p = max(0, x - px), max(0, y - py)
    x2p, y2p = min(iw, x + w + px), min(ih, y + h + py)
    crop_pad = img[y1p:y2p, x1p:x2p]
    emb_p = dino.run(None, {din: preprocess_crop(crop_pad)})[0].flatten()
    emb_p = emb_p / (np.linalg.norm(emb_p) + 1e-8)
    emb_pca_p = pca_transform(emb_p.reshape(1, -1), pca_mean, pca_matrix)[0]
    if knn(emb_pca_p, gallery_pca, gallery_labels, 10) == gt:
        correct_pad += 1

    total += 1
    if (i + 1) % 500 == 0:
        print(f"  {i+1}: nopad={correct_nopad/total:.4f} pad={correct_pad/total:.4f}")

print(f"\n=== PADDING A/B TEST ===")
print(f"kNN PCA-320 k=10 dist2 NO padding:   {correct_nopad}/{total} = {correct_nopad/total:.4f}")
print(f"kNN PCA-320 k=10 dist2 WITH 10% pad: {correct_pad}/{total} = {correct_pad/total:.4f}")
