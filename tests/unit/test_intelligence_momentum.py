"""Momentum Exhaustion Model: percentile-driven regime grammar, specificity
selection, continuation/exhaustion pairing, neutral paths, and architecture
conformance — all without a database.

Quantile stub convention: quantile(feature, p) == p, so a feature reading of
0.95 sits above its own p90 threshold (0.9), 0.35 below p40, and so on —
every test condition is readable directly."""

import ast
import inspect
from datetime import date

from mip.models.base import select_active
from mip.models.momentum import (
    FAMILIES,
    HORIZONS,
    MIN_PERCENTILE_OBS,
    MomentumExhaustionModel,
    regime_candidates,
)

AS_OF = date(2026, 7, 10)


def q_identity(feature: str, p: float) -> float:
    return p


def q_missing(missing: set[str]):
    return lambda feature, p: None if feature in missing else p


def latest_from(values: dict[tuple[str, str | None], float]):
    return lambda feature, symbol: values.get((feature, symbol))


def labels(active) -> list[str]:
    return [r.label for r in active]


# -- regime grammar -----------------------------------------------------------


def test_regime_library_covers_spec() -> None:
    families = regime_candidates("AMD", "XLK", q_identity)
    assert tuple(families) == FAMILIES  # all six families, stable order
    all_labels = [r.label for candidates in families.values() for r in candidates]
    assert len(all_labels) == len(set(all_labels))
    assert set(HORIZONS.values()) == {5, 10, 21, 63, 126, 252}
    for family, candidates in families.items():
        assert candidates, family
        for regime in candidates:
            assert regime.family == family
            assert regime.description and regime.feature


def test_rel_confirmation_family_needs_a_sector_etf() -> None:
    families = regime_candidates("AMD", None, q_identity)
    assert "rel_confirmation" not in families
    assert len(families) == len(FAMILIES) - 1


def test_thresholds_come_from_the_stocks_own_percentiles() -> None:
    """A doubled quantile scale must double the filter values — thresholds
    are data-derived, not constants."""
    families = regime_candidates("AMD", "XLK", lambda f, p: 2 * p)
    strong = families["abs_momentum"][1]  # '63d ret ≥ p90'
    assert strong.filters[0].feature == "ret_63d"
    assert strong.filters[0].op == ">=" and strong.filters[0].value == 1.8
    assert "+180.0%" in strong.description  # prose cites the actual value


def test_missing_history_omits_only_affected_candidates() -> None:
    families = regime_candidates("AMD", "XLK", q_missing({"ret_126d"}))
    abs_labels = [r.label for r in families["abs_momentum"]]
    assert "broad momentum ≥ p70" not in abs_labels  # needs ret_126d
    assert "63d ret ≥ p90" in abs_labels  # unaffected


def test_sign_conditions_survive_without_percentile_history() -> None:
    """Trend structure uses natural zero boundaries — available even when
    every percentile is unavailable (young listing)."""
    families = regime_candidates("AMD", None, lambda feature, p: None)
    assert [r.label for r in families["trend_structure"]] == [
        "MA bull, spread widening",
        "MA bull, spread narrowing",
        "trend crack (<MA50)",
        "below both MAs",
    ]
    assert families["abs_momentum"] == []


def test_etf_filter_targets_the_etf() -> None:
    families = regime_candidates("AMD", "XLK", q_identity)
    lagging = families["rel_confirmation"][2]
    by_symbol = {f.symbol: f for f in lagging.filters}
    assert by_symbol[None].feature == "rel_ret_sector_63d"  # the stock
    assert by_symbol["XLK"].feature == "rel_ret_spy_63d"  # the sector ETF


# -- specificity / no double-counting -------------------------------------------


def test_broad_momentum_beats_nested_single_window_conditions() -> None:
    values = {
        ("ret_21d", None): 0.75,
        ("ret_63d", None): 0.95,  # also satisfies ≥p90 and ≥p70
        ("ret_126d", None): 0.72,
    }
    active = select_active(regime_candidates("AMD", None, q_identity), latest_from(values))
    assert "broad momentum ≥ p70" in labels(active)
    assert "63d ret ≥ p90" not in labels(active)  # nested: not stacked
    assert "63d ret ≥ p70" not in labels(active)


def test_strong_beats_moderate_within_family() -> None:
    values = {("ret_63d", None): 0.95, ("ret_21d", None): 0.5, ("ret_126d", None): 0.5}
    active = select_active(regime_candidates("AMD", None, q_identity), latest_from(values))
    family = [r for r in active if r.family == "abs_momentum"]
    assert labels(family) == ["63d ret ≥ p90"]


def test_one_active_regime_per_family_at_most() -> None:
    values = {
        ("ret_21d", None): 0.85,
        ("ret_63d", None): 0.95,
        ("ret_126d", None): 0.75,
        ("dist_52w_high", None): 0.95,
        ("price_to_ma50", None): 0.95,
        ("price_to_ma200", None): 0.95,
        ("vol_ratio_21_63", None): 0.95,
        ("vol_21d", None): 0.95,
        ("atr14_pct", None): 0.95,
        ("ma50_ma200_spread_chg_21d", None): 0.5,
        ("rel_ret_sector_21d", None): 0.1,
        ("rel_ret_sector_63d", None): 0.1,
        ("rel_ret_spy_63d", "XLK"): 0.1,
    }
    active = select_active(regime_candidates("AMD", "XLK", q_identity), latest_from(values))
    assert len({r.family for r in active}) == len(active)  # one per family
    # every family except momentum_accel: acceleration conditions are
    # definitionally exclusive with steady broad strength (21d and 63d both
    # hot cannot be 'fading', 'recovering', or 'running ahead of trend')
    assert len(active) == len(FAMILIES) - 1
    assert "momentum_accel" not in {r.family for r in active}


