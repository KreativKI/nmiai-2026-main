---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 15:50 CET
self-destruct: after updating and committing, delete
---

## URGENT: Update validate_cv_zip.py with allowed file extensions

A submission was REJECTED because gallery.npz has a disallowed extension.

### Add this check to validate_cv_zip.py:
```python
ALLOWED_EXTENSIONS = {'.py', '.json', '.yaml', '.yml', '.cfg', '.pt', '.pth', '.onnx', '.safetensors', '.npy'}

for filepath in zip_contents:
    ext = Path(filepath).suffix.lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        print(f"FAIL: disallowed file extension: {filepath} ({ext})")
        print(f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
```

This must NEVER happen again. The validator should have caught this.
