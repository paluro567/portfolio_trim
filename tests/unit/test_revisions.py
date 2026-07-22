"""Revision materiality (docs/PRICES.md §2): provider float jitter must
produce no diff at all, while genuine adjustments and corrections do — with
absolute/relative/tolerance diagnostics attached. Pure, no database."""

from datetime import date
from decimal import Decimal

import pandas as pd

from mip.domain.models import DailyPrice
from mip.ingestion.revisions import (
    ABS_FLOOR,
    REL_TOLERANCE,
    diff_price_row,
    price_tolerance,
)

D = date(2024, 6, 14)


def stored(**overrides) -> DailyPrice:
    base = dict(
        price_date=D,
        open=Decimal("100.000000"),
        high=Decimal("101.000000"),
        low=Decimal("99.000000"),
        close=Decimal("100.500000"),
        adj_close=Decimal("90.250000"),
        volume=1_000_000,
    )
    base.update(overrides)
    return DailyPrice(**base)


def incoming(**overrides) -> pd.Series:
    base = dict(open=100.0, high=101.0, low=99.0, close=100.5, adj_close=90.25, volume=1_000_000)
    base.update(overrides)
    return pd.Series(base)


def test_identical_row_has_no_diff() -> None:
    assert diff_price_row(stored(), incoming()) == []


def test_sub_tolerance_adj_close_jitter_is_ignored() -> None:
    # 90.25 * 5e-7 ~= 4.5e-5 absolute; well inside the 1e-5-relative gate
    noisy = incoming(adj_close=90.25 + 0.000045)
    assert diff_price_row(stored(), noisy) == []


def test_material_adj_close_readjustment_is_a_diff_with_diagnostics() -> None:
    # a $0.05 dividend back-adjustment on a ~$90 adjusted close
    revised = incoming(adj_close=90.20)
    (diff,) = diff_price_row(stored(), revised)
    assert diff.field == "adj_close"
    assert diff.old_value == "90.250000" and diff.new_value == "90.200000"
    assert Decimal(diff.abs_diff) == Decimal("0.050000")
    assert diff.rel_diff is not None and diff.tolerance is not None
    assert Decimal(diff.tolerance) == price_tolerance(Decimal("90.250000"))


def test_absolute_floor_protects_sub_dollar_prices() -> None:
    # below $0.20 the 2e-6 absolute floor dominates the 1e-5 relative gate
    penny = stored(close=Decimal("0.100000"), adj_close=Decimal("0.100000"))
    assert price_tolerance(Decimal("0.10")) == ABS_FLOOR
    # 1e-6 change on a $0.10 price: below the floor -> noise
    assert diff_price_row(penny, incoming(close=0.100001, adj_close=0.100001)) == []
    # 3e-6 change clears the floor -> material
    diffs = diff_price_row(penny, incoming(close=0.100003, adj_close=0.100003))
    assert {d.field for d in diffs} == {"close", "adj_close"}


def test_volume_compared_exactly_and_null_transitions_are_material() -> None:
    (vol,) = diff_price_row(stored(), incoming(volume=1_000_001))
    assert vol.field == "volume" and vol.abs_diff is None  # exact, no tolerance
    (nulled,) = diff_price_row(stored(adj_close=None), incoming())
    assert nulled.field == "adj_close" and nulled.old_value is None


def test_tolerance_is_relative_above_the_floor() -> None:
    assert price_tolerance(Decimal("1000")) == Decimal("1000") * REL_TOLERANCE
    assert price_tolerance(Decimal("1000")) > ABS_FLOOR
