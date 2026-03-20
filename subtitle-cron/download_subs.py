#!/usr/bin/env python3
"""
Batch subtitle downloader for unmanaged content.
Uses OpenSubtitles v1 (XMLRPC) via subliminal.
Skips files that already have English subtitles (embedded or external).
"""
import os
import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)

from babelfish import Language
from subliminal import scan_video, download_best_subtitles, save_subtitles, region
from subliminal.video import Episode, Movie

# Configure cache — use /tmp inside the container
region.configure('dogpile.cache.dbm', arguments={'filename': '/tmp/subliminal.dbm'})

PROVIDERS = ['opensubtitles']
LANG = {Language('eng')}
VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.m4v'}

def has_english_sub(path):
    """Check if an external English .srt/.ass already exists next to the video."""
    p = Path(path)
    for ext in ['.en.srt', '.eng.srt', '.en.ass', '.srt']:
        if (p.parent / (p.stem + ext)).exists():
            return True
    return False

def process_directory(root_dir):
    videos = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip Extras, Featurettes, Subs subdirectories
        dirnames[:] = [d for d in dirnames if d.lower() not in ('extras', 'featurettes', 'subs', 'sample', 'samples', 'bonus')]
        for fname in filenames:
            if Path(fname).suffix.lower() in VIDEO_EXTENSIONS:
                fpath = os.path.join(dirpath, fname)
                if has_english_sub(fpath):
                    log.info(f'SKIP (has srt): {fname}')
                    continue
                try:
                    v = scan_video(fpath)
                    if v.subtitle_languages and Language('eng') in v.subtitle_languages:
                        log.info(f'SKIP (embedded eng): {fname}')
                        continue
                    videos.append(v)
                except Exception as e:
                    log.warning(f'ERROR scanning {fname}: {e}')
    return videos

def main():
    if not sys.argv[1:]:
        print("Usage: download_subs.py <dir1> [dir2] ...")
        sys.exit(1)
    dirs = sys.argv[1:]

    all_videos = []
    for d in dirs:
        log.info(f'Scanning {d}...')
        vids = process_directory(d)
        log.info(f'Found {len(vids)} videos needing subs in {d}')
        all_videos.extend(vids)

    log.info(f'Total: {len(all_videos)} videos to process')

    # Process in batches to avoid rate limiting
    batch_size = 20
    total_downloaded = 0

    for i in range(0, len(all_videos), batch_size):
        batch = all_videos[i:i+batch_size]
        log.info(f'Processing batch {i//batch_size + 1}/{(len(all_videos)+batch_size-1)//batch_size} ({len(batch)} videos)...')

        try:
            subtitles = download_best_subtitles(batch, LANG, providers=PROVIDERS)
            for video, subs in subtitles.items():
                if subs:
                    saved = save_subtitles(video, subs)
                    total_downloaded += len(saved)
                    log.info(f'DOWNLOADED: {Path(video.name).name} -> {[s.language for s in saved]}')
                else:
                    log.info(f'NOT FOUND: {Path(video.name).name}')
        except Exception as e:
            log.error(f'Batch error: {e}')

        log.info(f'Progress: {total_downloaded} downloaded so far')

    log.info(f'Done! Total downloaded: {total_downloaded}')

if __name__ == '__main__':
    main()
