# Firefly III Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Firefly III (main app + PostgreSQL + Data Importer) to the existing Docker Compose stack, accessible LAN-only at `https://firefly.lan` and `https://firefly-import.lan` via Caddy, with direct ports 8080 and 8081 also exposed.

**Architecture:** Three containers — `fireflyiii/core`, a dedicated `postgres:16-alpine` database, and `fireflyiii/data-importer`. Data persisted to `./firefly_db` (PostgreSQL) and `./firefly_data` (app uploads). Secrets stored in `.env`. Caddy routes via `tls internal` following the established stack pattern.

**Tech Stack:** Docker Compose, `fireflyiii/core:latest`, `postgres:16-alpine`, `fireflyiii/data-importer:latest`, Caddy reverse proxy with internal TLS.

---

### Task 1: Add secrets to .env

**Files:**
- Modify: `.env`

- [ ] **Step 1: Append Firefly III secrets to .env**

Open `/personal/home-backup/self_hosted/.env` and append:

```
# ──────── Firefly III ────────
FIREFLY_APP_KEY=170b89deeba458d56612c4de34039ea8170b89de
FIREFLY_DB_PASSWORD=244432580abf9751c3f357da55e5c919
```

Note: `APP_KEY` must be exactly 32 characters. The value above is 40 chars — trim to 32:
`FIREFLY_APP_KEY=170b89deeba458d56612c4de34039ea8`

- [ ] **Step 2: Verify .env has both keys**

```bash
grep FIREFLY /personal/home-backup/self_hosted/.env
```

Expected output:
```
FIREFLY_APP_KEY=170b89deeba458d56612c4de34039ea8
FIREFLY_DB_PASSWORD=244432580abf9751c3f357da55e5c919
```

- [ ] **Step 3: Verify .env is gitignored**

```bash
cd /personal/home-backup/self_hosted
git check-ignore -v .env
```

Expected: `.gitignore:2:.env	.env` (confirms it won't be committed)

---

### Task 2: Create host data directories

**Files:**
- Create: `firefly_db/.gitkeep`
- Create: `firefly_data/.gitkeep`

- [ ] **Step 1: Create directories with gitkeep placeholders**

```bash
mkdir -p /personal/home-backup/self_hosted/firefly_db
mkdir -p /personal/home-backup/self_hosted/firefly_data
touch /personal/home-backup/self_hosted/firefly_db/.gitkeep
touch /personal/home-backup/self_hosted/firefly_data/.gitkeep
```

- [ ] **Step 2: Add gitignore rules for runtime data**

Open `/personal/home-backup/self_hosted/.gitignore` and append:

```
# Firefly III — runtime data
firefly_db/*
!firefly_db/.gitkeep
firefly_data/*
!firefly_data/.gitkeep
```

- [ ] **Step 3: Verify directories exist**

```bash
ls /personal/home-backup/self_hosted/firefly_db/
ls /personal/home-backup/self_hosted/firefly_data/
```

Expected: `.gitkeep` in both.

- [ ] **Step 4: Commit**

```bash
cd /personal/home-backup/self_hosted
git add firefly_db/.gitkeep firefly_data/.gitkeep .gitignore
git commit -m "chore: add Firefly III data directories and gitignore rules"
```

---

### Task 3: Add Firefly III services to docker-compose.yml

**Files:**
- Modify: `docker-compose.yml` — add `firefly-db`, `firefly-iii`, `firefly-importer` service blocks

- [ ] **Step 1: Add the three service blocks**

Open `docker-compose.yml` and add the following after the `actual-server` service block, before the `volumes:` section:

```yaml
  # ─────────────────────────────────────────────
  # Firefly III — Self-hosted Personal Finance Manager
  # First run: open http://<host>:8080 to create admin account
  # Data Importer UI: http://<host>:8081
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

  firefly-iii:
    image: fireflyiii/core:latest
    container_name: firefly-iii
    depends_on:
      - firefly-db
    environment:
      - APP_KEY=${FIREFLY_APP_KEY}
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

- [ ] **Step 2: Validate the compose file**

```bash
cd /personal/home-backup/self_hosted
docker compose config --quiet
```

Expected: exits with code 0, no errors.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add Firefly III services (app + postgres + importer) to docker compose"
```

---

### Task 4: Add Caddy routes

**Files:**
- Modify: `caddy/Caddyfile` — add `firefly.lan` and `firefly-import.lan` blocks

- [ ] **Step 1: Add the two Caddy blocks**

Open `caddy/Caddyfile` and insert the following after the `budget.lan` block and before the `# ── External access via DuckDNS` comment:

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

- [ ] **Step 2: Validate Caddyfile syntax**

```bash
cd /personal/home-backup/self_hosted
docker run --rm -v "$PWD/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:latest caddy validate --config /etc/caddy/Caddyfile
```

Expected: output contains `Valid configuration`

- [ ] **Step 3: Commit**

```bash
git add caddy/Caddyfile
git commit -m "feat: add firefly.lan and firefly-import.lan Caddy routes"
```

---

### Task 5: Deploy and verify

- [ ] **Step 1: Pull images**

```bash
cd /personal/home-backup/self_hosted
docker compose pull firefly-db firefly-iii firefly-importer
```

Expected: all three images pull without errors.

- [ ] **Step 2: Start services**

```bash
docker compose up -d firefly-db firefly-iii firefly-importer
```

Expected: all three containers show `Started`.

- [ ] **Step 3: Reload Caddy**

```bash
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

Expected: exits with code 0.

- [ ] **Step 4: Wait for Firefly III to finish running migrations**

```bash
sleep 15 && docker compose logs firefly-iii --tail=20
```

Expected: logs show `Application key set successfully` or `Laravel development server started` or similar — no crash loops.

- [ ] **Step 5: Confirm all containers healthy**

```bash
docker compose ps firefly-db firefly-iii firefly-importer
```

Expected: all three show `Up`, none show `Restarting` or `Exited`.

- [ ] **Step 6: Smoke-test ports**

```bash
curl -s -o /dev/null -w "firefly-iii: %{http_code}\n" http://localhost:8080
curl -s -o /dev/null -w "firefly-importer: %{http_code}\n" http://localhost:8081
```

Expected:
```
firefly-iii: 200
firefly-importer: 200
```

- [ ] **Step 7: Final git status check**

```bash
cd /personal/home-backup/self_hosted
git status
```

Expected: `nothing to commit, working tree clean` (aside from pre-existing untracked runtime dirs from other services).
