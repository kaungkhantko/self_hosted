# Actual Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Actual Budget (`actualbudget/actual-server`) to the existing Docker Compose stack, accessible LAN-only at `https://budget.lan` via Caddy.

**Architecture:** Single container using the official `actualbudget/actual-server` Docker image. Data persisted to `./actual_data` on the host (SQLite, no external DB). Caddy routes `budget.lan` to the container with `tls internal`, following the identical pattern used by all other LAN-only services.

**Tech Stack:** Docker Compose, `actualbudget/actual-server:latest`, Caddy reverse proxy with internal TLS.

---

### Task 1: Create host data directory

**Files:**
- Create: `actual_data/.gitkeep` (empty placeholder so git tracks the directory)

- [ ] **Step 1: Create the directory and a gitkeep placeholder**

```bash
mkdir -p /personal/home-backup/self_hosted/actual_data
touch /personal/home-backup/self_hosted/actual_data/.gitkeep
```

- [ ] **Step 2: Verify directory exists**

```bash
ls /personal/home-backup/self_hosted/actual_data/
```

Expected output: `.gitkeep`

- [ ] **Step 3: Commit**

```bash
cd /personal/home-backup/self_hosted
git add actual_data/.gitkeep
git commit -m "chore: add actual_data directory for Actual Budget persistence"
```

---

### Task 2: Add actual-server to docker-compose.yml

**Files:**
- Modify: `docker-compose.yml` — add `actual-server` service block

- [ ] **Step 1: Add the service block**

Open `docker-compose.yml` and add the following block before the `volumes:` section at the bottom of the file (after the `media-watcher` service, before `volumes:`):

```yaml
  # ─────────────────────────────────────────────
  # Actual Budget — Personal Finance / Budgeting
  # First run: open https://budget.lan and set a password
  # Data persisted at ./actual_data (SQLite — no external DB needed)
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

- [ ] **Step 2: Validate the compose file**

```bash
cd /personal/home-backup/self_hosted
docker compose config --quiet
```

Expected: exits with code 0 and no errors.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add Actual Budget (actual-server) service to docker compose"
```

---

### Task 3: Add budget.lan to Caddyfile

**Files:**
- Modify: `caddy/Caddyfile` — add `budget.lan` reverse proxy block

- [ ] **Step 1: Add the Caddy block**

Open `caddy/Caddyfile` and append the following at the end of the LAN-only section (after the `jellyseerr.lan` block, before the `# ── External access` comment):

```
budget.lan {
	reverse_proxy actual-server:5006
	tls internal
}
```

- [ ] **Step 2: Verify the Caddyfile syntax**

```bash
cd /personal/home-backup/self_hosted
docker run --rm -v "$PWD/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:latest caddy validate --config /etc/caddy/Caddyfile
```

Expected output ends with: `Valid configuration`

- [ ] **Step 3: Commit**

```bash
git add caddy/Caddyfile
git commit -m "feat: add budget.lan Caddy route for Actual Budget"
```

---

### Task 4: Deploy and verify

- [ ] **Step 1: Pull the new image**

```bash
cd /personal/home-backup/self_hosted
docker compose pull actual-server
```

Expected: pulls `actualbudget/actual-server:latest` without errors.

- [ ] **Step 2: Start the new service**

```bash
docker compose up -d actual-server
```

Expected: `Container actual-server  Started`

- [ ] **Step 3: Reload Caddy to pick up the new route**

```bash
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

Expected: exits with code 0.

- [ ] **Step 4: Confirm the container is healthy**

```bash
docker compose ps actual-server
```

Expected: `actual-server` shows `Up` (not `Restarting` or `Exited`).

- [ ] **Step 5: Smoke-test the HTTP endpoint directly**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5006
```

Expected: `200` (Actual Budget serves its web UI on `/`).

- [ ] **Step 6: Open in browser and complete first-run setup**

Navigate to `https://budget.lan` in a browser on the LAN.

- Accept the internal TLS cert if prompted (Caddy internal CA).
- Create a server password when asked.
- Create a new budget or import an existing one.

- [ ] **Step 7: Final commit (no code changes — just verify git is clean)**

```bash
cd /personal/home-backup/self_hosted
git status
```

Expected: `nothing to commit, working tree clean`
