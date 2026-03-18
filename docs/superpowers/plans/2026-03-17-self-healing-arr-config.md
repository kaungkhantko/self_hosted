# Self-Healing *arr Configuration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure Radarr, Sonarr, and Jellyseerr so that media requests automatically fall back to the best available quality and stalled/dead downloads are automatically removed and re-searched — without any manual intervention.

**Architecture:** Two independent configuration changes via localhost APIs and a JSON file edit. No new code, no new services. All changes are idempotent and can be safely re-run. Jellyseerr uses a settings file on disk; Radarr and Sonarr expose full configuration via REST API.

**Tech Stack:** curl, python3 (stdlib only), docker compose, Radarr v3 API, Sonarr v3 API, Jellyseerr settings.json

---

## Chunk 1: Quality Profile Fallbacks

### Task 1: Update Jellyseerr settings.json

**Files:**
- Modify: `/home/kaung/self_hosted/jellyseerr/settings.json`

The field names in settings.json are `activeProfileId` and `activeProfileName` (not `qualityProfile`). Both Radarr and Sonarr integrations currently use profile `5` ("Ultra-HD"). We need to change them to `7` ("4K > 1080p > 720p").

Sonarr also has anime-specific profile fields (`activeAnimeProfileId`, `activeAnimeProfileName`) which must be updated too.

- [ ] **Step 1.1: Verify current profile IDs in settings.json**

Run:
```bash
python3 -c "
import json
with open('/home/kaung/self_hosted/jellyseerr/settings.json') as f:
    s = json.load(f)
for r in s.get('radarr', []):
    print('Radarr:', r['name'], '| profileId:', r['activeProfileId'], '| profileName:', r['activeProfileName'])
for sv in s.get('sonarr', []):
    print('Sonarr:', sv['name'], '| profileId:', sv['activeProfileId'], '| profileName:', sv['activeProfileName'])
    print('Sonarr anime:', sv['name'], '| animeProfileId:', sv.get('activeAnimeProfileId'), '| animeProfileName:', sv.get('activeAnimeProfileName'))
"
```

Expected output:
```
Radarr: Radarr | profileId: 5 | profileName: Ultra-HD
Sonarr: Sonarr | profileId: 5 | profileName: Ultra-HD
Sonarr anime: Sonarr | animeProfileId: 5 | animeProfileName: Ultra-HD
```

If any value is already `7`, skip the corresponding update in Step 1.2.

- [ ] **Step 1.2: Update profile IDs to 7**

Run:
```bash
python3 -c "
import json
path = '/home/kaung/self_hosted/jellyseerr/settings.json'
with open(path) as f:
    s = json.load(f)

for r in s.get('radarr', []):
    r['activeProfileId'] = 7
    r['activeProfileName'] = '4K > 1080p > 720p'

for sv in s.get('sonarr', []):
    sv['activeProfileId'] = 7
    sv['activeProfileName'] = '4K > 1080p > 720p'
    sv['activeAnimeProfileId'] = 7
    sv['activeAnimeProfileName'] = '4K > 1080p > 720p'

with open(path, 'w') as f:
    json.dump(s, f, indent=2)
print('Done')
"
```

Expected: `Done`

- [ ] **Step 1.3: Verify the file was written correctly**

Run:
```bash
python3 -c "
import json
with open('/home/kaung/self_hosted/jellyseerr/settings.json') as f:
    s = json.load(f)
for r in s.get('radarr', []):
    print('Radarr:', r['activeProfileId'], r['activeProfileName'])
for sv in s.get('sonarr', []):
    print('Sonarr:', sv['activeProfileId'], sv['activeProfileName'])
    print('Sonarr anime:', sv.get('activeAnimeProfileId'), sv.get('activeAnimeProfileName'))
"
```

Expected:
```
Radarr: 7 4K > 1080p > 720p
Sonarr: 7 4K > 1080p > 720p
Sonarr anime: 7 4K > 1080p > 720p
```

- [ ] **Step 1.4: Restart Jellyseerr to pick up the new settings**

Run:
```bash
docker compose -f /home/kaung/self_hosted/docker-compose.yml restart jellyseerr
```

Expected: `Container self_hosted-jellyseerr-1  Restarted` (or similar, no errors)

