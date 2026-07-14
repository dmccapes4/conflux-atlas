"""Pygame year-scrubber for Conflux Atlas (demo slice 1900–2025)."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Optional

import pygame

from .model import (
    RELIGION_RGB,
    YEAR_MAX,
    YEAR_MIN,
    ConfluxModel,
    RuntimeNode,
    YearView,
    layout_xy,
)

# ---- palette ------------------------------------------------------------
BG = (16, 18, 24)
PANEL = (24, 28, 36)
PANEL_HI = (32, 38, 50)
BORDER = (52, 60, 76)
TEXT = (220, 226, 234)
MUTED = (130, 140, 155)
ACCENT = (120, 190, 230)
EDGE_COL = (220, 160, 90)

WIDTH, HEIGHT = 1280, 800
TOPBAR_H = 52
BOTTOMBAR_H = 88
SIDE_W = 300
PAD = 14


def blend(fg: tuple[int, int, int], bg: tuple[int, int, int], a: float) -> tuple[int, int, int]:
    a = max(0.0, min(1.0, a))
    return (
        int(fg[0] * a + bg[0] * (1 - a)),
        int(fg[1] * a + bg[1] * (1 - a)),
        int(fg[2] * a + bg[2] * (1 - a)),
    )


def fmt_pop(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)


class SimApp:
    def __init__(
        self,
        start_year: int = 1900,
        play: bool = False,
        *,
        apply_event_deltas: bool = True,
    ) -> None:
        pygame.init()
        pygame.display.set_caption("Conflux Atlas — MENA + diaspora demography")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        self.f_title = pygame.font.SysFont("dejavusans", 22, bold=True)
        self.f_h = pygame.font.SysFont("dejavusans", 15, bold=True)
        self.f = pygame.font.SysFont("dejavusans", 13)
        self.f_sm = pygame.font.SysFont("dejavusans", 11)
        self.f_mono = pygame.font.SysFont("dejavusansmono", 14, bold=True)

        self.apply_event_deltas = apply_event_deltas
        self.model = ConfluxModel(apply_event_deltas=apply_event_deltas)
        self.year = int(max(YEAR_MIN, min(YEAR_MAX, start_year)))
        self.playing = play
        self.play_accum = 0.0
        self.years_per_sec = 8.0
        self.selected: Optional[str] = None
        self.dragging_scrub = False

        self.board = pygame.Rect(
            PAD,
            TOPBAR_H + PAD,
            WIDTH - SIDE_W - 3 * PAD,
            HEIGHT - TOPBAR_H - BOTTOMBAR_H - 3 * PAD,
        )
        self.side = pygame.Rect(
            self.board.right + PAD,
            TOPBAR_H + PAD,
            SIDE_W - PAD,
            self.board.height,
        )
        self.scrub = pygame.Rect(PAD + 80, HEIGHT - BOTTOMBAR_H + 28, WIDTH - 2 * PAD - 160, 18)

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if not self._handle(event):
                    running = False
            if self.playing:
                self.play_accum += dt * self.years_per_sec
                while self.play_accum >= 1.0:
                    self.play_accum -= 1.0
                    if self.year >= YEAR_MAX:
                        self.playing = False
                        self.year = YEAR_MAX
                    else:
                        self.year += 1
            self._draw()
            pygame.display.flip()
        pygame.quit()

    def _handle(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_q):
                return False
            if event.key == pygame.K_SPACE:
                self.playing = not self.playing
            elif event.key == pygame.K_d:
                self.apply_event_deltas = not self.apply_event_deltas
                self.model = ConfluxModel(apply_event_deltas=self.apply_event_deltas)
            elif event.key in (pygame.K_RIGHT, pygame.K_PERIOD):
                self.year = min(YEAR_MAX, self.year + (10 if event.mod & pygame.KMOD_SHIFT else 1))
            elif event.key in (pygame.K_LEFT, pygame.K_COMMA):
                self.year = max(YEAR_MIN, self.year - (10 if event.mod & pygame.KMOD_SHIFT else 1))
            elif event.key == pygame.K_HOME:
                self.year = YEAR_MIN
            elif event.key == pygame.K_END:
                self.year = YEAR_MAX
            elif event.key == pygame.K_LEFTBRACKET:
                self.years_per_sec = max(1.0, self.years_per_sec / 1.5)
            elif event.key == pygame.K_RIGHTBRACKET:
                self.years_per_sec = min(40.0, self.years_per_sec * 1.5)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.scrub.collidepoint(event.pos):
                self.dragging_scrub = True
                self._scrub_to(event.pos[0])
            else:
                self._click_node(event.pos)
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging_scrub = False
        if event.type == pygame.MOUSEMOTION and self.dragging_scrub:
            self._scrub_to(event.pos[0])
        return True

    def _scrub_to(self, x: int) -> None:
        t = (x - self.scrub.x) / max(1, self.scrub.w)
        t = max(0.0, min(1.0, t))
        self.year = int(round(YEAR_MIN + t * (YEAR_MAX - YEAR_MIN)))

    def _click_node(self, pos: tuple[int, int]) -> None:
        view = self.model.view(self.year)
        hit: Optional[str] = None
        best = 1e9
        for nid, node in view.nodes.items():
            cx, cy = layout_xy(nid, self._board_box())
            r = ConfluxModel.radius_for_pop(node.total_population, ghost=node.ghost)
            d = math.hypot(pos[0] - cx, pos[1] - cy)
            if d <= r + 4 and d < best:
                best = d
                hit = nid
        self.selected = hit

    def _board_box(self) -> tuple[int, int, int, int]:
        return (self.board.x, self.board.y, self.board.w, self.board.h)

    def _draw(self) -> None:
        self.screen.fill(BG)
        view = self.model.view(self.year)
        self._draw_topbar(view)
        self._draw_board(view)
        self._draw_side(view)
        self._draw_bottom()

    def _draw_topbar(self, view: YearView) -> None:
        pygame.draw.rect(self.screen, PANEL, (0, 0, WIDTH, TOPBAR_H))
        pygame.draw.line(self.screen, BORDER, (0, TOPBAR_H), (WIDTH, TOPBAR_H), 1)
        title = self.f_title.render("Conflux Atlas", True, TEXT)
        self.screen.blit(title, (PAD, 14))
        sub = self.f.render(
            f"hold anchors · migration edges · confidence decay  |  nodes {len(view.nodes)}  edges {len(view.edges)}",
            True,
            MUTED,
        )
        self.screen.blit(sub, (PAD + 170, 18))
        yr = self.f_mono.render(str(self.year), True, ACCENT)
        self.screen.blit(yr, (WIDTH - SIDE_W - 20, 14))

    def _draw_board(self, view: YearView) -> None:
        pygame.draw.rect(self.screen, PANEL, self.board, border_radius=8)
        pygame.draw.rect(self.screen, BORDER, self.board, 1, border_radius=8)

        # edges under nodes
        for re in view.edges:
            e = re.edge
            if e.from_polity not in view.nodes or e.to_polity not in view.nodes:
                continue
            x1, y1 = layout_xy(e.from_polity, self._board_box())
            x2, y2 = layout_xy(e.to_polity, self._board_box())
            # thickness from volume (log)
            thick = max(1, min(10, int(1 + math.log10(max(e.volume_est, 10)))))
            col = blend(EDGE_COL, PANEL, 0.35 + 0.65 * re.alpha)
            self._arrow(x1, y1, x2, y2, col, thick)

        for nid, node in view.nodes.items():
            self._draw_node(nid, node, selected=(nid == self.selected))

        hint = self.f_sm.render(
            "Click a polity · Space play/pause · ←/→ year · Shift+←/→ decade · [ ] speed",
            True,
            MUTED,
        )
        self.screen.blit(hint, (self.board.x + 10, self.board.bottom - 22))

    def _arrow(self, x1: float, y1: float, x2: float, y2: float, col: tuple[int, int, int], thick: int) -> None:
        pygame.draw.line(self.screen, col, (x1, y1), (x2, y2), thick)
        ang = math.atan2(y2 - y1, x2 - x1)
        ah = 10 + thick
        tip = (x2, y2)
        left = (x2 - ah * math.cos(ang - 0.4), y2 - ah * math.sin(ang - 0.4))
        right = (x2 - ah * math.cos(ang + 0.4), y2 - ah * math.sin(ang + 0.4))
        pygame.draw.polygon(self.screen, col, [tip, left, right])

    def _draw_node(self, nid: str, node: RuntimeNode, *, selected: bool) -> None:
        cx, cy = layout_xy(nid, self._board_box())
        r = ConfluxModel.radius_for_pop(node.total_population, ghost=node.ghost)
        fill = blend(node.color, PANEL, 0.25 + 0.75 * node.confidence)
        if node.ghost:
            pygame.draw.circle(self.screen, blend(MUTED, PANEL, 0.5), (int(cx), int(cy)), int(r), 2)
        else:
            pygame.draw.circle(self.screen, fill, (int(cx), int(cy)), int(r))
            pygame.draw.circle(self.screen, blend(fill, TEXT, 0.35), (int(cx), int(cy)), int(r), 2)
        if selected:
            pygame.draw.circle(self.screen, ACCENT, (int(cx), int(cy)), int(r) + 4, 2)
        label = self.f_sm.render(node.display_name, True, TEXT)
        self.screen.blit(label, (cx - label.get_width() / 2, cy + r + 2))

    def _draw_side(self, view: YearView) -> None:
        pygame.draw.rect(self.screen, PANEL, self.side, border_radius=8)
        pygame.draw.rect(self.screen, BORDER, self.side, 1, border_radius=8)
        x = self.side.x + 12
        y = self.side.y + 12
        self.screen.blit(self.f_h.render("Inspector", True, TEXT), (x, y))
        y += 28

        node = view.nodes.get(self.selected) if self.selected else None
        if node is None:
            # pick largest visible
            if view.nodes:
                node = max(view.nodes.values(), key=lambda n: n.total_population)
                self.screen.blit(self.f_sm.render("(largest node — click to select)", True, MUTED), (x, y))
                y += 18
            else:
                self.screen.blit(self.f.render("No anchors for this year.", True, MUTED), (x, y))
                return

        lines = [
            node.display_name,
            f"year {view.year}  ·  share-anchor {node.anchor_year}",
            f"population  {node.total_population:,}",
            f"pop source  {node.pop_source or '—'}",
            f"dominant    {node.dominant_religion}",
            f"confidence  {node.confidence:.2f}",
        ]
        if node.ghost:
            lines.append("ghost node (edge endpoint only)")
        for line in lines:
            self.screen.blit(self.f.render(line, True, TEXT if line == node.display_name else MUTED), (x, y))
            y += 18

        y += 8
        self.screen.blit(self.f_h.render("Shares", True, TEXT), (x, y))
        y += 22
        for rel, share in sorted(node.shares.items(), key=lambda kv: -kv[1]):
            if share < 0.0005:
                continue
            bar_w = int((self.side.w - 24) * share)
            col = blend(RELIGION_RGB.get(rel, MUTED), PANEL, 0.85)
            pygame.draw.rect(self.screen, col, (x, y, max(2, bar_w), 12), border_radius=3)
            self.screen.blit(self.f_sm.render(f"{rel}  {share * 100:.1f}%", True, TEXT), (x, y + 14))
            y += 32

        y += 6
        self.screen.blit(self.f_h.render("Active edges", True, TEXT), (x, y))
        y += 20
        shown = 0
        for re in sorted(view.edges, key=lambda r: -r.edge.volume_est):
            e = re.edge
            if self.selected and self.selected not in (e.from_polity, e.to_polity):
                continue
            label = f"{e.from_polity}→{e.to_polity}"
            detail = f"{e.group.value} ~{fmt_pop(e.volume_est)}  α={re.alpha:.2f}"
            self.screen.blit(self.f_sm.render(label, True, EDGE_COL), (x, y))
            y += 14
            self.screen.blit(self.f_sm.render(detail, True, MUTED), (x, y))
            y += 18
            shown += 1
            if shown >= 6 or y > self.side.bottom - 24:
                break
        if shown == 0:
            self.screen.blit(self.f_sm.render("none this year", True, MUTED), (x, y))

    def _draw_bottom(self) -> None:
        bar = pygame.Rect(0, HEIGHT - BOTTOMBAR_H, WIDTH, BOTTOMBAR_H)
        pygame.draw.rect(self.screen, PANEL, bar)
        pygame.draw.line(self.screen, BORDER, (0, bar.y), (WIDTH, bar.y), 1)

        self.screen.blit(self.f.render(str(YEAR_MIN), True, MUTED), (self.scrub.x - 48, self.scrub.y - 2))
        self.screen.blit(self.f.render(str(YEAR_MAX), True, MUTED), (self.scrub.right + 10, self.scrub.y - 2))

        pygame.draw.rect(self.screen, PANEL_HI, self.scrub, border_radius=6)
        pygame.draw.rect(self.screen, BORDER, self.scrub, 1, border_radius=6)
        t = (self.year - YEAR_MIN) / (YEAR_MAX - YEAR_MIN)
        knob_x = self.scrub.x + int(t * self.scrub.w)
        pygame.draw.circle(self.screen, ACCENT, (knob_x, self.scrub.centery), 9)
        pygame.draw.circle(self.screen, TEXT, (knob_x, self.scrub.centery), 9, 1)

        status = "PLAY" if self.playing else "PAUSE"
        deltas = "DELTAS ON" if self.apply_event_deltas else "deltas off"
        self.screen.blit(
            self.f.render(
                f"{status}  ·  {self.years_per_sec:.1f} yr/s  ·  {deltas}  ·  [D] toggle",
                True,
                MUTED,
            ),
            (PAD, bar.y + 58),
        )


def main(argv: Optional[list[str]] = None) -> None:
    p = argparse.ArgumentParser(description="Conflux Atlas demo scrubber")
    p.add_argument("--year", type=int, default=1900, help="starting year")
    p.add_argument("--play", action="store_true", help="auto-advance years on launch")
    p.add_argument(
        "--deltas",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="apply event-delta accounting (edge volumes mutate node pops); default on",
    )
    p.add_argument(
        "--smoke",
        action="store_true",
        help="load model, print a few year views, exit (no GUI)",
    )
    args = p.parse_args(argv)

    if args.smoke:
        for label, deltas in (("hold+overlay", False), ("event-deltas", True)):
            model = ConfluxModel(apply_event_deltas=deltas)
            print(f"##### mode={label} #####")
            for y in (1900, 1923, 1948, 1950, 1979, 2000, 2010, 2020):
                v = model.view(y)
                pops = sorted(
                    (
                        (n.display_name, n.total_population, n.confidence, n.net_migration)
                        for n in v.nodes.values()
                        if not n.ghost
                    ),
                    key=lambda t: -t[1],
                )
                print(f"=== {y}  nodes={len(v.nodes)} edges={len(v.edges)} deltas={len(v.applied_deltas)} ===")
                for name, pop, conf, net in pops[:5]:
                    extra = f"  net={net:+,}" if deltas and net else ""
                    print(f"  {name:16} {pop:>12,}  conf={conf:.2f}{extra}")
                for re in v.edges[:3]:
                    e = re.edge
                    desa = f" desa={re.desa_stock:,}" if re.desa_stock else ""
                    print(
                        f"  edge {e.from_polity}→{e.to_polity} {e.group.value} "
                        f"~{e.volume_est:,} α={re.alpha:.2f}{desa}"
                    )
        print("smoke ok")
        return

    # Prefer Wayland/X11 when available; fail clearly headless.
    app = SimApp(start_year=args.year, play=args.play, apply_event_deltas=args.deltas)
    app.run()


if __name__ == "__main__":
    main(sys.argv[1:])
