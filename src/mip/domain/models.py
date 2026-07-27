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
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from mip.domain.enums import (
    CorporateActionType,
    CostBasisMethod,
    DivergenceClass,
    ExperimentDecision,
    ExperimentRunStatus,
    FeatureScope,
    GainTerm,
    IdentifierType,
    IdentityWorld,
    InstrumentType,
    IssueSeverity,
    IssueStatus,
    LifecycleEventType,
    MappingMethod,
    MappingStatus,
    OutcomeStatus,
    ParityReviewStatus,
    ReturnStatus,
    RunStatus,
    RunType,
    SecurityType,
    SnapshotStatus,
    TerminalRule,
    TxnType,
    UniverseStatus,
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


class Portfolio(Base):
    """Portfolio header (§4.7). The transaction ledger is the SOURCE OF
    TRUTH (D14); lots, closures, and snapshots are derived projections."""

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    base_currency: Mapped[str] = mapped_column(Text, server_default="USD")
    cost_basis_method: Mapped[CostBasisMethod] = mapped_column(
        _text_enum(CostBasisMethod, "cost_basis_method"), server_default="FIFO"
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Transaction(Base):
    """APPEND-ONLY ledger (D14): corrections are reversing entries, never
    UPDATEs. total_amount is the signed cash impact for cash-moving types;
    for non-cash position movements (opening_balance, transfer_in/out) it
    carries the cost basis, with txn_type marking the row non-cash.
    ingestion_run_id is the declared minimal amendment resolving §4.7's
    omission against decision D7 (every fact row carries run lineage)."""

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "external_id"),
        Index("ix_txn_portfolio_date", "portfolio_id", "trade_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"))
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    txn_type: Mapped[TxnType] = mapped_column(_text_enum(TxnType, "txn_type"))
    trade_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    fees: Mapped[Decimal] = mapped_column(Numeric(18, 6), server_default="0")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    external_id: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )

    instrument: Mapped["Instrument | None"] = relationship()


class Lot(Base):
    """Derived tax lot; rebuildable from the ledger at any time (D14)."""

    __tablename__ = "lots"
    __table_args__ = (
        Index(
            "ix_lots_portfolio_instr",
            "portfolio_id",
            "instrument_id",
            postgresql_where=text("NOT is_closed"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"))
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    open_transaction_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("transactions.id"))
    open_date: Mapped[date] = mapped_column(Date)
    quantity_opened: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    quantity_remaining: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    cost_basis_per_share: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    is_closed: Mapped[bool] = mapped_column(Boolean, server_default="false")


class LotClosure(Base):
    """Realized gains at the lot-slice level; derived, rebuildable."""

    __tablename__ = "lot_closures"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lot_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("lots.id"))
    close_transaction_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("transactions.id"))
    close_date: Mapped[date] = mapped_column(Date)
    quantity_closed: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    proceeds: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    realized_gain: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    holding_period_days: Mapped[int] = mapped_column(Integer)
    term: Mapped[GainTerm] = mapped_column(_text_enum(GainTerm, "gain_term"))


class PositionSnapshot(Base):
    """Derived daily position projection; rebuildable from ledger + prices."""

    __tablename__ = "position_snapshots"

    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    market_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    unrealized_gain: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# -- Phase: Prediction Archive & Outcome Evaluation (ROADMAP Phase 10 ----
# "trim-score output tables") ---------------------------------------------


