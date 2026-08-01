#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$SCRIPT_DIR/pull-images.log"
APPLY_LOG="$SCRIPT_DIR/compose-apply.log"

echo "[$(date)] Waiting for image pulls to complete..." > "$APPLY_LOG"

# Wait until pull script signals it's done
while ! grep -q "PULLS_DONE" "$LOG" 2>/dev/null; do
  sleep 15
done

echo "[$(date)] Pulls complete. Running docker compose up..." >> "$APPLY_LOG"
cd "$SCRIPT_DIR"
docker compose up -d --remove-orphans >> "$APPLY_LOG" 2>&1
echo "[$(date)] docker compose up exit: $?" >> "$APPLY_LOG"
echo "APPLY_DONE" >> "$APPLY_LOG"
