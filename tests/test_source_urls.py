"""URL drift contracts — offline by default; live probes behind -m network.

Phase 0 does *not* require live scrapes. Scraping URLs rot; the durable
guard is (1) a canonical registry, (2) scripts still cite those strings,
(3) optional network probes when you want a heads-up.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "sources" / "CANONICAL_URLS.json"
BIB = ROOT / "data" / "sources" / "BIBLIOGRAPHY.md"


@pytest.fixture(scope="module")
def endpoints() -> list[dict]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    eps = data["endpoints"]
    assert eps, "CANONICAL_URLS.json has no endpoints"
    return eps


def test_canonical_urls_appear_in_declared_scripts(endpoints: list[dict]) -> None:
    for ep in endpoints:
        url = ep["url"]
        scripts = ep.get("scripts") or []
        assert scripts, f"{ep['id']}: no scripts listed"
        found = False
        for rel in scripts:
            text = (ROOT / rel).read_text(encoding="utf-8")
            if url in text:
                found = True
                break
        assert found, (
            f"{ep['id']}: URL not found in {scripts}. "
            "Update the script or CANONICAL_URLS.json together."
        )


def test_canonical_source_ids_in_bibliography(endpoints: list[dict]) -> None:
    bib = BIB.read_text(encoding="utf-8")
    missing: list[str] = []
    for ep in endpoints:
        sid = ep["source_id"]
        in_table = any(
            line.startswith("|") and len(line.split("|")) > 1 and line.split("|")[1].strip() == sid
            for line in bib.splitlines()
        )
        if not in_table:
            missing.append(sid)
    assert not missing, f"source_ids missing from BIBLIOGRAPHY.md: {missing}"


@pytest.mark.network
@pytest.mark.parametrize(
    "ep_id",
    [
        "owid_population_csv",
        "unhcr_population_api",
        "wikipedia_ottoman_demographics_api",
    ],
)
def test_live_url_reachable(endpoints: list[dict], ep_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Opt-in smoke: a few critical hosts still answer (not a Phase 0 gate)."""
    # Local Cursor/agent sandboxes often inject a broken HTTP(S)_PROXY.
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        monkeypatch.delenv(key, raising=False)

    ep = next(e for e in endpoints if e["id"] == ep_id)
    url = ep["url"]
    req = urllib.request.Request(
        url,
        method="HEAD" if ep.get("probe") == "head" else "GET",
        headers={"User-Agent": "ConfluxAtlas/0.1 (+pytest network)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            assert 200 <= resp.status < 400, f"{url} → {resp.status}"
    except urllib.error.HTTPError as e:
        if e.code in {403, 405, 501} and ep.get("probe") == "head":
            req = urllib.request.Request(
                url,
                method="GET",
                headers={"User-Agent": "ConfluxAtlas/0.1 (+pytest network)"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                assert 200 <= resp.status < 400
        else:
            raise
