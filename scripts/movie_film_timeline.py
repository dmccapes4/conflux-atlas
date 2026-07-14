"""Shared director timeline for the alpha film.

Single source of truth for the caption texts AND the pacing rule:
narration leads, picture follows. The narration script synthesizes each
cue at natural speed, measures it, and writes film/narration_timing.json;
build_script() then gives every caption a window of
(measured audio + GAP seconds of silence), so lines can never overlap
and there is always a beat of quiet between them. Without a timing file
(render-only dry runs) durations are estimated from a chars/sec rate.

Year motion is attached to the same windows, so slower narration
automatically slows the simulation.
"""

from __future__ import annotations

GAP = 1.1          # silence between narration lines (s)
CHARS_PER_SEC = 11.5  # fallback estimate when no timing file exists
MIN_CUE = 2.5


class Timeline:
    def __init__(self, durations: list[float] | None):
        self.durations = durations or []
        self.i = 0          # cue index (order of say() calls)
        self.t = 0.0        # wall clock (s)
        self.year = 1900.0
        self.captions: list[tuple[float, float, str]] = []
        self.year_segments: list[tuple[float, float, float, float]] = []

    def _dur(self, text: str) -> float:
        if self.i < len(self.durations):
            return float(self.durations[self.i])
        return max(MIN_CUE, len(text) / CHARS_PER_SEC)

    def say(self, text: str, year_to: float | None = None, extra: float = 0.0):
        """Narrated beat: caption for the audio's length, then GAP of quiet.

        If year_to is given the clock glides there across the whole window
        (audio + gap + extra); otherwise the year holds.
        """
        d = self._dur(text)
        self.i += 1
        start, end = self.t, self.t + d
        window = d + GAP + extra
        self.captions.append((start, end, text))
        y1 = self.year if year_to is None else float(year_to)
        self.year_segments.append((start, start + window, self.year, y1))
        self.year = y1
        self.t = start + window
        return start, start + window

    def travel(self, year_to: float, min_s: float = 3.0, max_s: float = 8.0):
        """Silent glide to a year; duration scales with the gap in years."""
        span = abs(float(year_to) - self.year)
        d = max(min_s, min(max_s, span * 0.35))
        self.year_segments.append((self.t, self.t + d, self.year, float(year_to)))
        self.year = float(year_to)
        self.t += d

    def hold(self, seconds: float):
        self.year_segments.append((self.t, self.t + seconds, self.year, self.year))
        self.t += seconds


def build_script(atlas: dict, durations: list[float] | None = None) -> dict:
    """Captions, year segments, scene/effect windows, total duration."""
    beacons = atlas["tour_beacons"]  # 1923 / 1948 / 1975 / 1979 / 2011
    tl = Timeline(durations)
    scenes: dict[str, tuple[float, float]] = {}

    # --- intro (map frozen at 1900) ---
    g0 = tl.t
    tl.say(
        "This is a real map — Morocco to Iran, Europe down to the Sahel. "
        "Demographics here get argued endlessly, but almost nobody keeps "
        "score. Conflux Atlas tracks religious shares and migrations as "
        "claims that can be settled later."
    )
    greyout = (g0 + 2.5, g0 + 6.5)  # veil breathes in during the first line

    tl.say(
        "Everything outside the desk fades to grey: out of scope, on "
        "purpose. Outlines mix Muslim red, Christian green, Jewish blue. "
        "Fill brightness is confidence — bright means a recent citation."
    )
    tl.say(
        "One mechanism matters. A source claims Egypt stays at least ninety "
        "percent Muslim through twenty twenty. Years later a census band "
        "arrives — hit or miss. Only then does that source's trust move. "
        "Recording is free; settlement moves belief."
    )

    # --- engine on: 1900 → 1920 across the whole line, slowly ---
    tl.say(
        "Starting the clock at nineteen hundred. Fills dim between anchors "
        "— that is honesty, not a rendering bug.",
        year_to=1920, extra=3.0,
    )

    # --- panels ---
    d0 = tl.t
    tl.say(
        "The data desk, with no map poetry: population, confidence, and "
        "shares per polity, held from the last cited anchor.",
        extra=3.0,
    )
    scenes["data"] = (d0, tl.t)

    s0 = tl.t
    tl.say(
        "And the scorekeeper: trust posteriors per source. Watch belief "
        "move only when outcomes land — alpha up on a hit, beta up on a "
        "miss. Run enough census rounds and you get a calibrated ledger of "
        "who to believe about demography.",
        extra=4.0,
    )
    scenes["sources"] = (s0, tl.t)

    tl.say(
        "Back to the map for the part history remembers: five events, "
        "nineteen twenty-three to twenty eleven.",
        year_to=1921,
    )

    # --- beacon walk: silent travel, then linger through the narration ---
    for b in beacons:
        tl.travel(float(b["year"]))
        tl.say(f"{b['title']}. {b['blurb']}", year_to=float(b["year"]) + 4.0, extra=2.0)

    # --- catch up and close ---
    tl.say("Rolling forward to the present day.", year_to=2020, extra=8.0)

    outro = (tl.t, tl.t + 8.0)
    tl.say(
        "Alpha findings, said plainly: the map is a view over sparse "
        "citations, not a crystal ball. Shock windows hurt prediction "
        "accuracy. Settlement moves trust. And a miss on the nineteen "
        "seventy-five prediction cut is still a result."
    )
    tl.say(
        "That is the system in miniature. Conflux Atlas — a ledger of who "
        "to believe about demography."
    )
    tl.hold(2.0)

    return {
        "captions": tl.captions,
        "year_segments": tl.year_segments,
        "scenes": scenes,
        "greyout": greyout,
        "outro": outro,
        "duration": tl.t,
    }
