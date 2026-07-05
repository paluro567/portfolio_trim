"""Repository for earnings_observations (append-only) and its current view.

INSERT is the only write. Corrections and date shifts are new observations;
`v_earnings_current` (database view) exposes the latest observation per
(instrument_id, earnings_date)."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from mip.domain.models import EarningsObservation


class EarningsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def latest_observation(
        self, instrument_id: int, earnings_date: date
    ) -> EarningsObservation | None:
        return self._session.scalar(
            select(EarningsObservation)
            .where(
                EarningsObservation.instrument_id == instrument_id,
                EarningsObservation.earnings_date == earnings_date,
            )
            .order_by(EarningsObservation.observed_at.desc())
            .limit(1)
        )

    def insert_observation(
        self,
        instrument_id: int,
        earnings_date: date,
        observed_at: datetime,
        values: dict[str, Any],
        run_id: int,
    ) -> EarningsObservation:
        observation = EarningsObservation(
            instrument_id=instrument_id,
            earnings_date=earnings_date,
            observed_at=observed_at,
            ingestion_run_id=run_id,
            **values,
        )
        self._session.add(observation)
        self._session.flush()
        return observation

    def observations(self, instrument_id: int) -> list[EarningsObservation]:
        return list(
            self._session.scalars(
                select(EarningsObservation)
                .where(EarningsObservation.instrument_id == instrument_id)
                .order_by(EarningsObservation.earnings_date, EarningsObservation.observed_at)
            )
        )

    def current_calendar(self, instrument_id: int | None = None) -> list[dict[str, Any]]:
        """Read v_earnings_current (latest observation per instrument+date)."""
        sql = "SELECT * FROM v_earnings_current"
        params: dict[str, Any] = {}
        if instrument_id is not None:
            sql += " WHERE instrument_id = :instrument_id"
            params["instrument_id"] = instrument_id
        sql += " ORDER BY earnings_date"
        return [dict(row) for row in self._session.execute(text(sql), params).mappings()]
