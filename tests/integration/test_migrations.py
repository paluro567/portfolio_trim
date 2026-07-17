import re

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import Engine, inspect, text

from tests.integration.conftest import make_alembic_config

pytestmark = pytest.mark.integration

# Schema surface at head (ARCHITECTURE.md §4.1 + §4.2/§4.5). Grows per phase.
REFERENCE_TABLES = {
    # Phase 1 — reference layer
    "sectors",
    "industries",
    "instruments",
    "symbol_history",
    "trading_calendar",
    # Phase 2 — ingestion layer
    "ingestion_runs",
    "daily_prices",
    "corporate_actions",
    "data_quality_issues",
    "data_revisions",
    # Phase 3 — macro layer
    "macro_series",
    "macro_observations",
    # Phase 4 — fundamentals & earnings (v_earnings_current is a view,
    # intentionally absent from get_table_names)
    "company_fundamentals",
    "earnings_observations",
    # Phase 5 — feature store (yearly partitions are filtered in _tables)
    "feature_definitions",
    "feature_store_daily",
    "feature_store_market_daily",
    # Phase 7 — portfolio layer (§4.7; append-only ledger + projections)
    "portfolios",
    "transactions",
    "lots",
    "lot_closures",
    "position_snapshots",
    # Prediction Archive & Outcome Evaluation (ROADMAP Phase 10
    # "trim-score output tables"): immutable archive + derived outcomes
    "predictions",
    "prediction_outcomes",
}


@pytest.fixture()
def alembic_config(test_database_url: str) -> AlembicConfig:
    return make_alembic_config(test_database_url)


@pytest.fixture(autouse=True)
def clean_alembic_state(engine: Engine):
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    yield
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


_PARTITION_PATTERN = re.compile(r"^feature_store_.*_y\d{4}$")


def _tables(engine: Engine) -> set[str]:
    tables = set(inspect(engine).get_table_names())
    tables.discard("alembic_version")
    tables.discard("phase0_session_check")  # scratch table from session tests
    return {t for t in tables if not _PARTITION_PATTERN.match(t)}


def test_upgrade_head_and_downgrade_base(alembic_config: AlembicConfig, engine: Engine) -> None:
    command.upgrade(alembic_config, "head")

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version  # head revision is stamped

    command.downgrade(alembic_config, "base")

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT count(*) FROM alembic_version")).scalar_one()
    assert rows == 0  # back to pre-baseline state


def test_head_creates_exactly_the_reference_schema(
    alembic_config: AlembicConfig, engine: Engine
) -> None:
    command.upgrade(alembic_config, "head")
    assert _tables(engine) == REFERENCE_TABLES

    command.downgrade(alembic_config, "base")
    assert _tables(engine) == set()  # downgrade removes everything it created


def test_migration_cycle_is_repeatable(alembic_config: AlembicConfig, engine: Engine) -> None:
    for _ in range(2):
        command.upgrade(alembic_config, "head")
        command.downgrade(alembic_config, "base")
    assert _tables(engine) == set()
