# Import Existing Media into Sonarr & Radarr — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add all existing on-disk TV shows and movies to Sonarr and Radarr as unmonitored entries so Bazarr can manage subtitles for the full library.

**Architecture:** Two scripts handle pre-flight work (Phase 0), then the user runs the built-in UI importer (Phase 1), then a second script (Phase 2) handles hard-to-match content via the Sonarr/Radarr APIs, and finally rescans are triggered across the stack.

**Tech Stack:** Python 3, `requests`, Sonarr API v3, Radarr API v3, Jellyfin API

---

## Environment

```
Sonarr:    http://localhost:8989  API key: ba1c87c1d3f84eb1a096095279dabed0
Radarr:    http://localhost:7878  API key: 9f1eed6ac4bc4f0eb9654c8b3d12e14d
Jellyfin:  http://localhost:8096  API key: e156612465294e5380221b28c2023f40

Host media paths:      /mnt/media/TV   /mnt/media/Movies
Container media paths: /data/TV        /data/Movies
```

---

## Chunk 1: Phase 0 — Pre-flight

Two pre-flight tasks before the UI importer runs:
1. Move the misplaced Money Heist folder from Movies → TV
2. Organize all loose video files in the Movies root into per-movie subfolders

**Files:**
- Create: `/home/kaung/preflight.py`

---

### Task 1: Move Money Heist from Movies to TV

- [ ] **Step 1: Verify the source folder exists**

```bash
ls /mnt/media/Movies/ | grep -i heist
```

Expected output: `La.Casa.De.Papel.(Money.Heist).S04.SweSub.1080p.x264-Justiso`

- [ ] **Step 2: Move it to the TV folder**

```bash
mv "/mnt/media/Movies/La.Casa.De.Papel.(Money.Heist).S04.SweSub.1080p.x264-Justiso" \
   "/mnt/media/TV/La.Casa.De.Papel.Money.Heist.S04"
```

- [ ] **Step 3: Confirm**

```bash
ls /mnt/media/TV/ | grep -i heist
ls /mnt/media/Movies/ | grep -i heist
```

Expected: appears in TV, gone from Movies.

---

### Task 2: Write and run the loose-file organizer script

These files sit directly in `/mnt/media/Movies/` with no subfolder. Radarr's importer requires one folder per movie.

**Exact loose files to handle:**

| Filename | Target folder |
|----------|---------------|
| `Frankenstein.2025.1080p.WEBRip.10Bit.DDP5.1.x265-NeoNoir.mkv` | `Frankenstein (2025)` |
| `Hardcore! - Hardcore Henry (2015) AC3 5.1 ITA.ENG 1080p H265 sub ita.eng Sp33dy94-MIRCrew.mkv` | `Hardcore Henry (2015)` |
| `Hot Rod 2007 1080p BluRay HEVC x265 5.1 BONE.mkv` | `Hot Rod (2007)` |
| `How.to.Train.Your.Dragon.2025.1080p.WEB-DL.DDP5.1.x265-NeoNoir.mkv` | `How to Train Your Dragon (2025)` |
| `[infanf] Weathering with You (Tenki no Ko) [1080p][x265].mkv` | `Weathering with You (2019)` |
| `[Judas] Jujutsu Kaisen - Movie 01 - Jujutsu Kaisen 0 [BD 1080p][HEVC x265 10bit][Dual-Audio][Multi-Subs].mkv` | `Jujutsu Kaisen 0 (2021)` |
| `Marty Supreme 2025 1080p WEB-DL HEVC x265 5.1 BONE.mkv` | `Marty Supreme (2025)` |
| `Memories.of.Murder.2003.1080p.BluRay.10bit.HEVC.6CH-MkvCage.ws.mkv` | `Memories of Murder (2003)` |
| `Monster 2023 1080p Japanese WEB-DL HEVC x265 5.1 BONE.mkv` | `Monster (2023)` |
| `Now.You.See.Me.2.2016.1080p.BluRay.6CH.ShAaNiG.mkv` | `Now You See Me 2 (2016)` |
| `Spirited Away (2001) [1080p x265 HEVC 10bit BluRay Dual Audio AAC 5.1] [Prof].mkv` | `Spirited Away (2001)` |
| `The.Godfather.1972.The.Coppola.Restoration.Bluray.1080p.AV1.OPUS.5.1-UH.mkv` | `The Godfather (1972)` |
| `Wall to Wall 2025 1080p (DUAL) WEB-DL HEVC x265 5.1 BONE.mkv` | `Wall to Wall (2025)` |

