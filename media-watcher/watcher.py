#!/usr/bin/env python3
"""
media-watcher
─────────────
Polls qBittorrent for active downloads and provides two features:

1. Sequential downloading — ensures qBittorrent always downloads files
   from the beginning so Jellyfin can start playback immediately. Downloads
   land directly in the Jellyfin library folders (Movies/TV), so no symlinks
   are needed.

2. Streaming priority — monitors active Jellyfin sessions and throttles
   other torrents when the download head is too close to the playback
   position, preventing buffering.
"""

import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests

# ── Configuration (all from environment variables) ────────────────────────────
QB_URL    = os.environ.get("QB_URL",    "http://qbittorrent:8082")
QB_USER   = os.environ.get("QB_USER",   "admin")
QB_PASS   = os.environ.get("QB_PASS",   "")

RADARR_URL = os.environ.get("RADARR_URL", "http://radarr:7878")
RADARR_KEY = os.environ.get("RADARR_KEY", "")

SONARR_URL = os.environ.get("SONARR_URL", "http://sonarr:8989")
SONARR_KEY = os.environ.get("SONARR_KEY", "")

JELLYFIN_URL = os.environ.get("JELLYFIN_URL", "http://jellyfin:8096")
JELLYFIN_KEY = os.environ.get("JELLYFIN_KEY", "")

MEDIA_PATH    = os.environ.get("MEDIA_PATH",    "/data")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "30"))
# Minimum download progress before enforcing sequential download (default 2%)
MIN_PROGRESS  = float(os.environ.get("MIN_PROGRESS", "0.02"))

# Streaming Priority Settings
QB_THROTTLE_LIMIT = int(os.environ.get("QB_THROTTLE_LIMIT", "204800"))  # 200 KB/s
# Re-throttle when gap between download% and playback% drops below this
BUFFER_GAP_MIN    = float(os.environ.get("BUFFER_GAP_MIN", "0.05"))  # 5%
# Restore full speeds when gap grows back above this (hysteresis)
BUFFER_GAP_MAX    = float(os.environ.get("BUFFER_GAP_MAX", "0.15"))  # 15%
WATCHER_PORT      = int(os.environ.get("WATCHER_PORT", "8888"))

log = logging.getLogger("media-watcher")

# ── State ─────────────────────────────────────────────────────────────────────
# Priority Management
# hashes currently being prioritized for streaming
streaming_priorities: set[str] = set()
# hash -> original speed limit (usually -1 for unlimited)
throttled_hashes: dict[str, int] = {}
# List of {title: str, year: int} from ntfy "Watch Now" button
pending_priorities: list[dict] = []

# Maps library folder name → torrent hash for active downloads.
# Built each poll cycle from Radarr/Sonarr queue data and used by the
# webhook handler (running in a separate thread) to map Jellyfin playback
# events back to a torrent hash.
folder_to_hash: dict[str, str] = {}

# ── qBittorrent ───────────────────────────────────────────────────────────────
_qb_session: requests.Session | None = None


def qb_session() -> requests.Session:
    global _qb_session
    if _qb_session is None:
        s = requests.Session()
        s.headers.update({"Referer": QB_URL})
        try:
            r = s.post(
                f"{QB_URL}/api/v2/auth/login",
                data={"username": QB_USER, "password": QB_PASS},
                timeout=10,
            )
            if "Ok" in r.text or r.status_code == 200:
                log.info("Authenticated with qBittorrent")
        except Exception as e:
            log.warning(f"qBittorrent auth error: {e}")
        _qb_session = s
    return _qb_session


