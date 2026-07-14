#!/usr/bin/env python3
"""Synthesize the alpha-film narration with a local Piper voice.

Narration leads, picture follows: every cue is synthesized once at
natural speaking pace and measured, the shared timeline
(movie_film_timeline.build_script) is rebuilt from those measured
durations — each line gets its audio length plus a beat of silence —
and only then is the master wav laid out. No cue can overlap the next
by construction. The measured durations go to film/narration_timing.json
so render_movie_alpha_film.py draws captions/year-motion on the exact
same clock.

Run this BEFORE the renderer (make movie-alpha-film does).

Default voice is the male en_US-ryan-high from the ogre voices folder
(PLAN: "suitable male voice"); pass --voice for any Piper .onnx.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import wave
from pathlib import Path

import numpy as np
from piper import PiperVoice
from piper.config import SynthesisConfig

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from movie_film_timeline import build_script  # noqa: E402

FILM = ROOT / "movie-alpha" / "film"
ATLAS = ROOT / "movie-alpha" / "data" / "atlas.json"
SR = 22050

# Spoken-form fixups. Caption text comes from two places — hand-written
# cues in movie_film_timeline.py AND beacon blurbs straight out of
# atlas.json — so every symbol that could reach the synthesizer needs a
# mapping here (espeak reads unknown glyphs literally: "↔" becomes
# "left right arrow").
REPLACEMENTS = [
    (r"\(.*?\)", ""),               # drop visual asides
    ("MENA", "the Middle East and North Africa"),
    ("UNHCR", "U N H C R"),
    ("≥", " at least "),
    ("≤", " at most "),
    ("≠", ", not "),                # "stocks ≠ flows" → "stocks, not flows"
    ("≈", " roughly "),
    ("α", "alpha"),
    ("β", "beta"),
    ("θ", "theta"),
    ("↔", " and "),                 # "Greece ↔ Turkey" → "Greece and Turkey"
    ("→", " to "),                  # "origin→Israel" → "origin to Israel"
    ("←", " from "),
    ("&", " and "),
    ("%", " percent"),
    ("—", ", "),
    ("–", ", "),
    ("·", ", "),
    ("…", ". "),
]

_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen",
]
_TENS = ["", "ten", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety"]


def _two(n: int) -> str:
    if n < 20:
        return _ONES[n]
    t, o = divmod(n, 10)
    return _TENS[t] + ("-" + _ONES[o] if o else "")


def _year_words(m: re.Match) -> str:
    """1948 → nineteen forty-eight; 2011 → twenty eleven; 1900 → nineteen hundred."""
    y = int(m.group())
    hi, lo = divmod(y, 100)
    if hi == 20 and lo == 0:
        return "two thousand"
    if lo == 0:
        return f"{_two(hi)} hundred"
    if hi == 20 and lo < 10:
        return f"two thousand {_ONES[lo]}"
    if lo < 10:
        return f"{_two(hi)} oh {_ONES[lo]}"
    return f"{_two(hi)} {_two(lo)}"


def clean(text: str) -> str:
    for pat, rep in REPLACEMENTS:
        if pat.startswith("\\") or ".*" in pat:
            text = re.sub(pat, rep, text)
        else:
            text = text.replace(pat, rep)
    text = re.sub(r"\b(1[89]|20)\d{2}\b", _year_words, text)
    # catch-all: any glyph without a mapping becomes a pause, never a
    # spelled-out symbol name
    text = re.sub(r"[^\x20-\x7e]", " ", text)
    leftover = re.findall(r"[~^_|<>#*+=/{}\[\]\\]", text)
    if leftover:
        print(f"  ⚠️  unmapped symbols dropped: {sorted(set(leftover))}")
        text = re.sub(r"[~^_|<>#*+=/{}\[\]\\]", " ", text)
    text = re.sub(r"\s+", " ", text).replace(" ,", ",").replace(" .", ".")
    return text.strip()


def synth(voice: PiperVoice, text: str, length_scale: float) -> np.ndarray:
    cfg = SynthesisConfig(length_scale=length_scale, normalize_audio=True)
    parts = [c.audio_int16_array for c in voice.synthesize(text, cfg)]
    if not parts:
        return np.zeros(0, dtype=np.int16)
    return np.concatenate(parts).astype(np.int16)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--voice",
        default=str(
            Path.home() / "dev" / "ogre-work-intelligence" / "voices" / "en_US-ryan-high.onnx"
        ),
    )
    ap.add_argument(
        "--pace", type=float, default=1.06,
        help="Piper length_scale: >1 is slower/calmer (default 1.06)",
    )
    ap.add_argument("--out", default=str(FILM / "narration.wav"))
    args = ap.parse_args()

    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))

    # Pass 1 — synthesize every cue at natural pace and measure it.
    texts = [c[2] for c in build_script(atlas)["captions"]]
    print(f"🗣️  loading voice {args.voice} ...")
    voice = PiperVoice.load(args.voice)
    clips: list[np.ndarray] = []
    durations: list[float] = []
    for text in texts:
        audio = synth(voice, clean(text), args.pace)
        clips.append(audio)
        durations.append(len(audio) / SR)

    # Pass 2 — rebuild the timeline from measured durations and lay out audio.
    script = build_script(atlas, durations)
    duration = float(script["duration"])
    master = np.zeros(int((duration + 1.0) * SR), dtype=np.int32)
    for (start, _end, text), audio in zip(script["captions"], clips):
        at = int(start * SR)
        stop = min(len(master), at + len(audio))
        master[at:stop] += audio[: stop - at].astype(np.int32)
        print(f"  [{start:6.1f}s] {len(audio) / SR:5.1f}s  {clean(text)[:58]}")

    master = np.clip(master, -32768, 32767).astype(np.int16)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(master.tobytes())
    print(f"✅ wrote {out}  ({len(master) / SR:.1f}s)")

    timing = out.parent / "narration_timing.json"
    timing.write_text(
        json.dumps({"pace": args.pace, "durations": durations}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"💾 wrote {timing} (render reads this for the shared clock)")


if __name__ == "__main__":
    main()
