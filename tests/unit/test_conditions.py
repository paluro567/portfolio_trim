"""Unit tests for the condition registry resolution (pure, fake context)."""

from datetime import date

from mip.research.conditions import (
    FALLBACK_LADDER,
    TEMPLATE_SET_VERSION,
    ConditionTemplate,
    EvaluateOn,
    Mode,
    ResolutionContext,
    build_condition_templates,
    resolve_active,
)


def make_ctx(values: dict, quantiles: dict | None = None, sector_etf: str | None = "XLK"):
    """values: {(feature, evaluate_on_value): number}; quantiles:
    {(feature, evaluate_on_value, p): number}."""
    quantiles = quantiles or {}

    def value(feature: str, on: EvaluateOn):
        return values.get((feature, on.value))

    def quantile(feature: str, on: EvaluateOn, p: float):
        return quantiles.get((feature, on.value, p))

    return ResolutionContext(
        target="AMD", as_of=date(2026, 7, 22), sector_etf=sector_etf, value=value, quantile=quantile
    )


def template(**kw) -> ConditionTemplate:
    base = dict(
        name="t",
        version=1,
        family="company",
        mode=Mode.SELF_BUCKET,
        feature="ret_63d",
        economic_rationale="r",
    )
    base.update(kw)
    return ConditionTemplate(**base)


class TestMarketModes:
    def test_flag_matches_current_side(self) -> None:
        t = template(mode=Mode.MARKET_FLAG, feature="regime_bull", evaluate_on=EvaluateOn.MARKET)
        bull = t.resolve(make_ctx({("regime_bull", "market"): 1.0}))
        assert bull is not None and bull.op == "==" and bull.value == 1.0
        bear = t.resolve(make_ctx({("regime_bull", "market"): 0.0}))
        assert bear is not None and bear.value == 0.0
        assert t.resolve(make_ctx({})) is None  # unavailable

    def test_bucket_only_at_extremes(self) -> None:
        t = template(
            mode=Mode.MARKET_BUCKET, feature="vix_pctile_252d", evaluate_on=EvaluateOn.MARKET
        )
        hi = t.resolve(make_ctx({("vix_pctile_252d", "market"): 0.9}))
        assert hi is not None and hi.op == ">=" and hi.value == 0.8
        lo = t.resolve(make_ctx({("vix_pctile_252d", "market"): 0.1}))
        assert lo is not None and lo.op == "<="
        assert t.resolve(make_ctx({("vix_pctile_252d", "market"): 0.5})) is None  # mid -> none

    def test_direction_respects_band(self) -> None:
        t = template(
            mode=Mode.MARKET_DIRECTION,
            feature="dgs10_chg_63d",
            evaluate_on=EvaluateOn.MARKET,
            direction_band=0.25,
        )
        assert t.resolve(make_ctx({("dgs10_chg_63d", "market"): 0.5})).op == ">"
        assert t.resolve(make_ctx({("dgs10_chg_63d", "market"): -0.5})).op == "<"
        assert t.resolve(make_ctx({("dgs10_chg_63d", "market"): 0.1})) is None  # inside band


class TestSelfModes:
    def test_bucket_top_bottom_and_middle(self) -> None:
        t = template(mode=Mode.SELF_BUCKET, feature="ret_63d")
        q = {("ret_63d", "self", 0.8): 0.15, ("ret_63d", "self", 0.2): -0.10}
        top = t.resolve(make_ctx({("ret_63d", "self"): 0.30}, q))
        assert top is not None and top.op == ">=" and top.threshold_kind == "own_percentile"
        assert top.percentile == 0.8
        bottom = t.resolve(make_ctx({("ret_63d", "self"): -0.20}, q))
        assert bottom is not None and bottom.op == "<="
        assert t.resolve(make_ctx({("ret_63d", "self"): 0.0}, q)) is None  # middle

    def test_bucket_suppressed_without_history(self) -> None:
        t = template(mode=Mode.SELF_BUCKET, feature="pe_forward", family="valuation")
        # quantiles return None -> insufficient own history -> suppressed
        assert t.resolve(make_ctx({("pe_forward", "self"): 40.0}, {})) is None

    def test_structural_sign(self) -> None:
        t = template(mode=Mode.SELF_STRUCTURAL, feature="price_to_ma200")
        assert t.resolve(make_ctx({("price_to_ma200", "self"): 0.05})).op == ">="
        assert t.resolve(make_ctx({("price_to_ma200", "self"): -0.05})).op == "<"


class TestSectorAndCatalyst:
    def test_sector_etf_requires_mapping(self) -> None:
        t = template(
            mode=Mode.SECTOR_STRUCTURAL,
            feature="price_to_ma50",
            family="sector",
            evaluate_on=EvaluateOn.SECTOR_ETF,
        )
        assert t.resolve(make_ctx({("price_to_ma50", "sector_etf"): 0.1}, sector_etf=None)) is None
        ok = t.resolve(make_ctx({("price_to_ma50", "sector_etf"): 0.1}, sector_etf="XLK"))
        assert ok is not None and ok.op == ">="

    def test_catalyst_only_when_near(self) -> None:
        t = template(
            mode=Mode.CATALYST_WINDOW,
            feature="days_until_earnings",
            family="catalyst",
            catalyst_max=10.0,
        )
        near = t.resolve(make_ctx({("days_until_earnings", "self"): 4.0}))
        assert near is not None and near.op == "<=" and near.value == 10.0
        assert t.resolve(make_ctx({("days_until_earnings", "self"): 40.0})) is None
        assert t.resolve(make_ctx({})) is None


class TestRegistry:
    def test_template_set_resolves_grouped_by_family(self) -> None:
        templates = build_condition_templates()
        assert TEMPLATE_SET_VERSION == "cpe-v1"
        ctx = make_ctx(
            {
                ("regime_bull", "market"): 1.0,
                ("vix_pctile_252d", "market"): 0.9,
                ("price_to_ma200", "self"): 0.1,
                ("days_until_earnings", "self"): 3.0,
                ("ret_63d", "self"): 0.30,
            },
            {("ret_63d", "self", 0.8): 0.15, ("ret_63d", "self", 0.2): -0.1},
        )
        active = resolve_active(templates, ctx)
        assert "market" in active and "company" in active and "catalyst" in active
        # every resolved condition is fully explainable
        for conditions in active.values():
            for c in conditions:
                assert c.description and c.economic_rationale and c.op

    def test_ladder_is_descending_and_market_anchored(self) -> None:
        assert all("market" in fams for _, fams in FALLBACK_LADDER)
        assert FALLBACK_LADDER[-1][1] == frozenset({"market"})
        sizes = [len(fams) for _, fams in FALLBACK_LADDER]
        assert sizes[0] == 4 and sizes[-1] == 1
