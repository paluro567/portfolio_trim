"""Repository for company_fundamentals (dated snapshots)."""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.domain.models import CompanyFundamentals


class FundamentalsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_snapshot(self, instrument_id: int, as_of: date) -> CompanyFundamentals | None:
        return self._session.get(CompanyFundamentals, (instrument_id, as_of))

    def latest_snapshot(
        self, instrument_id: int, before: date | None = None
    ) -> CompanyFundamentals | None:
        stmt = (
            select(CompanyFundamentals)
            .where(CompanyFundamentals.instrument_id == instrument_id)
            .order_by(CompanyFundamentals.as_of_date.desc())
            .limit(1)
        )
        if before is not None:
            stmt = stmt.where(CompanyFundamentals.as_of_date < before)
        return self._session.scalar(stmt)

    def insert_snapshot(
        self, instrument_id: int, as_of: date, values: dict[str, Any], run_id: int
    ) -> CompanyFundamentals:
        snapshot = CompanyFundamentals(
            instrument_id=instrument_id,
            as_of_date=as_of,
            ingestion_run_id=run_id,
            **values,
        )
        self._session.add(snapshot)
        self._session.flush()
        return snapshot

    def snapshot_count(self, instrument_id: int) -> int:
        from sqlalchemy import func

        return self._session.scalar(
            select(func.count())
            .select_from(CompanyFundamentals)
            .where(CompanyFundamentals.instrument_id == instrument_id)
        )
