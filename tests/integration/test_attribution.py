"""Evidence Attribution Engine against Postgres: real evidence, real trim
assessments, exact accounting end to end."""

import json
import math

import pytest
from typer.testing import CliRunner

from mip.core.db import session_scope
from mip.engine.attribution import AttributionEngine
from mip.engine.evidence import HORIZONS
from mip.engine.trim import TrimScoreEngine
from tests.integration.test_decision_evidence import build_features
from tests.integration.test_portfolio import (
    import_everything,
    portfolio_env,  # noqa: F401
)
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration


def total(report) -> float:
    return (
        report.neutral_baseline
        + sum(c.contribution for c in report.evidence_contributions)
        + report.portfolio_contributions.concentration_adjustment
        + report.portfolio_contributions.diversification_adjustment
        + report.clip_residual
    )


def test_end_to_end_accounting_matches_trim(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        reports = AttributionEngine(session).report(portfolio="main")
        trims = TrimScoreEngine(session).assess(portfolio="main")
        assert set(reports) == {"AAA", "BBB"}
        for symbol, items in reports.items():
            assert [r.horizon for r in items] == list(HORIZONS)
            trim_by_horizon = {a.horizon: a for a in trims[symbol]}
            for r in items:
                a = trim_by_horizon[r.horizon]
                assert r.trim_score == pytest.approx(a.trim_score)
                assert r.confidence == a.confidence
                assert math.isclose(total(r), r.trim_score, abs_tol=1e-9)
                assert r.portfolio_contributions.portfolio_overlay_contribution == pytest.approx(
                    a.portfolio_adjustment
                )
                if r.contribution_ranking:
                    assert r.contribution_ranking[-1].cumulative == pytest.approx(r.trim_score)
                assert len(r.evidence_contributions) == len(a.participating_models)


def test_without_portfolio_overlay_is_zero(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        reports = AttributionEngine(session).report(symbols=["AAA"])
        for r in reports["AAA"]:
            assert r.portfolio_contributions.portfolio_overlay_contribution == 0.0
            assert r.dominant_portfolio_driver is None
            assert all(item.kind != "portfolio" for item in r.contribution_ranking)
            assert math.isclose(total(r), r.trim_score, abs_tol=1e-9)


def test_deterministic_end_to_end(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        engine = AttributionEngine(session)
        first = [r.to_dict() for r in engine.report(symbols=["AAA"])["AAA"]]
        second = [r.to_dict() for r in engine.report(symbols=["AAA"])["AAA"]]
        assert first == second


def test_cli_text_and_json(
    portfolio_env, tmp_path, monkeypatch, test_database_url, restore_logging
) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    runner = CliRunner()
    text = runner.invoke(app, ["attribution", "AAA", "--portfolio", "main"])
    assert text.exit_code == 0, text.output
    for section in (
        "trim attribution",
        "TRIM SCORE",
        "DECOMPOSITION (sums exactly to the trim score)",
        "neutral baseline",
        "SUMMARY",
        "NOT IN THE DECOMPOSITION",
    ):
        assert section in text.output, section

    one = runner.invoke(app, ["attribution", "AAA", "--horizon", "3m"])
    assert one.exit_code == 0, one.output
    assert "3m trim attribution" in one.output

    bad = runner.invoke(app, ["attribution", "AAA", "--horizon", "9y"])
    assert bad.exit_code == 2

    as_json = runner.invoke(app, ["attribution", "AAA", "--json"])
    assert as_json.exit_code == 0, as_json.output
    payload = json.loads(as_json.output[as_json.output.index("{") :])
    assert len(payload["AAA"]) == len(HORIZONS)
    first = payload["AAA"][0]
    assert {
        "trim_score",
        "neutral_baseline",
        "evidence_contributions",
        "portfolio_contributions",
        "contribution_ranking",
        "traceability",
    } <= set(first)

    filtered = runner.invoke(app, ["attribution", "AAA", "--horizon", "1y", "--json"])
    assert filtered.exit_code == 0, filtered.output
    filtered_payload = json.loads(filtered.output[filtered.output.index("{") :])
    assert [r["horizon"] for r in filtered_payload["AAA"]] == ["1y"]
