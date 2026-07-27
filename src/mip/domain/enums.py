"""Domain enumerations."""

from enum import StrEnum


class InstrumentType(StrEnum):
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"


class RunType(StrEnum):
    PRICES = "prices"
    MACRO = "macro"
    FUNDAMENTALS = "fundamentals"
    EARNINGS = "earnings"
    FEATURES = "features"
    SNAPSHOTS = "snapshots"
    UPDATE = "update"  # daily orchestrator envelope run
    PORTFOLIO_IMPORT = "portfolio_import"
    SECURITIES = "securities"  # Phase-1 survivorship-clean security-master ingest
    UNIVERSE = "universe"  # Phase-1 point-in-time universe reconstruction
    BRIDGE = "bridge"  # Phase-2A instrument_id <-> security_id map ingest
    RESEARCH_PRICES = "research_prices"  # Phase-2A native security_id price/market ingest
    RESEARCH_OUTCOMES = "research_outcomes"  # Phase-2A native return/forward-outcome build
    RESEARCH_SNAPSHOT = "research_snapshot"  # Phase-2A immutable research dataset build
    EXPERIMENT = "experiment"  # Phase-2A execution-level experiment run


# -- Phase 1: point-in-time security master & universe integrity ---------------


class SecurityType(StrEnum):
    """Economic security type. The universe policy decides which are eligible;
    ADRs are labelled explicitly rather than silently mixed with common stock."""

    COMMON = "common"  # ordinary common equity
    ADR = "adr"
    ETF = "etf"
    PREFERRED = "preferred"
    WARRANT = "warrant"
    RIGHT = "right"
    UNIT = "unit"
    CLOSED_END_FUND = "closed_end_fund"
    REIT = "reit"
    OTHER = "other"


class IdentifierType(StrEnum):
    """Kinds of external identifier tracked through time. A ticker is NEVER the
    permanent identity — it is one time-bounded identifier among several."""

    TICKER = "ticker"
    COMPOSITE_TICKER = "composite_ticker"  # e.g. 'AAPL US'
    CUSIP = "cusip"
    ISIN = "isin"
    FIGI = "figi"
    VENDOR_ID = "vendor_id"


class LifecycleEventType(StrEnum):
    LISTED = "listed"
    DELISTED = "delisted"
    ACQUIRED = "acquired"
    MERGED = "merged"
    BANKRUPT = "bankrupt"
    LIQUIDATED = "liquidated"
    TICKER_CHANGED = "ticker_changed"
    EXCHANGE_CHANGED = "exchange_changed"
    NAME_CHANGED = "name_changed"
    SHARE_CLASS_CHANGED = "share_class_changed"
    REORGANIZED = "reorganized"
    SPUN_OFF = "spun_off"


class UniverseStatus(StrEnum):
    DRAFT = "draft"
    FROZEN = "frozen"  # immutable; historical experiments reference frozen versions only
    RETIRED = "retired"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class IssueSeverity(StrEnum):
    ERROR = "error"  # quarantined: excluded from fact tables
    WARNING = "warning"  # loaded, flagged
    INFO = "info"


