"""Analogue validation harness: metric arithmetic, cohorting, bootstrap
determinism, and system reconstruction — hand-verified, no database."""

import math
from datetime import date, timedelta

import pandas as pd
import pytest

from mip.validation import metrics as vm
from mip.validation.systems import RHO_GRID, build_systems

AS_OF = date(2023, 6, 1)


def prediction_row(
    model: str,
    *,
    symbol: str = "AAA",
    as_of: date = AS_OF,
    horizon: str = "1m",
    score: float = 70.0,
    excess: float = 0.02,
    z_raw: float = 2.0,
    neutral: bool = False,
) -> dict:
    return {
        "symbol": symbol,
        "as_of": as_of,
        "horizon": horizon,
        "model": model,
        "score": score,
        "confidence": 0.5,
        "neutral": neutral,
        "excess": None if neutral else excess,
        "expected": None if neutral else 0.01 + excess,
        "z_raw": None if neutral else z_raw,
        "n_eff": 40.0,
    }


def outcome_row(
    *,
    symbol: str = "AAA",
    as_of: date = AS_OF,
    horizon: str = "1m",
    actual: float = 0.05,
    spy_rel: float = 0.01,
    adverse: float = -0.03,
) -> dict:
    return {
        "symbol": symbol,
        "as_of": as_of,
        "horizon": horizon,
        "complete": True,
        "actual": actual,
        "spy_rel": spy_rel,
        "adverse": adverse,
        "drawdown": adverse,
        "fwd_vol": 0.3,
    }


def system_row(
    *,
    symbol: str = "AAA",
    as_of: date = AS_OF,
    horizon: str = "1m",
    system: str = "combined",
    score: float = 70.0,
    excess: float = 0.02,
    trim: float = 35.0,
    band: str = "Hold / Monitor",
    confidence: float = 0.5,
) -> dict:
    return {
        "symbol": symbol,
        "as_of": as_of,
        "horizon": horizon,
        "system": system,
        "evidence_score": score,
        "confidence": confidence,
        "expected_excess": excess,
        "expected_return": 0.01 + excess,
        "contradiction": 0.1,
        "n_eff": 40.0,
        "participating": 5,
        "trim_score": trim,
        "band": band,
    }


# -- prepare & core metrics --------------------------------------------------------


def test_prepare_uses_the_prediction_own_baseline() -> None:
    systems = pd.DataFrame([system_row(score=70.0, excess=0.02)])
    outcomes = pd.DataFrame([outcome_row(actual=0.05)])
    frame = vm.prepare(systems, outcomes)
    # baseline = expected - excess = 0.01; realized excess = 0.05 - 0.01
    assert frame.iloc[0]["realized_excess"] == pytest.approx(0.04)
    assert bool(frame.iloc[0]["hit"]) is True  # score>50 and excess>0


def test_accuracy_and_brier_by_hand() -> None:
    rows = [
        system_row(as_of=AS_OF, score=80.0, excess=0.02),
        system_row(as_of=AS_OF + timedelta(days=14), score=60.0, excess=0.01),
        system_row(as_of=AS_OF + timedelta(days=28), score=30.0, excess=-0.02),
    ]
    outs = [
        outcome_row(as_of=AS_OF, actual=0.05),  # excess +0.04 -> hit
        outcome_row(as_of=AS_OF + timedelta(days=14), actual=-0.02),  # excess -0.03 -> miss
        outcome_row(as_of=AS_OF + timedelta(days=28), actual=-0.05),  # excess -0.08 -> hit
    ]
    stats = vm.accuracy_and_brier(vm.prepare(pd.DataFrame(rows), pd.DataFrame(outs)))
    assert stats["n"] == 3
    assert stats["direction_accuracy"] == pytest.approx(2 / 3)
    brier = ((0.8 - 1) ** 2 + (0.6 - 0) ** 2 + (0.3 - 0) ** 2) / 3
    assert stats["brier"] == pytest.approx(brier)
    assert stats["brier_reference"] == pytest.approx(0.25)


def test_cohort_stride_removes_overlap() -> None:
    rows, outs = [], []
    for i in range(12):
        day = AS_OF + timedelta(days=14 * i)  # every 10 sessions on the grid
        rows.append(system_row(as_of=day, horizon="3m"))
        outs.append(outcome_row(as_of=day, horizon="3m"))
    frame = vm.prepare(pd.DataFrame(rows), pd.DataFrame(outs))
    cohort = vm.cohort(frame, "3m")  # stride = ceil(63/10) = 7
    assert len(cohort) == 2  # rows 0 and 7
    short = frame.assign(horizon="1w")
    assert len(vm.cohort(short, "1w")) == 12  # 5 sessions <= grid spacing: all kept


def test_block_bootstrap_is_deterministic_and_detects_improvement() -> None:
    rows, outs = [], []
    for i in range(40):
        day = AS_OF + timedelta(days=14 * i)
        up = i % 2 == 0
        outs.append(outcome_row(as_of=day, actual=0.06 if up else -0.06))
        for system, accurate in (("combined", True), ("baseline", False)):
            score = 80.0 if (up if accurate else not up) else 20.0
            rows.append(
                system_row(
                    system=system,
                    as_of=day,
                    score=score,
                    excess=0.02 if score > 50 else -0.02,
                )
            )
    frame = vm.prepare(pd.DataFrame(rows), pd.DataFrame(outs))
    combined = frame[frame["system"] == "combined"]
    baseline = frame[frame["system"] == "baseline"]
    first = vm.block_bootstrap_delta(combined, baseline, "hit")
    second = vm.block_bootstrap_delta(combined, baseline, "hit")
    assert first == second  # seeded
    assert first["delta"] == pytest.approx(1.0)  # 100% vs 0%
    assert first["ci_low"] > 0.9 and first["positive_share"] == 1.0


