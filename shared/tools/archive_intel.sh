#!/bin/bash
# Archive read intelligence messages to keep inboxes clean
# Moves all .md files EXCEPT CONSOLIDATED-ORDERS.md to an _archive/ subfolder
# Usage: archive_intel.sh [agent-name|all]

MAIN_REPO="/Volumes/devdrive/github_dev/nmiai-2026-main"
TIMESTAMP=$(date +%Y%m%d-%H%M)

archive_folder() {
    local FOLDER="$1"
    local AGENT="$2"

    if [ ! -d "$FOLDER" ]; then
        echo "  Skipping $AGENT (folder not found)"
        return
    fi

    ARCHIVE="$FOLDER/_archive"
    mkdir -p "$ARCHIVE"

    COUNT=0
    for f in "$FOLDER"/*.md; do
        [ -f "$f" ] || continue
        BASENAME=$(basename "$f")
        if [ "$BASENAME" = "CONSOLIDATED-ORDERS.md" ]; then
            continue
        fi
        mv "$f" "$ARCHIVE/${TIMESTAMP}_${BASENAME}"
        COUNT=$((COUNT + 1))
    done

    echo "  $AGENT: archived $COUNT messages"
}

AGENTS="${1:-all}"

if [ "$AGENTS" = "all" ]; then
    echo "Archiving intelligence messages..."
    for AGENT in cv ml nlp ops; do
        archive_folder "$MAIN_REPO/intelligence/for-${AGENT}-agent" "$AGENT"
    done
    archive_folder "$MAIN_REPO/intelligence/for-overseer" "overseer"
    archive_folder "$MAIN_REPO/intelligence/for-jc" "jc"
else
    archive_folder "$MAIN_REPO/intelligence/for-${AGENTS}-agent" "$AGENTS"
fi

echo "Done. CONSOLIDATED-ORDERS.md preserved in all folders."
