# Deploy-Ready IaC Refactor — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `self_hosted` into a deploy-ready IaC repo — clone, fill `.env`, run `./run.sh bootstrap`, full stack comes up on any machine.

**Architecture:** Single `docker-compose.yml` base + optional GPU overlay, all paths via `.env` vars, all scripts inside the repo, one `run.sh` CLI entrypoint, `scripts/bootstrap.sh` orchestrates first-run.

**Tech Stack:** Docker Compose v2, Bash, Python 3.12, subliminal, busybox crond (Alpine), GitHub CLI (`gh`)

**Spec:** `docs/superpowers/specs/2026-03-20-deploy-ready-iac-refactor.md`

---

## Chunk 1: Foundation — gitignore, env template, spec commit

### Task 1: Add `.gitignore`

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Create `.gitignore`**

```
# Credentials — never commit
.env

# Logs
*.log
compose-up.log
compose-apply.log
pull-images.log

# Python
__pycache__/
*.pyc
*.pyo
*.pyd

# Immich large binary outputs (auto-generated, not source)
immich_upload/backups/
immich_upload/encoded-video/
```

File path: `.gitignore` at repo root.

- [ ] **Step 2: Verify `.env` is no longer tracked**

```bash
git check-ignore -v .env
```
Expected: `.gitignore:2:.env    .env`

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: add .gitignore — exclude .env and generated files"
```

---

### Task 2: Create `.env.example`

**Files:**
- Create: `.env.example`

- [ ] **Step 1: Create `.env.example`**

```
# =============================================================================
# self_hosted — Environment Template
# Copy to .env and fill in all values before running ./run.sh bootstrap
# =============================================================================

# --- Timezone & User --------------------------------------------------------
TZ=America/Toronto
PUID=1000
PGID=1000

# --- Media Paths ------------------------------------------------------------
# Mount the media hard drive at this path via /etc/fstab (see README.md)
# Do not change this unless you deliberately mount the drive elsewhere.
MEDIA_PATH=/mnt/media

# Path to personal photos — used by Immich
PHOTOS_PATH=/mnt/personal

# --- Docker Compose Profile -------------------------------------------------
# No GPU (default):
COMPOSE_FILE=docker-compose.yml
# With NVIDIA GPU (jellyfin NVENC + immich CUDA):
# COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml

# --- DuckDNS ----------------------------------------------------------------
# Get your token at https://www.duckdns.org
DUCKDNS_TOKEN=your-duckdns-token-here

# --- Vaultwarden ------------------------------------------------------------
VAULTWARDEN_ADMIN_TOKEN=your-vaultwarden-admin-token-here

# --- Immich Database --------------------------------------------------------
IMMICH_DB_PASSWORD=your-strong-immich-db-password-here

# --- Mullvad VPN (Gluetun / WireGuard) -------------------------------------
# Generate a WireGuard key pair at https://mullvad.net/en/account/wireguard-config
MULLVAD_WG_PRIVATE_KEY=your-wireguard-private-key-here

