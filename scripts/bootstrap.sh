#!/usr/bin/env bash
# bootstrap.sh — First-run setup for self_hosted stack
# Run via: ./run.sh bootstrap
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Step 0: .env check ──────────────────────────────────────────────────────
if [[ ! -f "${REPO_ROOT}/.env" ]]; then
  echo "ERROR: .env not found."
  echo "       Copy .env.example to .env and fill in all values first:"
  echo "       cp .env.example .env && nano .env"
  exit 1
fi

# ── Step 1: Load env ────────────────────────────────────────────────────────
set -a; source "${REPO_ROOT}/.env"; set +a
MEDIA_PATH="${MEDIA_PATH:-/mnt/media}"

# ── Step 2: Media drive check ───────────────────────────────────────────────
if ! mountpoint -q "${MEDIA_PATH}"; then
  echo "ERROR: ${MEDIA_PATH} is not a mountpoint."
  echo "       Mount the media hard drive first."
  echo "       See README.md — 'Disk Setup' section."
  exit 1
fi
echo "✓ Media drive mounted at ${MEDIA_PATH}"

# ── Step 3: Create required directories ─────────────────────────────────────
echo "Creating media directories..."
mkdir -p \
  "${MEDIA_PATH}/TV" \
  "${MEDIA_PATH}/Movies" \
  "${MEDIA_PATH}/Music" \
  "${MEDIA_PATH}/Books" \
  "${MEDIA_PATH}/downloads/complete" \
  "${MEDIA_PATH}/downloads/incomplete"
echo "✓ Directories ready"

# ── Step 4: Install systemd unit ────────────────────────────────────────────
echo "Installing systemd unit..."
sudo cp "${REPO_ROOT}/systemd/selfhosted.service" /etc/systemd/system/selfhosted.service
sudo systemctl daemon-reload
sudo systemctl enable selfhosted
echo "✓ selfhosted.service installed and enabled"

# ── Step 5: Pull images ──────────────────────────────────────────────────────
echo "Pulling Docker images (this may take a while)..."
cd "${REPO_ROOT}"
docker compose pull

# ── Step 6: Start stack ──────────────────────────────────────────────────────
echo "Starting stack..."
docker compose up -d
echo "✓ Stack started"

# ── Step 7: Wait for *arr services to be healthy ────────────────────────────
echo "Waiting for *arr services to be healthy..."
ARR_SERVICES=(
  "http://localhost:7878/api/v3/system/status?apikey=${RADARR_KEY}"
  "http://localhost:8989/api/v3/system/status?apikey=${SONARR_KEY}"
)
for url in "${ARR_SERVICES[@]}"; do
  for i in $(seq 1 12); do
    if curl -sf "${url}" > /dev/null 2>&1; then
      echo "  ✓ ${url%%\?*} healthy"
      break
    fi
    if [[ $i -eq 12 ]]; then
      echo "  WARNING: service at ${url%%\?*} did not respond in 60s — continuing anyway"
    fi
    sleep 5
  done
done

# ── Step 8: Run preflight (organize loose movie files) ───────────────────────
echo "Running preflight.py (organizes loose movie files)..."
python3 "${REPO_ROOT}/scripts/preflight.py"
echo "✓ Preflight complete"

# ── Step 9: Seed Sonarr/Radarr libraries ────────────────────────────────────
echo "Running import_to_arr.py (seeds Sonarr/Radarr — skips existing)..."
python3 "${REPO_ROOT}/scripts/import_to_arr.py"
echo "✓ Import complete"

echo ""
echo "════════════════════════════════════════════"
echo "  Bootstrap complete! Stack is running."
echo "  Run ./run.sh status to verify all services."
echo "════════════════════════════════════════════"
