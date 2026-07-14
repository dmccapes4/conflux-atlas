"""Phase 1 gate — place vectors, cosine retrieval, ablation hooks.

CONTRACT (rationale in docs/PHASE1_TEST_SPEC.md):

  - `place_vector()` produces a fixed-length, L2-normalized numpy vector
    for a (polity, group, year) place. Dimension is exported as
    `movement.PLACE_VECTOR_DIM` so drift is caught here, not in analysis.
  - Confidence weighting is a flag (`weighted=`), because the Phase 1
    publishable ablation is confidence-weighted vs unweighted retrieval.
    Both variants must exist; the tests only require that they differ
    when confidence differs (the *research question* of which is better
    is answered by the scorecard, never asserted in tests).
  - Retrieval is plain numpy (`cosine_topk`) — no GPU, no external index.
  - The catalog keeps identity (polity/group/year) as metadata BESIDE the
    vector, never inside it: retrieval should surface cross-polity
    analogies ("Egypt 1950 looks like Syria 1970"), not identity matches.

SKIPS until conflux/movement.py exists. Run: `make test-phase1`.
"""

from __future__ import annotations

import numpy as np
import pytest

movement = pytest.importorskip(
    "conflux.movement", reason="Phase 1: conflux/movement.py not implemented yet"
)

pytestmark = pytest.mark.phase1


# ---------------------------------------------------------------------------
# place_vector
# ---------------------------------------------------------------------------


def _mk_events(mk_anchor, deltas=(0.05, 0.03)):
    """Small series with two transitions so vol/velocity are defined."""
    share = 0.60
    anchors = [mk_anchor("vecland", 1950, {"muslim": share})]
    year = 1950
    for d in deltas:
        share += d
        year += 25
        anchors.append(mk_anchor("vecland", year, {"muslim": round(share, 4)}))
    return movement.movement_events(anchors, group="muslim")


def test_place_vector_shape_norm_determinism(mk_anchor) -> None:
    events = _mk_events(mk_anchor)
    v1 = movement.place_vector(events[-1])
    v2 = movement.place_vector(events[-1])
    assert isinstance(v1, np.ndarray)
    assert v1.shape == (movement.PLACE_VECTOR_DIM,)
    assert v1.dtype == np.float32
    assert np.linalg.norm(v1) == pytest.approx(1.0, abs=1e-5)
    assert np.array_equal(v1, v2)  # bitwise deterministic


def test_place_vector_finite_on_degenerate_input(mk_anchor) -> None:
    """First transition of a series (no velocity/vol history) must still
    produce a finite unit vector — sparse series are the normal case."""
    anchors = [
        mk_anchor("sparseland", 1900, {"muslim": 0.5}),
        mk_anchor("sparseland", 2000, {"muslim": 0.5}),
    ]
    ev = movement.movement_events(anchors, group="muslim")[0]
    v = movement.place_vector(ev)
    assert np.all(np.isfinite(v))
    assert np.linalg.norm(v) == pytest.approx(1.0, abs=1e-5)


def test_place_vector_confidence_ablation_hook(mk_anchor) -> None:
    """weighted=True must incorporate confidence; weighted=False must not.
    Two places identical except confidence: unweighted vectors match,
    weighted vectors differ. Which retrieves better = scorecard question."""
    hi = mk_anchor("a_land", 1950, {"muslim": 0.7}, confidence=0.9)
    hi2 = mk_anchor("a_land", 1975, {"muslim": 0.75}, confidence=0.9)
    lo = mk_anchor("b_land", 1950, {"muslim": 0.7}, confidence=0.3)
    lo2 = mk_anchor("b_land", 1975, {"muslim": 0.75}, confidence=0.3)
    ev_hi = movement.movement_events([hi, hi2], group="muslim")[0]
    ev_lo = movement.movement_events([lo, lo2], group="muslim")[0]

    unw_hi = movement.place_vector(ev_hi, weighted=False)
    unw_lo = movement.place_vector(ev_lo, weighted=False)
    assert np.allclose(unw_hi, unw_lo, atol=1e-6)

    w_hi = movement.place_vector(ev_hi, weighted=True)
    w_lo = movement.place_vector(ev_lo, weighted=True)
    assert not np.allclose(w_hi, w_lo, atol=1e-6)


# ---------------------------------------------------------------------------
# catalog + cosine retrieval
# ---------------------------------------------------------------------------


