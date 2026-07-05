"""Validation: contract checks and quality rules with severity tiers
(prices and macro observations share the machinery).

error   -> row is quarantined (excluded from fact tables, ledgered in
           data_quality_issues, written to the .rejected.csv sidecar)
warning -> row loads, issue ledgered
Frame-level findings (stale closes, frequency mismatch) are warnings
attached to the symbol/series.

A rule hit whose (rule, date) appears in `accepted` — a human marked the
prior issue ACCEPTED via `mip quality accept` — is suppressed entirely:
the row loads and is not re-flagged (D15).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import pandas as pd

from mip.domain.enums import IssueSeverity
from mip.providers.base import MACRO_COLUMNS, PRICE_COLUMNS

# Rule names (stable identifiers; they appear in data_quality_issues.rule)
RULE_MISSING_COLUMNS = "contract_missing_columns"
RULE_DUPLICATE_DATE = "duplicate_date"
RULE_NONPOSITIVE_CLOSE = "nonpositive_close"
RULE_OHLC_INCOHERENT = "ohlc_incoherent"
RULE_NEGATIVE_VOLUME = "negative_volume"
RULE_RETURN_JUMP = "return_jump_no_corp_action"
RULE_ZERO_VOLUME = "zero_volume"
RULE_STALE_CLOSES = "stale_closes"
RULE_CALENDAR_GAP = "calendar_gap"  # emitted by the service (needs DB state)
RULE_VALUE_OUT_OF_RANGE = "value_out_of_range"
RULE_FREQUENCY_MISMATCH = "frequency_mismatch"
RULE_MISSING_PERIODS = "missing_periods"
RULE_STALE_SERIES = "stale_series"  # emitted by the service (needs today())

# Longest plausible gap between consecutive observations, per frequency.
_MAX_GAP_DAYS = {"D": 10, "W": 21, "M": 45, "Q": 120}


@dataclass(frozen=True)
class RowFinding:
    entity_date: date
    rule: str
    severity: IssueSeverity
    observed: str


@dataclass(frozen=True)
class FrameFinding:
    rule: str
    severity: IssueSeverity
    observed: str
    detail: dict[str, object]


@dataclass
class ValidationReport:
    valid: pd.DataFrame  # rows allowed into daily_prices
    rejected: pd.DataFrame  # quarantined rows (with 'rule' column)
    row_findings: list[RowFinding] = field(default_factory=list)
    frame_findings: list[FrameFinding] = field(default_factory=list)


def validate_prices(
    frame: pd.DataFrame,
    *,
    split_dates: set[date],
    accepted: set[tuple[str, date]],
    prior_close: Decimal | None = None,
    return_jump_threshold: float = 0.40,
    stale_run_length: int = 5,
) -> ValidationReport:
    """Apply the Phase 2 price rules; split rows into valid vs quarantined."""
    if frame.empty:
        return ValidationReport(valid=frame, rejected=frame.head(0))

    missing = [c for c in PRICE_COLUMNS if c not in frame.columns]
    if missing:
        # Contract violation: nothing in this frame is trustworthy.
        finding = FrameFinding(
            rule=RULE_MISSING_COLUMNS,
            severity=IssueSeverity.ERROR,
            observed=f"missing columns: {missing}",
            detail={"missing": missing},
        )
        return ValidationReport(
            valid=frame.head(0),
            rejected=frame.assign(rule=RULE_MISSING_COLUMNS),
            frame_findings=[finding],
        )

    frame = frame.sort_values("price_date").reset_index(drop=True)
    findings: list[RowFinding] = []
    error_rules: dict[int, str] = {}  # row position -> quarantining rule

    def flag(pos: int, rule: str, severity: IssueSeverity, observed: str) -> None:
        row_date = frame.at[pos, "price_date"]
        if (rule, row_date) in accepted:
            return  # human-accepted: suppress and let the row load
        findings.append(RowFinding(row_date, rule, severity, observed))
        if severity is IssueSeverity.ERROR:
            error_rules.setdefault(pos, rule)

    # duplicate dates: keep the first, quarantine the rest
    dupes = frame.duplicated(subset="price_date", keep="first")
    for pos in frame.index[dupes]:
        flag(pos, RULE_DUPLICATE_DATE, IssueSeverity.ERROR, str(frame.at[pos, "price_date"]))

    prev_close: float | None = float(prior_close) if prior_close is not None else None
    for pos in frame.index:
        close = frame.at[pos, "close"]
        high, low = frame.at[pos, "high"], frame.at[pos, "low"]
        open_, volume = frame.at[pos, "open"], frame.at[pos, "volume"]

        if pd.isna(close) or close <= 0:
            flag(pos, RULE_NONPOSITIVE_CLOSE, IssueSeverity.ERROR, f"close={close}")
        elif pd.notna(high) and pd.notna(low):
            coherent = (
                high >= low and (pd.isna(open_) or low <= open_ <= high) and low <= close <= high
            )
            if not coherent:
                flag(
                    pos,
                    RULE_OHLC_INCOHERENT,
                    IssueSeverity.ERROR,
                    f"o={open_} h={high} l={low} c={close}",
                )

        if pd.notna(volume):
            if volume < 0:
                flag(pos, RULE_NEGATIVE_VOLUME, IssueSeverity.ERROR, f"volume={volume}")
            elif volume == 0:
                flag(pos, RULE_ZERO_VOLUME, IssueSeverity.WARNING, "volume=0")

        # Return jump without a matching corporate action: the single rule
        # that catches most bad ticks and unadjusted splits.
        if (
            prev_close is not None
            and pd.notna(close)
            and close > 0
            and prev_close > 0
            and pos not in error_rules
        ):
            change = abs(float(close) / prev_close - 1.0)
            if change > return_jump_threshold and frame.at[pos, "price_date"] not in split_dates:
                flag(
                    pos,
                    RULE_RETURN_JUMP,
                    IssueSeverity.ERROR,
                    f"return={change:+.1%} prev_close={prev_close} close={close}",
                )
        if pd.notna(close) and pos not in error_rules:
            prev_close = float(close)

    # stale closes: N identical consecutive closes (frame-level warning)
    frame_findings: list[FrameFinding] = []
    run_start, run_len = 0, 1
    closes = frame["close"].tolist()
    for i in range(1, len(closes) + 1):
        if i < len(closes) and pd.notna(closes[i]) and closes[i] == closes[i - 1]:
            run_len += 1
            continue
        if run_len >= stale_run_length:
            first = frame.at[run_start, "price_date"]
            last = frame.at[i - 1, "price_date"]
            frame_findings.append(
                FrameFinding(
                    rule=RULE_STALE_CLOSES,
                    severity=IssueSeverity.WARNING,
                    observed=f"close={closes[run_start]} for {run_len} sessions",
                    detail={"from": str(first), "to": str(last), "sessions": run_len},
                )
            )
        run_start, run_len = i, 1

    quarantined_mask = frame.index.isin(error_rules)
    rejected = frame[quarantined_mask].copy()
    if not rejected.empty:
        rejected["rule"] = [error_rules[pos] for pos in frame.index[quarantined_mask]]
    valid = frame[~quarantined_mask].copy()

    return ValidationReport(
        valid=valid, rejected=rejected, row_findings=findings, frame_findings=frame_findings
    )


def _period_key(day: date, frequency: str) -> tuple[int, ...]:
    if frequency == "M":
        return (day.year, day.month)
    if frequency == "Q":
        return (day.year, (day.month - 1) // 3)
    return (day.year, day.month, day.day)  # D/W: dates are their own period


def validate_macro(
    frame: pd.DataFrame,
    *,
    frequency: str,
    accepted: set[tuple[str, date]],
    min_value: float | None = None,
    max_value: float | None = None,
) -> ValidationReport:
    """Apply the Phase 3 macro rules; split rows into valid vs quarantined.

    NaN values are legitimate (FRED '.') and pass through to be stored as
    NULL — never zero, never quarantined."""
    if frame.empty:
        return ValidationReport(valid=frame, rejected=frame.head(0))

    missing = [c for c in MACRO_COLUMNS if c not in frame.columns]
    if missing:
        finding = FrameFinding(
            rule=RULE_MISSING_COLUMNS,
            severity=IssueSeverity.ERROR,
            observed=f"missing columns: {missing}",
            detail={"missing": missing},
        )
        return ValidationReport(
            valid=frame.head(0),
            rejected=frame.assign(rule=RULE_MISSING_COLUMNS),
            frame_findings=[finding],
        )

    frame = frame.sort_values("obs_date").reset_index(drop=True)
    findings: list[RowFinding] = []
    error_rules: dict[int, str] = {}

    def flag(pos: int, rule: str, severity: IssueSeverity, observed: str) -> None:
        row_date = frame.at[pos, "obs_date"]
        if (rule, row_date) in accepted:
            return
        findings.append(RowFinding(row_date, rule, severity, observed))
        if severity is IssueSeverity.ERROR:
            error_rules.setdefault(pos, rule)

    dupes = frame.duplicated(subset="obs_date", keep="first")
    for pos in frame.index[dupes]:
        flag(pos, RULE_DUPLICATE_DATE, IssueSeverity.ERROR, str(frame.at[pos, "obs_date"]))

    for pos in frame.index:
        value = frame.at[pos, "value"]
        if pd.isna(value):
            continue  # published-but-missing: stored as NULL
        below = min_value is not None and value < min_value
        above = max_value is not None and value > max_value
        if below or above:
            flag(
                pos,
                RULE_VALUE_OUT_OF_RANGE,
                IssueSeverity.ERROR,
                f"value={value} outside [{min_value}, {max_value}]",
            )

    frame_findings: list[FrameFinding] = []

    # frequency conformity: two observations inside one reference period
    if frequency in ("M", "Q"):
        periods = [_period_key(d, frequency) for d in frame["obs_date"]]
        clashes = len(periods) - len(set(periods))
        if clashes:
            frame_findings.append(
                FrameFinding(
                    rule=RULE_FREQUENCY_MISMATCH,
                    severity=IssueSeverity.WARNING,
                    observed=f"{clashes} extra observation(s) for a {frequency} series",
                    detail={"extra_observations": clashes, "frequency": frequency},
                )
            )

    # missing periods: implausibly long gaps between consecutive observations
    max_gap = _MAX_GAP_DAYS.get(frequency, 45)
    dates = list(frame["obs_date"])
    gaps = [
        (str(a), str(b), (b - a).days)
        for a, b in zip(dates, dates[1:], strict=False)
        if (b - a).days > max_gap
    ]
    if gaps:
        frame_findings.append(
            FrameFinding(
                rule=RULE_MISSING_PERIODS,
                severity=IssueSeverity.WARNING,
                observed=f"{len(gaps)} gap(s) longer than {max_gap} days",
                detail={"gaps": gaps[:10], "total": len(gaps)},
            )
        )

    quarantined_mask = frame.index.isin(error_rules)
    rejected = frame[quarantined_mask].copy()
    if not rejected.empty:
        rejected["rule"] = [error_rules[pos] for pos in frame.index[quarantined_mask]]
    valid = frame[~quarantined_mask].copy()

    return ValidationReport(
        valid=valid, rejected=rejected, row_findings=findings, frame_findings=frame_findings
    )


RULE_NEGATIVE_FUNDAMENTAL = "negative_fundamental"
RULE_MARKETCAP_INCONSISTENT = "marketcap_price_shares_mismatch"
RULE_SHARES_JUMP = "shares_outstanding_jump"

_NON_NEGATIVE_FIELDS = ("market_cap", "shares_outstanding", "revenue_ttm", "dividend_yield")
_MARKETCAP_TOLERANCE = 0.15  # |mcap - close*shares| / mcap
_SHARES_JUMP_THRESHOLD = 0.5  # >50% change vs prior snapshot without a split


@dataclass(frozen=True)
class FundamentalFinding:
    field: str
    rule: str
    severity: IssueSeverity
    observed: str


def validate_fundamentals(
    snapshot: dict[str, float | None],
    *,
    prior_shares: int | None = None,
    latest_close: Decimal | None = None,
    had_recent_split: bool = False,
) -> tuple[dict[str, float | None], list[FundamentalFinding]]:
    """Field-level cleaning: an invalid field is nulled and ledgered; the
    snapshot itself is NEVER quarantined (missing fields are normal for
    yfinance). Cross-field checks are warnings on stored values."""
    cleaned = dict(snapshot)
    findings: list[FundamentalFinding] = []

    for field_name in _NON_NEGATIVE_FIELDS:
        value = cleaned.get(field_name)
        if value is not None and value < 0:
            findings.append(
                FundamentalFinding(
                    field=field_name,
                    rule=RULE_NEGATIVE_FUNDAMENTAL,
                    severity=IssueSeverity.ERROR,
                    observed=f"{field_name}={value}",
                )
            )
            cleaned[field_name] = None  # field nulled, snapshot kept

    # Unit-error tripwire: market cap should agree with price * shares.
    market_cap, shares = cleaned.get("market_cap"), cleaned.get("shares_outstanding")
    if market_cap and shares and latest_close is not None and market_cap > 0:
        implied = float(latest_close) * shares
        drift = abs(market_cap - implied) / market_cap
        if drift > _MARKETCAP_TOLERANCE:
            findings.append(
                FundamentalFinding(
                    field="market_cap",
                    rule=RULE_MARKETCAP_INCONSISTENT,
                    severity=IssueSeverity.WARNING,
                    observed=(
                        f"market_cap={market_cap:.0f} vs close*shares={implied:.0f} "
                        f"(drift {drift:.0%})"
                    ),
                )
            )

    if shares and prior_shares and not had_recent_split:
        change = abs(shares - prior_shares) / prior_shares
        if change > _SHARES_JUMP_THRESHOLD:
            findings.append(
                FundamentalFinding(
                    field="shares_outstanding",
                    rule=RULE_SHARES_JUMP,
                    severity=IssueSeverity.WARNING,
                    observed=f"shares {prior_shares} -> {shares} ({change:+.0%})",
                )
            )

    return cleaned, findings
