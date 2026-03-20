# Retired Services

These services were previously part of the stack but are no longer active. Their data directories are retained on disk.

---

## Nextcloud

**Status:** Retired (removed from compose)
**Data directories:** `./nextcloud_data/`, `./nextcloud_db/`
**Why retired:** Replaced by a combination of Immich (photos) and other services. Nextcloud's overhead wasn't justified for personal use.
**Stale env vars removed:** `NEXTCLOUD_DB`, `NEXTCLOUD_USER`, `NEXTCLOUD_PASSWORD`

**To clean up when ready:**
```bash
# Only do this if you are certain you no longer need the data
sudo rm -rf /home/kaung/self_hosted/nextcloud_data
sudo rm -rf /home/kaung/self_hosted/nextcloud_db
```

---

## PhotoPrism

**Status:** Retired (removed from compose)
**Data directory:** `./photoprism/`
**Why retired:** Replaced by Immich, which has better mobile app support and performance.

**To clean up when ready:**
```bash
sudo rm -rf /home/kaung/self_hosted/photoprism
```

---

## Homarr

**Status:** Referenced in old `pull-images.sh` but never in compose
**Data directory:** `./homarr/`
**Why retired:** Homer is used instead.

**To clean up when ready:**
```bash
sudo rm -rf /home/kaung/self_hosted/homarr
```
