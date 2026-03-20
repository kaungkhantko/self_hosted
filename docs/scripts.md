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
