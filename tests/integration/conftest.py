"""Integration fixtures: a THROWAWAY PostgreSQL via MIP_TEST_DATABASE_URL.

Tests skip (with instructions) when no reachable database is configured,
so the unit suite stays runnable anywhere. The Phase 0 gate requires these
to actually run — see .env.example for the variable.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from mip.core.config import Settings
from mip.core.db import create_db_engine, create_session_factory

SKIP_REASON = (
    "integration tests need a throwaway PostgreSQL: " "set MIP_TEST_DATABASE_URL (see .env.example)"
)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = os.environ.get("MIP_TEST_DATABASE_URL")
    if not url:
        pytest.skip(SKIP_REASON)
    return url


@pytest.fixture(autouse=True)
def _isolated_report_root(tmp_path_factory, monkeypatch) -> None:
    """CLI commands maintain <MIP_REPORT_ROOT>/latest/ as a side effect;
    keep every test's writes out of the repository's real data/reports."""
    monkeypatch.setenv("MIP_REPORT_ROOT", str(tmp_path_factory.mktemp("report_root")))


@pytest.fixture(scope="session")
def engine(test_database_url: str) -> Iterator[Engine]:
    settings = Settings(database_url=test_database_url, _env_file=None)
    eng = create_db_engine(settings)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"PostgreSQL not reachable ({exc.__class__.__name__}); {SKIP_REASON}")
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def make_alembic_config(database_url: str) -> "AlembicConfig":  # noqa: F821
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


@pytest.fixture()
def migrated_schema(engine: Engine, test_database_url: str) -> Iterator[None]:
    """Pristine schema at head for each test; torn down to base afterward."""
    from alembic import command

    cfg = make_alembic_config(test_database_url)
    command.upgrade(cfg, "head")
    yield
    command.downgrade(cfg, "base")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
