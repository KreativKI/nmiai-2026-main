# NorgesGruppen Object Detection — Rules

**Source:** Competition docs fetched 2026-03-20 00:00 CET
**Last verified:** 2026-03-20 03:30 CET
**Track weight:** 33.33% of total score
**Change log:** (append here when rules change)
- 2026-03-20 00:00: Initial rules populated from competition docs
- 2026-03-20 00:30: Added UTC rate limit reset time (midnight UTC = 01:00 CET)
- 2026-03-20 00:40: CRITICAL — 30+ teams BANNED for importing blocked modules. Organizers confirmed this is instant ban, not just an error.
- 2026-03-20 01:30: Submissions increased 3 -> 5/day. CLI confirmed: --images (not --input), output to /tmp/. Added blocked imports: urllib, http.client, gc.
- 2026-03-20 03:30: Submissions increased again 5 -> 10/day.

## Submission
- Upload ZIP file containing run.py + model weights
- run.py must be at ZIP root (NOT in a subfolder)
- Max 6 submissions per day (resets midnight UTC = 01:00 CET). Infrastructure errors don't count (up to 2/day).
- Max 420 MB total weight files
- Max 3 weight files
- Max 10 .py files

## Input/Output
- **CLI:** `python run.py --images /data/images/ --output /tmp/predictions.json`
- **Input:** `/data/images/` contains JPEG shelf images (format: img_XXXXX.jpg)
- **Output:** JSON array of predictions written to the path specified by `--output`

### Prediction format
```json
[
  {
    "image_id": 1,
    "category_id": 42,
    "bbox": [x, y, width, height],
    "score": 0.95
  }
]
```
- bbox: [x, y, width, height] in pixels (COCO format)
- category_id: 0-356 (357 product categories)
- score: confidence value

## Scoring
- **70% detection mAP:** Found the products? (IoU >= 0.5, category ignored)
- **30% classification mAP:** Right product? (IoU >= 0.5 AND correct category_id)
- Detection-only submissions can score up to 70%
- Public test set leaderboard; private test set determines final ranking
- Can select which submission gets evaluated on private set

## Sandbox Environment
- **GPU:** NVIDIA L4, 24 GB VRAM (always available)
- **Timeout:** 300 seconds
- **Python:** 3.11
- **NO network access**
- **Cannot pip install at runtime**

### Pre-installed packages
PyTorch 2.6.0+cu124, torchvision 0.21.0+cu124, ultralytics 8.1.0, onnxruntime-gpu 1.20.0, opencv-python-headless 4.9.0.80, numpy 1.26.4, Pillow 10.2.0, pycocotools 2.0.7, timm 0.9.12, safetensors 0.4.2, ensemble-boxes 1.0.9, supervision 0.18.0, albumentations 1.3.1, scipy 1.12.0, scikit-learn 1.4.0

### BLOCKED imports — IMPORTING ANY OF THESE = INSTANT ACCOUNT BAN
os, sys, subprocess, socket, ctypes, builtins, importlib, pickle, marshal, shelve, shutil, yaml, requests, urllib, http.client, multiprocessing, threading, signal, gc, code, codeop, pty

**WARNING (Slack announcement 2026-03-20 00:40 CET):** 30+ teams have already been BANNED for importing `sys` or other blocked modules. The organizers treat blocked imports as a security threat. This is not a soft error: your account gets permanently banned. Double-check EVERY import in run.py and all .py files before submission. Also check transitive imports from libraries.

### BLOCKED function calls
Dynamic code generation functions are blocked. Use pathlib instead of os. Use json instead of yaml.

## Training Data
- NM_NGD_coco_dataset.zip (~864 MB): 248 shelf images, ~22,700 annotations, 356 categories
- NM_NGD_product_images.zip (~60 MB): 327 product reference images with multi-angle photos
- 4 store sections: Egg, Frokost, Knekkebrod, Varmedrikker

## Competition-Wide Rules
- AI tools allowed
- No sharing solutions between teams
- No hardcoded responses
- Repo goes public at Sunday 14:45
- Deadline: Sunday March 22, 15:00 CET