- [ ] **Step 1: Write `/home/kaung/preflight.py`**

```python
#!/usr/bin/env python3
"""
Phase 0b: Move loose movie files in /mnt/media/Movies root into per-movie subfolders.
Each entry: (source_filename, target_folder_name)
Also moves any matching .en.srt sidecar.
"""
import os
import shutil

MOVIES_ROOT = "/mnt/media/Movies"

# (source filename without path, target folder name)
LOOSE_FILES = [
    ("Frankenstein.2025.1080p.WEBRip.10Bit.DDP5.1.x265-NeoNoir.mkv",
     "Frankenstein (2025)"),
    ("Hardcore! - Hardcore Henry (2015) AC3 5.1 ITA.ENG 1080p H265 sub ita.eng Sp33dy94-MIRCrew.mkv",
     "Hardcore Henry (2015)"),
    ("Hot Rod 2007 1080p BluRay HEVC x265 5.1 BONE.mkv",
     "Hot Rod (2007)"),
    ("How.to.Train.Your.Dragon.2025.1080p.WEB-DL.DDP5.1.x265-NeoNoir.mkv",
     "How to Train Your Dragon (2025)"),
    ("[infanf] Weathering with You (Tenki no Ko) [1080p][x265].mkv",
     "Weathering with You (2019)"),
    ("[Judas] Jujutsu Kaisen - Movie 01 - Jujutsu Kaisen 0 [BD 1080p][HEVC x265 10bit][Dual-Audio][Multi-Subs].mkv",
     "Jujutsu Kaisen 0 (2021)"),
    ("Marty Supreme 2025 1080p WEB-DL HEVC x265 5.1 BONE.mkv",
     "Marty Supreme (2025)"),
    ("Memories.of.Murder.2003.1080p.BluRay.10bit.HEVC.6CH-MkvCage.ws.mkv",
     "Memories of Murder (2003)"),
    ("Monster 2023 1080p Japanese WEB-DL HEVC x265 5.1 BONE.mkv",
     "Monster (2023)"),
    ("Now.You.See.Me.2.2016.1080p.BluRay.6CH.ShAaNiG.mkv",
     "Now You See Me 2 (2016)"),
    ("Spirited Away (2001) [1080p x265 HEVC 10bit BluRay Dual Audio AAC 5.1] [Prof].mkv",
     "Spirited Away (2001)"),
    ("The.Godfather.1972.The.Coppola.Restoration.Bluray.1080p.AV1.OPUS.5.1-UH.mkv",
     "The Godfather (1972)"),
    ("Wall to Wall 2025 1080p (DUAL) WEB-DL HEVC x265 5.1 BONE.mkv",
     "Wall to Wall (2025)"),
]

def move_file(src, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    shutil.move(src, dst)
    print(f"  Moved: {os.path.basename(src)} -> {os.path.basename(dst_dir)}/")

def main():
    for filename, folder_name in LOOSE_FILES:
        src_video = os.path.join(MOVIES_ROOT, filename)
        dst_dir   = os.path.join(MOVIES_ROOT, folder_name)

        if not os.path.exists(src_video):
            print(f"SKIP (not found): {filename}")
            continue

        stem = os.path.splitext(filename)[0]
        move_file(src_video, dst_dir)

        # Move matching .en.srt sidecar if present
        srt = os.path.join(MOVIES_ROOT, stem + ".en.srt")
        if os.path.exists(srt):
            move_file(srt, dst_dir)

    print("Done.")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

```bash
python3 /home/kaung/preflight.py
```

Expected: lines like `Moved: Frankenstein.2025...mkv -> Frankenstein (2025)/` for each file.

- [ ] **Step 3: Verify no loose video files remain in root**

```bash
find /mnt/media/Movies -maxdepth 1 \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \)
```

Expected: empty output (no files, only directories).

- [ ] **Step 4: Verify target folders were created**

```bash
ls /mnt/media/Movies/ | grep -E "Frankenstein|Hot Rod|Spirited|Godfather \(1972\)|Memories|Monster \(2023\)|Marty|Wall to Wall|Weathering|Jujutsu Kaisen 0|Now You See Me|How to Train|Hardcore Henry"
```

Expected: all 13 folder names appear.

---

## Chunk 2: Phase 2 — API Import Script

Script `/home/kaung/import_to_arr.py` handles content the built-in UI importer cannot auto-match.

**Files:**
- Create: `/home/kaung/import_to_arr.py`

---

### Task 3: Write the import_to_arr.py script

- [ ] **Step 1: Write `/home/kaung/import_to_arr.py`**

```python
#!/usr/bin/env python3
"""
Phase 2: Add hard-to-match TV shows and movies to Sonarr/Radarr via API.
Skips entries already present. Triggers per-entry rescan after each add.
"""
import sys
import time
import requests