class Prediction(Base):
    """One archived trim prediction — IMMUTABLE. Rows are only ever
    inserted (ON CONFLICT DO NOTHING on the natural key); no code path
    updates or deletes them. Every prediction is permanent evidence."""

    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "portfolio_key",
            "as_of",
            "horizon",
            "trim_engine_version",
            name="uq_predictions_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    portfolio_key: Mapped[str] = mapped_column(Text, default="", server_default="")
    as_of: Mapped[date] = mapped_column(Date)
    horizon: Mapped[str] = mapped_column(Text)
    horizon_sessions: Mapped[int] = mapped_column(Integer)
    trim_score: Mapped[float] = mapped_column(Float)
    evidence_trim_score: Mapped[float] = mapped_column(Float)
    portfolio_adjustment: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    recommendation_label: Mapped[str] = mapped_column(Text)
    expected_return: Mapped[float | None] = mapped_column(Float)
    expected_excess_return: Mapped[float | None] = mapped_column(Float)
    baseline_return: Mapped[float | None] = mapped_column(Float)
    data_quality_label: Mapped[str] = mapped_column(Text)
    contradictory_evidence: Mapped[float] = mapped_column(Float)
    effective_sample_size: Mapped[float] = mapped_column(Float)
    participating_models: Mapped[list | None] = mapped_column(JSONB)
    primary_trim_drivers: Mapped[list | None] = mapped_column(JSONB)
    primary_hold_strengths: Mapped[list | None] = mapped_column(JSONB)
    model_contributions: Mapped[list | None] = mapped_column(JSONB)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    trim_engine_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    instrument: Mapped[Instrument] = relationship()


class PredictionOutcome(Base):
    """Realized outcome for one matured prediction — DERIVED data,
    recomputable from prices; guarded upsert keeps re-evaluation
    idempotent. The prediction row itself is never touched."""

    __tablename__ = "prediction_outcomes"

    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"), primary_key=True)
    entry_date: Mapped[date] = mapped_column(Date)
    exit_date: Mapped[date] = mapped_column(Date)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    exit_price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    actual_return: Mapped[float] = mapped_column(Float)
    actual_excess_return: Mapped[float | None] = mapped_column(Float)
    prediction_error: Mapped[float | None] = mapped_column(Float)
    absolute_error: Mapped[float | None] = mapped_column(Float)
    direction_correct: Mapped[bool | None] = mapped_column(Boolean)
    outperformed: Mapped[bool | None] = mapped_column(Boolean)
    underperformed: Mapped[bool | None] = mapped_column(Boolean)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    prediction: Mapped[Prediction] = relationship()


# ============================================================================
# Phase 1 — Point-in-time security master & universe integrity (§ EVALUATION_
# FOUNDATION_DESIGN). Survivorship-clean historical identity: a security is
# keyed by a permanent internal `security_id`, NEVER by its ticker. Delisted,
# acquired, bankrupt, renamed, and share-class-split securities all persist.
# Nothing here touches production scoring; these tables carry their own source
# lineage + data_version for reproducibility.
# ============================================================================


class SecurityMaster(Base):
    """One persistent economic security across its whole lifecycle.

    Surrogate key: `security_id` (the permanent internal identity). Natural key:
    (source, source_security_id) — a given vendor's permanent record maps to
    exactly one security_id, which is the idempotency + resolution anchor."""

    __tablename__ = "security_master"
    __table_args__ = (
        UniqueConstraint("source", "source_security_id", name="uq_security_master_source_id"),
        Index("ix_security_master_active", "active_flag"),
        CheckConstraint(
            "delisting_date IS NULL OR first_trade_date IS NULL "
            "OR delisting_date >= first_trade_date",
            name="delist_after_list",
        ),
    )

    security_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    issuer_id: Mapped[int | None] = mapped_column(BigInteger)  # issuer modelling deferred
    security_type: Mapped[SecurityType] = mapped_column(_text_enum(SecurityType, "security_type_e"))
    share_class: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(Text, default="USD", server_default="USD")
    primary_exchange: Mapped[str | None] = mapped_column(Text)
    first_trade_date: Mapped[date | None] = mapped_column(Date)
    last_trade_date: Mapped[date | None] = mapped_column(Date)
    active_flag: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    delisted_flag: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    delisting_date: Mapped[date | None] = mapped_column(Date)
    delisting_reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    source_security_id: Mapped[str] = mapped_column(Text)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )
    data_version: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SecurityIdentifierHistory(Base):
    """Time-bounded external identifiers (ticker/CUSIP/ISIN/FIGI/vendor). Ticker
    reuse by a different security across time is supported; a ticker lookup
    ALWAYS carries an as-of date. No overlapping validity for the same
    (security, identifier_type) — the PK enforces one interval per valid_from."""

    __tablename__ = "security_identifier_history"
    __table_args__ = (Index("ix_sec_ident_lookup", "identifier_type", "identifier_value"),)

    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("security_master.security_id"), primary_key=True
    )
    identifier_type: Mapped[IdentifierType] = mapped_column(
        _text_enum(IdentifierType, "identifier_type_e"), primary_key=True
    )
    valid_from: Mapped[date] = mapped_column(Date, primary_key=True)
    identifier_value: Mapped[str] = mapped_column(Text)
    exchange: Mapped[str | None] = mapped_column(Text)
    valid_to: Mapped[date | None] = mapped_column(Date)  # NULL = current
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    source: Mapped[str] = mapped_column(Text)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )
    data_version: Mapped[str] = mapped_column(Text)


