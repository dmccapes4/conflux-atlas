#!/usr/bin/env python3
"""Build the alpha-movie basemap slice from Natural Earth (public domain).

PLAN_MOVIE_ALPHA.md §9.1: the basemap is owned vector geometry, not a
raster screenshot. This script takes the NE 50m admin-0 countries
GeoJSON, frames it like the composition reference (N. Atlantic → India,
N. Europe → Sahel), projects to Web-Mercator unit coordinates,
simplifies (Douglas–Peucker), joins desk ``polity_id``s via ADM0_A3, and
writes ``movie-alpha/assets/world_frame.json``.

Source (cached under data/raw/naturalearth/): Natural Earth, public
domain — https://www.naturalearthdata.com

Usage:
  python scripts/build_movie_basemap.py [--tolerance 0.0018]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw" / "naturalearth" / "ne_50m_admin_0_countries.geojson"
OUT = ROOT / "movie-alpha" / "assets" / "world_frame.json"
NE_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_50m_admin_0_countries.geojson"
)

# Composition frame (reference: user's Google Maps crop — used as framing
# guidance only; no Google pixels ship).
FRAME = {"lon_min": -30.0, "lon_max": 80.0, "lat_min": 2.0, "lat_max": 64.0}

# Desk polity_id -> Natural Earth ADM0_A3 (handles NE's ISO -99 quirks:
# France is -99 under ISO_A3, Palestine is PSX, Western Sahara SAH).
POLITY_TO_ADM0 = {
    "algeria": "DZA",
    "bahrain": "BHR",
    "egypt": "EGY",
    "iran": "IRN",
    "iraq": "IRQ",
    "israel": "ISR",
    "jordan": "JOR",
    "kuwait": "KWT",
    "lebanon": "LBN",
    "libya": "LBY",
    "morocco": "MAR",
    "oman": "OMN",
    "palestinian_territories": "PSX",
    "qatar": "QAT",
    "saudi_arabia": "SAU",
    "sudan": "SDN",
    "syria": "SYR",
    "tunisia": "TUN",
    "turkey": "TUR",
    "united_arab_emirates": "ARE",
    "western_sahara": "SAH",
    "yemen": "YEM",
    # diaspora polygons inside the frame
    "france": "FRA",
    "greece": "GRC",
    "germany": "DEU",
    "united_kingdom": "GBR",
}

# Diaspora nodes outside the frame become callout chips (uv on the
# Atlantic edge), not a second world map.
CHIPS = [
    {"polity_id": "united_states", "name": "United States", "uv": [0.045, 0.55]},
    {"polity_id": "canada", "name": "Canada", "uv": [0.045, 0.38]},
]

DISPLAY_NAMES = {
    "palestinian_territories": "Palestinian Territories",
    "western_sahara": "Western Sahara",
}


def _merc_y(lat: float) -> float:
    lat = max(-85.0, min(85.0, lat))
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


_Y0 = _merc_y(FRAME["lat_max"])
_Y1 = _merc_y(FRAME["lat_min"])


def project(lon: float, lat: float) -> tuple[float, float]:
    """(lon, lat) -> unit uv in the frame (v grows downward)."""
    u = (lon - FRAME["lon_min"]) / (FRAME["lon_max"] - FRAME["lon_min"])
    v = (_merc_y(lat) - _Y0) / (_Y1 - _Y0)
    return u, v


def simplify(points: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    """Douglas–Peucker on a closed ring.

    Closed rings (first == last) have a degenerate baseline that makes
    plain DP collapse the whole ring to two points, so the ring is split
    into two arcs at its midpoint and each arc is simplified alone.
    """
    if len(points) < 5:
        return points

    def dp(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if len(pts) < 3:
            return pts
        (x0, y0), (x1, y1) = pts[0], pts[-1]
        dx, dy = x1 - x0, y1 - y0
        norm = math.hypot(dx, dy) or 1e-12
        dmax, imax = 0.0, 0
        for i in range(1, len(pts) - 1):
            px, py = pts[i]
            d = abs(dx * (y0 - py) - dy * (x0 - px)) / norm
            if d > dmax:
                dmax, imax = d, i
        if dmax <= tol:
            return [pts[0], pts[-1]]
        left = dp(pts[: imax + 1])
        right = dp(pts[imax:])
        return left[:-1] + right

    ring = points[:-1] if points[0] == points[-1] else points
    mid = len(ring) // 2
    half_a = dp(ring[: mid + 1])
    half_b = dp(ring[mid:] + ring[:1])
    return half_a[:-1] + half_b[:-1]


def ring_bbox(ring: list[tuple[float, float]]):
    us = [p[0] for p in ring]
    vs = [p[1] for p in ring]
    return min(us), min(vs), max(us), max(vs)


def ring_area(ring: list[tuple[float, float]]) -> float:
    s = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        s += x0 * y1 - x1 * y0
    return abs(s) / 2


def centroid(ring: list[tuple[float, float]]) -> tuple[float, float]:
    us = [p[0] for p in ring]
    vs = [p[1] for p in ring]
    return sum(us) / len(us), sum(vs) / len(vs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tolerance", type=float, default=0.0018)
    args = ap.parse_args()

    if not CACHE.exists():
        print(f"⬇️  downloading Natural Earth 50m → {CACHE}")
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(NE_URL, CACHE)
    src = json.loads(CACHE.read_text(encoding="utf-8"))

    adm0_to_polity = {v: k for k, v in POLITY_TO_ADM0.items()}
    countries = []
    for feat in src["features"]:
        props = feat["properties"]
        adm0 = props.get("ADM0_A3") or props.get("ISO_A3_EH") or ""
        polity = adm0_to_polity.get(adm0)
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]

        rings = []
        in_frame_uv = []
        for poly in polys:
            outer = poly[0]  # alpha map skips holes (lakes are noise at this scale)
            uv = [project(lon, lat) for lon, lat, *_ in outer]
            lo_u, lo_v, hi_u, hi_v = ring_bbox(uv)
            # drop rings entirely outside the frame (with a bleed margin)
            if hi_u < -0.05 or lo_u > 1.05 or hi_v < -0.05 or lo_v > 1.05:
                continue
            in_frame_uv.append(uv)
            # drop islets that would render smaller than ~2px
            min_diag = 0.004 if polity else 0.010
            if math.hypot(hi_u - lo_u, hi_v - lo_v) < min_diag:
                continue
            s = simplify(uv, args.tolerance)
            if len(s) >= 4:
                rings.append([[round(u, 4), round(v, 4)] for u, v in s])

        # a desk polity must render even if it is one tiny island (Bahrain)
        if not rings and polity and in_frame_uv:
            biggest = max(in_frame_uv, key=ring_area)
            rings.append([[round(u, 4), round(v, 4)] for u, v in biggest])
        if not rings:
            continue
        main_ring = max(rings, key=lambda r: ring_area([(p[0], p[1]) for p in r]))
        cu, cv = centroid([(p[0], p[1]) for p in main_ring])
        name = (
            DISPLAY_NAMES.get(polity)
            if polity in DISPLAY_NAMES
            else (props.get("NAME") or props.get("ADMIN") or adm0)
        )
        countries.append(
            {
                "adm0": adm0,
                "name": name,
                "polity_id": polity,
                "label_uv": [round(cu, 4), round(cv, 4)],
                "rings": rings,
            }
        )

    joined = {c["polity_id"] for c in countries if c["polity_id"]}
    missing = set(POLITY_TO_ADM0) - joined
    if missing:
        sys.exit(f"polity join failed for: {sorted(missing)}")

    aspect = math.radians(FRAME["lon_max"] - FRAME["lon_min"]) / (_Y1 - _Y0)
    out = {
        "attribution": "Basemap geometry: Natural Earth (public domain), 50m admin-0.",
        "frame": FRAME,
        "projection": "web-mercator, unit uv within frame, v down",
        "aspect": round(abs(aspect), 4),
        "countries": countries,
        "chips": CHIPS,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")
    n_pts = sum(len(r) for c in countries for r in c["rings"])
    print(
        f"🗺️  wrote {OUT} — {len(countries)} countries "
        f"({len(joined)} desk polities), {n_pts} points, "
        f"{OUT.stat().st_size // 1024} KB"
    )


if __name__ == "__main__":
    main()
