# Deploy-Ready IaC Refactor — Design Spec

**Date:** 2026-03-20
**Status:** Approved
**Author:** kaungkhantko

---

## Goal

Refactor `/home/kaung/self_hosted` into a fully self-contained, deploy-ready infrastructure-as-code repository. Clone the repo on a fresh standalone machine, fill in `.env`, run `./run.sh bootstrap` — the full 25-service media stack comes up with no further manual steps.

---

## Context & Motivation

The stack is currently deployed on a personal PC. The owner is moving it to a dedicated standalone machine. The media hard drive (mounted at `/mnt/media`) is being physically moved to the new machine at the same mount point.

Current pain points:
- Git repo has no remote (no rollback, no portability)
- `.env` with real credentials is not gitignored — committed in plaintext
- Three Python scripts live outside the repo at `/home/kaung/` (not version controlled)
- Subtitle downloader runs as a host-level cron job with a host virtualenv — not portable
- Systemd unit uses the legacy `docker-compose` v1 binary path
- Shell scripts (`pull-images.sh`, `apply-stack.sh`) are stale (reference services not in compose)
- GPU config is baked into the base compose file — non-GPU machines can't use the repo as-is
- All `/mnt/media` paths are hardcoded throughout compose and scripts

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CLI entrypoint | `run.sh` (subcommands) | Universal bash, no Make dependency, easier to extend |
| GPU support | `docker-compose.gpu.yml` overlay | Opt-in via `COMPOSE_FILE` env var — base works on any machine |
| Subtitle downloader | Containerized (`subtitle-cron` service) | Eliminates host virtualenv and host cron — fully contained in compose |
| One-time scripts | `scripts/bootstrap.sh` orchestrator | `./run.sh bootstrap` is the single entry point for fresh machine setup |
| Media path | `MEDIA_PATH=/mnt/media` in `.env` | Configurable, but standardized to `/mnt/media` by convention |
| Photos path | `PHOTOS_PATH=/mnt/personal` in `.env` | Immich mounts `/mnt/personal/Photos` — separate from media drive |
| Legacy services | Document as retired | Nextcloud/photoprism data on disk, not removed — documented in `docs/retired.md` |

---

## Repository Structure

```
self_hosted/
├── .env.example              # committed — all key names, placeholder values, comments
├── .env                      # gitignored — never committed
├── .gitignore
├── run.sh                    # CLI entrypoint: bootstrap|up|down|restart|logs|pull|update|status|help
├── docker-compose.yml        # base stack — no GPU, paths via env vars
├── docker-compose.gpu.yml    # GPU overlay — adds nvidia runtime to jellyfin + immich
│
├── scripts/
│   ├── bootstrap.sh          # first-run orchestrator (env check, dirs, systemd, seed *arr)
│   ├── preflight.py          # moved from /home/kaung/ — organizes loose movie files
│   ├── import_to_arr.py      # moved from /home/kaung/ — seeds Sonarr/Radarr libraries
│   ├── pull-images.sh        # updated to match current compose services
│   └── apply-stack.sh        # existing upgrade helper (moved from root)
│
├── media-watcher/
│   ├── Dockerfile
│   └── watcher.py            # unchanged
│
├── subtitle-cron/
│   ├── Dockerfile            # python:3.12-alpine + subliminal + busybox crond
│   └── download_subs.py      # moved from /home/kaung/ — runs daily at 03:00 in-container
│
├── caddy/
│   └── Caddyfile             # unchanged
│
├── n8n-workflows/            # unchanged
│
├── systemd/
│   └── selfhosted.service    # updated to use `docker compose` v2
│
└── docs/
    ├── README.md             # prerequisites, quick start, command reference
    ├── services.md           # all 25 services — port, URL, purpose
    ├── scripts.md            # preflight.py + import_to_arr.py — when/how to run
    ├── retired.md            # nextcloud + photoprism — data retained, not active
    └── superpowers/          # AI planning artifacts (unchanged)
        ├── specs/
        └── plans/
```

---

## Secrets & Environment

### `.gitignore`
```
.env
*.log
__pycache__/
*.pyc
*.pyo
immich_upload/backups/
immich_upload/encoded-video/
```

### `.env.example` — All Keys

```bash
# === Timezone & User ===
TZ=America/Toronto
PUID=1000
PGID=1000

# === Media Paths ===
# Hard drive mounted at the same path on every machine
MEDIA_PATH=/mnt/media
PHOTOS_PATH=/mnt/personal

# === Docker Compose Profile ===
# No GPU (default): COMPOSE_FILE=docker-compose.yml
# With NVIDIA GPU:  COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml
COMPOSE_FILE=docker-compose.yml

# === DuckDNS ===
DUCKDNS_TOKEN=your-duckdns-token

# === Vaultwarden ===
VAULTWARDEN_ADMIN_TOKEN=your-vaultwarden-admin-token

# === Immich Database ===
IMMICH_DB_PASSWORD=your-immich-db-password

# === Mullvad VPN (Gluetun) ===
MULLVAD_WG_PRIVATE_KEY=your-wireguard-private-key

# === media-watcher ===
QB_URL=http://localhost:8082
QB_USER=admin
QB_PASS=your-qbittorrent-password
RADARR_URL=http://radarr:7878
RADARR_KEY=your-radarr-api-key
SONARR_URL=http://sonarr:8989
SONARR_KEY=your-sonarr-api-key
JELLYFIN_URL=http://jellyfin:8096
JELLYFIN_KEY=your-jellyfin-api-key
POLL_INTERVAL=30
MIN_PROGRESS=0.01
```

