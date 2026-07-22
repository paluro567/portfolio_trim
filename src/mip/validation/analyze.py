"""Stage D orchestration: merge frozen predictions with realized
outcomes, produce every validation table (CSV/JSON), and issue the
explicit shadow-mode decision from pre-declared criteria.

The calibration/holdout discipline: sensitivity and ablation readings
are taken on the calibration period only; the frozen rho=0.5 Combined
system is judged against Baseline on the untouched holdout period.
Nothing in production configuration is changed by this module.

Run:  uv run python -m mip.validation.analyze
"""

import json
import sys
from datetime import date

import pandas as pd

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope
from mip.domain.models import DailyPrice, Instrument  # noqa: F401 (session warm-up)
from mip.repositories.features import FeatureRepository
from mip.repositories.instruments import InstrumentRepository
from mip.validation import metrics as vm
from mip.validation.realized import realized_outcomes
from mip.validation.systems import build_systems, load_predictions
from mip.validation.walkforward import ARTIFACTS

SYMBOLS = ("AMD", "AMZN", "CRM", "ADBE", "HNST", "TSLA", "NOW")
HOLDOUT_START = date(2024, 1, 1)
HORIZON_ORDER = ("1w", "2w", "1m", "3m", "6m", "1y")
CORE_SYSTEMS = ("baseline", "analogue_only", "combined")


def _load_all_predictions() -> pd.DataFrame:
    frames = []
    for symbol in SYMBOLS:
        path = ARTIFACTS / f"predictions_{symbol}.jsonl"
        if path.exists():
            frames.append(load_predictions(path))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _load_variants() -> pd.DataFrame:
    frames = []
    for path in sorted(ARTIFACTS.glob("variants_*.jsonl")):
        frame = load_predictions(path)
        if not frame.empty:
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _regime_labels(factory, dates: list[date], per_symbol_dates: dict) -> pd.DataFrame:
    """Deterministic regime labels for every scoring date, from stored
    market features (the same values production used)."""
    with session_scope(factory) as session:
        features = FeatureRepository(session)
        instruments = InstrumentRepository(session)

        def market(name: str) -> pd.Series:
            definition = features.get_definition(name)
            return (
                features.get_market_series(definition.id) if definition else pd.Series(dtype=float)
            )

        def instrument(name: str, symbol: str) -> pd.Series:
            definition = features.get_definition(name)
            inst = instruments.get_by_symbol(symbol)
            if definition is None or inst is None:
                return pd.Series(dtype=float)
            return features.get_instrument_series(definition.id, inst.id)

        bull = market("regime_bull")
        vix = market("vix_pctile_252d")
        rates = market("dgs10_chg_63d")
        inflation = market("cpi_yoy_accel")
        breadth = market("sector_breadth_ma50")
        tech = instrument("rel_ret_spy_63d", "XLK")
        since = {s: instrument("days_since_earnings", s) for s in SYMBOLS}

    def last(series: pd.Series, day: date):
        subset = series.loc[: pd.Timestamp(day)].dropna()
        return float(subset.iloc[-1]) if len(subset) else None

    rows = []
    for symbol, symbol_dates in per_symbol_dates.items():
        for day in symbol_dates:
            value = last(since.get(symbol, pd.Series(dtype=float)), day)
            rows.append(
                {
                    "symbol": symbol,
                    "as_of": day,
                    "trend": {1.0: "bull", 0.0: "bear"}.get(last(bull, day)),
                    "volatility": (
                        "high"
                        if (last(vix, day) or 0) >= 0.8
                        else "low" if (last(vix, day) or 1) <= 0.2 else "mid"
                    ),
                    "rates": (
                        "rising"
                        if (last(rates, day) or 0) > 0.25
                        else "falling" if (last(rates, day) or 0) < -0.25 else "stable"
                    ),
                    "inflation": (
                        "accelerating" if (last(inflation, day) or 0) > 0 else "decelerating"
                    ),
                    "breadth": (
                        "strong"
                        if (last(breadth, day) or 0) >= 0.7
                        else "weak" if (last(breadth, day) or 1) <= 0.3 else "mixed"
                    ),
                    "technology": ("leading" if (last(tech, day) or 0) > 0 else "lagging"),
                    "earnings_window": (
                        "post" if value is not None and value <= 10.0 else "outside"
                    ),
                }
            )
    return pd.DataFrame(rows)


