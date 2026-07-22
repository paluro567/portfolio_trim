"""Stage B: reconstruct competing systems from cached walk-forward evidence.

Every system is produced by the PRODUCTION combination path
(`combine_model_evidence` + `assess_trim`) fed with the frozen per-model
evidence captured in Stage A — never by a reimplementation:

    baseline       seven models, historical_analogues excluded
    analogue_only  the analogue model alone
    combined       all eight, frozen correlation priors (rho = 0.5)
    shadow         identical scores to baseline; analogue evidence is
                   carried alongside for comparison (reported, unofficial)
    rho_XX         all eight with the analogue<->model prior patched to XX
                   (the three original regime-pair priors stay at 0.5)

Correlation-prior variants patch `model_correlation` only inside this
research harness; production code is never modified.
"""

import json
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pandas as pd

import mip.engine.evidence as decision
from mip.engine.trim import assess_trim
from mip.models.base import ScoreDiagnostics
from mip.models.evidence import NormalizedEvidence

ANALOGUE = "historical_analogues"
RHO_GRID = (0.25, 0.50, 0.75, 0.90)


def load_predictions(path: Path) -> pd.DataFrame:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    frame = pd.DataFrame([r for r in rows if "horizon" in r])
    if frame.empty:
        return frame
    frame["as_of"] = pd.to_datetime(frame["as_of"]).dt.date
    return frame


def _evidence(row: pd.Series) -> NormalizedEvidence:
    """Rebuild the minimal NormalizedEvidence the combiner consumes,
    exactly from the frozen captured fields."""
    z_raw = row.get("z_raw")
    diagnostics = None
    if z_raw is not None and not pd.isna(z_raw):
        diagnostics = ScoreDiagnostics(
            active_regimes=1,
            evidence_studies=1,
            max_n_eff=float(row["n_eff"]),
            mean_cross_correlation=0.0,
            agreement=1.0,
            z_raw=float(z_raw),
            z_clipped=float(z_raw),
            saturated=False,
        )
    excess = row.get("excess")
    expected = row.get("expected")
    return NormalizedEvidence(
        model_name=row["model"],
        model_version=1,
        symbol=row["symbol"],
        as_of=row["as_of"],
        horizon=row["horizon"],
        horizon_sessions={"1w": 5, "2w": 10, "1m": 21, "3m": 63, "6m": 126, "1y": 252}[
            row["horizon"]
        ],
        score=float(row["score"]),
        neutral=bool(row["neutral"]),
        expected_return=None if expected is None or pd.isna(expected) else float(expected),
        baseline_return=None,
        expected_excess_return=None if excess is None or pd.isna(excess) else float(excess),
        confidence=float(row["confidence"]),
        effective_sample_size=float(row["n_eff"]) if not pd.isna(row["n_eff"]) else 0.0,
        sample_size=0,
        historical_hit_rate=None,
        expected_volatility=None,
        downside_risk=None,
        upside_potential=None,
        evidence_strength=abs(float(row["score"]) - 50.0) / 50.0,
        contradictory_evidence=0.0,
        supporting_reasons=(),
        opposing_reasons=(),
        active_regimes=(),
        explanation="",
        diagnostics=diagnostics,
    )


@contextmanager
def analogue_rho(rho: float):
    """Patch ONLY the analogue<->model prior; regime pairs keep 0.5."""
    original = decision.model_correlation

    def patched(a: str, b: str) -> float:
        if a != b and ANALOGUE in (a, b):
            return rho
        return original(a, b)

    with mock.patch.object(decision, "model_correlation", patched):
        yield


def combine_rows(group: pd.DataFrame, models: list[str]) -> dict | None:
    per_model = {}
    for _, row in group.iterrows():
        if row["model"] in models:
            per_model[row["model"]] = _evidence(row)
    if not per_model:
        return None
    symbol = group.iloc[0]["symbol"]
    horizon = group.iloc[0]["horizon"]
    as_of = group.iloc[0]["as_of"]
    evidence = decision.combine_model_evidence(
        symbol, horizon, as_of, per_model, shadow=frozenset()
    )
    trim = assess_trim(evidence)
    return {
        "symbol": symbol,
        "as_of": as_of,
        "horizon": horizon,
        "evidence_score": evidence.combined_score,
        "confidence": evidence.combined_confidence,
        "expected_excess": evidence.expected_excess_return,
        "expected_return": evidence.expected_return,
        "contradiction": evidence.contradictory_evidence,
        "n_eff": evidence.effective_sample_size,
        "participating": len(evidence.participating_models),
        "trim_score": trim.trim_score,
        "band": trim.recommendation_label,
    }


def build_systems(frame: pd.DataFrame, rho_grid: tuple[float, ...] = RHO_GRID) -> pd.DataFrame:
    """All systems for every (symbol, as_of, horizon) in the cache."""
    all_models = sorted(frame["model"].unique())
    baseline_models = [m for m in all_models if m != ANALOGUE]
    out: list[dict] = []
    grouped = frame.groupby(["symbol", "as_of", "horizon"], sort=True)
    for _, group in grouped:
        baseline = combine_rows(group, baseline_models)
        analogue = combine_rows(group, [ANALOGUE])
        combined = combine_rows(group, all_models)
        for name, row in (
            ("baseline", baseline),
            ("analogue_only", analogue),
            ("combined", combined),
        ):
            if row is not None:
                out.append({"system": name, **row})
        for rho in rho_grid:
            if rho == 0.50:
                continue  # identical to `combined`
            with analogue_rho(rho):
                row = combine_rows(group, all_models)
            if row is not None:
                out.append({"system": f"rho_{int(rho * 100):02d}", **row})
    systems = pd.DataFrame(out)
    if not systems.empty:
        shadow = systems[systems["system"] == "baseline"].copy()
        shadow["system"] = "shadow"
        systems = pd.concat([systems, shadow], ignore_index=True)
    return systems
