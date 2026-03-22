"""Pre-compute SVC weights + PCA params. Ship as .npy files instead of training at runtime."""
import numpy as np
import json
import time
from pathlib import Path
from sklearn.svm import LinearSVC

gallery = np.load("gallery_output/gallery_rich.npy")
gl = np.array(json.load(open("gallery_output/gallery_rich_labels.json")), dtype=np.int32)

# PCA whiten
mean = gallery.mean(axis=0)
c = gallery - mean
cov = (c.T @ c) / len(c)
ev, evec = np.linalg.eigh(cov)
idx = np.argsort(ev)[::-1][:320]
wm = evec[:, idx].T / np.sqrt(ev[idx][:, None] + 1e-8)
t = c @ wm.T
gallery_pca = t / (np.linalg.norm(t, axis=1, keepdims=True) + 1e-8)

# Train SVC
t0 = time.time()
svc = LinearSVC(C=1.0, max_iter=1000, dual=False, tol=1e-3)
svc.fit(gallery_pca, gl)
print(f"SVC trained in {time.time()-t0:.1f}s")
print(f"coef_ shape: {svc.coef_.shape}")
print(f"intercept_ shape: {svc.intercept_.shape}")
print(f"classes_: {svc.classes_.shape}")

# Save weights
np.save("svc_coef.npy", svc.coef_.astype(np.float32))
np.save("svc_intercept.npy", svc.intercept_.astype(np.float32))
np.save("svc_classes.npy", svc.classes_.astype(np.int32))
np.save("pca_mean_precomputed.npy", mean.astype(np.float32))
np.save("pca_wm_precomputed.npy", wm.astype(np.float32))

for f in ["svc_coef.npy", "svc_intercept.npy", "svc_classes.npy", "pca_mean_precomputed.npy", "pca_wm_precomputed.npy"]:
    p = Path(f)
    print(f"  {f}: {p.stat().st_size / 1024:.1f} KB")
