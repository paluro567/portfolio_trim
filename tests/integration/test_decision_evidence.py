"""Decision Evidence Engine against Postgres: real models, real normalized
evidence, real portfolio context — combined end to end."""

import json

import pytest
from typer.testing import CliRunner

from mip.core.db import session_scope
from mip.core.exceptions import ConfigurationError
from mip.engine.evidence import HORIZONS, DecisionEvidenceEngine
from mip.models.evidence import KNOWN_MODELS
from mip.portfolio.analytics import PortfolioAnalyzer
from tests.integration.test_portfolio import (
    import_everything,
    portfolio_env,  # noqa: F401
)
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration


def build_features(factory, tmp_path) -> None:
    from datetime import date

    from mip.core.config import Settings
    from mip.domain.enums import RunStatus
    from mip.features.pipeline import FeaturePipeline
    from tests.integration.test_portfolio import START, TODAY

    settings = Settings(
        database_url="postgresql+psycopg://ignored/ignored",
        rawdata_root=tmp_path,
        history_start_date=START,
        _env_file=None,
    )
    assert isinstance(START, date)
    with session_scope(factory) as session:
        pipeline = FeaturePipeline(session=session, settings=settings, today=lambda: TODAY)
        run, _ = pipeline.build(["AAA", "BBB", "XLT", "SPY"])
        assert run.status is RunStatus.SUCCESS


def test_end_to_end_combination_with_portfolio_context(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        results = DecisionEvidenceEngine(session).assess(portfolio="main")
        assert set(results) == {"AAA", "BBB"}  # symbols came from the portfolio
        items = results["AAA"]
        assert [e.horizon for e in items] == list(HORIZONS)
        for e in items:
            classified = (
                set(e.participating_models)
                | set(e.neutral_models)
                | set(e.omitted_models)
                | set(e.shadow_models)
            )
            assert classified == set(KNOWN_MODELS)  # every model accounted for
            assert 0.0 <= e.combined_confidence <= 1.0
            assert 0.0 <= e.evidence_strength <= 1.0
            if e.participating_models:
                assert e.diagnostics is not None
                assert sum(c.weight_share for c in e.evidence_breakdown) == pytest.approx(1.0)
                assert sum(c.signed_contribution for c in e.evidence_breakdown) == pytest.approx(
                    e.expected_excess_return
                )
            else:
                assert e.expected_return is None

        # portfolio context rides along verbatim, never altering statistics
        (assessment,) = PortfolioAnalyzer(session).analyze(
            "main", symbols=["AAA"], with_evidence=False
        )
        first = items[0]
        assert first.portfolio_name == "main"
        assert first.portfolio_weight == pytest.approx(assessment.portfolio_weight)
        assert first.risk_contribution == pytest.approx(assessment.risk_contribution)
        assert first.concentration_flags == assessment.concentration_flags


def test_without_portfolio_context_fields_are_empty(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        results = DecisionEvidenceEngine(session).assess(symbols=["AAA"])
        for e in results["AAA"]:
            assert e.portfolio_name is None and e.portfolio_weight is None
            assert e.concentration_flags == ()


def test_deterministic_end_to_end(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        engine = DecisionEvidenceEngine(session)
        first = [e.to_dict() for e in engine.assess(symbols=["AAA"])["AAA"]]
        second = [e.to_dict() for e in engine.assess(symbols=["AAA"])["AAA"]]
        assert first == second


def test_symbols_or_portfolio_required(portfolio_env) -> None:
    with session_scope(portfolio_env) as session:
        with pytest.raises(ConfigurationError, match="symbols or --portfolio"):
            DecisionEvidenceEngine(session).assess()


def test_cli_evidence_and_explain(
    portfolio_env, tmp_path, monkeypatch, test_database_url, restore_logging
) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    runner = CliRunner()
    table = runner.invoke(app, ["decision", "evidence", "AAA", "--portfolio", "main"])
    assert table.exit_code == 0, table.output
    assert "combined evidence" in table.output and "MODELS" in table.output
    assert "[main: weight" in table.output  # portfolio context shown

    as_json = runner.invoke(app, ["decision", "evidence", "AAA", "--json"])
    assert as_json.exit_code == 0, as_json.output
    payload = json.loads(as_json.output[as_json.output.index("{") :])
    assert len(payload["AAA"]) == len(HORIZONS)
    banned = {"trim_score", "recommendation", "action"}
    assert not banned & set(payload["AAA"][0])

    explain = runner.invoke(
        app, ["decision", "explain", "AAA", "--horizon", "1m", "--portfolio", "main"]
    )
    assert explain.exit_code == 0, explain.output
    for section in (
        "MODEL CONTRIBUTIONS",
        "POSITIVE EVIDENCE",
        "NEGATIVE EVIDENCE",
        "CONTRADICTIONS",
        "PORTFOLIO CONSIDERATIONS",
        "HISTORICAL EXPECTATIONS",
        "CONFIDENCE",
    ):
        assert section in explain.output, section