class SecurityLifecycleEvent(Base):
    """Events affecting historical identity or eligibility, recorded point-in-
    time. Successor/predecessor link corporate reorganizations across ids."""

    __tablename__ = "security_lifecycle_event"
    __table_args__ = (
        UniqueConstraint("security_id", "event_type", "effective_date", name="uq_lifecycle_event"),
        CheckConstraint(
            "successor_security_id IS NULL OR successor_security_id <> security_id",
            name="successor_not_self",
        ),
    )

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    security_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("security_master.security_id"))
    event_type: Mapped[LifecycleEventType] = mapped_column(
        _text_enum(LifecycleEventType, "lifecycle_event_type_e")
    )
    effective_date: Mapped[date] = mapped_column(Date)
    announcement_date: Mapped[date | None] = mapped_column(Date)
    successor_security_id: Mapped[int | None] = mapped_column(BigInteger)
    predecessor_security_id: Mapped[int | None] = mapped_column(BigInteger)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(Text)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )
    data_version: Mapped[str] = mapped_column(Text)


class DelistingEvent(Base):
    """Explicit delisting outcome — the price history does NOT silently end.
    `delisting_return`/`terminal_price` stay NULL in Phase 1 (no price source
    yet); they are never fabricated. One delisting per security → PK is
    security_id."""

    __tablename__ = "delisting_event"
    __table_args__ = (
        CheckConstraint(
            "successor_security_id IS NULL OR successor_security_id <> security_id",
            name="delist_successor_not_self",
        ),
    )

    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("security_master.security_id"), primary_key=True
    )
    delisting_date: Mapped[date] = mapped_column(Date)
    delisting_code: Mapped[str | None] = mapped_column(Text)
    delisting_reason: Mapped[str | None] = mapped_column(Text)
    delisting_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))  # Phase 2
    cash_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    successor_security_id: Mapped[int | None] = mapped_column(BigInteger)
    terminal_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))  # Phase 2
    source: Mapped[str] = mapped_column(Text)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )
    data_version: Mapped[str] = mapped_column(Text)


class UniverseDefinition(Base):
    """Frozen, versioned eligibility rules. A historical experiment references an
    immutable (name, version); status=frozen forbids mutation."""

    __tablename__ = "universe_definition"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_universe_definition_name_ver"),)

    universe_definition_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    eligibility_rules_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source_requirements_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[UniverseStatus] = mapped_column(
        _text_enum(UniverseStatus, "universe_status_e"),
        default=UniverseStatus.DRAFT,
        server_default="draft",
    )


class UniverseMembership(Base):
    """Whether a security was eligible on a historical date. Reconstructable
    point-in-time; membership never extends past the security's delisting date
    (enforced by the builder + a data-quality check). Market-cap/price/volume
    stay NULL until Phase 2 supplies the filters."""

    __tablename__ = "universe_membership"

    universe_definition_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("universe_definition.universe_definition_id"), primary_key=True
    )
    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("security_master.security_id"), primary_key=True
    )
    membership_date: Mapped[date] = mapped_column(Date, primary_key=True)
    included_flag: Mapped[bool] = mapped_column(Boolean)
    exclusion_reason: Mapped[str | None] = mapped_column(Text)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))  # Phase 2
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))  # Phase 2
    dollar_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))  # Phase 2
    exchange: Mapped[str | None] = mapped_column(Text)
    security_type: Mapped[SecurityType | None] = mapped_column(
        _text_enum(SecurityType, "security_type_e")
    )
    classification_id: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(Text)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )
    data_version: Mapped[str] = mapped_column(Text)


