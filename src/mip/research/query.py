"""Research query vocabulary: filters, window, and the query itself.

A query is declarative data — no SQL, no pandas — so it can be built from
the CLI, from tests, or (later) from intelligence models, and echoed back
verbatim in results for reproducibility.
"""

import operator
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from mip.core.exceptions import ConfigurationError

DEFAULT_HORIZONS: tuple[int, ...] = (1, 5, 21, 63, 126, 252)

OPERATORS: dict[str, Callable[[float, float], bool]] = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}


class SampleMode(StrEnum):
    EVENTS = "events"  # first day of each matching episode (independent samples)
    ALL = "all"  # every matching day (overlapping forward windows)


@dataclass(frozen=True)
class ResearchFilter:
    """One condition on one feature. `symbol` overrides which instrument the
    feature is read for (e.g. condition on XLK's rel_ret_spy_21d while
    studying AMD); None = the query's target for instrument-scoped features,
    ignored for market-scoped ones."""

    feature: str
    op: str
    value: float
    symbol: str | None = None

    def __post_init__(self) -> None:
        if self.op not in OPERATORS:
            raise ConfigurationError(
                f"unknown operator {self.op!r}; supported: {sorted(OPERATORS)}"
            )

    def describe(self) -> str:
        prefix = f"{self.symbol}:" if self.symbol else ""
        return f"{prefix}{self.feature} {self.op} {self.value:g}"


@dataclass(frozen=True)
class ResearchWindow:
    """Bounds the CONDITION dates. Forward outcomes are computed only from
    prices observable by `end` (point-in-time alignment): windows that
    would cross `end` yield NaN and shrink samples honestly, identical
    to live evaluation on that date."""

    start: date | None = None
    end: date | None = None


@dataclass(frozen=True)
class ResearchQuery:
    symbol: str
    filters: tuple[ResearchFilter, ...]
    window: ResearchWindow = field(default_factory=ResearchWindow)
    horizons: tuple[int, ...] = DEFAULT_HORIZONS
    mode: SampleMode = SampleMode.EVENTS

    def __post_init__(self) -> None:
        if not self.filters:
            raise ConfigurationError("a research query needs at least one filter")
        if not self.horizons or any(h < 1 for h in self.horizons):
            raise ConfigurationError(f"horizons must be positive sessions: {self.horizons}")

    def describe(self) -> str:
        parts = " AND ".join(f.describe() for f in self.filters)
        return f"{self.symbol} where {parts} [{self.mode.value}]"


def parse_filter(text: str) -> ResearchFilter:
    """Parse 'vix_level > 25' or 'XLK:rel_ret_spy_21d > 0' (CLI syntax).
    Longest operators first so '>=' is not read as '>'."""
    for op in sorted(OPERATORS, key=len, reverse=True):
        left, sep, right = text.partition(op)
        if not sep:
            continue
        name = left.strip()
        symbol: str | None = None
        if ":" in name:
            symbol, _, name = name.partition(":")
            symbol = symbol.strip().upper()
        if not name:
            break
        try:
            value = float(right.strip())
        except ValueError as exc:
            raise ConfigurationError(f"filter value is not a number: {text!r}") from exc
        return ResearchFilter(feature=name, op=op, value=value, symbol=symbol)
    raise ConfigurationError(
        f"cannot parse filter {text!r}; expected '<feature> <op> <value>' "
        f"with op in {sorted(OPERATORS)}"
    )
