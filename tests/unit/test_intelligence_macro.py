"""Macro Regime Model: market-scope regime grammar, composite specificity,
neutral paths, and architecture conformance — no database.

Quantile stub convention: quantile(feature, p) == p."""

import ast
import inspect
from datetime import date

from mip.models.base import select_active
from mip.models.macro import (
    CORE_FEATURES,
    FAMILIES,
    HORIZONS,
    MIN_PERCENTILE_OBS,
    MacroRegimeModel,
    regime_candidates,
)

AS_OF = date(2026, 7, 10)


def q_identity(feature: str, p: float) -> float:
    return p


def latest_from(values: dict[str, float]):
    return lambda feature, symbol: values.get(feature)


def labels(active) -> list[str]:
    return [r.label for r in active]


# -- regime grammar -----------------------------------------------------------


def test_regime_library_covers_spec() -> None:
    families = regime_candidates(q_identity)
    assert tuple(families) == FAMILIES
    all_labels = [r.label for candidates in families.values() for r in candidates]
    assert len(all_labels) == len(set(all_labels))
    assert set(HORIZONS.values()) == {5, 10, 21, 63, 126, 252}
    for family, candidates in families.items():
        assert candidates, family
        for regime in candidates:
            assert regime.family == family
            assert regime.description and regime.feature
    composite = labels(families["composite"])
    for state in ("recession-like", "soft landing", "risk-on environment", "expansion"):
        assert state in composite


def test_boundary_conditions_survive_without_percentile_history() -> None:
    """Curve inversion and disinflation+easing use sign boundaries only —
    available even with thin percentile history."""
    families = regime_candidates(lambda feature, p: None)
    assert "inversion normalizing" in labels(families["yield_curve"])
    assert "disinflation + easing" in labels(families["composite"])
    assert families["policy"] == [] or all(
        "cycle" not in r.label for r in families["policy"]
    )  # percentile-gated candidates are gone


# -- detection / specificity -------------------------------------------------------


def test_hot_inflation_beats_plain_acceleration() -> None:
    values = {"cpi_yoy": 0.9, "cpi_yoy_accel": 0.95}
    active = select_active(regime_candidates(q_identity), latest_from(values))
    family = [r for r in active if r.family == "inflation"]
    assert labels(family) == ["hot inflation, rising"]


def test_disinflation_from_high_detection() -> None:
    values = {"cpi_yoy": 0.6, "cpi_yoy_accel": -0.5}
    active = select_active(regime_candidates(q_identity), latest_from(values))
    family = [r for r in active if r.family == "inflation"]
    assert labels(family) == ["disinflation from high"]


def test_easing_and_tightening_cycles() -> None:
    grammar = regime_candidates(q_identity)
    tightening = {"fedfunds_chg_6m": 0.9, "fedfunds_level": 0.5}
    easing = {"fedfunds_chg_6m": -0.5, "fedfunds_level": 0.5}
    assert "tightening cycle" in labels(select_active(grammar, latest_from(tightening)))
    lit = labels(select_active(grammar, latest_from(easing)))
    assert "easing cycle" in lit  # -0.5 <= p20 (0.2) and < 0


def test_curve_inversion_states() -> None:
    grammar = regime_candidates(q_identity)
    normalizing = {"curve_slope_10y2y": -0.5, "curve_slope_10y2y_chg_63d": 0.1}
    deepening = {"curve_slope_10y2y": -0.5, "curve_slope_10y2y_chg_63d": -0.1}
    lit = labels(select_active(grammar, latest_from(normalizing)))
    assert "inversion normalizing" in lit
    assert "inversion deepening" not in lit
    assert "inversion deepening" in labels(select_active(grammar, latest_from(deepening)))


