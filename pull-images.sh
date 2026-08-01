#!/bin/bash
# Sequential image pull to avoid rate-limit/bandwidth issues
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

IMAGES=(
  "vaultwarden/server:latest"
  "linuxserver/bazarr"
  "louislam/uptime-kuma:1"
  "b4bz/homer:latest"
  "linuxserver/readarr:amd64-nightly-version-0.4.19.2811"
  "linuxserver/calibre-web:latest"
  "docker.io/valkey/valkey:9"
  "ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0"
  "ghcr.io/immich-app/immich-server:release"
  "ghcr.io/immich-app/immich-machine-learning:release-cuda"
  "deluan/navidrome"
  "linuxserver/duckdns"
  "caddy:latest"
  "jellyfin/jellyfin"
  "n8nio/n8n:latest"
  "qmcgaw/gluetun:latest"
  "linuxserver/qbittorrent"
  "ghcr.io/flaresolverr/flaresolverr:latest"
  "linuxserver/prowlarr"
  "linuxserver/radarr"
  "linuxserver/sonarr"
  "linuxserver/lidarr"
  "ghcr.io/seerr-team/seerr:v3.1.0"
  "binwiederhier/ntfy"
)

LOG="$SCRIPT_DIR/pull-images.log"
echo "[$(date)] Starting sequential image pull..." > "$LOG"
for img in "${IMAGES[@]}"; do
  echo "[$(date)] Pulling: $img" >> "$LOG"
  docker pull "$img" >> "$LOG" 2>&1
  echo "[$(date)] Done: $img (exit $?)" >> "$LOG"
done
echo "[$(date)] All pulls complete." >> "$LOG"
echo "PULLS_DONE" >> "$LOG"