def get_torrents() -> list[dict]:
    global _qb_session
    try:
        r = qb_session().get(f"{QB_URL}/api/v2/torrents/info", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning(f"qBittorrent fetch error: {e}")
        _qb_session = None  # force re-auth next cycle
        return []


def get_torrent_properties(hash_id: str) -> dict:
    try:
        r = qb_session().get(
            f"{QB_URL}/api/v2/torrents/properties",
            params={"hash": hash_id},
            timeout=10
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning(f"  [QB] Failed to get properties for {hash_id[:8]}: {e}")
        return {}


def set_sequential_download(hash_id: str):
    """Enforce sequential downloading ONLY if not already enabled."""
    props = get_torrent_properties(hash_id)
    if props.get("seq_dl") is False:
        try:
            r = qb_session().post(
                f"{QB_URL}/api/v2/torrents/toggleSequentialDownload",
                data={"hashes": hash_id},
                timeout=10,
            )
            if r.status_code == 200:
                log.info(f"  [QB] Enabled sequential download for {hash_id[:8]}")
        except Exception as e:
            log.warning(f"  [QB] Failed to set sequential download: {e}")


def apply_streaming_priority(priority_hash: str, all_active_hashes: set[str]):
    """Throttle everything else, boost this one."""
    if priority_hash in streaming_priorities:
        return

    log.info(f"!!! STARTING STREAMING PRIORITY for {priority_hash[:8]} !!!")
    streaming_priorities.add(priority_hash)

    # 1. Top priority in queue
    try:
        qb_session().post(f"{QB_URL}/api/v2/torrents/topPrio", data={"hashes": priority_hash})
    except: pass

    # 2. Throttle everyone else
    others = all_active_hashes - {priority_hash}
    for h in others:
        if h in throttled_hashes: continue
        try:
            throttled_hashes[h] = -1
            qb_session().post(f"{QB_URL}/api/v2/torrents/setDownloadLimit", data={"hashes": h, "limit": QB_THROTTLE_LIMIT})
            log.info(f"  [QB] Throttled {h[:8]} to {QB_THROTTLE_LIMIT/1024:.0f} KB/s")
        except: pass


def restore_throttled():
    """Remove all speed limits."""
    if not throttled_hashes:
        return
    log.info("Restoring normal speeds to all torrents")
    hashes = ",".join(throttled_hashes.keys())
    try:
        qb_session().post(f"{QB_URL}/api/v2/torrents/setDownloadLimit", data={"hashes": hashes, "limit": -1})
    except: pass
    throttled_hashes.clear()


# ── Internal API Server ──────────────────────────────────────────────────────
class WatcherAPI(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            data = json.loads(body)
        except:
            data = {}

        if self.path == '/prioritize':
            # From ntfy button: {"title": "...", "year": 2024}
            if 'title' in data:
                pending_priorities.append(data)
                log.info(f"Pending priority added via ntfy: {data['title']}")
                self.send_response(200)
            else:
                self.send_response(400)

        elif self.path == '/webhook/playback-start':
            # From Jellyfin: {"ItemId": "...", "ItemType": "Movie/Episode", "Name": "..."}
            item_id = data.get("ItemId")
            name = data.get("Name")
            log.info(f"Playback started in Jellyfin for ItemId: {item_id}")

            # Map the playing item's parent folder to an active torrent hash.
            # folder_to_hash is built each poll cycle from Radarr/Sonarr queue data.
            found_hash = folder_to_hash.get(name) if name else None

            if found_hash:
                pending_priorities.append({"hash": found_hash})
                log.info(f"Priority triggered by Jellyfin Playback: {found_hash[:8]}")
                self.send_response(200)
            else:
                log.warning(f"Could not map Jellyfin Item '{name}' to an active torrent")
                self.send_response(404)
        else:
            self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return # silence logs

def run_server():
    server = HTTPServer(('0.0.0.0', WATCHER_PORT), WatcherAPI)
    log.info(f"Internal API listening on port {WATCHER_PORT}")
    server.serve_forever()


# ── Radarr ────────────────────────────────────────────────────────────────────
def get_radarr_queue() -> dict[str, dict]:
    """Returns {download_id_upper: queue_item}"""
    try:
        r = requests.get(
            f"{RADARR_URL}/api/v3/queue",
            headers={"X-Api-Key": RADARR_KEY},
            params={"page": 1, "pageSize": 200, "includeMovie": True},
            timeout=10,
        )
        r.raise_for_status()
        return {
            item["downloadId"].upper(): item
            for item in r.json().get("records", [])
            if item.get("downloadId")
        }
    except Exception as e:
        log.warning(f"Radarr queue error: {e}")
        return {}


# ── Sonarr ────────────────────────────────────────────────────────────────────
def get_sonarr_queue() -> dict[str, dict]:
    """Returns {download_id_upper: queue_item}"""
    try:
        r = requests.get(
            f"{SONARR_URL}/api/v3/queue",
            headers={"X-Api-Key": SONARR_KEY},
            params={
                "page": 1,
                "pageSize": 200,
                "includeSeries": True,
                "includeEpisode": True,
            },
            timeout=10,
        )
        r.raise_for_status()
        return {
            item["downloadId"].upper(): item
            for item in r.json().get("records", [])
            if item.get("downloadId")
        }
    except Exception as e:
        log.warning(f"Sonarr queue error: {e}")
        return {}


# ── Jellyfin ──────────────────────────────────────────────────────────────────
def get_active_sessions() -> list[dict]:
    """
    Return info about everything currently being played in Jellyfin.
    Each entry: {"path": str, "folder": str, "position_pct": float, "name": str}
    position_pct is 0.0–1.0 representing how far into the file the user is.
    """
    try:
        r = requests.get(
            f"{JELLYFIN_URL}/Sessions",
            headers={"X-Emby-Token": JELLYFIN_KEY},
            timeout=10,
        )
        r.raise_for_status()
        sessions = []
        for session in r.json():
            item = session.get("NowPlayingItem")
            if not item:
                continue
            path = item.get("Path", "")
            if not path:
                continue
            runtime_ticks = item.get("RunTimeTicks") or 0
            position_ticks = (session.get("PlayState") or {}).get("PositionTicks") or 0
            position_pct = (position_ticks / runtime_ticks) if runtime_ticks > 0 else 0.0
            sessions.append({
                "path": path,
                "folder": Path(path).parent.name,
                "position_pct": position_pct,
                "name": item.get("Name", ""),
            })
        return sessions
    except Exception as e:
        log.warning(f"Jellyfin sessions error: {e}")
        return []


# ── Main poll cycle ───────────────────────────────────────────────────────────
def poll():
    global folder_to_hash

    torrents  = get_torrents()
    radarr_q  = get_radarr_queue()
    sonarr_q  = get_sonarr_queue()

    # Build folder name → torrent hash from Radarr/Sonarr queue data.
    # Used by the gap hysteresis logic and the Jellyfin webhook handler to
    # map a playing item back to its in-progress torrent.
    new_folder_to_hash: dict[str, str] = {}
    for h, item in radarr_q.items():
        movie = item.get("movie") or {}
        folder = movie.get("folderName") or (
            f"{movie.get('title', 'Unknown')} ({movie.get('year', '')})"
        )
        new_folder_to_hash[folder] = h
    for h, item in sonarr_q.items():
        series = item.get("series") or {}
        series_path = series.get("path", "")
        if series_path:
            new_folder_to_hash[Path(series_path).name] = h
        else:
            title = series.get("title", "Unknown")
            year  = series.get("year", "")
            new_folder_to_hash[f"{title} ({year})"] = h
    folder_to_hash = new_folder_to_hash

    # Build download progress map: hash → progress (0.0–1.0)
    dl_progress_map: dict[str, float] = {}
    for t in torrents:
        dl_progress_map[t["hash"].upper()] = t.get("progress", 0.0)

    # ── Session-based gap hysteresis ─────────────────────────────────────────
    # Compare each active Jellyfin session's playback position against the
    # download progress for the matching torrent.  Throttle when the gap is
    # too small; restore when it opens back up; auto-restore when no session
    # is found for a previously-prioritised hash.
    active_sessions = get_active_sessions()
    seen_priority_hashes: set[str] = set()

    for session in active_sessions:
        played_folder = session["folder"]  # e.g. "City of God (2002)"
        h = folder_to_hash.get(played_folder)
        if not h:
            continue  # not one of our managed downloads

        seen_priority_hashes.add(h)
        position_pct = session["position_pct"]
        dl_pct       = dl_progress_map.get(h, 1.0)
        gap          = dl_pct - position_pct

        log.debug(
            f"  [GAP] {session['name']!r}: dl={dl_pct*100:.1f}%  "
            f"pos={position_pct*100:.1f}%  gap={gap*100:.1f}%"
        )

        if gap < BUFFER_GAP_MIN:
            # Buffer is thin — apply / maintain streaming priority
            if h not in streaming_priorities:
                log.info(
                    f"Gap {gap*100:.1f}% < {BUFFER_GAP_MIN*100:.0f}% for "
                    f"'{session['name']}' → throttling others"
                )
                pending_priorities.append({"hash": h})
        elif gap > BUFFER_GAP_MAX and h in streaming_priorities:
            # Buffer is comfortably large — release throttle
            log.info(
                f"Gap {gap*100:.1f}% > {BUFFER_GAP_MAX*100:.0f}% for "
                f"'{session['name']}' → restoring full speeds"
            )
            streaming_priorities.discard(h)
            if not streaming_priorities:
                restore_throttled()

    # Auto-restore: user stopped watching (no active session for this hash)
    for h in list(streaming_priorities):
        if h not in seen_priority_hashes:
            log.info(f"No active session for {h[:8]} → auto-restoring speeds")
            streaming_priorities.discard(h)
            if not streaming_priorities:
                restore_throttled()
    # ─────────────────────────────────────────────────────────────────────────

    active_hashes: set[str] = set()

    for t in torrents:
        hash_id  = t["hash"].upper()
        progress = t.get("progress", 0)
        state    = t.get("state", "")

        # Only process torrents that are actively downloading content
        if state not in ("downloading", "stalledDL", "metaDL", "checkingDL"):
            continue
        if progress < MIN_PROGRESS:
            continue

        active_hashes.add(hash_id)

        # Enforce sequential download ONLY if not already enabled.
        set_sequential_download(hash_id)

        # ── Pending priority queue (from ntfy button or webhook) ─────────────
        for p in list(pending_priorities):
            # Check by hash (from Jellyfin webhook or session detection above)
            if p.get("hash") == hash_id:
                apply_streaming_priority(hash_id, active_hashes)
                pending_priorities.remove(p)
            # Check by title (from ntfy "Watch Now" button)
            elif p.get("title") and p.get("title") in t.get("name", ""):
                apply_streaming_priority(hash_id, active_hashes)
                pending_priorities.remove(p)
        # ─────────────────────────────────────────────────────────────────────


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    log.info(
        "media-watcher started  (poll=%ds  min_progress=%.0f%%)",
        POLL_INTERVAL,
        MIN_PROGRESS * 100,
    )

    # Start the API server in a separate thread
    threading.Thread(target=run_server, daemon=True).start()

    while True:
        try:
            poll()
        except Exception as e:
            log.error(f"Unhandled error in poll(): {e}", exc_info=True)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
