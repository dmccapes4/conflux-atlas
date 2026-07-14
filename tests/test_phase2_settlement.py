"""Phase 2 gate — temporal-cut claims + settlement (`conflux/settlement.py`).

CONTRACT (rationale in docs/PHASE2_TEST_SPEC.md):

  - This is the miniature of the North-Star 1975-cut protocol: freeze
    knowledge at `cut_year`, emit CLAIMS about post-cut transitions, then
    SETTLE them against recorded outcomes and bump `policy:*` posteriors.
  - Temporal hygiene is absolute:
      * train  = transitions with year_to   <= cut_year
      * claims = transitions with year_from >= cut_year
      * straddlers (year_from < cut_year < year_to) are excluded from
        BOTH sides — a straddling transition contains post-cut knowledge.
  - Abstention = no claim (hash bucket too thin, no prior transition).
    Never a filler guess: unmade claims are the honest record of what the
    policy could not say.
  - Settlement is exactly-once per claim; posterior trials must equal
    settled-claim counts (the ledger and the posteriors never disagree).

SKIPS until conflux/settlement.py exists. Run: `make test-phase2`.
"""

from __future__ import annotations

import pytest

movement = pytest.importorskip(
    "conflux.movement", reason="requires Phase 1 conflux/movement.py"
)
learning = pytest.importorskip(
    "conflux.learning", reason="Phase 2: conflux/learning.py not implemented yet"
)
settlement = pytest.importorskip(
    "conflux.settlement", reason="Phase 2: conflux/settlement.py not implemented yet"
)

pytestmark = pytest.mark.phase2

POLICIES = {"hash_mode", "reversion", "persistence", "majority"}


def _catalog(mk_anchor, specs: dict[str, list[tuple[int, float]]]):
    anchors = []
    for pid, pts in specs.items():
        anchors.extend(mk_anchor(pid, y, {"muslim": s}) for y, s in pts)
    return movement.build_catalog(anchors, groups=["muslim"])


@pytest.fixture
def simple_catalog(mk_anchor):
    """3 pre-cut transitions and 2 post-cut transitions per polity."""
    return _catalog(
        mk_anchor,
        {
            "upland": [(1900, 0.40), (1925, 0.45), (1950, 0.52), (1975, 0.60),
                       (2000, 0.68), (2020, 0.75)],
            "downland": [(1900, 0.80), (1925, 0.74), (1950, 0.68), (1975, 0.60),
                         (2000, 0.52), (2020, 0.45)],
            "flatland": [(1900, 0.50), (1925, 0.50), (1950, 0.50), (1975, 0.50),
                         (2000, 0.50), (2020, 0.50)],
        },
    )


# ---------------------------------------------------------------------------
# Claim construction — temporal hygiene
# ---------------------------------------------------------------------------


def test_claims_only_about_post_cut_transitions(simple_catalog) -> None:
    claims = settlement.make_policy_claims(simple_catalog, cut_year=1975, min_bucket_n=1)
    assert claims, "expected claims for post-cut transitions"
    for c in claims:
        assert c.cut_year == 1975
        assert c.hypothesis_id.startswith("policy:")
        assert c.hypothesis_id.split(":", 1)[1] in POLICIES
        assert c.predicted in {"up", "down", "flat"}
        assert 0.0 < c.stated_p <= 1.0
        # the transition being claimed must start at/after the cut
        assert c.year_from >= 1975


def test_straddling_transition_excluded_both_sides(mk_anchor) -> None:
    """A 1950→2000 transition straddles a 1975 cut: its outcome uses
    post-cut knowledge, so it may neither train nor be claimed."""
    catalog = _catalog(
        mk_anchor,
        {"straddleland": [(1950, 0.50), (2000, 0.70)]},
    )
    claims = settlement.make_policy_claims(catalog, cut_year=1975, min_bucket_n=1)
    assert claims == []


def test_no_post_cut_leakage_into_majority(mk_anchor) -> None:
    """Pre-cut world is all-up; post-cut world is all-down. If majority
    claims predict 'down', post-cut outcomes leaked into training."""
    catalog = _catalog(
        mk_anchor,
        {
            "a_land": [(1900, 0.40), (1925, 0.48), (1950, 0.56), (1975, 0.64),
                       (2000, 0.55), (2020, 0.45)],
            "b_land": [(1900, 0.42), (1925, 0.50), (1950, 0.58), (1975, 0.66),
                       (2000, 0.57), (2020, 0.47)],
        },
    )
    claims = settlement.make_policy_claims(catalog, cut_year=1975, min_bucket_n=1)
    maj = [c for c in claims if c.hypothesis_id == "policy:majority"]
    assert maj, "expected majority claims"
    assert all(c.predicted == "up" for c in maj), (
        "majority predicted the post-cut direction — training leaked past the cut"
    )


