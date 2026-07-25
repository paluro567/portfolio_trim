"""The typed boundary between the cross-sectional matcher and the outcome
engine (research-wide vocabulary, not CPE-specific).

The matcher's ONLY output is a ``HistoricalMatchSet``: which historical
``(symbol, date)`` observations satisfied a condition set, each carrying a
weight (uniform in version 1; a future weigher supplies non-uniform weights
without any change here or in the matcher). The outcome engine consumes match
sets and knows nothing about how they were discovered; the baseline population
is itself a ``HistoricalMatchSet`` (empty condition tuple) flowing through the
identical outcome pipeline — no special-case baseline path.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from mip.research.conditions import Condition


@dataclass(frozen=True)
class MatchedObservation:
    """One historical observation selected by the matcher. ``weight`` is 1.0 in
    version 1; future match weighting (sector/industry/factor/size similarity)
    supplies a different weight and every downstream statistic adapts through
    the WeightedSample abstraction."""

    symbol: str
    date: date
    weight: float = 1.0


@dataclass(frozen=True)
class HistoricalMatchSet:
    """A pooled set of matched observations plus the conditions that defined it.
    ``conditions`` is empty for the unconditional baseline set."""

    label: str  # fallback-level name, or 'baseline'
    conditions: tuple[Condition, ...]
    observations: tuple[MatchedObservation, ...]

    def __len__(self) -> int:
        return len(self.observations)

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(o.symbol for o in self.observations)

    @property
    def dates(self) -> tuple[date, ...]:
        return tuple(o.date for o in self.observations)

    @property
    def weights(self) -> np.ndarray:
        return np.array([o.weight for o in self.observations], dtype=float)

    def without(self, condition_name: str) -> "HistoricalMatchSet":
        """Reserved for leave-one-condition-out diagnostics: the same matcher
        re-runs with one condition dropped and produces a new match set; this
        helper documents the intended identity for that flow (the engine
        rebuilds rather than filtering, since dropping a condition changes which
        observations qualify)."""
        remaining = tuple(c for c in self.conditions if c.name != condition_name)
        return HistoricalMatchSet(label=self.label, conditions=remaining, observations=())

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "conditions": [c.to_dict() for c in self.conditions],
            "n": len(self),
            "distinct_symbols": len(set(self.symbols)),
        }


def observations_from(pairs: Sequence[tuple[str, date]], weight: float = 1.0) -> tuple:
    """Build a deterministic, sorted tuple of uniform-weight observations from
    ``(symbol, date)`` pairs. Sorting makes pooled results order-independent
    (validation gate G5)."""
    ordered = sorted(set(pairs), key=lambda p: (p[1], p[0]))
    return tuple(MatchedObservation(symbol=s, date=d, weight=weight) for s, d in ordered)
