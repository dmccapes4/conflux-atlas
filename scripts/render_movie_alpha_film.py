#!/usr/bin/env python3
"""Render the alpha movie to a .mov — same pipeline as ogre-work-intelligence.

Offline, fixed-step render (no wall clock): headless pygame draws the same
visual language as the browser player (Natural Earth basemap, grey-out,
confidence fills, gamma RGB strokes, migration arcs, beacon halos, diaspora
chips) on a scripted director timeline, and every frame is piped to
imageio's bundled ffmpeg (H.264 / yuv420p). No system ffmpeg needed.

Narration leads, picture follows: the caption texts and pacing rule live
in scripts/movie_film_timeline.py, and scripts/build_movie_narration.py
must run FIRST — it synthesizes each cue, measures it, and writes
film/narration_timing.json; this renderer rebuilds the same timeline
from those measured durations, so captions and year motion sit exactly
under the voice. scripts/mux_movie_alpha.py then marries them.

Usage:
  python scripts/render_movie_alpha_film.py [--out movie-alpha/film/conflux-alpha.mov]
                                            [--fps 30]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np  # noqa: E402
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from movie_film_timeline import build_script  # noqa: E402
ATLAS = ROOT / "movie-alpha" / "data" / "atlas.json"
WORLD = ROOT / "movie-alpha" / "assets" / "world_frame.json"

W, H = 1480, 940  # even dims (macro_block_size=2), like the ogre demo

GROUP_RGB = {
    "muslim": (196, 68, 68),
    "christian": (74, 168, 120),
    "jewish": (72, 140, 200),
    "unaffiliated": (120, 130, 140),
    "other": (150, 110, 170),
}
GOLD = (226, 184, 106)
INK = (232, 238, 244)
INK_DIM = (138, 154, 171)


# ---------------------------------------------------------------------------
# Director timeline — captions are the narration source of truth
# ---------------------------------------------------------------------------


def load_timing() -> list[float] | None:
    """Measured cue durations from build_movie_narration.py, if it has run.

    With the timing file, captions and year motion sit on the exact clock
    the narration was laid out on; without it (render-only dry run) the
    timeline falls back to a chars/sec estimate and the picture may drift
    from a later narration pass.
    """
    p = ROOT / "movie-alpha" / "film" / "narration_timing.json"
    if not p.exists():
        print("⚠️  no narration_timing.json — using estimated cue durations "
              "(run build_movie_narration.py first for a locked A/V clock)")
        return None
    return [float(d) for d in json.loads(p.read_text(encoding="utf-8"))["durations"]]


def year_at(tsec: float, segments) -> float:
    for t0, t1, y0, y1 in segments:
        if t0 <= tsec <= t1:
            k = 0.0 if t1 == t0 else (tsec - t0) / (t1 - t0)
            return y0 + (y1 - y0) * k
    return segments[-1][3]


# ---------------------------------------------------------------------------
# Geometry / drawing helpers
# ---------------------------------------------------------------------------


class Frame:
    """uv → screen mapping with the basemap's true aspect, letterboxed."""

    def __init__(self, world: dict, w: int, h: int):
        aspect = world.get("aspect", 1.34)
        fw, fh = w, w / aspect
        if fh > h:
            fh, fw = h, h * aspect
        self.ox = (w - fw) / 2
        self.oy = (h - fh) / 2
        self.w = fw
        self.h = fh

    def px(self, uv) -> tuple[float, float]:
        return (self.ox + uv[0] * self.w, self.oy + uv[1] * self.h)


def poly_points(ring, fr: Frame):
    return [fr.px(p) for p in ring]


def draw_country(layer, rings, fr, fill=None, stroke=None, width=1):
    for ring in rings:
        pts = poly_points(ring, fr)
        if len(pts) < 3:
            continue
        if fill:
            pygame.draw.polygon(layer, fill, pts)
        if stroke:
            pygame.draw.polygon(layer, stroke, pts, max(1, int(width)))


