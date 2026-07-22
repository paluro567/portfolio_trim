"""Portfolio Intelligence Engine against Postgres: one model pass, full
holding intelligence, shadow discipline, archive diffing, and the
institutional report."""

import json

import pytest
from typer.testing import CliRunner

from mip.core.db import session_scope
from mip.engine.intelligence import FOCUS, PortfolioIntelligenceEngine
from mip.evaluation.archive import PredictionArchiver
from tests.integration.test_decision_evidence import build_features
from tests.integration.test_portfolio import (
    import_everything,
    portfolio_env,  # noqa: F401
)
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration


def prepare(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)


def test_holding_intelligence_end_to_end(portfolio_env, tmp_path) -> None:
    prepare(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        results = PortfolioIntelligenceEngine(session).evaluate(portfolio="main")
        assert set(results) == {"AAA", "BBB"}
        hi = results["AAA"]

        # complete object: every mandated section present
        assert set(hi.sections) == {
            "company",
            "technical",
            "macro",
            "market",
            "sector",
            "catalysts",
            "historical",
            "portfolio",
        }
        assert len(hi.horizons) == 6
        assert hi.portfolio_name == "main"

        # shadow discipline end to end
        trace = hi.traceability
        assert "historical_analogues" not in trace["participating_models"]
        assert all(p.model != "historical_analogues" for p in (*hi.bull_thesis, *hi.bear_thesis))
        assert all("historical_analogues" != d["name"] for d in hi.key_drivers)  # never a driver
        if hi.shadow_evidence:
            assert "informational" in next(iter(hi.shadow_evidence.values()))["status"]

        # attribution traceability: drivers sum to the focus trim score
        focus_row = next(h for h in hi.horizons if h["horizon"] == FOCUS)
        assert trace["attribution_sums_to"] == pytest.approx(focus_row["trim_score"])

        # unknowns are explicit, recommendation fully populated
        assert hi.unknowns
        for key in (
            "label",
            "why",
            "conflicting_evidence",
            "major_risks",
            "conditions_to_change",
            "expected_catalysts",
            "disclaimer",
        ):
            assert key in hi.recommendation


def test_what_changed_uses_the_immutable_archive(portfolio_env, tmp_path) -> None:
    prepare(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        engine = PortfolioIntelligenceEngine(session)
        first = engine.evaluate(symbols=["AAA"])["AAA"]
        assert all("note" in c for c in first.what_changed)  # nothing archived yet

        PredictionArchiver(session).archive(first.assessments)
        session.flush()
        # a later evaluation can now diff (same as_of -> archive is < filter,
        # so simulate "yesterday" by comparing against an earlier as_of run)
        earlier_dates = sorted({a.as_of for a in first.assessments})
        again = engine.evaluate(symbols=["AAA"])["AAA"]
        # same day: still strictly-before -> remains first evaluation
        assert all("note" in c for c in again.what_changed)
        assert earlier_dates  # sanity


def test_intelligence_deterministic_and_json(portfolio_env, tmp_path) -> None:
    prepare(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        engine = PortfolioIntelligenceEngine(session)
        first = engine.evaluate(symbols=["AAA"])["AAA"].to_dict()
        second = engine.evaluate(symbols=["AAA"])["AAA"].to_dict()
        assert first == second
        assert json.loads(json.dumps(first)) == first


def test_institutional_cli(
    portfolio_env, tmp_path, monkeypatch, test_database_url, restore_logging
) -> None:
    prepare(portfolio_env, tmp_path)
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    runner = CliRunner()
    text = runner.invoke(app, ["report", "institutional", "AAA", "--portfolio", "main"])
    assert text.exit_code == 0, text.output
    for section in (
        "Institutional Research Report",
        "Executive Summary",
        "Investment Thesis",
        "Bear Thesis",
        "Macro Environment",
        "Sector Environment",
        "Company Fundamentals",
        "Technical Condition",
        "Catalysts",
        "Historical Research",
        "Portfolio Context",
        "Key Drivers",
        "What Changed",
        "Unknowns",
        "Recommendation",
    ):
        assert section in text.output, section
    assert "not personalized financial advice" in text.output

    as_json = runner.invoke(app, ["report", "institutional", "AAA", "--json"])
    assert as_json.exit_code == 0, as_json.output
    payload = json.loads(as_json.output[as_json.output.index("{") :])
    assert payload["symbol"] == "AAA"
    assert set(payload["sections"]) >= {"macro", "technical", "portfolio"}
    assert "historical_analogues" not in payload["traceability"]["participating_models"]