SONARR_URL = "http://localhost:8989"
SONARR_KEY = "ba1c87c1d3f84eb1a096095279dabed0"
RADARR_URL = "http://localhost:7878"
RADARR_KEY = "9f1eed6ac4bc4f0eb9654c8b3d12e14d"

# --- Sonarr helpers ---

def sonarr_get(path, params=None):
    r = requests.get(f"{SONARR_URL}/api/v3{path}",
                     headers={"X-Api-Key": SONARR_KEY}, params=params)
    r.raise_for_status()
    return r.json()

def sonarr_post(path, body):
    r = requests.post(f"{SONARR_URL}/api/v3{path}",
                      headers={"X-Api-Key": SONARR_KEY}, json=body)
    return r

def get_sonarr_quality_profile_id():
    profiles = sonarr_get("/qualityprofile")
    # Prefer "Any" profile, fall back to first
    for p in profiles:
        if p["name"].lower() == "any":
            return p["id"]
    return profiles[0]["id"]

def get_sonarr_root_folder():
    folders = sonarr_get("/rootfolder")
    return folders[0]["path"]  # /data/TV

def add_series(folder_path, search_term, year):
    """Look up series, add as unmonitored. Returns (ok, message)."""
    results = sonarr_get("/series/lookup", {"term": search_term})
    if not results:
        return False, f"SKIP: no lookup results for '{search_term}'"

    # Pick match by year, or first result
    match = None
    if year:
        for r in results:
            if r.get("year") == year:
                match = r
                break
    if match is None:
        match = results[0]

    title = match["title"]
    tvdb_id = match["tvdbId"]

    # Check if already in Sonarr
    existing = sonarr_get("/series")
    for s in existing:
        if s.get("tvdbId") == tvdb_id:
            return False, f"SKIP: '{title}' already in Sonarr"

    quality_profile_id = get_sonarr_quality_profile_id()
    root_folder = get_sonarr_root_folder()

    body = {
        "title": title,
        "tvdbId": tvdb_id,
        "qualityProfileId": quality_profile_id,
        "rootFolderPath": root_folder,
        "path": folder_path,
        "monitored": False,
        "seasonFolder": True,
        "addOptions": {
            "searchForMissingEpisodes": False,
            "ignoreEpisodesWithFiles": True,
            "ignoreEpisodesWithoutFiles": True,
        },
        "seasons": [
            dict(s, monitored=False)
            for s in match.get("seasons", [])
        ],
    }

    resp = sonarr_post("/series", body)
    if resp.status_code == 201:
        series_id = resp.json()["id"]
        sonarr_post("/command", {"name": "RescanSeries", "seriesId": series_id})
        return True, f"ADDED: '{title}' (tvdbId={tvdb_id})"
    elif resp.status_code == 400:
        return False, f"SKIP: '{title}' already exists (400)"
    else:
        return False, f"ERROR {resp.status_code}: {resp.text[:200]}"

# --- Radarr helpers ---

def radarr_get(path, params=None):
    r = requests.get(f"{RADARR_URL}/api/v3{path}",
                     headers={"X-Api-Key": RADARR_KEY}, params=params)
    r.raise_for_status()
    return r.json()

