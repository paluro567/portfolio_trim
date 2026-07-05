"""ORM models — schema per docs/ARCHITECTURE.md v2 (frozen).

Phase 1: reference layer (§4.1) — sectors, industries, instruments,
symbol_history, trading_calendar.
Phase 2: ingestion layer (§4.2, §4.5) — ingestion_runs, daily_prices,
corporate_actions, data_quality_issues, data_revisions.
Later phases add their own tables; nothing here may be redesigned without
an architecture amendment.

The naming convention must exist before the first migration: Alembic
autogenerate and future ALTERs depend on deterministic constraint names.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from mip.domain.enums import (
    CorporateActionType,
    FeatureScope,
    InstrumentType,
    IssueSeverity,
    IssueStatus,
    RunStatus,
    RunType,
)


def _text_enum(enum_cls: type, name: str) -> Enum:
    """TEXT column constrained to enum values (per architecture DDL)."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda e: [m.value for m in e],
    )


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Sector(Base):
    __tablename__ = "sectors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    # FK, not a ticker string (D11). use_alter: instruments references
    # sectors, so this circular edge is added after both tables exist.
    etf_instrument_id: Mapped[int | None] = mapped_column(
        ForeignKey("instruments.id", use_alter=True)
    )

    etf_instrument: Mapped["Instrument | None"] = relationship(
        foreign_keys=[etf_instrument_id], post_update=True
    )
    industries: Mapped[list["Industry"]] = relationship(back_populates="sector")


class Industry(Base):
    __tablename__ = "industries"
    __table_args__ = (UniqueConstraint("sector_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sector_id: Mapped[int] = mapped_column(ForeignKey("sectors.id"))
    name: Mapped[str] = mapped_column(Text)

    sector: Mapped[Sector] = relationship(back_populates="industries")


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        # At most one direct classification: industry implies sector (3NF).
        CheckConstraint(
            "NOT (industry_id IS NOT NULL AND sector_id IS NOT NULL)",
            name="single_classification",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(Text, unique=True)  # CURRENT symbol only
    name: Mapped[str | None] = mapped_column(Text)
    instrument_type: Mapped[InstrumentType] = mapped_column(
        _text_enum(InstrumentType, "instrument_type")
    )
    industry_id: Mapped[int | None] = mapped_column(ForeignKey("industries.id"))
    sector_id: Mapped[int | None] = mapped_column(ForeignKey("sectors.id"))
    currency: Mapped[str] = mapped_column(Text, default="USD", server_default="USD")
    exchange: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    delisted_date: Mapped[date | None] = mapped_column(Date)  # never DELETE instruments
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    industry: Mapped[Industry | None] = relationship(foreign_keys=[industry_id])
    sector: Mapped[Sector | None] = relationship(foreign_keys=[sector_id])
    symbol_records: Mapped[list["SymbolHistory"]] = relationship(
        back_populates="instrument", order_by="SymbolHistory.valid_from"
    )


class SymbolHistory(Base):
    __tablename__ = "symbol_history"

    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), primary_key=True)
    valid_from: Mapped[date] = mapped_column(Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(Text, index=True)
    valid_to: Mapped[date | None] = mapped_column(Date)  # NULL = current

    instrument: Mapped[Instrument] = relationship(back_populates="symbol_records")


class TradingDay(Base):
    __tablename__ = "trading_calendar"

    exchange: Mapped[str] = mapped_column(Text, primary_key=True, default="NYSE")
    calendar_date: Mapped[date] = mapped_column(Date, primary_key=True)
    is_half_day: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


# -- Phase 2: ingestion (§4.2, §4.5) ------------------------------------


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("ix_runs_type_started", "run_type", "started_at", postgresql_using="btree"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_type: Mapped[RunType] = mapped_column(_text_enum(RunType, "run_type"))
    provider: Mapped[str] = mapped_column(Text)
    scope: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[RunStatus] = mapped_column(
        _text_enum(RunStatus, "run_status"), default=RunStatus.RUNNING, server_default="running"
    )
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rows_updated: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    archive_path: Mapped[str | None] = mapped_column(Text)
    error_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class DailyPrice(Base):
    __tablename__ = "daily_prices"
    __table_args__ = (Index("ix_daily_prices_date", "price_date"),)

    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), primary_key=True)
    price_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )


class CorporateAction(Base):
    __tablename__ = "corporate_actions"
    __table_args__ = (UniqueConstraint("instrument_id", "action_type", "ex_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    action_type: Mapped[CorporateActionType] = mapped_column(
        _text_enum(CorporateActionType, "corporate_action_type")
    )
    ex_date: Mapped[date] = mapped_column(Date)
    split_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    cash_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )


