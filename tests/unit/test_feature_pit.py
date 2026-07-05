"""Point-in-time tests: publication lag enforcement in the macro path.
These are THE look-ahead regression tests (§6.1)."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from mip.features.base import FeatureContext, align_availability
from mip.features.macro import CurveSlope, MacroChange, MacroLevel, MacroPercentile, YoYChange


def macro_frame(rows: list[tuple[date, float, date]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=["obs_date", "value", "available_from"])
    frame["obs_date"] = pd.to_datetime(frame["obs_date"])
    return frame.set_index("obs_date")


def dates(*days: date) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(list(days)))


def test_align_availability_respects_lag() -> None:
    frame = macro_frame(
        [
            (date(2026, 6, 1), 4.00, date(2026, 6, 2)),
            (date(2026, 6, 2), 4.10, date(2026, 6, 3)),
        ]
    )
    aligned = align_availability(frame, dates(date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)))

    assert np.isnan(aligned.iloc[0])  # June 1: nothing published yet
    assert aligned.iloc[1] == 4.00  # June 2: only the June 1 obs is public
    assert aligned.iloc[2] == 4.10  # June 3: June 2 obs published


def test_macro_level_never_sees_unpublished_value() -> None:
    calc = MacroLevel("vix_level", "VIXCLS", "test")
    ctx = FeatureContext(
        dates=dates(date(2026, 6, 2)),
        macro={
            "VIXCLS": macro_frame(
                [
                    (date(2026, 6, 1), 18.0, date(2026, 6, 2)),
                    (date(2026, 6, 2), 99.0, date(2026, 6, 3)),  # not yet public
                ]
            )
        },
    )
    series = calc.compute(ctx)
    assert series.iloc[0] == 18.0  # the 99 spike is tomorrow's knowledge


def test_yoy_available_only_when_newer_obs_published() -> None:
    # CPI monthly, lag 45 days: May obs public ~Jun 15, June obs ~Jul 16
    rows = []
    for month in range(1, 13):  # 2025: base year, all long public
        rows.append((date(2025, month, 1), 300.0 + month, date(2025, month, 15)))
    rows.append((date(2026, 5, 1), 330.0, date(2026, 6, 15)))  # yoy vs 305 -> 8.2%
    rows.append((date(2026, 6, 1), 340.0, date(2026, 7, 16)))  # yoy vs 306 -> 11.1%
    frame = macro_frame(rows)

    calc = YoYChange("cpi_yoy", "CPIAUCSL", "test")
    series = calc.compute(
        FeatureContext(dates=dates(date(2026, 7, 10), date(2026, 7, 20)), macro={"CPIAUCSL": frame})
    )
    assert series.iloc[0] == pytest.approx(330.0 / 305.0 - 1)  # June CPI not out yet
    assert series.iloc[1] == pytest.approx(340.0 / 306.0 - 1)  # published Jul 16


def test_curve_slope_waits_for_both_legs() -> None:
    long_leg = macro_frame([(date(2026, 6, 1), 4.5, date(2026, 6, 2))])
    short_leg = macro_frame([(date(2026, 6, 1), 3.5, date(2026, 6, 4))])  # slower leg

    calc = CurveSlope("curve_slope_10y2y", "DGS10", "DGS2", "test")
    series = calc.compute(
        FeatureContext(
            dates=dates(date(2026, 6, 2), date(2026, 6, 4)),
            macro={"DGS10": long_leg, "DGS2": short_leg},
        )
    )
    assert np.isnan(series.iloc[0])  # only one leg public
    assert series.iloc[1] == pytest.approx(1.0)


def test_macro_change_availability_is_newer_obs() -> None:
    frame = macro_frame(
        [
            (date(2026, 6, 1), 4.00, date(2026, 6, 2)),
            (date(2026, 6, 2), 4.05, date(2026, 6, 3)),
            (date(2026, 6, 3), 4.20, date(2026, 6, 4)),
        ]
    )
    calc = MacroChange("dgs10_chg_1d", "DGS10", 1, "test")
    series = calc.compute(
        FeatureContext(dates=dates(date(2026, 6, 3), date(2026, 6, 4)), macro={"DGS10": frame})
    )
    assert series.iloc[0] == pytest.approx(0.05)  # knows up to Jun 2 obs
    assert series.iloc[1] == pytest.approx(0.15)


def test_percentile_ignores_missing_value_markers() -> None:
    # FRED daily series carry '.' -> NULL on holidays; a NaN inside the
    # window must not poison the percentile (regression: vix_pctile_252d
    # produced zero rows over 16 years of VIX history)
    rows = [
        (date(2026, 6, 1), 10.0, date(2026, 6, 2)),
        (date(2026, 6, 2), float("nan"), date(2026, 6, 3)),  # holiday marker
        (date(2026, 6, 3), 20.0, date(2026, 6, 4)),
        (date(2026, 6, 4), 30.0, date(2026, 6, 5)),
    ]
    calc = MacroPercentile("vix_pctile_3d", "VIXCLS", 3, "test")
    series = calc.compute(
        FeatureContext(dates=dates(date(2026, 6, 5)), macro={"VIXCLS": macro_frame(rows)})
    )
    # window = the three real observations [10, 20, 30]; 30 is the max
    assert series.iloc[0] == pytest.approx(1.0)


def test_missing_macro_code_yields_absent_not_error() -> None:
    calc = MacroLevel("vix_level", "VIXCLS", "test")
    series = calc.compute(FeatureContext(dates=dates(date(2026, 6, 2)), macro={}))
    assert series.isna().all()