def radarr_post(path, body):
    r = requests.post(f"{RADARR_URL}/api/v3{path}",
                      headers={"X-Api-Key": RADARR_KEY}, json=body)
    return r

def get_radarr_quality_profile_id():
    profiles = radarr_get("/qualityprofile")
    for p in profiles:
        if p["name"].lower() == "any":
            return p["id"]
    return profiles[0]["id"]

def get_radarr_root_folder():
    folders = radarr_get("/rootfolder")
    return folders[0]["path"]  # /data/Movies

def add_movie(folder_path, search_term, year):
    """Look up movie, add as unmonitored. Returns (ok, message)."""
    results = radarr_get("/movie/lookup", {"term": search_term})
    if not results:
        return False, f"SKIP: no lookup results for '{search_term}'"

    match = None
    if year:
        for r in results:
            if r.get("year") == year:
                match = r
                break
    if match is None:
        match = results[0]

    title = match["title"]
    tmdb_id = match["tmdbId"]

    existing = radarr_get("/movie")
    for m in existing:
        if m.get("tmdbId") == tmdb_id:
            return False, f"SKIP: '{title}' already in Radarr"

    quality_profile_id = get_radarr_quality_profile_id()
    root_folder = get_radarr_root_folder()

    body = {
        "title": title,
        "tmdbId": tmdb_id,
        "qualityProfileId": quality_profile_id,
        "rootFolderPath": root_folder,
        "path": folder_path,
        "monitored": False,
        "addOptions": {
            "searchForMovie": False,
        },
    }

    resp = radarr_post("/movie", body)
    if resp.status_code == 201:
        movie_id = resp.json()["id"]
        radarr_post("/command", {"name": "RescanMovie", "movieId": movie_id})
        return True, f"ADDED: '{title}' (tmdbId={tmdb_id})"
    elif resp.status_code == 400:
        return False, f"SKIP: '{title}' already exists (400)"
    else:
        return False, f"ERROR {resp.status_code}: {resp.text[:200]}"

# --- Entry list ---
# (container_folder_path, search_term, year_int_or_None, "tv"/"movie")

TV_ROOT = "/data/TV"
MOVIE_ROOT = "/data/Movies"

