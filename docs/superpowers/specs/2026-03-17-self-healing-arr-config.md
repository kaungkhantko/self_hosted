# Self-Healing *arr Configuration

**Date:** 2026-03-17  
**Status:** Approved  
**Scope:** Radarr, Sonarr, Jellyseerr  
**Approach:** Native *arr configuration only (no new code)

---

## Problem Statement

Two recurring issues currently require manual intervention to resolve:

1. **Quality profile fallbacks** — Radarr's "Ultra-HD" profile (id:5) only accepts 2160p formats. When a requested movie has no 4K release, Radarr silently grabs nothing. The user must manually change the quality profile per-movie to get any download at all.

2. **Stalled/dead torrent accumulation** — Torrents with 0 seeds sit in the queue indefinitely. No automatic cleanup or retry occurs. Dead queue entries accumulate until manually cleared.

---

## Solution Overview

Use existing native *arr features that are currently misconfigured or disabled:

1. Switch to the "4K > 1080p > 720p" quality profile (id:7) as the default for all requests — this profile already exists in both Radarr and Sonarr.
2. Enable Failed Download Handling in both apps so stalled/failed downloads are auto-removed, blocklisted, and re-searched.

---

## Part 1: Quality Profile Fallbacks

### Profile Change

**Target profile:** id:7 "4K > 1080p > 720p" (exists in both Radarr and Sonarr)

| Setting | Value |
|---|---|
| `upgradeAllowed` | `true` |
| Allowed qualities | 720p, 1080p, 2160p (all variants) |
| Cutoff | `WEB 2160p` |
| Behavior | Grabs best available quality immediately; upgrades to 4K when it appears |

**Why id:7 instead of modifying Ultra-HD (id:5):**  
Ultra-HD is used by other items that are correctly 4K-only. Changing it would lower quality for those. Profile id:7 was specifically created for the fallback use case.

### Changes Required

#### Jellyseerr (`jellyseerr/settings.json`)

Change the Radarr quality profile ID from `5` to `7`:
```json
// In radarr[] array entry:
"qualityProfile": 7
```

Change the Sonarr quality profile ID from `5` to `7`:
```json
// In sonarr[] array entry:
"qualityProfile": 7
```

This affects all future requests submitted through Jellyseerr.

#### Radarr — Bulk migrate existing movies

Via Radarr API (`PUT /api/v3/movie/editor`):
- Find all movies where `qualityProfileId == 5` AND `hasFile == false`
- Update their `qualityProfileId` to `7`
- Trigger `MoviesSearch` command for migrated movie IDs

Condition `hasFile == false` ensures we only touch movies that haven't successfully downloaded anything yet. Movies already downloaded at 4K are unaffected.

#### Sonarr — Bulk migrate existing series

Via Sonarr API (`PUT /api/v3/series/editor`):
- Find all series where `qualityProfileId == 5` AND `statistics.episodeFileCount == 0`
- Update their `qualityProfileId` to `7`
- Trigger `SeriesSearch` command for migrated series IDs

Same condition: only series with nothing downloaded yet.

### Expected Outcome

- New requests via Jellyseerr: grabbed at best available quality, upgraded to 4K when available
- Existing stuck movies/shows: re-searched immediately after profile change; will grab 1080p if no 4K exists
- Movies/shows already downloaded at 4K: unaffected

---

## Part 2: Stalled/Dead Torrent Cleanup

### Mechanism

Sonarr and Radarr poll qBittorrent periodically. When qBittorrent reports a torrent as `stalledDL` (0 seeds, no progress), Sonarr/Radarr can be configured to:
1. Mark the download as failed
2. Remove the torrent from qBittorrent
3. Add the release to the blocklist (so the same bad release isn't re-grabbed)
4. Immediately trigger a new search for an alternative release

This is the **Failed Download Handling** feature, currently disabled.

### Changes Required

#### Radarr (Settings → Download Clients → Failed Download Handling)

| Setting | Current | Target |
|---|---|---|
| `Remove` | unknown/off | **Enabled** |
| `Redownload` | unknown/off | **Enabled** |

#### Sonarr (Settings → Download Clients → Failed Download Handling)

| Setting | Current | Target |
|---|---|---|
| `Remove` | unknown/off | **Enabled** |
| `Redownload` | unknown/off | **Enabled** |

These settings are toggled via the UI or via API:
- Radarr: `PUT /api/v3/config/downloadclient`
- Sonarr: `PUT /api/v3/config/downloadclient`

### Known Limitations

- A torrent downloading at extremely low speed (1 seed, 1 KB/s) will not be detected as stalled — qBittorrent does not report it as `stalledDL`. These edge cases can be handled later with a scheduled cleanup script (Approach B) if needed.
- If no alternative release exists on any indexer, the re-search will also fail. The episode/movie will remain in a "missing" state and retry on the next scheduled search.

---

## Out of Scope

The following known issues are explicitly excluded from this spec:

- **Jellyseerr AvailabilitySync false positives** — nightly job marking shows as deleted
- **OpenSubtitles account block** — Bazarr subtitle provider failure
- **Grey's S14E07 / S17E17** — specific missing episodes with no indexer coverage
- **Naruto Shippuden manual import** — torrent added outside Sonarr

These can be addressed in separate specs.

---

## Implementation Steps

1. Read current Jellyseerr `settings.json` to confirm Radarr/Sonarr profile field names
2. Update `jellyseerr/settings.json`: set `qualityProfile` to `7` for both Radarr and Sonarr entries
3. Restart Jellyseerr container to pick up settings change
4. Radarr bulk profile migration: query movies, filter, PATCH to id:7, trigger search
5. Sonarr bulk profile migration: query series, filter, PATCH to id:7, trigger search
6. Enable Failed Download Handling in Radarr via API
7. Enable Failed Download Handling in Sonarr via API
8. Verify: check Radarr/Sonarr queues and confirm previously-stuck items start downloading

---

## Verification

After implementation:

```bash
# Check Radarr movies still on Ultra-HD with no files (should be 0 after migration)
curl -s "http://localhost:7878/api/v3/movie?apikey=9f1eed6ac4bc4f0eb9654c8b3d12e14d" | \
  python3 -c "import sys,json; ms=json.load(sys.stdin); stuck=[m['title'] for m in ms if m['qualityProfileId']==5 and not m['hasFile']]; print(len(stuck),'stuck:', stuck[:5])"

# Check Sonarr series still on Ultra-HD with no files (should be 0 after migration)
curl -s "http://localhost:8989/api/v3/series?apikey=ba1c87c1d3f84eb1a096095279dabed0" | \
  python3 -c "import sys,json; ss=json.load(sys.stdin); stuck=[s['title'] for s in ss if s['qualityProfileId']==5 and s['statistics']['episodeFileCount']==0]; print(len(stuck),'stuck:', stuck[:5])"

# Check Failed Download Handling is enabled in Radarr
curl -s "http://localhost:7878/api/v3/config/downloadclient?apikey=9f1eed6ac4bc4f0eb9654c8b3d12e14d" | python3 -c "import sys,json; c=json.load(sys.stdin); print('remove:', c.get('removeCompletedDownloads'), 'redownload:', c.get('autoRedownloadFailed'))"
```
