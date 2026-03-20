#!/bin/bash
# Inbox checker v2 for competition agents
# Uses PreToolUse hook with additionalContext so Claude (the model) sees messages
# Usage: check_inbox_v2.sh <agent-name> (cv, ml, nlp, ops)

AGENT="${1:-unknown}"
MAIN_REPO="/Volumes/devdrive/github_dev/nmiai-2026-main"
INBOX="$MAIN_REPO/intelligence/for-${AGENT}-agent"

if [ ! -d "$INBOX" ]; then
    exit 0
fi

MARKER="$INBOX/.last_check"

# Find new messages
if [ ! -f "$MARKER" ]; then
    NEW_FILES=$(find "$INBOX" -maxdepth 1 -name "*.md" 2>/dev/null)
else
    NEW_FILES=$(find "$INBOX" -maxdepth 1 -name "*.md" -newer "$MARKER" 2>/dev/null)
fi

COUNT=$(echo "$NEW_FILES" | grep -c . 2>/dev/null || echo 0)

if [ "$COUNT" -gt 0 ] && [ -n "$NEW_FILES" ]; then
    # Read the content of new messages (first 500 chars each, max 3 messages)
    CONTENT=""
    MSG_NUM=0
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        MSG_NUM=$((MSG_NUM + 1))
        [ "$MSG_NUM" -gt 3 ] && break
        BASENAME=$(basename "$f")
        MSG_BODY=$(head -c 500 "$f" 2>/dev/null | tr '\n' ' ' | tr '"' "'")
        CONTENT="${CONTENT}[${BASENAME}]: ${MSG_BODY} "
    done <<< "$NEW_FILES"

    # Output JSON with additionalContext for PreToolUse hook
    # This injects the message into Claude's context so the MODEL sees it
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"OVERSEER MESSAGE for %s agent (%d new): %s -- READ these files in intelligence/for-%s-agent/ and act on them NOW."}}\n' \
        "$AGENT" "$COUNT" "$CONTENT" "$AGENT"
fi

# Update marker AFTER checking
touch "$MARKER"
exit 0