class HistoricalClassification(Base):
    """Point-in-time sector/industry. Never backfilled from today's sector.
    Absent PIT classifications are recorded as absent, not fabricated."""

    __tablename__ = "historical_classification"
    __table_args__ = (
        UniqueConstraint(
            "security_id", "classification_scheme", "valid_from", name="uq_hist_classification"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    security_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("security_master.security_id"))
    classification_scheme: Mapped[str] = mapped_column(Text)  # e.g. 'GICS'
    sector: Mapped[str | None] = mapped_column(Text)
    industry_group: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(Text)
    sub_industry: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(Text)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )
    data_version: Mapped[str] = mapped_column(Text)


# ============================================================================
# Phase 2A — Native survivorship-clean outcome foundation & migration
# guardrails (§ PHASE2_DESIGN, PHASE3_IDENTITY_MIGRATION). Everything here keys
# on the permanent `security_id`, NEVER on ticker or legacy `instrument_id`.
# Delisted/inactive securities and terminal outcomes are preserved, never
# dropped. Nothing here touches production scoring; every row carries source +
# ingestion_run_id + data_version + calculation/identity-world lineage so that
# research is reproducible and legacy/native worlds can never be silently mixed.
# ============================================================================


class InstrumentSecurityMap(Base):
    """First-class point-in-time bridge legacy `instrument_id` <-> native
    `security_id`. This is the load-bearing seam between the two identity worlds:
    every crossing is explicit, as-of-dated, lineage-stamped, and (when
    ambiguous) quarantined. Ticker equality alone never establishes identity.

    No two ACTIVE rows for the same instrument_id may overlap in time — enforced
    by the ingestor + a data-quality check; a partial-index would also enforce it
    but the map is small and validated on every write."""

    __tablename__ = "instrument_security_map"
    __table_args__ = (
        Index("ix_ism_instrument", "instrument_id", "valid_from"),
        Index("ix_ism_security", "security_id", "valid_from"),
        CheckConstraint("valid_to IS NULL OR valid_from <= valid_to", name="ism_interval_ordered"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ism_confidence_unit"),
    )

    map_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("instruments.id"))
    security_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("security_master.security_id"))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)  # NULL = still current
    mapping_reason: Mapped[str | None] = mapped_column(Text)
    mapping_method: Mapped[MappingMethod] = mapped_column(
        _text_enum(MappingMethod, "mapping_method_e")
    )
    status: Mapped[MappingStatus] = mapped_column(
        _text_enum(MappingStatus, "mapping_status_e"),
        default=MappingStatus.ACTIVE,
        server_default="active",
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0, server_default="1.0")
    source: Mapped[str] = mapped_column(Text)
    source_record_id: Mapped[str | None] = mapped_column(Text)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )
    data_version: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SecurityPriceDaily(Base):
    """Native daily prices under permanent `security_id`. Keyed by
    (security_id, trade_date, source, data_version) so multiple vendor snapshots
    coexist for cross-check/parity without collision. NEVER keyed by ticker or
    instrument_id."""

    __tablename__ = "security_price_daily"
    __table_args__ = (
        UniqueConstraint(
            "security_id", "trade_date", "source", "data_version", name="uq_spd_natural"
        ),
        Index("ix_spd_date", "trade_date"),
        CheckConstraint("close IS NULL OR close >= 0", name="spd_close_nonneg"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    security_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("security_master.security_id"))
    trade_date: Mapped[date] = mapped_column(Date)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    total_return_factor: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    split_factor: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    dividend_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(Text, default="USD", server_default="USD")
    exchange: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    source_record_id: Mapped[str | None] = mapped_column(Text)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )
    data_version: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SecurityMarketSnapshot(Base):
    """Point-in-time eligibility & exposure inputs (price, shares, market cap,
    liquidity) that activate the Phase-1 PENDING universe filters. Values are
    as-of; never today's shares projected back, never fabricated."""

    __tablename__ = "security_market_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "security_id", "snapshot_date", "source", "data_version", name="uq_sms_natural"
        ),
        Index("ix_sms_date", "snapshot_date"),
        CheckConstraint("market_cap IS NULL OR market_cap >= 0", name="sms_mktcap_nonneg"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    security_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("security_master.security_id"))
    snapshot_date: Mapped[date] = mapped_column(Date)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    shares_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    average_dollar_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    exchange: Mapped[str | None] = mapped_column(Text)
    security_type: Mapped[SecurityType | None] = mapped_column(
        _text_enum(SecurityType, "security_type_e")
    )
    sector: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )
    data_version: Mapped[str] = mapped_column(Text)