# --- media-watcher ----------------------------------------------------------
QB_URL=http://localhost:8082
QB_USER=admin
QB_PASS=your-qbittorrent-password-here
RADARR_URL=http://radarr:7878
RADARR_KEY=your-radarr-api-key-here
SONARR_URL=http://sonarr:8989
SONARR_KEY=your-sonarr-api-key-here
JELLYFIN_URL=http://jellyfin:8096
JELLYFIN_KEY=your-jellyfin-api-key-here
POLL_INTERVAL=30
MIN_PROGRESS=0.01
```

- [ ] **Step 2: Commit spec + env example together**

```bash
git add docs/superpowers/specs/2026-03-20-deploy-ready-iac-refactor.md .env.example
git commit -m "chore: add .env.example and IaC refactor spec"
```

---

## Chunk 2: Docker Compose Refactor

### Task 3: Refactor `docker-compose.yml`

**Files:**
- Modify: `docker-compose.yml`

This task replaces all hardcoded `/mnt/media` and `/mnt/personal` paths with env vars, and removes GPU-specific config from all services. Read the current file first.

- [ ] **Step 1: Replace all `/mnt/media` volume paths with `${MEDIA_PATH}`**

In `docker-compose.yml`, find every occurrence of `/mnt/media` in volume definitions and replace with `${MEDIA_PATH}`. The affected services are:
- `jellyfin` — 3 volume mounts (`/mnt/media/TV`, `/mnt/media/Movies`, `/mnt/media`)
- `qbittorrent` — 1 volume mount
- `radarr` — 1 volume mount
- `sonarr` — 1 volume mount
- `lidarr` — 1 volume mount
- `readarr` — 1 volume mount
- `bazarr` — 1 volume mount
- `navidrome` — 1 volume mount (`/mnt/media/Music`)
- `calibre-web` — 1 volume mount (`/mnt/media/Books`)
- `media-watcher` — 1 volume mount

Use search-and-replace: `/mnt/media` → `${MEDIA_PATH}`

- [ ] **Step 2: Replace `/mnt/personal` with `${PHOTOS_PATH}` in `immich-server`**

Find the `immich-server` volume: `/mnt/personal/Photos:/mnt/personal/Photos:ro`

Replace with: `${PHOTOS_PATH}/Photos:/mnt/personal/Photos:ro`

The host-side path becomes `${PHOTOS_PATH}/Photos` (configurable); the container-side path stays `/mnt/personal/Photos` (unchanged — paths inside the container are fixed).

- [ ] **Step 3: Remove GPU config from `jellyfin`**

Remove these lines from the `jellyfin` service:
```yaml
    runtime: nvidia
```
And remove from its `environment` section:
```yaml
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=compute,video,utility
```

- [ ] **Step 4: Remove GPU config from `immich-server`**

Remove from `immich-server`:
```yaml
    runtime: nvidia
```
And remove from its `environment` section:
```yaml
      - NVIDIA_VISIBLE_DEVICES=all
```

- [ ] **Step 5: Remove GPU config from `immich-machine-learning`**

Remove from `immich-machine-learning`:
```yaml
    runtime: nvidia
```
And remove from its `environment` section:
```yaml
      - NVIDIA_VISIBLE_DEVICES=all
```

- [ ] **Step 6: Validate compose parses correctly**

```bash
docker compose config --quiet
```
Expected: no output, exit code 0. If errors, fix before proceeding.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml
git commit -m "refactor: replace hardcoded media paths with env vars, strip GPU config from base compose"
```

---

### Task 4: Create `docker-compose.gpu.yml`

**Files:**
- Create: `docker-compose.gpu.yml`

- [ ] **Step 1: Create `docker-compose.gpu.yml`**

```yaml
# GPU overlay — activate by setting in .env:
# COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml
#
# Requires: NVIDIA drivers + NVIDIA Container Toolkit on the host.
# Install guide: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html

services:
  jellyfin:
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=compute,video,utility

  immich-server:
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all

  immich-machine-learning:
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
```

- [ ] **Step 2: Validate overlay parses correctly**

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml config --quiet
```
Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.gpu.yml
git commit -m "feat: add docker-compose.gpu.yml overlay for NVIDIA GPU support"
```

---

## Chunk 3: subtitle-cron Service

### Task 5: Move and adapt `download_subs.py`

**Files:**
- Create: `subtitle-cron/download_subs.py` (moved + adapted from `/home/kaung/download_subs.py`)

- [ ] **Step 1: Read the current script**

Read `/home/kaung/download_subs.py`. Identify:
- How the target path is currently received (hardcoded string, `sys.argv[1]`, or argparse)
- The exact line(s) where subliminal is invoked with that path (e.g. a `subprocess.run(...)` or `subliminal.download(...)` call)
- Whether there is an existing `if __name__ == "__main__":` block or bare top-level code

- [ ] **Step 2: Copy the script to `subtitle-cron/download_subs.py`**

Create the `subtitle-cron/` directory and copy the file content there.

- [ ] **Step 3: Adapt to accept multiple directory arguments**

The script currently takes a single path (via `sys.argv[1]` or hardcoded). Wrap the existing subliminal invocation in a `for path in paths:` loop. Do not add the `pass` line — replace the loop body with the actual invocation found in Step 1. The final structure should be:

