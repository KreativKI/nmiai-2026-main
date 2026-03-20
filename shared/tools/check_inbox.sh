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

COUNT=$(find "$INBOX" -name "*.md" -newer "$INBOX/.last_check" 2>/dev/null | wc -l | tr -d ' ')

if [ ! -f "$INBOX/.last_check" ]; then
    COUNT=$(find "$INBOX" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
fi

if [ "$COUNT" -gt 0 ]; then
    FILES=$(find "$INBOX" -name "*.md" -newer "$INBOX/.last_check" 2>/dev/null | xargs -I{} basename {} 2>/dev/null | head -3)
    if [ -z "$FILES" ]; then
        FILES=$(ls "$INBOX"/*.md 2>/dev/null | xargs -I{} basename {} | head -3)
    fi
    echo "NEW MESSAGES ($COUNT) in intelligence/for-${AGENT}-agent/: $FILES — Read them now."
fi
