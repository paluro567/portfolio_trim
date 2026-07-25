"""Pre-registration integrity (Stage 7).

A confirmatory validation run must be preceded by a FROZEN pre-registration: the
hypothesis, metrics, windows, success/failure/promotion criteria, known biases,
assumptions, allowed degrees of freedom, planned ablations, and limitations —
all declared BEFORE results are observed (the discipline the CPE followed by
hand). Freezing stamps a content hash over the scientific fields; any later edit
to those fields without re-freezing is detected as an integrity violation, so a
frozen plan cannot be silently modified once a run begins.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, replace
from pathlib import Path

from mip.core.exceptions import ConfigurationError
from mip.research.experiments.registry import ExperimentSpec

# Fields that define the scientific pre-registration (hashed). frozen_at and
# content_hash are metadata ABOUT the freeze and are excluded from the digest.
_CONTENT_FIELDS = (
    "experiment_id",
    "version",
    "hypothesis",
    "null_hypothesis",
    "primary_metric",
    "secondary_metrics",
    "validation_window",
    "holdout_window",
    "success_criteria",
    "failure_criteria",
    "promotion_criteria",
    "known_biases",
    "statistical_assumptions",
    "allowed_degrees_of_freedom",
    "planned_ablations",
    "limitations",
)


@dataclass(frozen=True)
class PreRegistration:
    experiment_id: str
    version: int
    hypothesis: str
    null_hypothesis: str
    primary_metric: str
    secondary_metrics: tuple[str, ...]
    validation_window: tuple[str, str]
    holdout_window: tuple[str, str]
    success_criteria: tuple[str, ...]
    failure_criteria: tuple[str, ...]
    promotion_criteria: tuple[str, ...]
    known_biases: tuple[str, ...]
    statistical_assumptions: tuple[str, ...]
    allowed_degrees_of_freedom: tuple[str, ...]
    planned_ablations: tuple[str, ...]
    limitations: tuple[str, ...]
    frozen_at: str | None = None
    content_hash: str | None = None

    def content_digest(self) -> str:
        payload = {name: _norm(getattr(self, name)) for name in _CONTENT_FIELDS}
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @property
    def is_frozen(self) -> bool:
        return self.frozen_at is not None and self.content_hash is not None

    def freeze(self, now: str) -> PreRegistration:
        if self.is_frozen:
            raise ConfigurationError(
                f"pre-registration for {self.experiment_id} is already frozen at {self.frozen_at}"
            )
        return replace(self, frozen_at=now, content_hash=self.content_digest())

    def verify_integrity(self) -> None:
        if not self.is_frozen:
            raise ConfigurationError("pre-registration is not frozen")
        if self.content_digest() != self.content_hash:
            raise ConfigurationError(
                "pre-registration integrity violation: content changed after freeze "
                f"(stored {self.content_hash[:12]}…, recomputed {self.content_digest()[:12]}…)"
            )

    def to_dict(self) -> dict:
        return {name: _norm(getattr(self, name)) for name in _all_field_names()}

    @classmethod
    def from_dict(cls, payload: dict) -> PreRegistration:
        data = dict(payload)
        for name in ("validation_window", "holdout_window"):
            data[name] = tuple(data[name])
        for name in (
            "secondary_metrics",
            "success_criteria",
            "failure_criteria",
            "promotion_criteria",
            "known_biases",
            "statistical_assumptions",
            "allowed_degrees_of_freedom",
            "planned_ablations",
            "limitations",
        ):
            data[name] = tuple(data.get(name, ()))
        return cls(**data)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True))

    @classmethod
    def load(cls, path: Path) -> PreRegistration:
        return cls.from_dict(json.loads(path.read_text()))


def _norm(value):
    if isinstance(value, tuple):
        return [_norm(v) for v in value]
    return value


def _all_field_names() -> tuple[str, ...]:
    return tuple(f.name for f in fields(PreRegistration))


def draft_from_spec(
    spec: ExperimentSpec,
    validation_window: tuple[str, str],
    holdout_window: tuple[str, str],
    primary_metric: str = "delta_direction_accuracy@1m",
) -> PreRegistration:
    """A pre-registration draft seeded from the experiment's declared record —
    the researcher edits it, then freezes it."""
    return PreRegistration(
        experiment_id=spec.experiment_id,
        version=spec.version,
        hypothesis=spec.hypothesis,
        null_hypothesis=spec.null_hypothesis,
        primary_metric=primary_metric,
        secondary_metrics=("brier@1m", "rank_correlation@1m", "ece@1m"),
        validation_window=validation_window,
        holdout_window=holdout_window,
        success_criteria=tuple(c.statement for c in spec.promotion_criteria),
        failure_criteria=("any promotion criterion fails, is inconclusive, or is not measurable",),
        promotion_criteria=tuple(c.statement for c in spec.promotion_criteria),
        known_biases=((spec.limitations,) if spec.limitations else ()),
        statistical_assumptions=(
            "overlapping windows handled by episode-based effective sample",
            "combined-baseline uncertainty via paired circular block bootstrap",
        ),
        allowed_degrees_of_freedom=("frozen constants only; no tuning on evaluation data",),
        planned_ablations=spec.ablation_dimensions,
        limitations=((spec.limitations,) if spec.limitations else ()),
    )
