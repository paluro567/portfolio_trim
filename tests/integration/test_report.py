"""Portfolio Decision Report Generator against Postgres: real assessments,
real attribution, all three output formats end to end."""

import json
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

from mip.core.db import session_scope
from mip.engine.report import HORIZONS, ReportGenerator
from mip.engine.trim import TrimScoreEngine
from tests.integration.test_decision_evidence import build_features
from tests.integration.test_portfolio import (
    import_everything,
    portfolio_env,  # noqa: F401
)
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration

GENERATED_AT = datetime(2026, 7, 14, 12, 0, 0, tzinfo=UTC)


def test_symbol_report_end_to_end(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        report = ReportGenerator(session).symbol_report("AAA", portfolio="main")
        trims = {a.horizon: a for a in TrimScoreEngine(session).assess(portfolio="main")["AAA"]}
        assert [row.horizon for row in report.horizon_rows] == list(HORIZONS)
        for row in report.horizon_rows:
            assert row.trim_score == pytest.approx(trims[row.horizon].trim_score)
            assert row.confidence == trims[row.horizon].confidence
        total = report.neutral_baseline + sum(i.contribution for i in report.attribution_rows)
        assert total == pytest.approx(report.trim_score)
        assert f"{report.trim_score:.1f}" in report.narrative
        assert report.portfolio_name == "main"


def test_portfolio_report_contains_every_holding(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        report = ReportGenerator(session).portfolio_report("main", generated_at=GENERATED_AT)
        assert [p["symbol"] for p in report.position_summaries] == ["AAA", "BBB"]
        assert report.overview["n_positions"] == 2
        assert report.overview["total_market_value"] is None
        assert {e["symbol"] for e in report.highest_trim} == {"AAA", "BBB"}
        assert len(report.greatest_uncertainty) == 2
        assert len(report.cross_horizon_changes) == 2


def test_deterministic_reports(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        generator = ReportGenerator(session)
        first = generator.portfolio_report("main", generated_at=GENERATED_AT).to_dict()
        second = generator.portfolio_report("main", generated_at=GENERATED_AT).to_dict()
        assert first == second
        assert generator.symbol_report("AAA").to_dict() == generator.symbol_report("AAA").to_dict()


def test_cli_all_formats(
    portfolio_env, tmp_path, monkeypatch, test_database_url, restore_logging
) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    runner = CliRunner()
    text = runner.invoke(app, ["report", "symbol", "AAA", "--portfolio", "main"])
    assert text.exit_code == 0, text.output
    assert "AAA — decision report" in text.output
    assert "ATTRIBUTION (1m" in text.output

    md = runner.invoke(app, ["report", "symbol", "AAA", "--markdown", "--horizon", "3m"])
    assert md.exit_code == 0, md.output
    assert "# AAA — Decision Report" in md.output
    assert "## Attribution (3m)" in md.output

    as_json = runner.invoke(app, ["report", "symbol", "AAA", "--json"])
    assert as_json.exit_code == 0, as_json.output
    payload = json.loads(as_json.output[as_json.output.index("{") :])
    assert len(payload["horizon_rows"]) == len(HORIZONS)

    both = runner.invoke(app, ["report", "symbol", "AAA", "--json", "--markdown"])
    assert both.exit_code == 2

    ptext = runner.invoke(
        app, ["report", "portfolio", "--portfolio", "main", "--top", "1", "--min-confidence", "0"]
    )
    assert ptext.exit_code == 0, ptext.output
    assert "PORTFOLIO DECISION REPORT — main" in ptext.output
    assert "POSITION SUMMARIES:" in ptext.output

    pjson = runner.invoke(app, ["report", "portfolio", "--portfolio", "main", "--json"])
    assert pjson.exit_code == 0, pjson.output
    ppayload = json.loads(pjson.output[pjson.output.index("{") :])
    assert ppayload["portfolio_name"] == "main"
    assert len(ppayload["position_summaries"]) == 2

    pmd = runner.invoke(app, ["report", "portfolio", "--portfolio", "main", "--markdown"])
    assert pmd.exit_code == 0, pmd.output
    assert "# Portfolio Decision Report — main" in pmd.output
