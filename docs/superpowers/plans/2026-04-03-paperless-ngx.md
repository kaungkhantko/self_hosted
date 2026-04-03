# Paperless-ngx Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Paperless-ngx document management with OCR to the existing Docker Compose self-hosted stack, accessible at `https://docs.lan`.

**Architecture:** Two new containers (`paperless-redis` as broker, `paperless-ngx` as app+worker) are added to `docker-compose.yml`. SQLite is used as the database (embedded, no separate DB container). Documents are stored on the host at `/mnt/personal/Documents/paperless/`; files dropped into `/mnt/personal/Documents/paperless-consume/` are auto-ingested and OCR'd.

**Tech Stack:** Docker Compose, `ghcr.io/paperless-ngx/paperless-ngx:latest`, `valkey/valkey:9`, Caddy reverse proxy (internal TLS), Tesseract OCR (eng+mya)

---

### Task 1: Add PAPERLESS_SECRET_KEY to .env

**Files:**
- Modify: `.env`

- [ ] **Step 1: Append the secret key to .env**

Open `.env` and add the following block at the end:

```
# ──────── Paperless-ngx ────────
PAPERLESS_SECRET_KEY=rWZSBOxeya6JOA5KKw9EL9tVHS7CqZMO5WxjlT1lXMbqD0jKDTDHag
```

- [ ] **Step 2: Verify the key is present**

Run:
```bash
grep PAPERLESS_SECRET_KEY .env
```
Expected output:
```
PAPERLESS_SECRET_KEY=rWZSBOxeya6JOA5KKw9EL9tVHS7CqZMO5WxjlT1lXMbqD0jKDTDHag
```

- [ ] **Step 3: Commit**

```bash
git add .env
git commit -m "chore: add paperless-ngx secret key to .env"
```

---

### Task 2: Add paperless-redis service to docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add the paperless-redis service**

In `docker-compose.yml`, append the following block before the `volumes:` section at the bottom of the file (after the `media-watcher` service):

```yaml
  # ─────────────────────────────────────────────
  # Paperless-ngx Redis — Job queue / broker
  paperless-redis:
    image: docker.io/valkey/valkey:9
    container_name: paperless-redis
    restart: unless-stopped
```

- [ ] **Step 2: Validate compose syntax**

Run:
```bash
docker compose config --quiet
```
Expected: no output (exit code 0). If there is output, fix any YAML indentation errors.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add paperless-redis broker container"
```

---

### Task 3: Add paperless-ngx service to docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add the paperless-ngx service**

In `docker-compose.yml`, append the following block directly after the `paperless-redis` service (still before the `volumes:` section):

```yaml
  # ─────────────────────────────────────────────
  # Paperless-ngx — Document Management with OCR
  # Consume folder (inbox): /mnt/personal/Documents/paperless-consume/
  # Drop documents there to auto-ingest, OCR, and archive them.
  # After first deploy, create admin: docker compose exec paperless-ngx python manage.py createsuperuser
  paperless-ngx:
    image: ghcr.io/paperless-ngx/paperless-ngx:latest
    container_name: paperless-ngx
    depends_on:
      - paperless-redis
    environment:
      - PAPERLESS_REDIS=redis://paperless-redis:6379
      - PAPERLESS_OCR_LANGUAGE=eng+mya
      - PAPERLESS_TIME_ZONE=Asia/Rangoon
      - PAPERLESS_URL=https://docs.lan
      - PAPERLESS_SECRET_KEY=${PAPERLESS_SECRET_KEY}
      - USERMAP_UID=1000
      - USERMAP_GID=1000
    volumes:
      - ./paperless:/usr/src/paperless/data
      - /mnt/personal/Documents/paperless:/usr/src/paperless/media
      - /mnt/personal/Documents/paperless-consume:/usr/src/paperless/consume
      - /mnt/personal/Documents/paperless-export:/usr/src/paperless/export
    ports:
      - "8000:8000"
    deploy:
      resources:
        limits:
          memory: 1g
    restart: unless-stopped
