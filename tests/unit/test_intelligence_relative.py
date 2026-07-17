"""Relative Strength Model: leadership grammar, persistence/breadth/momentum
detection, neutral paths, and architecture conformance — no database.

Quantile stub convention: quantile(feature, p) == p."""

import ast
import inspect
from datetime import date

from mip.models.base import select_active
from mip.models.relative import (
    CORE_FEATURES,
    FAMILIES,
    HORIZONS,
    MIN_PERCENTILE_OBS,
    RelativeStrengthModel,
    regime_candidates,
)

AS_OF = date(2026, 7, 10)


def q_identity(feature: str, p: float) -> float:
    return p


def latest_from(values: dict[tuple[str, str | None], float]):
    return lambda feature, symbol: values.get((feature, symbol))


def labels(active) -> list[str]:
    return [r.label for r in active]


# -- regime grammar -----------------------------------------------------------


def test_regime_library_covers_spec() -> None:
    families = regime_candidates("AMD", "XLK", q_identity)
    assert tuple(families) == FAMILIES
    all_labels = [r.label for candidates in families.values() for r in candidates]
    assert len(all_labels) == len(set(all_labels))
    assert set(HORIZONS.values()) == {5, 10, 21, 63, 126, 252}
    for family, candidates in families.items():
        for regime in candidates:
            assert regime.family == family
            assert regime.description and regime.feature


def test_industry_leadership_is_an_honest_placeholder() -> None:
    """The frozen schema has no industry->ETF mapping: the family must be
    present but empty — never invented conditions."""
    families = regime_candidates("AMD", "XLK", q_identity)
    assert families["industry_leadership"] == []


def test_no_sector_mapping_drops_sector_dependent_candidates() -> None:
    families = regime_candidates("AMD", None, q_identity)
    assert "sector_leadership" not in families
    breadth = labels(families["breadth"])
    assert breadth == ["leader in weak market"]  # only the market-side condition


def test_thresholds_come_from_the_stocks_own_percentiles() -> None:
    families = regime_candidates("AMD", "XLK", lambda f, p: 2 * p)
    strong = families["market_leadership"][2]  # 'strong market leader'
    assert strong.filters[0].feature == "rel_ret_spy_63d"
    assert strong.filters[0].op == ">=" and strong.filters[0].value == 1.8
    assert "+180.0%" in strong.description


# -- specificity / detection -------------------------------------------------------


def test_persistent_alpha_beats_nested_single_window_leadership() -> None:
    values = {
        ("rel_ret_spy_21d", None): 0.75,
        ("rel_ret_spy_63d", None): 0.95,  # also satisfies ≥p90 and ≥p70
        ("rel_ret_spy_126d", None): 0.72,
    }
    active = select_active(regime_candidates("AMD", None, q_identity), latest_from(values))
    family = [r for r in active if r.family == "market_leadership"]
    assert labels(family) == ["persistent alpha"]


def test_strong_leader_beats_plain_leader() -> None:
    values = {("rel_ret_spy_63d", None): 0.95, ("rel_ret_spy_21d", None): 0.5}
    active = select_active(regime_candidates("AMD", None, q_identity), latest_from(values))
    family = [r for r in active if r.family == "market_leadership"]
    assert labels(family) == ["strong market leader"]


def test_persistence_structure_detection() -> None:
    grammar = regime_candidates("AMD", None, q_identity)
    intact = {("rel_ret_spy_126d", None): 0.85, ("rel_ret_spy_5d", None): 0.7}
    cracking = {("rel_ret_spy_126d", None): 0.85, ("rel_ret_spy_5d", None): 0.1}
    reversing = {("rel_ret_spy_126d", None): 0.1, ("rel_ret_spy_5d", None): 0.9}
    persisting = {("rel_ret_spy_126d", None): 0.1, ("rel_ret_spy_5d", None): 0.2}

    assert "leadership intact" in labels(select_active(grammar, latest_from(intact)))
    lit = labels(select_active(grammar, latest_from(cracking)))
    assert "leadership cracking" in lit  # the false-breakout signature
    assert "leadership intact" not in lit
    assert "weakness reversing" in labels(select_active(grammar, latest_from(reversing)))
    assert "weakness persisting" in labels(select_active(grammar, latest_from(persisting)))