```python
import sys

if __name__ == "__main__":
    paths = sys.argv[1:]
    if not paths:
        print("Usage: download_subs.py <dir1> [dir2] ...")
        sys.exit(1)
    for path in paths:
        # Paste the existing subliminal download invocation here,
        # substituting the original hardcoded/argv[1] path with `path`.
        # Example (actual call may differ — use what you found in Step 1):
        # subprocess.run(["subliminal", "download", "-l", "en", path], check=True)
```

The key change: one invocation that ran for a single path now runs once per path in the list.

- [ ] **Step 4: Verify Python syntax**

```bash
python3 -m py_compile subtitle-cron/download_subs.py && echo "OK"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add subtitle-cron/download_subs.py
git commit -m "feat: add subtitle-cron/download_subs.py — moved from host, multi-dir support"
```

---

### Task 6: Create `subtitle-cron/Dockerfile`

**Files:**
- Create: `subtitle-cron/Dockerfile`

- [ ] **Step 1: Create `subtitle-cron/Dockerfile`**

```dockerfile
FROM python:3.12-alpine

# Install subliminal and its dependencies
RUN pip install --no-cache-dir subliminal

# Copy subtitle downloader script
COPY download_subs.py /app/download_subs.py

# Set up crontab: run daily at 03:00, log to stdout (PID 1 fd)
RUN echo "0 3 * * * python /app/download_subs.py /mnt/media/TV /mnt/media/Movies >> /proc/1/fd/1 2>&1" \
    | crontab -

# busybox crond: -f foreground, -d 8 debug level (warnings + errors only)
CMD ["crond", "-f", "-d", "8"]
```

- [ ] **Step 2: Verify Dockerfile builds**

```bash
docker build -t subtitle-cron-test ./subtitle-cron
```
Expected: `Successfully built <id>` (or `FINISHED` in BuildKit output). Fix any build errors.

- [ ] **Step 3: Clean up test image**

```bash
docker rmi subtitle-cron-test
```

- [ ] **Step 4: Commit**

```bash
git add subtitle-cron/Dockerfile
git commit -m "feat: add subtitle-cron Dockerfile — containerized daily subtitle downloader"
```

---

### Task 7: Add `subtitle-cron` service to `docker-compose.yml`

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add the `subtitle-cron` service**

Add the following service definition to `docker-compose.yml` (alongside the other services):

```yaml
  subtitle-cron:
    build: ./subtitle-cron
    container_name: subtitle-cron
    restart: unless-stopped
    volumes:
      - ${MEDIA_PATH}:/mnt/media
    environment:
      - TZ=${TZ}
```

- [ ] **Step 2: Validate compose**

