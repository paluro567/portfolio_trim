"""feature store

Revision ID: a91c3fd02b77
Revises: f087df9fe3e1
Create Date: 2026-07-04 20:00:00

Hand-written: partitioned tables (PARTITION BY RANGE) are outside
autogenerate's vocabulary. Yearly partitions 2009-2028 are created here;
FeatureRepository.ensure_partitions() adds later years at runtime.
"""

from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401
from alembic import op

revision: str = "a91c3fd02b77"
down_revision: str | None = "f087df9fe3e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARTITION_YEARS = range(2009, 2029)


def upgrade() -> None:
    op.create_table(
        "feature_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "scope",
            sa.Enum(
                "instrument",
                "market",
                name="feature_scope",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("params", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("uses_adjusted_prices", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feature_definitions")),
        sa.UniqueConstraint("name", "version", name=op.f("uq_feature_definitions_name_version")),
    )

    op.execute("""
        CREATE TABLE feature_store_daily (
            instrument_id INT NOT NULL
                CONSTRAINT fk_feature_store_daily_instrument_id_instruments
                REFERENCES instruments(id),
            feature_date DATE NOT NULL,
            feature_id INT NOT NULL
                CONSTRAINT fk_feature_store_daily_feature_id_feature_definitions
                REFERENCES feature_definitions(id),
            value NUMERIC(20,8),
            computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT pk_feature_store_daily
                PRIMARY KEY (instrument_id, feature_date, feature_id)
        ) PARTITION BY RANGE (feature_date)
        """)
    op.execute(
        "CREATE INDEX ix_fs_daily_feature_date " "ON feature_store_daily (feature_id, feature_date)"
    )

    op.execute("""
        CREATE TABLE feature_store_market_daily (
            feature_date DATE NOT NULL,
            feature_id INT NOT NULL
                CONSTRAINT fk_feature_store_market_daily_feature_id_feature_definitions
                REFERENCES feature_definitions(id),
            value NUMERIC(20,8),
            computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT pk_feature_store_market_daily
                PRIMARY KEY (feature_date, feature_id)
        ) PARTITION BY RANGE (feature_date)
        """)
    op.execute(
        "CREATE INDEX ix_fs_market_feature_date "
        "ON feature_store_market_daily (feature_id, feature_date)"
    )

    for table in ("feature_store_daily", "feature_store_market_daily"):
        for year in PARTITION_YEARS:
            op.execute(
                f"CREATE TABLE {table}_y{year} PARTITION OF {table} "
                f"FOR VALUES FROM ('{year}-01-01') TO ('{year + 1}-01-01')"
            )


def downgrade() -> None:
    # Dropping the parents drops all partitions with them.
    op.execute("DROP TABLE feature_store_market_daily")
    op.execute("DROP TABLE feature_store_daily")
    op.drop_table("feature_definitions")