- [ ] **Step 1.5: Verify Jellyseerr is healthy after restart**

Run:
```bash
sleep 10 && curl -s -o /dev/null -w "%{http_code}" http://localhost:5055/api/v1/status
```

Expected: `200`

If not 200 within 30 seconds, check logs: `docker compose -f /home/kaung/self_hosted/docker-compose.yml logs --tail=50 jellyseerr`

- [ ] **Step 1.6: Commit**

```bash
cd /home/kaung/self_hosted && git add jellyseerr/settings.json && git commit -m "config: set Jellyseerr default quality profile to '4K > 1080p > 720p' (id:7)"
```

---

### Task 2: Bulk migrate Radarr movies from Ultra-HD to fallback profile

**Files:** No files. API calls only to `http://localhost:7878`.

Find all Radarr movies currently on profile 5 (Ultra-HD) with no file downloaded, update them to profile 7, and trigger a search so they start downloading immediately.

- [ ] **Step 2.1: Identify stuck movies**

Run:
```bash
python3 -c "
import urllib.request, json
url = 'http://localhost:7878/api/v3/movie?apikey=9f1eed6ac4bc4f0eb9654c8b3d12e14d'
with urllib.request.urlopen(url) as r:
    movies = json.load(r)
stuck = [m for m in movies if m['qualityProfileId'] == 5 and not m['hasFile']]
print(f'Found {len(stuck)} stuck movies:')
for m in stuck:
    print(f'  id={m[\"id\"]} | {m[\"title\"]} ({m.get(\"year\",\"?\")})')
"
```

Note the count and IDs. If 0, skip Steps 2.2–2.4.

- [ ] **Step 2.2: Bulk update stuck movies to profile 7**

Run (replace the movie IDs list with actual IDs from Step 2.1 — the script collects them automatically):
```bash
python3 -c "
import urllib.request, urllib.parse, json

apikey = '9f1eed6ac4bc4f0eb9654c8b3d12e14d'
base = 'http://localhost:7878/api/v3'

# Fetch all movies
with urllib.request.urlopen(f'{base}/movie?apikey={apikey}') as r:
    movies = json.load(r)

stuck_ids = [m['id'] for m in movies if m['qualityProfileId'] == 5 and not m['hasFile']]
if not stuck_ids:
    print('No stuck movies. Nothing to do.')
    exit(0)

print(f'Updating {len(stuck_ids)} movies to profile 7...')

# Bulk editor endpoint
payload = json.dumps({
    'movieIds': stuck_ids,
    'qualityProfileId': 7,
    'applyTags': 'add'
}).encode()

req = urllib.request.Request(
    f'{base}/movie/editor?apikey={apikey}',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='PUT'
)
with urllib.request.urlopen(req) as r:
    result = json.load(r)
    print(f'Updated {len(result)} movies successfully.')
"
```

Expected: `Updated N movies successfully.`

- [ ] **Step 2.3: Trigger search for migrated movies**

Run:
```bash
python3 -c "
import urllib.request, json

apikey = '9f1eed6ac4bc4f0eb9654c8b3d12e14d'
base = 'http://localhost:7878/api/v3'

# Re-fetch to get updated list (now on profile 7 with no file)
with urllib.request.urlopen(f'{base}/movie?apikey={apikey}') as r:
    movies = json.load(r)

migrated_ids = [m['id'] for m in movies if m['qualityProfileId'] == 7 and not m['hasFile']]
if not migrated_ids:
    print('No movies to search.')
    exit(0)

print(f'Triggering search for {len(migrated_ids)} movies...')

payload = json.dumps({
    'name': 'MoviesSearch',
    'movieIds': migrated_ids
}).encode()

req = urllib.request.Request(
    f'{base}/command?apikey={apikey}',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    result = json.load(r)
    print(f'Search command queued, id={result[\"id\"]}, status={result[\"status\"]}')
"
```

Expected: `Search command queued, id=<N>, status=queued`

If non-2xx error, the movies will still be picked up on next scheduled search. Log the error and continue.

- [ ] **Step 2.4: Verify migration — no movies remain on Ultra-HD with no file**