class BenchmarkReturnDaily(Base):
    """Daily total return for a benchmark (market or a sector). `benchmark_key`
    is 'MARKET' or 'SECTOR:<gics sector>'. Feeds benchmark- and sector-relative
    forward returns. Identity-neutral (not per security)."""

    __tablename__ = "benchmark_return_daily"
    __table_args__ = (
        UniqueConstraint(
            "benchmark_key", "trade_date", "source", "data_version", name="uq_brd_natural"
        ),
        Index("ix_brd_date", "trade_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    benchmark_key: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)  # 'market' | 'sector'
    trade_date: Mapped[date] = mapped_column(Date)
    total_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    source: Mapped[str] = mapped_column(Text)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )
    data_version: Mapped[str] = mapped_column(Text)


class SecurityReturnDaily(Base):
    """Canonical daily total-return outcome under `security_id`. `return_status`
    distinguishes normal / corporate-action / delisting / terminal / missing /
    unresolved so a delisting is never silently a gap and never assumed zero."""

    __tablename__ = "security_return_daily"
    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "trade_date",
            "source",
            "data_version",
            "calculation_version",
            name="uq_srd_natural",
        ),
        Index("ix_srd_date", "trade_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    security_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("security_master.security_id"))
    trade_date: Mapped[date] = mapped_column(Date)
    price_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    dividend_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    delisting_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    total_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    return_status: Mapped[ReturnStatus] = mapped_column(_text_enum(ReturnStatus, "return_status_e"))
    source: Mapped[str] = mapped_column(Text)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )
    data_version: Mapped[str] = mapped_column(Text)
    calculation_version: Mapped[str] = mapped_column(Text)


class TerminalOutcome(Base):
    """Explicit terminal (delisting/M&A/bankruptcy) valuation for a security.
    Complements Phase-1 `delisting_event`; records the deterministic RULE used,
    the resulting investor value, its source and confidence — never fabricated,
    never zero-assumed. UNKNOWN rule ⇒ unresolved (the observation survives)."""

    __tablename__ = "terminal_outcome"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="terminal_confidence_unit",
        ),
    )

    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("security_master.security_id"), primary_key=True
    )
    event_date: Mapped[date] = mapped_column(Date)
    rule: Mapped[TerminalRule] = mapped_column(_text_enum(TerminalRule, "terminal_rule_e"))
    terminal_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    terminal_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    cash_consideration: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    successor_security_id: Mapped[int | None] = mapped_column(BigInteger)
    resolved: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    confidence: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(Text)
    dq_status: Mapped[IssueStatus] = mapped_column(
        _text_enum(IssueStatus, "issue_status_e"),
        default=IssueStatus.OPEN,
        server_default="open",
    )
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )
    data_version: Mapped[str] = mapped_column(Text)
    calculation_version: Mapped[str] = mapped_column(Text)