def _system_metrics(frame: pd.DataFrame, systems, horizons=HORIZON_ORDER) -> pd.DataFrame:
    rows = []
    for system in systems:
        subset = frame[frame["system"] == system]
        for horizon in horizons:
            h_all = subset[subset["horizon"] == horizon]
            h_cohort = vm.cohort(subset, horizon)
            for sample, data in (("all", h_all), ("cohort", h_cohort)):
                stats = vm.accuracy_and_brier(data)
                rows.append({"system": system, "horizon": horizon, "sample": sample, **stats})
    return pd.DataFrame(rows)


def _decide(holdout: pd.DataFrame, turnover_delta: float | None, weight_stable: bool) -> dict:
    """The pre-declared promotion criteria, evaluated on the holdout."""
    criteria: dict[str, bool | None] = {}
    combined = holdout[(holdout["system"] == "combined") & (holdout["sample"] == "cohort")]
    baseline = holdout[(holdout["system"] == "baseline") & (holdout["sample"] == "cohort")]
    merged = combined.merge(baseline, on="horizon", suffixes=("_c", "_b"))
    merged = merged[merged["n_c"] >= 10]
    if merged.empty:
        return {"decision": "CONTINUE IN SHADOW MODE", "criteria": {"holdout_sample": False}}
    criteria["improves_brier"] = bool((merged["brier_c"] < merged["brier_b"]).mean() > 0.5)
    criteria["improves_accuracy"] = bool(
        (merged["direction_accuracy_c"] >= merged["direction_accuracy_b"] - 0.005).mean() > 0.5
    )
    criteria["improves_ranking"] = bool(
        (merged["rank_correlation_c"] > merged["rank_correlation_b"]).mean() > 0.5
    )
    criteria["turnover_acceptable"] = (
        None if turnover_delta is None else bool(turnover_delta <= 3.0)
    )
    criteria["weights_stable"] = weight_stable
    passed = sum(1 for v in criteria.values() if v)
    failed_hard = criteria["improves_brier"] is False and criteria["improves_accuracy"] is False
    if not weight_stable:
        decision = "REVISE AND RETEST"
    elif failed_hard:
        decision = "CONTINUE IN SHADOW MODE"
    elif passed >= 4:
        decision = "PROMOTE TO OFFICIAL SCORE"
    else:
        decision = "CONTINUE IN SHADOW MODE"
    return {"decision": decision, "criteria": criteria}


def _leakage_report() -> dict | None:
    """Aggregate the per-date observability diagnostics (present only in
    hardened runs; original contaminated artifacts have none)."""
    import json as json_lib

    rows = []
    for path in sorted(ARTIFACTS.glob("predictions_*.jsonl")):
        for line in path.read_text().splitlines():
            record = json_lib.loads(line)
            if record.get("leakage_diagnostics"):
                rows.append(record)
    if not rows:
        return None
    by_horizon: dict[str, dict[str, int]] = {}
    violations = 0
    for record in rows:
        violations += record.get("violations", 0)
        for horizon, detail in record.get("horizons", {}).items():
            bucket = by_horizon.setdefault(
                horizon, {"used": 0, "observable": 0, "embargoed": 0, "unavailable": 0}
            )
            for key in bucket:
                bucket[key] += detail.get(key, 0)
    for bucket in by_horizon.values():
        total = bucket["used"] + bucket["embargoed"] + bucket["unavailable"]
        bucket["embargoed_pct"] = round(bucket["embargoed"] / total, 4) if total else 0.0
    return {
        "checked_dates": len(rows),
        "violations_total": violations,
        "by_horizon": by_horizon,
    }