```

- [ ] **Step 2: Validate compose syntax**

Run:
```bash
docker compose config --quiet
```
Expected: no output (exit code 0).

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add paperless-ngx document management service"
```

---

### Task 4: Add docs.lan to Caddyfile

**Files:**
- Modify: `caddy/Caddyfile`

- [ ] **Step 1: Add the docs.lan block**

In `caddy/Caddyfile`, append the following after the `books.lan` block (keeping all LAN entries together):

```
docs.lan {
	reverse_proxy paperless-ngx:8000
	tls internal
}
```

Use a tab for indentation, matching the style of all other blocks in the file.

- [ ] **Step 2: Verify the block is present**

Run:
```bash
grep -A2 "docs.lan" caddy/Caddyfile
```
Expected:
```
docs.lan {
	reverse_proxy paperless-ngx:8000
	tls internal
```

- [ ] **Step 3: Commit**

```bash
git add caddy/Caddyfile
git commit -m "feat: add docs.lan Caddy route for paperless-ngx"
```

---

### Task 5: Create host directories

**Files:**
- No file changes — host filesystem setup.

- [ ] **Step 1: Create the three document directories**

Run:
```bash
sudo mkdir -p /mnt/personal/Documents/paperless \
              /mnt/personal/Documents/paperless-consume \
              /mnt/personal/Documents/paperless-export
```

- [ ] **Step 2: Set ownership to uid/gid 1000**

Run:
```bash
sudo chown -R 1000:1000 /mnt/personal/Documents/paperless \
                         /mnt/personal/Documents/paperless-consume \
                         /mnt/personal/Documents/paperless-export
```

- [ ] **Step 3: Verify ownership**

Run:
```bash
ls -ld /mnt/personal/Documents/paperless \
       /mnt/personal/Documents/paperless-consume \
       /mnt/personal/Documents/paperless-export
```
Expected: all three lines show `kaung kaung` (uid 1000) as owner.

---

### Task 6: Pull images and start services

- [ ] **Step 1: Pull the new images**

Run:
```bash
docker compose pull paperless-redis paperless-ngx
```
Expected: both images download successfully.

- [ ] **Step 2: Start the new services**

Run:
```bash
docker compose up -d paperless-redis paperless-ngx
```
Expected: both containers start without error.

- [ ] **Step 3: Reload Caddy to pick up the new docs.lan route**

Run:
```bash
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```
Expected: `{"level":"info",...,"msg":"config reloaded"}` or similar (no error).

- [ ] **Step 4: Check paperless-ngx logs for startup errors**

Run:
```bash
docker compose logs --tail=40 paperless-ngx
```
Expected: logs showing database migrations completed and the server listening on port 8000. There should be no `ERROR` lines. The Myanmar Tesseract data download may appear in early logs — this is normal and only happens on first start.

---

### Task 7: Create superuser and verify access

- [ ] **Step 1: Create the admin user**

Run (fill in your preferred username/email/password when prompted):
```bash
docker compose exec -it paperless-ngx python manage.py createsuperuser
```
Expected: prompts for username, email, password. Completes with no error.

- [ ] **Step 2: Verify the web UI is reachable**

Open a browser on your LAN and navigate to:
```
https://docs.lan
```
Expected: Paperless-ngx login page loads (accept the internal CA cert warning if you haven't installed the Caddy CA yet). Log in with the credentials created in Step 1.

- [ ] **Step 3: Smoke-test document ingestion**

Copy any PDF into the consume folder:
```bash
cp /path/to/any.pdf /mnt/personal/Documents/paperless-consume/
```
Wait ~30 seconds, then refresh the Paperless UI. The document should appear in the inbox with OCR text extracted.

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "chore: paperless-ngx fully deployed and verified"
```
