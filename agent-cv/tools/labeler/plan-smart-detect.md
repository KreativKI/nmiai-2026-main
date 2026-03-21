# Plan: Smart Product Detection (Double-Tap)

## Problem
Current GrabCut uses color only. Products stacked together (same color) look like one big block. Need to detect individual product boundaries using both color AND shape/edges.

## Trigger
Double-tap on the product on iPad. Single tap/drag still draws manually.

## Approach: Color + Edge Hybrid Detection

### Step 1: Pre-process (20ms)
- Bilateral filter: smooth noise while preserving edges
- `cv2.bilateralFilter(img, d=9, sigmaColor=75, sigmaSpace=75)`

### Step 2: Edge detection (20ms)
- Canny edge detection to find product boundaries
- Edges reveal individual product shapes even when colors are identical
- Find contours from edges
- Filter: keep contours near the tap point and above minimum area

### Step 3: Contour selection (5ms)
- From all contours, find the one closest to the tap point
- If the tap point is inside a contour, use that contour
- If not, find the nearest contour by distance
- Get bounding rect of that contour

### Step 4: GrabCut refinement (50ms)
- Use the contour's bounding rect as the GrabCut init rect
- This is tighter than the generic 40% box we use now
- Run GrabCut with 5 iterations
- The edge-guided init rect means GrabCut starts closer to the answer

### Step 5: Post-process (10ms)
- Morphological opening (remove shelf artifacts)
- Keep largest connected foreground component near tap point
- Get tight bounding rect

### Total: ~105ms (well under 200ms)

## Fallback
If edge detection finds no good contour near the tap point, fall back to current approach: rough centered box + GrabCut.

## Frontend change
- Double-tap detection: two taps within 300ms and 30px of each other
- Single tap + drag: still works for manual drawing
- Swipe: still works for navigation

## Files to change
- `server.py`: new `/api/smart-detect` endpoint with the hybrid approach
- `index.html`: double-tap detection in pointer handler