---

## Docker Compose Changes

### Base `docker-compose.yml`
- Remove `runtime: nvidia` from `jellyfin`, `immich-server`, `immich-machine-learning`
- Remove `NVIDIA_VISIBLE_DEVICES` and `NVIDIA_DRIVER_CAPABILITIES` env vars from those services
- Replace all hardcoded `/mnt/media` volume paths with `${MEDIA_PATH}`
- Replace `/mnt/personal` with `${PHOTOS_PATH}` in `immich-server`
- Add new `subtitle-cron` service
- Remove stale Nextcloud environment variables (if present)

### `docker-compose.gpu.yml` (new — GPU overlay)
```yaml
services:
  jellyfin:
    runtime: nvidia
    environment:
      NVIDIA_VISIBLE_DEVICES: all
      NVIDIA_DRIVER_CAPABILITIES: compute,video,utility
  immich-server:
    runtime: nvidia
    environment:
      NVIDIA_VISIBLE_DEVICES: all
  immich-machine-learning:
    runtime: nvidia
    environment:
      NVIDIA_VISIBLE_DEVICES: all
```

### `subtitle-cron` service (new)
```yaml
subtitle-cron:
  build: ./subtitle-cron
  restart: unless-stopped
  volumes:
    - ${MEDIA_PATH}:/mnt/media
  environment:
    - TZ=${TZ}
```

---

## `subtitle-cron` Container

**`subtitle-cron/Dockerfile`:**
```dockerfile
FROM python:3.12-alpine
RUN pip install --no-cache-dir subliminal
COPY download_subs.py /app/download_subs.py
RUN echo "0 3 * * * python /app/download_subs.py /mnt/media/TV /mnt/media/Movies >> /proc/1/fd/1 2>&1" \
    | crontab -
CMD ["crond", "-f", "-d", "8"]
```

**`subtitle-cron/download_subs.py`:**
- Moved from `/home/kaung/download_subs.py`
- Adapted to accept multiple directory arguments (`sys.argv[1:]`)
- Replaces host cron + `/home/kaung/subliminal_venv/`

---

## `scripts/bootstrap.sh` Flow

Runs as part of `./run.sh bootstrap`. Steps are idempotent — safe to re-run.

```
Step 0: Check .env exists — exit with instructions if not
Step 1: Source .env to get MEDIA_PATH
Step 2: Check MEDIA_PATH is a mountpoint — exit if drive not mounted
Step 3: Create host dirs:
          ${MEDIA_PATH}/TV
          ${MEDIA_PATH}/Movies
          ${MEDIA_PATH}/Music
          ${MEDIA_PATH}/Books
          ${MEDIA_PATH}/downloads/complete
          ${MEDIA_PATH}/downloads/incomplete
Step 4: Install systemd unit:
          sudo cp systemd/selfhosted.service /etc/systemd/system/
          sudo systemctl daemon-reload
          sudo systemctl enable selfhosted
Step 5: docker compose pull
Step 6: docker compose up -d
Step 7: Wait for *arr services healthy (poll /api/v3/system/status, max 60s)
Step 8: python3 scripts/preflight.py    (organizes loose movie files)
Step 9: python3 scripts/import_to_arr.py  (seeds Sonarr/Radarr — skips existing)
```

---

## `run.sh` Commands

| Command | Action |
|---------|--------|
| `./run.sh bootstrap` | Full first-run setup (calls `scripts/bootstrap.sh`) |
| `./run.sh up` | `docker compose up -d` |
| `./run.sh down` | `docker compose down` |
| `./run.sh restart` | `down` then `up` |
| `./run.sh logs [service]` | `docker compose logs -f [service]` |
| `./run.sh pull` | Pull latest images via `scripts/pull-images.sh` |
| `./run.sh update` | `pull` + `up --remove-orphans` |
| `./run.sh status` | `docker compose ps` |
| `./run.sh help` | Print formatted command reference |

---

## Systemd Unit (`systemd/selfhosted.service`)

```ini
[Unit]
Description=Self-hosted Docker Compose Stack
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

[Install]
WantedBy=multi-user.target
```

Key change: `ExecStart` now uses `docker compose` (v2 plugin) instead of `docker-compose` (legacy v1).
Added `network-online.target` dependency.

---

## Documentation Plan

| File | Contents |
|------|----------|
| `README.md` | Prerequisites (Docker CE, Docker Compose v2), disk setup (fstab by UUID), clone, fill `.env`, `./run.sh bootstrap`, GPU setup instructions, command reference |
| `docs/services.md` | Table: every service, port, local URL, what it does |
| `docs/scripts.md` | `preflight.py` and `import_to_arr.py` — what they do, when to run, how to run them directly |
| `docs/retired.md` | Nextcloud + photoprism — data dirs on disk, why they're not active, how to clean up when ready |

---

## Out of Scope

- Changes to `media-watcher/watcher.py` logic
- n8n workflow content
- Physical media data migration (same drive, same paths)
- Immich photo data migration
- Caddy config changes
- Homer/Homarr dashboard config

---

## Prerequisites for New Machine

1. Ubuntu/Debian Linux (or equivalent)
2. Docker CE + Docker Compose v2 plugin installed
3. Media hard drive mounted at `/mnt/media` via `/etc/fstab` by UUID (with `nofail`)
4. User `kaung` exists with `PUID=1000`, `PGID=1000`
5. For GPU: NVIDIA drivers + NVIDIA Container Toolkit installed; set `COMPOSE_FILE` accordingly in `.env`
