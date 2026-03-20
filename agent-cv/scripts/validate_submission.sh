#!/bin/bash
# Validate a submission ZIP before uploading to competition
# Usage: ./validate_submission.sh path/to/submission.zip
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CV_DIR="$(dirname "$SCRIPT_DIR")"
ZIP_PATH="${1:?Usage: validate_submission.sh path/to/submission.zip}"

echo "=== NorgesGruppen Submission Validator ==="
echo "ZIP: $ZIP_PATH"

# 1. Check zip exists and size
if [ ! -f "$ZIP_PATH" ]; then
    echo "ERROR: ZIP file not found: $ZIP_PATH"
    exit 1
fi

ZIP_SIZE=$(stat -f%z "$ZIP_PATH" 2>/dev/null || stat -c%s "$ZIP_PATH" 2>/dev/null)
ZIP_MB=$((ZIP_SIZE / 1024 / 1024))
echo "Size: ${ZIP_MB}MB (limit: 420MB)"
if [ "$ZIP_MB" -gt 420 ]; then
    echo "ERROR: ZIP exceeds 420MB limit!"
    exit 1
fi

# 2. Check structure
echo ""
echo "=== ZIP Contents ==="
unzip -l "$ZIP_PATH" | head -30
echo ""

# Check run.py at root
if ! unzip -l "$ZIP_PATH" | grep -q "^ .* run.py$"; then
    echo "ERROR: run.py not found at ZIP root!"
    exit 1
fi
echo "OK: run.py found at root"

# Count .py files
PY_COUNT=$(unzip -l "$ZIP_PATH" | grep '\.py$' | wc -l)
echo "Python files: $PY_COUNT (limit: 10)"
if [ "$PY_COUNT" -gt 10 ]; then
    echo "ERROR: More than 10 .py files!"
    exit 1
fi

# Count weight files
WEIGHT_COUNT=$(unzip -l "$ZIP_PATH" | grep -E '\.(onnx|pt|pth|bin|safetensors)$' | wc -l)
echo "Weight files: $WEIGHT_COUNT (limit: 3)"
if [ "$WEIGHT_COUNT" -gt 3 ]; then
    echo "ERROR: More than 3 weight files!"
    exit 1
fi

# 3. Check for blocked imports using Python (avoids false positives)
echo ""
echo "=== Checking for BLOCKED imports ==="
TMPDIR=$(mktemp -d)
unzip -q "$ZIP_PATH" -d "$TMPDIR"

python3 "$SCRIPT_DIR/check_blocked_imports.py" "$TMPDIR"
IMPORT_CHECK=$?
if [ "$IMPORT_CHECK" -ne 0 ]; then
    echo "FATAL: Blocked imports found! Submitting this = INSTANT BAN"
    rm -rf "$TMPDIR"
    exit 1
fi

# 4. Docker validation
echo ""
echo "=== Docker Validation ==="

# Prepare submission dir for Docker
SUBMISSION_DIR="$CV_DIR/submission"
rm -rf "$SUBMISSION_DIR"
cp -r "$TMPDIR" "$SUBMISSION_DIR"

# Create test images if none exist
TEST_IMAGES="$CV_DIR/test_images"
mkdir -p "$TEST_IMAGES"
if [ -z "$(ls -A "$TEST_IMAGES" 2>/dev/null)" ]; then
    echo "Creating dummy test images..."
    python3 -c "
from PIL import Image
for i in range(3):
    img = Image.new('RGB', (2000, 1500), color=(128, 128, 128))
    img.save('$TEST_IMAGES/img_{:05d}.jpg'.format(i+1))
print('Created 3 dummy test images')
"
fi

# Build and run Docker
echo "Building Docker image..."
docker build -t ng-sandbox "$CV_DIR" 2>&1 | tail -3

OUTPUT_DIR="$CV_DIR/docker_output"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

echo "Running submission in Docker sandbox..."
if docker run --rm \
    -v "$TEST_IMAGES:/data/images:ro" \
    -v "$OUTPUT_DIR:/tmp:rw" \
    ng-sandbox \
    python run.py --images /data/images --output /tmp/predictions.json 2>&1; then
    echo ""
    echo "OK: Docker run completed successfully"
else
    echo ""
    echo "FAILED: Docker run failed!"
    rm -rf "$TMPDIR" "$SUBMISSION_DIR"
    exit 1
fi

# 5. Validate output
echo ""
echo "=== Validating Output ==="
if [ ! -f "$OUTPUT_DIR/predictions.json" ]; then
    # Docker maps /tmp to OUTPUT_DIR, so predictions.json should be there
    echo "ERROR: predictions.json not created!"
    rm -rf "$TMPDIR" "$SUBMISSION_DIR"
    exit 1
fi

python3 -c "
import json
with open('$OUTPUT_DIR/predictions.json') as f:
    preds = json.load(f)
assert isinstance(preds, list), 'predictions.json must be a JSON array'
print(f'Predictions: {len(preds)}')
if preds:
    p = preds[0]
    required = {'image_id', 'category_id', 'bbox', 'score'}
    assert required <= set(p.keys()), f'Missing fields: {required - set(p.keys())}'
    assert isinstance(p['bbox'], list) and len(p['bbox']) == 4, 'bbox must be [x,y,w,h]'
    assert 0 <= p['category_id'] <= 355, f'category_id {p[\"category_id\"]} out of range'
    assert 0 <= p['score'] <= 1, f'score {p[\"score\"]} out of range'
    print(f'Sample: image_id={p[\"image_id\"]}, cat={p[\"category_id\"]}, score={p[\"score\"]:.3f}, bbox={p[\"bbox\"]}')
print('OK: Output format valid')
"

# Cleanup
rm -rf "$TMPDIR" "$SUBMISSION_DIR"

echo ""
echo "=== ALL CHECKS PASSED ==="
echo "Safe to submit: $ZIP_PATH"
