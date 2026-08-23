"""CLI wiring, and the architectural boundary the layer must respect.

The DB is not available in unit tests, so ``_gather`` is replaced with a
prebuilt holding. What is under test here is flag routing, artifact placement
and the guarantee that the deterministic path runs unchanged when the research
layer is off.
"""

from __future__ import annotations

import ast
from contextlib import contextmanager
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mip.cli import product as product_cli
from mip.product.decide import decide
from mip.product.policy import PolicyUnavailable
from mip.product.render import render
from mip.research_assistant.config import ResearchSettings, load_research_settings
from mip.research_assistant.payload import build_payload
from tests.unit._research_support import ev
from tests.unit.test_product_slice import _cons, _pos

runner = CliRunner()


@pytest.fixture()
def stub_gather(monkeypatch, tmp_path):
    """Replace the DB-backed gather with a deterministic in-memory holding."""

    @contextmanager
    def _fake_scope(_factory):
        yield object()

    monkeypatch.setattr(product_cli, "open_session_factory", lambda: object())
    monkeypatch.setattr(product_cli, "session_scope", _fake_scope)
    monkeypatch.setattr(
        product_cli,
        "load_policy",
        lambda _p: PolicyUnavailable(reason="unset", missing=("hard_cap_pct",), path="p"),
    )

    def _gather(session, symbol, as_of, balances, policy, commit, *, want_payload):
        pos = _pos(symbol=symbol, as_of=as_of)
        cons = _cons()
        evidence = [ev("ret_21d")]
        verdicts = decide(evidence, cons, pos)
        meta = {"commit": commit, "feature_date": as_of.isoformat(), "policy": policy.to_dict()}
        markdown = render(pos, evidence, cons, verdicts, meta)
        payload = (
            build_payload(pos, evidence, cons, verdicts, policy=policy) if want_payload else None
        )
        return product_cli._Holding(
            symbol, pos, evidence, cons, verdicts, meta, markdown, payload, 0
        )

    monkeypatch.setattr(product_cli, "_gather", _gather)

    # The calibration gate queries the database, which these tests do not have.
    # Stub it to the state the real gate currently reports: blocked, with a
    # reason, so the CLI path under test is the one that actually runs today.
    def _calibration_context(_session):
        from mip.calibration.lookup import CalibrationLookup
        from mip.calibration.readiness import Check, ReadinessReport

        report = ReadinessReport(
            checks=[
                Check(
                    name="survivorship_control",
                    passed=False,
                    observed="0 delisted",
                    requirement="delisted securities present",
                    blocker="survivor-only universe",
                )
            ]
        )
        return CalibrationLookup.unavailable_because(report.reason()), report

    monkeypatch.setattr(product_cli, "_calibration_context", _calibration_context)
    return tmp_path


def _balances(tmp_path: Path) -> Path:
    path = tmp_path / "holdings.csv"
    path.write_text(
        "symbol,as_of_date,quantity,average_cost,source,notes\n"
        "TEST,2026-07-16,10,100,manual,none\n"
    )
    return path


