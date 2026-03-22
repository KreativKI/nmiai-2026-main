import json, random, numpy as np, cv2, onnxruntime as ort, time
from pathlib import Path

DINO_INPUT_SIZE = 518

def preprocess_crop(crop_bgr, size=518):
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    r = cv2.resize(crop_rgb, (size, size), interpolation=cv2.INTER_LINEAR)
    f = r.astype(np.float32) / 255.0
    m = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    s = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    return np.transpose((f - m) / s, (2, 0, 1))[np.newaxis, ...].astype(np.float32)

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

def knn_classify(q, gallery, labels, k=10):
    sims = q @ gallery.T
    top = np.argsort(sims)[-k:]
    votes = {}
    for l, s in zip(labels[top], sims[top]):
        w = max(0.0, float(s)) ** 2
        votes[int(l)] = votes.get(int(l), 0.0) + w
    return max(votes, key=votes.get)

gallery = np.load("gallery_output/gallery_rich.npy")
gl = np.array(json.load(open("gallery_output/gallery_rich_labels.json")), dtype=np.int32)
gallery_pca, pca_mean, pca_matrix = pca_whiten_fit(gallery, 320)

from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression

t0 = time.time()
svc = LinearSVC(C=1.0, max_iter=3000, dual=False)
svc.fit(gallery_pca, gl)
print(f"SVC trained: {time.time()-t0:.1f}s", flush=True)

t0 = time.time()
lr = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
lr.fit(gallery_pca, gl)
print(f"LR trained: {time.time()-t0:.1f}s", flush=True)

coco = json.load(open("trainingdata/train/annotations.json"))
img_dir = Path("trainingdata/train/images/")
img_lookup = {img["id"]: img["file_name"] for img in coco["images"]}
dino = ort.InferenceSession("dinov2_vits.onnx", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
din = dino.get_inputs()[0].name
anns = [a for a in coco["annotations"] if a["bbox"][2] >= 10 and a["bbox"][3] >= 10]
random.seed(42)
anns = random.sample(anns, 2000)
img_cache = {}
ck = cs = cl = total = 0
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
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(iw, x + w), min(ih, y + h)
    if x2 - x1 < 10 or y2 - y1 < 10:
        continue
    crop = img[y1:y2, x1:x2]
    emb = dino.run(None, {din: preprocess_crop(crop)})[0].flatten()
    emb = emb / (np.linalg.norm(emb) + 1e-8)
    ep = pca_transform(emb.reshape(1, -1), pca_mean, pca_matrix)
    if knn_classify(ep[0], gallery_pca, gl, 10) == gt:
        ck += 1
    if svc.predict(ep)[0] == gt:
        cs += 1
    if lr.predict(ep)[0] == gt:
        cl += 1
    total += 1
    if (i + 1) % 500 == 0:
        print(f"  {i+1}: knn={ck/total:.4f} svc={cs/total:.4f} lr={cl/total:.4f}", flush=True)

print(f"\n=== CLASSIFIER COMPARISON ===", flush=True)
print(f"kNN k=10 PCA-320 dist2:  {ck}/{total} = {ck/total:.4f}", flush=True)
print(f"LinearSVC:               {cs}/{total} = {cs/total:.4f}", flush=True)
print(f"LogisticRegression:      {cl}/{total} = {cl/total:.4f}", flush=True)