def test_breadth_divergence_detection() -> None:
    grammar = regime_candidates("AMD", "XLK", q_identity)
    solo = {("rel_ret_spy_63d", None): 0.85, ("rel_ret_spy_63d", "XLK"): -0.02}
    left_behind = {("rel_ret_spy_63d", None): 0.1, ("rel_ret_spy_63d", "XLK"): 0.03}
    confirmed = {("rel_ret_spy_63d", None): 0.85, ("rel_ret_spy_63d", "XLK"): 0.03}
    narrow = {("rel_ret_spy_63d", None): 0.85, ("regime_bull", None): 0.0}

    assert "solo leadership (sector weak)" in labels(select_active(grammar, latest_from(solo)))
    assert "left behind (sector strong)" in labels(select_active(grammar, latest_from(left_behind)))
    lit = labels(select_active(grammar, latest_from(confirmed)))
    assert "confirmed leadership" in lit
    assert "solo leadership (sector weak)" not in lit
    assert "leader in weak market" in labels(select_active(grammar, latest_from(narrow)))


def test_relative_momentum_detection() -> None:
    grammar = regime_candidates("AMD", None, q_identity)
    fading = {("rel_ret_spy_63d", None): 0.85, ("rel_ret_spy_accel_21d", None): 0.1}
    recovering = {("rel_ret_spy_63d", None): 0.1, ("rel_ret_spy_accel_21d", None): 0.9}
    accelerating = {("rel_ret_spy_63d", None): 0.5, ("rel_ret_spy_accel_21d", None): 0.9}

    lit = labels(select_active(grammar, latest_from(fading)))
    assert "strong but fading" in lit  # exhaustion beats plain deterioration
    assert "alpha deteriorating" not in lit
    assert "weak but recovering" in labels(select_active(grammar, latest_from(recovering)))
    assert "alpha accelerating" in labels(select_active(grammar, latest_from(accelerating)))


def test_one_active_regime_per_family_at_most() -> None:
    values = {
        ("rel_ret_spy_5d", None): 0.85,
        ("rel_ret_spy_21d", None): 0.85,
        ("rel_ret_spy_63d", None): 0.95,
        ("rel_ret_spy_126d", None): 0.85,
        ("rel_ret_sector_63d", None): 0.95,
        ("rel_ret_spy_accel_21d", None): 0.9,
        ("rel_ret_spy_63d", "XLK"): 0.03,
        ("regime_bull", None): 1.0,
    }
    active = select_active(regime_candidates("AMD", "XLK", q_identity), latest_from(values))
    assert len({r.family for r in active}) == len(active)
    # industry placeholder is empty; 'leader in weak market' needs a bear
    assert len(active) == len(FAMILIES) - 1
    assert "persistent alpha" in labels(active)
    assert "confirmed leadership" in labels(active)


# -- neutral paths ------------------------------------------------------------


def make_model() -> RelativeStrengthModel:
    model = RelativeStrengthModel.__new__(RelativeStrengthModel)  # no DB here
    model.half_life_years, model.min_events, model.prior_events = 10.0, 5, 30.0
    model.min_history = MIN_PERCENTILE_OBS
    return model


def test_insufficient_history_is_honestly_neutral() -> None:
    model = make_model()
    model._sector_etf = lambda symbol: None
    model._latest_feature_date = lambda symbol: AS_OF
    model._detect = lambda symbol, etf, as_of: ([], AS_OF, {n: 3 for n in CORE_FEATURES})

    scores = model.evaluate("AMD")

    assert [s.horizon for s in scores] == list(HORIZONS)
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert "Insufficient relative-return history" in s.explanation


def test_no_active_regimes_yields_neutral_scores() -> None:
    model = make_model()
    model._sector_etf = lambda symbol: None
    spans = {n: MIN_PERCENTILE_OBS + 100 for n in CORE_FEATURES}
    model._detect = lambda symbol, etf, as_of: ([], AS_OF, spans)

    scores = model.evaluate("AMD")

    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert "No relative-strength regime is currently active" in s.explanation


def test_no_data_at_as_of_yields_neutral_scores() -> None:
    model = make_model()
    model._sector_etf = lambda symbol: None
    spans = {n: MIN_PERCENTILE_OBS + 100 for n in CORE_FEATURES}
    model._detect = lambda symbol, etf, as_of: ([], None, spans)

    scores = model.evaluate("AMD", as_of=AS_OF)

    for s in scores:
        assert s.as_of == AS_OF
        assert s.score == 50.0 and s.confidence == 0.0
        assert "insufficient data" in s.explanation.lower()


# -- architecture conformance ---------------------------------------------------


def test_model_imports_no_providers_or_raw_ingestion() -> None:
    import mip.models.relative as module

    tree = ast.parse(inspect.getsource(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = ("mip.providers", "mip.ingestion", "yfinance", "fredapi", "requests", "urllib")
    for name in imported:
        assert not name.startswith(forbidden), f"forbidden import in relative model: {name}"
