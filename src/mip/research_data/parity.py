"""Two-track parity infrastructure (Stage 9).

Track 1 — Computation equivalence: feed IDENTICAL inputs to a legacy and a native
computation path; equivalent outputs (exact, or within a frozen tolerance) prove
the migration preserved the feature definition. Any unexplained mismatch fails.

Track 2 — Data-divergence characterization: the legacy vs native VALUES differ
because the underlying data differs (survivor yfinance vs clean vendor). Every
difference is attributed to a class and explained; an UNKNOWN class or an
``unexplained`` review status is material-divergence-until-explained and BLOCKS
promotion (see ``guardrails.assert_no_unexplained_divergence``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from mip.domain.enums import DivergenceClass, ParityReviewStatus
from mip.domain.models import DataDivergenceRecord, FeatureParityRecord

DEFAULT_TOLERANCE = 1e-9


# -- Track 1: computation equivalence ------------------------------------------


@dataclass(frozen=True)
class ParityCase:
    """One shared-input fixture fed to both computation paths."""

    feature_name: str
    fixture_key: str
    inputs: dict
    feature_version: str | None = None
    tolerance: float = DEFAULT_TOLERANCE


class ComputationParity:
    def __init__(self, session: Session) -> None:
        self._s = session

    def compare(
        self,
        case: ParityCase,
        legacy_fn: Callable[[dict], float | None],
        native_fn: Callable[[dict], float | None],
        *,
        calculation_version: str | None = None,
    ) -> FeatureParityRecord:
        legacy = legacy_fn(case.inputs)
        native = native_fn(case.inputs)
        if legacy is None or native is None:
            passed = legacy is None and native is None
            diff = None
        else:
            diff = abs(legacy - native)
            passed = diff <= case.tolerance
        rec = FeatureParityRecord(
            feature_name=case.feature_name,
            feature_version=case.feature_version,
            fixture_key=case.fixture_key,
            legacy_value=legacy,
            native_value=native,
            absolute_difference=diff,
            tolerance=case.tolerance,
            passed=passed,
            detail=None if passed else "computation mismatch beyond tolerance",
            calculation_version=calculation_version,
        )
        self._s.add(rec)
        self._s.flush()
        return rec

    def all_passed(self, feature_name: str | None = None) -> bool:
        from sqlalchemy import func, select

        stmt = (
            select(func.count())
            .select_from(FeatureParityRecord)
            .where(FeatureParityRecord.passed.is_(False))
        )
        if feature_name is not None:
            stmt = stmt.where(FeatureParityRecord.feature_name == feature_name)
        return int(self._s.scalar(stmt) or 0) == 0


# -- Track 2: data divergence characterization ---------------------------------


class DivergenceLedger:
    def __init__(self, session: Session) -> None:
        self._s = session

    def record(
        self,
        *,
        divergence_class: DivergenceClass,
        legacy_value: float | None,
        native_value: float | None,
        security_id: int | None = None,
        observation_date=None,
        feature_name: str | None = None,
        explanation: str | None = None,
        source_lineage: dict | None = None,
        review_status: ParityReviewStatus | None = None,
    ) -> DataDivergenceRecord:
        abs_diff = (
            abs(legacy_value - native_value)
            if legacy_value is not None and native_value is not None
            else None
        )
        rel_diff = (
            abs_diff / abs(legacy_value)
            if abs_diff is not None and legacy_value not in (None, 0)
            else None
        )
        # Default review status: UNKNOWN class or no explanation => unexplained.
        if review_status is None:
            if divergence_class is DivergenceClass.UNKNOWN or not explanation:
                review_status = ParityReviewStatus.UNEXPLAINED
            else:
                review_status = ParityReviewStatus.EXPLAINED
        rec = DataDivergenceRecord(
            security_id=security_id,
            observation_date=observation_date,
            feature_name=feature_name,
            legacy_value=legacy_value,
            native_value=native_value,
            absolute_difference=abs_diff,
            relative_difference=rel_diff,
            divergence_class=divergence_class,
            explanation=explanation,
            source_lineage=source_lineage,
            review_status=review_status,
        )
        self._s.add(rec)
        self._s.flush()
        return rec
