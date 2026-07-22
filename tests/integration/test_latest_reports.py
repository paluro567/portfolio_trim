"""Latest-report maintenance through the real CLI: every successful
report command atomically refreshes <MIP_REPORT_ROOT>/latest/ under a
stable untimestamped name; failed runs leave the previous latest intact;
report contents are byte-identical to what the command prints."""

import pytest
from typer.testing import CliRunner

from mip.core.db import session_scope
from tests.integration.test_decision_evidence import build_features
from tests.integration.test_portfolio import (
    import_everything,
    portfolio_env,  # noqa: F401
)
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture()
def latest(portfolio_env, tmp_path, monkeypatch, test_database_url, restore_logging):
    """Prepared universe + CLI env; returns the latest/ directory path."""
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    root = tmp_path / "reports"
    monkeypatch.setenv("MIP_REPORT_ROOT", str(root))
    return root / "latest"


def run_cli(args):
    from mip.cli.main import app

    return CliRunner().invoke(app, args)


def expected_institutional(portfolio_env, symbol: str) -> str:
    from mip.engine.intelligence import PortfolioIntelligenceEngine, render_institutional

    with session_scope(portfolio_env) as session:
        results = PortfolioIntelligenceEngine(session).evaluate(symbols=[symbol], portfolio="main")
        return render_institutional(results[symbol])


def test_repeated_generation_overwrites_the_latest_report(latest, portfolio_env) -> None:
    first = run_cli(["report", "institutional", "AAA", "--portfolio", "main"])
    assert first.exit_code == 0, first.output
    target = latest / "AAA.md"
    expected = expected_institutional(portfolio_env, "AAA") + "\n"
    # identical to the previous implementation: the persisted latest is
    # byte-for-byte the unchanged renderer's output, and exactly what the
    # command printed
    assert target.read_text() == expected
    assert target.read_text() in first.output

    target.write_text("sentinel — must be replaced\n")
    second = run_cli(["report", "institutional", "AAA", "--portfolio", "main"])
    assert second.exit_code == 0, second.output
    assert target.read_text() == expected  # sentinel gone, newest run wins
    assert sorted(p.name for p in latest.iterdir()) == ["AAA.md"]  # no timestamped names


def test_failed_generation_leaves_previous_latest_intact(latest) -> None:
    ok = run_cli(["report", "institutional", "AAA", "--portfolio", "main"])
    assert ok.exit_code == 0, ok.output
    before = (latest / "AAA.md").read_text()
    names = sorted(p.name for p in latest.iterdir())

    failed = run_cli(["report", "institutional", "ZZZ", "--portfolio", "main"])
    assert failed.exit_code != 0
    assert (latest / "AAA.md").read_text() == before
    assert sorted(p.name for p in latest.iterdir()) == names  # no partial or temp files


def test_multiple_symbols_update_independently(latest) -> None:
    assert run_cli(["report", "institutional", "AAA", "--portfolio", "main"]).exit_code == 0
    aaa_before = (latest / "AAA.md").read_text()
    assert run_cli(["report", "institutional", "BBB", "--portfolio", "main"]).exit_code == 0
    assert (latest / "BBB.md").is_file()
    assert (latest / "AAA.md").read_text() == aaa_before


def test_portfolio_report_overwrites_only_the_portfolio_latest(latest) -> None:
    assert run_cli(["report", "institutional", "AAA", "--portfolio", "main"]).exit_code == 0
    aaa_before = (latest / "AAA.md").read_text()

    md = run_cli(["report", "portfolio", "--portfolio", "main", "--markdown", "--no-archive"])
    assert md.exit_code == 0, md.output
    portfolio_file = latest / "Portfolio.md"
    assert portfolio_file.read_text() in md.output  # persisted == printed
    assert portfolio_file.read_text().startswith("# Portfolio Decision Report — main")
    assert (latest / "AAA.md").read_text() == aaa_before  # untouched

    portfolio_file.write_text("sentinel\n")
    again = run_cli(["report", "portfolio", "--portfolio", "main", "--markdown", "--no-archive"])
    assert again.exit_code == 0
    assert "sentinel" not in portfolio_file.read_text()

    text = run_cli(["report", "portfolio", "--portfolio", "main", "--no-archive"])
    assert text.exit_code == 0
    assert (latest / "Portfolio.txt").read_text() in text.output  # per-format files
    assert "sentinel" not in portfolio_file.read_text()


def test_symbol_decision_report_and_json_use_their_own_files(latest) -> None:
    assert run_cli(["report", "institutional", "AAA", "--portfolio", "main"]).exit_code == 0
    institutional_before = (latest / "AAA.md").read_text()

    md = run_cli(["report", "symbol", "AAA", "--markdown", "--no-archive"])
    assert md.exit_code == 0, md.output
    decision = latest / "AAA_decision.md"
    assert decision.read_text() in md.output
    assert decision.read_text().startswith("# AAA — Decision Report")
    # the institutional latest for the same symbol is a different file
    assert (latest / "AAA.md").read_text() == institutional_before

    as_json = run_cli(["report", "institutional", "AAA", "--portfolio", "main", "--json"])
    assert as_json.exit_code == 0, as_json.output
    assert (latest / "AAA.json").read_text().startswith("{")
    assert (latest / "AAA.md").read_text() == institutional_before