def bezier(a, c, b, n=28):
    out = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t * t * b[0]
        y = (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t * t * b[1]
        out.append((x, y))
    return out


def wrap_text(font, text, max_w):
    words = text.split()
    lines, cur = [], ""
    for w_ in words:
        probe = (cur + " " + w_).strip()
        if font.size(probe)[0] <= max_w:
            cur = probe
        else:
            if cur:
                lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


class FilmRenderer:
    def __init__(self, atlas: dict, world: dict, fps: int):
        self.atlas = atlas
        self.world = world
        self.fps = fps
        self.script = build_script(atlas, load_timing())
        self.fr = Frame(world, W, H)
        self.polity_country = {c["polity_id"]: c for c in world["countries"] if c["polity_id"]}
        self.chip_uv = {c["polity_id"]: c["uv"] for c in world.get("chips", [])}
        self.arc_birth: dict[str, float] = {}

        pygame.font.init()
        self.f_label = pygame.font.SysFont("dejavusans", 13, bold=True)
        self.f_label_sm = pygame.font.SysFont("dejavusans", 10, bold=True)
        self.f_caption = pygame.font.SysFont("dejavusans", 21)
        self.f_phase = pygame.font.SysFont("dejavusansmono", 14)
        self.f_hud = pygame.font.SysFont("dejavusansmono", 22, bold=True)
        self.f_panel = pygame.font.SysFont("dejavusans", 16)
        self.f_panel_sm = pygame.font.SysFont("dejavusansmono", 12)

        # prerender lit + fully-dimmed out-of-scope land for cheap grey-out mix
        self.base_lit = self._render_base(dim=0.42)
        self.base_dim = self._render_base(dim=0.12)

    def _render_base(self, dim: float) -> pygame.Surface:
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        for c in self.world["countries"]:
            if c["polity_id"]:
                continue
            fill = (52, 62, 70, int(255 * dim))
            stroke = (70, 82, 92, int(255 * max(0.08, dim * 0.55)))
            draw_country(s, c["rings"], self.fr, fill=fill, stroke=stroke, width=1)
        return s

    # --- data access ---
    def node_frame(self, year: float) -> dict:
        y = int(round(year))
        frames = self.atlas["frames"]
        for probe in range(0, 6):
            for cand in (y - probe, y + probe):
                if str(cand) in frames:
                    return frames[str(cand)]
        return frames[sorted(frames)[-1]]

    def anchor(self, pid):
        if pid in self.polity_country:
            return self.fr.px(self.polity_country[pid]["label_uv"])
        if pid in self.chip_uv:
            return self.fr.px(self.chip_uv[pid])
        return None

    def active_event(self, year: float):
        for e in self.atlas.get("events", []):
            if e["year"] <= year <= (e.get("year_end") or e["year"] + 3):
                return e
        return None

    # --- main frame draw ---
    def draw(self, screen: pygame.Surface, tsec: float):
        sc = self.script
        year = year_at(tsec, sc["year_segments"])
        fr_data = self.node_frame(year)
        g0, g1 = sc["greyout"]
        greyout = min(1.0, max(0.0, (tsec - g0) / (g1 - g0)))
        o0, o1 = sc["outro"]
        darken = min(1.0, max(0.0, (tsec - o0) / (o1 - o0)))

        screen.fill((10, 17, 24))
        # out-of-scope land: crossfade lit → dim as the veil breathes in
        screen.blit(self.base_lit, (0, 0))
        if greyout > 0:
            veil = self.base_dim.copy()
            veil.set_alpha(int(255 * greyout))
            screen.blit(veil, (0, 0))
            shade = pygame.Surface((W, H), pygame.SRCALPHA)
            shade.fill((8, 12, 16, int(70 * greyout)))
            screen.blit(shade, (0, 0))

        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        ev = self.active_event(year)
        ev_pols = set(ev.get("polities") or []) if ev else set()

        # desk polities
        for pid, c in self.polity_country.items():
            n = fr_data["nodes"].get(pid)
            if not n:
                draw_country(layer, c["rings"], self.fr, fill=(60, 72, 82, 90))
                continue
            conf = max(0.2, n["confidence"])
            r, g, b = (int(v * 255) for v in n["rgb"])
            if darken > 0:
                r = int(r * (1 - darken) + 40 * darken)
                g = int(g * (1 - darken) + 44 * darken)
                b = int(b * (1 - darken) + 48 * darken)
            if pid in ev_pols and darken == 0:
                halo = 0.5 + 0.5 * math.sin(tsec * 5.0)
                draw_country(layer, c["rings"], self.fr, stroke=(*GOLD, int(200 * halo)), width=5)
            fill_a = int(255 * (0.10 + 0.24 * conf))
            pulse = 1 + min(
                0.9,
                n["velocity"] * 14 + min(0.45, abs(n["net_migration"]) / 8e5),
            ) * (0.5 + 0.5 * math.sin(tsec * 4.0 + len(pid)))
            draw_country(
                layer, c["rings"], self.fr,
                fill=(r, g, b, fill_a),
                stroke=(r, g, b, int(255 * (0.55 + 0.4 * conf))),
                width=1.1 * pulse + 0.4,
            )

        # arcs
        live = set()
        for e in fr_data["edges"]:
            if e["alpha"] < 0.05:
                continue
            a = self.anchor(e["from"])
            b = self.anchor(e["to"])
            if not a or not b:
                continue
            live.add(e["id"])
            if e["id"] not in self.arc_birth:
                self.arc_birth[e["id"]] = tsec
            sweep = min(1.0, (tsec - self.arc_birth[e["id"]]) / 1.2)
            mx = (a[0] + b[0]) / 2
            my = (a[1] + b[1]) / 2 - 26 - min(70, math.log10(e["volume"] + 10) * 10)
            col = GROUP_RGB.get(e["group"], (180, 180, 180))
            pts = bezier(a, (mx, my), b)
            n_pts = max(2, int(len(pts) * sweep))
            alpha = int(255 * (0.2 + 0.5 * e["alpha"]) * (1 - darken))
            width = int(1 + min(5, math.log10(e["volume"] + 10) - 1))
            pygame.draw.lines(layer, (*col, alpha), False, pts[:n_pts], max(1, width))
            if sweep < 1:
                hx, hy = pts[n_pts - 1]
                pygame.draw.circle(layer, (*col, 230), (int(hx), int(hy)), 3)
        for k in list(self.arc_birth):
            if k not in live:
                del self.arc_birth[k]

        # labels
        max_pop = max((n["pop"] for n in fr_data["nodes"].values()), default=1)
        for pid, c in self.polity_country.items():
            n = fr_data["nodes"].get(pid)
            if not n:
                continue
            x, y = self.fr.px(c["label_uv"])
            big = n["pop"] / max_pop > 0.25
            font = self.f_label if big else self.f_label_sm
            img = font.render(n["name"], True, INK)
            img.set_alpha(int(255 * (0.85 - 0.6 * darken)))
            layer.blit(img, img.get_rect(center=(x, y)))

        # diaspora chips
        for chip in self.world.get("chips", []):
            n = fr_data["nodes"].get(chip["polity_id"])
            if not n:
                continue
            x, y = self.fr.px(chip["uv"])
            r, g, b = (int(v * 255) for v in n["rgb"])
            rect = pygame.Rect(int(x - 10), int(y - 13), 96, 26)
            pygame.draw.rect(layer, (16, 24, 32, 215), rect, border_radius=6)
            pygame.draw.rect(layer, (r, g, b, 235), rect, width=1, border_radius=6)
            pygame.draw.circle(layer, (r, g, b, 240), (int(x + 2), int(y)), 3)
            img = self.f_label_sm.render(chip["name"], True, INK)
            layer.blit(img, (x + 10, y - 6))

        screen.blit(layer, (0, 0))

        # scene panels
        d0, d1 = sc["scenes"]["data"]
        s0, s1 = sc["scenes"]["sources"]
        if d0 <= tsec <= d1:
            self._panel_data(screen, fr_data)
        elif s0 <= tsec <= s1:
            self._panel_sources(screen, (tsec - s0) / (s1 - s0))

        # outro veil
        if darken > 0:
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((5, 8, 11, int(150 * darken)))
            screen.blit(veil, (0, 0))

        self._chrome(screen, tsec, year, ev)

    # --- overlay panels (starved views, PLAN §3.4) ---
    def _panel_data(self, screen, fr_data):
        panel = pygame.Surface((W, H), pygame.SRCALPHA)
        rect = pygame.Rect(W // 2 - 390, 90, 780, 520)
        pygame.draw.rect(panel, (10, 16, 22, 235), rect, border_radius=14)
        pygame.draw.rect(panel, (60, 80, 96, 255), rect, width=1, border_radius=14)
        title = self.f_panel.render("Data desk — featured polities (cold readout)", True, INK)
        panel.blit(title, (rect.x + 24, rect.y + 18))
        feats = ["egypt", "turkey", "iran", "israel", "lebanon", "syria", "saudi_arabia", "iraq"]
        y = rect.y + 58
        for pid in feats:
            n = fr_data["nodes"].get(pid)
            if not n:
                continue
            name = self.f_panel.render(n["name"], True, INK)
            panel.blit(name, (rect.x + 24, y))
            meta = self.f_panel_sm.render(
                f"pop {n['pop'] / 1e6:5.1f}M   conf {n['confidence']:.2f}   anchor {n['anchor_year']}",
                True, INK_DIM,
            )
            panel.blit(meta, (rect.x + 190, y + 3))
            bx, bw = rect.x + 480, 270
            x = bx
            for grp in ("muslim", "christian", "jewish"):
                share = n["shares"].get(grp) or 0
                seg = int(bw * share)
                if seg:
                    pygame.draw.rect(panel, GROUP_RGB[grp], (x, y + 2, seg, 14))
                    x += seg
            pygame.draw.rect(panel, (60, 80, 96), (bx, y + 2, bw, 14), width=1)
            y += 54
        screen.blit(panel, (0, 0))

    def _panel_sources(self, screen, k: float):
        tape = self.atlas.get("settlement_tape", [])
        steps = min(len(tape), 6)
        idx = min(steps - 1, int(k * (steps + 1)) - 1) if steps else -1
        snapshot = tape[idx]["snapshot"] if idx >= 0 else {}
        if idx < 0 and tape:
            snapshot = {h: {"alpha": 1, "beta": 1, "mean": 0.5} for h in list(tape[0]["snapshot"])[:5]}

        panel = pygame.Surface((W, H), pygame.SRCALPHA)
        rect = pygame.Rect(W // 2 - 390, 90, 780, 520)
        pygame.draw.rect(panel, (10, 16, 22, 235), rect, border_radius=14)
        pygame.draw.rect(panel, (60, 80, 96, 255), rect, width=1, border_radius=14)
        title = self.f_panel.render("Source weighting — settlement moves belief", True, INK)
        panel.blit(title, (rect.x + 24, rect.y + 18))

        y = rect.y + 62
        for hid, p in list(sorted(snapshot.items(), key=lambda kv: -kv[1]["mean"]))[:5]:
            name = hid.replace("source_trust:", "")[:38]
            img = self.f_panel_sm.render(name, True, INK)
            panel.blit(img, (rect.x + 24, y))
            bw = 420
            pygame.draw.rect(panel, (26, 38, 50), (rect.x + 24, y + 18, bw, 12))
            pygame.draw.rect(panel, (92, 184, 168), (rect.x + 24, y + 18, int(bw * p["mean"]), 12))
            stats = self.f_panel_sm.render(
                f"E[θ]={p['mean']:.3f}  α={p['alpha']:.1f} β={p['beta']:.1f}", True, INK_DIM
            )
            panel.blit(stats, (rect.x + 460, y + 14))
            y += 58
        if idx >= 0:
            step = tape[idx]
            verdict = "HIT " if step["success"] else "MISS"
            col = (92, 184, 130) if step["success"] else (196, 92, 92)
            img = self.f_panel_sm.render(
                f"[{step['t']}] {verdict} w={step['weight']}  {step['hypothesis_id'].replace('source_trust:', '')}",
                True, col,
            )
            panel.blit(img, (rect.x + 24, rect.y + 470 - 62))
            note = self.f_panel_sm.render(str(step["note"])[:86], True, INK_DIM)
            panel.blit(note, (rect.x + 24, rect.y + 470 - 40))
        screen.blit(panel, (0, 0))

    # --- chrome: HUD, captions, attribution ---
    def _chrome(self, screen, tsec, year, ev):
        chip = pygame.Surface((150, 44), pygame.SRCALPHA)
        pygame.draw.rect(chip, (10, 16, 22, 210), chip.get_rect(), border_radius=10)
        img = self.f_hud.render(str(int(round(year))), True, GOLD)
        chip.blit(img, img.get_rect(center=(75, 22)))
        screen.blit(chip, (W - 170, 18))

        brand = self.f_phase.render("CONFLUX ATLAS · alpha build — not posterior", True, INK_DIM)
        screen.blit(brand, (20, 20))
        if ev:
            evimg = self.f_phase.render(ev["title"][:70], True, GOLD)
            screen.blit(evimg, (20, 42))

        cap = next(
            (c for c in self.script["captions"] if c[0] <= tsec <= c[1]), None
        )
        if cap:
            lines = wrap_text(self.f_caption, cap[2], W - 320)
            band_h = 26 * len(lines) + 26
            band = pygame.Surface((W, band_h), pygame.SRCALPHA)
            band.fill((6, 10, 14, 190))
            screen.blit(band, (0, H - band_h))
            y = H - band_h + 12
            for ln in lines:
                img = self.f_caption.render(ln, True, INK)
                screen.blit(img, img.get_rect(midtop=(W // 2, y)))
                y += 26

        att = self.f_panel_sm.render("Basemap: Natural Earth (public domain)", True, (138, 154, 171))
        att.set_alpha(120)
        screen.blit(att, (12, H - 20))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "movie-alpha" / "film" / "conflux-alpha.mov"))
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()

    import imageio.v2 as imageio

    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    world = json.loads(WORLD.read_text(encoding="utf-8"))

    pygame.display.init()
    screen = pygame.Surface((W, H))
    r = FilmRenderer(atlas, world, args.fps)
    duration = r.script["duration"]
    total = int(duration * args.fps)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(
        str(out), fps=args.fps, codec="libx264", quality=8,
        macro_block_size=2, ffmpeg_log_level="error",
        output_params=["-pix_fmt", "yuv420p"],
    )
    print(f"🎬 rendering {total} frames ({duration:.0f}s @ {args.fps}fps) → {out}")
    for i in range(total):
        t = i / args.fps
        r.draw(screen, t)
        buf = pygame.image.tostring(screen, "RGB")
        arr = np.frombuffer(buf, dtype=np.uint8).reshape((H, W, 3))
        writer.append_data(arr)
        if i % (args.fps * 10) == 0:
            print(f"  ⏱️  {t:5.1f}s / {duration:.0f}s", flush=True)
    writer.close()
    print(f"✅ wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
    # narration timeline handshake
    meta = {"duration": duration, "captions": r.script["captions"]}
    (out.parent / "film_script.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"💾 wrote {out.parent / 'film_script.json'} (caption timeline for narration)")


if __name__ == "__main__":
    sys.exit(main())
