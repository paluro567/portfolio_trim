"""Security-master ingestion: canonical DTOs -> identity-resolved rows.

Identity resolution is deterministic and NEVER merges on ticker equality:
  - a record without a permanent id (source_security_id) is quarantined;
  - (source, source_security_id) is the idempotency + resolution anchor —
    re-ingesting the same snapshot updates in place, no duplicates;
  - a permanent identifier (CUSIP/ISIN/FIGI) already held by a DIFFERENT
    security over an overlapping interval is a conflict -> quarantined;
  - otherwise a new security_id is minted.

Every row carries source + ingestion_run_id + data_version lineage. Delisted /
inactive securities are preserved, never dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.domain.enums import (
    IdentifierType,
    IssueSeverity,
    RunStatus,
    RunType,
)
from mip.domain.models import (
    DataQualityIssue,
    DelistingEvent,
    HistoricalClassification,
    IngestionRun,
    SecurityIdentifierHistory,
    SecurityLifecycleEvent,
    SecurityMaster,
)
from mip.securities.source import SecuritySource, SourceSecurity

_PERMANENT = (IdentifierType.CUSIP, IdentifierType.ISIN, IdentifierType.FIGI)
_FAR = date(9999, 12, 31)


@dataclass
class IngestStats:
    created: int = 0
    updated: int = 0
    quarantined: int = 0
    identifiers: int = 0
    lifecycle_events: int = 0
    delistings: int = 0
    classifications: int = 0
    quarantine_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "created": self.created,
            "updated": self.updated,
            "quarantined": self.quarantined,
            "identifiers": self.identifiers,
            "lifecycle_events": self.lifecycle_events,
            "delistings": self.delistings,
            "classifications": self.classifications,
            "quarantine_reasons": self.quarantine_reasons,
        }


def _overlaps(a_from, a_to, b_from, b_to) -> bool:
    a_to = a_to or _FAR
    b_to = b_to or _FAR
    return a_from <= b_to and b_from <= a_to


class SecurityMasterIngestor:
    def __init__(self, session: Session) -> None:
        self._s = session

    def ingest(self, source: SecuritySource) -> tuple[IngestionRun, IngestStats]:
        run = IngestionRun(
            run_type=RunType.SECURITIES,
            provider=source.name,
            scope=source.data_version,
            status=RunStatus.RUNNING,
        )
        self._s.add(run)
        self._s.flush()
        stats = IngestStats()
        for src in source.securities():
            self._ingest_one(run, source, src, stats)
        run.completed_at = datetime.now(UTC)
        run.status = RunStatus.PARTIAL if stats.quarantined else RunStatus.SUCCESS
        run.rows_inserted = stats.created
        run.rows_updated = stats.updated
        run.error_detail = stats.to_dict()
        self._s.flush()
        return run, stats

    # -- resolution --------------------------------------------------------

    def _quarantine(self, run: IngestionRun, key: str, rule: str, detail: dict, stats) -> None:
        self._s.add(
            DataQualityIssue(
                ingestion_run_id=run.id,
                entity_type="security",
                entity_key=key,
                rule=rule,
                severity=IssueSeverity.ERROR,
                details=detail,
            )
        )
        stats.quarantined += 1
        stats.quarantine_reasons.append(f"{key}: {rule}")

    def _existing(self, source: str, source_security_id: str) -> SecurityMaster | None:
        return self._s.scalar(
            select(SecurityMaster).where(
                SecurityMaster.source == source,
                SecurityMaster.source_security_id == source_security_id,
            )
        )

    def _identifier_conflict(self, src: SourceSecurity, own_id: int | None) -> str | None:
        """A permanent identifier already assigned to a DIFFERENT security over
        an overlapping interval — ambiguous identity, never auto-merged."""
        for ident in src.identifiers:
            if ident.identifier_type not in _PERMANENT:
                continue
            rows = self._s.execute(
                select(SecurityIdentifierHistory).where(
                    SecurityIdentifierHistory.identifier_type == ident.identifier_type,
                    SecurityIdentifierHistory.identifier_value == ident.identifier_value,
                )
            ).scalars()
            for row in rows:
                if row.security_id == own_id:
                    continue
                if _overlaps(ident.valid_from, ident.valid_to, row.valid_from, row.valid_to):
                    return (
                        f"{ident.identifier_type.value}={ident.identifier_value} also held by "
                        f"security_id={row.security_id} over an overlapping interval"
                    )
        return None

    def _ingest_one(self, run, source, src: SourceSecurity, stats) -> None:
        if not src.source_security_id:
            self._quarantine(run, "<missing>", "missing_permanent_id", {"name": src.name}, stats)
            return
        existing = self._existing(source.name, src.source_security_id)
        own_id = existing.security_id if existing else None
        conflict = self._identifier_conflict(src, own_id)
        if conflict:
            self._quarantine(
                run, src.source_security_id, "ambiguous_identity", {"conflict": conflict}, stats
            )
            return

        master = existing or SecurityMaster(
            source=source.name, source_security_id=src.source_security_id
        )
        master.security_type = src.security_type
        master.issuer_id = None
        master.share_class = src.share_class
        master.country = src.country
        master.currency = src.currency
        master.primary_exchange = src.primary_exchange
        master.first_trade_date = src.first_trade_date
        master.last_trade_date = src.last_trade_date
        master.active_flag = src.active
        master.delisted_flag = src.delisted
        master.delisting_date = src.delisting_date
        master.delisting_reason = src.delisting_reason
        master.ingestion_run_id = run.id
        master.data_version = source.data_version
        master.updated_at = datetime.now(UTC)
        if existing is None:
            self._s.add(master)
            stats.created += 1
        else:
            stats.updated += 1
        self._s.flush()  # assign security_id
        sid = master.security_id

        self._upsert_identifiers(run, source, src, sid, stats)
        self._upsert_lifecycle(run, source, src, sid, stats)
        self._upsert_delisting(run, source, src, sid, stats)
        self._upsert_classifications(run, source, src, sid, stats)

    # -- children (idempotent upserts by natural key) ----------------------

    def _upsert_identifiers(self, run, source, src, sid, stats) -> None:
        for ident in src.identifiers:
            row = self._s.get(
                SecurityIdentifierHistory, (sid, ident.identifier_type, ident.valid_from)
            )
            if row is None:
                self._s.add(
                    SecurityIdentifierHistory(
                        security_id=sid,
                        identifier_type=ident.identifier_type,
                        valid_from=ident.valid_from,
                        identifier_value=ident.identifier_value,
                        exchange=ident.exchange,
                        valid_to=ident.valid_to,
                        is_primary=ident.is_primary,
                        source=source.name,
                        ingestion_run_id=run.id,
                        data_version=source.data_version,
                    )
                )
                stats.identifiers += 1
            else:
                row.identifier_value = ident.identifier_value
                row.exchange = ident.exchange
                row.valid_to = ident.valid_to
                row.is_primary = ident.is_primary
                row.ingestion_run_id = run.id
                row.data_version = source.data_version

    def _resolve_source_id(self, source_name: str, vendor_id: str | None) -> int | None:
        if not vendor_id:
            return None
        m = self._existing(source_name, vendor_id)
        return m.security_id if m else None

    def _upsert_lifecycle(self, run, source, src, sid, stats) -> None:
        for ev in src.lifecycle_events:
            existing = self._s.scalar(
                select(SecurityLifecycleEvent).where(
                    SecurityLifecycleEvent.security_id == sid,
                    SecurityLifecycleEvent.event_type == ev.event_type,
                    SecurityLifecycleEvent.effective_date == ev.effective_date,
                )
            )
            successor = self._resolve_source_id(source.name, ev.successor_source_id)
            predecessor = self._resolve_source_id(source.name, ev.predecessor_source_id)
            if existing is None:
                self._s.add(
                    SecurityLifecycleEvent(
                        security_id=sid,
                        event_type=ev.event_type,
                        effective_date=ev.effective_date,
                        announcement_date=ev.announcement_date,
                        successor_security_id=successor,
                        predecessor_security_id=predecessor,
                        details=ev.details,
                        source=source.name,
                        ingestion_run_id=run.id,
                        data_version=source.data_version,
                    )
                )
                stats.lifecycle_events += 1
            else:
                existing.announcement_date = ev.announcement_date
                existing.successor_security_id = successor
                existing.predecessor_security_id = predecessor
                existing.details = ev.details
                existing.ingestion_run_id = run.id
                existing.data_version = source.data_version

    def _upsert_delisting(self, run, source, src, sid, stats) -> None:
        if src.delisting is None:
            return
        row = self._s.get(DelistingEvent, sid)
        successor = self._resolve_source_id(source.name, src.delisting.successor_source_id)
        if row is None:
            self._s.add(
                DelistingEvent(
                    security_id=sid,
                    delisting_date=src.delisting.delisting_date,
                    delisting_code=src.delisting.delisting_code,
                    delisting_reason=src.delisting.delisting_reason,
                    successor_security_id=successor,
                    source=source.name,
                    ingestion_run_id=run.id,
                    data_version=source.data_version,
                )
            )
            stats.delistings += 1
        else:
            row.delisting_date = src.delisting.delisting_date
            row.delisting_code = src.delisting.delisting_code
            row.delisting_reason = src.delisting.delisting_reason
            row.successor_security_id = successor
            row.ingestion_run_id = run.id
            row.data_version = source.data_version

    def _upsert_classifications(self, run, source, src, sid, stats) -> None:
        for cl in src.classifications:
            existing = self._s.scalar(
                select(HistoricalClassification).where(
                    HistoricalClassification.security_id == sid,
                    HistoricalClassification.classification_scheme == cl.scheme,
                    HistoricalClassification.valid_from == cl.valid_from,
                )
            )
            if existing is None:
                self._s.add(
                    HistoricalClassification(
                        security_id=sid,
                        classification_scheme=cl.scheme,
                        sector=cl.sector,
                        industry_group=cl.industry_group,
                        industry=cl.industry,
                        sub_industry=cl.sub_industry,
                        valid_from=cl.valid_from,
                        valid_to=cl.valid_to,
                        source=source.name,
                        ingestion_run_id=run.id,
                        data_version=source.data_version,
                    )
                )
                stats.classifications += 1
            else:
                existing.sector = cl.sector
                existing.industry_group = cl.industry_group
                existing.industry = cl.industry
                existing.sub_industry = cl.sub_industry
                existing.valid_to = cl.valid_to
                existing.ingestion_run_id = run.id
                existing.data_version = source.data_version
