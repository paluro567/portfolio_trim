"""Price ingestion service (D2): cursor -> fetch (retry) -> validate ->
archive -> upsert -> revisions -> run record.

Per-symbol failures are isolated in SAVEPOINTs: a symbol that fails
permanently has all its database mutations rolled back, is recorded in
error_detail, and the run continues (status=partial). The fetch window
ends at the last COMPLETED session — an in-progress intraday bar is a
quote, not a fact. A material adj_close re-adjustment on a completed
historical session (raw close unchanged), or a newly arrived split,
triggers an immediate full-history refresh for that instrument within
the same run (D12 tripwire; policy and tolerances in docs/PRICES.md).
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.core.config import Settings
from mip.core.exceptions import MIPError, PermanentError
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
from mip.ingestion.revisions import RevisionDiff, diff_price_row, to_decimal, to_volume
from mip.ingestion.validation import RULE_CALENDAR_GAP, validate_prices
from mip.providers.base import PriceFetch, PriceProvider
from mip.repositories.ingestion_runs import IngestionRunRepository
from mip.repositories.instruments import InstrumentRepository
from mip.repositories.prices import PriceRepository
from mip.repositories.quality import QualityRepository

logger = get_logger(__name__)

ENTITY_TYPE = "price"

# Systematic-raw-shift guard: normal daily updates change zero historical
# raw closes; a genuine multi-row provider correction is small and rare. A
# large fraction of the compared window shifting its RAW close with no
# split action to explain it is the signature of a semantic/config error
# (auto_adjust flipped to True, raw-vs-adjusted column swap, or a provider
# schema change) — surface it as a loud per-symbol failure instead of
# recording thousands of false revisions (docs/PRICES.md §3).
RAW_SHIFT_MIN_ROWS = 5
RAW_SHIFT_ALERT_FRACTION = 0.5


@dataclass
class SymbolOutcome:
    symbol: str
    status: str = "ok"  # 'ok' | 'failed'
    inserted: int = 0  # grand totals (incremental + refresh pass)
    updated: int = 0
    quarantined: int = 0
    warnings: int = 0
    revisions: int = 0
    full_refresh: bool = False
    # reconciliation breakdown: the refresh pass's share of the totals
    refresh_inserted: int = 0
    refresh_updated: int = 0
    refresh_revisions: int = 0
    refresh_quarantined: int = 0
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
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._provider = provider
        self._archive = archive
        self._settings = settings
        self._today = today
        self._now = now
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
                # SAVEPOINT per symbol: a failure rolls back every database
                # mutation of this symbol (rows, revisions, quality issues,
                # actions) without touching other symbols or the run record.
                with self._session.begin_nested():
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
        # Never ingest an in-progress session: an intraday bar is a quote,
        # not a fact, and comparing it against the completed bar tomorrow
        # manufactures revisions (incl. false adj_close tripwires).
        fetch_end = self._completed_session_end()

        fetched: PriceFetch = self._fetch(symbol, fetch_start, fetch_end)
        frame = fetched.prices
        if not frame.empty:
            frame = frame[
                (frame["price_date"] >= fetch_start) & (frame["price_date"] <= fetch_end)
            ].reset_index(drop=True)

        # corporate actions first: the return-jump rule needs split dates,
        # and a split not seen before means the provider restated raw OHLC
        # history in new share units -> full refresh required.
        prior_split_dates = self._prices.split_dates(instrument.id)
        action_rows = self._action_rows(instrument.id, fetched.actions)
        self._prices.upsert_actions(action_rows, run.id)
        fetched_split_dates = {
            row["ex_date"] for row in action_rows if row["action_type"] is CorporateActionType.SPLIT
        }
        new_split_dates = fetched_split_dates - prior_split_dates
        split_dates = prior_split_dates | fetched_split_dates

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

        # the refresh pass is a distinct logical artifact: label it so its
        # archives can never collide with the incremental pass's paths
        archive_label = "full" if _refresh_pass else ""
        if not report.valid.empty:
            self._archive.write(
                "prices",
                symbol,
                report.valid,
                report.valid["price_date"].iloc[0],
                report.valid["price_date"].iloc[-1],
                run.id,
                label=archive_label,
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
                label=archive_label,
            )

        # Insert anything not stored yet (new dates AND overlap backfills);
        # ON CONFLICT DO NOTHING makes the count exact.
        outcome.inserted = self._prices.insert_rows(
            self._price_rows(instrument.id, report.valid), run.id
        )

        # Diff re-fetched overlap rows against stored values (D12) with
        # materiality tolerances, collecting re-adjustment evidence: a
        # material adj_close change on a session STRICTLY BEFORE the newest
        # fetched session whose raw close did not change is the fingerprint
        # of a provider back-adjustment. The trailing session completing or
        # a spot correction (close AND adj_close move together) is an
        # ordinary revision, not an escalation.
        adjustment_evidence: list[RevisionDiff] = []
        if cursor is not None and not report.valid.empty:
            newest_fetched = report.valid["price_date"].max()
            overlap = report.valid[report.valid["price_date"] <= cursor]
            stored = self._prices.get_rows(instrument.id, list(overlap["price_date"]))

            # Phase 1: compute material diffs per row (no mutation yet).
            pending: list[tuple[pd.Series, list[RevisionDiff], set[str]]] = []
            compared = raw_close_shifts = 0
            for _, incoming in overlap.iterrows():
                row = stored.get(incoming["price_date"])
                if row is None:
                    continue  # backfill, already inserted above
                compared += 1
                diffs = diff_price_row(row, incoming)
                if not diffs:
                    continue
                fields = {diff.field for diff in diffs}
                if "close" in fields:
                    raw_close_shifts += 1
                pending.append((incoming, diffs, fields))

            # Semantic guard: a systematic raw-close shift with no explaining
            # split is a config/provider-semantics error, not a revision run.
            # Only applies to the normal incremental pass — a deliberate full
            # refresh (manual, or split-/adjustment-triggered) legitimately
            # rewrites raw history and must reconcile it.
            if (
                not full_refresh
                and compared >= RAW_SHIFT_MIN_ROWS
                and not new_split_dates
                and raw_close_shifts / compared > RAW_SHIFT_ALERT_FRACTION
            ):
                raise PermanentError(
                    f"{symbol}: raw close shifted on {raw_close_shifts}/{compared} compared "
                    "sessions with no corporate action — likely an auto_adjust / "
                    "raw-vs-adjusted representation mismatch or provider semantics change; "
                    "refusing to record systematic false revisions"
                )

            # Phase 2: record and apply the genuine revisions.
            for incoming, diffs, fields in pending:
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
                    if (
                        diff.field == "adj_close"
                        and "close" not in fields
                        and diff.price_date < newest_fetched
                    ):
                        adjustment_evidence.append(diff)
                self._prices.apply_revision(instrument.id, incoming["price_date"], changes, run.id)
                outcome.updated += 1
                outcome.revisions += len(diffs)

        # Corporate-action tripwire: escalate to a full-history refresh only
        # on proven historical re-adjustment (docs/PRICES.md §3). A first
        # ingest (no cursor) already fetched full history — nothing to do.
        escalate = (
            (adjustment_evidence or new_split_dates) and cursor is not None and not full_refresh
        )
        if escalate and not _refresh_pass:
            for evidence in adjustment_evidence[:10]:
                logger.warning(
                    "prices.adjustment_evidence",
                    run_id=run.id,
                    symbol=symbol,
                    field=evidence.field,
                    price_date=str(evidence.price_date),
                    stored=evidence.old_value,
                    incoming=evidence.new_value,
                    abs_diff=evidence.abs_diff,
                    rel_diff=evidence.rel_diff,
                    tolerance=evidence.tolerance,
                )
            logger.warning(
                "prices.adj_close_tripwire",
                run_id=run.id,
                symbol=symbol,
                action="full history refresh",
                reason=(
                    "adj_close re-adjusted on completed historical session(s) "
                    "with raw close unchanged"
                    if adjustment_evidence
                    else "new split action restates raw price history"
                ),
                evidence_dates=len(adjustment_evidence),
                new_splits=sorted(str(d) for d in new_split_dates),
            )
            refresh = self._ingest_symbol(run, instrument, True, _refresh_pass=True)
            outcome.inserted += refresh.inserted
            outcome.updated += refresh.updated
            outcome.revisions += refresh.revisions
            outcome.quarantined += refresh.quarantined
            outcome.warnings += refresh.warnings
            outcome.full_refresh = True
            outcome.refresh_inserted = refresh.inserted
            outcome.refresh_updated = refresh.updated
            outcome.refresh_revisions = refresh.revisions
            outcome.refresh_quarantined = refresh.quarantined

        if _refresh_pass:
            logger.info(
                "prices.full_refresh_done",
                run_id=run.id,
                symbol=symbol,
                inserted=outcome.inserted,
                updated=outcome.updated,
                revisions=outcome.revisions,
                quarantined=outcome.quarantined,
            )
            return outcome

        outcome.warnings += self._check_calendar_gaps(run, instrument, fetch_start, fetch_end)

        # exactly one final per-symbol summary; totals include both passes,
        # the refresh_* fields break out the reconciliation share.
        logger.info(
            "prices.symbol_done",
            run_id=run.id,
            symbol=symbol,
            inserted=outcome.inserted,
            updated=outcome.updated,
            quarantined=outcome.quarantined,
            revisions=outcome.revisions,
            full_refresh=outcome.full_refresh,
            refresh_inserted=outcome.refresh_inserted,
            refresh_updated=outcome.refresh_updated,
            refresh_revisions=outcome.refresh_revisions,
        )
        return outcome

    # -- helpers -------------------------------------------------------------

    def _resolve(self, symbols: Sequence[str] | None) -> list[tuple[str, Instrument | None]]:
        if symbols is None:
            return [(i.symbol, i) for i in self._instruments.list_instruments() if i.is_active]
        return [(s, self._instruments.get_by_symbol(s)) for s in symbols]

    def _completed_session_end(self) -> date:
        """Last COMPLETED trading session (close + availability buffer, the
        same rule the update orchestrator resolves against) — the fetch
        window must never include an in-progress session. Falls back to
        wall-clock today only when no trading calendar exists (bootstrap
        before `mip calendar build`)."""
        # market.py is pure (stdlib + core exceptions); the update package
        # re-exports orchestration on init but creates no import cycle.
        from mip.update.market import now_eastern, resolve_market_date

        today = self._today()
        sessions = list(
            self._session.scalars(
                select(TradingDay.calendar_date)
                .where(TradingDay.calendar_date <= today)
                .order_by(TradingDay.calendar_date)
            )
        )
        if not sessions:
            return today
        now = self._now() if self._now is not None else now_eastern()
        return resolve_market_date(sessions, now, self._settings.market_close_buffer_minutes)

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
