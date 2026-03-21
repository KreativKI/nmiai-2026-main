---
priority: URGENT
from: cv-agent + JC
timestamp: 2026-03-21 19:00 CET
---

## Gemini 2.5 Flash for Auto Bounding Box Detection

### What we need
Use Gemini 2.5 Flash to automatically detect where a KNOWN product is in a shelf image and return bounding box coordinates. This replaces manual labeling for most images.

### Why it should work
- Gemini understands Norwegian product names (Grounding DINO failed because it doesn't)
- We KNOW which product is in each image (from the filename: `cat_026_shelf_v00.jpg` = category 26)
- We have reference product photos we can show Gemini alongside the shelf image
- Gemini just needs to say "the product is at these coordinates"

### The prompt

```
You are a product detection system. You will be shown a grocery store shelf image and reference photos of a specific product.

Your task: Find the product "{PRODUCT_NAME}" in the shelf image and return its bounding box coordinates.

Rules:
- Return ONLY a JSON object, no other text
- The bounding box should tightly enclose the target product
- Coordinates are in pixels relative to the image dimensions
- Format: {"bbox": [x_min, y_min, x_max, y_max], "confidence": 0.0-1.0}
- If the product is not visible or you are unsure, return: {"bbox": null, "confidence": 0.0}
- If multiple instances exist, return the most prominent/front-facing one
- Do NOT include surrounding products in the box

Example response:
{"bbox": [287, 277, 737, 762], "confidence": 0.92}
```

### Integration into the labeling tool

**Flow:**
1. For each image, send to Gemini 2.5 Flash:
   - The shelf image
   - 1-2 reference product photos (front.jpg, main.jpg from the product image folder)
   - The prompt above with {PRODUCT_NAME} filled in
2. Parse the JSON response
3. If confidence > 0.5: draw the predicted box as a pre-suggestion in the GUI
4. JC confirms (Enter), adjusts (drag), or rejects (Skip)
5. If confidence <= 0.5 or bbox is null: JC draws manually

**API call pattern:**
```python
import google.generativeai as genai

model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20")

# Load images
shelf_image = PIL.Image.open("cat_026_shelf_v00.jpg")
ref_front = PIL.Image.open("trainingdata/NM_NGD_product_images/{EAN}/front.jpg")

prompt = f'''You are a product detection system. You will be shown a grocery store shelf image and a reference photo of a specific product.

Your task: Find the product "{product_name}" in the shelf image and return its bounding box coordinates.

Rules:
- Return ONLY a JSON object, no other text
- The bounding box should tightly enclose the target product
- Coordinates are in pixels relative to the image dimensions
- Format: {{"bbox": [x_min, y_min, x_max, y_max], "confidence": 0.0-1.0}}
- If the product is not visible or you are unsure, return: {{"bbox": null, "confidence": 0.0}}
- If multiple instances exist, return the most prominent/front-facing one
- Do NOT include surrounding products in the box'''

response = model.generate_content([ref_front, shelf_image, prompt])
# Parse JSON from response.text
```

**Converting to YOLO format (after getting pixel coords):**
```python
img_w, img_h = shelf_image.size
x_min, y_min, x_max, y_max = bbox
cx = ((x_min + x_max) / 2) / img_w
cy = ((y_min + y_max) / 2) / img_h
w = (x_max - x_min) / img_w
h = (y_max - y_min) / img_h
yolo_label = f"{category_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"
```

### API access
- Model: `gemini-2.5-flash-preview-05-20`
- Can use Vertex AI (project ai-nm26osl-1779, ADC authenticated) or Google AI Studio API key
- Rate limit: generous for 2.5 Flash
- Cost: minimal (text+image input, tiny text output)

### What Butler should build
Integrate this into the labeling GUI as "Auto-detect" mode:
- Toggle: "Use Gemini auto-detect" (on by default)
- When on: before showing each image, call Gemini to get bbox prediction
- Show the predicted box as a GREEN dashed rectangle
- JC can: confirm (Enter), adjust (drag corners), or reject and draw manually
- Show confidence score next to the box
- If Gemini returns null/low confidence: skip auto-detect, JC draws manually

### Fallback
If Gemini API is slow or fails: fall back to center-crop pre-suggestion (40% of image, centered). The GUI should work without Gemini too.

### Product name + EAN lookup
```
manifest.json in each batch folder has:
{
  "cat_026_shelf_v00.jpg": {
    "category_id": 26,
    "product_name": "OB PROCOMFORT NORMAL 16ST"
  }
}

Reference images at:
trainingdata/NM_NGD_product_images/{EAN}/front.jpg

EAN lookup: trainingdata/NM_NGD_product_images/metadata.json
  -> products[] -> match by product_name -> product_code = EAN
```
