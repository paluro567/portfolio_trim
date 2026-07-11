"""Sector Rotation Model: regime grammar, specificity selection, neutral
paths, and architecture conformance — all without a database."""

import ast
import inspect
from datetime import date

import pytest

from mip.models.sector import (
    ACCEL_THRESHOLDS,
    HORIZONS,
    REL_THRESHOLDS,
    WINDOWS,
    SectorRotationModel,
    regime_candidates,
    select_active,
)

AS_OF = date(2026, 7, 10)
FAMILY_COUNT = 2 * len(WINDOWS) + 1  # sector_env + stock_vs_sector per window, momentum


def latest_from(values: dict[tuple[str, str | None], float]) -> "callable":
    return lambda feature, symbol: values.get((feature, symbol))


# -- regime grammar -----------------------------------------------------------


def test_regime_library_covers_spec() -> None:
    families = regime_candidates("XLK", "AMD")
    assert len(families) == FAMILY_COUNT
    labels = [r.label for candidates in families.values() for r in candidates]
    assert len(labels) == len(set(labels))  # unambiguous evidence labels
    assert set(HORIZONS.values()) == {5, 10, 21, 63, 126, 252}
    for family, candidates in families.items():
        for regime in candidates:
            assert regime.family == family
            assert regime.description  # explanations need prose


def test_thresholds_are_ordered_and_positive() -> None:
    for window in WINDOWS:
        strong, mild = REL_THRESHOLDS[window]
        assert strong > mild > 0.0
    strong, mild = ACCEL_THRESHOLDS
    assert strong > mild > 0.0


def test_filters_target_the_right_symbols() -> None:
    families = regime_candidates("XLK", "AMD")

    outperf = families["sector_env_21d"][4]  # strong outperform
    assert outperf.filters[0].feature == "rel_ret_spy_21d"
    assert outperf.filters[0].symbol == "XLK"  # condition on the ETF, not the stock
    assert outperf.filters[0].op == ">=" and outperf.filters[0].value == 0.05

    stock = families["stock_vs_sector_63d"][0]
    assert stock.filters[0].feature == "rel_ret_sector_63d"
    assert stock.filters[0].symbol is None  # the query target (the stock)
    assert stock.filters[0].value == 0.085

    high_vol = families["sector_env_21d"][2]
    assert {f.feature for f in high_vol.filters} == {"rel_ret_spy_21d", "regime_high_vol"}

    momentum = families["sector_momentum"][0]
    assert momentum.filters[0].feature == "rel_ret_spy_accel_21d"
    assert momentum.filters[0].symbol == "XLK"


# -- specificity / no double-counting -------------------------------------------


def test_one_active_regime_per_family() -> None:
    """Strong outperformance satisfies BOTH thresholds; only the most
    specific (strong) may be kept."""
    families = regime_candidates("XLK", "AMD")
    active = select_active(
        families,
        latest_from({("rel_ret_spy_21d", "XLK"): 0.10}),
    )
    assert [r.label for r in active] == ["XLK +5% vs SPY/21d"]


def test_divergence_beats_plain_outperformance() -> None:
    values = {
        ("rel_ret_spy_21d", "XLK"): 0.10,
        ("ret_21d", "XLK"): 0.04,
        ("ret_21d", "SPY"): -0.06,
    }
    active = select_active(regime_candidates("XLK", "AMD"), latest_from(values))
    assert [r.label for r in active] == ["XLK up, SPY down/21d"]


def test_conditional_regimes_beat_plain_thresholds() -> None:
    values = {
        ("rel_ret_spy_21d", "XLK"): -0.03,
        ("ret_21d", "XLK"): 0.01,  # both up: no divergence
        ("ret_21d", "SPY"): 0.04,
        ("regime_bull", None): 1.0,
    }
    active = select_active(regime_candidates("XLK", "AMD"), latest_from(values))
    assert [r.label for r in active] == ["XLK -2% vs SPY, bull mkt/21d"]


def test_families_are_independent() -> None:
    values = {
        ("rel_ret_spy_21d", "XLK"): 0.06,
        ("rel_ret_sector_21d", None): -0.03,
        ("rel_ret_spy_accel_21d", "XLK"): 0.06,
    }
    active = select_active(regime_candidates("XLK", "AMD"), latest_from(values))
    assert [r.label for r in active] == [
        "XLK +5% vs SPY/21d",
        "AMD -2% vs XLK/21d",
        "XLK accel +5%/21d",
    ]
    assert len({r.family for r in active}) == len(active)


def test_unavailable_values_deactivate_candidates() -> None:
    """A candidate with any missing input is not active (absent, never zero) —
    e.g. regime_high_vol unavailable must not fake a high-vol regime."""
    values = {("rel_ret_spy_21d", "XLK"): 0.03}  # mild only; no VIX regime stored
    active = select_active(regime_candidates("XLK", "AMD"), latest_from(values))
    assert [r.label for r in active] == ["XLK +2% vs SPY/21d"]


def test_inside_thresholds_means_nothing_active() -> None:
    values = {(f"rel_ret_spy_{w}d", "XLK"): 0.001 for w in WINDOWS} | {
        (f"rel_ret_sector_{w}d", None): -0.001 for w in WINDOWS
    }
    assert select_active(regime_candidates("XLK", "AMD"), latest_from(values)) == []


# -- neutral paths ------------------------------------------------------------


def make_model() -> SectorRotationModel:
    model = SectorRotationModel.__new__(SectorRotationModel)  # no DB on these paths
    model.half_life_years, model.min_events, model.prior_events = 10.0, 5, 30.0
    return model


def test_no_active_regimes_yields_neutral_scores() -> None:
    model = make_model()
    model._sector_etf = lambda symbol: "XLK"
    model._detect = lambda symbol, etf, as_of: ([], AS_OF)

    scores = model.evaluate("AMD")

    assert [s.horizon for s in scores] == list(HORIZONS)
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert s.expected_return is None and s.sample_size == 0
        assert "No sector-rotation regime is currently active" in s.explanation


def test_no_sector_mapping_yields_neutral_scores() -> None:
    model = make_model()
    model._sector_etf = lambda symbol: None
    model._latest_feature_date = lambda symbol: AS_OF

    scores = model.evaluate("QQQ")

    assert [s.horizon for s in scores] == list(HORIZONS)
    for s in scores:
        assert s.as_of == AS_OF
        assert s.score == 50.0 and s.confidence == 0.0
        assert "no sector→ETF mapping" in s.explanation


# -- architecture conformance ---------------------------------------------------


def test_model_imports_no_providers_or_raw_ingestion() -> None:
    """Models consume ONLY the feature store + research engine (Phase 9
    gate): no provider adapters, no ingestion services, no external access."""
    import mip.models.sector as module

    tree = ast.parse(inspect.getsource(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = ("mip.providers", "mip.ingestion", "yfinance", "fredapi", "requests")
    for name in imported:
        assert not name.startswith(forbidden), f"forbidden import in sector model: {name}"


def test_score_interpretation_contract() -> None:
    """50 = neutral is guaranteed by score_from_z(0); the mapping is shared
    with every model (models.base)."""
    from mip.models.base import score_from_z

    assert score_from_z(0.0) == pytest.approx(50.0)