```bash
docker compose config --quiet
```
Expected: exit code 0.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add subtitle-cron service to compose — replaces host cron job"
```

---

## Chunk 4: Scripts Consolidation

### Task 8: Move `preflight.py` and `import_to_arr.py` into `scripts/`

**Files:**
- Create: `scripts/preflight.py` (moved from `/home/kaung/preflight.py`)
- Create: `scripts/import_to_arr.py` (moved from `/home/kaung/import_to_arr.py`)

- [ ] **Step 1: Read both scripts**

Read `/home/kaung/preflight.py` and `/home/kaung/import_to_arr.py`. Verify:
- Neither script requires command-line arguments to run (they should use hardcoded paths or read from env vars internally)
- Both use standard library + `requests` (no unusual dependencies)
- There are no hardcoded paths that would break on the new machine (e.g. `/home/kaung/` references instead of `/mnt/media`)

If any hardcoded paths are found that would break, note them — they will need updating in the copy.

- [ ] **Step 2: Copy `preflight.py` to `scripts/preflight.py`**

Content is identical to `/home/kaung/preflight.py` — no logic changes.

- [ ] **Step 3: Copy `import_to_arr.py` to `scripts/import_to_arr.py`**

Content is identical to `/home/kaung/import_to_arr.py` — no logic changes.

- [ ] **Step 4: Verify both files parse cleanly**

```bash
python3 -m py_compile scripts/preflight.py && echo "preflight OK"
python3 -m py_compile scripts/import_to_arr.py && echo "import_to_arr OK"
```
Expected: both print `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/preflight.py scripts/import_to_arr.py
git commit -m "feat: move preflight.py and import_to_arr.py into scripts/"
```

---

### Task 9: Move and update `pull-images.sh` and `apply-stack.sh`

**Files:**
- Create: `scripts/pull-images.sh` (moved + updated from `./pull-images.sh`)
- Create: `scripts/apply-stack.sh` (moved from `./apply-stack.sh`)

- [ ] **Step 1: Read both existing shell scripts**

Read `./pull-images.sh` and `./apply-stack.sh`. In `pull-images.sh`, identify:
- The full list of images being pulled
- The exact readarr image tag currently in the file (it will be something like `ghcr.io/linuxserver/readarr:amd64-nightly-<date>`)
- Whether `homarr` is present (it should be — remove it)

In `apply-stack.sh`, identify:
- All relative file path references (log files, sentinel files)
- Any calls to `docker-compose` (v1) vs `docker compose` (v2)

- [ ] **Step 2: Create `scripts/pull-images.sh`**

Copy the content of `pull-images.sh`, then make these corrections:
- Remove `ghcr.io/ajnart/homarr:latest` — `homarr` is not in `docker-compose.yml`
- Fix readarr image: match the exact tag used in `docker-compose.yml` (the pinned nightly tag, not `:develop`)
- Ensure the sentinel `echo "PULLS_DONE"` writes to `pull-images.log` in the repo root (adjust path if needed since file now lives in `scripts/`)

- [ ] **Step 3: Create `scripts/apply-stack.sh`**

Copy the content of `apply-stack.sh`. The file moves from the repo root to `scripts/`, so fix these specific path references:
- Any reference to `pull-images.log` — change to `"${REPO_ROOT}/pull-images.log"` (add `REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"` at the top of the script if not present)
- Any reference to `compose-apply.log` — change to `"${REPO_ROOT}/compose-apply.log"`
- Any `docker-compose` or `docker compose` call — ensure it uses `docker compose` (v2) and runs from `${REPO_ROOT}`
- The sentinel check that reads `pull-images.log` should use the same `${REPO_ROOT}/pull-images.log` path

- [ ] **Step 4: Verify bash syntax on both**

```bash
bash -n scripts/pull-images.sh && echo "pull-images OK"
bash -n scripts/apply-stack.sh && echo "apply-stack OK"
```
Expected: both print `OK`.

- [ ] **Step 5: Remove old root-level scripts**

```bash
git rm pull-images.sh apply-stack.sh
```

- [ ] **Step 6: Commit**

```bash
git add scripts/pull-images.sh scripts/apply-stack.sh
git commit -m "refactor: move pull-images.sh and apply-stack.sh into scripts/, fix stale image refs"
```

---

### Task 10: Create `scripts/bootstrap.sh`

**Files:**
- Create: `scripts/bootstrap.sh`

- [ ] **Step 1: Create `scripts/bootstrap.sh`**

```bash
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/bootstrap.sh
```

- [ ] **Step 3: Verify bash syntax**

```bash
bash -n scripts/bootstrap.sh && echo "OK"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add scripts/bootstrap.sh
git commit -m "feat: add scripts/bootstrap.sh — first-run orchestrator for fresh machine setup"
```

---

## Chunk 5: `run.sh` + Systemd Unit

### Task 11: Create `run.sh`

**Files:**
- Create: `run.sh`

- [ ] **Step 1: Create `run.sh`**

```bash
#!/usr/bin/env bash
# run.sh — CLI entrypoint for self_hosted stack
# Usage: ./run.sh <command> [args]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${REPO_ROOT}"

# Load .env if it exists (for COMPOSE_FILE support)
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

CMD="${1:-help}"

case "${CMD}" in
  bootstrap)
    ## First-run: env check, dirs, systemd, pull, up, seed *arr
    bash scripts/bootstrap.sh
    ;;
  up)
    ## Start the stack
    docker compose up -d
    ;;
  down)
    ## Stop the stack
    docker compose down
    ;;
  restart)
    ## Stop then start the stack
    docker compose down
    docker compose up -d
    ;;
  logs)
    ## Follow logs — optionally pass a service name
    ## Usage: ./run.sh logs [service]
    shift
    docker compose logs -f "$@"
    ;;
  pull)
    ## Pull latest images via scripts/pull-images.sh
    bash scripts/pull-images.sh
    ;;
  update)
    ## Pull latest images then restart with orphan cleanup
    bash scripts/pull-images.sh
    docker compose up -d --remove-orphans
    ;;
  status)
    ## Show running containers
    docker compose ps
    ;;
  help|--help|-h|"")
    echo ""
    echo "  self_hosted — run.sh command reference"
    echo ""
    echo "  Usage: ./run.sh <command> [args]"
    echo ""
    echo "  Commands:"
    echo "    bootstrap          First-run setup: env, dirs, systemd, seed *arr"
    echo "    up                 Start the stack (docker compose up -d)"
    echo "    down               Stop the stack"
    echo "    restart            Stop then start"
    echo "    logs [service]     Follow logs (all services, or a named one)"
    echo "    pull               Pull latest images"
    echo "    update             Pull + restart with orphan cleanup"
    echo "    status             Show running containers"
    echo "    help               Show this message"
    echo ""
    ;;
  *)
    echo "Unknown command: ${CMD}"
    echo "Run ./run.sh help for usage."
    exit 1
    ;;
esac
```

