"""Revision detection (D12): diff re-fetched overlap rows against stored rows.

An adj_close difference is the corporate-action tripwire — the provider has
retroactively re-adjusted history — and triggers a full-history refresh for
the instrument (performed immediately by the ingestion service; there is no
scheduler in Phase 2 by design).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd

from mip.domain.models import DailyPrice

REVISION_FIELDS = ("open", "high", "low", "close", "adj_close", "volume")
_QUANTUM = Decimal("0.000001")  # NUMERIC(18,6) storage precision


@dataclass(frozen=True)
class RevisionDiff:
    price_date: date
    field: str
    old_value: str | None
    new_value: str | None


def to_decimal(value: object) -> Decimal | None:
    """Incoming float -> Decimal at storage precision (None for NaN)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return Decimal(str(value)).quantize(_QUANTUM)


def to_volume(value: object) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return int(value)


def diff_price_row(stored: DailyPrice, incoming: pd.Series) -> list[RevisionDiff]:
    """Field-level differences between a stored row and its re-fetched value."""
    diffs: list[RevisionDiff] = []
    for field in REVISION_FIELDS:
        if field == "volume":
            old: object = stored.volume
            new: object = to_volume(incoming["volume"])
        else:
            stored_value = getattr(stored, field)
            old = stored_value.quantize(_QUANTUM) if stored_value is not None else None
            new = to_decimal(incoming[field])
        if old != new:
            diffs.append(
                RevisionDiff(
                    price_date=stored.price_date,
                    field=field,
                    old_value=str(old) if old is not None else None,
                    new_value=str(new) if new is not None else None,
                )
            )
    return diffs
