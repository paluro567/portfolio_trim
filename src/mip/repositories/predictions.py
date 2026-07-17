"""Prediction archive persistence: append-only predictions, derived
outcomes, and the market-data lookups evaluation needs (calendar
sessions, closes, macro series values).

IMMUTABILITY SEAM: predictions are INSERT-only. This repository exposes
no update or delete for them; inserts use ON CONFLICT DO NOTHING on the
natural key, so an archived prediction can never be overwritten.
Outcomes are derived data with a guarded upsert (idempotent re-runs).
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.domain.models import (
    DailyPrice,
    Instrument,
    MacroObservation,
    MacroSeries,
    Prediction,
    PredictionOutcome,
    TradingDay,
)

OUTCOME_FIELDS = (
    "entry_date",
    "exit_date",
    "entry_price",
    "exit_price",
    "actual_return",
    "actual_excess_return",
    "prediction_error",
    "absolute_error",
    "direction_correct",
    "outperformed",
    "underperformed",
)


class PredictionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- archive (append-only) ----------------------------------------------

    def instrument_id(self, symbol: str) -> int:
        instrument_id = self._session.scalar(
            select(Instrument.id).where(Instrument.symbol == symbol.strip().upper())
        )
        if instrument_id is None:
            raise ConfigurationError(f"unknown instrument {symbol!r}")
        return instrument_id

    def insert_predictions(self, rows: list[dict[str, Any]]) -> int:
        """Append new predictions; existing natural keys are silently kept
        as-is (never updated). Returns the number actually inserted."""
        inserted = 0
        for row in rows:
            statement = (
                pg_insert(Prediction)
                .values(**row)
                .on_conflict_do_nothing(constraint="uq_predictions_identity")
                .returning(Prediction.id)  # returns a row only when actually inserted
            )
            inserted += len(self._session.execute(statement).fetchall())
        return inserted

    # -- reads ----------------------------------------------------------------

    def pending(self) -> list[tuple[Prediction, str]]:
        """Archived predictions without an outcome yet, oldest first."""
        rows = self._session.execute(
            select(Prediction, Instrument.symbol)
            .join(Instrument, Instrument.id == Prediction.instrument_id)
            .outerjoin(PredictionOutcome, PredictionOutcome.prediction_id == Prediction.id)
            .where(PredictionOutcome.prediction_id.is_(None))
            .order_by(Prediction.as_of, Instrument.symbol, Prediction.horizon_sessions)
        ).all()
        return [(prediction, symbol) for prediction, symbol in rows]

    def all_predictions(self) -> list[tuple[Prediction, str]]:
        rows = self._session.execute(
            select(Prediction, Instrument.symbol)
            .join(Instrument, Instrument.id == Prediction.instrument_id)
            .order_by(Prediction.as_of, Instrument.symbol, Prediction.horizon_sessions)
        ).all()
        return [(prediction, symbol) for prediction, symbol in rows]

    def with_outcomes(self) -> list[tuple[Prediction, PredictionOutcome, str]]:
        rows = self._session.execute(
            select(Prediction, PredictionOutcome, Instrument.symbol)
            .join(PredictionOutcome, PredictionOutcome.prediction_id == Prediction.id)
            .join(Instrument, Instrument.id == Prediction.instrument_id)
            .order_by(Prediction.as_of, Instrument.symbol, Prediction.horizon_sessions)
        ).all()
        return [(p, o, s) for p, o, s in rows]

    # -- calendar & prices ----------------------------------------------------

    def entry_session(self, as_of: date) -> date | None:
        return self._session.scalar(
            select(TradingDay.calendar_date)
            .where(TradingDay.calendar_date <= as_of)
            .order_by(TradingDay.calendar_date.desc())
            .limit(1)
        )

    def session_after(self, entry: date, sessions: int) -> date | None:
        """The `sessions`-th trading session strictly after `entry`."""
        dates = self._session.scalars(
            select(TradingDay.calendar_date)
            .where(TradingDay.calendar_date > entry)
            .order_by(TradingDay.calendar_date)
            .limit(sessions)
        ).all()
        return dates[-1] if len(dates) == sessions else None

    def close_on(self, instrument_id: int, day: date) -> Decimal | None:
        return self._session.scalar(
            select(DailyPrice.close).where(
                DailyPrice.instrument_id == instrument_id, DailyPrice.price_date == day
            )
        )

    def closes_through(self, symbol: str, through: date, limit: int) -> list[tuple[date, float]]:
        rows = self._session.execute(
            select(DailyPrice.price_date, DailyPrice.close)
            .join(Instrument, Instrument.id == DailyPrice.instrument_id)
            .where(Instrument.symbol == symbol, DailyPrice.price_date <= through)
            .order_by(DailyPrice.price_date.desc())
            .limit(limit)
        ).all()
        return [(d, float(c)) for d, c in reversed(rows)]

    def macro_values(self, provider_code: str, through: date) -> list[tuple[date, float]]:
        rows = self._session.execute(
            select(MacroObservation.obs_date, MacroObservation.value)
            .join(MacroSeries, MacroSeries.id == MacroObservation.series_id)
            .where(
                MacroSeries.provider_code == provider_code,
                MacroObservation.obs_date <= through,
                MacroObservation.value.is_not(None),
            )
            .order_by(MacroObservation.obs_date)
        ).all()
        return [(d, float(v)) for d, v in rows]

    # -- outcomes (derived; guarded upsert) -----------------------------------

    def upsert_outcome(self, prediction_id: int, values: dict[str, Any]) -> bool:
        """Insert or update-if-different. Returns True when anything was
        written; identical re-evaluation writes nothing."""
        existing = self._session.get(PredictionOutcome, prediction_id)
        if existing is None:
            self._session.add(PredictionOutcome(prediction_id=prediction_id, **values))
            return True
        changed = False
        for field in OUTCOME_FIELDS:
            if getattr(existing, field) != values[field]:
                setattr(existing, field, values[field])
                changed = True
        return changed