- [ ] **Step 2: Make executable**

```bash
chmod +x run.sh
```

- [ ] **Step 3: Verify bash syntax**

```bash
bash -n run.sh && echo "OK"
```
Expected: `OK`

- [ ] **Step 4: Smoke test help**

```bash
./run.sh help
```
Expected: prints the command reference table, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add run.sh
git commit -m "feat: add run.sh — bash CLI entrypoint with bootstrap, up, down, logs, update, status"
```

---

### Task 12: Create `systemd/selfhosted.service`

**Files:**
- Create: `systemd/selfhosted.service`

- [ ] **Step 1: Create `systemd/` directory and service file**

```ini
[Unit]
Description=Self-hosted Docker Compose Stack
Documentation=https://github.com/kaungkhantko/self_hosted
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
WorkingDirectory=/home/kaung/self_hosted
RemainAfterExit=yes
TimeoutStartSec=0
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Key changes from current `/etc/systemd/system/selfhosted.service`:
- `ExecStart` uses `docker compose` (v2 plugin) instead of `docker-compose` (legacy v1)
- Added `network-online.target` dependency
- Added `Restart=on-failure`
- Added `Documentation` field

- [ ] **Step 2: Commit**

```bash
git add systemd/selfhosted.service
git commit -m "feat: add systemd/selfhosted.service — updated to docker compose v2"
```

---

## Chunk 6: Documentation

### Task 13: Create `README.md`

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md` at repo root**

```markdown
# self_hosted

Personal self-hosted media and productivity stack running on a dedicated Linux machine.

25 services managed by Docker Compose: Jellyfin, Sonarr, Radarr, Bazarr, Prowlarr, qBittorrent (via Mullvad VPN), Jellyseerr, Immich, Navidrome, Vaultwarden, Calibre-Web, Readarr, Lidarr, Bazarr, n8n, ntfy, Uptime Kuma, Homer, Caddy, and more.

---

## Prerequisites

Install these on the new machine before anything else:

1. **Docker CE + Docker Compose v2**
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   # Log out and back in to apply group membership
   docker compose version  # should print v2.x.x
   ```

2. **Git**
   ```bash
   sudo apt install git
   ```

3. **(Optional) NVIDIA GPU support** — only if the machine has an NVIDIA GPU
   - Install NVIDIA drivers
   - Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
   - Set `COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml` in your `.env`

---

## Disk Setup

The media hard drive must be mounted at `/mnt/media` on every boot.

```bash
# 1. Find the drive UUID
sudo blkid /dev/sdX   # replace sdX with your drive

# 2. Create mount point
sudo mkdir -p /mnt/media

# 3. Add to /etc/fstab (replace UUID with yours, adjust fstype if needed)
echo "UUID=your-uuid-here  /mnt/media  ext4  defaults,nofail  0  2" | sudo tee -a /etc/fstab

# 4. Test mount
sudo mount -a
mountpoint /mnt/media   # should print: /mnt/media is a mountpoint
```

The `nofail` option ensures the machine boots even if the drive is temporarily unplugged.

---

## Quick Start (Fresh Machine)

```bash
# 1. Clone the repo
git clone git@github.com:kaungkhantko/self_hosted.git
cd self_hosted

# 2. Create your .env from the template
cp .env.example .env
nano .env   # fill in all values

