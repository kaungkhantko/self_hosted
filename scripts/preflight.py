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
