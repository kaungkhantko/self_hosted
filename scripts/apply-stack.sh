#!/usr/bin/env bash
# apply-stack.sh — Wait for image pulls then apply docker compose up
# Usage: bash scripts/apply-stack.sh
#        (typically run in the background after scripts/pull-images.sh)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="${REPO_ROOT}/pull-images.log"
APPLY_LOG="${REPO_ROOT}/compose-apply.log"

echo "[$(date)] Waiting for image pulls to complete..." > "$APPLY_LOG"

# Wait until pull script signals it's done
while ! grep -q "PULLS_DONE" "$LOG" 2>/dev/null; do
  sleep 15
done

echo "[$(date)] Pulls complete. Running docker compose up..." >> "$APPLY_LOG"
cd "${REPO_ROOT}"
docker compose up -d --remove-orphans >> "$APPLY_LOG" 2>&1
echo "[$(date)] docker compose up exit: $?" >> "$APPLY_LOG"
echo "APPLY_DONE" >> "$APPLY_LOG"
