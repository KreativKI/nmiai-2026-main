---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 15:50 CET
self-destruct: after fixing and committing, delete
---

## ZIP REJECTED: .npz is a disallowed file extension

### The Problem
`gallery.npz` was rejected. The allowed file extensions are:
`.py, .json, .yaml, .yml, .cfg, .pt, .pth, .onnx, .safetensors, .npy`

`.npz` is NOT on this list. `.npy` IS.

### The Fix
Convert gallery.npz to gallery.npy:
```python
import numpy as np
data = np.load('gallery.npz')
# Save embeddings and labels as separate .npy files
np.save('gallery_embeddings.npy', data['embeddings'])
np.save('gallery_labels.npy', data['labels'])
```

Then update run.py to load .npy instead of .npz:
```python
gallery = np.load(str(model_dir / "gallery_embeddings.npy"))
gallery_labels = np.load(str(model_dir / "gallery_labels.npy"))
```

BUT: this uses 2 .npy files + best.onnx + dinov2_vits.onnx = 4 files.
Weight file limit is 3. So combine embeddings and labels into ONE .npy file:
```python
# Build time: save as structured array or stack with labels as first row
combined = np.vstack([gallery_labels.reshape(1, -1).astype(np.float32), embeddings_padded])
# Or: save labels as .json (allowed) and embeddings as .npy
```

Simplest fix: save labels as gallery_labels.json and embeddings as gallery.npy.
Then weight files = best.onnx + dinov2_vits.onnx + gallery.npy = 3 (at limit).

### Also From Updated Docs

**CLI flag is `--input`, NOT `--images`:**
```
python run.py --input /data/images --output /output/predictions.json
```
Your run.py accepts both (--images/--input alias), which is fine.

**CV submission limit is 5/day** (not 10). We have 1 left today.

**Output format has TWO valid formats** (check which one competition expects):
Format A (our current): `[{"image_id": 1, "category_id": 42, "bbox": [...], "score": 0.95}]`
Format B (from docs): `[{"image_name": "img_00001.jpg", "predictions": [{"bbox": [...], "category_id": 0, "score": 0.95}]}]`

The docs show BOTH formats on different pages. Our current format (A) worked for the 0.5756 submission, so it's correct.

### Allowed Extensions (HARDCODE THIS)
```
ALLOWED_EXTENSIONS = {'.py', '.json', '.yaml', '.yml', '.cfg', '.pt', '.pth', '.onnx', '.safetensors', '.npy'}
```

### Update validate_cv_zip.py
The validator must check file extensions against the allowed list. Add this check.

### COMMIT AFTER FIXING. We have 1 submission left today.
