# self_hosted

Personal self-hosted media and productivity stack running on a dedicated Linux machine.

25 services managed by Docker Compose: Jellyfin, Sonarr, Radarr, Bazarr, Prowlarr, qBittorrent (via Mullvad VPN), Jellyseerr, Immich, Navidrome, Vaultwarden, Calibre-Web, Readarr, Lidarr, Bazarr, n8n, ntfy, Uptime Kuma, Homer, Caddy, and more.

---

## Prerequisites

Install these on the new machine before anything else:

1. **Docker CE + Docker Compose v2**
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   # Log out and back in to apply group membership
   docker compose version  # should print v2.x.x
   ```

2. **Git**
   ```bash
   sudo apt install git
   ```

3. **(Optional) NVIDIA GPU support** — only if the machine has an NVIDIA GPU
   - Install NVIDIA drivers
   - Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
   - Set `COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml` in your `.env`

---

## Disk Setup

The media hard drive must be mounted at `/mnt/media` on every boot.

```bash
# 1. Find the drive UUID
sudo blkid /dev/sdX   # replace sdX with your drive

# 2. Create mount point
sudo mkdir -p /mnt/media

# 3. Add to /etc/fstab (replace UUID with yours, adjust fstype if needed)
echo "UUID=your-uuid-here  /mnt/media  ext4  defaults,nofail  0  2" | sudo tee -a /etc/fstab

# 4. Test mount
sudo mount -a
mountpoint /mnt/media   # should print: /mnt/media is a mountpoint
```

The `nofail` option ensures the machine boots even if the drive is temporarily unplugged.

---

## Quick Start (Fresh Machine)

```bash
# 1. Clone the repo
git clone git@github.com:kaungkhantko/self_hosted.git
cd self_hosted

# 2. Create your .env from the template
cp .env.example .env
nano .env   # fill in all values

# 3. Bootstrap — creates dirs, installs systemd, pulls images, starts stack, seeds *arr
./run.sh bootstrap
```

That's it. The stack starts automatically on every boot via the installed systemd unit.

---

## Daily Commands

```bash
./run.sh status           # show running containers
./run.sh logs             # follow all logs
./run.sh logs jellyfin    # follow a specific service's logs
./run.sh up               # start stack
./run.sh down             # stop stack
./run.sh restart          # restart stack
./run.sh update           # pull latest images + restart
./run.sh help             # full command reference
```

---

## Stack Architecture

| Service | Port | Purpose |
|---------|------|---------|
| Jellyfin | 8096 | Media server |
| Sonarr | 8989 | TV show manager |
| Radarr | 7878 | Movie manager |
| Bazarr | 6767 | Subtitle manager |
| Prowlarr | 9696 | Indexer aggregator |
| qBittorrent | 8082 | Torrent client (via Mullvad VPN) |
| Jellyseerr | 5055 | Media request portal |
| Immich | 2283 | Photo management |
| Navidrome | 4533 | Music streaming |
| Vaultwarden | 8089 | Password manager |
| Calibre-Web | 8083 | Book library |
| Readarr | 8787 | Book manager |
| Lidarr | 8686 | Music manager |
| n8n | 5678 | Workflow automation |
| ntfy | 2586 | Push notifications |
| Uptime Kuma | 3001 | Monitoring |
| Homer | 7575 | Dashboard |
| Caddy | 80/443 | Reverse proxy |
| Gluetun | — | Mullvad WireGuard VPN |
| media-watcher | — | Watch-while-downloading bridge |
| subtitle-cron | — | Daily subtitle downloader |

See [docs/services.md](docs/services.md) for full details.

---

## GPU Support

GPU is **off by default**. To enable NVIDIA GPU (Jellyfin NVENC transcoding + Immich CUDA):

```bash
# In .env, change:
COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml
```

Requires NVIDIA drivers and NVIDIA Container Toolkit on the host.

---

## One-Time Setup Scripts

After bootstrap, these scripts are available for post-install tasks:

- `scripts/preflight.py` — Organizes loose movie files into per-movie subdirs (required by Radarr)
- `scripts/import_to_arr.py` — Seeds Sonarr/Radarr with your existing media library

Bootstrap runs them automatically. To re-run manually:
```bash
python3 scripts/preflight.py
python3 scripts/import_to_arr.py
```

See [docs/scripts.md](docs/scripts.md) for details.

---

## Repo Structure

```
self_hosted/
├── README.md                 # this file
├── run.sh                    # CLI entrypoint
├── docker-compose.yml        # base stack
├── docker-compose.gpu.yml    # GPU overlay (opt-in)
├── .env.example              # env template
├── scripts/                  # bootstrap + utility scripts
├── media-watcher/            # watch-while-downloading service
├── subtitle-cron/            # containerized subtitle downloader
├── caddy/                    # reverse proxy config
├── systemd/                  # systemd unit file
├── n8n-workflows/            # n8n workflow exports
└── docs/                     # documentation
```
