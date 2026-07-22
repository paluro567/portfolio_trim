"""Historical analogue engine: similarity math, PIT normalization, staged
selection, temporal deduplication, leakage guards — no database."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from mip.core.exceptions import ConfigurationError
from mip.models.analogues import HistoricalAnalogueModel
from mip.research.analogues import (
    CATALYST_FEATURES,
    COMPANY_FEATURES,
    HOLDING_SECTOR_FEATURES,
    MARKET_FEATURES,
    SECTOR_ETF_FEATURES,
    Analogue,
    AnalogueConfig,
    AnalogueEngine,
    AnalogueResult,
    cosine_similarity,
    zscore_frame,
)

AS_OF = date(2026, 7, 10)


def engine_with(config: AnalogueConfig) -> AnalogueEngine:
    engine = AnalogueEngine.__new__(AnalogueEngine)
    engine._config = config
    return engine


def frame(columns: dict[str, list[float]], start: date = date(2020, 1, 1)) -> pd.DataFrame:
    length = len(next(iter(columns.values())))
    index = pd.DatetimeIndex([pd.Timestamp(start + timedelta(days=i)) for i in range(length)])
    return pd.DataFrame(columns, index=index)


# -- config ------------------------------------------------------------------------


def test_config_validation() -> None:
    with pytest.raises(ConfigurationError, match="weights"):
        AnalogueConfig(market_weight=-0.1)
    with pytest.raises(ConfigurationError, match="counts"):
        AnalogueConfig(final_analogue_count=0)
    with pytest.raises(ConfigurationError, match="coverage"):
        AnalogueConfig(min_domain_coverage=0.0)
    cfg = AnalogueConfig()
    assert cfg.weight("market") == 0.35 and cfg.weight("catalysts") == 0.15


# -- similarity math ----------------------------------------------------------------


def test_cosine_masks_missing_dimensions() -> None:
    target = np.array([1.0, 2.0, np.nan, 4.0])
    candidate = np.array([1.0, np.nan, 3.0, 4.0])
    similarity, coverage = cosine_similarity(target, candidate)
    # shared dims are indices 0 and 3 -> identical -> cosine 1.0
    assert similarity == pytest.approx(1.0)
    assert coverage == pytest.approx(0.5)
    none_sim, none_cov = cosine_similarity(np.array([np.nan]), np.array([1.0]))
    assert none_sim is None and none_cov == 0.0
    zero, _ = cosine_similarity(np.array([0.0, 0.0]), np.array([1.0, 1.0]))
    assert zero == 0.0


def test_zscore_uses_only_history_through_the_scoring_date() -> None:
    """Values AFTER the scoring date must not influence normalization."""
    values = [1.0] * 50 + [2.0] * 50
    data = frame({"x": values})
    through = data.index[49]  # end of the all-1.0 era... but std=0 drops it
    ramp = frame({"x": [float(i) for i in range(100)]})
    through = ramp.index[49]
    scored = zscore_frame(ramp, through)
    basis = ramp["x"].iloc[:50]
    expected = (ramp["x"] - basis.mean()) / basis.std(ddof=0)
    pd.testing.assert_series_equal(scored["x"], expected, check_names=False)
    # a wild future value changes nothing before `through`
    corrupted = ramp.copy()
    corrupted.iloc[-1] = 1e9
    again = zscore_frame(corrupted, through)
    pd.testing.assert_series_equal(scored["x"].iloc[:50], again["x"].iloc[:50], check_names=False)


def test_constant_columns_are_dropped() -> None:
    data = frame({"flat": [3.0] * 20, "moves": [float(i) for i in range(20)]})
    scored = zscore_frame(data, data.index[-1])
    assert list(scored.columns) == ["moves"]


# -- staged selection ---------------------------------------------------------------


def synthetic_domains(n: int = 60) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(7)
    idx_frame = frame({"a": list(rng.normal(size=n)), "b": list(rng.normal(size=n))})
    market = idx_frame.copy()
    company = frame({"c": list(rng.normal(size=n)), "d": list(rng.normal(size=n))})
    # make one candidate nearly identical to the target in every domain
    target = market.index[-1]
    twin = market.index[10]
    for f in (market, company):
        f.loc[twin] = f.loc[target] * 0.999
    return {
        "market": market,
        "sector": pd.DataFrame(),  # unavailable -> weights renormalize
        "company": company,
        "catalysts": pd.DataFrame(),
    }


def test_staged_selection_is_deterministic_and_ranks_the_twin_first() -> None:
    cfg = AnalogueConfig(minimum_valid_analogues=1, min_gap_sessions=1)
    engine = engine_with(cfg)
    domains = synthetic_domains()
    target = domains["market"].index[-1]
    candidates = list(domains["market"].index[:-1])
    scored = {k: zscore_frame(v, target) if not v.empty else v for k, v in domains.items()}
    first = engine._staged_selection(scored, target, candidates)
    second = engine._staged_selection(scored, target, candidates)
    assert first == second  # deterministic
    assert first[0].date == domains["market"].index[10].date()  # the twin wins
    assert first[0].sector is None and first[0].catalysts is None  # honest absences
    # overall equals the weight-renormalized mean of available domains
    top = first[0]
    weights = cfg.weight("market") + cfg.weight("company")
    expected = (cfg.weight("market") * top.market + cfg.weight("company") * top.company) / weights
    assert top.overall == pytest.approx(expected)


def test_market_stage_caps_candidates() -> None:
    cfg = AnalogueConfig(market_candidate_count=5, minimum_valid_analogues=1, min_gap_sessions=1)
    engine = engine_with(cfg)
    domains = synthetic_domains()
    target = domains["market"].index[-1]
    scored = {k: zscore_frame(v, target) if not v.empty else v for k, v in domains.items()}
    result = engine._staged_selection(scored, target, list(domains["market"].index[:-1]))
    assert len(result) <= 5


def test_temporal_deduplication_enforces_the_gap() -> None:
    engine = engine_with(AnalogueConfig(min_gap_sessions=10))
    index = pd.DatetimeIndex(
        [pd.Timestamp(date(2024, 1, 1) + timedelta(days=i)) for i in range(40)]
    )
    ranked = [
        Analogue(index[i].date(), 1.0 - i * 0.01, 0.9, None, 0.9, None, 1.0)
        for i in (0, 3, 5, 15, 18, 30)
    ]
    kept = engine._deduplicate(ranked, index)
    positions = [i for i in (0, 3, 5, 15, 18, 30) if index[i].date() in {a.date for a in kept}]
    assert positions == [0, 15, 30]  # 3, 5, 18 all fall inside a 10-session gap


# -- leakage guards -----------------------------------------------------------------


def test_no_forward_looking_feature_in_any_domain() -> None:
    """Forward returns and outcome fields must never enter a vector."""
    every = (
        MARKET_FEATURES
        + tuple(name for _, name in ())
        + SECTOR_ETF_FEATURES
        + HOLDING_SECTOR_FEATURES
        + COMPANY_FEATURES
        + CATALYST_FEATURES
    )
    for name in every:
        assert not name.startswith("fwd"), name
        assert "forward" not in name, name


# -- model wrapping -----------------------------------------------------------------


def make_result(insufficient: str | None = None) -> AnalogueResult:
    return AnalogueResult(
        symbol="AAA",
        as_of=AS_OF,
        analogues=(),
        environment={"trend": "bull"},
        catalysts={"days_until_earnings": None},
        insufficient=insufficient,
    )


def test_model_is_neutral_below_the_minimum() -> None:
    model = HistoricalAnalogueModel.__new__(HistoricalAnalogueModel)
    model._config = AnalogueConfig()
    score = model._score_horizon(make_result("only 3 candidate dates"), "1m", 21)
    assert score.score == 50.0 and score.confidence == 0.0
    assert score.expected_return is None
    assert "only 3 candidate dates" in score.explanation
    assert score.context["insufficient"] == "only 3 candidate dates"
    assert score.context["environment"] == {"trend": "bull"}
    # a result without enough matured outcomes is equally neutral
    empty = make_result(None)
    score = model._score_horizon(empty, "1y", 252)
    assert score.score == 50.0 and "complete 1y forward window" in score.explanation
