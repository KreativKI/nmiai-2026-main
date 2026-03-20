---
priority: HIGH — PERMANENT RULE
from: overseer
timestamp: 2026-03-20 04:30 CET
self-destruct: NEVER — save this to your CLAUDE.md permanently
---

## Mandatory QC Loop Before ANY Submission

After the YOLO11m exit code 2 failure, this loop is mandatory for EVERY submission ZIP:

### Step 1: Build ZIP
Create the submission ZIP with run.py at root.

### Step 2: Clean Room Test
```bash
# Unzip into a CLEAN temporary directory
mkdir -p /tmp/cv-test && rm -rf /tmp/cv-test/*
unzip submission.zip -d /tmp/cv-test/
ls -la /tmp/cv-test/  # Verify run.py at root, weights present
```

### Step 3: Docker Validation (OrbStack)
Run with REAL test images and the EXACT competition command:
```bash
docker run --rm --gpus all \
  -v /tmp/cv-test:/app \
  -v /path/to/test_images:/data/images \
  -v /tmp/output:/tmp \
  ng-sandbox \
  python /app/run.py --images /data/images/ --output /tmp/predictions.json
```
Must exit code 0. Must produce valid predictions.json.

### Step 4: Validate Output
```bash
python3 -c "
import json
with open('/tmp/output/predictions.json') as f:
    preds = json.load(f)
print(f'{len(preds)} predictions')
if preds:
    p = preds[0]
    assert 'image_id' in p and 'category_id' in p and 'bbox' in p and 'score' in p
    print(f'Fields OK: image_id={p[\"image_id\"]}, cat={p[\"category_id\"]}, bbox={p[\"bbox\"]}, score={p[\"score\"]}')
print('VALIDATION PASSED')
"
```

### Step 5: Report to Overseer
Write to intelligence/for-overseer/cv-submission-ready.md:
- ZIP filename and size
- Docker exit code
- Number of predictions generated
- Sample prediction
- Overseer and JC review before upload

NEVER upload a ZIP that hasn't passed ALL 5 steps.
