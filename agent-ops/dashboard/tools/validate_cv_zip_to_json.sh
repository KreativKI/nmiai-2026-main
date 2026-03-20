#!/bin/bash
# Run CV ZIP validator and write JSON to dashboard public/data/
# Usage: ./tools/validate_cv_zip_to_json.sh /path/to/submission.zip
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DASH_DIR="$(dirname "$SCRIPT_DIR")"
VALIDATOR="$DASH_DIR/../../shared/tools/validate_cv_zip.py"
OUTPUT="$DASH_DIR/public/data/cv_validation.json"

if [ -z "$1" ]; then
    echo "Usage: $0 /path/to/submission.zip"
    exit 1
fi

python3 "$VALIDATOR" "$1" --output "$OUTPUT"
echo "Dashboard will show results on next refresh."