ENTRIES = [
    # TV
    (f"{TV_ROOT}/[Judas] Hunter x Hunter (2011) (Complete Series + Movies) [BD 1080p][HEVC x265 10bit][Dual-Audio][Eng-Subs]",
     "Hunter x Hunter", 2011, "tv"),
    (f"{TV_ROOT}/[Anime Time] Dandadan (Season 01) [Dual Audio][1080p][HEVC 10bit x265][AAC][Multi Sub]",
     "Dandadan", 2024, "tv"),
    (f"{TV_ROOT}/[Anime Time] Death Parade + Special [BD][Dual Audio][1080p][HEVC 10bit x265][AAC][Eng Sub]",
     "Death Parade", 2015, "tv"),
    (f"{TV_ROOT}/[Anime Time] Monster (2004 - 2005) [Dual Audio] [DVD][480p][HEVC 10bit x265][AAC][Eng Sub]",
     "Monster", 2004, "tv"),
    (f"{TV_ROOT}/Gyakkyou Burai Kaiji Ultimate Survivor",
     "Kaiji", 2007, "tv"),
    (f"{TV_ROOT}/Gyakkyou Burai Kaiji Hakairoku-hen",
     "Kaiji Against All Rules", 2011, "tv"),
    (f"{TV_ROOT}/[Saizen-HnG]_Ashita_no_Joe_01-79_[Complete_DVD]",
     "Ashita no Joe", 1970, "tv"),
    (f"{TV_ROOT}/Legend.of.the.Galactic.Heroes.1988.S01.REPACK.720p.Blu-ray.Opus2.0.x264-koala",
     "Legend of the Galactic Heroes", 1988, "tv"),
    (f"{TV_ROOT}/[Sokudo] Boku no Hero Academia [1080p BD][AV1][dual audio]",
     "My Hero Academia", 2016, "tv"),
    (f"{TV_ROOT}/kijin gentosho",
     "Kijin Gentosho", None, "tv"),
    (f"{TV_ROOT}/[NewbSubs] Attack on Titan~Shingeki no Kyojin Series (1080p Blu-ray x265 Dual Audio)",
     "Attack on Titan", 2013, "tv"),
    (f"{TV_ROOT}/[Trix] Spy x Family S01+02+Movie (BD 1080p AV1) [Triple Audio] [Multi Subs]",
     "Spy x Family", 2022, "tv"),
    (f"{TV_ROOT}/I.Know.What.You.Did.Last.Summer.S01.COMPLETE.720p.AMZN.WEBRip.x264-GalaxyTV[TGx]",
     "I Know What You Did Last Summer", 2021, "tv"),
    (f"{TV_ROOT}/La.Casa.De.Papel.Money.Heist.S04",
     "Money Heist", 2017, "tv"),
    (f"{TV_ROOT}/Dungeon Meshi S01 1080p Dual Audio WEBRip DD+ x265-EMBER",
     "Delicious in Dungeon", 2024, "tv"),
    (f"{TV_ROOT}/[Judas] Mob Psycho 100 (Seasons 1-2 + OVA + Specials) [BD 1080p][HEVC x265 10bit][Dual-Audio][Multi-Subs]",
     "Mob Psycho 100", 2016, "tv"),
    (f"{TV_ROOT}/[Judas] Overlord (Seasons 1-3 + Movies + OVA + Specials) [BD 1080p][HEVC x265 10bit][Dual-Audio][Eng-Subs]",
     "Overlord", 2015, "tv"),
    (f"{TV_ROOT}/Tengen Toppa Gurren Lagann",
     "Gurren Lagann", 2007, "tv"),
    # Additional TV shows likely missed by UI importer
    (f"{TV_ROOT}/Alice.in.Borderland.S03.1080p.NF.WEB-DL.AAC5.1.H.265-REL1VIN",
     "Alice in Borderland", 2020, "tv"),
    (f"{TV_ROOT}/BEEF (2023) Season 1 S01 (1080p NF WEB-DL x265 HEVC 10bit EAC3 5.1 Silence)",
     "Beef", 2023, "tv"),
    (f"{TV_ROOT}/Better.Call.Saul.S01-S06.COMPLETE.1080p.WEBRip.x264.EAC3-SURGE",
     "Better Call Saul", 2015, "tv"),
    (f"{TV_ROOT}/Black.Mirror.S07.1080p.WEBRip.10bit.DDP5.1.x265-HODL",
     "Black Mirror", 2011, "tv"),
    (f"{TV_ROOT}/Breaking.Bad.Complete.S01-S05.1080p.10bit.BluRay.x265.HEVC.6CH-MRN",
     "Breaking Bad", 2008, "tv"),
    (f"{TV_ROOT}/Brooklyn Nine Nine 2013 Seasons 1 to 8 Complete 1080p BluRay x264 [i_c]",
     "Brooklyn Nine-Nine", 2013, "tv"),
    (f"{TV_ROOT}/Invincible 2021 Seasons 1 to 3 Complete 1080p WEB x264 [i_c]",
     "Invincible", 2021, "tv"),
    (f"{TV_ROOT}/Its Always Sunny in Philadelphia",
     "It's Always Sunny in Philadelphia", 2005, "tv"),
    (f"{TV_ROOT}/Jujutsu Kaisen S03",
     "Jujutsu Kaisen", 2020, "tv"),
    (f"{TV_ROOT}/[Judas] Jujutsu Kaisen (Season 1) [1080p][HEVC x265 10bit][Multi-Subs]",
     "Jujutsu Kaisen", 2020, "tv"),
    (f"{TV_ROOT}/Law & Order",
     "Law & Order", 1990, "tv"),
    (f"{TV_ROOT}/Made in Abyss",
     "Made in Abyss", 2017, "tv"),
    (f"{TV_ROOT}/[Judas] Mob Psycho 100 (Season 3) [1080p][HEVC x265 10bit][Multi-Subs]",
     "Mob Psycho 100", 2016, "tv"),
    (f"{TV_ROOT}/[Judas] Overlord (Season 4) [1080p][HEVC x265 10bit][Dual-Audio][Multi-Subs]",
     "Overlord", 2015, "tv"),
    (f"{TV_ROOT}/The.Boondocks.S03.1080p.AMZN.WEB-DL.DDP5.1.H.264-ViETNAM",
     "The Boondocks", 2005, "tv"),
    (f"{TV_ROOT}/The.Simpsons.S04.REPACK.1080p.WEBRip.x265-KONTRAST",
     "The Simpsons", 1989, "tv"),
    (f"{TV_ROOT}/The Sopranos",
     "The Sopranos", 1999, "tv"),
    # Movies
    (f"{MOVIE_ROOT}/[JuicySubs] Tokyo Godfathers",
     "Tokyo Godfathers", 2003, "movie"),
    (f"{MOVIE_ROOT}/Weathering with You (2019)",
     "Weathering with You", 2019, "movie"),
    (f"{MOVIE_ROOT}/Jujutsu Kaisen 0 (2021)",
     "Jujutsu Kaisen 0", 2021, "movie"),
    (f"{MOVIE_ROOT}/Akira Kurosawa - Ikiru.1952.JPN.Criterion.BluRay.1080p.FLAC.1.0.HEVC-DDR[EtHD]",
     "Ikiru", 1952, "movie"),
    (f"{MOVIE_ROOT}/round-about-midnight-281999-29-dvdrip",
     "Round About Midnight", 1999, "movie"),
    (f"{MOVIE_ROOT}/Lola.Montes.1955.(Max.Ophuls).1080p.BRRip.x264-Classics",
     "Lola Montès", 1955, "movie"),
    (f"{MOVIE_ROOT}/Spirited Away (2001)",
     "Spirited Away", 2001, "movie"),
    (f"{MOVIE_ROOT}/The Godfather (1972)",
     "The Godfather", 1972, "movie"),
    (f"{MOVIE_ROOT}/Memories of Murder (2003)",
     "Memories of Murder", 2003, "movie"),
]