# 3. Bootstrap — creates dirs, installs systemd, pulls images, starts stack, seeds *arr
./run.sh bootstrap
```

That's it. The stack starts automatically on every boot via the installed systemd unit.

---

## Daily Commands

```bash
./run.sh status           # show running containers
./run.sh logs             # follow all logs
./run.sh logs jellyfin    # follow a specific service's logs
./run.sh up               # start stack
./run.sh down             # stop stack
./run.sh restart          # restart stack
./run.sh update           # pull latest images + restart
./run.sh help             # full command reference
```

---

## Stack Architecture

| Service | Port | Purpose |
|---------|------|---------|
| Jellyfin | 8096 | Media server |
| Sonarr | 8989 | TV show manager |
| Radarr | 7878 | Movie manager |
| Bazarr | 6767 | Subtitle manager |
| Prowlarr | 9696 | Indexer aggregator |
| qBittorrent | 8082 | Torrent client (via Mullvad VPN) |
| Jellyseerr | 5055 | Media request portal |
| Immich | 2283 | Photo management |
| Navidrome | 4533 | Music streaming |
| Vaultwarden | 8089 | Password manager |
| Calibre-Web | 8083 | Book library |
| Readarr | 8787 | Book manager |
| Lidarr | 8686 | Music manager |
| n8n | 5678 | Workflow automation |
| ntfy | 2586 | Push notifications |
| Uptime Kuma | 3001 | Monitoring |
| Homer | 7575 | Dashboard |
| Caddy | 80/443 | Reverse proxy |
| Gluetun | — | Mullvad WireGuard VPN |
| media-watcher | — | Watch-while-downloading bridge |
| subtitle-cron | — | Daily subtitle downloader |

See [docs/services.md](docs/services.md) for full details.

---

## GPU Support

GPU is **off by default**. To enable NVIDIA GPU (Jellyfin NVENC transcoding + Immich CUDA):

```bash
# In .env, change:
COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml
```

Requires NVIDIA drivers and NVIDIA Container Toolkit on the host.

---

## One-Time Setup Scripts

After bootstrap, these scripts are available for post-install tasks:

- `scripts/preflight.py` — Organizes loose movie files into per-movie subdirs (required by Radarr)
- `scripts/import_to_arr.py` — Seeds Sonarr/Radarr with your existing media library

Bootstrap runs them automatically. To re-run manually:
```bash
python3 scripts/preflight.py
python3 scripts/import_to_arr.py
```

See [docs/scripts.md](docs/scripts.md) for details.

---

## Repo Structure

```
self_hosted/
├── README.md                 # this file
├── run.sh                    # CLI entrypoint
├── docker-compose.yml        # base stack
├── docker-compose.gpu.yml    # GPU overlay (opt-in)
├── .env.example              # env template
├── scripts/                  # bootstrap + utility scripts
├── media-watcher/            # watch-while-downloading service
├── subtitle-cron/            # containerized subtitle downloader
├── caddy/                    # reverse proxy config
├── systemd/                  # systemd unit file
├── n8n-workflows/            # n8n workflow exports
└── docs/                     # documentation
```
```

- [ ] **Step 2: Verify markdown syntax is correct**

Check that the file renders without obvious issues (no unclosed code fences, correct heading levels). No automated check needed — a visual scan is sufficient.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add README.md — quick start, disk setup, command reference"
```

---

### Task 14: Create `docs/services.md`

**Files:**
- Create: `docs/services.md`

- [ ] **Step 1: Create `docs/services.md`**

```markdown
# Services Reference

All services are defined in `docker-compose.yml`. Start/stop with `./run.sh up` / `./run.sh down`.

## Media Stack

| Service | Port | Local URL | Purpose |
|---------|------|-----------|---------|
| Jellyfin | 8096 | http://localhost:8096 | Media server — streams TV, movies, music |
| Sonarr | 8989 | http://localhost:8989 | TV show downloader and library manager |
| Radarr | 7878 | http://localhost:7878 | Movie downloader and library manager |
| Lidarr | 8686 | http://localhost:8686 | Music downloader and library manager |
| Readarr | 8787 | http://localhost:8787 | Book downloader and library manager |
| Bazarr | 6767 | http://localhost:6767 | Subtitle downloader — integrates with Sonarr/Radarr |
| Prowlarr | 9696 | http://localhost:9696 | Indexer aggregator for all *arr apps |
| Jellyseerr | 5055 | http://localhost:5055 | Media request portal — submit TV/movie requests |
| qBittorrent | 8082 | http://localhost:8082 | Torrent client (all traffic via Mullvad VPN) |

