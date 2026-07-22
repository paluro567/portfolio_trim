"""Revision detection (D12): diff re-fetched overlap rows against stored
rows using field-specific materiality tolerances.

Yahoo recomputes the split/dividend factor product behind adj_close
continuously, so consecutive fetches of the SAME history differ in the
low-order bits (measured 2026-07-20: up to ~5.4e-7 relative across
2010-2026 history within 35 minutes, while raw OHLC was byte-identical).
Exact comparison therefore manufactures thousands of false revisions per
symbol. The materiality gate separates that float noise from genuine
signals — see docs/PRICES.md §2 for the measured justification:

- provider factor noise:            <= ~5.4e-7 relative (measured)
- smallest genuine dividend signal: ~5.5e-5 relative ($0.01 on ~$180)
- REL_TOLERANCE = 1e-5: >=18x above noise, >=5x below smallest signal
- ABS_FLOOR = 2e-6 (two storage quanta) protects sub-dollar prices

Volume compares exactly; NULL<->value transitions are always material.
An adj_close difference on a completed historical session with raw close
unchanged is the corporate-action tripwire — the provider re-adjusted
history — and triggers a full-history refresh (policy in docs/PRICES.md
§3, enforced by the ingestion service).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd

from mip.domain.models import DailyPrice

REVISION_FIELDS = ("open", "high", "low", "close", "adj_close", "volume")
_QUANTUM = Decimal("0.000001")  # NUMERIC(18,6) storage precision
REL_TOLERANCE = Decimal("0.00001")  # 1e-5 relative materiality for price fields
ABS_FLOOR = Decimal("0.000002")  # two storage quanta


@dataclass(frozen=True)
class RevisionDiff:
    price_date: date
    field: str
    old_value: str | None
    new_value: str | None
    abs_diff: str | None = None  # decimal string; None for volume/NULL transitions
    rel_diff: str | None = None
    tolerance: str | None = None


def to_decimal(value: object) -> Decimal | None:
    """Incoming float -> Decimal at storage precision (None for NaN)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return Decimal(str(value)).quantize(_QUANTUM)


def to_volume(value: object) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return int(value)


def price_tolerance(old: Decimal) -> Decimal:
    return max(ABS_FLOOR, abs(old) * REL_TOLERANCE)


def diff_price_row(stored: DailyPrice, incoming: pd.Series) -> list[RevisionDiff]:
    """Material field-level differences between a stored row and its
    re-fetched value. Sub-tolerance float noise produces no diff at all:
    no revision record, no update, no rewrite of the stored value."""
    diffs: list[RevisionDiff] = []
    for field in REVISION_FIELDS:
        if field == "volume":
            old: object = stored.volume
            new: object = to_volume(incoming["volume"])
            if old != new:
                diffs.append(_diff(stored.price_date, field, old, new))
            continue
        stored_value = getattr(stored, field)
        old = stored_value.quantize(_QUANTUM) if stored_value is not None else None
        new = to_decimal(incoming[field])
        if old is None or new is None:
            if old != new:  # NULL<->value transitions are always material
                diffs.append(_diff(stored.price_date, field, old, new))
            continue
        abs_diff = abs(new - old)
        if abs_diff == 0:
            continue
        tolerance = price_tolerance(old)
        if abs_diff <= tolerance:
            continue  # provider float jitter, not a revision
        rel = abs_diff / abs(old) if old else None
        diffs.append(
            RevisionDiff(
                price_date=stored.price_date,
                field=field,
                old_value=str(old),
                new_value=str(new),
                abs_diff=str(abs_diff),
                rel_diff=f"{rel:.3e}" if rel is not None else None,
                tolerance=str(tolerance),
            )
        )
    return diffs


def _diff(price_date: date, field: str, old: object, new: object) -> RevisionDiff:
    return RevisionDiff(
        price_date=price_date,
        field=field,
        old_value=str(old) if old is not None else None,
        new_value=str(new) if new is not None else None,
    )
