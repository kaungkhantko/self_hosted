# Odoo 19 Self-Hosted Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Odoo 19 Community Edition (CRM + Accounting) to the existing Docker Compose stack, accessible at `https://odoo.lan` via Caddy with internal TLS.

**Architecture:** Two new containers (`odoo` + `odoo_db`) are appended to `docker-compose.yml`. DB credentials are injected via environment variables. Caddy reverse-proxies `odoo.lan` to `odoo:8069` using the existing `tls internal` pattern.

**Tech Stack:** Docker Compose, `odoo:19` official image, `postgres:16`, Caddy

---

## File Map

| Action | File | Change |
|--------|------|--------|
| Modify | `docker-compose.yml` | Add `odoo` + `odoo_db` services; add `odoo_data` + `odoo_db_data` to `volumes:` |
| Modify | `caddy/Caddyfile` | Add `odoo.lan` reverse proxy block |
| Modify | `.env` | Add `ODOO_DB_PASSWORD` |
| Create | `odoo/odoo.conf` | Minimal Odoo configuration file |

---

### Task 1: Generate a strong DB password and add it to `.env`

**Files:**
- Modify: `.env`

- [ ] **Step 1: Generate a strong random password**

```bash
openssl rand -base64 32
```

Copy the output — this is your `ODOO_DB_PASSWORD`.

- [ ] **Step 2: Add to `.env`**

Append the following line to `.env` (replace `<generated-password>` with the value from Step 1):

```
ODOO_DB_PASSWORD=<generated-password>
```

- [ ] **Step 3: Verify the variable is present**

```bash
grep ODOO_DB_PASSWORD .env
```

Expected output: `ODOO_DB_PASSWORD=<your-value>` (non-empty)

- [ ] **Step 4: Commit**

```bash
git add .env
```

> **Note:** `.env` is in `.gitignore` — `git add .env` will be silently ignored, which is correct. Do not force-add it.

---

### Task 2: Create the Odoo configuration directory and config file

**Files:**
- Create: `odoo/odoo.conf`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p odoo
```

- [ ] **Step 2: Create `odoo/odoo.conf`**

Create the file `odoo/odoo.conf` with this exact content:

```ini
[options]
data_dir = /var/lib/odoo
proxy_mode = True
```

`addons_path` is intentionally omitted — Odoo uses its compiled-in default, which is correct for the official Docker image.

- [ ] **Step 3: Verify the file**

```bash
cat odoo/odoo.conf
```

Expected output:
```
[options]
data_dir = /var/lib/odoo
proxy_mode = True
```

- [ ] **Step 4: Commit**

```bash
git add odoo/odoo.conf
git commit -m "feat: add Odoo config directory and odoo.conf"
```

---

### Task 3: Add `odoo_db` service and `odoo_db_data` volume to docker-compose.yml

**Files:**
- Modify: `docker-compose.yml` (append before the `volumes:` section, add to `volumes:` section)

- [ ] **Step 1: Append `odoo_db` service**

In `docker-compose.yml`, insert the following block **before** the `volumes:` section (i.e., after the `media-watcher` service block, around line 502):

```yaml
  # ─────────────────────────────────────────────
  # Odoo 19 — PostgreSQL database
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

- [ ] **Step 2: Add `odoo_db_data` named volume**

In the `volumes:` section at the bottom of `docker-compose.yml`, add:

```yaml
  odoo_db_data:
```

The `volumes:` section should now look like:

```yaml
volumes:
  caddy_data:
  caddy_config:
  immich_model_cache:
  odoo_db_data:
```

- [ ] **Step 3: Validate compose syntax**

```bash
docker compose config --quiet
```

Expected: no output (exit code 0). Any error means a YAML syntax issue — fix it before proceeding.

- [ ] **Step 4: Pull the postgres image**

```bash
docker compose pull odoo_db
```

Expected: `postgres:16` pulled successfully.

- [ ] **Step 5: Start the database container**

```bash
docker compose up -d odoo_db
```

- [ ] **Step 6: Verify the database is healthy**

