"""Earnings ingestion: change-driven APPEND-ONLY observations.

A new row is inserted only when the fetched state of an
(instrument, earnings_date) differs from the latest stored observation —
so re-running is idempotent, dates that shift produce new observations,
and nothing is ever updated or deleted. Point-in-time truth survives for
the future Catalyst model (D13)."""

import time
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pandas as pd
from sqlalchemy.orm import Session

from mip.core.config import Settings
from mip.core.logging import get_logger
from mip.core.retry import retry
from mip.domain.enums import InstrumentType, IssueSeverity, RunType
from mip.domain.models import EarningsObservation, IngestionRun, Instrument
from mip.ingestion.archive import RawDataArchive
from mip.ingestion.runner import IngestOutcome, run_ingestion
from mip.providers.base import EarningsProvider
from mip.repositories.earnings import EarningsRepository
from mip.repositories.instruments import InstrumentRepository
from mip.repositories.quality import QualityRepository

logger = get_logger(__name__)

ENTITY_TYPE = "earnings"
RULE_IMPLAUSIBLE_DATE = "implausible_earnings_date"

_EPS_SCALE = Decimal("0.0001")  # NUMERIC(12,4)
_MIN_DATE = date(2000, 1, 1)
_MAX_AHEAD = timedelta(days=730)


def _eps(value: object) -> Decimal | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return Decimal(str(value)).quantize(_EPS_SCALE)


class EarningsIngestionService:
    def __init__(
        self,
        session: Session,
        provider: EarningsProvider,
        archive: RawDataArchive,
        settings: Settings,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = date.today,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session = session
        self._provider = provider
        self._archive = archive
        self._today = today
        self._now = now
        self._earnings = EarningsRepository(session)
        self._quality = QualityRepository(session)
        self._instruments = InstrumentRepository(session)
        self._fetch = retry(
            max_attempts=settings.retry_max_attempts,
            backoff_seconds=settings.retry_backoff_seconds,
            sleep=sleep,
        )(provider.fetch_earnings)

    def ingest(
        self, symbols: Sequence[str] | None = None
    ) -> tuple[IngestionRun, list[IngestOutcome]]:
        return run_ingestion(
            self._session,
            RunType.EARNINGS,
            self._provider.name,
            self._resolve(symbols),
            self._worker,
            archive_path=str(self._archive.root / "earnings"),
        )

    def _resolve(self, symbols: Sequence[str] | None) -> list[tuple[str, Instrument | None]]:
        if symbols is None:
            return [
                (i.symbol, i)
                for i in self._instruments.list_instruments()
                if i.is_active and i.instrument_type is InstrumentType.STOCK
            ]
        return [(s, self._instruments.get_by_symbol(s)) for s in symbols]

    def _worker(self, run: IngestionRun, symbol: str, instrument: Instrument) -> IngestOutcome:
        outcome = IngestOutcome(key=symbol)
        frame = self._fetch(symbol)
        if frame.empty:
            return outcome

        plausible_max = self._today() + _MAX_AHEAD
        keep: list[bool] = []
        for _, row in frame.iterrows():
            plausible = _MIN_DATE <= row["earnings_date"] <= plausible_max
            keep.append(plausible)
            if not plausible:
                self._quality.add_issue(
                    run.id,
                    ENTITY_TYPE,
                    f"{symbol}/{row['earnings_date']}",
                    RULE_IMPLAUSIBLE_DATE,
                    IssueSeverity.ERROR,
                    str(row["earnings_date"]),
                )
                outcome.quarantined += 1
        frame = frame[pd.Series(keep, index=frame.index)].reset_index(drop=True)
        if frame.empty:
            return outcome

        self._archive.write(
            "earnings",
            symbol,
            frame,
            frame["earnings_date"].iloc[0],
            frame["earnings_date"].iloc[-1],
            run.id,
        )

        observed_at = self._now()
        for _, row in frame.iterrows():
            state = {
                "time_of_day": row["time_of_day"],
                "eps_estimate": _eps(row["eps_estimate"]),
                "eps_actual": _eps(row["eps_actual"]),
                "is_confirmed": _eps(row["eps_actual"]) is not None,
            }
            latest = self._earnings.latest_observation(instrument.id, row["earnings_date"])
            if latest is not None and not self._differs(latest, state):
                continue  # unchanged state: append nothing (idempotent)
            self._earnings.insert_observation(
                instrument.id, row["earnings_date"], observed_at, state, run.id
            )
            outcome.inserted += 1

        logger.info(
            "earnings.symbol_done",
            run_id=run.id,
            symbol=symbol,
            observations=outcome.inserted,
            quarantined=outcome.quarantined,
        )
        return outcome

    @staticmethod
    def _differs(stored: EarningsObservation, state: dict[str, object]) -> bool:
        stored_estimate = (
            stored.eps_estimate.quantize(_EPS_SCALE) if stored.eps_estimate is not None else None
        )
        stored_actual = (
            stored.eps_actual.quantize(_EPS_SCALE) if stored.eps_actual is not None else None
        )
        return (
            stored.time_of_day != state["time_of_day"]
            or stored_estimate != state["eps_estimate"]
            or stored_actual != state["eps_actual"]
            or stored.is_confirmed != state["is_confirmed"]
        )