## Photos & Personal

| Service | Port | Local URL | Purpose |
|---------|------|-----------|---------|
| Immich | 2283 | http://localhost:2283 | Self-hosted Google Photos alternative |
| Navidrome | 4533 | http://localhost:4533 | Music streaming server (Subsonic-compatible) |
| Calibre-Web | 8083 | http://localhost:8083 | Book library browser and reader |

## Productivity

| Service | Port | Local URL | Purpose |
|---------|------|-----------|---------|
| Vaultwarden | 8089 | http://localhost:8089 | Bitwarden-compatible password manager |
| n8n | 5678 | http://localhost:5678 | Workflow automation |
| ntfy | 2586 | http://localhost:2586 | Push notification server |

## Infrastructure

| Service | Port | Local URL | Purpose |
|---------|------|-----------|---------|
| Caddy | 80, 443 | — | Reverse proxy — LAN + DuckDNS external access |
| Homer | 7575 | http://localhost:7575 | Dashboard / service index |
| Uptime Kuma | 3001 | http://localhost:3001 | Service uptime monitoring |
| Gluetun | — | — | Mullvad WireGuard VPN — qBittorrent routes through this |
| FlareSolverr | 8191 | — | Cloudflare bypass for Prowlarr indexers |
| DuckDNS | — | — | Dynamic DNS updater for external access |

## Custom Services

| Service | Port | Purpose |
|---------|------|---------|
| media-watcher | 8888 (internal) | Watch-while-downloading: creates Jellyfin symlinks for in-progress torrents |
| subtitle-cron | — | Runs `download_subs.py` daily at 03:00 via containerized cron |
```

- [ ] **Step 2: Commit**

```bash
git add docs/services.md
git commit -m "docs: add docs/services.md — full service reference table"
```

---

### Task 15: Create `docs/scripts.md` and `docs/retired.md`

**Files:**
- Create: `docs/scripts.md`
- Create: `docs/retired.md`

- [ ] **Step 1: Create `docs/scripts.md`**

```markdown
# Utility Scripts

These scripts live in `scripts/` and handle one-time setup tasks. Bootstrap runs them automatically. You can also run them manually at any time — they are idempotent (safe to re-run).

---

## `scripts/preflight.py` — Organize Loose Movie Files

**What it does:** Moves movie files that are sitting directly in the root of `${MEDIA_PATH}/Movies/` into proper per-movie subdirectories. This is required before Radarr can import them — Radarr expects `Movies/<Movie Title>/file.mkv`, not `Movies/file.mkv`.

Also moves matching `.en.srt` subtitle sidecar files into the same subdirectory.

**When to run:**
- Automatically during `./run.sh bootstrap`
- Manually after dropping new movie files directly into the Movies folder without a subdirectory

**How to run:**
```bash
python3 scripts/preflight.py
```

**Safe to re-run:** Yes — skips files already in subdirectories.

---

## `scripts/import_to_arr.py` — Seed Sonarr/Radarr Libraries

**What it does:** Adds TV shows and movies to Sonarr/Radarr via their REST APIs. Designed for the initial import of a large existing media library. Handles content the built-in UI importer can't auto-match (anime packs with group-name prefixes, etc.).

Skips entries already present in Sonarr/Radarr. Triggers a rescan for each newly added entry.

**When to run:**
- Automatically during `./run.sh bootstrap` (on first deploy)
- Manually if you've added new entries to the `ENTRIES` list inside the script

**How to run:**
```bash
python3 scripts/import_to_arr.py
```

**Requires:** Sonarr and Radarr must be running and healthy. Bootstrap waits for this before running.

**Safe to re-run:** Yes — skips already-present entries.

---

## `scripts/pull-images.sh` — Pull Docker Images Sequentially

**What it does:** Pulls all Docker images one at a time to avoid Docker Hub rate limits and bandwidth spikes. Used before a stack upgrade.

**When to run:** Before `./run.sh update` when you want to pre-pull images in the background.

```bash
bash scripts/pull-images.sh
# or via:
./run.sh pull
```