def test_recession_like_beats_component_states() -> None:
    values = {
        "curve_slope_10y2y": -0.8,
        "curve_slope_10y2y_chg_63d": -0.1,
        "unrate_chg_6m": 0.9,
        "vix_pctile_252d": 0.85,
        "vix_chg_21d": 0.9,
        "regime_bull": 0.0,
    }
    active = select_active(regime_candidates(q_identity), latest_from(values))
    composite = [r for r in active if r.family == "composite"]
    assert labels(composite) == ["recession-like"]  # beats risk-off etc.
    lit = labels(active)
    assert "inversion deepening" in lit
    assert "employment weakening" in lit
    assert "risk-off spike" in lit


def test_soft_landing_detection() -> None:
    values = {
        "cpi_yoy": 0.4,
        "cpi_yoy_accel": -0.3,
        "unrate_chg_6m": -0.5,
        "regime_bull": 1.0,
        "vix_pctile_252d": 0.15,
        "fedfunds_chg_6m": -0.5,
        "fedfunds_level": 0.5,
    }
    active = select_active(regime_candidates(q_identity), latest_from(values))
    composite = [r for r in active if r.family == "composite"]
    assert labels(composite) == ["soft landing"]  # beats disinflation + easing
    assert "easing cycle" in labels(active)


def test_one_active_regime_per_family_at_most() -> None:
    values = {
        "cpi_yoy": 0.9,
        "cpi_yoy_accel": 0.9,
        "fedfunds_chg_6m": 0.9,
        "fedfunds_level": 0.9,
        "curve_slope_10y2y": -0.5,
        "curve_slope_10y2y_chg_63d": -0.3,
        "unrate_chg_6m": 0.9,
        "payems_yoy": 0.1,
        "gdpc1_yoy": 0.1,
        "houst_yoy": 0.1,
        "rsafs_yoy": 0.1,
        "vix_pctile_252d": 0.9,
        "vix_chg_21d": 0.9,
        "umcsent_chg_6m": 0.1,
        "regime_bull": 0.0,
    }
    active = select_active(regime_candidates(q_identity), latest_from(values))
    assert len({r.family for r in active}) == len(active)
    assert len(active) == len(FAMILIES)  # a full risk-off tightening regime set


# -- neutral paths ------------------------------------------------------------


def make_model() -> MacroRegimeModel:
    model = MacroRegimeModel.__new__(MacroRegimeModel)  # no DB on these paths
    model.half_life_years, model.min_events, model.prior_events = 10.0, 5, 30.0
    model.min_history = MIN_PERCENTILE_OBS
    return model


def test_insufficient_macro_history_is_honestly_neutral() -> None:
    model = make_model()
    model._instrument_id = lambda symbol: 1
    model._latest_feature_date = lambda symbol: AS_OF
    model._detect = lambda as_of: ([], AS_OF, {name: 3 for name in CORE_FEATURES})

    scores = model.evaluate("AMD")

    assert [s.horizon for s in scores] == list(HORIZONS)
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert "Insufficient macro history" in s.explanation


def test_no_active_regimes_yields_neutral_scores() -> None:
    model = make_model()
    model._instrument_id = lambda symbol: 1
    spans = {name: MIN_PERCENTILE_OBS + 100 for name in CORE_FEATURES}
    model._detect = lambda as_of: ([], AS_OF, spans)

    scores = model.evaluate("AMD")

    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert "No macro regime is currently active" in s.explanation


def test_no_data_at_as_of_yields_neutral_scores() -> None:
    model = make_model()
    model._instrument_id = lambda symbol: 1
    spans = {name: MIN_PERCENTILE_OBS + 100 for name in CORE_FEATURES}
    model._detect = lambda as_of: ([], None, spans)

    scores = model.evaluate("AMD", as_of=AS_OF)

    for s in scores:
        assert s.as_of == AS_OF
        assert s.score == 50.0 and s.confidence == 0.0
        assert "insufficient data" in s.explanation.lower()


# -- architecture conformance ---------------------------------------------------


def test_model_imports_no_providers_or_raw_ingestion() -> None:
    import mip.models.macro as module

    tree = ast.parse(inspect.getsource(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = ("mip.providers", "mip.ingestion", "yfinance", "fredapi", "requests", "urllib")
    for name in imported:
        assert not name.startswith(forbidden), f"forbidden import in macro model: {name}"