def test_turnover_by_hand() -> None:
    rows = []
    trims = [30.0, 45.0, 30.0, 30.0]  # +15 then -15 -> one reversal
    bands = ["Hold / Monitor", "Mixed Evidence", "Hold / Monitor", "Hold / Monitor"]
    for i, (t, b) in enumerate(zip(trims, bands, strict=True)):
        rows.append(
            {**system_row(as_of=AS_OF + timedelta(days=14 * i), trim=t, band=b), "hit": None}
        )
    stats = vm.turnover(pd.DataFrame(rows))
    assert stats["n"] == 3
    assert stats["mean_abs_change"] == pytest.approx((15 + 15 + 0) / 3)
    assert stats["band_turnover"] == pytest.approx(2 / 3)
    assert stats["reversal_rate"] == pytest.approx(1 / 2)


def test_false_and_missed_trim() -> None:
    rows = [
        system_row(as_of=AS_OF, trim=80.0, score=20.0, excess=-0.02),
        system_row(as_of=AS_OF + timedelta(days=14), trim=80.0, score=20.0, excess=-0.02),
        system_row(as_of=AS_OF + timedelta(days=28), trim=20.0, score=80.0, excess=0.02),
        system_row(as_of=AS_OF + timedelta(days=42), trim=20.0, score=80.0, excess=0.02),
    ]
    outs = [
        outcome_row(as_of=AS_OF, actual=-0.06),  # true trim
        outcome_row(as_of=AS_OF + timedelta(days=14), actual=0.08),  # false trim
        outcome_row(as_of=AS_OF + timedelta(days=28), actual=0.08),  # good keep
        outcome_row(as_of=AS_OF + timedelta(days=42), actual=-0.09),  # missed trim
    ]
    stats = vm.false_missed_trim(vm.prepare(pd.DataFrame(rows), pd.DataFrame(outs)))
    assert stats["n_trim_signals"] == 2
    assert stats["false_trim_rate"] == pytest.approx(0.5)
    assert stats["missed_trim_rate"] == pytest.approx(1.0)


def test_decile_table_orders_outcomes() -> None:
    rows, outs = [], []
    for i in range(40):
        day = AS_OF + timedelta(days=14 * i)
        score = float(i * 2 + 10)
        rows.append(system_row(as_of=day, score=score, excess=(score - 50) / 1000))
        outs.append(outcome_row(as_of=day, actual=(score - 50) / 500 + 0.01))
    table = vm.decile_table(vm.prepare(pd.DataFrame(rows), pd.DataFrame(outs)))
    assert len(table) == 10
    assert table.iloc[-1]["mean_excess"] > table.iloc[0]["mean_excess"]
    assert table.iloc[-1]["mean_score"] > table.iloc[0]["mean_score"]


# -- system reconstruction ---------------------------------------------------------


def eight_model_frame() -> pd.DataFrame:
    rows = []
    models = [
        "interest_rate_sensitivity",
        "sector_rotation",
        "momentum_exhaustion",
        "valuation",
        "earnings_behavior",
        "macro_regime",
        "relative_strength",
    ]
    for m in models[:3]:
        rows.append(prediction_row(m, score=70.0, excess=0.02, z_raw=2.0))
    for m in models[3:]:
        rows.append(prediction_row(m, neutral=True, score=50.0))
    rows.append(prediction_row("historical_analogues", score=30.0, excess=-0.03, z_raw=-2.5))
    return pd.DataFrame(rows)


def test_build_systems_partitions_models_correctly() -> None:
    systems = build_systems(eight_model_frame())
    by = {r["system"]: r for _, r in systems.iterrows()}
    assert by["baseline"]["participating"] == 3  # analogue and neutrals excluded
    assert by["combined"]["participating"] == 4
    assert by["analogue_only"]["participating"] == 1
    # shadow is numerically the baseline
    assert by["shadow"]["evidence_score"] == pytest.approx(by["baseline"]["evidence_score"])
    assert by["shadow"]["trim_score"] == pytest.approx(by["baseline"]["trim_score"])
    # the opposing analogue pulls the combined score below the baseline
    assert by["combined"]["evidence_score"] < by["baseline"]["evidence_score"]
    expected_trim = 50.0 + by["combined"]["confidence"] * (50.0 - by["combined"]["evidence_score"])
    assert by["combined"]["trim_score"] == pytest.approx(expected_trim)


def test_rho_variants_only_touch_analogue_pairs() -> None:
    systems = build_systems(eight_model_frame(), rho_grid=RHO_GRID)
    by = {r["system"]: r for _, r in systems.iterrows()}
    # the prior only inflates uncertainty: the combined POINT estimate is
    # identical at every rho ...
    for name in ("rho_25", "rho_75", "rho_90"):
        assert by[name]["expected_excess"] == pytest.approx(by["combined"]["expected_excess"])
    # ... while higher rho discounts the shared information harder, so the
    # combined score loses conviction monotonically (moves toward 50,
    # i.e. AWAY from the strongly positive baseline here)
    gap = {
        name: abs(by[name]["evidence_score"] - by["baseline"]["evidence_score"])
        for name in ("rho_25", "combined", "rho_75", "rho_90")
    }
    assert gap["rho_25"] <= gap["combined"] <= gap["rho_75"] <= gap["rho_90"]
    assert math.isfinite(by["rho_90"]["evidence_score"])


def test_incomplete_outcomes_are_excluded() -> None:
    systems = pd.DataFrame([system_row()])
    outcomes = pd.DataFrame([{**outcome_row(), "complete": False, "actual": None}])
    assert vm.prepare(systems, outcomes).empty