```bash
docker compose logs odoo_db --tail=20
```

Expected output should contain: `database system is ready to accept connections`

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add odoo_db postgres service and named volume"
```

---

### Task 4: Add `odoo` service and `odoo_data` volume to docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Append `odoo` service**

In `docker-compose.yml`, insert the following block **after** the `odoo_db` service block and **before** the `volumes:` section:

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
```

- [ ] **Step 2: Add `odoo_data` named volume**

In the `volumes:` section at the bottom of `docker-compose.yml`, add:

```yaml
  odoo_data:
```

The `volumes:` section should now look like:

```yaml
volumes:
  caddy_data:
  caddy_config:
  immich_model_cache:
  odoo_db_data:
  odoo_data:
```

- [ ] **Step 3: Validate compose syntax**

```bash
docker compose config --quiet
```

Expected: no output (exit code 0).

- [ ] **Step 4: Pull the Odoo image**

```bash
docker compose pull odoo
```

Expected: `odoo:19` pulled successfully.

- [ ] **Step 5: Start Odoo**

```bash
docker compose up -d odoo
```

- [ ] **Step 6: Verify Odoo started without errors**

```bash
docker compose logs odoo --tail=30
```

Expected output should contain: `odoo.service.server: HTTP service (werkzeug) running on` or similar startup message. There should be no `FATAL` or `ConnectionRefusedError` lines.

If you see `could not connect to server: Connection refused` it means `odoo_db` is still initializing — wait 10 seconds and re-run the log check.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add odoo service and named volume"
```

---

### Task 5: Add `odoo.lan` to Caddy

**Files:**
- Modify: `caddy/Caddyfile`

- [ ] **Step 1: Add the `odoo.lan` block**

In `caddy/Caddyfile`, append the following block after the last `*.lan` entry (before the `# ── External access` comment):

```caddyfile
odoo.lan {
    reverse_proxy odoo:8069
    tls internal
}
```

- [ ] **Step 2: Reload Caddy**

```bash
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

Expected output: `Successfully loaded new configuration`

- [ ] **Step 3: Verify Caddy config is valid**

```bash
docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile
```

Expected: `Valid configuration`

- [ ] **Step 4: Commit**

```bash
git add caddy/Caddyfile
git commit -m "feat: add odoo.lan reverse proxy to Caddy"
```

---

### Task 6: End-to-end verification

No files modified — this is a verification-only task.

- [ ] **Step 1: Check all three new containers are running**

```bash
docker compose ps odoo odoo_db
```

Expected: both containers show `running` status (not `restarting` or `exited`).

- [ ] **Step 2: Test connectivity from Caddy to Odoo**

```bash
docker compose exec caddy curl -s -o /dev/null -w "%{http_code}" http://odoo:8069/web/health
```

Expected output: `200`

If you get `000` or a connection error, check `docker compose logs odoo --tail=20` for errors.

- [ ] **Step 3: Access Odoo in a browser**

Navigate to `https://odoo.lan` on your LAN.

Expected: Odoo database setup screen or login page loads without certificate warnings (after trusting the internal CA, which is already done for your other `.lan` services).

- [ ] **Step 4: Create the database and install modules**

On the database creation screen:
1. Set a master password (store it safely)
2. Set a database name (e.g. `odoo`)
3. Set your email and admin password
4. Select language and country
5. Click "Create database"

After the database is created, go to **Apps** and install:
- **CRM**
- **Accounting** (search for "Invoicing" or "Accounting")

- [ ] **Step 5: Final commit (stack state)**

```bash
git status
```

If there are any uncommitted changes, commit them now. Otherwise, the stack is complete.

---

## Rollback

If anything goes wrong and you need to remove Odoo from the stack:

```bash
# Stop and remove containers
docker compose rm -sf odoo odoo_db

# Remove named volumes (WARNING: destroys all data)
docker volume rm self_hosted_odoo_data self_hosted_odoo_db_data

# Revert docker-compose.yml and Caddyfile changes via git
git checkout docker-compose.yml caddy/Caddyfile
```
