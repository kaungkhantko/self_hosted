# Actual Budget — Self-Hosted Design

**Date:** 2026-04-03  
**Status:** Approved

## Goal

Add [Actual Budget](https://github.com/actualbudget/actual) to the existing self-hosted Docker Compose stack, accessible LAN-only via Caddy at `https://budget.lan`.

## Architecture

Single container using the official `actualbudget/actual-server` image. No external database required — Actual Budget uses SQLite embedded in its data directory. Follows the identical pattern of every other service in the stack.

```
Browser (LAN)
    └── https://budget.lan (Caddy, internal TLS)
            └── actual-server:5006 (Docker container)
                    └── ./actual_data:/data (host volume, SQLite + budget files)
```

## Components

### 1. Docker Compose service (`docker-compose.yml`)

```yaml
actual-server:
  image: actualbudget/actual-server:latest
  container_name: actual-server
  volumes:
    - ./actual_data:/data
  ports:
    - "5006:5006"
  deploy:
    resources:
      limits:
        memory: 128m
  restart: unless-stopped
```

- No environment variables required at container level
- Password and budget setup handled via the web UI on first login
- Port 5006 is the upstream default

### 2. Caddy reverse proxy (`caddy/Caddyfile`)

```
budget.lan {
    reverse_proxy actual-server:5006
    tls internal
}
```

Follows the same `*.lan` / `tls internal` pattern used by all other LAN-only services.

### 3. Host data directory

`./actual_data/` — created before first `docker compose up`. Stores SQLite databases and uploaded budget files. Back this directory up to preserve all budget data.

## Data & Persistence

All budget data lives in `./actual_data`. No external database, no Redis, no additional containers. The Actual server uses SQLite internally and stores encrypted sync files per budget on disk.

## Error Handling

- Container restart policy is `unless-stopped`, consistent with all other services.
- If the container crashes, it restarts automatically.
- Data directory is on the host, so a container restart/update does not lose data.

## Testing / Verification

After deployment:
1. `docker compose ps` — confirm `actual-server` is `Up`
2. Navigate to `https://budget.lan` — confirm Caddy serves it with a valid internal cert
3. Complete first-run setup (create password, create or import a budget)

## Out of Scope

- External (DuckDNS) access — intentionally excluded; LAN-only is the chosen access model
- Multi-user setup — Actual Budget is designed for personal/household use
- Automated backups — handled separately by existing backup strategy for the host
