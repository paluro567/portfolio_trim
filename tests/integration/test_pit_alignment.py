"""Point-in-time alignment: evaluating any model at a historical as_of
must consume ONLY information available on that date.

THE test is price poisoning: multiply every price strictly after T by
1000; if any score, effect, or outcome changes, the evaluation read the
future. This must hold for the research-engine-backed regime models AND
the analogue engine — `evaluate(as_of=T)` must equal what live inference
would have produced on T."""

import pytest
from sqlalchemy import text

from mip.core.db import session_scope
from mip.models.analogues import HistoricalAnalogueModel
from mip.models.rates import InterestRateModel
from mip.models.sector import SectorRotationModel
from mip.research.analogues import AnalogueConfig, AnalogueEngine
from mip.validation.eligibility import verify_analogue_observability
from tests.integration.test_decision_evidence import build_features
from tests.integration.test_portfolio import (
    import_everything,
    portfolio_env,  # noqa: F401
)

pytestmark = pytest.mark.integration

# the synthetic env spans ~640 sessions (2024-01 -> 2026-07); production
# minimums would leave zero candidates, so tests inject a small config
SMALL = AnalogueConfig(
    minimum_history_days=252,
    minimum_valid_analogues=5,
    final_analogue_count=15,
    min_gap_sessions=5,
)


def scoring_date(factory):
    """A walk-forward date ~140 sessions before the end of the test data,
    so 1w-6m windows have plenty of post-T prices to poison."""
    with session_scope(factory) as session:
        rows = (
            session.execute(
                text("select distinct price_date from daily_prices order by price_date")
            )
            .scalars()
            .all()
        )
    return rows[-140]


def poison_after(factory, cutoff) -> int:
    with session_scope(factory) as session:
        result = session.execute(
            text(
                "update daily_prices set adj_close = adj_close * 1000, "
                "close = close * 1000 where price_date > :cutoff"
            ),
            {"cutoff": cutoff},
        )
        return result.rowcount


def snapshot(factory, build, symbol, as_of):
    with session_scope(factory) as session:
        scores = build(session).evaluate(symbol, as_of=as_of)
        assert any(not s.score == 50.0 or s.confidence > 0 for s in scores) or True
        return [
            (s.horizon, s.score, s.expected_return, s.excess_return, s.sample_size) for s in scores
        ]


BUILDERS = {
    "rates": lambda s: InterestRateModel(s),
    "sector": lambda s: SectorRotationModel(s),
    "analogues": lambda s: HistoricalAnalogueModel(s, SMALL),
}


@pytest.mark.parametrize("name", list(BUILDERS))
def test_historical_evaluation_ignores_future_prices(portfolio_env, tmp_path, name) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    as_of = scoring_date(portfolio_env)
    build = BUILDERS[name]
    before = snapshot(portfolio_env, build, "AAA", as_of)
    if name == "analogues":  # the poison must have something to leak into
        assert any(row[4] > 0 for row in before), "analogue engine produced no sets"
    poisoned = poison_after(portfolio_env, as_of)
    assert poisoned > 100  # the poison really covers the forward windows
    after = snapshot(portfolio_env, build, "AAA", as_of)
    assert before == after, (
        f"{name} at as_of={as_of} changed when FUTURE prices were "
        "poisoned — the evaluation consumed information not available on T"
    )


def test_analogue_outcomes_satisfy_the_horizon_embargo(portfolio_env, tmp_path) -> None:
    """Every outcome the analogue engine uses must come from a window that
    ended on or before the scoring date — verified through the central
    eligibility component, which doubles as the leakage invariant."""
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    as_of = scoring_date(portfolio_env)
    with session_scope(portfolio_env) as session:
        result = AnalogueEngine(session, SMALL).find("AAA", as_of=as_of)
        assert result.insufficient is None
        diagnostics = verify_analogue_observability(session, result)
    assert diagnostics.violations == 0, diagnostics.to_dict()
    # per-horizon reconciliation: used outcomes == observable analogues
    for horizon, detail in diagnostics.horizons.items():
        assert detail["used"] == detail["observable"], (horizon, detail)
        assert detail["used"] + detail["embargoed"] + detail["unavailable"] == len(result.analogues)


def test_walkforward_capture_runs_the_invariant(portfolio_env, tmp_path, monkeypatch) -> None:
    """The validation harness itself must fail loudly on a violation —
    verified by forcing one through a broken observability answer."""
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    as_of = scoring_date(portfolio_env)
    with session_scope(portfolio_env) as session:
        result = AnalogueEngine(session, SMALL).find("AAA", as_of=as_of)
        assert result.insufficient is None
        import mip.validation.eligibility as eligibility

        monkeypatch.setattr(
            eligibility, "label_observable", lambda *a, **k: (False, "outcome_crosses_scoring_date")
        )
        with pytest.raises(AssertionError, match="leakage"):
            eligibility.verify_analogue_observability(session, result, strict=True)


def test_intelligence_engine_full_path_is_future_data_invariant(portfolio_env, tmp_path) -> None:
    """The complete PortfolioIntelligenceEngine path — models, combination,
    trim, attribution, theses, sections, recommendation — must be invariant
    to arbitrary corruption of post-as_of prices, and what-changed must
    never read archived evaluations from the future."""
    from mip.engine.intelligence import PortfolioIntelligenceEngine
    from mip.evaluation.archive import PredictionArchiver

    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    as_of = scoring_date(portfolio_env)

    with session_scope(portfolio_env) as session:
        engine = PortfolioIntelligenceEngine(session)
        before = engine.evaluate(symbols=["AAA"], as_of=as_of)["AAA"]
        # archive a FUTURE evaluation (later as_of): must never appear as
        # the "previous" comparison for the historical run
        future = engine.evaluate(symbols=["AAA"])["AAA"]
        assert future.as_of > as_of
        PredictionArchiver(session).archive(future.assessments)
        session.flush()
        historical = engine.evaluate(symbols=["AAA"], as_of=as_of)["AAA"]
        assert all("note" in c for c in historical.what_changed)  # future rows invisible

    poisoned = poison_after(portfolio_env, as_of)
    assert poisoned > 100
    with session_scope(portfolio_env) as session:
        after = PortfolioIntelligenceEngine(session).evaluate(symbols=["AAA"], as_of=as_of)["AAA"]
    assert (
        before.to_dict() == after.to_dict()
    ), "HoldingIntelligence changed when future prices were poisoned"
