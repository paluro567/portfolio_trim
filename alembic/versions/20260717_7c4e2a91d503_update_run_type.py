"""allow run_type='update' — Daily Update Orchestrator audit runs.

Smallest possible amendment, exactly the portfolio_import precedent:
the orchestrator reuses ingestion_runs (scope = portfolio, archive_path
= report directory, JSONB detail = stage manifest); only the check
constraint needs the new value. Raw SQL for the swap — op.drop_constraint
re-applies the naming convention and would double the prefix.

Revision ID: 7c4e2a91d503
Revises: 219b0ba4f2e1
Create Date: 2026-07-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "7c4e2a91d503"
down_revision: str | None = "219b0ba4f2e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WITH_UPDATE = (
    "prices",
    "macro",
    "fundamentals",
    "earnings",
    "features",
    "snapshots",
    "portfolio_import",
    "update",
)


def _check(values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"run_type IN ({quoted})"


def upgrade() -> None:
    op.execute("ALTER TABLE ingestion_runs DROP CONSTRAINT ck_ingestion_runs_run_type")
    op.execute(
        "ALTER TABLE ingestion_runs ADD CONSTRAINT ck_ingestion_runs_run_type "
        f"CHECK ({_check(WITH_UPDATE)})"
    )


def downgrade() -> None:
    op.execute("DELETE FROM ingestion_runs WHERE run_type = 'update'")
    op.execute("ALTER TABLE ingestion_runs DROP CONSTRAINT ck_ingestion_runs_run_type")
    op.execute(
        "ALTER TABLE ingestion_runs ADD CONSTRAINT ck_ingestion_runs_run_type "
        f"CHECK ({_check(WITH_UPDATE[:-1])})"
    )
