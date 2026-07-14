#!/usr/bin/env python3
"""Mux the alpha film: silent .mov + narration.wav → narrated .mp4 + .m4a.

Same output set as ogre-work-intelligence (mov master, mp4 for feeds,
m4a audio track), using the ffmpeg binary bundled by imageio-ffmpeg —
no system ffmpeg needed.

Usage:
  python scripts/mux_movie_alpha.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILM = ROOT / "movie-alpha" / "film"
MOV = FILM / "conflux-alpha.mov"
WAV = FILM / "narration.wav"
MP4 = FILM / "conflux-alpha-narrated.mp4"
M4A = FILM / "conflux-alpha-narration.m4a"


def ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd: list[str]) -> None:
    print("  $", " ".join(str(c) for c in cmd[1:]))
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> int:
    for p in (MOV, WAV):
        if not p.exists():
            sys.exit(f"missing {p} — run the render/narration scripts first")
    exe = ffmpeg()

    print("🔊 mux narrated mp4")
    run([
        exe, "-y", "-i", str(MOV), "-i", str(WAV),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        "-shortest",
        str(MP4),
    ])
    print("🎧 extract m4a narration track")
    run([
        exe, "-y", "-i", str(WAV),
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(M4A),
    ])
    for p in (MOV, MP4, M4A):
        print(f"✅ {p.relative_to(ROOT)}  {p.stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
