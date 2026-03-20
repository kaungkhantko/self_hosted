#!/usr/bin/env bash
# pull-images.sh — Sequential image pull to avoid rate-limit/bandwidth issues
# Usage: bash scripts/pull-images.sh
#        or via: ./run.sh pull
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="${REPO_ROOT}/pull-images.log"

IMAGES=(
  "vaultwarden/server:latest"
  "linuxserver/bazarr"
  "louislam/uptime-kuma:1"
  "ghcr.io/linuxserver/readarr:amd64-nightly-version-0.4.19.2811"
  "linuxserver/calibre-web:latest"
  "docker.io/valkey/valkey:9"
  "ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0"
  "ghcr.io/immich-app/immich-server:release"
  "ghcr.io/immich-app/immich-machine-learning:release"
)

echo "[$(date)] Starting sequential image pull..." > "$LOG"
for img in "${IMAGES[@]}"; do
  echo "[$(date)] Pulling: $img" >> "$LOG"
  docker pull "$img" >> "$LOG" 2>&1
  echo "[$(date)] Done: $img (exit $?)" >> "$LOG"
done
echo "[$(date)] All pulls complete." >> "$LOG"
echo "PULLS_DONE" >> "$LOG"