---

## `scripts/bootstrap.sh` — First-Run Orchestrator

Invoked by `./run.sh bootstrap`. Not intended to be run directly, but safe to do so.

Steps:
1. Verify `.env` exists
2. Verify media drive is mounted at `${MEDIA_PATH}`
3. Create required media subdirectories
4. Install and enable `systemd/selfhosted.service`
5. Pull Docker images
6. Start the stack (`docker compose up -d`)
7. Wait for Sonarr/Radarr to be healthy
8. Run `preflight.py`
9. Run `import_to_arr.py`
```

- [ ] **Step 2: Create `docs/retired.md`**

```markdown
# Retired Services

These services were previously part of the stack but are no longer active. Their data directories are retained on disk.

---

## Nextcloud

**Status:** Retired (removed from compose)
**Data directories:** `./nextcloud_data/`, `./nextcloud_db/`
**Why retired:** Replaced by a combination of Immich (photos) and other services. Nextcloud's overhead wasn't justified for personal use.
**Stale env vars removed:** `NEXTCLOUD_DB`, `NEXTCLOUD_USER`, `NEXTCLOUD_PASSWORD`

**To clean up when ready:**
```bash
# Only do this if you are certain you no longer need the data
sudo rm -rf /home/kaung/self_hosted/nextcloud_data
sudo rm -rf /home/kaung/self_hosted/nextcloud_db
```

---

## PhotoPrism

**Status:** Retired (removed from compose)
**Data directory:** `./photoprism/`
**Why retired:** Replaced by Immich, which has better mobile app support and performance.

**To clean up when ready:**
```bash
sudo rm -rf /home/kaung/self_hosted/photoprism
```

---

## Homarr

**Status:** Referenced in old `pull-images.sh` but never in compose
**Data directory:** `./homarr/`
**Why retired:** Homer is used instead.

**To clean up when ready:**
```bash
sudo rm -rf /home/kaung/self_hosted/homarr
```
```

- [ ] **Step 3: Commit both**

```bash
git add docs/scripts.md docs/retired.md
git commit -m "docs: add docs/scripts.md and docs/retired.md"
```

---

## Chunk 7: GitHub Private Repo + Push

### Task 16: Create private GitHub repo and push

**Files:** none — git + GitHub operations only

- [ ] **Step 1: Verify gh CLI is authenticated**

```bash
gh auth status
```
Expected: `✓ Logged in to github.com account kaungkhantko`

- [ ] **Step 2: Create the private repo on GitHub**

```bash
gh repo create kaungkhantko/self_hosted \
  --private \
  --description "Self-hosted media and productivity stack — deploy-ready IaC" \
  --source . \
  --remote origin
```

Expected: `✓ Created repository kaungkhantko/self_hosted on GitHub` and remote `origin` added locally. **Commits are not pushed yet** — that happens in Step 5.

- [ ] **Step 3: Verify remote was added**

```bash
git remote -v
```
Expected:
```
origin  git@github.com:kaungkhantko/self_hosted.git (fetch)
origin  git@github.com:kaungkhantko/self_hosted.git (push)
```

- [ ] **Step 4: Verify `.env` is not in git history before pushing**

The `.env` file with real credentials was previously committed to the local repo before `.gitignore` was added. Purge it from history before pushing to GitHub:

```bash
# Check if .env appears anywhere in git history
git log --all --full-history -- .env
```

If the above shows any commits, remove it from history:

```bash
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all
```

Then verify it's gone:

```bash
git log --all --full-history -- .env
```
Expected: no output (no commits reference `.env`).

Also verify `.env` is not currently tracked:
```bash
git ls-files .env
```
Expected: no output. If it prints `.env`, run `git rm --cached .env && git commit -m "chore: untrack .env"` before pushing.

- [ ] **Step 5: Push all commits to GitHub**

```bash
git push -u origin master
```
Expected: `Branch 'master' set up to track remote branch 'master' from 'origin'.`

- [ ] **Step 6: Verify repo is visible and private**

```bash
gh repo view kaungkhantko/self_hosted
```
Expected: shows repo details with `Visibility: private`.

- [ ] **Step 7: Final status check**

```bash
git status
git log --oneline -15
```
Expected: clean working tree, all commits visible.
