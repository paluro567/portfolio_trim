"""Repository for daily_prices and corporate_actions.

All writes are ON CONFLICT upserts against natural keys (D4): re-running
any ingestion is always safe, and insert counts come from rowcount (only
genuinely new rows are affected by DO NOTHING).
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from mip.domain.models import CorporateAction, DailyPrice


class PriceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def latest_date(self, instrument_id: int) -> date | None:
        return self._session.scalar(
            select(func.max(DailyPrice.price_date)).where(DailyPrice.instrument_id == instrument_id)
        )

    def last_close_before(self, instrument_id: int, day: date) -> Decimal | None:
        return self._session.scalar(
            select(DailyPrice.close)
            .where(DailyPrice.instrument_id == instrument_id, DailyPrice.price_date < day)
            .order_by(DailyPrice.price_date.desc())
            .limit(1)
        )

    def get_rows(self, instrument_id: int, dates: list[date]) -> dict[date, DailyPrice]:
        if not dates:
            return {}
        rows = self._session.scalars(
            select(DailyPrice).where(
                DailyPrice.instrument_id == instrument_id,
                DailyPrice.price_date.in_(dates),
            )
        )
        return {row.price_date: row for row in rows}

    def dates_in_range(self, instrument_id: int, start: date, end: date) -> set[date]:
        rows = self._session.scalars(
            select(DailyPrice.price_date).where(
                DailyPrice.instrument_id == instrument_id,
                DailyPrice.price_date >= start,
                DailyPrice.price_date <= end,
            )
        )
        return set(rows)

    def insert_rows(self, rows: list[dict[str, Any]], run_id: int) -> int:
        """Insert price rows; existing (instrument_id, price_date) untouched.
        RETURNING gives the exact inserted count (rowcount is unreliable
        for multi-row statements under psycopg3)."""
        if not rows:
            return 0
        stmt = (
            pg_insert(DailyPrice)
            .values([{**row, "ingestion_run_id": run_id} for row in rows])
            .on_conflict_do_nothing(index_elements=["instrument_id", "price_date"])
            .returning(DailyPrice.price_date)
        )
        return len(self._session.execute(stmt).fetchall())

    def apply_revision(
        self, instrument_id: int, price_date: date, changes: dict[str, Any], run_id: int
    ) -> None:
        """Update a stored row with revised provider values (bumps last_updated_at)."""
        self._session.execute(
            update(DailyPrice)
            .where(
                DailyPrice.instrument_id == instrument_id,
                DailyPrice.price_date == price_date,
            )
            .values(**changes, last_updated_at=func.now(), ingestion_run_id=run_id)
        )

    def upsert_actions(self, rows: list[dict[str, Any]], run_id: int) -> int:
        if not rows:
            return 0
        stmt = (
            pg_insert(CorporateAction)
            .values([{**row, "ingestion_run_id": run_id} for row in rows])
            .on_conflict_do_nothing(index_elements=["instrument_id", "action_type", "ex_date"])
            .returning(CorporateAction.id)
        )
        return len(self._session.execute(stmt).fetchall())

    def split_dates(self, instrument_id: int) -> set[date]:
        rows = self._session.scalars(
            select(CorporateAction.ex_date).where(
                CorporateAction.instrument_id == instrument_id,
                CorporateAction.action_type == "split",
            )
        )
        return set(rows)
