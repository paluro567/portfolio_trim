"""Hard research-integrity guardrails (Stages 7 & 8).

These make scientifically invalid combinations *structurally impossible* rather
than merely discouraged. Every function fails LOUDLY (raises) — never a warning,
never a silent pass. The identity world is always taken from an explicit stamp,
never inferred from a table name.

The critical prohibited combination is: legacy ``feature_store_daily`` features
joined to native ``research_observation`` / ``forward_return`` outcomes. That is
``MixedIdentityWorldError`` and it is unconditional.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mip.core.exceptions import MIPError
from mip.domain.enums import DivergenceClass, IdentityWorld, ParityReviewStatus
from mip.domain.models import DataDivergenceRecord


class ResearchIntegrityError(MIPError):
    """Base for every structural research-integrity violation."""


class MixedIdentityWorldError(ResearchIntegrityError):
    """A legacy artifact was combined with a native one (the core prohibition)."""


class MissingIntegrityStampError(ResearchIntegrityError):
    """A required identity-world / version stamp is absent."""


class SnapshotChecksumMismatchError(ResearchIntegrityError):
    """Two artifacts in one experiment carry different snapshot checksums."""


class UniverseVersionMismatchError(ResearchIntegrityError):
    """Universe versions differ across artifacts expected to align."""


class DataVersionMismatchError(ResearchIntegrityError):
    """Data versions differ with no explicit reconciliation policy."""


class LegacyTickerJoinError(ResearchIntegrityError):
    """A legacy ticker join was attempted without point-in-time resolution."""


class UnexplainedDivergenceError(ResearchIntegrityError):
    """Material legacy-vs-native divergence remains unexplained; promotion blocked."""


@dataclass(frozen=True)
class IntegrityStamp:
    """The explicit provenance every research artifact must carry or inherit."""

    identity_world: IdentityWorld
    data_version: str
    snapshot_checksum: str
    calculation_version: str
    universe_version: str | None = None
    feature_version: str | None = None
    code_sha: str | None = None

    def require_complete(self) -> None:
        missing = [
            n
            for n in ("identity_world", "data_version", "snapshot_checksum", "calculation_version")
            if not getattr(self, n)
        ]
        if missing:
            raise MissingIntegrityStampError(
                f"research artifact is missing required integrity stamps: {missing}"
            )


# -- the critical join guardrail -----------------------------------------------


def assert_worlds_joinable(feature_world: IdentityWorld, outcome_world: IdentityWorld) -> None:
    """Reject any legacy/native mix. Feature and outcome must be the SAME world;
    a legacy feature against a native outcome is the exact scientifically-invalid
    combination Phase 2A exists to prevent."""
    if feature_world != outcome_world:
        raise MixedIdentityWorldError(
            f"cannot join {feature_world.value} features to {outcome_world.value} outcomes: "
            "survivor-biased legacy features may never be evaluated against survivorship-clean "
            "native outcomes (docs/PHASE3_IDENTITY_MIGRATION.md). Recompute features natively "
            "or restrict the study to one identity world."
        )


def assert_native_outcomes(outcome_world: IdentityWorld) -> None:
    if outcome_world is not IdentityWorld.NATIVE_SECURITY:
        raise MixedIdentityWorldError(
            f"outcome_world={outcome_world.value}: native research requires "
            "survivorship-clean native_security outcomes."
        )


def assert_no_legacy_ticker_join(*, used_pit_resolution: bool, context: str = "") -> None:
    """A legacy ticker may only reach a security via point-in-time bridge
    resolution — never a raw current-symbol equality join."""
    if not used_pit_resolution:
        suffix = f" ({context})" if context else ""
        raise LegacyTickerJoinError(
            f"legacy ticker join without point-in-time resolution{suffix}: resolve "
            "instrument_id/ticker through instrument_security_map AS OF the date."
        )


# -- version / checksum coherence within one experiment ------------------------


def assert_single_snapshot(checksums: Iterable[str | None]) -> None:
    distinct = {c for c in checksums if c is not None}
    if len(distinct) > 1:
        raise SnapshotChecksumMismatchError(
            f"an experiment run mixes {len(distinct)} snapshot checksums: {sorted(distinct)}; "
            "every observation in a run must come from one frozen snapshot."
        )


def assert_universe_versions_match(versions: Iterable[str | None]) -> None:
    distinct = {v for v in versions if v is not None}
    if len(distinct) > 1:
        raise UniverseVersionMismatchError(
            f"mismatched universe versions in one run: {sorted(distinct)}."
        )


def assert_data_versions_reconciled(
    versions: Iterable[str | None], *, reconciliation_policy: str | None = None
) -> None:
    distinct = {v for v in versions if v is not None}
    if len(distinct) > 1 and not reconciliation_policy:
        raise DataVersionMismatchError(
            f"mismatched data versions {sorted(distinct)} with no explicit reconciliation policy."
        )


def guard_stamp(stamp: IntegrityStamp) -> None:
    """Full single-artifact guard: complete stamps + native outcomes."""
    stamp.require_complete()
    assert_native_outcomes(stamp.identity_world)


# -- promotion gate: unexplained divergence blocks -----------------------------


def count_blocking_divergences(session: Session, *, feature_name: str | None = None) -> int:
    """Rows that BLOCK promotion: review_status=unexplained OR class=unknown and
    not yet accepted."""
    stmt = (
        select(func.count())
        .select_from(DataDivergenceRecord)
        .where(
            (DataDivergenceRecord.review_status == ParityReviewStatus.UNEXPLAINED)
            | (
                (DataDivergenceRecord.divergence_class == DivergenceClass.UNKNOWN)
                & (DataDivergenceRecord.review_status != ParityReviewStatus.ACCEPTED)
            )
        )
    )
    if feature_name is not None:
        stmt = stmt.where(DataDivergenceRecord.feature_name == feature_name)
    return int(session.scalar(stmt) or 0)


def assert_no_unexplained_divergence(session: Session, *, feature_name: str | None = None) -> None:
    n = count_blocking_divergences(session, feature_name=feature_name)
    if n:
        raise UnexplainedDivergenceError(
            f"{n} material data-divergence record(s) remain unexplained/unknown; "
            "promotion is blocked until each is classified and explained."
        )