def _mk_catalog(mk_anchor):
    """3 polities × 3 anchors → 6 transitions; enough to rank."""
    rows = []
    specs = {
        "growland": [(1950, 0.50), (1975, 0.60), (2000, 0.70)],   # steady up
        "shrinkland": [(1950, 0.70), (1975, 0.60), (2000, 0.50)],  # steady down
        "flatland": [(1950, 0.60), (1975, 0.60), (2000, 0.60)],   # flat
    }
    for pid, pts in specs.items():
        rows.extend(mk_anchor(pid, y, {"muslim": s}) for y, s in pts)
    return movement.build_catalog(rows, groups=["muslim"])


def test_catalog_rows_carry_metadata_not_identity_in_vector(mk_anchor) -> None:
    catalog = _mk_catalog(mk_anchor)
    assert len(catalog) == 6
    for row in catalog:
        assert row.polity_id in {"growland", "shrinkland", "flatland"}
        assert row.group == "muslim"
        assert row.vector.shape == (movement.PLACE_VECTOR_DIM,)
        assert isinstance(row.origin_hash, str)
        # outcome direction is stored for scorecard settlement
        assert row.outcome in {"up", "down", "flat"}


def test_cosine_topk_self_similarity(mk_anchor) -> None:
    """A catalog vector's nearest neighbor must be itself with score ~1 —
    the minimal correctness proof for the similarity math."""
    catalog = _mk_catalog(mk_anchor)
    mat = np.stack([r.vector for r in catalog])
    idx, scores = movement.cosine_topk(catalog[0].vector, mat, k=3)
    assert idx[0] == 0
    assert scores[0] == pytest.approx(1.0, abs=1e-5)
    # scores sorted descending, all in [-1, 1]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
    assert np.all(scores <= 1.0 + 1e-6) and np.all(scores >= -1.0 - 1e-6)


def test_cosine_topk_finds_analogous_movement(mk_anchor) -> None:
    """Steady-up transitions should rank each other above steady-down ones.
    This is a *constructed* geometry check, not a historical claim."""
    catalog = _mk_catalog(mk_anchor)
    mat = np.stack([r.vector for r in catalog])
    up_rows = [i for i, r in enumerate(catalog) if r.polity_id == "growland"]
    down_rows = [i for i, r in enumerate(catalog) if r.polity_id == "shrinkland"]

    query = catalog[up_rows[0]].vector
    _, scores = movement.cosine_topk(query, mat, k=len(catalog))
    idx, _ = movement.cosine_topk(query, mat, k=len(catalog))
    rank = {int(i): pos for pos, i in enumerate(idx)}
    best_other_up = min(rank[i] for i in up_rows if i != up_rows[0])
    best_down = min(rank[i] for i in down_rows)
    assert best_other_up < best_down, (
        "an analogous up-movement should outrank a down-movement"
    )


def test_cosine_topk_k_larger_than_catalog(mk_anchor) -> None:
    catalog = _mk_catalog(mk_anchor)
    mat = np.stack([r.vector for r in catalog])
    idx, scores = movement.cosine_topk(catalog[0].vector, mat, k=100)
    assert len(idx) == len(catalog) == len(scores)


# ---------------------------------------------------------------------------
# hash catalog grouping (mode outcome per place)
# ---------------------------------------------------------------------------


def test_hash_catalog_mode_outcomes(mk_anchor) -> None:
    """Group catalog rows by origin_hash → outcome histogram + mode.
    This is the lookup table the scorecard uses as the 'hash mode' policy."""
    catalog = _mk_catalog(mk_anchor)
    table = movement.hash_outcome_table(catalog, min_n=1)
    assert table, "expected at least one hash bucket"
    for entry in table.values():
        assert entry.n >= 1
        assert entry.mode in {"up", "down", "flat"}
        assert abs(sum(entry.dist.values()) - 1.0) < 1e-6
        # purity = share of the modal outcome; must be consistent with dist
        assert entry.purity == pytest.approx(max(entry.dist.values()))


def test_hash_outcome_table_respects_min_n(mk_anchor) -> None:
    """min_n guards against 1-sample buckets masquerading as knowledge —
    the same discipline as min-bucket-n in the ptv-embed-lab hash catalog."""
    catalog = _mk_catalog(mk_anchor)
    table_all = movement.hash_outcome_table(catalog, min_n=1)
    table_strict = movement.hash_outcome_table(catalog, min_n=10_000)
    assert len(table_strict) == 0
    assert len(table_all) >= len(table_strict)