class ForwardReturn(Base):
    """Reproducible forward outcome per (security_id, as_of_date, horizon). The
    generator NEVER discards an observation for lack of a normal exit price:
    delisting/terminal outcomes fill the exit, and an unknown terminal outcome is
    recorded as `unresolved`. Carries the full integrity stamp set."""

    __tablename__ = "forward_return"
    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "as_of_date",
            "horizon",
            "snapshot_checksum",
            name="uq_fwd_natural",
        ),
        Index("ix_fwd_asof", "as_of_date", "horizon"),
        CheckConstraint(
            "exit_date IS NULL OR entry_date IS NULL OR exit_date >= entry_date",
            name="fwd_exit_after_entry",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    security_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("security_master.security_id"))
    as_of_date: Mapped[date] = mapped_column(Date)
    horizon: Mapped[str] = mapped_column(Text)
    entry_date: Mapped[date | None] = mapped_column(Date)
    exit_date: Mapped[date | None] = mapped_column(Date)
    absolute_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    benchmark_relative_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    sector_relative_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    residual_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))  # deferred (Phase 2B+)
    terminal_event_flag: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    delisting_in_window_flag: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    outcome_status: Mapped[OutcomeStatus] = mapped_column(
        _text_enum(OutcomeStatus, "outcome_status_e")
    )
    # -- research integrity stamps (Stage 7) --
    identity_world: Mapped[IdentityWorld] = mapped_column(
        _text_enum(IdentityWorld, "identity_world_e"),
        default=IdentityWorld.NATIVE_SECURITY,
        server_default="native_security",
    )
    calculation_version: Mapped[str] = mapped_column(Text)
    universe_version: Mapped[str | None] = mapped_column(Text)
    snapshot_checksum: Mapped[str] = mapped_column(Text)
    source_data_version: Mapped[str] = mapped_column(Text)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ingestion_runs.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchDatasetSnapshot(Base):
    """Immutable, reproducible research-ready dataset. A FROZEN snapshot may never
    be mutated; rebuilding from the same inputs yields the same `snapshot_checksum`.
    `identity_world`/`feature_world`/`outcome_world` are persisted explicitly so a
    consumer never infers the world from a table name (Stage 7)."""

    __tablename__ = "research_dataset_snapshot"
    __table_args__ = (
        UniqueConstraint("snapshot_name", "snapshot_version", name="uq_rds_name_ver"),
    )

    snapshot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    snapshot_name: Mapped[str] = mapped_column(Text)
    snapshot_version: Mapped[int] = mapped_column(Integer)
    universe_definition_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("universe_definition.universe_definition_id")
    )
    universe_version: Mapped[str | None] = mapped_column(Text)
    identity_world: Mapped[IdentityWorld] = mapped_column(
        _text_enum(IdentityWorld, "identity_world_e")
    )
    feature_world: Mapped[IdentityWorld | None] = mapped_column(
        _text_enum(IdentityWorld, "feature_world_e")
    )
    outcome_world: Mapped[IdentityWorld] = mapped_column(
        _text_enum(IdentityWorld, "outcome_world_e")
    )
    data_version: Mapped[str] = mapped_column(Text)
    code_sha: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    security_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    date_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    manifest_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    snapshot_checksum: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SnapshotStatus] = mapped_column(
        _text_enum(SnapshotStatus, "snapshot_status_e"),
        default=SnapshotStatus.DRAFT,
        server_default="draft",
    )


