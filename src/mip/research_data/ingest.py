"""Native outcome ingestion: canonical DTOs -> security_id-keyed rows.

Prices, market snapshots, benchmark returns, and terminal outcomes are resolved
to the permanent ``security_id`` via the Phase-1 ``security_master`` natural key
(source, source_security_id) — NEVER via ticker. A bar whose vendor id has no
security_master record is quarantined (not silently dropped). Delisted/inactive
securities are ingested normally; their price history does not end silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.domain.enums import IssueSeverity, RunStatus, RunType, TerminalRule
from mip.domain.models import (
    BenchmarkReturnDaily,
    DataQualityIssue,
    IngestionRun,
    SecurityMarketSnapshot,
    SecurityMaster,
    SecurityPriceDaily,
    TerminalOutcome,
)
from mip.research_data.source import OutcomeSource

# A terminal event with an unknown/unresolved vendor outcome is NEVER assumed to
# be a total loss. These rules are treated as unresolved when no value is given.
_UNRESOLVED_RULES = {TerminalRule.UNKNOWN}


@dataclass
class OutcomeIngestStats:
    prices: int = 0
    market_snapshots: int = 0
    benchmarks: int = 0
    terminals: int = 0
    terminals_unresolved: int = 0
    quarantined: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "prices": self.prices,
            "market_snapshots": self.market_snapshots,
            "benchmarks": self.benchmarks,
            "terminals": self.terminals,
            "terminals_unresolved": self.terminals_unresolved,
            "quarantined": self.quarantined,
            "reasons": self.reasons[:50],
        }


class OutcomeIngestor:
    def __init__(self, session: Session) -> None:
        self._s = session
        self._id_cache: dict[tuple[str, str], int | None] = {}

    def _resolve(self, source: str, vendor_id: str) -> int | None:
        key = (source, vendor_id)
        if key not in self._id_cache:
            self._id_cache[key] = self._s.scalar(
                select(SecurityMaster.security_id).where(
                    SecurityMaster.source == source,
                    SecurityMaster.source_security_id == vendor_id,
                )
            )
        return self._id_cache[key]

    def _quarantine(self, run, entity_type, key, rule, detail, stats) -> None:
        self._s.add(
            DataQualityIssue(
                ingestion_run_id=run.id,
                entity_type=entity_type,
                entity_key=key,
                rule=rule,
                severity=IssueSeverity.ERROR,
                details=detail,
            )
        )
        stats.quarantined += 1
        stats.reasons.append(f"{key}: {rule}")

    def ingest(self, source: OutcomeSource) -> tuple[IngestionRun, OutcomeIngestStats]:
        run = IngestionRun(
            run_type=RunType.RESEARCH_PRICES,
            provider=source.name,
            scope=source.data_version,
            status=RunStatus.RUNNING,
        )
        self._s.add(run)
        self._s.flush()
        stats = OutcomeIngestStats()

        for bar in source.prices():
            sid = self._resolve(source.name, bar.source_security_id)
            if sid is None:
                self._quarantine(
                    run, "price", bar.source_security_id, "unresolved_security", {}, stats
                )
                continue
            self._s.add(
                SecurityPriceDaily(
                    security_id=sid,
                    trade_date=bar.trade_date,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    adjusted_close=bar.adjusted_close,
                    volume=bar.volume,
                    total_return_factor=bar.total_return_factor,
                    split_factor=bar.split_factor,
                    dividend_amount=bar.dividend_amount,
                    currency=bar.currency,
                    exchange=bar.exchange,
                    source=source.name,
                    source_record_id=bar.source_record_id,
                    ingestion_run_id=run.id,
                    data_version=source.data_version,
                )
            )
            stats.prices += 1

        for ms in source.market_snapshots():
            sid = self._resolve(source.name, ms.source_security_id)
            if sid is None:
                self._quarantine(
                    run, "market_snapshot", ms.source_security_id, "unresolved_security", {}, stats
                )
                continue
            self._s.add(
                SecurityMarketSnapshot(
                    security_id=sid,
                    snapshot_date=ms.snapshot_date,
                    price=ms.price,
                    shares_outstanding=ms.shares_outstanding,
                    market_cap=ms.market_cap,
                    volume=ms.volume,
                    average_dollar_volume=ms.average_dollar_volume,
                    exchange=ms.exchange,
                    security_type=ms.security_type,
                    sector=ms.sector,
                    source=source.name,
                    ingestion_run_id=run.id,
                    data_version=source.data_version,
                )
            )
            stats.market_snapshots += 1

        for bm in source.benchmarks():
            self._s.add(
                BenchmarkReturnDaily(
                    benchmark_key=bm.benchmark_key,
                    kind=bm.kind,
                    trade_date=bm.trade_date,
                    total_return=bm.total_return,
                    source=source.name,
                    ingestion_run_id=run.id,
                    data_version=source.data_version,
                )
            )
            stats.benchmarks += 1

        for term in source.terminals():
            sid = self._resolve(source.name, term.source_security_id)
            if sid is None:
                self._quarantine(
                    run, "terminal", term.source_security_id, "unresolved_security", {}, stats
                )
                continue
            successor = (
                self._resolve(source.name, term.successor_source_id)
                if term.successor_source_id
                else None
            )
            unresolved = (not term.resolved) or (
                term.rule in _UNRESOLVED_RULES
                and term.terminal_return is None
                and term.terminal_value is None
            )
            if unresolved:
                stats.terminals_unresolved += 1
            existing = self._s.get(TerminalOutcome, sid)
            if existing is None:
                self._s.add(
                    TerminalOutcome(
                        security_id=sid,
                        event_date=term.event_date,
                        rule=term.rule,
                        terminal_return=term.terminal_return,
                        terminal_value=term.terminal_value,
                        cash_consideration=term.cash_consideration,
                        successor_security_id=successor,
                        resolved=not unresolved,
                        confidence=term.confidence,
                        source=source.name,
                        ingestion_run_id=run.id,
                        data_version=source.data_version,
                        calculation_version="terminal-v1",
                    )
                )
                stats.terminals += 1
            else:
                existing.event_date = term.event_date
                existing.rule = term.rule
                existing.terminal_return = term.terminal_return
                existing.terminal_value = term.terminal_value
                existing.cash_consideration = term.cash_consideration
                existing.successor_security_id = successor
                existing.resolved = not unresolved
                existing.confidence = term.confidence
                existing.ingestion_run_id = run.id
                existing.data_version = source.data_version

        run.completed_at = datetime.now(UTC)
        run.status = RunStatus.PARTIAL if stats.quarantined else RunStatus.SUCCESS
        run.rows_inserted = (
            stats.prices + stats.market_snapshots + stats.benchmarks + stats.terminals
        )
        run.error_detail = stats.to_dict()
        self._s.flush()
        return run, stats
