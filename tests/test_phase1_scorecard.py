"""Phase 1 gate — hash-catalog scorecard vs baselines (`conflux/scorecard.py`).

CONTRACT (rationale in docs/PHASE1_TEST_SPEC.md):

  - The scorecard answers Phase 1's milestone question: does conditioning
    on origin place-hash predict transition direction better than dumb
    baselines? Policies, all evaluated on the SAME held-out transitions:
        "hash_mode"    — modal outcome of the origin hash bucket (train only)
        "reversion"    — predict the opposite of the previous transition
        "persistence"  — predict the same direction as the previous transition
        "majority"     — global modal direction of the training set
  - Evaluation is leave-one-polity-out (STRATEGY v0.2 Phase 2 critique:
    with ~4 snapshots/polity, leave-one-year-out is too fragile).
  - CRITICAL DESIGN RULE: tests assert the scorecard is *well-formed*
    (coverage, accuracy bounds, no train/test leakage), never that the
    hash beats the baseline. Whether it wins is the RESEARCH RESULT that
    goes in the report — a threshold miss is a result, not a test failure.

SKIPS until conflux/scorecard.py exists. Run: `make test-phase1`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

movement = pytest.importorskip(
    "conflux.movement", reason="Phase 1: conflux/movement.py not implemented yet"
)
scorecard = pytest.importorskip(
    "conflux.scorecard", reason="Phase 1: conflux/scorecard.py not implemented yet"
)

pytestmark = pytest.mark.phase1

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_POLICIES = {"hash_mode", "reversion", "persistence", "majority"}


def _synthetic_catalog(mk_anchor):
    """4 polities with mixed trajectories → enough transitions to score."""
    specs = {
        "upland": [(1900, 0.40), (1950, 0.55), (2000, 0.70), (2020, 0.80)],
        "downland": [(1900, 0.80), (1950, 0.70), (2000, 0.55), (2020, 0.40)],
        "meanrevland": [(1900, 0.60), (1950, 0.70), (2000, 0.60), (2020, 0.70)],
        "flatland": [(1900, 0.50), (1950, 0.50), (2000, 0.50), (2020, 0.50)],
    }
    anchors = []
    for pid, pts in specs.items():
        anchors.extend(mk_anchor(pid, y, {"muslim": s}) for y, s in pts)
    return movement.build_catalog(anchors, groups=["muslim"])


def test_scorecard_shape_and_bounds(mk_anchor) -> None:
    catalog = _synthetic_catalog(mk_anchor)
    result = scorecard.run_scorecard(catalog, min_bucket_n=1)

    assert REQUIRED_POLICIES <= set(result.policies)
    for name in REQUIRED_POLICIES:
        pol = result.policies[name]
        # accuracy is a probability; n_scored bounded by total transitions
        assert 0.0 <= pol.accuracy <= 1.0
        assert 0 < pol.n_scored <= result.n_transitions
    # every policy scored the same settlement tape (fair comparison)
    ns = {result.policies[p].n_scored for p in REQUIRED_POLICIES}
    assert len(ns) == 1, "all policies must be scored on identical holdouts"


def test_scorecard_leave_one_polity_out_no_leakage(mk_anchor) -> None:
    """A polity's own transitions must never inform its hash_mode
    predictions. Construct a world where ONE polity moves up and all
    others move down from the *same* origin level so origin hashes collide:
    without leakage, training buckets for the up-polity only ever saw 'down'.
    """
    # Shared starting level → identical first-transition origin hashes
    # (level|na|era|na). Divergent trajectories supply the outcomes.
    specs = {
        "loner_up": [(1900, 0.50), (1950, 0.65), (2000, 0.80)],
        "down_a": [(1900, 0.50), (1950, 0.35), (2000, 0.20)],
        "down_b": [(1900, 0.50), (1950, 0.34), (2000, 0.18)],
        "down_c": [(1900, 0.50), (1950, 0.36), (2000, 0.22)],
    }
    anchors = []
    for pid, pts in specs.items():
        anchors.extend(mk_anchor(pid, y, {"muslim": s}) for y, s in pts)
    catalog = movement.build_catalog(anchors, groups=["muslim"])
    result = scorecard.run_scorecard(catalog, min_bucket_n=1)

    loner_preds = [
        p for p in result.predictions
        if p.polity_id == "loner_up" and p.policy == "hash_mode" and p.predicted
    ]
    assert loner_preds, "expected hash_mode predictions for held-out polity"
    assert all(p.predicted != "up" for p in loner_preds), (
        "hash_mode predicted 'up' for the only up-moving polity — "
        "its own transitions leaked into its training buckets"
    )


def test_scorecard_abstains_below_min_bucket_n(mk_anchor) -> None:
    """When the origin bucket has < min_bucket_n training rows, hash_mode
    must ABSTAIN (predicted=None), and abstentions must be reported as
    coverage — never silently backfilled with a guess."""
    catalog = _synthetic_catalog(mk_anchor)
    strict = scorecard.run_scorecard(catalog, min_bucket_n=10_000)
    pol = strict.policies["hash_mode"]
    assert pol.coverage == pytest.approx(0.0)
    loose = scorecard.run_scorecard(catalog, min_bucket_n=1)
    assert loose.policies["hash_mode"].coverage > 0.0


def test_scorecard_report_is_serializable(mk_anchor, tmp_path: Path) -> None:
    """The milestone artifact is a JSON report the docs/ report cites."""
    import json

    catalog = _synthetic_catalog(mk_anchor)
    result = scorecard.run_scorecard(catalog, min_bucket_n=1)
    out = tmp_path / "scorecard.json"
    scorecard.write_report(result, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert REQUIRED_POLICIES <= set(data["policies"])
    for pol in data["policies"].values():
        assert {"accuracy", "n_scored", "coverage"} <= set(pol)
    assert data["n_transitions"] == result.n_transitions
    # provenance: report states its evaluation protocol
    assert data["protocol"] == "leave_one_polity_out"


def test_scorecard_runs_on_real_demo_cohort() -> None:
    """Integration smoke on the actual processed anchors (demo polities).

    Asserts only well-formedness: real hand-seeded data is sparse
    (~4 transitions/polity) and NOTHING about accuracy is promised.
    If this passes, the Phase 1 milestone report can be generated."""
    from conflux.model import ConfluxModel, DEMO_POLITIES

    model = ConfluxModel()
    anchors = [a for pid in DEMO_POLITIES for a in model.anchors_by_polity.get(pid, [])]
    catalog = movement.build_catalog(anchors, groups=["muslim", "christian", "jewish"])
    assert len(catalog) >= 20, "expected ≥20 transitions from demo cohort"

    result = scorecard.run_scorecard(catalog, min_bucket_n=2)
    for name in REQUIRED_POLICIES:
        assert 0.0 <= result.policies[name].accuracy <= 1.0
    assert result.n_transitions == len(catalog)
