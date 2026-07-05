"""reference data layer

Revision ID: 68ffe5a2f498
Revises: 5f5857c012a0
Create Date: 2026-07-04 14:00:17.746122
"""

from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "68ffe5a2f498"
down_revision: str | None = "5f5857c012a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # sectors <-> instruments is circular: sectors is created WITHOUT the
    # etf_instrument_id FK, which is added by ALTER once instruments exists.
    op.create_table(
        "sectors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("etf_instrument_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sectors")),
        sa.UniqueConstraint("name", name=op.f("uq_sectors_name")),
    )
    op.create_table(
        "trading_calendar",
        sa.Column("exchange", sa.Text(), nullable=False),
        sa.Column("calendar_date", sa.Date(), nullable=False),
        sa.Column("is_half_day", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("exchange", "calendar_date", name=op.f("pk_trading_calendar")),
    )
    op.create_table(
        "industries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sector_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sector_id"], ["sectors.id"], name=op.f("fk_industries_sector_id_sectors")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_industries")),
        sa.UniqueConstraint("sector_id", "name", name=op.f("uq_industries_sector_id_name")),
    )
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column(
            "instrument_type",
            sa.Enum(
                "stock",
                "etf",
                "index",
                name="instrument_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("industry_id", sa.Integer(), nullable=True),
        sa.Column("sector_id", sa.Integer(), nullable=True),
        sa.Column("currency", sa.Text(), server_default="USD", nullable=False),
        sa.Column("exchange", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("delisted_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "NOT (industry_id IS NOT NULL AND sector_id IS NOT NULL)",
            name=op.f("ck_instruments_single_classification"),
        ),
        sa.ForeignKeyConstraint(
            ["industry_id"], ["industries.id"], name=op.f("fk_instruments_industry_id_industries")
        ),
        sa.ForeignKeyConstraint(
            ["sector_id"], ["sectors.id"], name=op.f("fk_instruments_sector_id_sectors")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_instruments")),
        sa.UniqueConstraint("symbol", name=op.f("uq_instruments_symbol")),
    )
    op.create_table(
        "symbol_history",
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_symbol_history_instrument_id_instruments"),
        ),
        sa.PrimaryKeyConstraint("instrument_id", "valid_from", name=op.f("pk_symbol_history")),
    )
    op.create_index(op.f("ix_symbol_history_symbol"), "symbol_history", ["symbol"], unique=False)
    op.create_foreign_key(
        op.f("fk_sectors_etf_instrument_id_instruments"),
        "sectors",
        "instruments",
        ["etf_instrument_id"],
        ["id"],
    )


def downgrade() -> None:
    # Drop the circular FK first so instruments can be dropped.
    op.drop_constraint(
        op.f("fk_sectors_etf_instrument_id_instruments"), "sectors", type_="foreignkey"
    )
    op.drop_index(op.f("ix_symbol_history_symbol"), table_name="symbol_history")
    op.drop_table("symbol_history")
    op.drop_table("instruments")
    op.drop_table("industries")
    op.drop_table("trading_calendar")
    op.drop_table("sectors")