Run:
```bash
python3 -c "
import urllib.request, json
url = 'http://localhost:7878/api/v3/movie?apikey=9f1eed6ac4bc4f0eb9654c8b3d12e14d'
with urllib.request.urlopen(url) as r:
    movies = json.load(r)
stuck = [m['title'] for m in movies if m['qualityProfileId'] == 5 and not m['hasFile']]
print(f'{len(stuck)} still stuck:', stuck[:5] if stuck else 'none')
"
```

Expected: `0 still stuck: none`

- [ ] **Step 2.5: Commit**

```bash
cd /home/kaung/self_hosted && git commit --allow-empty -m "ops: migrated Radarr stuck Ultra-HD movies to profile 7 and triggered search"
```

(Allow-empty because no tracked files changed — this is just a record of the operation.)

---

### Task 3: Bulk migrate Sonarr series from Ultra-HD to fallback profile

**Files:** No files. API calls only to `http://localhost:8989`.

Same pattern as Task 2 but for Sonarr series.

- [ ] **Step 3.1: Identify stuck series**

Run:
```bash
python3 -c "
import urllib.request, json
url = 'http://localhost:8989/api/v3/series?apikey=ba1c87c1d3f84eb1a096095279dabed0'
with urllib.request.urlopen(url) as r:
    series = json.load(r)
stuck = [s for s in series if s['qualityProfileId'] == 5 and s['statistics']['episodeFileCount'] == 0]
print(f'Found {len(stuck)} stuck series:')
for s in stuck:
    print(f'  id={s[\"id\"]} | {s[\"title\"]}')
"
```

Note the count and IDs. If 0, skip Steps 3.2–3.4.

- [ ] **Step 3.2: Bulk update stuck series to profile 7**

Run:
```bash
python3 -c "
import urllib.request, json

apikey = 'ba1c87c1d3f84eb1a096095279dabed0'
base = 'http://localhost:8989/api/v3'

with urllib.request.urlopen(f'{base}/series?apikey={apikey}') as r:
    series = json.load(r)

stuck_ids = [s['id'] for s in series if s['qualityProfileId'] == 5 and s['statistics']['episodeFileCount'] == 0]
if not stuck_ids:
    print('No stuck series. Nothing to do.')
    exit(0)

print(f'Updating {len(stuck_ids)} series to profile 7...')

payload = json.dumps({
    'seriesIds': stuck_ids,
    'qualityProfileId': 7,
    'applyTags': 'add'
}).encode()

req = urllib.request.Request(
    f'{base}/series/editor?apikey={apikey}',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='PUT'
)
with urllib.request.urlopen(req) as r:
    result = json.load(r)
    print(f'Updated {len(result)} series successfully.')
"
```

Expected: `Updated N series successfully.`

- [ ] **Step 3.3: Trigger search for migrated series**

Run:
```bash
python3 -c "
import urllib.request, json

apikey = 'ba1c87c1d3f84eb1a096095279dabed0'
base = 'http://localhost:8989/api/v3'

with urllib.request.urlopen(f'{base}/series?apikey={apikey}') as r:
    series = json.load(r)

migrated_ids = [s['id'] for s in series if s['qualityProfileId'] == 7 and s['statistics']['episodeFileCount'] == 0]
if not migrated_ids:
    print('No series to search.')
    exit(0)

print(f'Triggering search for {len(migrated_ids)} series...')

# Sonarr SeriesSearch takes a single seriesId — trigger one command per series
results = []
for sid in migrated_ids:
    payload = json.dumps({'name': 'SeriesSearch', 'seriesId': sid}).encode()
    req = urllib.request.Request(
        f'{base}/command?apikey={apikey}',
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = json.load(r)
            results.append(result['id'])
    except Exception as e:
        print(f'  Warning: search failed for seriesId={sid}: {e}')

print(f'Queued {len(results)} search commands.')
"
```

Expected: `Queued N search commands.`

- [ ] **Step 3.4: Verify migration — no series remain on Ultra-HD with no files**

Run:
```bash
python3 -c "
import urllib.request, json
url = 'http://localhost:8989/api/v3/series?apikey=ba1c87c1d3f84eb1a096095279dabed0'
with urllib.request.urlopen(url) as r:
    series = json.load(r)
stuck = [s['title'] for s in series if s['qualityProfileId'] == 5 and s['statistics']['episodeFileCount'] == 0]
print(f'{len(stuck)} still stuck:', stuck[:5] if stuck else 'none')
"
```

