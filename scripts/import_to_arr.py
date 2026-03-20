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
