# Implementation Plan — Food Tracker (Obsidian → SQLite + Renpho)

**Source of truth:** the design decisions from the food-tracker design conversation (no gh issue exists for this work); vault plugin formats verified against `forketyfork/obsidian-food-tracker` `constants.ts`/`NutritionCalculator.ts` and `danvaneijck/renpho-api` `client.py` at plan time.
**Repo:** kaungkhantko/self_hosted — `/home/kaung/server_hosted`
**Base:** `master` @ `43fcba99ba6fef19c8a179448c8bca4adbc7b124`
**Branch:** `feature/food-tracker`

Conventions (from `git log`): conventional commits — `feat:`, `fix:`, `docs:`, `chore:`; lowercase summary, no trailing period; feature work on `feature/<slug>` branches; plans and service docs committed as `docs:` commits; runtime data dirs as `chore:` with gitkeep + `.gitignore`; every compose service carries `deploy.resources.limits.memory`; custom services live in `./<name>/` with a `Dockerfile`.

Implement commits in order; each leaves the tree working. Commits 1–5 are this repo; "Manual follow-ups" are steps on other machines/repos — not commits.

## 1. docs: add food tracker implementation plan

Intent: commit the plan first, matching the Firefly III precedent (`docs: add Firefly III implementation plan`), so the repo documents what it will build before the code lands.

New file `docs/food-tracker.md` — full content is this plan file (copy it verbatim).

Checks: none natural.

## 2. chore: add food-tracker runtime data dir and gitignore rules

Intent: reserve the `./food-data` runtime dir (SQLite, vault mirror, token cache, heartbeat) with a gitkeep, and gitignore its contents — same shape as `actual_data` and `firefly_db`.

New file `food-data/.gitkeep` — empty.

`-` in `.gitignore`, after the Actual Budget block (line 25):

```
+# Food tracker — runtime data (SQLite, vault mirror, renpho token)
+food-data/*
+!food-data/.gitkeep
```

Checks: `git check-ignore food-data/food.db` prints `food-data/food.db`.

## 3. feat: add food-tracker sync script (Obsidian vault to SQLite + Renpho poll)

Intent: the tracker itself — a two-loop daemon that mirrors the notes vault from Forgejo, parses `#food` entries from daily notes into SQLite, polls the Renpho cloud every 6 h for body composition, and maintains a BMR-derived daily kcal goal. Runtime data in `/data`; all config via env.

New files — full content:

`food-tracker/Dockerfile`

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir renpho-api
WORKDIR /app
COPY main.py .
CMD ["python", "-u", "main.py"]
```

`food-tracker/main.py`

```python
#!/usr/bin/env python3
"""food-tracker: Obsidian vault -> SQLite, plus Renpho body-composition poll.

Loop A (every 10 min): git-pull a mirror of the notes vault from Forgejo, parse
  #food entries in Personal/Notes/Daily/YYYY-MM-DD.md, upsert food_entries.
Loop B (every 6 h): poll the Renpho cloud for body measurements, store
  body_measurements, and maintain a BMR-derived daily kcal goal.

Runtime data (SQLite, vault mirror, token cache, heartbeat) lives in /data.
"""

import datetime as dt
import glob
import hashlib
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import time

from renpho import RenphoClient

LOG = logging.getLogger("food-tracker")

VAULT = "/data/vault"
DB_PATH = "/data/food.db"
TOKEN_PATH = "/data/renpho_token.json"
HEARTBEAT = "/data/heartbeat"

DAILY_DIR = os.path.join(VAULT, "Personal", "Notes", "Daily")
PRODUCTS_DIR = os.environ.get("PRODUCTS_DIR", "Foods")

FOOD_TAG = os.environ.get("FOOD_TAG", "food")
ACTIVITY_FACTOR = float(os.environ.get("ACTIVITY_FACTOR", "1.5"))
FORGEJO_REPO_URL = os.environ.get("FORGEJO_REPO_URL", "")

LOOP_A_SECONDS = 600
LOOP_B_SECONDS = 21600
SLEEP_SECONDS = 60

# --- Entry formats, mirroring obsidian-food-tracker constants.ts -----------
LINKED_RE = re.compile(
    rf"#{re.escape(FOOD_TAG)}\s+(?:\[\[(?P<name>[^\]]+)\]\]|\[[^\]]*\]\((?P<md>[^)]+)\))\s+(?P<amount>\d+(?:\.\d+)?)(?P<unit>kg|lb|cups?|tbsp|tsp|ml|oz|g|l|pcs?)",
    re.I,
)
INLINE_VALUE_RE = re.compile(r"-?\d+(?:\.\d+)?(?:kcal|fat|satfat|prot|carbs|sugar|fiber|sodium)", re.I)

