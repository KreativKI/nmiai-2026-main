---
priority: HIGH
from: cv-agent (via JC)
timestamp: 2026-03-21 08:15 CET
---

# Assignment: Build Image Labeling GUI for CV Track

## What We Need
A web-based tool where JC can manually draw bounding boxes on AI-generated grocery shelf images. One product per image, category already known. JC draws the box, tool saves in YOLO format.

## Context
We're generating ~2000 product images using Gemini (products on realistic grocery shelves). Each image features ONE known product. We need bounding box labels for YOLO training. JC will be the human labeler.

## Requirements

### Core
- Web UI (Streamlit, Flask, or plain HTML+JS). Must run locally on JC's Mac.
- Show one image at a time, full screen
- Display the product name and category_id at the top (read from filename or manifest)
- JC clicks and drags to draw a bounding box rectangle on the image
- Save label in YOLO format: `{category_id} {center_x} {center_y} {width} {height}` (normalized 0-1)
- Next/Previous navigation (arrow keys or buttons)
- Auto-save on Next (no separate save button)
- Skip button for bad/unusable images
- Progress counter: "47 / 2150 labeled"

### Nice to Have
- Pre-suggest a bounding box (center 60% of image) that JC can adjust
- Keyboard shortcuts: Enter=confirm+next, S=skip, Z=undo
- Show a small reference photo of the product in the corner (so JC knows what to look for)
- Resume from where you left off (track progress in a JSON file)

### File Structure
Input:
```
agent-cv/synthetic_shelf/
  images/
    cat_043_MEIERISMOR_500G_v01.jpg
    cat_043_MEIERISMOR_500G_v02.jpg
    ...
  manifest.json   # {filename: {category_id: 43, product_name: "MEIERISMOR 500G TINE"}}
```

Output:
```
agent-cv/synthetic_shelf/
  labels/
    cat_043_MEIERISMOR_500G_v01.txt   # YOLO format: "43 0.5 0.5 0.6 0.7"
    cat_043_MEIERISMOR_500G_v02.txt
  progress.json   # tracks which images are labeled/skipped
```

### Constraints
- Must work on macOS (JC's machine)
- No heavy dependencies. Prefer: plain HTML+JS (zero install) or Streamlit (pip install streamlit)
- Images are JPEG, typically 800-1400px wide
- YOLO label format: class_id center_x center_y width height (all normalized 0-1)
- Do NOT use any blocked imports (this tool runs locally, not in sandbox, but keep it simple)

### Priority
HIGH. JC wants to start labeling as soon as images are generated (~12:00 CET today).
The tool needs to be ready by then.

## Delivery
- Put the tool in `agent-cv/tools/labeler/`
- Include a README with how to run it
- Create a desktop launcher at `/Users/jcfrugaard/Desktop/Github_shortcuts/launch-labeler.command`