def test_abstention_is_no_claim_not_filler(simple_catalog) -> None:
    """With an impossibly strict bucket threshold, hash_mode must emit
    ZERO claims (not low-confidence guesses); other policies still claim."""
    claims = settlement.make_policy_claims(
        simple_catalog, cut_year=1975, min_bucket_n=10_000
    )
    by_policy = {p: [c for c in claims if c.hypothesis_id == f"policy:{p}"] for p in POLICIES}
    assert by_policy["hash_mode"] == []
    assert by_policy["majority"], "majority can always claim"


def test_claim_ids_deterministic(simple_catalog) -> None:
    """Same catalog + cut → identical claim ids (idempotent reruns must
    not mint duplicate ledger entries)."""
    a = settlement.make_policy_claims(simple_catalog, cut_year=1975, min_bucket_n=1)
    b = settlement.make_policy_claims(simple_catalog, cut_year=1975, min_bucket_n=1)
    assert [c.claim_id for c in a] == [c.claim_id for c in b]
    assert len({c.claim_id for c in a}) == len(a), "claim_ids must be unique"


# ---------------------------------------------------------------------------
# Settlement — exactly once, ledger ↔ posterior consistency
# ---------------------------------------------------------------------------


def test_settle_claims_bumps_policy_posteriors(simple_catalog) -> None:
    store = learning.TrustStore()
    claims = settlement.make_policy_claims(simple_catalog, cut_year=1975, min_bucket_n=1)
    n = settlement.settle_policy_claims(claims, simple_catalog, store)
    assert n == len(claims) > 0

    # ledger and posteriors agree exactly
    for p in POLICIES:
        hyp = f"policy:{p}"
        made = [c for c in claims if c.hypothesis_id == hyp]
        post = store.get(hyp)
        assert post.trials == len(made)
        successes = sum(1 for c in made if c.success)
        assert post.alpha == pytest.approx(1.0 + successes)
        assert post.beta == pytest.approx(1.0 + len(made) - successes)


def test_settlement_matches_recorded_outcomes(simple_catalog) -> None:
    """success == (predicted == catalog outcome) — settlement never
    reinterprets; it compares the claim to the tape."""
    store = learning.TrustStore()
    claims = settlement.make_policy_claims(simple_catalog, cut_year=1975, min_bucket_n=1)
    settlement.settle_policy_claims(claims, simple_catalog, store)
    outcome_by_key = {
        (r.polity_id, r.group, r.year_from, r.year_to): r.outcome
        for r in simple_catalog
    }
    for c in claims:
        actual = outcome_by_key[(c.polity_id, c.group, c.year_from, c.year_to)]
        assert c.settled
        assert c.success == (c.predicted == actual)


def test_resettling_same_claims_raises(simple_catalog) -> None:
    store = learning.TrustStore()
    claims = settlement.make_policy_claims(simple_catalog, cut_year=1975, min_bucket_n=1)
    settlement.settle_policy_claims(claims, simple_catalog, store)
    trials_before = store.get("policy:majority").trials
    with pytest.raises(ValueError):
        settlement.settle_policy_claims(claims, simple_catalog, store)
    assert store.get("policy:majority").trials == trials_before


# ---------------------------------------------------------------------------
# Integration smoke — the canonical cut on real demo data
# ---------------------------------------------------------------------------


def test_full_loop_on_real_demo_cohort(tmp_path) -> None:
    """1975-cut miniature on actual anchors: claims → settle → posteriors →
    persisted store. Asserts mechanics only — accuracy is the research
    result and lands in docs/REPORT_PHASE2_TRUST.md, not in this gate."""
    from conflux.model import ConfluxModel, DEMO_POLITIES

    model = ConfluxModel()
    anchors = [a for pid in DEMO_POLITIES for a in model.anchors_by_polity.get(pid, [])]
    catalog = movement.build_catalog(anchors, groups=["muslim", "christian", "jewish"])

    store = learning.TrustStore()
    claims = settlement.make_policy_claims(catalog, cut_year=1975, min_bucket_n=2)
    n = settlement.settle_policy_claims(claims, catalog, store)
    assert n > 0
    assert store.get("policy:majority").trials > 0

    path = tmp_path / "trust.json"
    store.save(path)
    loaded = learning.TrustStore.load(path)
    assert loaded.get("policy:majority").trials == store.get("policy:majority").trials
