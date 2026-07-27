"""First-class point-in-time identity bridge: legacy ``instrument_id`` <->
native ``security_id`` (Stage 2, PHASE3_IDENTITY_MIGRATION.md).

This is the load-bearing seam between the two identity worlds. Every crossing is
explicit, as-of-dated, and lineage-stamped. Rules:
  * no two ACTIVE mappings for one instrument_id may overlap in time;
  * ticker equality ALONE never establishes identity (a ``pit_ticker`` mapping is
    recorded but must be reviewed — it is not trusted for resolution here unless
    explicitly promoted);
  * an ambiguous mapping (overlaps an existing ACTIVE row pointing elsewhere) is
    quarantined, never auto-merged;
  * one instrument may map to DIFFERENT securities across NON-overlapping periods
    (legitimate ticker reuse), which is allowed;
  * a manual override is explicit, audited, and supersedes prior rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from mip.domain.enums import (
    IssueSeverity,
    MappingMethod,
    MappingStatus,
    RunStatus,
    RunType,
)
from mip.domain.models import (
    DataQualityIssue,
    IngestionRun,
    InstrumentSecurityMap,
)

_FAR = date(9999, 12, 31)


def _overlaps(a_from, a_to, b_from, b_to) -> bool:
    a_to = a_to or _FAR
    b_to = b_to or _FAR
    return a_from <= b_to and b_from <= a_to


@dataclass(frozen=True)
class SourceMapping:
    instrument_id: int
    security_id: int
    valid_from: date
    valid_to: date | None = None
    mapping_reason: str | None = None
    mapping_method: MappingMethod = MappingMethod.EXACT_SOURCE_ID
    confidence: float = 1.0
    source_record_id: str | None = None


@dataclass
class BridgeStats:
    created: int = 0
    quarantined: int = 0
    superseded: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "created": self.created,
            "quarantined": self.quarantined,
            "superseded": self.superseded,
            "reasons": self.reasons,
        }


class BridgeRepository:
    """Point-in-time bridge queries. Resolution uses ACTIVE mappings only."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def _as_of(self, as_of: date):
        return and_(
            InstrumentSecurityMap.status == MappingStatus.ACTIVE,
            InstrumentSecurityMap.valid_from <= as_of,
            or_(
                InstrumentSecurityMap.valid_to.is_(None),
                InstrumentSecurityMap.valid_to >= as_of,
            ),
        )

    def resolve_instrument(self, instrument_id: int, as_of: date) -> int | None:
        """The security_id this legacy instrument maps to AS OF `as_of`."""
        return self._s.scalar(
            select(InstrumentSecurityMap.security_id).where(
                InstrumentSecurityMap.instrument_id == instrument_id,
                self._as_of(as_of),
            )
        )

    def resolve_security(self, security_id: int, as_of: date) -> list[int]:
        """Legacy instruments compatible with this security AS OF `as_of`."""
        return list(
            self._s.scalars(
                select(InstrumentSecurityMap.instrument_id).where(
                    InstrumentSecurityMap.security_id == security_id,
                    self._as_of(as_of),
                )
            )
        )

    def validate_coverage(self, instrument_ids: list[int], as_of: date) -> list[int]:
        """Instrument ids with NO active mapping as of `as_of` (missing coverage)."""
        return [i for i in instrument_ids if self.resolve_instrument(i, as_of) is None]

    def list_quarantined(self) -> list[InstrumentSecurityMap]:
        return list(
            self._s.scalars(
                select(InstrumentSecurityMap).where(
                    InstrumentSecurityMap.status == MappingStatus.QUARANTINED
                )
            )
        )

    def overlap_violations(self) -> list[tuple[int, int, int]]:
        """(instrument_id, map_id_a, map_id_b) pairs of ACTIVE rows that overlap
        in time for the same instrument — should be empty after ingest."""
        rows = list(
            self._s.scalars(
                select(InstrumentSecurityMap)
                .where(InstrumentSecurityMap.status == MappingStatus.ACTIVE)
                .order_by(InstrumentSecurityMap.instrument_id, InstrumentSecurityMap.valid_from)
            )
        )
        by_instr: dict[int, list[InstrumentSecurityMap]] = {}
        for r in rows:
            by_instr.setdefault(r.instrument_id, []).append(r)
        out: list[tuple[int, int, int]] = []
        for instr, group in by_instr.items():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    if _overlaps(
                        group[i].valid_from,
                        group[i].valid_to,
                        group[j].valid_from,
                        group[j].valid_to,
                    ):
                        out.append((instr, group[i].map_id, group[j].map_id))
        return out


