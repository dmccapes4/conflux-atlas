"""Beta-Bernoulli trust posteriors + claim ledger (nakatomi / ptv lineage).

Near-verbatim port of ``ptv_embed/learning.py`` with two deliberate
departures: demographic ``Claim`` instead of clinical ``Prediction``, and
full ``save`` / ``load`` so the settlement tape outlives a process.

Rule (identical to nakatomi): *nothing but a settled outcome may bump a
posterior.* ``record()`` is free; only ``settle()`` moves belief.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Posterior:
    """Beta(α, β) posterior. Uniform prior = Beta(1, 1)."""

    alpha: float = 1.0
    beta: float = 1.0
    trials: int = 0

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def variance(self) -> float:
        a, b = self.alpha, self.beta
        return (a * b) / ((a + b) ** 2 * (a + b + 1))

    def bumped(self, success: bool, weight: float = 1.0) -> Posterior:
        """Graded (fractional) evidence: ``weight`` < 1 discounts the bump.

        Used for method-family independence discounts (connascence §2.1)
        and one-hop partial settlement (§2.3). ``weight=1.0`` is the
        classic full Bernoulli update; ``trials`` counts bumps, not mass.
        """
        w = float(weight)
        if not 0.0 < w <= 1.0:
            raise ValueError(f"weight must be in (0, 1]: {w}")
        return Posterior(
            alpha=self.alpha + (w if success else 0.0),
            beta=self.beta + (0.0 if success else w),
            trials=self.trials + 1,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "alpha": self.alpha,
            "beta": self.beta,
            "trials": self.trials,
            "mean": self.mean,
            "variance": self.variance,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Posterior:
        return cls(
            alpha=float(d["alpha"]),
            beta=float(d["beta"]),
            trials=int(d["trials"]),
        )


@dataclass
class Claim:
    """One falsifiable statement, made at a cut, settled later."""

    claim_id: str
    hypothesis_id: str
    polity_id: str
    group: str
    cut_year: int
    predicted: str
    stated_p: float
    train_n: int
    year_from: int = 0
    year_to: int = 0
    made_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    settled: bool = False
    success: bool | None = None
    settled_at: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Claim:
        known = {
            "claim_id",
            "hypothesis_id",
            "polity_id",
            "group",
            "cut_year",
            "predicted",
            "stated_p",
            "train_n",
            "year_from",
            "year_to",
            "made_at",
            "settled",
            "success",
            "settled_at",
            "meta",
        }
        return cls(**{k: d[k] for k in known if k in d})


class TrustStore:
    """In-memory hypothesis posteriors + claim ledger."""

    def __init__(self) -> None:
        self.posteriors: dict[str, Posterior] = {}
        self.ledger: list[Claim] = []

    def get(self, hypothesis_id: str) -> Posterior:
        """Read-only: unknown keys return the uniform prior without insert."""
        return self.posteriors.get(hypothesis_id, Posterior())

    def bump(self, hypothesis_id: str, success: bool, weight: float = 1.0) -> Posterior:
        cur = self.get(hypothesis_id)
        nxt = cur.bumped(success, weight=weight)
        self.posteriors[hypothesis_id] = nxt
        return nxt

    def record(self, claim: Claim) -> None:
        """Append to the ledger. Never touches a posterior."""
        self.ledger.append(claim)

    def settle(self, claim: Claim, success: bool, weight: float = 1.0) -> Posterior:
        if claim.settled:
            raise ValueError(f"already settled: {claim.claim_id}")
        claim.settled = True
        claim.success = bool(success)
        claim.settled_at = datetime.now(timezone.utc).isoformat()
        if weight != 1.0:
            claim.meta["settle_weight"] = float(weight)
        return self.bump(claim.hypothesis_id, bool(success), weight=weight)

    def summary(self) -> list[dict[str, Any]]:
        rows = []
        for hid, post in sorted(self.posteriors.items(), key=lambda x: -x[1].mean):
            rows.append({"hypothesis_id": hid, **post.to_dict()})
        return rows

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "posteriors": {k: v.to_dict() for k, v in self.posteriors.items()},
            "ledger": [c.to_dict() for c in self.ledger],
            "n_claims": len(self.ledger),
            "n_settled": sum(1 for c in self.ledger if c.settled),
            "n_success": sum(1 for c in self.ledger if c.settled and c.success),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> TrustStore:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        store = cls()
        for hid, pdata in (data.get("posteriors") or {}).items():
            store.posteriors[hid] = Posterior.from_dict(pdata)
        for row in data.get("ledger") or []:
            store.ledger.append(Claim.from_dict(row))
        return store
