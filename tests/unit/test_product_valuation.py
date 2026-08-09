"""Contextual valuation: validity guards, banding, and single-voice behaviour."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from mip.product.contracts import Direction, Evidence, Status
from mip.product.decide import confidence_for, directional_view
from mip.product.slice import VALUATION_HORIZONS
from mip.product.valuation import BANDS, METRICS, MIN_ANY_PEERS, MIN_SECTOR_PEERS, _valid_metrics


def _row(**kw):
    base = dict(
        trailing_pe=Decimal("20"),
        forward_pe=Decimal("18"),
        price_to_book=Decimal("3"),
        market_cap=Decimal("1000"),
        revenue_ttm=Decimal("500"),
        trailing_eps=Decimal("5"),
        forward_eps=Decimal("6"),
    )
    base.update(kw)
    return base


# -- economic validity guards -------------------------------------------------
def test_negative_trailing_earnings_drops_pe():
    v = _valid_metrics(_row(trailing_eps=Decimal("-1")))
    assert "trailing_pe" not in v and "price_to_book" in v


def test_zero_trailing_earnings_drops_pe():
    assert "trailing_pe" not in _valid_metrics(_row(trailing_eps=Decimal("0")))


def test_negative_forward_earnings_drops_forward_pe():
    assert "forward_pe" not in _valid_metrics(_row(forward_eps=Decimal("-2")))


def test_negative_book_value_drops_price_to_book():
    assert "price_to_book" not in _valid_metrics(_row(price_to_book=Decimal("-4")))


def test_price_to_sales_is_derived_not_stored():
    v = _valid_metrics(_row())
    assert v["price_to_sales"] == Decimal("1000") / Decimal("500")


def test_zero_revenue_drops_price_to_sales():
    assert "price_to_sales" not in _valid_metrics(_row(revenue_ttm=Decimal("0")))


def test_company_with_no_valid_multiple_yields_nothing():
    v = _valid_metrics(
        _row(
            trailing_eps=Decimal("-1"),
            forward_eps=Decimal("-1"),
            price_to_book=Decimal("-1"),
            revenue_ttm=Decimal("0"),
        )
    )
    assert v == {}


# -- banding ------------------------------------------------------------------
def test_bands_are_ordered_and_total():
    edges = [e for e, _ in BANDS]
    assert edges == sorted(edges) and edges[-1] > Decimal("1")


def test_band_labels():
    def band(p):
        return next(label for edge, label in BANDS if p < edge)

    assert band(Decimal("0.03")) == "CHEAP"
    assert band(Decimal("0.30")) == "BELOW NORMAL"
    assert band(Decimal("0.50")) == "NORMAL"
    assert band(Decimal("0.70")) == "ABOVE NORMAL"
    assert band(Decimal("0.95")) == "EXPENSIVE"


def test_peer_minimums_are_enforced_constants():
    assert MIN_SECTOR_PEERS >= 5 and MIN_ANY_PEERS >= 5


# -- single voice, no double counting ----------------------------------------
def _val(direction):
    return Evidence(
        "valuation_position",
        "valuation",
        Status.DESCRIPTIVE,
        "EXPENSIVE (87%)",
        "company_fundamentals",
        date(2026, 8, 7),
        VALUATION_HORIZONS,
        "e",
        "l",
        direction=direction,
        group="valuation_level",
    )


def test_valuation_is_one_item_not_four():
    """Four multiples inform one item; they never vote separately."""
    assert len(METRICS) == 4
    direction, detail, _ = directional_view([_val(Direction.NEGATIVE)], "1y")
    assert direction is Direction.NEGATIVE
    assert len([d for d in detail if d.startswith("[")]) == 1


def test_valuation_disagreeing_with_momentum_is_conflicted():
    mom = replace(
        Evidence(
            "ret_252d",
            "price/technical",
            Status.DESCRIPTIVE,
            "+1",
            "f",
            date(2026, 8, 7),
            ("6m", "1y"),
            "e",
            "l",
            direction=Direction.POSITIVE,
        ),
        group="absolute_momentum",
    )
    assert directional_view([mom, _val(Direction.NEGATIVE)], "1y")[0] is Direction.CONFLICTED


def test_valuation_absent_from_short_horizons():
    """Valuation is a level, not a timing signal."""
    assert VALUATION_HORIZONS == ("6m", "1y")
    assert directional_view([_val(Direction.NEGATIVE)], "1w")[0] is Direction.UNAVAILABLE


def test_unavailable_valuation_never_becomes_neutral():
    ev = [replace(_val(Direction.NEUTRAL), status=Status.UNAVAILABLE)]
    assert directional_view(ev, "1y")[0] is Direction.UNAVAILABLE


def test_duplicate_valuation_items_do_not_strengthen_confidence():
    one = [_val(Direction.NEGATIVE)]
    many = one + [replace(_val(Direction.NEGATIVE), name=f"v{i}") for i in range(4)]
    from tests.unit.test_product_slice import _pos

    c1, _ = confidence_for(one, "1y", Direction.NEGATIVE, [], _pos())
    c2, _ = confidence_for(many, "1y", Direction.NEGATIVE, [], _pos())
    assert c1 is c2
