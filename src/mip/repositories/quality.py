"""Repository for the ops aggregate: data_quality_issues and data_revisions.

Issue de-duplication: an OPEN issue with the same (entity_type, entity_key,
rule) is not re-inserted on the next run; an ACCEPTED one suppresses the
rule entirely (enforced upstream in validation via accepted_row_rules)."""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.domain.enums import IssueSeverity, IssueStatus
from mip.domain.models import DataQualityIssue, DataRevision


class QualityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_issue(
        self,
        run_id: int,
        entity_type: str,
        entity_key: str,
        rule: str,
        severity: IssueSeverity,
        observed_value: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> DataQualityIssue:
        existing = self._session.scalar(
            select(DataQualityIssue).where(
                DataQualityIssue.entity_type == entity_type,
                DataQualityIssue.entity_key == entity_key,
                DataQualityIssue.rule == rule,
                DataQualityIssue.status == IssueStatus.OPEN,
            )
        )
        if existing is not None:
            return existing  # already ledgered and still unresolved
        issue = DataQualityIssue(
            ingestion_run_id=run_id,
            entity_type=entity_type,
            entity_key=entity_key,
            rule=rule,
            severity=severity,
            observed_value=observed_value,
            details=details,
        )
        self._session.add(issue)
        self._session.flush()
        return issue

    def accepted_row_rules(self, entity_type: str, key_prefix: str) -> set[tuple[str, date]]:
        """(rule, date) pairs a human has ACCEPTED for e.g. 'AAPL/' keys."""
        rows = self._session.execute(
            select(DataQualityIssue.rule, DataQualityIssue.entity_key).where(
                DataQualityIssue.entity_type == entity_type,
                DataQualityIssue.entity_key.like(key_prefix + "%"),
                DataQualityIssue.status == IssueStatus.ACCEPTED,
            )
        )
        accepted: set[tuple[str, date]] = set()
        for rule, entity_key in rows:
            _, _, day = entity_key.rpartition("/")
            try:
                accepted.add((rule, date.fromisoformat(day)))
            except ValueError:
                continue  # non-row-level key (e.g. range keys); not suppressible by date
        return accepted

    def list_issues(
        self, status: IssueStatus | None = IssueStatus.OPEN, limit: int = 50
    ) -> list[DataQualityIssue]:
        stmt = select(DataQualityIssue).order_by(DataQualityIssue.created_at.desc()).limit(limit)
        if status is not None:
            stmt = stmt.where(DataQualityIssue.status == status)
        return list(self._session.scalars(stmt))

    def set_status(self, issue_id: int, status: IssueStatus) -> DataQualityIssue | None:
        issue = self._session.get(DataQualityIssue, issue_id)
        if issue is not None:
            issue.status = status
            self._session.flush()
        return issue

    # -- revisions --------------------------------------------------------

    def record_revision(
        self,
        table_name: str,
        entity_key: str,
        field: str,
        old_value: str | None,
        new_value: str | None,
        run_id: int,
    ) -> None:
        self._session.add(
            DataRevision(
                table_name=table_name,
                entity_key=entity_key,
                field=field,
                old_value=old_value,
                new_value=new_value,
                ingestion_run_id=run_id,
            )
        )
