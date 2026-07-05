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
