from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from mip.core.db import session_scope

pytestmark = pytest.mark.integration

TABLE = "phase0_session_check"


@pytest.fixture()
def scratch_table(engine: Engine) -> Iterator[str]:
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {TABLE} (id INT PRIMARY KEY, note TEXT)"))
    yield TABLE
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE}"))


def _count(factory: sessionmaker[Session], table: str) -> int:
    with session_scope(factory) as session:
        return session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_connects(session_factory: sessionmaker[Session]) -> None:
    with session_scope(session_factory) as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1


def test_commit_persists_across_sessions(
    session_factory: sessionmaker[Session], scratch_table: str
) -> None:
    with session_scope(session_factory) as session:
        session.execute(text(f"INSERT INTO {scratch_table} VALUES (1, 'committed')"))

    assert _count(session_factory, scratch_table) == 1


def test_rollback_discards_on_error(
    session_factory: sessionmaker[Session], scratch_table: str
) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        with session_scope(session_factory) as session:
            session.execute(text(f"INSERT INTO {scratch_table} VALUES (2, 'doomed')"))
            raise RuntimeError("boom")

    assert _count(session_factory, scratch_table) == 0
