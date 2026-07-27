"""Point-in-time universe reconstruction — reproducible & survivorship-aware.

A build evaluates every security's eligibility as of each membership date using
only <=date information (via the PIT identifier/classification repository),
writes the included members, and records a reproducible manifest (definition +
data versions, counts, exclusion tallies, deterministic checksum) on a
`universe` ingestion_run. Re-running with the same frozen definition and data
version yields identical membership.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import IdentifierType, RunStatus, RunType, UniverseStatus
from mip.domain.models import (
    IngestionRun,
    SecurityIdentifierHistory,
    SecurityMaster,
    UniverseDefinition,
    UniverseMembership,
)
from mip.repositories.securities import _as_of
from mip.securities.universe_policy import UniversePolicy


class UniverseBuilder:
    def __init__(self, session: Session, data_version: str = "phase1-fixture") -> None:
        self._s = session
        self._data_version = data_version

    # -- definitions (versioned, immutable once frozen) --------------------

    def register(self, policy: UniversePolicy) -> UniverseDefinition:
        existing = self._s.scalar(
            select(UniverseDefinition).where(
                UniverseDefinition.name == policy.name,
                UniverseDefinition.version == policy.version,
            )
        )
        if existing is not None:
            if existing.status is UniverseStatus.FROZEN:
                return existing  # immutable — return as-is
            raise ConfigurationError(
                f"universe {policy.name} v{policy.version} exists in status "
                f"{existing.status.value}; bump the version to change rules"
            )
        definition = UniverseDefinition(
            name=policy.name,
            version=policy.version,
            description=policy.description,
            eligibility_rules_json=policy.to_rules_json(),
            source_requirements_json={
                "requires": ["security_master", "security_identifier_history"],
                "pending_phase2": list(policy.pending_filters),
            },
            status=UniverseStatus.FROZEN,
            frozen_at=datetime.now(UTC),
        )
        self._s.add(definition)
        self._s.flush()
        return definition

    # -- build ------------------------------------------------------------

    def build(
        self, policy: UniversePolicy, membership_dates: list[date]
    ) -> tuple[IngestionRun, dict]:
        definition = self.register(policy)
        run = IngestionRun(
            run_type=RunType.UNIVERSE,
            provider="universe_builder",
            scope=f"{policy.name} v{policy.version}",
            status=RunStatus.RUNNING,
        )
        self._s.add(run)
        self._s.flush()

        securities = list(
            self._s.scalars(select(SecurityMaster).order_by(SecurityMaster.security_id))
        )
        included_keys: list[tuple[str, int]] = []
        excluded: Counter[str] = Counter()
        included_count = 0

        for as_of in sorted(membership_dates):
            for sec in securities:
                exchange, has_listing = self._pit_listing(sec.security_id, as_of)
                ok, reason = policy.eligibility(
                    security_type=sec.security_type,
                    first_trade_date=sec.first_trade_date,
                    delisting_date=sec.delisting_date,
                    exchange=exchange,
                    has_listing_as_of=has_listing,
                    as_of=as_of,
                )
                if not ok:
                    excluded[reason or "excluded"] += 1
                    continue
                self._write_member(run, definition, sec, as_of, exchange)
                included_keys.append((as_of.isoformat(), sec.security_id))
                included_count += 1

        checksum = hashlib.sha256(
            "|".join(f"{d}:{sid}" for d, sid in sorted(included_keys)).encode()
        ).hexdigest()
        manifest = {
            "universe_definition_id": definition.universe_definition_id,
            "definition_version": definition.version,
            "data_version": self._data_version,
            "membership_dates": [d.isoformat() for d in sorted(membership_dates)],
            "input_securities": len(securities),
            "included_members": included_count,
            "excluded_by_reason": dict(excluded),
            "checksum": checksum,
        }
        run.completed_at = datetime.now(UTC)
        run.status = RunStatus.SUCCESS
        run.rows_inserted = included_count
        run.error_detail = manifest
        self._s.flush()
        return run, manifest

    def _pit_listing(self, security_id: int, as_of: date) -> tuple[str | None, bool]:
        """The security's exchange as-of (from its ticker identifier valid that
        day) and whether it had ANY listing on `as_of`."""
        row = self._s.scalar(
            select(SecurityIdentifierHistory).where(
                SecurityIdentifierHistory.security_id == security_id,
                SecurityIdentifierHistory.identifier_type == IdentifierType.TICKER,
                _as_of(
                    SecurityIdentifierHistory.valid_from,
                    SecurityIdentifierHistory.valid_to,
                    as_of,
                ),
            )
        )
        if row is None:
            return None, False
        return row.exchange, True

    def _write_member(self, run, definition, sec, as_of, exchange) -> None:
        existing = self._s.get(
            UniverseMembership, (definition.universe_definition_id, sec.security_id, as_of)
        )
        if existing is None:
            self._s.add(
                UniverseMembership(
                    universe_definition_id=definition.universe_definition_id,
                    security_id=sec.security_id,
                    membership_date=as_of,
                    included_flag=True,
                    exclusion_reason=None,
                    exchange=exchange,
                    security_type=sec.security_type,
                    source="universe_builder",
                    ingestion_run_id=run.id,
                    data_version=self._data_version,
                )
            )
        else:
            existing.included_flag = True
            existing.exchange = exchange
            existing.security_type = sec.security_type
            existing.ingestion_run_id = run.id
            existing.data_version = self._data_version
