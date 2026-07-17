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