class MacroSeries(Base):
    __tablename__ = "macro_series"
    __table_args__ = (UniqueConstraint("provider", "provider_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(Text, default="FRED", server_default="FRED")
    provider_code: Mapped[str] = mapped_column(Text)  # 'DGS10', 'FEDFUNDS', ...
    name: Mapped[str] = mapped_column(Text)
    frequency: Mapped[str] = mapped_column(Text)  # 'D' | 'W' | 'M' | 'Q'
    units: Mapped[str | None] = mapped_column(Text)
    seasonally_adjusted: Mapped[bool | None] = mapped_column(Boolean)
    # obs_date + publication_lag_days = first date the value was knowable.
    # Every downstream consumer must respect this (D13).
    publication_lag_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class MacroObservation(Base):
    __tablename__ = "macro_observations"
    __table_args__ = (Index("ix_macro_obs_date", "obs_date"),)

    series_id: Mapped[int] = mapped_column(ForeignKey("macro_series.id"), primary_key=True)
    obs_date: Mapped[date] = mapped_column(Date, primary_key=True)  # reference period date
    value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))  # NULL = FRED '.'
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )


class CompanyFundamentals(Base):
    """Dated snapshots (§4.4): one row per (instrument, fetch date), never
    mutated across dates. History accumulates from the day this ships;
    PIT-honest — as_of_date is when WE fetched, not a report period."""

    __tablename__ = "company_fundamentals"

    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, primary_key=True)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    trailing_pe: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    forward_pe: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    price_to_book: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    trailing_eps: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    forward_eps: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    beta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    shares_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    revenue_ttm: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    profit_margin: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    debt_to_equity: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )


class EarningsObservation(Base):
    """APPEND-ONLY (§4.4): every observed state of an earnings date is a new
    row; announced dates shift and 'what was known when' must survive.
    v_earnings_current (view, created in migration) exposes the latest
    observation per (instrument, earnings_date)."""

    __tablename__ = "earnings_observations"
    __table_args__ = (UniqueConstraint("instrument_id", "earnings_date", "observed_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    earnings_date: Mapped[date] = mapped_column(Date)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    time_of_day: Mapped[str | None] = mapped_column(Text)  # 'BMO' | 'AMC' | 'unknown'
    eps_estimate: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    eps_actual: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"
    __table_args__ = (Index("ix_dqi_status", "status", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ingestion_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ingestion_runs.id"))
    entity_type: Mapped[str] = mapped_column(Text)  # 'price' | 'macro_obs' | ...
    entity_key: Mapped[str] = mapped_column(Text)  # e.g. 'AAPL/2026-07-02'
    rule: Mapped[str] = mapped_column(Text)
    severity: Mapped[IssueSeverity] = mapped_column(_text_enum(IssueSeverity, "issue_severity"))
    observed_value: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[IssueStatus] = mapped_column(
        _text_enum(IssueStatus, "issue_status"), default=IssueStatus.OPEN, server_default="open"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataRevision(Base):
    __tablename__ = "data_revisions"
    __table_args__ = (Index("ix_revisions_entity", "table_name", "entity_key"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    table_name: Mapped[str] = mapped_column(Text)  # 'daily_prices' | 'macro_observations'
    entity_key: Mapped[str] = mapped_column(Text)  # 'AAPL/2026-06-15'
    field: Mapped[str] = mapped_column(Text)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )


# -- Phase 5: feature store (§4.6) ---------------------------------------


class FeatureDefinition(Base):
    """Features as governed, versioned entities (D6). Changing params is a
    NEW version — stored values are never silently redefined. description
    is human-readable: it becomes future explanation text (D7/§7)."""

    __tablename__ = "feature_definitions"
    __table_args__ = (UniqueConstraint("name", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    scope: Mapped[FeatureScope] = mapped_column(_text_enum(FeatureScope, "feature_scope"))
    description: Mapped[str] = mapped_column(Text)
    params: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    uses_adjusted_prices: Mapped[bool | None] = mapped_column(Boolean)


class FeatureStoreDaily(Base):
    """Instrument-scoped features. Partitioned by year on feature_date;
    partitions are created in the migration and by ensure_partitions()."""

    __tablename__ = "feature_store_daily"
    __table_args__ = (
        Index("ix_fs_daily_feature_date", "feature_id", "feature_date"),
        {"postgresql_partition_by": "RANGE (feature_date)"},
    )

    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), primary_key=True)
    feature_date: Mapped[date] = mapped_column(Date, primary_key=True)
    feature_id: Mapped[int] = mapped_column(ForeignKey("feature_definitions.id"), primary_key=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FeatureStoreMarketDaily(Base):
    """Market-wide features (curve slope, regimes). Separate table so both
    stores have real composite PKs (v2 fix of the NULL-uniqueness defect)."""

    __tablename__ = "feature_store_market_daily"
    __table_args__ = (
        Index("ix_fs_market_feature_date", "feature_id", "feature_date"),
        {"postgresql_partition_by": "RANGE (feature_date)"},
    )

    feature_date: Mapped[date] = mapped_column(Date, primary_key=True)
    feature_id: Mapped[int] = mapped_column(ForeignKey("feature_definitions.id"), primary_key=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
