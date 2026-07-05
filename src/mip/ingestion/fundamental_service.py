"""Fundamentals ingestion: dated snapshots with field-level cleaning,
cross-checks against prices, and same-day revision detection.

Snapshot semantics (§4.4): one row per (instrument, as_of_date). A
different day -> a new row (history accumulates). A same-day re-fetch
upserts: changed fields are ledgered in data_revisions and applied —
never a duplicate row."""

import time
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from mip.core.config import Settings
from mip.core.logging import get_logger
from mip.core.retry import retry
from mip.domain.enums import InstrumentType, IssueSeverity, RunType
from mip.domain.models import IngestionRun, Instrument
from mip.ingestion.archive import RawDataArchive
from mip.ingestion.runner import IngestOutcome, run_ingestion
from mip.ingestion.validation import validate_fundamentals
from mip.providers.base import FUNDAMENTAL_FIELDS, FundamentalsProvider
from mip.repositories.fundamentals import FundamentalsRepository
from mip.repositories.instruments import InstrumentRepository
from mip.repositories.prices import PriceRepository
from mip.repositories.quality import QualityRepository

logger = get_logger(__name__)

ENTITY_TYPE = "fundamental"
_RECENT_SPLIT_WINDOW = timedelta(days=120)

# Column scale per field: incoming values are quantized to storage scale
# BEFORE insert/compare, so Postgres rounding can't fabricate revisions.
_SCALES: dict[str, int] = {
    "market_cap": 2,
    "trailing_pe": 4,
    "forward_pe": 4,
    "price_to_book": 4,
    "trailing_eps": 4,
    "forward_eps": 4,
    "dividend_yield": 6,
    "beta": 4,
    "revenue_ttm": 2,
    "profit_margin": 6,
    "debt_to_equity": 4,
}


def _scaled(field: str, value: float | None) -> Decimal | int | None:
    if value is None:
        return None
    if field == "shares_outstanding":
        return int(value)
    return Decimal(str(value)).quantize(Decimal(1).scaleb(-_SCALES[field]))


class FundamentalIngestionService:
    def __init__(
        self,
        session: Session,
        provider: FundamentalsProvider,
        archive: RawDataArchive,
        settings: Settings,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._session = session
        self._provider = provider
        self._archive = archive
        self._today = today
        self._fundamentals = FundamentalsRepository(session)
        self._prices = PriceRepository(session)
        self._quality = QualityRepository(session)
        self._instruments = InstrumentRepository(session)
        self._fetch = retry(
            max_attempts=settings.retry_max_attempts,
            backoff_seconds=settings.retry_backoff_seconds,
            sleep=sleep,
        )(provider.fetch_fundamentals)

    def ingest(
        self, symbols: Sequence[str] | None = None
    ) -> tuple[IngestionRun, list[IngestOutcome]]:
        return run_ingestion(
            self._session,
            RunType.FUNDAMENTALS,
            self._provider.name,
            self._resolve(symbols),
            self._worker,
            archive_path=str(self._archive.root / "fundamentals"),
        )

    def _resolve(self, symbols: Sequence[str] | None) -> list[tuple[str, Instrument | None]]:
        if symbols is None:
            # fundamentals are meaningful for stocks; ETFs opt in via --symbols
            return [
                (i.symbol, i)
                for i in self._instruments.list_instruments()
                if i.is_active and i.instrument_type is InstrumentType.STOCK
            ]
        return [(s, self._instruments.get_by_symbol(s)) for s in symbols]

    def _worker(self, run: IngestionRun, symbol: str, instrument: Instrument) -> IngestOutcome:
        outcome = IngestOutcome(key=symbol)
        as_of = self._today()

        raw = self._fetch(symbol)
        prior = self._fundamentals.latest_snapshot(instrument.id, before=as_of)
        split_dates = self._prices.split_dates(instrument.id)
        cleaned, findings = validate_fundamentals(
            raw,
            prior_shares=prior.shares_outstanding if prior else None,
            latest_close=self._prices.last_close_before(instrument.id, as_of + timedelta(days=1)),
            had_recent_split=any(as_of - d <= _RECENT_SPLIT_WINDOW for d in split_dates),
        )
        for finding in findings:
            self._quality.add_issue(
                run.id,
                ENTITY_TYPE,
                f"{symbol}/{as_of}",
                finding.rule,
                finding.severity,
                finding.observed,
                details={"field": finding.field},
            )
            if finding.severity is IssueSeverity.ERROR:
                outcome.quarantined += 1  # field-level: value nulled, snapshot kept
            else:
                outcome.warnings += 1

        self._archive.write(
            "fundamentals",
            symbol,
            pd.DataFrame([{"as_of_date": as_of, **raw}]),
            as_of,
            as_of,
            run.id,
        )

        values: dict[str, Any] = {f: _scaled(f, cleaned[f]) for f in FUNDAMENTAL_FIELDS}
        existing = self._fundamentals.get_snapshot(instrument.id, as_of)
        if existing is None:
            self._fundamentals.insert_snapshot(instrument.id, as_of, values, run.id)
            outcome.inserted = 1
        else:
            changed = False
            for field_name, new in values.items():
                old = getattr(existing, field_name)
                if field_name != "shares_outstanding" and old is not None:
                    old = old.quantize(Decimal(1).scaleb(-_SCALES[field_name]))
                if old != new:
                    self._quality.record_revision(
                        "company_fundamentals",
                        f"{symbol}/{as_of}",
                        field_name,
                        str(old) if old is not None else None,
                        str(new) if new is not None else None,
                        run.id,
                    )
                    setattr(existing, field_name, new)
                    outcome.revisions += 1
                    changed = True
            if changed:
                existing.ingestion_run_id = run.id
                outcome.updated = 1
            self._session.flush()

        logger.info(
            "fundamentals.symbol_done",
            run_id=run.id,
            symbol=symbol,
            inserted=outcome.inserted,
            updated=outcome.updated,
            nulled_fields=outcome.quarantined,
            revisions=outcome.revisions,
        )
        return outcome
