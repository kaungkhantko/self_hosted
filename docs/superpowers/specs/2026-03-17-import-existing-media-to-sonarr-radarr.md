# Import Existing Media into Sonarr & Radarr

**Date**: 2026-03-17  
**Status**: Approved

## Goal

Add all existing on-disk TV shows (~40 folders) and movies (~80 folders) into Sonarr and Radarr respectively, as **unmonitored** entries with existing files linked. This makes Bazarr aware of all content for subtitle management.

## Settings for All Imports

| Setting | Value |
|---------|-------|
| Quality Profile | Any |
| Monitored | false |
| Search on add | false |
| Search for missing episodes | false |
| Root folder (TV) | `/data/TV` |
| Root folder (Movies) | `/data/Movies` |

---

## Phase 0 — Pre-flight

### 0a — Move Money Heist to TV

`/mnt/media/Movies/La.Casa.De.Papel.(Money.Heist).S04.*` is misplaced in the Movies folder.

**Action**: Move to `/mnt/media/TV/La.Casa.De.Papel.Money.Heist.S04/` before running any import.

### 0b — Organize loose movie files into subfolders

Several MKV/MP4 files sit directly in `/mnt/media/Movies/` without a subfolder. Radarr's importer requires each movie to be in its own folder.

**Loose files to organize:**
- `Hot Rod 2007 ...mkv`
- `Frankenstein.2025...mkv`
- `Hardcore Henry...mkv`
- `Marty Supreme 2025...mkv`
- `Memories.of.Murder...mkv`
- `Monster 2023...mkv`
- `Now.You.See.Me.2...mkv`
- `Spirited Away...mkv`
- `Wall to Wall 2025...mkv`
- `How.to.Train.Your.Dragon.2025...mkv`

**Action**: For each loose file, derive a clean folder name by stripping everything after the year (e.g. `Hot Rod 2007 1080p BluRay HEVC x265 5.1 BONE.mkv` → `Hot Rod (2007)`). Create the folder and move both the video file and any matching `.en.srt` sidecar into it.

After Phase 0, these folders are treated as normal folders by Phase 1's built-in importer. They do **not** appear in the Phase 2 hard-to-match table.

---

## Phase 1 — Built-in Importer (UI)

Use the Sonarr and Radarr built-in import pages to bulk-add cleanly-named content.

- **Sonarr**: `http://localhost:8989` → Series → Import → point at `/data/TV`
- **Radarr**: `http://localhost:7878` → Movies → Import Existing Movies → point at `/data/Movies`

The importer scans subfolders, guesses title/year via TVDB/TMDB, presents matches for confirmation, then adds with existing files already linked.

---

## Phase 2 — API Script for Hard-to-Match Content

Script: `/home/kaung/import_to_arr.py`

Handles folders the built-in importer cannot auto-match due to non-standard naming (anime tags, bracket prefixes, etc.).

### Script behavior
1. Accept a list of `(folder_path, search_term, year, type)` tuples — type is `tv` or `movie`
2. Call `GET /api/v3/series/lookup?term=<search_term>` (Sonarr) or `GET /api/v3/movie/lookup?term=<search_term>` (Radarr)
3. Pick the first result whose year matches (exact match). If no year is specified, pick the first result. If zero results are returned, log `SKIP: no match for <search_term>` and continue to the next entry.
4. `POST /api/v3/series` or `POST /api/v3/movie` with monitored=false, no search on add. If the API returns 400 (already exists), log `SKIP: already in Sonarr/Radarr` and continue.
5. Trigger a per-entry rescan using the ID returned from step 4:
   - Sonarr: `POST /api/v3/command {"name":"RescanSeries","seriesId":<id>}`
   - Radarr: `POST /api/v3/command {"name":"RescanMovie","movieId":<id>}`

### Known hard-to-match entries

