"""portfolio layer

Revision ID: b3c9e1d47a20
Revises: a91c3fd02b77
Create Date: 2026-07-13

The frozen §4.7 portfolio schema: append-only transaction ledger as the
source of truth (D14), with lots / lot_closures / position_snapshots as
derived, rebuildable projections. One declared minimal amendment:
transactions.ingestion_run_id — §4.7 omitted it, but decision D7 mandates
run lineage on every fact row (as daily_prices and macro_observations
already carry); import batches are ingestion_runs rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c9e1d47a20"
down_revision: str | None = "a91c3fd02b77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RUN_TYPES = ("prices", "macro", "fundamentals", "earnings", "features", "snapshots")
RUN_TYPES_V2 = RUN_TYPES + ("portfolio_import",)


def _run_type_check(values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"run_type IN ({quoted})"


def upgrade() -> None:
    # extend the audit vocabulary: portfolio imports are ingestion runs too
    # (raw SQL: alembic would re-apply the ck_ naming convention on top of
    # the already-conventional constraint name)
    op.execute("ALTER TABLE ingestion_runs DROP CONSTRAINT ck_ingestion_runs_run_type")
    op.alter_column("ingestion_runs", "run_type", type_=sa.String(32))
    op.execute(
        "ALTER TABLE ingestion_runs ADD CONSTRAINT ck_ingestion_runs_run_type "
        f"CHECK ({_run_type_check(RUN_TYPES_V2)})"
    )

    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("base_currency", sa.Text(), server_default="USD", nullable=False),
        sa.Column(
            "cost_basis_method",
            sa.Enum(
                "FIFO",
                "specific_id",
                name="cost_basis_method",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="FIFO",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portfolios")),
        sa.UniqueConstraint("name", name=op.f("uq_portfolios_name")),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column(
            "txn_type",
            sa.Enum(
                "buy",
                "sell",
                "dividend",
                "fee",
                "deposit",
                "withdrawal",
                "transfer_in",
                "transfer_out",
                "opening_balance",
                "split",
                name="txn_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=True),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        sa.Column("fees", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("total_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
        sa.UniqueConstraint(
            "portfolio_id", "external_id", name=op.f("uq_transactions_portfolio_id_external_id")
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.id"],
            name=op.f("fk_transactions_portfolio_id_portfolios"),
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_transactions_instrument_id_instruments"),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name=op.f("fk_transactions_ingestion_run_id_ingestion_runs"),
        ),
    )
    op.create_index(
        "ix_txn_portfolio_date", "transactions", ["portfolio_id", "trade_date"], unique=False
    )

    op.create_table(
        "lots",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("open_transaction_id", sa.BigInteger(), nullable=False),
        sa.Column("open_date", sa.Date(), nullable=False),
        sa.Column("quantity_opened", sa.Numeric(20, 8), nullable=False),
        sa.Column("quantity_remaining", sa.Numeric(20, 8), nullable=False),
        sa.Column("cost_basis_per_share", sa.Numeric(18, 6), nullable=False),
        sa.Column("is_closed", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lots")),
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["portfolios.id"], name=op.f("fk_lots_portfolio_id_portfolios")
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], name=op.f("fk_lots_instrument_id_instruments")
        ),
        sa.ForeignKeyConstraint(
            ["open_transaction_id"],
            ["transactions.id"],
            name=op.f("fk_lots_open_transaction_id_transactions"),
        ),
    )
    op.create_index(
        "ix_lots_portfolio_instr",
        "lots",
        ["portfolio_id", "instrument_id"],
        unique=False,
        postgresql_where=sa.text("NOT is_closed"),
    )

    op.create_table(
        "lot_closures",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("lot_id", sa.BigInteger(), nullable=False),
        sa.Column("close_transaction_id", sa.BigInteger(), nullable=False),
        sa.Column("close_date", sa.Date(), nullable=False),
        sa.Column("quantity_closed", sa.Numeric(20, 8), nullable=False),
        sa.Column("proceeds", sa.Numeric(20, 6), nullable=False),
        sa.Column("cost_basis", sa.Numeric(20, 6), nullable=False),
        sa.Column("realized_gain", sa.Numeric(20, 6), nullable=False),
        sa.Column("holding_period_days", sa.Integer(), nullable=False),
        sa.Column(
            "term",
            sa.Enum("short", "long", name="gain_term", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lot_closures")),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.id"], name=op.f("fk_lot_closures_lot_id_lots")),
        sa.ForeignKeyConstraint(
            ["close_transaction_id"],
            ["transactions.id"],
            name=op.f("fk_lot_closures_close_transaction_id_transactions"),
        ),
    )

    op.create_table(
        "position_snapshots",
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("cost_basis", sa.Numeric(20, 6), nullable=False),
        sa.Column("market_value", sa.Numeric(20, 6), nullable=True),
        sa.Column("unrealized_gain", sa.Numeric(20, 6), nullable=True),
        sa.Column("weight", sa.Numeric(10, 8), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "portfolio_id", "instrument_id", "snapshot_date", name=op.f("pk_position_snapshots")
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.id"],
            name=op.f("fk_position_snapshots_portfolio_id_portfolios"),
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_position_snapshots_instrument_id_instruments"),
        ),
    )


def downgrade() -> None:
    op.drop_table("position_snapshots")
    op.drop_table("lot_closures")
    op.drop_index("ix_lots_portfolio_instr", table_name="lots")
    op.drop_table("lots")
    op.drop_index("ix_txn_portfolio_date", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("portfolios")
    op.execute("DELETE FROM ingestion_runs WHERE run_type = 'portfolio_import'")
    op.execute("ALTER TABLE ingestion_runs DROP CONSTRAINT ck_ingestion_runs_run_type")
    op.execute(
        "ALTER TABLE ingestion_runs ADD CONSTRAINT ck_ingestion_runs_run_type "
        f"CHECK ({_run_type_check(RUN_TYPES)})"
    )
