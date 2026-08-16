#!/bin/bash

PROJECT="/Users/mary/munich-ai-job-alert"
PYTHON="$PROJECT/.venv/bin/python"
LOCKDIR="/tmp/munich-ai-job-alert.lock"

cd "$PROJECT" || exit 1

# Prevent overlapping runs
if ! mkdir "$LOCKDIR" 2>/dev/null; then
    exit 0
fi

trap 'rmdir "$LOCKDIR"' EXIT

echo ""
echo "========================================"
echo "Run started: $(date)"
echo "========================================"

"$PYTHON" "$PROJECT/main.py"

echo "Run finished: $(date)"