# -- continuation vs exhaustion pairing ----------------------------------------


def test_same_momentum_opposite_volatility_qualifiers() -> None:
    """A strong advance is not bearish by fiat: expanding vs subdued
    volatility select DIFFERENT regimes whose history decides direction."""
    base = {("ret_63d", None): 0.75}
    expanding = base | {("vol_ratio_21_63", None): 0.9}
    subdued = base | {("vol_ratio_21_63", None): 0.2}
    grammar = regime_candidates("AMD", None, q_identity)

    lit_expanding = labels(select_active(grammar, latest_from(expanding)))
    lit_subdued = labels(select_active(grammar, latest_from(subdued)))
    assert "strong 63d, vol expanding" in lit_expanding
    assert "strong 63d, vol subdued" in lit_subdued
    assert "strong 63d, vol subdued" not in lit_expanding


def test_confirmation_vs_divergence_relative_strength() -> None:
    grammar = regime_candidates("AMD", "XLK", q_identity)
    rising = {("ret_63d", None): 0.75, ("rel_ret_sector_63d", None): 0.04}
    confirmed = rising | {("rel_ret_sector_21d", None): 0.02}
    diverging = rising | {("rel_ret_sector_21d", None): -0.02}
    lagging = {
        ("rel_ret_sector_63d", None): -0.05,
        ("rel_ret_spy_63d", "XLK"): 0.06,
    }

    assert "rising, confirmed vs XLK" in labels(select_active(grammar, latest_from(confirmed)))
    lit = labels(select_active(grammar, latest_from(diverging)))
    assert "rising, fading vs XLK" in lit  # divergence beats confirmation
    assert "rising, confirmed vs XLK" not in lit
    assert "lagging strong XLK" in labels(select_active(grammar, latest_from(lagging)))


def test_acceleration_and_deceleration_detection() -> None:
    grammar = regime_candidates("AMD", None, q_identity)
    fading = {("ret_63d", None): 0.75, ("ret_21d", None): 0.35}
    recovery = {("ret_63d", None): 0.15, ("ret_21d", None): 0.65}
    accelerating = {("ret_21d", None): 0.85, ("ret_63d", None): 0.55}

    assert "fading after advance" in labels(select_active(grammar, latest_from(fading)))
    assert "momentum recovery" in labels(select_active(grammar, latest_from(recovery)))
    assert "short-term acceleration" in labels(select_active(grammar, latest_from(accelerating)))


def test_trend_structure_detection() -> None:
    grammar = regime_candidates("AMD", None, q_identity)
    widening = {
        ("price_to_ma50", None): 0.05,
        ("price_to_ma200", None): 0.10,
        ("ma50_ma200_spread_chg_21d", None): 0.01,
    }
    narrowing = widening | {("ma50_ma200_spread_chg_21d", None): -0.01}
    crack = {("price_to_ma50", None): -0.02, ("price_to_ma200", None): 0.05}
    breakdown = {("price_to_ma50", None): -0.05, ("price_to_ma200", None): -0.05}

    assert "MA bull, spread widening" in labels(select_active(grammar, latest_from(widening)))
    assert "MA bull, spread narrowing" in labels(select_active(grammar, latest_from(narrowing)))
    assert "trend crack (<MA50)" in labels(select_active(grammar, latest_from(crack)))
    assert "below both MAs" in labels(select_active(grammar, latest_from(breakdown)))


def test_failed_breakout_beats_near_high_strength() -> None:
    values = {
        ("dist_52w_high", None): 0.95,  # still near the high
        ("ret_21d", None): 0.1,  # sharp short-term reversal
        ("ret_63d", None): 0.75,  # after a strong advance
    }
    active = select_active(regime_candidates("AMD", None, q_identity), latest_from(values))
    lit = labels(active)
    assert "failed breakout" in lit
    assert "near 52w high, strong 63d" not in lit


# -- neutral paths ------------------------------------------------------------


def make_model() -> MomentumExhaustionModel:
    model = MomentumExhaustionModel.__new__(MomentumExhaustionModel)  # no DB here
    model.half_life_years, model.min_events, model.prior_events = 10.0, 5, 30.0
    model.min_history = MIN_PERCENTILE_OBS
    return model


def test_no_active_regimes_yields_neutral_scores() -> None:
    model = make_model()
    model._sector_etf = lambda symbol: None
    model._detect = lambda symbol, etf, as_of: ([], AS_OF)

    scores = model.evaluate("AMD")

    assert [s.horizon for s in scores] == list(HORIZONS)
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert s.expected_return is None and s.sample_size == 0
        assert "No momentum regime is currently active" in s.explanation


def test_no_data_at_as_of_yields_neutral_scores() -> None:
    model = make_model()
    model._sector_etf = lambda symbol: None
    model._detect = lambda symbol, etf, as_of: ([], None)

    scores = model.evaluate("AMD", as_of=AS_OF)

    for s in scores:
        assert s.as_of == AS_OF
        assert s.score == 50.0 and s.confidence == 0.0
        assert "insufficient data" in s.explanation.lower()


# -- architecture conformance ---------------------------------------------------


def test_model_imports_no_providers_or_raw_ingestion() -> None:
    import mip.models.momentum as module

    tree = ast.parse(inspect.getsource(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = ("mip.providers", "mip.ingestion", "yfinance", "fredapi", "requests", "urllib")
    for name in imported:
        assert not name.startswith(forbidden), f"forbidden import in momentum model: {name}"
