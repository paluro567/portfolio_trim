"""Typer CLI entry point (`mip`).

Phase 2 surface: --version, `mip db upgrade|downgrade`, `mip universe
seed|list`, `mip calendar build`, `mip ingest prices`, `mip runs list`,
`mip quality list|accept`. Feature and portfolio command groups arrive
with their phases.
"""

from pathlib import Path

import typer

from mip import __version__
from mip.cli.attribution import attribution
from mip.cli.calendar import app as calendar_app
from mip.cli.decision import app as decision_app
from mip.cli.earnings import app as earnings_app
from mip.cli.evaluate import app as evaluate_app
from mip.cli.features import app as features_app
from mip.cli.ingest import app as ingest_app
from mip.cli.intelligence import app as intelligence_app
from mip.cli.macro import app as macro_app
from mip.cli.portfolio import app as portfolio_app
from mip.cli.product import app as product_app
from mip.cli.quality import app as quality_app
from mip.cli.report import app as report_app
from mip.cli.research import app as research_app
from mip.cli.research_data import app as research_data_app
from mip.cli.runs import app as runs_app
from mip.cli.securities import app as securities_app
from mip.cli.trim import app as trim_app
from mip.cli.universe import app as universe_app
from mip.cli.update import update as update_command
from mip.core.exceptions import ConfigurationError

app = typer.Typer(
    name="mip",
    help="Market Intelligence Platform — quantitative research data platform.",
    no_args_is_help=True,
)
db_app = typer.Typer(help="Database schema management (Alembic).", no_args_is_help=True)
app.add_typer(db_app, name="db")
app.add_typer(universe_app, name="universe")
app.add_typer(calendar_app, name="calendar")
app.add_typer(ingest_app, name="ingest")
app.add_typer(macro_app, name="macro")
app.add_typer(earnings_app, name="earnings")
app.add_typer(features_app, name="features")
app.add_typer(research_app, name="research")
app.add_typer(research_data_app, name="research-data")
app.add_typer(intelligence_app, name="intelligence")
app.add_typer(runs_app, name="runs")
app.add_typer(quality_app, name="quality")
app.add_typer(securities_app, name="securities")
app.add_typer(portfolio_app, name="portfolio")
app.add_typer(decision_app, name="decision")
app.add_typer(trim_app, name="trim")
app.command("attribution")(attribution)
app.add_typer(evaluate_app, name="evaluate")
app.command("update")(update_command)
app.add_typer(report_app, name="report")
app.add_typer(product_app, name="product")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"mip {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version."
    ),
) -> None:
    """Market Intelligence Platform."""


def find_project_root(start: Path | None = None) -> Path:
    """Walk upward to the directory containing alembic.ini."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "alembic.ini").is_file():
            return candidate
    raise ConfigurationError(
        f"alembic.ini not found in {current} or any parent — run from the project directory."
    )


def _alembic_config() -> "AlembicConfig":  # noqa: F821 - forward ref for lazy import
    from alembic.config import Config as AlembicConfig

    root = find_project_root()
    cfg = AlembicConfig(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    return cfg


@db_app.command("upgrade")
def db_upgrade(revision: str = typer.Argument("head", help="Target revision.")) -> None:
    """Apply migrations up to the target revision (default: head)."""
    from alembic import command

    command.upgrade(_alembic_config(), revision)
    typer.echo(f"Database upgraded to {revision}.")


@db_app.command("downgrade")
def db_downgrade(revision: str = typer.Argument(..., help="Target revision (e.g. base).")) -> None:
    """Revert migrations down to the target revision."""
    from alembic import command

    command.downgrade(_alembic_config(), revision)
    typer.echo(f"Database downgraded to {revision}.")


if __name__ == "__main__":
    app()
