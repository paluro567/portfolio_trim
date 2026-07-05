from pathlib import Path

import pytest
from typer.testing import CliRunner

from mip import __version__
from mip.cli.main import app, find_project_root
from mip.core.exceptions import ConfigurationError

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"mip {__version__}" in result.output


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "Market Intelligence Platform" in result.output


def test_db_group_registered() -> None:
    result = runner.invoke(app, ["db", "--help"])
    assert result.exit_code == 0
    assert "upgrade" in result.output
    assert "downgrade" in result.output


def test_find_project_root_walks_upward(tmp_path: Path) -> None:
    (tmp_path / "alembic.ini").write_text("[alembic]\n")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert find_project_root(nested) == tmp_path


def test_find_project_root_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="alembic.ini not found"):
        find_project_root(tmp_path)