Expected: `0 still stuck: none`

- [ ] **Step 3.5: Commit**

```bash
cd /home/kaung/self_hosted && git commit --allow-empty -m "ops: migrated Sonarr stuck Ultra-HD series to profile 7 and triggered search"
```

---

## Chunk 2: Failed Download Handling + Final Verification

### Task 4: Enable Failed Download Handling in Radarr

**Files:** No files. API calls only to `http://localhost:7878`.

Always GET the full config first, modify only the two target fields, then PUT the full object back.

- [ ] **Step 4.1: Read current Radarr download client config**

Run:
```bash
python3 -c "
import urllib.request, json
url = 'http://localhost:7878/api/v3/config/downloadclient?apikey=9f1eed6ac4bc4f0eb9654c8b3d12e14d'
with urllib.request.urlopen(url) as r:
    c = json.load(r)
print('removeCompletedDownloads:', c.get('removeCompletedDownloads'))
print('autoRedownloadFailed:', c.get('autoRedownloadFailed'))
print('Full config id:', c.get('id'))
"
```

Note the current values and the `id` field. If both are already `True`, skip Steps 4.2–4.3.

- [ ] **Step 4.2: Enable Failed Download Handling**

Run:
```bash
python3 -c "
import urllib.request, json

apikey = '9f1eed6ac4bc4f0eb9654c8b3d12e14d'
base = 'http://localhost:7878/api/v3'

# GET full config
with urllib.request.urlopen(f'{base}/config/downloadclient?apikey={apikey}') as r:
    config = json.load(r)

# Modify only the two target fields
config['removeCompletedDownloads'] = True
config['autoRedownloadFailed'] = True

# PUT full config back
payload = json.dumps(config).encode()
req = urllib.request.Request(
    f'{base}/config/downloadclient?apikey={apikey}',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='PUT'
)
with urllib.request.urlopen(req) as r:
    result = json.load(r)
    print('removeCompletedDownloads:', result['removeCompletedDownloads'])
    print('autoRedownloadFailed:', result['autoRedownloadFailed'])
"
```

Expected:
```
removeCompletedDownloads: True
autoRedownloadFailed: True
```

- [ ] **Step 4.3: Commit**

```bash
cd /home/kaung/self_hosted && git commit --allow-empty -m "ops: enabled Failed Download Handling in Radarr (removeCompleted + autoRedownload)"
```

---

### Task 5: Enable Failed Download Handling in Sonarr

**Files:** No files. API calls only to `http://localhost:8989`.

Identical pattern to Task 4.

- [ ] **Step 5.1: Read current Sonarr download client config**

Run:
```bash
python3 -c "
import urllib.request, json
url = 'http://localhost:8989/api/v3/config/downloadclient?apikey=ba1c87c1d3f84eb1a096095279dabed0'
with urllib.request.urlopen(url) as r:
    c = json.load(r)
print('removeCompletedDownloads:', c.get('removeCompletedDownloads'))
print('autoRedownloadFailed:', c.get('autoRedownloadFailed'))
print('Full config id:', c.get('id'))
"
```

Note current values. If both are already `True`, skip Steps 5.2–5.3.

- [ ] **Step 5.2: Enable Failed Download Handling**

Run:
```bash
python3 -c "
import urllib.request, json

apikey = 'ba1c87c1d3f84eb1a096095279dabed0'
base = 'http://localhost:8989/api/v3'

with urllib.request.urlopen(f'{base}/config/downloadclient?apikey={apikey}') as r:
    config = json.load(r)

config['removeCompletedDownloads'] = True
config['autoRedownloadFailed'] = True

payload = json.dumps(config).encode()
req = urllib.request.Request(
    f'{base}/config/downloadclient?apikey={apikey}',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='PUT'
)
with urllib.request.urlopen(req) as r:
    result = json.load(r)
    print('removeCompletedDownloads:', result['removeCompletedDownloads'])
    print('autoRedownloadFailed:', result['autoRedownloadFailed'])
"
```

Expected:
```
removeCompletedDownloads: True
autoRedownloadFailed: True
```

- [ ] **Step 5.3: Commit**