def main():
    added = 0
    skipped = 0
    errors = 0

    for folder, term, year, kind in ENTRIES:
        print(f"\n[{kind.upper()}] {term} ({year or '?'}) ...")
        try:
            if kind == "tv":
                ok, msg = add_series(folder, term, year)
            else:
                ok, msg = add_movie(folder, term, year)
            print(f"  {msg}")
            if ok:
                added += 1
                time.sleep(1)  # be gentle with the APIs
            elif msg.startswith("SKIP"):
                skipped += 1
            else:
                errors += 1
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            errors += 1

    print(f"\n=== Done: {added} added, {skipped} skipped, {errors} errors ===")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the script is syntactically valid**

```bash
python3 -m py_compile /home/kaung/import_to_arr.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 3: Do a dry-run lookup test (Sonarr)**

```bash
python3 -c "
import requests
r = requests.get('http://localhost:8989/api/v3/series/lookup',
    headers={'X-Api-Key': 'ba1c87c1d3f84eb1a096095279dabed0'},
    params={'term': 'Hunter x Hunter'})
results = r.json()
print(f'Got {len(results)} results')
for x in results[:3]:
    print(f'  {x[\"title\"]} ({x.get(\"year\")}) tvdbId={x[\"tvdbId\"]}')
"
```

Expected: at least 1 result including "Hunter x Hunter (2011)"

- [ ] **Step 4: Do a dry-run lookup test (Radarr)**

```bash
python3 -c "
import requests
r = requests.get('http://localhost:7878/api/v3/movie/lookup',
    headers={'X-Api-Key': '9f1eed6ac4bc4f0eb9654c8b3d12e14d'},
    params={'term': 'Tokyo Godfathers'})
results = r.json()
print(f'Got {len(results)} results')
for x in results[:3]:
    print(f'  {x[\"title\"]} ({x.get(\"year\")}) tmdbId={x[\"tmdbId\"]}')
"
```

Expected: at least 1 result including "Tokyo Godfathers (2003)"

---

## Chunk 3: Phase 1 (UI) + Phase 3 (Rescans)

### Task 4: Run Sonarr built-in importer (UI step)

This is a manual step done in the browser before running the API script. The UI importer handles cleanly-named content that the API script doesn't need to touch.

- [ ] **Step 1: Open Sonarr importer**

Navigate to: `http://localhost:8989`  
Go to: **Series → Import**  
Set root folder to: `/data/TV`

