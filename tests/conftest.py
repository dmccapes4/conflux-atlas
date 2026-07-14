"""Shared test fixtures (Phase 0 + Phase 1)."""

from __future__ import annotations

import pytest

from conflux.schema import Anchor, dominant_from_shares


@pytest.fixture
def mk_anchor():
    """Factory for valid synthetic Anchors.

    Pass partial shares; the remainder is folded into "other" so the
    shares-sum-to-1 validator passes. Keeps Phase 1 tests focused on
    movement math instead of fixture bookkeeping.
    """

    def _mk(
        polity_id: str,
        year: int,
        shares: dict[str, float],
        *,
        confidence: float = 0.8,
        pop: int = 1_000_000,
        source: str = "test_fixture",
    ) -> Anchor:
        full = dict(shares)
        total = sum(full.values())
        if total < 1.0 - 1e-9:
            full["other"] = full.get("other", 0.0) + (1.0 - total)
        return Anchor(
            anchor_id=f"{polity_id}_{year}_test",
            polity_id=polity_id,
            year=year,
            total_population=pop,
            shares=full,
            dominant_religion=dominant_from_shares(full),
            confidence=confidence,
            source_ids=[source],
        )

    return _mk
