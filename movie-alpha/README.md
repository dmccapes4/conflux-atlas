# Conflux Atlas — Alpha Movie

Two artifacts, one atlas:

1. **Interactive player** (`index.html`, served) — a live walk-through for
   showing people in the room: guided tour with Continue gates at each
   beacon, free scrubbing, tabbed Data / Source-weighting views, Web Speech
   narration.
2. **Film export** (`film/`) — shareable `.mov` / `.mp4` / `.m4a`, rendered
   offline with the same pipeline as ogre-work-intelligence
   (headless pygame → imageio ffmpeg → Piper narration → mux).

## Interactive player

From repo root:

```bash
make movie-alpha-export    # rebuild movie-alpha/data/atlas.json from the model
make movie-alpha-basemap   # rebuild assets/world_frame.json from Natural Earth
make movie-alpha           # serve (reuses an existing movie server if already up)
```

Open the URL → **Start tour** (allow voice if prompted). The tour hard-stops
at each historical beacon with **Continue / Replay** buttons; scrubbing the
timeline pauses the tour and keeps it resumable. Or skip the tour and drive
manually: speed presets 0.5×–4×, `Space` play/pause, tabs for data/sources.

Keys: `Space` play/pause · on Source weighting: `n` next settlement · `r` reset tape.

### Tabs

1. **Map** — real Natural Earth geography (Morocco→Iran, Europe→Sahel).
   Out-of-scope land greys out; desk polities get gamma RGB outlines
   (Muslim red / Christian green / Jewish blue), fill opacity = confidence,
   stroke pulse = share velocity + |net migration|; arcs = migration edges;
   US/Canada as diaspora chips.
2. **Data** — 8 featured polity cards (toggle to all 28); click for
   histograms + share timelines + hold-model math.
3. **Source weighting** — 5 trust bars + settlement feed (evidence loop).

## Film export (mov / mp4 / m4a)

```bash
make movie-alpha-film
```

Produces in `film/`:

- `conflux-alpha.mov` — silent H.264 master (fixed-step offline render, 30fps)
- `conflux-alpha-narrated.mp4` — narrated feed cut (aac, faststart)
- `conflux-alpha-narration.m4a` — narration track alone
- `film_script.json` — the caption timeline (single source of truth: the
  renderer writes it, the narration script reads it)

Narration is offline Piper TTS (default: male `en_US-ryan-high` from the
ogre voices folder; pass `--voice` to `scripts/build_movie_narration.py`
for any other `.onnx`). No system ffmpeg needed — mux uses the binary
bundled by `imageio-ffmpeg`.

## Tour / film spine

Intro (map frozen, grey veil breathes in) → map language → dummy settlement →
engine on → data desk → source scoreboard → beacon walk
(1923 / 1948 / 1975 / 1979 / 2011) → catch-up to 2020 → dark outro + findings.

## Honesty

- Numeric desk starts ~1900; older beacons are narrative markers.
- Shares **hold** between anchors; event deltas rewrite nodes when edges fire.
- Syria volumes are UNHCR **stocks**, not flows.
- Basemap geometry: Natural Earth (public domain), 50m admin-0.
- Player voice uses the browser's speech engine; film voice is local Piper.