#### TV (Sonarr)
| Folder | Search term | Year | Notes |
|--------|-------------|------|-------|
| `[Judas] Hunter x Hunter (2011)` | Hunter x Hunter | 2011 | |
| `[Anime Time] Dandadan (Season 01+02)` | Dandadan | 2024 | |
| `[Anime Time] Death Parade` | Death Parade | 2015 | |
| `[Anime Time] Monster (2004)` | Monster | 2004 | |
| `Gyakkyou Burai Kaiji Ultimate Survivor` | Kaiji | 2007 | |
| `Gyakkyou Burai Kaiji Hakairoku-hen` | Kaiji Against All Rules | 2011 | |
| `[Saizen-HnG] Ashita_no_Joe_01-79` | Ashita no Joe | 1970 | |
| `Legend.of.the.Galactic.Heroes.1988.S01` | Legend of the Galactic Heroes | 1988 | Single series spanning S01–S03; one POST covers all seasons. S02 and S03 folders are sub-paths of the same series root and will be linked by the rescan. |
| `Legend.of.the.Galactic.Heroes.1988.S02` | — | — | **SKIP — same series as S01 above; rescan handles it** |
| `Legend.of.the.Galactic.Heroes.1988.S03` | — | — | **SKIP — same series as S01 above; rescan handles it** |
| `[Sokudo] Boku no Hero Academia` | My Hero Academia | 2016 | |
| `kijin gentosho` | Kijin Gentosho | — | No year; use first result |
| `[NewbSubs] Attack on Titan` | Attack on Titan | 2013 | |
| `[Trix] Spy x Family` | Spy x Family | 2022 | |
| `I.Know.What.You.Did.Last.Summer.S01` | I Know What You Did Last Summer | 2021 | |
| `La.Casa.De.Papel.(Money.Heist).S04` | Money Heist | 2017 | Moved from Movies in Phase 0 |
| `Dungeon Meshi S01` | Delicious in Dungeon | 2024 | |
| `[Judas] Mob Psycho 100` | Mob Psycho 100 | 2016 | |
| `[Judas] Overlord` | Overlord | 2015 | |
| `Tengen Toppa Gurren Lagann` | Gurren Lagann | 2007 | |

#### Movies (Radarr)
| Folder/file | Search term | Year | Notes |
|-------------|-------------|------|-------|
| `[JuicySubs] Tokyo Godfathers` | Tokyo Godfathers | 2003 | |
| `[infanf] Weathering with You` | Weathering with You | 2019 | |
| `[Judas] Jujutsu Kaisen - Movie 01` | Jujutsu Kaisen 0 | 2021 | |
| `Akira Kurosawa - Ikiru.1952` | Ikiru | 1952 | Use this folder (Criterion BD) |
| `Ikiru (1952) 720p BluRay` | — | — | **SKIP — lower quality duplicate; Criterion copy above is preferred** |
| `round-about-midnight-281999-29-dvdrip` | Round About Midnight | 1999 | |
| `Lola.Montes.1955` | Lola Montès | 1955 | |
| `Wathan Film Festival` | — | — | **SKIP — folder of short films** |

### Loose files in Movies root (no subfolder)

Handled in Phase 0b above. These files will be in proper subfolders before Phase 1 runs.

---

---

## Phase 3 — Post-import Rescan

After all adds:
1. Trigger Sonarr rescan all: `POST /api/v3/command {"name":"RescanSeries"}`
2. Trigger Radarr rescan all: `POST /api/v3/command {"name":"RescanMovie"}`
3. Trigger Jellyfin library refresh:
   - URL: `http://localhost:8096/Library/Refresh`
   - Header: `X-Emby-Token: e156612465294e5380221b28c2023f40`
   - Method: `POST` (no body)

**Note on Bazarr**: Bazarr polls Sonarr and Radarr on its own schedule (default every 12 hours). No manual Bazarr action is required — newly added series/movies will appear in Bazarr automatically on its next sync cycle. If you want to force it, restart the Bazarr container.

---

## Out of Scope

- No quality profile upgrades
- No automatic episode downloads
- Wathan Film Festival short films — skip entirely
- Duplicate entries (two versions of same film) — add only one; the script picks the one with the better-named folder
