"""Execution-level experiment provenance (Stage 6).

The definition-level registry (``mip.research.experiments.registry``) says WHAT an
experiment is. This records that it RAN: one immutable ``experiment_run`` bound to
its exact inputs (identity world, signal/feature/outcome/universe/data versions,
snapshot + checksum, code sha) plus metrics and a decision — so every research
result traces to one execution record. Runs are auto-numbered per experiment.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mip.domain.enums import ExperimentDecision, ExperimentRunStatus, IdentityWorld
from mip.domain.models import (
    ExperimentRun,
    ExperimentRunDecision,
    ExperimentRunMetric,
    ResearchDatasetSnapshot,
)
from mip.research_data.guardrails import IntegrityStamp, guard_stamp


class ExperimentProvenance:
    def __init__(self, session: Session) -> None:
        self._s = session

    def start_run(
        self,
        *,
        experiment_id: str,
        stamp: IntegrityStamp,
        snapshot: ResearchDatasetSnapshot | None = None,
        signal_version: str | None = None,
        feature_version: str | None = None,
        outcome_version: str | None = None,
        configuration: dict | None = None,
        pre_registration: dict | None = None,
        kill_criteria: dict | None = None,
    ) -> ExperimentRun:
        """Open an immutable run record. The integrity stamp is validated up front
        (complete + native outcomes) so a run cannot be created under-provenanced."""
        guard_stamp(stamp)
        next_number = (
            self._s.scalar(
                select(func.coalesce(func.max(ExperimentRun.run_number), 0)).where(
                    ExperimentRun.experiment_id == experiment_id
                )
            )
            or 0
        ) + 1
        run = ExperimentRun(
            experiment_id=experiment_id,
            run_number=next_number,
            status=ExperimentRunStatus.RUNNING,
            identity_world=stamp.identity_world,
            signal_version=signal_version,
            feature_version=feature_version or stamp.feature_version,
            outcome_version=outcome_version,
            universe_version=stamp.universe_version,
            snapshot_id=snapshot.snapshot_id if snapshot else None,
            snapshot_checksum=stamp.snapshot_checksum,
            data_version=stamp.data_version,
            code_sha=stamp.code_sha,
            configuration_json=configuration,
            pre_registration_json=pre_registration,
            kill_criteria_json=kill_criteria,
        )
        self._s.add(run)
        self._s.flush()
        return run

    def record_metric(
        self,
        run: ExperimentRun,
        *,
        metric_name: str,
        value: float | None,
        horizon: str | None = None,
        segment: str | None = None,
        confidence_lower: float | None = None,
        confidence_upper: float | None = None,
        sample_size: int | None = None,
        effective_sample_size: float | None = None,
        calculation_version: str | None = None,
    ) -> ExperimentRunMetric:
        m = ExperimentRunMetric(
            experiment_run_id=run.experiment_run_id,
            metric_name=metric_name,
            horizon=horizon,
            segment=segment,
            value=value,
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            sample_size=sample_size,
            effective_sample_size=effective_sample_size,
            calculation_version=calculation_version,
        )
        self._s.add(m)
        self._s.flush()
        return m

    def complete_run(
        self, run: ExperimentRun, *, status: ExperimentRunStatus = ExperimentRunStatus.COMPLETED
    ) -> None:
        run.status = status
        run.completed_at = datetime.now(UTC)
        self._s.flush()

    def fail_run(self, run: ExperimentRun, *, error: dict) -> None:
        run.status = ExperimentRunStatus.FAILED
        run.completed_at = datetime.now(UTC)
        run.error_detail = error
        self._s.flush()

    def record_decision(
        self,
        run: ExperimentRun,
        *,
        decision: ExperimentDecision,
        reason: str | None = None,
        gate_results: dict | None = None,
        reviewer: str | None = None,
        knowledge_update_reference: str | None = None,
    ) -> ExperimentRunDecision:
        existing = self._s.get(ExperimentRunDecision, run.experiment_run_id)
        if existing is None:
            existing = ExperimentRunDecision(
                experiment_run_id=run.experiment_run_id, decision=decision
            )
            self._s.add(existing)
        existing.decision = decision
        existing.decision_reason = reason
        existing.promotion_gate_results_json = gate_results
        existing.reviewer = reviewer
        existing.knowledge_update_reference = knowledge_update_reference
        existing.reviewed_at = datetime.now(UTC)
        self._s.flush()
        return existing

    # -- read helpers --

    def runs_for(self, experiment_id: str) -> list[ExperimentRun]:
        return list(
            self._s.scalars(
                select(ExperimentRun)
                .where(ExperimentRun.experiment_id == experiment_id)
                .order_by(ExperimentRun.run_number)
            )
        )

    def stamp_from_native(
        self,
        snapshot: ResearchDatasetSnapshot,
        *,
        calculation_version: str,
        code_sha: str | None = None,
    ) -> IntegrityStamp:
        """Build a native integrity stamp from a frozen snapshot."""
        return IntegrityStamp(
            identity_world=IdentityWorld.NATIVE_SECURITY,
            data_version=snapshot.data_version,
            snapshot_checksum=snapshot.snapshot_checksum or "",
            calculation_version=calculation_version,
            universe_version=snapshot.universe_version,
            code_sha=code_sha,
        )
