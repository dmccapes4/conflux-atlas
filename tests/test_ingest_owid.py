"""Offline ingest fixture — parse logic, not live download."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_ingest_module():
    path = ROOT / "scripts" / "ingest_owid_population.py"
    spec = importlib.util.spec_from_file_location("ingest_owid_population", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_owid_ingest_from_tiny_fixture(tmp_path: Path) -> None:
    raw = tmp_path / "population.csv"
    raw.write_text(
        "Entity,Code,Year,Population\n"
        "Egypt,EGY,1900,10000000\n"
        "Egypt,EGY,1950,20000000\n"
        "Israel,ISR,1950,1267000\n"
        "Atlantis,ATL,1950,1\n",  # unmapped — skipped
        encoding="utf-8",
    )
    out = tmp_path / "population_totals.jsonl"
    mod = _load_ingest_module()
    n = mod.ingest(raw, out, year_min=1900, year_max=2000)
    assert n == 3
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    assert all('"source_ids": ["owid_population"]' in line for line in lines)
    assert "egypt" in lines[0]
