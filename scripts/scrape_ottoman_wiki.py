#!/usr/bin/env python3
"""Scrape Demographics of the Ottoman Empire (Wikipedia) into CSV tables.

Bootstrap only — prefer Karpat / academic cites when building anchors.
Saves page HTML snapshot + one CSV per wikitable under data/raw/ottoman/wiki/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from io import StringIO

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "ottoman" / "wiki"
PAGE = "Demographics_of_the_Ottoman_Empire"
API = (
    "https://en.wikipedia.org/w/api.php"
    f"?action=parse&page={PAGE}&prop=text|revid|displaytitle&format=json"
)
UA = "ConfluxAtlas/0.1 (research; local ingest)"


def _slug(s: str, i: int) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", "_", s.strip().lower())
    s = re.sub(r"[^a-z0-9_]+", "", s)
    s = s.strip("_")[:60] or f"table_{i:02d}"
    return f"{i:02d}_{s}"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    try:
        import pandas as pd
    except ImportError:
        print("Need pandas (+ lxml). In venv: pip install pandas lxml", file=sys.stderr)
        sys.exit(1)

    req = urllib.request.Request(API, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        payload = json.load(resp)
    parsed = payload["parse"]
    html = parsed["text"]["*"]
    revid = parsed.get("revid")

    (args.out / "page.html").write_text(html, encoding="utf-8")
    meta = {
        "page": PAGE,
        "url": f"https://en.wikipedia.org/wiki/{PAGE}",
        "revid": revid,
        "source_id": "ottoman_demographics_wiki",
        "note": "Bootstrap scrape. Cross-check against Karpat before high-confidence anchors.",
    }
    (args.out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    tables = pd.read_html(StringIO(html))
    # Drop navbox-like tiny junk: keep tables with >= 2 cols and >= 2 rows
    kept = []
    for i, df in enumerate(tables):
        if df.shape[0] < 2 or df.shape[1] < 2:
            continue
        # Heuristic: skip huge reference/nav tables with mostly NaN
        if df.shape[1] > 20 and df.isna().mean().mean() > 0.7:
            continue
        kept.append((i, df))

    index_rows = []
    for n, (orig_i, df) in enumerate(kept):
        # caption-ish name from first column header or generic
        title = " / ".join(str(c) for c in df.columns[:3])
        name = _slug(title, n)
        path = args.out / f"{name}.csv"
        df.to_csv(path, index=False)
        index_rows.append(
            {
                "file": path.name,
                "orig_table_index": orig_i,
                "rows": int(df.shape[0]),
                "cols": int(df.shape[1]),
                "columns": [str(c) for c in df.columns],
            }
        )
        print(f"wrote {path.name} ({df.shape[0]}×{df.shape[1]})")

    (args.out / "index.json").write_text(
        json.dumps({"tables": index_rows, "meta": meta}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"tables kept: {len(kept)} / {len(tables)}")
    print(f"out: {args.out}")


if __name__ == "__main__":
    main()