class IssueStatus(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"  # human-confirmed real; suppresses re-flagging
    RESOLVED = "resolved"


class CorporateActionType(StrEnum):
    SPLIT = "split"
    DIVIDEND = "dividend"


class FeatureScope(StrEnum):
    INSTRUMENT = "instrument"
    MARKET = "market"


class TxnType(StrEnum):
    """Transaction types. txn_type is a TEXT column per the frozen DDL;
    transfer/opening values extend the documented examples without any
    schema change. OPENING_BALANCE is ALWAYS synthetic — it initializes a
    position when real trade history is unavailable and must never be read
    as an actual historical trade."""

    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    FEE = "fee"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    OPENING_BALANCE = "opening_balance"
    SPLIT = "split"  # reserved by the schema; unsupported in this phase


# Transaction types that open lots / close lots / never touch positions.
POSITION_OPENING_TYPES = (TxnType.BUY, TxnType.TRANSFER_IN, TxnType.OPENING_BALANCE)
POSITION_CLOSING_TYPES = (TxnType.SELL, TxnType.TRANSFER_OUT)
CASH_ONLY_TYPES = (TxnType.DIVIDEND, TxnType.FEE, TxnType.DEPOSIT, TxnType.WITHDRAWAL)


class CostBasisMethod(StrEnum):
    FIFO = "FIFO"
    SPECIFIC_ID = "specific_id"  # reserved by the schema; not yet implemented


class GainTerm(StrEnum):
    SHORT = "short"
    LONG = "long"


# -- Phase 2A: native outcome foundation & migration guardrails -----------------


class IdentityWorld(StrEnum):
    """Which identity/data world a research artifact was computed in. Persisted
    explicitly on every artifact — NEVER inferred from a table name. The whole
    point of the guardrails is that these two worlds may not be silently mixed."""

    LEGACY_INSTRUMENT = "legacy_instrument"  # instrument_id + survivor-biased feed
    NATIVE_SECURITY = "native_security"  # security_id + survivorship-clean feed


class MappingMethod(StrEnum):
    """How an instrument_id<->security_id bridge row was established. Ticker
    equality alone is NOT allowed to establish identity (PIT_TICKER exists only
    to record a legacy row that must be reviewed, never as an auto-merge)."""

    EXACT_SOURCE_ID = "exact_source_id"  # same vendor permanent id on both sides
    PERMANENT_IDENTIFIER = "permanent_identifier"  # CUSIP/ISIN/FIGI match over interval
    MANUAL_OVERRIDE = "manual_override"  # explicit, audited human decision
    PIT_TICKER = "pit_ticker"  # point-in-time ticker resolution (weak; review required)


class MappingStatus(StrEnum):
    ACTIVE = "active"  # trusted, usable for resolution
    QUARANTINED = "quarantined"  # ambiguous/overlapping; never used for resolution
    SUPERSEDED = "superseded"  # replaced by a manual override


class ReturnStatus(StrEnum):
    """The nature of a single day's canonical return."""

    NORMAL = "normal"  # ordinary trading return
    CORPORATE_ACTION = "corporate_action"  # split/dividend adjusted day
    DELISTING = "delisting"  # the delisting day's terminal return
    TERMINAL = "terminal"  # post-terminal-event settlement return
    MISSING = "missing"  # price expected but absent (flagged, not dropped)
    UNRESOLVED = "unresolved"  # terminal event with no known return (never zero-assumed)


class OutcomeStatus(StrEnum):
    """The disposition of a forward-return observation. An observation is NEVER
    silently discarded: absence of a normal exit price yields a status, not a
    deleted row."""

    NORMAL = "normal"  # priced entry and exit
    DELISTED_IN_WINDOW = "delisted_in_window"  # exited via delisting/terminal return
    TERMINATED = "terminated"  # terminal event resolved to investor value
    TRUNCATED = "truncated"  # still listed at the data edge (no exit yet)
    UNRESOLVED = "unresolved"  # terminal event but no known outcome value
    NO_ENTRY_PRICE = "no_entry_price"  # could not be entered (flagged, not dropped)


class TerminalRule(StrEnum):
    """The deterministic rule used to value a terminal event. Recorded on every
    terminal outcome so the treatment is auditable and never fabricated."""

    CASH_ACQUISITION = "cash_acquisition"  # investor cash consideration
    STOCK_ACQUISITION = "stock_acquisition"  # successor share value
    MERGER = "merger"
    BANKRUPTCY = "bankruptcy"  # vendor delisting return / terminal proceeds
    LIQUIDATION = "liquidation"
    STOPPED_TRADING = "stopped_trading"  # ceased before normal exit
    VENDOR_DELISTING_RETURN = "vendor_delisting_return"
    UNKNOWN = "unknown"  # unresolved; NOT assumed to be -100%


class SnapshotStatus(StrEnum):
    DRAFT = "draft"
    FROZEN = "frozen"  # immutable; the only status a research experiment may cite


class ExperimentRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class ExperimentDecision(StrEnum):
    PENDING = "pending"
    PROMOTE = "promote"
    REJECT = "reject"
    HOLD = "hold"  # inconclusive; keep as shadow
    BLOCKED = "blocked"  # blocked by unexplained divergence / failed gate


class DivergenceClass(StrEnum):
    """Classification of a legacy-vs-native value difference (parity track 2).
    UNKNOWN is material-divergence-until-explained and BLOCKS promotion."""

    PRICE_ADJUSTMENT = "price_adjustment"
    DIVIDEND_TREATMENT = "dividend_treatment"
    SPLIT_TREATMENT = "split_treatment"
    DELISTING_INCLUSION = "delisting_inclusion"
    TICKER_HISTORY = "ticker_history"
    VENDOR_RESTATEMENT = "vendor_restatement"
    MISSING_LEGACY_SECURITY = "missing_legacy_security"
    UNIVERSE_DIFFERENCE = "universe_difference"
    CORPORATE_ACTION_CORRECTION = "corporate_action_correction"
    UNKNOWN = "unknown"


class ParityReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    EXPLAINED = "explained"  # attributed to a known, accepted cause
    UNEXPLAINED = "unexplained"  # blocks promotion
    ACCEPTED = "accepted"  # human-confirmed acceptable
