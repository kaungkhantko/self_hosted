#!/usr/bin/env bash
# Installs jellyfin-mpv-shim as a systemd user service.
# Run once after cloning the repo on a new machine.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_SRC="$SCRIPT_DIR/jellyfin-mpv-shim.service"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_DST="$SERVICE_DIR/jellyfin-mpv-shim.service"

if ! command -v jellyfin-mpv-shim &>/dev/null; then
  echo "jellyfin-mpv-shim not found. Install it first:"
  echo "  sudo pacman -S jellyfin-mpv-shim"
  exit 1
fi

mkdir -p "$SERVICE_DIR"
cp "$SERVICE_SRC" "$SERVICE_DST"

systemctl --user daemon-reload
systemctl --user enable --now jellyfin-mpv-shim.service

echo "Done. Status:"
systemctl --user status jellyfin-mpv-shim.service --no-pager
