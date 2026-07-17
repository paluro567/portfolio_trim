"""prediction archive — ROADMAP Phase 10 "trim-score output tables"

`predictions` is APPEND-ONLY (immutable archive; natural-key unique
constraint + ON CONFLICT DO NOTHING at the repository seam).
`prediction_outcomes` is derived data (guarded upsert; recomputable).

Autogenerate note: the yearly feature-store partitions and the
ingestion_runs.run_type raw-SQL widening are runtime/deliberate artifacts
and are intentionally NOT touched here.

Revision ID: 219b0ba4f2e1
Revises: b3c9e1d47a20
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "219b0ba4f2e1"
down_revision: str | None = "b3c9e1d47a20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_key", sa.Text(), server_default="", nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("horizon", sa.Text(), nullable=False),
        sa.Column("horizon_sessions", sa.Integer(), nullable=False),
        sa.Column("trim_score", sa.Float(), nullable=False),
        sa.Column("evidence_trim_score", sa.Float(), nullable=False),
        sa.Column("portfolio_adjustment", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("recommendation_label", sa.Text(), nullable=False),
        sa.Column("expected_return", sa.Float(), nullable=True),
        sa.Column("expected_excess_return", sa.Float(), nullable=True),
        sa.Column("baseline_return", sa.Float(), nullable=True),
        sa.Column("data_quality_label", sa.Text(), nullable=False),
        sa.Column("contradictory_evidence", sa.Float(), nullable=False),
        sa.Column("effective_sample_size", sa.Float(), nullable=False),
        sa.Column("participating_models", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("primary_trim_drivers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("primary_hold_strengths", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model_contributions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("trim_engine_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_predictions_instrument_id_instruments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_predictions")),
        sa.UniqueConstraint(
            "instrument_id",
            "portfolio_key",
            "as_of",
            "horizon",
            "trim_engine_version",
            name="uq_predictions_identity",
        ),
    )
    op.create_table(
        "prediction_outcomes",
        sa.Column("prediction_id", sa.Integer(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("exit_date", sa.Date(), nullable=False),
        sa.Column("entry_price", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("exit_price", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("actual_return", sa.Float(), nullable=False),
        sa.Column("actual_excess_return", sa.Float(), nullable=True),
        sa.Column("prediction_error", sa.Float(), nullable=True),
        sa.Column("absolute_error", sa.Float(), nullable=True),
        sa.Column("direction_correct", sa.Boolean(), nullable=True),
        sa.Column("outperformed", sa.Boolean(), nullable=True),
        sa.Column("underperformed", sa.Boolean(), nullable=True),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["prediction_id"],
            ["predictions.id"],
            name=op.f("fk_prediction_outcomes_prediction_id_predictions"),
        ),
        sa.PrimaryKeyConstraint("prediction_id", name=op.f("pk_prediction_outcomes")),
    )


def downgrade() -> None:
    op.drop_table("prediction_outcomes")
    op.drop_table("predictions")