# --------------------------------------------------------------- default path
def test_report_without_research_produces_only_the_deterministic_artifacts(stub_gather, tmp_path):
    out = tmp_path / "out"
    result = runner.invoke(
        product_cli.app,
        [
            "report",
            "--symbol",
            "TEST",
            "--as-of",
            "2026-07-16",
            "--balances",
            str(_balances(tmp_path)),
            "--out-dir",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    d = out / "2026-07-16" / "TEST"
    assert (d / "TEST_2026-07-16.md").is_file()
    assert (d / "inputs.json").is_file()
    assert (d / "report.sha256").is_file()
    assert not (d / "TEST_2026-07-16_BRIEF.md").exists(), "no brief without --with-research"
    # No research summary line is emitted (the tmp path itself contains the word,
    # so assert on the summary labels rather than the raw substring).
    assert "research  :" not in result.output
    assert "api usage :" not in result.output
    assert "brief:" not in result.output


def test_no_llm_hard_overrides_with_research(stub_gather, tmp_path):
    out = tmp_path / "out"
    result = runner.invoke(
        product_cli.app,
        [
            "report",
            "--symbol",
            "TEST",
            "--as-of",
            "2026-07-16",
            "--balances",
            str(_balances(tmp_path)),
            "--out-dir",
            str(out),
            "--with-research",
            "--no-llm",
        ],
    )
    assert result.exit_code == 0, result.output
    assert not (out / "2026-07-16" / "TEST" / "TEST_2026-07-16_BRIEF.md").exists()


def test_with_research_writes_a_brief_even_when_the_layer_is_disabled(
    stub_gather, tmp_path, monkeypatch
):
    """No API key must still yield a brief that explains itself."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("MIP_RESEARCH_ROOT", str(tmp_path / "research"))
    out = tmp_path / "out"

    result = runner.invoke(
        product_cli.app,
        [
            "report",
            "--symbol",
            "TEST",
            "--as-of",
            "2026-07-16",
            "--balances",
            str(_balances(tmp_path)),
            "--out-dir",
            str(out),
            "--with-research",
        ],
    )
    assert result.exit_code == 0, result.output

    d = out / "2026-07-16" / "TEST"
    brief = d / "TEST_2026-07-16_BRIEF.md"
    assert brief.is_file()
    text = brief.read_text()
    assert "Qualitative research is UNAVAILABLE" in text
    assert "OPENAI_API_KEY" in text
    # The research audit companion is written alongside the brief.
    assert (d / "TEST_2026-07-16_RESEARCH_AUDIT.md").is_file()
    # The deterministic long-form report is unaffected.
    assert (d / "TEST_2026-07-16.md").is_file()


def test_research_only_requires_with_research(stub_gather, tmp_path):
    result = runner.invoke(
        product_cli.app,
        [
            "report",
            "--symbol",
            "TEST",
            "--as-of",
            "2026-07-16",
            "--balances",
            str(_balances(tmp_path)),
            "--out-dir",
            str(tmp_path / "o"),
            "--research-only",
        ],
    )
    assert result.exit_code != 0
    assert "--research-only requires --with-research" in result.output


def test_bad_as_of_is_rejected(stub_gather, tmp_path):
    result = runner.invoke(
        product_cli.app,
        [
            "report",
            "--symbol",
            "TEST",
            "--as-of",
            "16-07-2026",
            "--balances",
            str(_balances(tmp_path)),
        ],
    )
    assert result.exit_code != 0
    assert "ISO YYYY-MM-DD" in result.output


def test_show_payload_prints_the_payload_and_makes_no_call(stub_gather, tmp_path):
    result = runner.invoke(
        product_cli.app,
        [
            "research",
            "--symbol",
            "TEST",
            "--as-of",
            "2026-07-16",
            "--balances",
            str(_balances(tmp_path)),
            "--show-payload",
        ],
    )
    assert result.exit_code == 0, result.output
    assert '"symbol": "TEST"' in result.output
    assert '"deterministic_verdicts"' in result.output


def test_portfolio_without_research_writes_no_research_artifacts(stub_gather, tmp_path):
    out = tmp_path / "out"
    result = runner.invoke(
        product_cli.app,
        [
            "portfolio",
            "--as-of",
            "2026-07-16",
            "--balances",
            str(_balances(tmp_path)),
            "--out-dir",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (out / "2026-07-16" / "PORTFOLIO.md").is_file()
    assert not (out / "2026-07-16" / "PORTFOLIO_RESEARCH.md").exists()


def test_max_holdings_is_accepted_as_a_cost_control(stub_gather, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("MIP_RESEARCH_ROOT", str(tmp_path / "research"))
    out = tmp_path / "out"
    result = runner.invoke(
        product_cli.app,
        [
            "portfolio",
            "--as-of",
            "2026-07-16",
            "--balances",
            str(_balances(tmp_path)),
            "--out-dir",
            str(out),
            "--with-research",
            "--max-holdings",
            "1",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (out / "2026-07-16" / "PORTFOLIO_RESEARCH.md").is_file()


# ------------------------------------------------------------------- settings
def test_settings_default_model_and_flags(monkeypatch):
    for var in ("OPENAI_MODEL", "MIP_OPENAI_ENABLED", "MIP_OPENAI_MAX_SEARCH_CALLS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-value")
    s = load_research_settings()
    assert s.model == "gpt-5.6-terra"
    assert s.enabled and s.api_key_present and s.operational


def test_settings_never_serialise_the_secret(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret-value")
    s = load_research_settings()
    body = str(s.to_dict())
    assert "sk-super-secret" not in body
    assert "api_key" not in body
    # The dataclass itself must not hold the key either.
    assert "sk-super-secret" not in repr(s)


def test_enabled_flag_can_disable_the_layer_even_with_a_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("MIP_OPENAI_ENABLED", "false")
    s = load_research_settings()
    assert not s.operational
    assert "MIP_OPENAI_ENABLED" in (s.disabled_reason() or "")


def test_missing_key_is_reported_by_name(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert "OPENAI_API_KEY" in (load_research_settings().disabled_reason() or "")


def test_invalid_numeric_env_falls_back_rather_than_crashing(monkeypatch):
    monkeypatch.setenv("MIP_OPENAI_MAX_SEARCH_CALLS", "not-a-number")
    assert load_research_settings().max_search_calls == 8


def test_settings_dataclass_has_no_key_field():
    assert "api_key" not in ResearchSettings.__slots__
    assert "api_key_present" in ResearchSettings.__slots__


# ------------------------------------------------------- architectural boundary
def test_product_layer_never_imports_the_research_layer():
    """One-way dependency: product must stay usable with the LLM layer deleted."""
    offenders = []
    for path in Path("src/mip/product").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "mip.research_assistant"
            ):
                offenders.append(f"{path.name}: from {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("mip.research_assistant"):
                        offenders.append(f"{path.name}: import {alias.name}")
    assert offenders == [], f"mip.product must not depend on the research layer: {offenders}"


def test_research_layer_never_imports_the_legacy_ensemble():
    """The retired predictive stack must not leak back in through this door."""
    forbidden = ("mip.engine", "mip.models", "mip.validation", "mip.research.")
    offenders = []
    for path in Path("src/mip/research_assistant").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = ",".join(a.name for a in node.names)
            for bad in forbidden:
                if module.startswith(bad):
                    offenders.append(f"{path.name}: {module}")
    assert offenders == [], f"research layer must not import the retired stack: {offenders}"