class ExperimentRun(Base):
    """Execution-level provenance for one experiment run. The definition-level
    registry (`research/experiments/registry.py`) says WHAT an experiment is;
    this says that it RAN, against which exact inputs, with what integrity stamps
    — so every research result traces to one immutable execution record."""

    __tablename__ = "experiment_run"
    __table_args__ = (
        UniqueConstraint("experiment_id", "run_number", name="uq_exprun_experiment_number"),
        Index("ix_exprun_experiment", "experiment_id", "started_at"),
    )

    experiment_run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(Text)
    run_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[ExperimentRunStatus] = mapped_column(
        _text_enum(ExperimentRunStatus, "experiment_run_status_e"),
        default=ExperimentRunStatus.RUNNING,
        server_default="running",
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    identity_world: Mapped[IdentityWorld] = mapped_column(
        _text_enum(IdentityWorld, "identity_world_e")
    )
    signal_version: Mapped[str | None] = mapped_column(Text)
    feature_version: Mapped[str | None] = mapped_column(Text)
    outcome_version: Mapped[str | None] = mapped_column(Text)
    universe_version: Mapped[str | None] = mapped_column(Text)
    snapshot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("research_dataset_snapshot.snapshot_id")
    )
    snapshot_checksum: Mapped[str | None] = mapped_column(Text)
    data_version: Mapped[str | None] = mapped_column(Text)
    code_sha: Mapped[str | None] = mapped_column(Text)
    configuration_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    pre_registration_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    kill_criteria_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExperimentRunMetric(Base):
    __tablename__ = "experiment_run_metric"
    __table_args__ = (Index("ix_exprunmetric_run", "experiment_run_id", "metric_name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    experiment_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("experiment_run.experiment_run_id")
    )
    metric_name: Mapped[str] = mapped_column(Text)
    horizon: Mapped[str | None] = mapped_column(Text)
    segment: Mapped[str | None] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Float)
    confidence_lower: Mapped[float | None] = mapped_column(Float)
    confidence_upper: Mapped[float | None] = mapped_column(Float)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    effective_sample_size: Mapped[float | None] = mapped_column(Float)
    calculation_version: Mapped[str | None] = mapped_column(Text)


class ExperimentRunDecision(Base):
    __tablename__ = "experiment_run_decision"

    experiment_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("experiment_run.experiment_run_id"), primary_key=True
    )
    decision: Mapped[ExperimentDecision] = mapped_column(
        _text_enum(ExperimentDecision, "experiment_decision_e")
    )
    decision_reason: Mapped[str | None] = mapped_column(Text)
    promotion_gate_results_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer: Mapped[str | None] = mapped_column(Text)
    knowledge_update_reference: Mapped[str | None] = mapped_column(Text)


class FeatureParityRecord(Base):
    """Parity track 1 — computation equivalence. One recorded comparison of a
    feature computed by the legacy vs native code path on IDENTICAL inputs; an
    unexplained mismatch beyond tolerance fails (`passed=False`)."""

    __tablename__ = "feature_parity_record"
    __table_args__ = (Index("ix_fpr_feature", "feature_name", "passed"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    feature_name: Mapped[str] = mapped_column(Text)
    feature_version: Mapped[str | None] = mapped_column(Text)
    fixture_key: Mapped[str] = mapped_column(Text)  # identifies the shared input fixture
    legacy_value: Mapped[float | None] = mapped_column(Float)
    native_value: Mapped[float | None] = mapped_column(Float)
    absolute_difference: Mapped[float | None] = mapped_column(Float)
    tolerance: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    passed: Mapped[bool] = mapped_column(Boolean)
    detail: Mapped[str | None] = mapped_column(Text)
    calculation_version: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataDivergenceRecord(Base):
    """Parity track 2 — data divergence characterization. A legacy-vs-native
    value difference attributed to a cause. `review_status=unexplained` (or an
    UNKNOWN class) is material-divergence-until-explained and BLOCKS promotion."""

    __tablename__ = "data_divergence_record"
    __table_args__ = (Index("ix_ddr_review", "divergence_class", "review_status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    security_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("security_master.security_id")
    )
    observation_date: Mapped[date | None] = mapped_column(Date)
    feature_name: Mapped[str | None] = mapped_column(Text)
    legacy_value: Mapped[float | None] = mapped_column(Float)
    native_value: Mapped[float | None] = mapped_column(Float)
    absolute_difference: Mapped[float | None] = mapped_column(Float)
    relative_difference: Mapped[float | None] = mapped_column(Float)
    divergence_class: Mapped[DivergenceClass] = mapped_column(
        _text_enum(DivergenceClass, "divergence_class_e")
    )
    explanation: Mapped[str | None] = mapped_column(Text)
    source_lineage: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    review_status: Mapped[ParityReviewStatus] = mapped_column(
        _text_enum(ParityReviewStatus, "parity_review_status_e"),
        default=ParityReviewStatus.UNREVIEWED,
        server_default="unreviewed",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
