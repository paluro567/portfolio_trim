"""Stage A of the analogue validation: walk-forward evidence capture.

For every (symbol, scoring date) on the grid, run every model exactly as
production does — `normalize_scores(model.evaluate(symbol, as_of=date))`
— and persist the per-model evidence essentials the decision engine
consumes. Predictions are frozen at capture time; outcomes are computed
later from prices only. Resumable: dates already captured are skipped.

Run:
    uv run python -m mip.validation.walkforward predictions AMD AMZN ...
    uv run python -m mip.validation.walkforward variants AMD AMZN ...
"""

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

from sqlalchemy import select

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope
from mip.core.exceptions import ConfigurationError
from mip.core.logging import get_logger
from mip.domain.models import TradingDay
from mip.models import ALL_MODELS
from mip.models.analogues import HistoricalAnalogueModel
from mip.models.evidence import normalize_scores
from mip.research.analogues import AnalogueConfig

logger = get_logger(__name__)

# override with MIP_VALIDATION_DIR for hardened/embargoed reruns
ARTIFACTS = Path(os.environ.get("MIP_VALIDATION_DIR", "data/validation/analogue_v1"))
START = date(2019, 1, 1)
END = date(2026, 6, 30)
MAIN_STRIDE = 10  # every 10th trading session
VARIANT_STRIDE = 21  # monthly, for sensitivity/ablation grids

BIG = 10**6  # disables a selection stage without touching frozen code
VARIANTS: dict[str, AnalogueConfig] = {
    "full": AnalogueConfig(),
    "no_market": AnalogueConfig(market_weight=0.0, market_candidate_count=BIG),
    "no_sector": AnalogueConfig(sector_weight=0.0, sector_candidate_count=BIG),
    "no_company": AnalogueConfig(company_weight=0.0),
    "no_catalysts": AnalogueConfig(catalyst_weight=0.0),
    "market_only": AnalogueConfig(
        sector_weight=0.0, company_weight=1e-9, catalyst_weight=0.0, sector_candidate_count=BIG
    ),
    "company_only": AnalogueConfig(
        market_weight=0.0,
        sector_weight=0.0,
        catalyst_weight=0.0,
        market_candidate_count=BIG,
        sector_candidate_count=BIG,
    ),
    "market_company": AnalogueConfig(
        market_weight=0.5,
        sector_weight=0.0,
        company_weight=0.5,
        catalyst_weight=0.0,
        sector_candidate_count=BIG,
    ),
    "equal_weights": AnalogueConfig(
        market_weight=0.25, sector_weight=0.25, company_weight=0.25, catalyst_weight=0.25
    ),
    "company_heavy": AnalogueConfig(
        market_weight=0.15, sector_weight=0.15, company_weight=0.55, catalyst_weight=0.15
    ),
    "market_heavy": AnalogueConfig(
        market_weight=0.55, sector_weight=0.15, company_weight=0.20, catalyst_weight=0.10
    ),
    "catalyst_light": AnalogueConfig(
        market_weight=0.40, sector_weight=0.22, company_weight=0.33, catalyst_weight=0.05
    ),
}


def grid_dates(session, stride: int) -> list[date]:
    sessions = list(
        session.scalars(
            select(TradingDay.calendar_date)
            .where(TradingDay.calendar_date >= START, TradingDay.calendar_date <= END)
            .order_by(TradingDay.calendar_date)
        )
    )
    return sessions[::stride]


def _quality(evidence) -> dict | None:
    context = evidence.context or {}
    analogues = context.get("analogues") or []
    if not analogues:
        return None
    similarities = [a["overall"] for a in analogues]
    years = [a["date"][:4] for a in analogues]
    outcomes = context.get("outcomes") or {}
    weighted = outcomes.get("weighted_mean_return")
    unweighted = outcomes.get("mean_return")
    return {
        "n": len(analogues),
        "mean_similarity": sum(similarities) / len(similarities),
        "min_similarity": min(similarities),
        "coverage": sum(a["coverage"] for a in analogues) / len(analogues),
        "year_concentration": max(years.count(y) for y in set(years)) / len(years),
        "weighted_unweighted_gap": (
            weighted - unweighted if None not in (weighted, unweighted) else None
        ),
    }


