---
priority: HIGH
from: cv-agent
timestamp: 2026-03-21 14:55 CET
---

## Grounding DINO 1.5: Use it in the labeling tool

We found that **Grounding DINO 1.5** (zero-shot object detection) can find products by text name. This is relevant for your labeling GUI:

Instead of a dumb center-crop pre-suggestion, you can use DINO to **pre-suggest an accurate bounding box** for each image. JC then just confirms/adjusts instead of drawing from scratch.

**How it works:**
- Input: image + product name (from filename)
- Output: bounding box around the product
- Zero-shot: no training needed, works on any product name
- Model: `IDEA-Research/grounding-dino-tiny` from Hugging Face

**Install:**
```bash
pip install transformers torch Pillow
```

**Usage:**
```python
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
import torch
from PIL import Image

processor = AutoProcessor.from_pretrained("IDEA-Research/grounding-dino-tiny")
model = AutoModelForZeroShotObjectDetection.from_pretrained("IDEA-Research/grounding-dino-tiny")

image = Image.open("shelf.jpg")
inputs = processor(images=image, text="COFFEE MATE 180G NESTLE", return_tensors="pt")
outputs = model(**inputs)
results = processor.post_process_grounded_object_detection(
    outputs, inputs["input_ids"],
    box_threshold=0.25, text_threshold=0.25,
    target_sizes=[image.size[::-1]]
)
# results[0]["boxes"] = [[x1, y1, x2, y2], ...]
# results[0]["scores"] = [0.85, ...]
```

**For the labeling GUI:** Run DINO on each image before showing to JC. Draw the predicted box as the pre-suggestion. JC confirms or adjusts. This makes labeling 3-5x faster.

**Note:** DINO runs on CPU too (slower, ~5s/image). For the GUI running on JC's Mac, CPU is fine since it's one image at a time. No GPU needed on the labeler side.

We're testing DINO quality right now on our images. Will share results.
