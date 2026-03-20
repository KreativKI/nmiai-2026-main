---
priority: HIGH
from: overseer
timestamp: 2026-03-20 06:10 CET
self-destruct: after incorporating into plan.md, delete
---

## Synthetic Training Data: Two Approaches (Do Both)

### CONFIRMED: Nano Banana (gemini-2.5-flash-image) Works on GCP For Free

```python
from google import genai
from google.genai import types

client = genai.Client(
    vertexai=True,
    project='ai-nm26osl-1779',
    location='global'  # MUST be 'global', not a region
)

response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents='your prompt here',
    config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE']
    )
)

# Save image
for part in response.candidates[0].content.parts:
    if hasattr(part, 'inline_data') and part.inline_data:
        with open('output.png', 'wb') as f:
            f.write(part.inline_data.data)
```

JC will decide on AI-generated images tomorrow. For now, focus on copy-paste augmentation.

---

### Approach A: Copy-Paste Augmentation (DO NOW, free, proven)

Cut product reference images from NM_NGD_product_images.zip and paste onto real shelf backgrounds. Auto-generate COCO annotations since we know exactly where we paste.

**Steps:**
1. Load all 327 product reference images from NM_NGD_product_images.zip
2. Load all 248 real shelf images as backgrounds
3. For each synthetic image:
   a. Pick a random real shelf image as background
   b. Pick 5-15 random product reference images
   c. Remove background from reference images (simple thresholding or edge detection, they're on clean backgrounds)
   d. Random scale (0.3x-1.5x), slight rotation (-5 to +5 degrees)
   e. Paste at random positions on shelf
   f. Blend edges (Gaussian blur on mask boundary for realism)
   g. Apply lighting jitter (brightness, contrast, hue shift via albumentations)
   h. Save image + COCO annotation (bbox = paste location, category_id = product ID)
4. Generate 500-1000 synthetic images
5. Combine with real 248 images for training
6. Retrain YOLO11m on combined dataset

**Expected impact:** +3-7 mAP. Google's Copy-Paste paper (CVPR 2021) showed **+6.9 box AP in low-data regimes** (10% of COCO = ~12K images, we have 248). Our setup is even better: clean product cutouts + real backgrounds.

**Key details:**
- Use `cv2.seamlessClone` (Poisson blending) for realistic edges. Mode: `NORMAL_CLONE` or `MIXED_CLONE`.
- Product reference images likely have clean/white backgrounds. Use simple color thresholding to create masks.
- Vary the number of pasted products per image (5-15) to match real shelf density.
- Some products should overlap slightly (realistic shelf placement).
- Generate **250-500 images** (sweet spot: 1-2x real data). Diminishing returns after 500.
- **Bridged transfer:** Pre-train on synthetic data first, THEN fine-tune on real 248 images. This beats mixing them together.
- Slight color jitter on pasted products to match shelf lighting.

**Bonus: Gemini Annotation QC**
After copy-paste pipeline is built, use Gemini 2.5 Flash vision to QC our 22,700 training annotations:
```python
client = genai.Client(vertexai=True, project='ai-nm26osl-1779', location='global')
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[image_bytes, 'List all grocery products visible with bounding boxes'],
)
```
Compare Gemini detections against COCO annotations. Find missed products or wrong labels. Even fixing 5-10% annotation errors could yield +1-3 mAP.

**Commit: "Synthetic data: copy-paste augmentation pipeline"**

---

### Approach B: Nano Banana Generated Shelves (TOMORROW, JC decides on cost)

Prompt Nano Banana to generate realistic grocery shelf images with specific products:
- "A Norwegian grocery store shelf with eggs, bread, and crackers neatly arranged"
- Use Gemini 2.5 Flash vision to analyze real shelf images first, describe the layout, then generate similar ones
- Requires COCO annotation generation (use Gemini vision to identify product locations in generated images, or use YOLO inference as pseudo-labels)

This is more experimental. Copy-paste is the safe bet. Do copy-paste first.

---

### Implementation Priority
1. Build copy-paste pipeline (2-3 hours)
2. Generate 500 synthetic images
3. Retrain YOLO11m on combined 748 images
4. Docker validate and prepare new ZIP
5. (Tomorrow) JC decides on Nano Banana AI images
