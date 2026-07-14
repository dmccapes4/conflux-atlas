"""Phase 2 gate — Beta trust primitives (`conflux/learning.py`).

CONTRACT (rationale in docs/PHASE2_TEST_SPEC.md):

  - `Posterior` is a near-verbatim port of ptv-embed-lab
    `ptv_embed/learning.py` (nakatomi lineage): immutable Beta(α, β),
    uniform prior Beta(1, 1), `bumped(success)` returns a NEW posterior.
  - `TrustStore` enforces settlement-only learning: recording a claim
    never moves a posterior; only `settle()` does; double-settlement
    raises. This is the discipline the whole project inherits.
  - Unlike the ptv original, the store must survive process restarts
    (`save` / `load` roundtrip) — the demographic settlement tape spans
    runs, censuses, and years.

SKIPS until conflux/learning.py exists. Run: `make test-phase2`.
"""

from __future__ import annotations

import pytest

learning = pytest.importorskip(
    "conflux.learning", reason="Phase 2: conflux/learning.py not implemented yet"
)

pytestmark = pytest.mark.phase2


# ---------------------------------------------------------------------------
# Posterior — Beta(α, β)
# ---------------------------------------------------------------------------


def test_posterior_uniform_prior() -> None:
    p = learning.Posterior()
    assert p.alpha == 1.0 and p.beta == 1.0 and p.trials == 0
    assert p.mean == pytest.approx(0.5)


def test_posterior_bump_math_and_immutability() -> None:
    p0 = learning.Posterior()
    p1 = p0.bumped(True)
    p2 = p1.bumped(False)
    # p0 untouched (frozen); each bump returns a new object
    assert p0.mean == pytest.approx(0.5) and p0.trials == 0
    assert p1.alpha == 2.0 and p1.beta == 1.0 and p1.trials == 1
    assert p1.mean == pytest.approx(2.0 / 3.0)
    assert p2.alpha == 2.0 and p2.beta == 2.0 and p2.trials == 2
    assert p2.mean == pytest.approx(0.5)


def test_posterior_variance_shrinks_with_evidence() -> None:
    """More settlements → tighter belief, regardless of direction."""
    p = learning.Posterior()
    var0 = p.variance
    for success in (True, False, True, False, True, False):
        p = p.bumped(success)
    assert p.variance < var0
    assert p.mean == pytest.approx(0.5)  # balanced evidence, same mean, less doubt


# ---------------------------------------------------------------------------
# TrustStore — settlement-only discipline
# ---------------------------------------------------------------------------


def _mk_claim(claim_id: str = "c1", hyp: str = "policy:persistence") -> "learning.Claim":
    return learning.Claim(
        claim_id=claim_id,
        hypothesis_id=hyp,
        polity_id="testland",
        group="muslim",
        cut_year=1950,
        predicted="up",
        stated_p=0.5,
        train_n=0,
    )


def test_get_returns_prior_without_inserting() -> None:
    store = learning.TrustStore()
    p = store.get("policy:never_seen")
    assert p.mean == pytest.approx(0.5)
    assert "policy:never_seen" not in store.posteriors, (
        "get() must be read-only — phantom keys distort summaries"
    )


def test_recording_a_claim_never_moves_a_posterior() -> None:
    """THE rule (nakatomi / LEARNING_LOOP_GUIDANCE): nothing but a settled
    outcome may bump a posterior. Making claims is free; being right isn't."""
    store = learning.TrustStore()
    store.record(_mk_claim())
    assert store.posteriors == {}
    assert len(store.ledger) == 1


def test_settle_bumps_and_marks() -> None:
    store = learning.TrustStore()
    claim = _mk_claim()
    store.record(claim)
    post = store.settle(claim, success=True)
    assert claim.settled is True and claim.success is True
    assert claim.settled_at is not None
    assert post.mean == pytest.approx(2.0 / 3.0)
    assert store.get("policy:persistence").trials == 1


def test_double_settlement_raises() -> None:
    """A settlement is a historical fact — it must be impossible to count
    the same outcome twice (double-bumps silently inflate trust)."""
    store = learning.TrustStore()
    claim = _mk_claim()
    store.record(claim)
    store.settle(claim, success=True)
    with pytest.raises(ValueError):
        store.settle(claim, success=True)
    assert store.get("policy:persistence").trials == 1


def test_summary_sorted_by_mean_desc() -> None:
    store = learning.TrustStore()
    for hyp, outcomes in {
        "policy:good": [True, True, True],
        "policy:bad": [False, False, False],
        "policy:mixed": [True, False],
    }.items():
        for i, success in enumerate(outcomes):
            c = _mk_claim(claim_id=f"{hyp}_{i}", hyp=hyp)
            store.record(c)
            store.settle(c, success=success)
    rows = store.summary()
    means = [r["mean"] for r in rows]
    assert means == sorted(means, reverse=True)
    assert rows[0]["hypothesis_id"] == "policy:good"
    assert rows[-1]["hypothesis_id"] == "policy:bad"


# ---------------------------------------------------------------------------
# Persistence — the tape outlives the process
# ---------------------------------------------------------------------------


def test_save_load_roundtrip(tmp_path) -> None:
    store = learning.TrustStore()
    claims = [_mk_claim(claim_id=f"c{i}") for i in range(3)]
    for i, c in enumerate(claims):
        store.record(c)
        if i < 2:
            store.settle(c, success=(i == 0))

    path = tmp_path / "trust_store.json"
    store.save(path)
    loaded = learning.TrustStore.load(path)

    orig = store.get("policy:persistence")
    back = loaded.get("policy:persistence")
    assert back.alpha == orig.alpha and back.beta == orig.beta
    assert back.trials == orig.trials == 2

    assert len(loaded.ledger) == 3
    by_id = {c.claim_id: c for c in loaded.ledger}
    assert by_id["c0"].settled and by_id["c0"].success is True
    assert by_id["c1"].settled and by_id["c1"].success is False
    assert not by_id["c2"].settled, "unsettled claims must survive reload unsettled"


def test_loaded_store_rejects_resettlement(tmp_path) -> None:
    """Settlement facts survive persistence: a claim settled before save
    cannot be settled again after load."""
    store = learning.TrustStore()
    claim = _mk_claim()
    store.record(claim)
    store.settle(claim, success=True)
    path = tmp_path / "trust_store.json"
    store.save(path)

    loaded = learning.TrustStore.load(path)
    reclaim = next(c for c in loaded.ledger if c.claim_id == "c1")
    with pytest.raises(ValueError):
        loaded.settle(reclaim, success=False)