```bash
cd /home/kaung/self_hosted && git commit --allow-empty -m "ops: enabled Failed Download Handling in Sonarr (removeCompleted + autoRedownload)"
```

---

### Task 6: Full Verification

Run all checks in sequence. Every check must pass before considering this complete.

- [ ] **Step 6.1: Verify Jellyseerr settings on disk**

```bash
python3 -c "
import json
with open('/home/kaung/self_hosted/jellyseerr/settings.json') as f:
    s = json.load(f)
ok = True
for r in s.get('radarr', []):
    if r['activeProfileId'] != 7:
        print('FAIL Radarr profile:', r['activeProfileId'])
        ok = False
    else:
        print('OK Radarr:', r['activeProfileId'], r['activeProfileName'])
for sv in s.get('sonarr', []):
    if sv['activeProfileId'] != 7:
        print('FAIL Sonarr profile:', sv['activeProfileId'])
        ok = False
    else:
        print('OK Sonarr:', sv['activeProfileId'], sv['activeProfileName'])
    if sv.get('activeAnimeProfileId') != 7:
        print('FAIL Sonarr anime profile:', sv.get('activeAnimeProfileId'))
        ok = False
    else:
        print('OK Sonarr anime:', sv['activeAnimeProfileId'], sv['activeAnimeProfileName'])
print('PASS' if ok else 'FAIL - check above')
"
```

Expected: All lines show `OK` and final line shows `PASS`

- [ ] **Step 6.2: Verify Jellyseerr is alive**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5055/api/v1/status
```

Expected: `200`

- [ ] **Step 6.3: Verify no Radarr movies stuck on Ultra-HD with no file**

```bash
python3 -c "
import urllib.request, json
with urllib.request.urlopen('http://localhost:7878/api/v3/movie?apikey=9f1eed6ac4bc4f0eb9654c8b3d12e14d') as r:
    movies = json.load(r)
stuck = [m['title'] for m in movies if m['qualityProfileId'] == 5 and not m['hasFile']]
print(f'{len(stuck)} stuck:', stuck[:5] if stuck else 'none')
"
```

Expected: `0 stuck: none`

- [ ] **Step 6.4: Verify no Sonarr series stuck on Ultra-HD with no files**

```bash
python3 -c "
import urllib.request, json
with urllib.request.urlopen('http://localhost:8989/api/v3/series?apikey=ba1c87c1d3f84eb1a096095279dabed0') as r:
    series = json.load(r)
stuck = [s['title'] for s in series if s['qualityProfileId'] == 5 and s['statistics']['episodeFileCount'] == 0]
print(f'{len(stuck)} stuck:', stuck[:5] if stuck else 'none')
"
```

Expected: `0 stuck: none`

- [ ] **Step 6.5: Verify Radarr Failed Download Handling**

```bash
python3 -c "
import urllib.request, json
with urllib.request.urlopen('http://localhost:7878/api/v3/config/downloadclient?apikey=9f1eed6ac4bc4f0eb9654c8b3d12e14d') as r:
    c = json.load(r)
ok = c.get('removeCompletedDownloads') and c.get('autoRedownloadFailed')
print('removeCompletedDownloads:', c.get('removeCompletedDownloads'))
print('autoRedownloadFailed:', c.get('autoRedownloadFailed'))
print('PASS' if ok else 'FAIL')
"
```

Expected: Both `True`, final line `PASS`

- [ ] **Step 6.6: Verify Sonarr Failed Download Handling**

```bash
python3 -c "
import urllib.request, json
with urllib.request.urlopen('http://localhost:8989/api/v3/config/downloadclient?apikey=ba1c87c1d3f84eb1a096095279dabed0') as r:
    c = json.load(r)
ok = c.get('removeCompletedDownloads') and c.get('autoRedownloadFailed')
print('removeCompletedDownloads:', c.get('removeCompletedDownloads'))
print('autoRedownloadFailed:', c.get('autoRedownloadFailed'))
print('PASS' if ok else 'FAIL')
"
```

Expected: Both `True`, final line `PASS`

- [ ] **Step 6.7: Final commit**

```bash
cd /home/kaung/self_hosted && git commit --allow-empty -m "ops: self-healing arr config complete - quality fallbacks and failed download handling enabled"
```