class BridgeIngestor:
    """Writes bridge rows with overlap detection + quarantine."""

    def __init__(self, session: Session) -> None:
        self._s = session
        self._repo = BridgeRepository(session)

    def ingest(
        self, mappings: list[SourceMapping], *, source: str, data_version: str
    ) -> tuple[IngestionRun, BridgeStats]:
        run = IngestionRun(
            run_type=RunType.BRIDGE,
            provider=source,
            scope=data_version,
            status=RunStatus.RUNNING,
        )
        self._s.add(run)
        self._s.flush()
        stats = BridgeStats()
        for m in mappings:
            self._ingest_one(run, source, data_version, m, stats)
        run.completed_at = datetime.now(UTC)
        run.status = RunStatus.PARTIAL if stats.quarantined else RunStatus.SUCCESS
        run.rows_inserted = stats.created
        run.error_detail = stats.to_dict()
        self._s.flush()
        return run, stats

    def _active_for_instrument(self, instrument_id: int) -> list[InstrumentSecurityMap]:
        return list(
            self._s.scalars(
                select(InstrumentSecurityMap).where(
                    InstrumentSecurityMap.instrument_id == instrument_id,
                    InstrumentSecurityMap.status == MappingStatus.ACTIVE,
                )
            )
        )

    def _quarantine(self, run, m: SourceMapping, rule: str, detail: dict, stats) -> None:
        self._s.add(
            InstrumentSecurityMap(
                instrument_id=m.instrument_id,
                security_id=m.security_id,
                valid_from=m.valid_from,
                valid_to=m.valid_to,
                mapping_reason=m.mapping_reason,
                mapping_method=m.mapping_method,
                status=MappingStatus.QUARANTINED,
                confidence=m.confidence,
                source=run.provider,
                source_record_id=m.source_record_id,
                ingestion_run_id=run.id,
                data_version=run.scope,
            )
        )
        self._s.add(
            DataQualityIssue(
                ingestion_run_id=run.id,
                entity_type="instrument_security_map",
                entity_key=f"instrument={m.instrument_id}/security={m.security_id}",
                rule=rule,
                severity=IssueSeverity.ERROR,
                details=detail,
            )
        )
        stats.quarantined += 1
        stats.reasons.append(f"instrument={m.instrument_id}: {rule}")

    def _ingest_one(self, run, source, data_version, m: SourceMapping, stats) -> None:
        # A manual override is explicit: it supersedes overlapping active rows.
        if m.mapping_method is MappingMethod.MANUAL_OVERRIDE:
            for row in self._active_for_instrument(m.instrument_id):
                if _overlaps(m.valid_from, m.valid_to, row.valid_from, row.valid_to):
                    row.status = MappingStatus.SUPERSEDED
                    row.updated_at = datetime.now(UTC)
                    stats.superseded += 1
            self._add_active(run, m, stats)
            return

        # Ambiguity: overlaps an existing ACTIVE mapping to a DIFFERENT security.
        for row in self._active_for_instrument(m.instrument_id):
            if _overlaps(m.valid_from, m.valid_to, row.valid_from, row.valid_to):
                if row.security_id != m.security_id:
                    self._quarantine(
                        run,
                        m,
                        "ambiguous_mapping",
                        {
                            "conflict_map_id": row.map_id,
                            "existing_security_id": row.security_id,
                            "new_security_id": m.security_id,
                            "overlap": [str(m.valid_from), str(m.valid_to)],
                        },
                        stats,
                    )
                    return
                # same security, overlapping interval -> idempotent, skip duplicate
                return
        self._add_active(run, m, stats)

    def _add_active(self, run, m: SourceMapping, stats) -> None:
        self._s.add(
            InstrumentSecurityMap(
                instrument_id=m.instrument_id,
                security_id=m.security_id,
                valid_from=m.valid_from,
                valid_to=m.valid_to,
                mapping_reason=m.mapping_reason,
                mapping_method=m.mapping_method,
                status=MappingStatus.ACTIVE,
                confidence=m.confidence,
                source=run.provider,
                source_record_id=m.source_record_id,
                ingestion_run_id=run.id,
                data_version=run.scope,
            )
        )
        self._s.flush()
        stats.created += 1
