# Services Reference

All services are defined in `docker-compose.yml`. Start/stop with `./run.sh up` / `./run.sh down`.

## Media Stack

| Service | Port | Local URL | Purpose |
|---------|------|-----------|---------|
| Jellyfin | 8096 | http://localhost:8096 | Media server — streams TV, movies, music |
| Sonarr | 8989 | http://localhost:8989 | TV show downloader and library manager |
| Radarr | 7878 | http://localhost:7878 | Movie downloader and library manager |
| Lidarr | 8686 | http://localhost:8686 | Music downloader and library manager |
| Readarr | 8787 | http://localhost:8787 | Book downloader and library manager |
| Bazarr | 6767 | http://localhost:6767 | Subtitle downloader — integrates with Sonarr/Radarr |
| Prowlarr | 9696 | http://localhost:9696 | Indexer aggregator for all *arr apps |
| Jellyseerr | 5055 | http://localhost:5055 | Media request portal — submit TV/movie requests |
| qBittorrent | 8082 | http://localhost:8082 | Torrent client (all traffic via Mullvad VPN) |

## Photos & Personal

| Service | Port | Local URL | Purpose |
|---------|------|-----------|---------|
| Immich | 2283 | http://localhost:2283 | Self-hosted Google Photos alternative |
| Navidrome | 4533 | http://localhost:4533 | Music streaming server (Subsonic-compatible) |
| Calibre-Web | 8083 | http://localhost:8083 | Book library browser and reader |

## Productivity

| Service | Port | Local URL | Purpose |
|---------|------|-----------|---------|
| Vaultwarden | 8089 | http://localhost:8089 | Bitwarden-compatible password manager |
| n8n | 5678 | http://localhost:5678 | Workflow automation |
| ntfy | 2586 | http://localhost:2586 | Push notification server |

## Infrastructure

| Service | Port | Local URL | Purpose |
|---------|------|-----------|---------|
| Caddy | 80, 443 | — | Reverse proxy — LAN + DuckDNS external access |
| Homer | 7575 | http://localhost:7575 | Dashboard / service index |
| Uptime Kuma | 3001 | http://localhost:3001 | Service uptime monitoring |
| Gluetun | — | — | Mullvad WireGuard VPN — qBittorrent routes through this |
| FlareSolverr | 8191 | — | Cloudflare bypass for Prowlarr indexers |
| DuckDNS | — | — | Dynamic DNS updater for external access |

## Custom Services

| Service | Port | Purpose |
|---------|------|---------|
| media-watcher | 8888 (internal) | Watch-while-downloading: creates Jellyfin symlinks for in-progress torrents |
| subtitle-cron | — | Runs `download_subs.py` daily at 03:00 via containerized cron |
