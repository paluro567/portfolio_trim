"""Trim Score Engine against Postgres: real models -> decision evidence ->
trim assessments, with portfolio context and CLI, end to end."""

import json

import pytest
from typer.testing import CliRunner

from mip.core.db import session_scope
from mip.core.exceptions import ConfigurationError
from mip.engine.evidence import HORIZONS, DecisionEvidenceEngine
from mip.engine.trim import TrimConfig, TrimScoreEngine, evidence_trim_score
from tests.integration.test_decision_evidence import build_features
from tests.integration.test_portfolio import (
    import_everything,
    portfolio_env,  # noqa: F401
)
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration


def test_end_to_end_reproducible_from_decision_evidence(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    config = TrimConfig()
    with session_scope(portfolio_env) as session:
        evidence = DecisionEvidenceEngine(session).assess(portfolio="main")
        results = TrimScoreEngine(session).assess(portfolio="main")
        assert set(results) == {"AAA", "BBB"}
        for symbol, assessments in results.items():
            assert [a.horizon for a in assessments] == list(HORIZONS)
            by_horizon = {e.horizon: e for e in evidence[symbol]}
            for a in assessments:
                e = by_horizon[a.horizon]
                # the whole engine, recomputed by hand from DecisionEvidence
                expected_e = 50.0 + e.combined_confidence * (50.0 - e.combined_score)
                assert a.evidence_trim_score == pytest.approx(expected_e)
                assert a.evidence_trim_score == pytest.approx(evidence_trim_score(e))
                assert abs(a.portfolio_adjustment) <= config.max_portfolio_adjustment
                assert a.trim_score == pytest.approx(
                    min(100.0, max(0.0, a.evidence_trim_score + a.portfolio_adjustment))
                )
                assert 0.0 <= a.trim_score <= 100.0
                assert a.confidence == e.combined_confidence
                assert a.portfolio_name == "main"
                assert a.portfolio_weight == e.portfolio_weight
                assert a.model_contributions == e.evidence_breakdown
                assert a.recommendation_label
                assert a.explanation


def test_without_portfolio_no_adjustment(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        results = TrimScoreEngine(session).assess(symbols=["AAA"])
        for a in results["AAA"]:
            assert a.portfolio_adjustment == 0.0
            assert a.portfolio_weight is None and a.portfolio_name is None
            assert a.trim_score == pytest.approx(a.evidence_trim_score)
            assert any("no portfolio context" in note for note in a.limitations)


def test_deterministic_end_to_end(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        engine = TrimScoreEngine(session)
        first = [a.to_dict() for a in engine.assess(symbols=["AAA"])["AAA"]]
        second = [a.to_dict() for a in engine.assess(symbols=["AAA"])["AAA"]]
        assert first == second


def test_symbols_or_portfolio_required(portfolio_env) -> None:
    with session_scope(portfolio_env) as session:
        with pytest.raises(ConfigurationError, match="symbols or --portfolio"):
            TrimScoreEngine(session).assess()


def test_cli_score_and_explain(
    portfolio_env, tmp_path, monkeypatch, test_database_url, restore_logging
) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    runner = CliRunner()
    table = runner.invoke(app, ["trim", "score", "AAA", "--portfolio", "main"])
    assert table.exit_code == 0, table.output
    for column in ("TRIM", "EVID", "ADJ", "CONF", "EXCESS", "LABEL", "PRIMARY DRIVER"):
        assert column in table.output
    assert "trim assessment" in table.output
    assert "not trade instructions" in table.output  # disclaimer always shown

    as_json = runner.invoke(app, ["trim", "score", "AAA", "--json"])
    assert as_json.exit_code == 0, as_json.output
    payload = json.loads(as_json.output[as_json.output.index("{") :])
    assert len(payload["AAA"]) == len(HORIZONS)
    first = payload["AAA"][0]
    assert {"trim_score", "evidence_trim_score", "portfolio_adjustment", "confidence"} <= set(first)
    assert first["recommendation_label"]
    banned = {"order", "order_quantity", "execution", "broker", "action"}
    assert not banned & set(first)

    explain = runner.invoke(
        app, ["trim", "explain", "AAA", "--horizon", "1m", "--portfolio", "main"]
    )
    assert explain.exit_code == 0, explain.output
    for section in (
        "TRIM SCORE",
        "LABEL",
        "CONFIDENCE",
        "EVIDENCE FOR TRIMMING",
        "EVIDENCE AGAINST TRIMMING",
        "HISTORICAL EXPECTATION",
        "EVIDENCE QUALITY",
        "PORTFOLIO ADJUSTMENT",
        "CROSS-HORIZON NOTES",
        "LIMITATIONS",
    ):
        assert section in explain.output, section