def _row(symbol: str, as_of: date, model: str, evidence) -> dict:
    diagnostics = evidence.diagnostics
    return {
        "symbol": symbol,
        "as_of": as_of.isoformat(),
        "horizon": evidence.horizon,
        "model": model,
        "score": evidence.score,
        "confidence": evidence.confidence,
        "neutral": evidence.neutral,
        "excess": evidence.expected_excess_return,
        "expected": evidence.expected_return,
        "z_raw": diagnostics.z_raw if diagnostics else None,
        "n_eff": evidence.effective_sample_size,
    }


def _done_dates(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {json.loads(line)["as_of"] for line in path.read_text().splitlines() if line}


def self_check(factory, symbol: str, as_of) -> dict | None:
    """Leakage invariant + diagnostics for one scoring date: reconcile the
    analogue selection against the central observability rule. Fails
    LOUDLY (strict) on any violation — a validation run must never
    silently consume an unobservable label."""
    from mip.research.analogues import AnalogueEngine
    from mip.validation.eligibility import verify_analogue_observability

    with session_scope(factory) as session:
        try:
            result = AnalogueEngine(session).find(symbol, as_of=as_of)
        except ConfigurationError:
            return None
        if result.insufficient is not None:
            return None
        diagnostics = verify_analogue_observability(session, result, strict=True)
    payload = diagnostics.to_dict()
    payload["leakage_diagnostics"] = True
    return payload


def run_predictions(symbols: list[str]) -> None:
    factory = open_session_factory()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for symbol in symbols:
        out = ARTIFACTS / f"predictions_{symbol}.jsonl"
        done = _done_dates(out)
        with session_scope(factory) as session:
            dates = grid_dates(session, MAIN_STRIDE)
        started = time.monotonic()
        with out.open("a") as handle:
            for as_of in dates:
                if as_of.isoformat() in done:
                    continue
                rows: list[dict] = []
                with session_scope(factory) as session:
                    for model_cls in ALL_MODELS:
                        try:
                            batch = normalize_scores(
                                model_cls(session).evaluate(symbol, as_of=as_of)
                            )
                        except ConfigurationError as exc:
                            rows.append(
                                {
                                    "symbol": symbol,
                                    "as_of": as_of.isoformat(),
                                    "model": model_cls.name,
                                    "omitted": str(exc)[:120],
                                }
                            )
                            continue
                        for evidence in batch:
                            row = _row(symbol, as_of, evidence.model_name, evidence)
                            if evidence.model_name == "historical_analogues":
                                row["quality"] = _quality(evidence)
                            rows.append(row)
                diagnostics = self_check(factory, symbol, as_of)
                if diagnostics is not None:
                    rows.append(diagnostics)
                for row in rows:
                    handle.write(json.dumps(row) + "\n")
                handle.flush()
        logger.info(
            "validation.predictions_done",
            symbol=symbol,
            dates=len(dates),
            minutes=round((time.monotonic() - started) / 60, 1),
        )


def run_variants(symbols: list[str]) -> None:
    factory = open_session_factory()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for symbol in symbols:
        out = ARTIFACTS / f"variants_{symbol}.jsonl"
        done = _done_dates(out)
        with session_scope(factory) as session:
            dates = grid_dates(session, VARIANT_STRIDE)
        with out.open("a") as handle:
            for as_of in dates:
                if as_of.isoformat() in done:
                    continue
                rows = []
                with session_scope(factory) as session:
                    for name, config in VARIANTS.items():
                        try:
                            batch = normalize_scores(
                                HistoricalAnalogueModel(session, config).evaluate(
                                    symbol, as_of=as_of
                                )
                            )
                        except ConfigurationError:
                            continue
                        for evidence in batch:
                            row = _row(symbol, as_of, "historical_analogues", evidence)
                            row["variant"] = name
                            rows.append(row)
                if not rows:  # keep resume idempotent even when nothing was scorable
                    rows.append({"symbol": symbol, "as_of": as_of.isoformat(), "sentinel": True})
                for row in rows:
                    handle.write(json.dumps(row) + "\n")
                handle.flush()
        logger.info("validation.variants_done", symbol=symbol)


if __name__ == "__main__":
    mode, symbols = sys.argv[1], [s.upper() for s in sys.argv[2:]]
    if mode == "predictions":
        run_predictions(symbols)
    elif mode == "variants":
        run_variants(symbols)
    else:  # pragma: no cover
        raise SystemExit(f"unknown mode {mode!r}")
