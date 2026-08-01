# Paperless-ngx Self-Hosted Deployment Design

**Date:** 2026-04-03  
**Status:** Approved

## Overview

Add Paperless-ngx to the existing self-hosted Docker Compose stack as a document management system with OCR. It will be accessible LAN-only at `https://docs.lan`.

## Architecture

Two new containers added to the existing `docker-compose.yml`:

| Container | Image | Role |
|---|---|---|
| `paperless-redis` | `valkey/valkey:9` | Job queue / broker |
| `paperless-ngx` | `ghcr.io/paperless-ngx/paperless-ngx:latest` | App server + OCR worker |

Database: SQLite (embedded inside `paperless-ngx` container, persisted via `./paperless/` volume). Chosen over PostgreSQL because this is a single-user personal deployment and the upstream project recommends SQLite for this use case.

`paperless-ngx` depends on `paperless-redis`.

## Data Layout

| Purpose | Host Path | Container Path |
|---|---|---|
| Config + SQLite DB + media | `./paperless/` | `/usr/src/paperless/data` |
| Archived documents | `/mnt/personal/Documents/paperless/` | `/usr/src/paperless/media` |
| Consume folder (inbox) | `/mnt/personal/Documents/paperless-consume/` | `/usr/src/paperless/consume` |
| Export folder | `/mnt/personal/Documents/paperless-export/` | `/usr/src/paperless/export` |

Files dropped into `paperless-consume/` are automatically picked up, OCR'd, and archived. The export folder is used by `document_exporter` for backups.

## Configuration

All environment variables set directly on the container (no secrets except `PAPERLESS_SECRET_KEY` which lives in `.env`).

| Variable | Value | Notes |
|---|---|---|
| `PAPERLESS_REDIS` | `redis://paperless-redis:6379` | Points to broker container |
| `PAPERLESS_OCR_LANGUAGE` | `eng+mya` | English + Myanmar (Tesseract) |
| `PAPERLESS_TIME_ZONE` | `Asia/Rangoon` | Matches all other services |
| `PAPERLESS_URL` | `https://docs.lan` | Required for CSRF and internal links |
| `PAPERLESS_SECRET_KEY` | `${PAPERLESS_SECRET_KEY}` | Random string in `.env` |
| `USERMAP_UID` | `1000` | Matches host user and all other services |
| `USERMAP_GID` | `1000` | Matches host user and all other services |

Resource limit: 1GB RAM (OCR can spike briefly; 512MB is too tight for Myanmar Tesseract data).

Port 8000 exposed on host for debugging, but Caddy reaches the container by name directly.

## Routing

New entry in `caddy/Caddyfile` (LAN-only, internal TLS):

```
docs.lan {
    reverse_proxy paperless-ngx:8000
    tls internal
}
```

No external DuckDNS route.

## Changes Required

1. **`docker-compose.yml`** — add `paperless-redis` and `paperless-ngx` services
2. **`.env`** — add `PAPERLESS_SECRET_KEY`
3. **`caddy/Caddyfile`** — add `docs.lan` block
4. **Host directories** — create `/mnt/personal/Documents/paperless/`, `/mnt/personal/Documents/paperless-consume/`, `/mnt/personal/Documents/paperless-export/` with correct ownership (`1000:1000`)

## Post-Deploy Steps

1. Create the initial superuser: `docker compose exec paperless-ngx python manage.py createsuperuser`
2. Visit `https://docs.lan` and log in
3. Configure storage paths and any additional settings in the UI
4. Optionally configure email ingestion later via Settings → Mail

## Backup

- Run `docker compose exec paperless-ngx document_exporter ../export` to export all documents to `/mnt/personal/Documents/paperless-export/`
- The `./paperless/` directory (config + SQLite DB) should be included in any host-level backup

## Out of Scope

- Email ingestion (can be configured post-deploy via UI)
- External access (no DuckDNS route added)
- PostgreSQL migration (SQLite is sufficient; migration path exists if needed later)