- [ ] **Step 2: Confirm and add matches**

Sonarr scans all subfolders and presents guessed matches. For each:
- Verify the title match is correct
- Set Quality Profile: **Any**
- Set Monitor: **None** (not monitored)
- Confirm

Click **Import X Series** to bulk-add all confirmed matches.

- [ ] **Step 3: Note any unmatched folders**

If Sonarr shows "No match found" for any folder, note those — the API script will handle them. Typical unmatched: anything with `[Judas]`, `[Anime Time]`, `[Sokudo]`, `[NewbSubs]`, `[Trix]`, `[Saizen-HnG]` prefixes.

---

### Task 5: Run Radarr built-in importer (UI step)

- [ ] **Step 1: Open Radarr importer**

Navigate to: `http://localhost:7878`  
Go to: **Movies → Import Existing Movies**  
Set root folder to: `/data/Movies`

- [ ] **Step 2: Confirm and add matches**

Same process as Sonarr. Set Quality Profile: **Any**, Monitor: **No**.

- [ ] **Step 3: Note any unmatched folders**

Typical unmatched: `[JuicySubs]`, `[infanf]` (already moved to `Weathering with You (2019)`), `round-about-midnight`, `Lola.Montes`, `Akira Kurosawa - Ikiru`.

---

### Task 6: Run the API import script

- [ ] **Step 1: Run the script**

```bash
python3 /home/kaung/import_to_arr.py 2>&1 | tee /home/kaung/import_to_arr.log
```

- [ ] **Step 2: Check results**

```bash
grep -E "ADDED|ERROR" /home/kaung/import_to_arr.log
```

Expected: mostly `ADDED:` lines. `SKIP: already in Sonarr/Radarr` lines are fine (means UI importer got them). Only `ERROR` lines need investigation.

- [ ] **Step 3: Fix any ERROR lines**

For each error, check the log message. Common causes:
- Wrong search term → edit the ENTRIES list in the script and re-run just that entry
- API timeout → re-run the full script (it skips already-added entries)

---

### Task 7: Post-import rescans

- [ ] **Step 1: Rescan all Sonarr**

```bash
curl -s -X POST "http://localhost:8989/api/v3/command" \
  -H "X-Api-Key: ba1c87c1d3f84eb1a096095279dabed0" \
  -H "Content-Type: application/json" \
  -d '{"name":"RescanSeries"}' | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status', d))"
```

Expected: `queued` or `started`

- [ ] **Step 2: Rescan all Radarr**

```bash
curl -s -X POST "http://localhost:7878/api/v3/command" \
  -H "X-Api-Key: 9f1eed6ac4bc4f0eb9654c8b3d12e14d" \
  -H "Content-Type: application/json" \
  -d '{"name":"RescanMovie"}' | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status', d))"
```

Expected: `queued` or `started`

- [ ] **Step 3: Refresh Jellyfin library**

```bash
curl -s -X POST "http://localhost:8096/Library/Refresh" \
  -H "X-Emby-Token: e156612465294e5380221b28c2023f40"
echo "Jellyfin refresh triggered"
```

- [ ] **Step 4: Verify Sonarr series count increased**

```bash
curl -s "http://localhost:8989/api/v3/series" \
  -H "X-Api-Key: ba1c87c1d3f84eb1a096095279dabed0" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Sonarr series: {len(d)}')"
```

Expected: significantly more than the original 7 (should be ~35+)

- [ ] **Step 5: Verify Radarr movie count increased**

```bash
curl -s "http://localhost:7878/api/v3/movie" \
  -H "X-Api-Key: 9f1eed6ac4bc4f0eb9654c8b3d12e14d" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Radarr movies: {len(d)}')"
```

Expected: significantly more than the original 4 (should be ~70+)

---

## Execution Order

1. **Task 1** — Move Money Heist (bash, 1 min)
2. **Task 2** — Run `preflight.py` to organize loose files (5 min)
3. **Task 4** — Sonarr UI importer (manual, ~10 min)
4. **Task 5** — Radarr UI importer (manual, ~10 min)
5. **Task 3** — Write and run `import_to_arr.py` for hard-to-match entries (10 min)
6. **Task 6** — Run the API script
7. **Task 7** — Post-import rescans
