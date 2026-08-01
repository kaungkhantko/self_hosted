# Odoo 19 Self-Hosted Design

**Date:** 2026-04-03  
**Status:** Approved

---

## Overview

Add Odoo 19.0 Community Edition to the existing Docker Compose self-hosted stack, accessible on the local network at `odoo.lan` via Caddy with internal TLS. Initial use case: CRM and Accounting modules.

---

## Architecture

Two new containers are added to the existing `docker-compose.yml`:

- **`odoo`** — `odoo:19` official image; Odoo 19.0 Community Edition application server
- **`odoo_db`** — `postgres:16` dedicated database for Odoo, isolated from all other services

Caddy reverse-proxies `odoo.lan` to `odoo:8069` with `tls internal` (same pattern as all other LAN services).

Two named Docker volumes provide persistent storage:
- `odoo_data` — Odoo filestore: uploaded attachments, session files, compiled assets
- `odoo_db_data` — PostgreSQL data directory

A minimal config file at `./odoo/odoo.conf` configures database connectivity and enables proxy mode.

---

## Components

### Docker Compose additions

Two new service blocks appended to `docker-compose.yml`, plus two entries added to the existing `volumes:` section:

```yaml
  # ─────────────────────────────────────────────
  # Odoo 19 — CRM + Accounting (Community Edition)
  odoo:
    image: odoo:19
    container_name: odoo
    depends_on:
      - odoo_db
    environment:
      - HOST=odoo_db
      - USER=odoo
      - PASSWORD=${ODOO_DB_PASSWORD}
    volumes:
      - odoo_data:/var/lib/odoo
      - ./odoo/odoo.conf:/etc/odoo/odoo.conf
    restart: unless-stopped

  odoo_db:
    image: postgres:16
    container_name: odoo_db
    environment:
      - POSTGRES_DB=postgres
      - POSTGRES_USER=odoo
      - POSTGRES_PASSWORD=${ODOO_DB_PASSWORD}
    volumes:
      - odoo_db_data:/var/lib/postgresql/data
    restart: unless-stopped
```

No ports are exposed to the host — all access goes through Caddy.

The official Odoo Docker image reads database credentials from the `HOST`, `USER`, and `PASSWORD` environment variables, which override any values in `odoo.conf`. This keeps secrets out of the config file.

### Caddy configuration

One new block added to `caddy/Caddyfile`:

```caddyfile
odoo.lan {
    reverse_proxy odoo:8069
    tls internal
}
```

### Odoo configuration file

New file at `./odoo/odoo.conf`:

```ini
[options]
data_dir = /var/lib/odoo
proxy_mode = True
```

`addons_path` is intentionally omitted — Odoo uses its compiled-in default for the official Docker image. Adding it would require hardcoding the Python dist-packages path which differs between Odoo versions.

`proxy_mode = True` is required when Odoo sits behind a reverse proxy. Without it, Odoo generates incorrect redirect URLs and sessions may fail.

### Environment variables

One new variable added to `.env`:

```
ODOO_DB_PASSWORD=<strong-random-password>
```

---

## Data Persistence

| Volume | Mount path in container | Contents |
|--------|------------------------|----------|
| `odoo_data` | `/var/lib/odoo` | Filestore, sessions, compiled assets |
| `odoo_db_data` | `/var/lib/postgresql/data` | Postgres database files |

Both are named Docker volumes (not bind mounts) for portability and to avoid permission issues.

---

## First-Run Flow

1. Bring up the stack: `docker compose up -d odoo_db odoo`
2. Navigate to `https://odoo.lan` on the LAN
3. Odoo presents the database creation screen — create a new database
4. Install CRM and Accounting modules from the Apps menu
5. Complete initial configuration wizard

---

## Out of Scope

- External (DuckDNS) access — LAN only by design
- Odoo Enterprise features
- Multi-worker / gevent longpolling setup
- Automated backups (can be added later)
- Custom addons

---

## Upgrade Path

To upgrade Odoo in the future:
1. Stop containers and back up `odoo_data` volume and Postgres database
2. Change the image tag in `docker-compose.yml` (e.g. `odoo:19` → `odoo:20`)
3. Restart — Odoo runs migrations automatically on startup
