"""Generalized walk-forward capture harness (Stage 3).

The model-agnostic promotion of the CPE capture driver. Given a plan and an
experiment id, it runs the registry's PRODUCTION models plus the experiment
model IN SHADOW over the scoring grid, capturing each model's NormalizedEvidence
per (symbol, as_of, horizon). It is resumable, de-duplicates, isolates model
failures, distinguishes neutral evidence from execution failure, supports shared
baseline capture with manifest-gated reuse, asserts point-in-time safety, and
records timing/cost. It contains NO experiment-specific branches — everything
model-specific comes from the registry and the model contract.

Row schema is the shipped ``mip.validation.walkforward._row`` (reused, not
re-invented), so Stage-4 reconstruction consumes it via the existing
``combine_rows``.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path

from mip.core.db import session_scope
from mip.core.exceptions import ConfigurationError
from mip.core.logging import get_logger
from mip.models.evidence import normalize_scores
from mip.research.experiments.registry import EXPERIMENTS, Role, get_experiment
from mip.validation.walkforward import _row

logger = get_logger(__name__)

# Leakage marker: a model must never resolve a scoring date AFTER the requested
# one (that would consume post-date information). Enforced strictly (G3).
PIT_VIOLATION = "pit_violation_resolved_after_scoring_date"


class ModelSet(StrEnum):
    BASELINE = "baseline"  # production models only (shared baseline capture)
    EXPERIMENT = "experiment"  # the experiment model only (reuses a baseline cache)
    ALL = "all"  # production + experiment in one pass


@dataclass(frozen=True)
class WalkForwardPlan:
    experiment_id: str
    targets: tuple[str, ...]
    scoring_dates: tuple[date, ...]
    holdout_start: date
    schedule: str = "monthly-first-trading-day"
    seeds: dict[str, int] = field(default_factory=lambda: {"block_bootstrap": 7})

    def __post_init__(self) -> None:
        if not self.targets:
            raise ConfigurationError("plan needs at least one target symbol")
        if not self.scoring_dates:
            raise ConfigurationError("plan needs at least one scoring date")


@dataclass
class CaptureStats:
    pairs: int = 0
    evidence_rows: int = 0
    neutral_rows: int = 0
    failures: int = 0
    pit_violations: int = 0
    elapsed_seconds: float = 0.0
    failures_by_model: Counter = field(default_factory=Counter)

    def to_dict(self) -> dict:
        return {
            "pairs": self.pairs,
            "evidence_rows": self.evidence_rows,
            "neutral_rows": self.neutral_rows,
            "failures": self.failures,
            "pit_violations": self.pit_violations,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "failures_by_model": dict(self.failures_by_model),
        }


def _production_ids() -> tuple[str, ...]:
    return tuple(s.experiment_id for s in EXPERIMENTS if s.role is Role.PRODUCTION)


def monthly_plan(
    session,
    experiment_id: str,
    start: date,
    holdout_start: date,
    history_cutoff: date | None = None,
) -> WalkForwardPlan:
    """A default plan: first trading day of each month from ``start``, targets =
    stocks with price history by ``history_cutoff`` (default ``start``). Reads
    only the trading calendar + instruments; deterministic ordering."""
    from sqlalchemy import func, select

    from mip.domain.models import DailyPrice, Instrument, TradingDay

    days = list(
        session.scalars(
            select(TradingDay.calendar_date)
            .where(TradingDay.calendar_date >= start)
            .order_by(TradingDay.calendar_date)
        )
    )
    seen: set[tuple[int, int]] = set()
    grid: list[date] = []
    for d in days:
        if (d.year, d.month) not in seen:
            seen.add((d.year, d.month))
            grid.append(d)
    cutoff = history_cutoff or start
    rows = session.execute(
        select(Instrument.symbol, func.min(DailyPrice.price_date))
        .join(DailyPrice, DailyPrice.instrument_id == Instrument.id)
        .where(Instrument.instrument_type == "stock")
        .group_by(Instrument.symbol)
    ).all()
    targets = tuple(sorted(s for s, first in rows if first is not None and first <= cutoff))
    return WalkForwardPlan(
        experiment_id=experiment_id,
        targets=targets,
        scoring_dates=tuple(grid),
        holdout_start=holdout_start,
    )


class WalkForwardHarness:
    """Drives capture for one experiment. Reads the registry for the production
    model set and the experiment model — no hardcoded model names."""

    def __init__(self, factory, artifacts_dir: Path) -> None:
        self._factory = factory
        self._dir = Path(artifacts_dir)

    def output_path(self, experiment_id: str, model_set: ModelSet) -> Path:
        return self._dir / experiment_id / f"predictions_{model_set.value}.jsonl"

    def _done(self, path: Path) -> set[str]:
        if not path.exists():
            return set()
        done = set()
        for line in path.read_text().splitlines():
            if not line:
                continue
            r = json.loads(line)
            if r.get("marker") == "pair_done":
                done.add(f"{r['symbol']}|{r['as_of']}")
        return done

    def _models_to_run(self, plan: WalkForwardPlan, model_set: ModelSet) -> list[str]:
        spec = get_experiment(plan.experiment_id)
        if spec.role is not Role.SHADOW:
            raise ConfigurationError(
                f"{plan.experiment_id} is not a shadow experiment; refusing to "
                "run it through the shadow capture harness"
            )
        if model_set is ModelSet.BASELINE:
            return list(_production_ids())
        if model_set is ModelSet.EXPERIMENT:
            return [plan.experiment_id]
        return [*_production_ids(), plan.experiment_id]

    def capture(
        self,
        plan: WalkForwardPlan,
        model_set: ModelSet = ModelSet.ALL,
        strict_pit: bool = True,
    ) -> CaptureStats:
        model_ids = self._models_to_run(plan, model_set)
        classes = {s.experiment_id: s.model_cls for s in EXPERIMENTS}
        out = self.output_path(plan.experiment_id, model_set)
        out.parent.mkdir(parents=True, exist_ok=True)
        done = self._done(out)
        stats = CaptureStats()
        started = time.monotonic()

        with session_scope(self._factory) as session, out.open("a") as handle:
            for as_of in sorted(plan.scoring_dates):
                # instantiate each model once per scoring date; reused across
                # symbols at this date (model-agnostic; no per-model caching hook)
                instances = {mid: classes[mid](session) for mid in model_ids}
                for symbol in sorted(plan.targets):
                    key = f"{symbol}|{as_of.isoformat()}"
                    if key in done:
                        continue
                    rows = self._capture_pair(session, instances, symbol, as_of, strict_pit, stats)
                    rows.append(
                        {"marker": "pair_done", "symbol": symbol, "as_of": as_of.isoformat()}
                    )
                    for row in rows:
                        handle.write(json.dumps(row) + "\n")
                    handle.flush()
                    stats.pairs += 1
                session.expunge_all()
                logger.info(
                    "walkforward.date_done",
                    experiment=plan.experiment_id,
                    as_of=as_of.isoformat(),
                    pairs=stats.pairs,
                )
        stats.elapsed_seconds = time.monotonic() - started
        return stats

    def _capture_pair(self, session, instances, symbol, as_of, strict_pit, stats) -> list[dict]:
        rows: list[dict] = []
        for model_id, model in instances.items():
            try:
                evidence = normalize_scores(model.evaluate(symbol, as_of=as_of))
            except ConfigurationError as exc:
                # honest OMISSION (the model cannot evaluate here) — distinct
                # from a crash and distinct from neutral evidence
                rows.append(
                    {
                        "marker": "omitted",
                        "symbol": symbol,
                        "as_of": as_of.isoformat(),
                        "model": model_id,
                        "reason": str(exc)[:150],
                    }
                )
                continue
            except Exception as exc:  # noqa: BLE001 - a failed model must not abort the run
                session.rollback()
                stats.failures += 1
                stats.failures_by_model[model_id] += 1
                rows.append(
                    {
                        "marker": "model_error",
                        "symbol": symbol,
                        "as_of": as_of.isoformat(),
                        "model": model_id,
                        "error": str(exc)[:150],
                    }
                )
                continue
            for ev in evidence:
                if ev.as_of > as_of:  # PIT: resolved a date after the scoring cutoff
                    stats.pit_violations += 1
                    if strict_pit:
                        raise AssertionError(
                            f"{PIT_VIOLATION}: {model_id} {symbol}@{as_of} resolved {ev.as_of}"
                        )
                row = _row(symbol, as_of, ev.model_name, ev)
                if ev.context:
                    row["fallback_level"] = ev.context.get("fallback_level")
                rows.append(row)
                stats.evidence_rows += 1
                if ev.neutral:
                    stats.neutral_rows += 1
        return rows
