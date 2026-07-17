"""Earnings Behavior Model: anchored regime grammar, surprise/reaction
detection, neutral paths, and architecture conformance — no database.

Quantile stub convention: quantile(feature, p) == p (see momentum tests)."""

import ast
import inspect
from datetime import date

from mip.models.base import select_active
from mip.models.earnings import (
    EVENT_WINDOW_DAYS,
    FAMILIES,
    HORIZONS,
    MIN_PERCENTILE_OBS,
    EarningsBehaviorModel,
    regime_candidates,
)

AS_OF = date(2026, 7, 10)


def q_identity(feature: str, p: float) -> float:
    return p


def latest_from(values: dict[tuple[str, str | None], float]):
    return lambda feature, symbol: values.get((feature, symbol))


def labels(active) -> list[str]:
    return [r.label for r in active]


IN_WINDOW = {("days_since_earnings", None): 3.0}
OUT_OF_WINDOW = {("days_since_earnings", None): 45.0}


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


def test_guidance_family_is_an_honest_placeholder() -> None:
    """No guidance data exists in the platform: the family must be present
    in the grammar but empty — never fabricated conditions."""
    families = regime_candidates("AMD", "XLK", q_identity)
    assert families["guidance"] == []


def test_every_candidate_is_anchored_to_the_post_report_window() -> None:
    families = regime_candidates("AMD", "XLK", q_identity)
    for candidates in families.values():
        for regime in candidates:
            anchor = regime.filters[0]
            assert anchor.feature == "days_since_earnings"
            assert anchor.op == "<=" and anchor.value == EVENT_WINDOW_DAYS


def test_sign_conditions_survive_without_percentile_history() -> None:
    families = regime_candidates("AMD", None, lambda feature, p: None)
    assert labels(families["surprise"]) == ["moderate beat", "moderate miss"]
    assert families["reaction"] == []  # all percentile-gated


# -- detection ------------------------------------------------------------------


def test_nothing_active_outside_the_event_window() -> None:
    values = OUT_OF_WINDOW | {("eps_surprise", None): 0.95}
    active = select_active(regime_candidates("AMD", None, q_identity), latest_from(values))
    assert active == []  # the anchor gates everything


def test_large_beat_beats_moderate_beat() -> None:
    values = IN_WINDOW | {("eps_surprise", None): 0.95}
    active = select_active(regime_candidates("AMD", None, q_identity), latest_from(values))
    family = [r for r in active if r.family == "surprise"]
    assert labels(family) == ["large beat"]


def test_miss_detection_and_no_stacking() -> None:
    # surprise 0.15 is negative? No — with q_identity, thresholds are the
    # percentiles themselves; a large miss needs value <= p20 AND < 0
    values = IN_WINDOW | {("eps_surprise", None): -0.5}
    active = select_active(regime_candidates("AMD", None, q_identity), latest_from(values))
    family = [r for r in active if r.family == "surprise"]
    assert labels(family) == ["large miss"]


def test_reaction_gap_beats_rally() -> None:
    values = IN_WINDOW | {("gap_1d", None): 0.95, ("ret_5d", None): 0.85}
    active = select_active(regime_candidates("AMD", None, q_identity), latest_from(values))
    family = [r for r in active if r.family == "reaction"]
    assert labels(family) == ["gap up on report"]


def test_trend_and_volatility_families() -> None:
    values = IN_WINDOW | {
        ("dist_52w_high", None): 0.9,
        ("ret_63d", None): 0.9,
        ("vol_21d", None): 0.05,
    }
    active = select_active(regime_candidates("AMD", None, q_identity), latest_from(values))
    lit = labels(active)
    assert "reported near 52w highs" in lit  # beats plain extended trend
    assert "extended trend into report" not in lit
    assert "low volatility report" in lit


def test_market_env_conditions_target_the_right_sources() -> None:
    families = regime_candidates("AMD", "XLK", q_identity)
    sector_led = families["market_env"][0]
    by_symbol = {f.symbol: f.feature for f in sector_led.filters}
    assert by_symbol["XLK"] == "rel_ret_spy_63d"
    values = IN_WINDOW | {
        ("eps_surprise", None): 0.5,
        ("regime_bull", None): 1.0,
        ("rel_ret_spy_63d", "XLK"): -0.02,  # sector NOT leading
    }
    active = select_active(regime_candidates("AMD", "XLK", q_identity), latest_from(values))
    family = [r for r in active if r.family == "market_env"]
    assert labels(family) == ["beat in bull market"]


def test_one_active_regime_per_family_at_most() -> None:
    values = IN_WINDOW | {
        ("eps_surprise", None): 0.95,
        ("gap_1d", None): 0.95,
        ("ret_5d", None): 0.95,
        ("dist_52w_high", None): 0.95,
        ("ret_63d", None): 0.95,
        ("vol_21d", None): 0.95,
        ("regime_bull", None): 1.0,
        ("rel_ret_spy_63d", "XLK"): 0.05,
    }
    active = select_active(regime_candidates("AMD", "XLK", q_identity), latest_from(values))
    assert len({r.family for r in active}) == len(active)
    assert len(active) == len(FAMILIES) - 1  # every family except empty guidance


# -- neutral paths ------------------------------------------------------------


def make_model() -> EarningsBehaviorModel:
    model = EarningsBehaviorModel.__new__(EarningsBehaviorModel)  # no DB here
    model.half_life_years, model.min_events, model.prior_events = 10.0, 5, 30.0
    model.min_history = MIN_PERCENTILE_OBS
    return model


def test_no_earnings_history_is_honestly_neutral() -> None:
    model = make_model()
    model._sector_etf = lambda symbol: None
    model._detect = lambda symbol, etf, as_of: ([], AS_OF, None)

    scores = model.evaluate("AMD")

    assert [s.horizon for s in scores] == list(HORIZONS)
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert "No reported earnings history" in s.explanation


def test_outside_event_window_is_honestly_neutral() -> None:
    model = make_model()
    model._sector_etf = lambda symbol: None
    model._detect = lambda symbol, etf, as_of: ([], AS_OF, 45.0)

    scores = model.evaluate("AMD")

    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert "outside" in s.explanation and "post-earnings window" in s.explanation


def test_no_data_at_as_of_yields_neutral_scores() -> None:
    model = make_model()
    model._sector_etf = lambda symbol: None
    model._detect = lambda symbol, etf, as_of: ([], None, 3.0)

    scores = model.evaluate("AMD", as_of=AS_OF)

    for s in scores:
        assert s.as_of == AS_OF
        assert s.score == 50.0 and s.confidence == 0.0
        assert "insufficient data" in s.explanation.lower()


# -- architecture conformance ---------------------------------------------------


def test_model_imports_no_providers_or_raw_ingestion() -> None:
    import mip.models.earnings as module

    tree = ast.parse(inspect.getsource(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = ("mip.providers", "mip.ingestion", "yfinance", "fredapi", "requests", "urllib")
    for name in imported:
        assert not name.startswith(forbidden), f"forbidden import in earnings model: {name}"