def main() -> None:
    factory = open_session_factory()
    predictions = _load_all_predictions()
    if predictions.empty:
        sys.exit("no captured predictions found — run walkforward first")

    systems = build_systems(predictions)
    systems.to_csv(ARTIFACTS / "systems.csv", index=False)

    per_symbol_dates = {
        s: sorted(predictions[predictions["symbol"] == s]["as_of"].unique()) for s in SYMBOLS
    }
    outcomes = realized_outcomes(factory, list(SYMBOLS), per_symbol_dates)
    outcomes.to_csv(ARTIFACTS / "outcomes.csv", index=False)

    frame = vm.prepare(systems, outcomes)
    frame.to_csv(ARTIFACTS / "merged.csv", index=False)
    calibration = frame[frame["as_of"] < HOLDOUT_START]
    holdout = frame[frame["as_of"] >= HOLDOUT_START]

    artifacts: dict[str, object] = {}

    # 5. aggregate metrics, both periods, all-dates + non-overlapping cohorts
    rho_systems = sorted({s for s in frame["system"].unique() if s.startswith("rho_")})
    for name, period in (("calibration", calibration), ("holdout", holdout)):
        table = _system_metrics(period, list(CORE_SYSTEMS) + rho_systems)
        table.to_csv(ARTIFACTS / f"metrics_{name}.csv", index=False)
        artifacts[f"metrics_{name}"] = table.to_dict("records")

    # deciles + calibration bins + band outcomes (holdout, combined vs baseline)
    for system in CORE_SYSTEMS:
        subset = holdout[holdout["system"] == system]
        vm.decile_table(subset).to_csv(ARTIFACTS / f"deciles_holdout_{system}.csv", index=False)
        vm.calibration_bins(subset).to_csv(
            ARTIFACTS / f"calibration_bins_holdout_{system}.csv", index=False
        )
        vm.trim_band_outcomes(subset).to_csv(ARTIFACTS / f"bands_holdout_{system}.csv", index=False)

    # 4/11. block bootstrap on cohort series (combined - baseline)
    bootstrap = {}
    for horizon in HORIZON_ORDER:
        combined_cohort = vm.cohort(holdout[holdout["system"] == "combined"], horizon)
        baseline_cohort = vm.cohort(holdout[holdout["system"] == "baseline"], horizon)
        bootstrap[horizon] = {
            "hit": vm.block_bootstrap_delta(combined_cohort, baseline_cohort, "hit"),
            "excess": vm.block_bootstrap_delta(combined_cohort, baseline_cohort, "realized_excess"),
        }
    artifacts["bootstrap_holdout"] = bootstrap

    # 6. trim usefulness extras
    artifacts["false_missed"] = {
        s: vm.false_missed_trim(holdout[holdout["system"] == s]) for s in CORE_SYSTEMS
    }
    artifacts["confidence_split"] = {
        s: vm.confidence_split(holdout[holdout["system"] == s]) for s in CORE_SYSTEMS
    }

    # 7. per-holding
    per_holding = []
    for symbol in SYMBOLS:
        for system in ("baseline", "combined"):
            subset = holdout[(holdout["symbol"] == symbol) & (holdout["system"] == system)]
            stats = vm.accuracy_and_brier(subset[subset["horizon"] == "1m"])
            per_holding.append({"symbol": symbol, "system": system, "horizon": "1m", **stats})
    per_holding_frame = pd.DataFrame(per_holding)
    per_holding_frame.to_csv(ARTIFACTS / "per_holding_holdout_1m.csv", index=False)
    artifacts["per_holding"] = per_holding

    # 8. regimes (full-sample deltas; small cells reported as-is)
    labels = _regime_labels(factory, [], per_symbol_dates)
    labelled = frame.merge(labels, on=["symbol", "as_of"], how="left")
    regime_rows = []
    for dimension in (
        "trend",
        "volatility",
        "rates",
        "inflation",
        "breadth",
        "technology",
        "earnings_window",
    ):
        for value, group in labelled.groupby(dimension):
            for system in ("baseline", "combined"):
                stats = vm.accuracy_and_brier(
                    group[(group["system"] == system) & (group["horizon"] == "1m")]
                )
                regime_rows.append(
                    {"dimension": dimension, "regime": value, "system": system, **stats}
                )
    pd.DataFrame(regime_rows).to_csv(ARTIFACTS / "regimes_1m.csv", index=False)
    artifacts["regimes"] = regime_rows

    # 9/15. turnover per system + rho turnover
    turnover = {
        s: vm.turnover(frame[frame["system"] == s]) for s in list(CORE_SYSTEMS) + rho_systems
    }
    artifacts["turnover"] = turnover

    # 10/12/13/14. variant grid (analogue-only under each config), calibration period
    variants = _load_variants()
    variant_rows = []
    weight_accuracy = {}
    if not variants.empty:
        variant_systems = []
        for name, group in variants.groupby("variant"):
            renamed = group.copy()
            renamed["model"] = "historical_analogues"
            built = build_systems(renamed, rho_grid=())
            only = built[built["system"] == "analogue_only"].copy()
            only["system"] = f"variant_{name}"
            variant_systems.append(only)
        variant_frame = vm.prepare(pd.concat(variant_systems, ignore_index=True), outcomes)
        variant_calibration = variant_frame[variant_frame["as_of"] < HOLDOUT_START]
        for system in sorted(variant_frame["system"].unique()):
            subset = variant_calibration[variant_calibration["system"] == system]
            stats = vm.accuracy_and_brier(subset[subset["horizon"] == "1m"])
            variant_rows.append({"variant": system.replace("variant_", ""), **stats})
            weight_accuracy[system] = stats.get("direction_accuracy")
        pd.DataFrame(variant_rows).to_csv(ARTIFACTS / "variants_calibration_1m.csv", index=False)
    artifacts["variants"] = variant_rows
    weight_names = (
        "variant_full",
        "variant_equal_weights",
        "variant_company_heavy",
        "variant_market_heavy",
        "variant_catalyst_light",
    )
    weight_values = [v for k, v in weight_accuracy.items() if k in weight_names and v is not None]
    weight_stable = (
        (max(weight_values) - min(weight_values) <= 0.08) if len(weight_values) >= 3 else True
    )
    artifacts["weight_stability"] = {"values": weight_accuracy, "stable": weight_stable}

    # 11. analogue quality vs accuracy
    quality_rows = predictions[
        (predictions["model"] == "historical_analogues") & predictions["quality"].notna()
    ]
    quality_analysis = {}
    if not quality_rows.empty:
        quality = pd.json_normalize(quality_rows["quality"])
        quality["symbol"] = quality_rows["symbol"].to_numpy()
        quality["as_of"] = quality_rows["as_of"].to_numpy()
        quality["horizon"] = quality_rows["horizon"].to_numpy()
        merged_quality = frame[frame["system"] == "analogue_only"].merge(
            quality, on=["symbol", "as_of", "horizon"], how="inner"
        )
        scored = merged_quality[merged_quality["hit"].notna()]
        if len(scored) >= 50:
            median_similarity = scored["mean_similarity"].median()
            quality_analysis = {
                "n": int(len(scored)),
                "high_similarity_accuracy": float(
                    scored[scored["mean_similarity"] >= median_similarity]["hit"]
                    .astype(float)
                    .mean()
                ),
                "low_similarity_accuracy": float(
                    scored[scored["mean_similarity"] < median_similarity]["hit"]
                    .astype(float)
                    .mean()
                ),
                "median_mean_similarity": float(median_similarity),
                "mean_year_concentration": float(scored["year_concentration"].mean()),
            }
    artifacts["analogue_quality"] = quality_analysis

    # 14. simple momentum baseline: sign of trailing 63d return
    with session_scope(factory) as session:
        features = FeatureRepository(session)
        instruments = InstrumentRepository(session)
        definition = features.get_definition("ret_63d")
        naive_rows = []
        for symbol in SYMBOLS:
            inst = instruments.get_by_symbol(symbol)
            series = features.get_instrument_series(definition.id, inst.id)
            for day in per_symbol_dates.get(symbol, []):
                subset = series.loc[: pd.Timestamp(day)].dropna()
                if len(subset):
                    naive_rows.append(
                        {"symbol": symbol, "as_of": day, "naive_up": float(subset.iloc[-1]) > 0}
                    )
    naive = pd.DataFrame(naive_rows)
    analogue_holdout = holdout[holdout["system"] == "analogue_only"].merge(
        naive, on=["symbol", "as_of"], how="left"
    )
    scored = analogue_holdout[
        analogue_holdout["realized_excess"].notna() & analogue_holdout["naive_up"].notna()
    ]
    artifacts["simple_baselines_holdout"] = {
        "naive_momentum_accuracy": (
            float((scored["naive_up"] == (scored["realized_excess"] > 0)).mean())
            if len(scored)
            else None
        ),
        "analogue_only_accuracy": (
            float(scored["hit"].astype(float).mean()) if len(scored) else None
        ),
        "unconditional_brier_reference": (
            float((((scored["realized_excess"] > 0).astype(float) - 0.5) ** 2).mean())
            if len(scored)
            else None
        ),
        "note": "regime-conditional baseline == the seven-model Baseline system; "
        "company-only and market+company appear in the variant table",
    }

    # decision
    holdout_table = pd.DataFrame(artifacts["metrics_holdout"])
    turnover_delta = None
    if turnover.get("combined", {}).get("n") and turnover.get("baseline", {}).get("n"):
        turnover_delta = (
            turnover["combined"]["mean_abs_change"] - turnover["baseline"]["mean_abs_change"]
        )
    artifacts["decision"] = _decide(holdout_table, turnover_delta, weight_stable)

    leakage = _leakage_report()
    if leakage is not None:
        artifacts["leakage"] = leakage
        (ARTIFACTS / "leakage_report.json").write_text(json.dumps(leakage, indent=2))
        assert leakage["violations_total"] == 0, "leakage diagnostics reported violations"

    (ARTIFACTS / "analysis.json").write_text(json.dumps(artifacts, indent=2, default=str))
    print(json.dumps(artifacts["decision"], indent=2))
    print(f"artifacts written to {ARTIFACTS}/")


if __name__ == "__main__":
    main()
