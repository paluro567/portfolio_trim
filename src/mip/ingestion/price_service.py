"""Price ingestion service (D2): cursor -> fetch (retry) -> validate ->
archive -> upsert -> revisions -> run record.

Per-symbol failures are isolated: a symbol that fails permanently is
recorded in error_detail and the run continues (status=partial). An
adj_close revision in the overlap window (D12 tripwire) triggers an
immediate full-history refresh for that instrument within the same run.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.core.config import Settings
from mip.core.exceptions import MIPError
from mip.core.logging import get_logger
from mip.core.retry import retry
from mip.domain.enums import (
    CorporateActionType,
    IssueSeverity,
    RunStatus,
    RunType,
)
from mip.domain.models import IngestionRun, Instrument, TradingDay
from mip.ingestion.archive import RawDataArchive
from mip.ingestion.revisions import diff_price_row, to_decimal, to_volume
from mip.ingestion.validation import RULE_CALENDAR_GAP, validate_prices
from mip.providers.base import PriceFetch, PriceProvider
from mip.repositories.ingestion_runs import IngestionRunRepository
from mip.repositories.instruments import InstrumentRepository
from mip.repositories.prices import PriceRepository
from mip.repositories.quality import QualityRepository

logger = get_logger(__name__)

ENTITY_TYPE = "price"


@dataclass
class SymbolOutcome:
    symbol: str
    status: str = "ok"  # 'ok' | 'failed'
    inserted: int = 0
    updated: int = 0
    quarantined: int = 0
    warnings: int = 0
    revisions: int = 0
    full_refresh: bool = False
    error: str | None = None


class PriceIngestionService:
    def __init__(
        self,
        session: Session,
        provider: PriceProvider,
        archive: RawDataArchive,
        settings: Settings,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._session = session
        self._provider = provider
        self._archive = archive
        self._settings = settings
        self._today = today
        self._runs = IngestionRunRepository(session)
        self._prices = PriceRepository(session)
        self._quality = QualityRepository(session)
        self._instruments = InstrumentRepository(session)
        self._fetch = retry(
            max_attempts=settings.retry_max_attempts,
            backoff_seconds=settings.retry_backoff_seconds,
            sleep=sleep,
        )(provider.fetch_daily)

    # -- public entry point ------------------------------------------------

    def ingest(
        self, symbols: Sequence[str] | None = None, full_refresh: bool = False
    ) -> tuple[IngestionRun, list[SymbolOutcome]]:
        scope = ",".join(symbols) if symbols else "ALL"
        run = self._runs.start(RunType.PRICES, self._provider.name, scope)
        logger.info("prices.run_started", run_id=run.id, scope=scope)

        outcomes: list[SymbolOutcome] = []
        for symbol, instrument in self._resolve(symbols):
            if instrument is None:
                outcomes.append(
                    SymbolOutcome(symbol=symbol, status="failed", error="unknown symbol")
                )
                continue
            try:
                outcomes.append(self._ingest_symbol(run, instrument, full_refresh))
            except MIPError as exc:
                logger.error("prices.symbol_failed", run_id=run.id, symbol=symbol, error=str(exc))
                outcomes.append(SymbolOutcome(symbol=symbol, status="failed", error=str(exc)))

        failed = {o.symbol: o.error for o in outcomes if o.status == "failed"}
        if not outcomes or len(failed) == len(outcomes):
            status = RunStatus.FAILED
        elif failed:
            status = RunStatus.PARTIAL
        else:
            status = RunStatus.SUCCESS

        self._runs.complete(
            run,
            status=status,
            rows_inserted=sum(o.inserted for o in outcomes),
            rows_updated=sum(o.updated for o in outcomes),
            archive_path=str(self._archive.root / "prices"),
            error_detail={"failed_symbols": failed} if failed else None,
        )
        logger.info(
            "prices.run_completed",
            run_id=run.id,
            status=status.value,
            inserted=run.rows_inserted,
            updated=run.rows_updated,
            failed=len(failed),
        )
        return run, outcomes

    # -- per-symbol flow -----------------------------------------------------

    def _ingest_symbol(
        self,
        run: IngestionRun,
        instrument: Instrument,
        full_refresh: bool,
        _refresh_pass: bool = False,
    ) -> SymbolOutcome:
        symbol = instrument.symbol
        outcome = SymbolOutcome(symbol=symbol, full_refresh=full_refresh)
        cursor = self._prices.latest_date(instrument.id)

        if full_refresh or cursor is None:
            fetch_start = self._settings.history_start_date
        else:
            fetch_start = self._overlap_start(cursor)
        fetch_end = self._today()

        fetched: PriceFetch = self._fetch(symbol, fetch_start, fetch_end)
        frame = fetched.prices
        if not frame.empty:
            frame = frame[
                (frame["price_date"] >= fetch_start) & (frame["price_date"] <= fetch_end)
            ].reset_index(drop=True)

        # corporate actions first: the return-jump rule needs split dates
        action_rows = self._action_rows(instrument.id, fetched.actions)
        self._prices.upsert_actions(action_rows, run.id)
        split_dates = self._prices.split_dates(instrument.id) | {
            row["ex_date"] for row in action_rows if row["action_type"] is CorporateActionType.SPLIT
        }

        report = validate_prices(
            frame,
            split_dates=split_dates,
            accepted=self._quality.accepted_row_rules(ENTITY_TYPE, f"{symbol}/"),
            prior_close=(
                self._prices.last_close_before(instrument.id, frame["price_date"].iloc[0])
                if not frame.empty
                else None
            ),
            return_jump_threshold=self._settings.return_jump_threshold,
            stale_run_length=self._settings.stale_close_run_length,
        )

        for finding in report.row_findings:
            self._quality.add_issue(
                run.id,
                ENTITY_TYPE,
                f"{symbol}/{finding.entity_date}",
                finding.rule,
                finding.severity,
                finding.observed,
            )
            if finding.severity is IssueSeverity.ERROR:
                outcome.quarantined += 1
            else:
                outcome.warnings += 1
        for finding in report.frame_findings:
            self._quality.add_issue(
                run.id,
                ENTITY_TYPE,
                f"{symbol}/{fetch_start}..{fetch_end}",
                finding.rule,
                finding.severity,
                finding.observed,
                details=dict(finding.detail),
            )
            outcome.warnings += 1

        if not report.valid.empty:
            self._archive.write(
                "prices",
                symbol,
                report.valid,
                report.valid["price_date"].iloc[0],
                report.valid["price_date"].iloc[-1],
                run.id,
            )
        if not report.rejected.empty:
            self._archive.write(
                "prices",
                symbol,
                report.rejected,
                report.rejected["price_date"].iloc[0],
                report.rejected["price_date"].iloc[-1],
                run.id,
                rejected=True,
            )

        # Insert anything not stored yet (new dates AND overlap backfills);
        # ON CONFLICT DO NOTHING makes the count exact.
        outcome.inserted = self._prices.insert_rows(
            self._price_rows(instrument.id, report.valid), run.id
        )

        # Diff re-fetched overlap rows against stored values (D12).
        adj_close_revised = False
        if cursor is not None and not report.valid.empty:
            overlap = report.valid[report.valid["price_date"] <= cursor]
            stored = self._prices.get_rows(instrument.id, list(overlap["price_date"]))
            for _, incoming in overlap.iterrows():
                row = stored.get(incoming["price_date"])
                if row is None:
                    continue  # backfill, already inserted above
                diffs = diff_price_row(row, incoming)
                if not diffs:
                    continue
                changes: dict[str, Any] = {}
                for diff in diffs:
                    self._quality.record_revision(
                        "daily_prices",
                        f"{symbol}/{diff.price_date}",
                        diff.field,
                        diff.old_value,
                        diff.new_value,
                        run.id,
                    )
                    if diff.field == "volume":
                        changes["volume"] = to_volume(incoming["volume"])
                    else:
                        changes[diff.field] = to_decimal(incoming[diff.field])
                    if diff.field == "adj_close":
                        adj_close_revised = True
                self._prices.apply_revision(instrument.id, incoming["price_date"], changes, run.id)
                outcome.updated += 1
                outcome.revisions += len(diffs)

        # Corporate-action tripwire: provider re-adjusted history.
        if adj_close_revised and not full_refresh and not _refresh_pass:
            logger.warning(
                "prices.adj_close_tripwire",
                run_id=run.id,
                symbol=symbol,
                action="full history refresh",
            )
            refresh = self._ingest_symbol(run, instrument, True, _refresh_pass=True)
            outcome.inserted += refresh.inserted
            outcome.updated += refresh.updated
            outcome.revisions += refresh.revisions
            outcome.quarantined += refresh.quarantined
            outcome.warnings += refresh.warnings
            outcome.full_refresh = True

        if not _refresh_pass:
            outcome.warnings += self._check_calendar_gaps(run, instrument, fetch_start, fetch_end)

        logger.info(
            "prices.symbol_done",
            run_id=run.id,
            symbol=symbol,
            inserted=outcome.inserted,
            updated=outcome.updated,
            quarantined=outcome.quarantined,
            revisions=outcome.revisions,
        )
        return outcome

    # -- helpers -------------------------------------------------------------

    def _resolve(self, symbols: Sequence[str] | None) -> list[tuple[str, Instrument | None]]:
        if symbols is None:
            return [(i.symbol, i) for i in self._instruments.list_instruments() if i.is_active]
        return [(s, self._instruments.get_by_symbol(s)) for s in symbols]

    def _overlap_start(self, cursor: date) -> date:
        """First date of the revision-detection window: N sessions before cursor."""
        sessions = list(
            self._session.scalars(
                select(TradingDay.calendar_date)
                .where(TradingDay.calendar_date <= cursor)
                .order_by(TradingDay.calendar_date.desc())
                .limit(self._settings.overlap_trading_days)
            )
        )
        if sessions:
            return min(sessions)
        return cursor - timedelta(days=2 * self._settings.overlap_trading_days)

    def _price_rows(self, instrument_id: int, frame: pd.DataFrame) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for _, r in frame.iterrows():
            rows.append(
                {
                    "instrument_id": instrument_id,
                    "price_date": r["price_date"],
                    "open": to_decimal(r["open"]),
                    "high": to_decimal(r["high"]),
                    "low": to_decimal(r["low"]),
                    "close": to_decimal(r["close"]),
                    "adj_close": to_decimal(r["adj_close"]),
                    "volume": to_volume(r["volume"]),
                }
            )
        return rows

    def _action_rows(self, instrument_id: int, actions: pd.DataFrame) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for _, r in actions.iterrows():
            rows.append(
                {
                    "instrument_id": instrument_id,
                    "action_type": CorporateActionType(r["action_type"]),
                    "ex_date": r["ex_date"],
                    "split_ratio": to_decimal(r["split_ratio"]),
                    "cash_amount": to_decimal(r["cash_amount"]),
                }
            )
        return rows

    def _check_calendar_gaps(
        self, run: IngestionRun, instrument: Instrument, start: date, end: date
    ) -> int:
        """Missing trading days between the instrument's own first stored
        date (never before — IPOs aren't gaps) and the fetch end."""
        have = self._prices.dates_in_range(instrument.id, start, end)
        if not have:
            return 0
        check_start = max(start, min(have))
        expected = set(
            self._session.scalars(
                select(TradingDay.calendar_date).where(
                    TradingDay.calendar_date >= check_start,
                    TradingDay.calendar_date <= end,
                )
            )
        )
        if not expected:
            return 0  # no calendar coverage for this range: nothing to assert
        missing = sorted(expected - have)
        # the most recent session may legitimately not be published yet
        missing = [d for d in missing if d < max(expected)]
        if not missing:
            return 0
        self._quality.add_issue(
            run.id,
            ENTITY_TYPE,
            f"{instrument.symbol}/{check_start}..{end}",
            RULE_CALENDAR_GAP,
            IssueSeverity.WARNING,
            f"{len(missing)} missing trading days",
            details={"missing": [str(d) for d in missing[:10]], "total": len(missing)},
        )
        return 1
