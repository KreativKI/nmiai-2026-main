#!/bin/bash
# Inbox checker for competition agents
# Called as a PostToolUse hook - alerts agent when new messages arrive
# Usage: check_inbox.sh <agent-name> (cv, ml, nlp, ops)

AGENT="${1:-unknown}"
MAIN_REPO="/Volumes/devdrive/github_dev/nmiai-2026-main"
INBOX="$MAIN_REPO/intelligence/for-${AGENT}-agent"

if [ ! -d "$INBOX" ]; then
    exit 0
fi

MARKER="$INBOX/.last_check"

if [ ! -f "$MARKER" ]; then
    COUNT=$(find "$INBOX" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$COUNT" -gt 0 ]; then
        FILES=$(ls -1 "$INBOX"/*.md 2>/dev/null | xargs -I{} basename {} | head -5)
        echo "NEW MESSAGES ($COUNT) in intelligence/for-${AGENT}-agent/: $FILES -- Read them now."
    fi
    touch "$MARKER"
    exit 0
fi

NEW_FILES=$(find "$INBOX" -maxdepth 1 -name "*.md" -newer "$MARKER" 2>/dev/null)
COUNT=$(echo "$NEW_FILES" | grep -c . 2>/dev/null || echo 0)

if [ "$COUNT" -gt 0 ]; then
    NAMES=$(echo "$NEW_FILES" | xargs -I{} basename {} | head -5 | tr '\n' ', ' | sed 's/,$//')
    echo "NEW MESSAGES ($COUNT) in intelligence/for-${AGENT}-agent/: $NAMES -- Read them now."
fi

touch "$MARKER"
