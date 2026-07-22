"""Historical analogue engine against Postgres: end-to-end selection,
outcomes, eighth-model integration, report sections, archive context."""

import json

import pytest
from typer.testing import CliRunner

from mip.core.db import session_scope
from mip.engine.evidence import DecisionEvidenceEngine
from mip.models.analogues import HistoricalAnalogueModel
from mip.research.analogues import AnalogueConfig, AnalogueEngine
from tests.integration.test_decision_evidence import build_features
from tests.integration.test_portfolio import (
    import_everything,
    portfolio_env,  # noqa: F401
)
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration

# the synthetic env is smaller than production defaults — scale the knobs
CFG = AnalogueConfig(
    market_candidate_count=300,
    sector_candidate_count=120,
    final_analogue_count=15,
    minimum_history_days=300,
    minimum_valid_analogues=5,
    min_gap_sessions=5,
)


def prepare(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)


def test_find_selects_past_only_with_gap_and_dedup(portfolio_env, tmp_path) -> None:
    prepare(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        engine = AnalogueEngine(session, CFG)
        result = engine.find("AAA")
        assert result.insufficient is None, result.insufficient
        assert len(result.analogues) >= CFG.minimum_valid_analogues
        dates = [a.date for a in result.analogues]
        assert max(dates) < result.as_of  # strictly historical
        # the adjacency window is excluded and analogues respect the gap
        ordered = sorted(dates)
        assert all(
            (b - a).days >= CFG.min_gap_sessions for a, b in zip(ordered, ordered[1:], strict=False)
        )
        # deterministic
        again = engine.find("AAA")
        assert [a.to_dict() for a in again.analogues] == [a.to_dict() for a in result.analogues]
        # outcomes: complete windows only, weighted and unweighted both present
        one_m = result.outcomes["1m"]
        assert 0 < one_m.n <= len(result.analogues)
        assert one_m.baseline_mean is not None
        assert one_m.p10 <= one_m.p25 <= one_m.median_return <= one_m.p75 <= one_m.p90
        assert one_m.median_max_drawdown <= 0.0


def test_eighth_model_flows_through_the_decision_engine(portfolio_env, tmp_path) -> None:
    prepare(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        scores = HistoricalAnalogueModel(session, CFG).evaluate("AAA")
        assert [s.horizon for s in scores] == ["1w", "2w", "1m", "3m", "6m", "1y"]
        assert all(s.model == "historical_analogues" for s in scores)
        one_m = next(s for s in scores if s.horizon == "1m")
        assert one_m.context and "outcomes" in one_m.context

        results = DecisionEvidenceEngine(session).assess(symbols=["AAA"])
        evidence = results["AAA"][2]  # 1m
        # shadow discipline: evaluated and reported, NEVER in the score
        assert "historical_analogues" in evidence.shadow_models
        assert "historical_analogues" not in evidence.participating_models
        assert "historical_analogues" not in evidence.neutral_models
        assert "historical_analogues" in evidence.model_context
        context = evidence.model_context["historical_analogues"]
        assert "environment" in context and "catalysts" in context


def test_report_shows_combined_state_sections_and_archive_context(
    portfolio_env, tmp_path, monkeypatch, test_database_url, restore_logging
) -> None:
    prepare(portfolio_env, tmp_path)
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    runner = CliRunner()
    report = runner.invoke(app, ["report", "symbol", "AAA"])
    assert report.exit_code == 0, report.output
    for section in ("MARKET ENVIRONMENT:", "CATALYSTS:", "HISTORICAL ANALOGUES"):
        assert section in report.output, section
    assert "next earnings: unavailable" in report.output  # no earnings data -> labeled

    # the archived prediction carries the full context for reconstruction
    from sqlalchemy import select

    from mip.domain.models import Prediction

    with session_scope(portfolio_env) as session:
        rows = session.scalars(select(Prediction)).all()
        assert rows, "report should have archived predictions"
        payload = rows[0].evidence["context"]
        json.dumps(payload)  # JSON-safe
        assert "historical_analogues" in payload

    research = runner.invoke(app, ["research", "analogues", "AAA"])
    assert research.exit_code == 0, research.output
    assert "OVERALL" in research.output and "W-MEAN" in research.output
    environment = runner.invoke(app, ["research", "environment"])
    assert environment.exit_code == 0, environment.output
    assert "trend" in environment.output
    catalysts = runner.invoke(app, ["research", "catalysts", "AAA"])
    assert catalysts.exit_code == 0, catalysts.output
    assert "unavailable" in catalysts.output  # honest missing catalyst data
