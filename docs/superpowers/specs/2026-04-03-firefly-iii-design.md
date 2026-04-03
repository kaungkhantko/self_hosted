# Firefly III — Self-Hosted Design

**Date:** 2026-04-03  
**Status:** Approved

## Goal

Add [Firefly III](https://www.firefly-iii.org/) to the existing Docker Compose self-hosted stack, accessible LAN-only via Caddy at `https://firefly.lan`, with the Data Importer at `https://firefly-import.lan`. Both services also expose direct ports for immediate access.

## Architecture

Three containers following the official Firefly III production deployment pattern. A dedicated PostgreSQL database keeps Firefly III's data isolated from other services (e.g. Immich's DB). The Data Importer is a separate web UI for importing CSV/OFX files and connecting bank accounts.

```
Browser (LAN)
    ├── https://firefly.lan  (Caddy, internal TLS)  ──► firefly-iii:8080
    │   also: http://<host>:8080 (direct port)
    └── https://firefly-import.lan (Caddy, internal TLS) ──► firefly-importer:8081
        also: http://<host>:8081 (direct port)

firefly-iii ──► firefly-db:5432 (PostgreSQL 16)
                    └── ./firefly_db:/var/lib/postgresql/data
firefly-iii ──► ./firefly_data:/var/www/html/storage/upload
```

## Components

### 1. `firefly-iii` — Main App

```yaml
firefly-iii:
  image: fireflyiii/core:latest
  container_name: firefly-iii
  depends_on:
    - firefly-db
  environment:
    - APP_KEY=${FIREFLY_APP_KEY}           # 32-char random key
    - APP_URL=http://firefly.lan
    - DB_CONNECTION=pgsql
    - DB_HOST=firefly-db
    - DB_PORT=5432
    - DB_DATABASE=firefly
    - DB_USERNAME=firefly
    - DB_PASSWORD=${FIREFLY_DB_PASSWORD}
    - TZ=Asia/Rangoon
    - TRUSTED_PROXIES=**
  volumes:
    - ./firefly_data:/var/www/html/storage/upload
  ports:
    - "8080:8080"
  deploy:
    resources:
      limits:
        memory: 512m
  restart: unless-stopped
```

### 2. `firefly-db` — PostgreSQL 16

```yaml
firefly-db:
  image: postgres:16-alpine
  container_name: firefly-db
  environment:
    - POSTGRES_USER=firefly
    - POSTGRES_PASSWORD=${FIREFLY_DB_PASSWORD}
    - POSTGRES_DB=firefly
  volumes:
    - ./firefly_db:/var/lib/postgresql/data
  deploy:
    resources:
      limits:
        memory: 256m
  restart: unless-stopped
```

### 3. `firefly-importer` — Data Importer

```yaml
firefly-importer:
  image: fireflyiii/data-importer:latest
  container_name: firefly-importer
  depends_on:
    - firefly-iii
  environment:
    - FIREFLY_III_URL=http://firefly-iii:8080
    - VANITY_URL=http://firefly.lan
    - TZ=Asia/Rangoon
  ports:
    - "8081:8080"
  deploy:
    resources:
      limits:
        memory: 128m
  restart: unless-stopped
```

### 4. Caddy routes (`caddy/Caddyfile`)

```
firefly.lan {
    reverse_proxy firefly-iii:8080
    tls internal
}

firefly-import.lan {
    reverse_proxy firefly-importer:8080
    tls internal
}
```

### 5. `.env` additions

```
# Firefly III
FIREFLY_APP_KEY=<32-char random string, generated at deploy time>
FIREFLY_DB_PASSWORD=<random password, generated at deploy time>
```

### 6. Host data directories

- `./firefly_db/` — PostgreSQL data
- `./firefly_data/` — app uploads and attachments

## Data & Persistence

- All budget data in `./firefly_db` (PostgreSQL). Back this up to preserve all data.
- Attachments/uploads in `./firefly_data`.
- No named Docker volumes — consistent with the rest of the stack.

## Error Handling

- All containers: `restart: unless-stopped`
- `firefly-iii` has `depends_on: firefly-db` so the app only starts after DB is up
- `firefly-importer` has `depends_on: firefly-iii`

## Verification After Deploy

1. `docker compose ps` — all three containers `Up`
2. `http://<host>:8080` — Firefly III first-run setup (create admin account)
3. `http://<host>:8081` — Data Importer UI loads
4. `https://firefly.lan` — Caddy serves with internal cert

## Out of Scope

- External (DuckDNS) access — LAN-only is the chosen model
- Automatic bank sync (GoCardless/Nordigen) — can be configured later in the Data Importer UI
- Cron jobs for recurring transactions — Firefly III handles this via its own scheduler
