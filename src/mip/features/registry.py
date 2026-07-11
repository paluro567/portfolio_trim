"""The feature registry: the single list of live calculators.

Adding a feature = write a FeatureCalculator + add ONE line here.
topological_order() resolves depends_on chains and fails loudly on
unknown dependencies or cycles."""

from graphlib import CycleError, TopologicalSorter

from mip.core.exceptions import ConfigurationError
from mip.features.base import FeatureCalculator
from mip.features.earnings import (
    DaysSinceEarnings,
    DaysUntilEarnings,
    EarningsRecency,
    EpsSurprise,
)
from mip.features.fundamental import (
    EpsGrowthYoY,
    FundamentalField,
    PriceToSales,
    RevenueGrowthYoY,
)
from mip.features.macro import (
    CurveSlope,
    MacroChange,
    MacroLevel,
    MacroPercentile,
    YoYChange,
)
from mip.features.price import (
    ATRPercent,
    Distance52Week,
    LogReturn1d,
    MASpread,
    PriceToMA,
    RollingReturn,
    Volatility,
)
from mip.features.regime import RegimeBull, RegimeHighVol, RegimeRates
from mip.features.relative import RelativeReturn, RelativeReturnAccel


def build_registry() -> list[FeatureCalculator]:
    return [
        # -- price -----------------------------------------------------
        RollingReturn(1),
        RollingReturn(5),
        RollingReturn(21),
        RollingReturn(63),
        RollingReturn(126),
        RollingReturn(252),
        LogReturn1d(),
        PriceToMA(50),
        PriceToMA(200),
        MASpread(50, 200),
        Volatility(21),
        Volatility(63),
        ATRPercent(14),
        Distance52Week("high"),
        Distance52Week("low"),
        # -- relative performance ---------------------------------------
        RelativeReturn("SPY", 5),
        RelativeReturn("SPY", 21),
        RelativeReturn("SPY", 63),
        RelativeReturn("SPY", 126),
        RelativeReturn("sector", 5),
        RelativeReturn("sector", 21),
        RelativeReturn("sector", 63),
        RelativeReturn("sector", 126),
        RelativeReturnAccel(21),
        # -- macro (market scope) ----------------------------------------
        MacroChange(
            "dgs10_chg_5d", "DGS10", 5, "10y Treasury yield change over 5 observations (pp)"
        ),
        MacroChange(
            "dgs10_chg_21d", "DGS10", 21, "10y Treasury yield change over 21 observations (pp)"
        ),
        MacroChange(
            "dgs10_chg_63d", "DGS10", 63, "10y Treasury yield change over 63 observations (pp)"
        ),
        MacroChange(
            "dgs10_chg_126d", "DGS10", 126, "10y Treasury yield change over 126 observations (pp)"
        ),
        MacroChange("dgs2_chg_5d", "DGS2", 5, "2y Treasury yield change over 5 observations (pp)"),
        MacroChange(
            "dgs2_chg_21d", "DGS2", 21, "2y Treasury yield change over 21 observations (pp)"
        ),
        MacroChange(
            "dgs2_chg_63d", "DGS2", 63, "2y Treasury yield change over 63 observations (pp)"
        ),
        MacroChange(
            "dgs2_chg_126d", "DGS2", 126, "2y Treasury yield change over 126 observations (pp)"
        ),
        CurveSlope("curve_slope_10y2y", "DGS10", "DGS2", "10y minus 2y Treasury yield (pp)"),
        MacroLevel("fedfunds_level", "FEDFUNDS", "Effective Fed Funds rate (%, monthly)"),
        YoYChange("cpi_yoy", "CPIAUCSL", "CPI year-over-year change (inflation trend)"),
        YoYChange(
            "cpi_yoy_accel",
            "CPIAUCSL",
            "Change in CPI YoY vs 3 months earlier (inflation acceleration)",
            accel_months=3,
        ),
        MacroLevel("vix_level", "VIXCLS", "CBOE VIX close"),
        MacroPercentile(
            "vix_pctile_252d",
            "VIXCLS",
            252,
            "VIX close percentile within its trailing 252 observations",
        ),
        # -- fundamentals --------------------------------------------------
        FundamentalField("pe_trailing", "trailing_pe", "Trailing price/earnings (latest snapshot)"),
        FundamentalField("pe_forward", "forward_pe", "Forward price/earnings (latest snapshot)"),
        PriceToSales(),
        FundamentalField(
            "log_market_cap", "market_cap", "log10 of market capitalization", log10=True
        ),
        RevenueGrowthYoY(),
        EpsGrowthYoY(),
        # -- earnings proximity ----------------------------------------------
        DaysSinceEarnings(),
        DaysUntilEarnings(),
        EarningsRecency(),
        EpsSurprise(),
        # -- market regimes ----------------------------------------------------
        RegimeBull(),
        RegimeHighVol(),
        RegimeRates("rising"),
        RegimeRates("falling"),
    ]


def topological_order(calculators: list[FeatureCalculator]) -> list[FeatureCalculator]:
    """Dependency-respecting order; loud failure on unknown deps/cycles."""
    by_name = {c.spec.name: c for c in calculators}
    duplicated = len(by_name) != len(calculators)
    if duplicated:
        names = [c.spec.name for c in calculators]
        raise ConfigurationError(
            f"duplicate feature names in registry: "
            f"{sorted({n for n in names if names.count(n) > 1})}"
        )

    sorter: TopologicalSorter[str] = TopologicalSorter()
    for calc in calculators:
        for dep in calc.spec.depends_on:
            if dep not in by_name:
                raise ConfigurationError(
                    f"feature {calc.spec.name!r} depends on unknown feature {dep!r}"
                )
        sorter.add(calc.spec.name, *calc.spec.depends_on)
    try:
        ordered_names = list(sorter.static_order())
    except CycleError as exc:
        raise ConfigurationError(f"feature dependency cycle: {exc.args[1]}") from exc
    return [by_name[name] for name in ordered_names]