UNIT_TO_GRAMS = {
    "g": 1.0, "kg": 1000.0, "ml": 1.0, "l": 1000.0,
    "oz": 28.35, "lb": 453.6, "cup": 240.0, "cups": 240.0,
    "tbsp": 15.0, "tsp": 5.0,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS food_entries (
  id         INTEGER PRIMARY KEY,
  date       TEXT NOT NULL,
  name       TEXT NOT NULL,
  mass_g     REAL,
  line_hash  TEXT NOT NULL UNIQUE,
  kcal       REAL,
  protein_g  REAL,
  carbs_g    REAL,
  fat_g      REAL,
  source     TEXT NOT NULL DEFAULT 'plugin',
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS body_measurements (
  id             INTEGER PRIMARY KEY,
  measured_at    TEXT NOT NULL UNIQUE,
  weight_kg      REAL,
  bodyfat_pct    REAL,
  muscle_pct     REAL,
  water_pct      REAL,
  bone_kg        REAL,
  visfat         REAL,
  bmr_kcal       REAL,
  heart_rate_bpm REAL
);

CREATE TABLE IF NOT EXISTS goals (
  id        INTEGER PRIMARY KEY,
  date      TEXT NOT NULL,
  kcal      REAL,
  protein_g REAL,
  carbs_g   REAL,
  fat_g     REAL,
  source    TEXT NOT NULL DEFAULT 'manual'
);

CREATE VIEW IF NOT EXISTS daily_totals AS
  SELECT date, SUM(kcal) AS kcal, SUM(protein_g) AS protein_g,
         SUM(carbs_g) AS carbs_g, SUM(fat_g) AS fat_g, COUNT(*) AS entries
  FROM food_entries GROUP BY date;
"""


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def save_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f)


def line_hash(date, line):
    return hashlib.sha1(f"{date}|{line}".encode()).hexdigest()


def read_product(name):
    """Read a product note's frontmatter. Returns dict of NutrientData keys or None."""
    for base in (os.path.join(VAULT, PRODUCTS_DIR), VAULT):
        path = os.path.join(base, name + ".md")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            return None
        if not text.startswith("---"):
            return None
        _, front, _ = text.split("---", 2)
        data = {}
        for m in re.finditer(r"^(\w[\w]*)\s*:\s*(.+?)\s*$", front, re.M):
            key, val = m.group(1), m.group(2)
            try:
                data[key] = float(val)
            except ValueError:
                data[key] = val
        return data
    return None


def unit_multiplier(amount, unit, serving_size=None):
    """Multiplier on per-100g values, parity with plugin getUnitMultiplier."""
    unit = unit.lower()
    if unit in ("pc", "pcs"):
        return amount * (serving_size if serving_size else 100) / 100.0
    return amount * UNIT_TO_GRAMS.get(unit, 1.0) / 100.0


def parse_note(conn, path, date):
    with open(path, encoding="utf-8") as f:
        content = f.read()
    tag_re = re.compile(rf"#{re.escape(FOOD_TAG)}\b", re.I)
    if not tag_re.search(content):
        return
    for lineno, line in enumerate(content.splitlines(), 1):
        if not tag_re.search(line):
            continue
        line = line.strip()
        m = LINKED_RE.search(line)
        if m:
            name = m.group("name") or m.group("md")
            name = os.path.basename(name).removesuffix(".md")
            amount, unit = float(m.group("amount")), m.group("unit").lower()
            data = read_product(name)
            if data is None:
                LOG.warning("no product note for [[%s]] (%s:%s)", name, date, lineno)
                continue
            mult = unit_multiplier(amount, unit, data.get("serving_size"))
            if unit in ("pc", "pcs"):
                mass_g = amount * (data.get("serving_size") or 100.0)
            else:
                mass_g = amount * UNIT_TO_GRAMS.get(unit, 1.0)
            row = {
                "name": name, "mass_g": mass_g, "source": "plugin",
                "kcal": data.get("calories"),
                "protein_g": data.get("protein"),
                "carbs_g": data.get("carbs"),
                "fat_g": data.get("fats"),
            }
            for k in ("kcal", "protein_g", "carbs_g", "fat_g"):
                if row[k] is not None:
                    row[k] = round(row[k] * mult, 2)
            upsert_entry(conn, date, line, row)
        else:
            body = re.sub(rf"^#{re.escape(FOOD_TAG)}\s+", "", line, flags=re.I)
            tokens = INLINE_VALUE_RE.findall(body)
            if not tokens:
                LOG.warning("unparsed #food line (%s:%s): %s", date, lineno, line)
                continue
            values = {}
            for t in tokens:
                num = re.sub(r"[a-z]+", "", t)
                unit = re.sub(r"[\d.-]+", "", t).lower()
                values[unit] = float(num)
            name = INLINE_VALUE_RE.sub("", body).strip()
            row = {
                "name": name, "mass_g": None, "source": "inline",
                "kcal": values.get("kcal"),
                "protein_g": values.get("prot"),
                "carbs_g": values.get("carbs"),
                "fat_g": values.get("fat"),
            }
            upsert_entry(conn, date, line, row)


def upsert_entry(conn, date, line, row):
    h = line_hash(date, line)
    conn.execute(
        """INSERT INTO food_entries (date, name, mass_g, line_hash, kcal, protein_g, carbs_g, fat_g, source, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))
           ON CONFLICT(line_hash) DO UPDATE SET
             name=excluded.name, mass_g=excluded.mass_g, kcal=excluded.kcal,
             protein_g=excluded.protein_g, carbs_g=excluded.carbs_g,
             fat_g=excluded.fat_g, source=excluded.source, updated_at=excluded.updated_at""",
        (date, row["name"], row["mass_g"], h, row["kcal"], row["protein_g"], row["carbs_g"], row["fat_g"], row["source"]),
    )


def git(args, cwd):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)


def ensure_mirror():
    if not FORGEJO_REPO_URL:
        LOG.error("FORGEJO_REPO_URL not set; skipping vault sync")
        return False
    os.makedirs(VAULT, exist_ok=True)
    if os.path.isdir(os.path.join(VAULT, ".git")):
        r = git(["pull", "--ff-only"], VAULT)
    else:
        r = git(["clone", "--depth", "1", FORGEJO_REPO_URL, VAULT], os.path.dirname(VAULT))
    if r.returncode != 0:
        LOG.warning("git mirror sync failed: %s", r.stderr.strip()[:300])
        return False
    return True


def run_loop_a(conn):
    if not ensure_mirror():
        return
    files = sorted(glob.glob(os.path.join(DAILY_DIR, "*.md")))
    for path in files:
        date = os.path.splitext(os.path.basename(path))[0]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            continue
        try:
            parse_note(conn, path, date)
        except OSError:
            LOG.exception("cannot read %s", path)
    conn.commit()
    LOG.info("vault sync done: %d notes scanned", len(files))


def renpho_measurements():
    client = RenphoClient(os.environ["RENPHO_EMAIL"], os.environ["RENPHO_PASSWORD"])
    cached = load_json(TOKEN_PATH)
    if cached:
        client.token = cached.get("token")
        client.user_id = cached.get("user_id")
    try:
        measurements = client.get_all_measurements()
    except Exception:
        client = RenphoClient(os.environ["RENPHO_EMAIL"], os.environ["RENPHO_PASSWORD"])
        client.login()
        measurements = client.get_all_measurements()
    save_json(TOKEN_PATH, {"token": client.token, "user_id": client.user_id})
    return measurements


def sync_measurements(conn, measurements):
    count = 0
    for m in measurements:
        ts = m.get("timeStamp")
        if not ts:
            continue
        measured_at = dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S")
        cur = conn.execute(
            """INSERT INTO body_measurements (measured_at, weight_kg, bodyfat_pct, muscle_pct, water_pct, bone_kg, visfat, bmr_kcal, heart_rate_bpm)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(measured_at) DO NOTHING""",
            (measured_at, m.get("weight"), m.get("bodyfat"), m.get("muscle"), m.get("water"),
             m.get("bone"), m.get("visfat"), m.get("bmr"), m.get("heartRate")),
        )
        count += cur.rowcount
    return count


def update_goal(conn):
    row = conn.execute(
        "SELECT bmr_kcal FROM body_measurements WHERE bmr_kcal IS NOT NULL ORDER BY measured_at DESC LIMIT 1"
    ).fetchone()
    if not row:
        return
    kcal = round(row[0] * ACTIVITY_FACTOR)
    today = dt.date.today().isoformat()
    exists = conn.execute(
        "SELECT 1 FROM goals WHERE source='bmr' AND date=? AND kcal=?", (today, kcal)
    ).fetchone()
    if not exists:
        conn.execute("INSERT INTO goals (date, kcal, source) VALUES (?,?,'bmr')", (today, kcal))
        LOG.info("bmr goal updated: %d kcal", kcal)


def run_loop_b(conn):
    try:
        measurements = renpho_measurements()
    except Exception:
        LOG.exception("renpho poll failed")
        return
    new = sync_measurements(conn, measurements)
    update_goal(conn)
    conn.commit()
    LOG.info("renpho sync done: %d new measurements", new)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    conn = init_db()
    last_a = last_b = 0.0
    while True:
        try:
            with open(HEARTBEAT, "w"):
                pass
            now = time.time()
            if now - last_a >= LOOP_A_SECONDS:
                run_loop_a(conn)
                last_a = now
            if now - last_b >= LOOP_B_SECONDS:
                run_loop_b(conn)
                last_b = now
        except KeyboardInterrupt:
            return 0
        except Exception:
            LOG.exception("loop iteration failed")
        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
```

Checks:
- `python3 -m py_compile food-tracker/main.py`
- `docker build -t food-tracker:test ./food-tracker`

## 4. feat: add food-tracker compose service

Intent: register the service in the stack (`./run.sh up` starts it) and document its env vars, so first boot after `run.sh up` works with a filled `.env`. Same shape as `media-watcher`/`subtitle-cron` (build dir, container_name, deploy memory limit, restart).

`+` in `docker-compose.yml`, inserted between the `subtitle-cron` block (ends line 583, `- TZ=${TZ}`) and the `# ─── Actual Budget` comment (line 585):

```yaml
  # ─────────────────────────────────────────────
  # food-tracker — Obsidian vault -> SQLite + Renpho weight sync
  # Syncs #food entries from the notes vault into SQLite (./food-data)
  # and polls the Renpho cloud every 6h for body composition + BMR.
  food-tracker:
    build: ./food-tracker
    container_name: food-tracker
    restart: unless-stopped
    environment:
      - TZ=${TZ}
      - FORGEJO_REPO_URL=https://kaung:${FORGEJO_TOKEN}@${FORGEJO_HOST:-home.tailc65fb0.ts.net}/kaung/Kaung-Notes-Vault.git
      - RENPHO_EMAIL=${RENPHO_EMAIL}
      - RENPHO_PASSWORD=${RENPHO_PASSWORD}
      - ACTIVITY_FACTOR=${ACTIVITY_FACTOR:-1.5}
    volumes:
      - ./food-data:/data
    deploy:
      resources:
        limits:
          memory: 128m
    healthcheck:
      test: ["CMD", "python", "-c", "import os,time; m=os.path.getmtime('/data/heartbeat'); exit(0 if time.time()-m<1800 else 1)"]
      interval: 5m
      timeout: 10s
      retries: 3
```

`+` in `.env.example`, after the media-watcher block (line 50):

```
# --- Food tracker --------------------------------------------------------
# Forgejo token: Forgejo -> Settings -> Applications -> Generate Token (read access)
FORGEJO_TOKEN=your-forgejo-token-here
# Tailnet hostname of the Forgejo server (vault remote: kaung@home.tailc65fb0.ts.net)
FORGEJO_HOST=home.tailc65fb0.ts.net
# Renpho Health account — the scale syncs via the mobile app, tracker polls the cloud
RENPHO_EMAIL=your-renpho-email-here
RENPHO_PASSWORD=your-renpho-password-here
# Daily kcal goal = latest scale BMR x this factor
ACTIVITY_FACTOR=1.5
```

Checks: `FORGEJO_TOKEN=t RENPHO_EMAIL=e RENPHO_PASSWORD=p docker compose config -q`

## 5. docs: add food tracker to services reference

Intent: the stack reference documents the new custom service, like media-watcher/subtitle-cron.

`+` in `docs/services.md`, in the Custom Services table (after line 51):

```
| food-tracker | — | Syncs #food entries from the Obsidian vault into SQLite; polls Renpho for weight/body composition every 6h |
```

Checks: `command grep -c "food-tracker" docs/services.md` prints `1`.

---

## Manual follow-ups (outside this repo — not commits)

1. **Vault** (`/home/kaung/vault`, separate git repo): install `obsidian-food-tracker` from Community Plugins; create `Foods/` nutrient directory; import staple foods (search or barcode scan); add `## Food Log` + `#food [[Example Product]] 100g` to `Templates/Daily Notes Template.md`. Product notes get frontmatter keys `calories`/`fats`/`protein`/`carbs` (per 100g, optional `serving_size`, `nutrition_per`) — the script reads these.
2. **`.env`** (gitignored, local): fill `FORGEJO_TOKEN` (Forgejo → Settings → Applications), `RENPHO_EMAIL`, `RENPHO_PASSWORD`.
3. **Deploy:** `./run.sh up`; verify with `docker compose logs food-tracker` and `sqlite3 food-data/food.db 'SELECT * FROM daily_totals;'`.
4. Note: the container must reach the tailnet hostname `home.tailc65fb0.ts.net` (tailscale MagicDNS); if it can't, set `FORGEJO_HOST` to the tailnet IP in `.env`.
