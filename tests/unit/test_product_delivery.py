"""Earnings delivery: multi-observation robustness and denominator safety."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from mip.product.contracts import Direction, Evidence, Status
from mip.product.decide import confidence_for, directional_view
from mip.product.delivery import MIN_REPORTS, STRONG_BEATS, WEAK_BEATS, WINDOW, DeliveryRecord
from mip.product.slice import DELIVERY_HORIZONS

AS = date(2026, 8, 7)


def _rec(beats, n=8, state=None):
    misses = n - beats
    state = state or (
        "CONSISTENT_BEATS"
        if beats >= STRONG_BEATS
        else "CONSISTENT_MISSES" if beats <= WEAK_BEATS else "MIXED"
    )
    return DeliveryRecord(state, n, beats, misses, 0, 0.05, AS, "r")


def _ev(record: DeliveryRecord) -> Evidence:
    direction = (
        Direction.POSITIVE
        if record.state == "CONSISTENT_BEATS"
        else Direction.NEGATIVE if record.state == "CONSISTENT_MISSES" else Direction.NEUTRAL
    )
    return Evidence(
        "earnings_delivery_record",
        "earnings",
        Status.DESCRIPTIVE,
        f"{record.state} ({record.beats}/{record.n_reports})",
        "earnings_observations",
        AS,
        DELIVERY_HORIZONS,
        "e",
        "l",
        direction=direction,
        group="earnings_delivery",
    )


# -- multi-observation, not single -------------------------------------------
def test_window_is_multi_observation():
    assert WINDOW >= 8 and MIN_REPORTS >= 6


def test_one_extreme_report_cannot_set_the_state():
    """Seven beats and one catastrophic miss is still a beating record."""
    assert _rec(7).state == "CONSISTENT_BEATS"


def test_consistent_misses_requires_a_pattern():
    assert _rec(2).state == "CONSISTENT_MISSES"
    assert _rec(3).state == "MIXED"


def test_thresholds_are_ordered():
    assert WEAK_BEATS < STRONG_BEATS <= WINDOW


# -- denominator safety -------------------------------------------------------
def test_state_uses_sign_not_percentage():
    """A $1.00 miss against a $0.02 estimate is one miss, not -5000%."""
    tiny = _rec(4)
    assert tiny.state == "MIXED"
    assert tiny.median_abs_dollar_surprise is not None  # dollars, not percent


def test_insufficient_history_is_unavailable_not_neutral():
    r = DeliveryRecord("UNAVAILABLE", 2, 0, 0, 0, None, None, "only 2 reports")
    ev = replace(_ev(_rec(4)), status=Status.UNAVAILABLE, value="-")
    assert r.state == "UNAVAILABLE"
    assert directional_view([ev], "1m")[0] is Direction.UNAVAILABLE


# -- horizon treatment --------------------------------------------------------
def test_delivery_excluded_from_one_week():
    """A quarterly record cannot inform a five-session horizon."""
    assert DELIVERY_HORIZONS == ("1m", "3m", "6m", "1y")
    assert directional_view([_ev(_rec(7))], "1w")[0] is Direction.UNAVAILABLE


def test_delivery_present_at_longer_horizons():
    assert directional_view([_ev(_rec(7))], "1m")[0] is Direction.POSITIVE
    assert directional_view([_ev(_rec(1))], "1y")[0] is Direction.NEGATIVE


# -- one voice ----------------------------------------------------------------
def test_delivery_components_form_one_group():
    ev = [
        _ev(_rec(7)),
        replace(_ev(_rec(7)), name="beat_rate"),
        replace(_ev(_rec(7)), name="median_surprise"),
    ]
    direction, detail, _ = directional_view(ev, "1m")
    assert direction is Direction.POSITIVE
    assert len([d for d in detail if d.startswith("[")]) == 1


def test_duplicate_delivery_items_do_not_strengthen_confidence():
    from tests.unit.test_product_slice import _pos

    one = [_ev(_rec(7))]
    many = one + [replace(_ev(_rec(7)), name=f"d{i}") for i in range(4)]
    c1, _ = confidence_for(one, "1m", Direction.POSITIVE, [], _pos())
    c2, _ = confidence_for(many, "1m", Direction.POSITIVE, [], _pos())
    assert c1 is c2


def test_delivery_can_oppose_momentum():
    mom = replace(
        Evidence(
            "ret_21d",
            "price/technical",
            Status.DESCRIPTIVE,
            "-1",
            "f",
            AS,
            ("1m",),
            "e",
            "l",
            direction=Direction.NEGATIVE,
        ),
        group="absolute_momentum",
    )
    assert directional_view([mom, _ev(_rec(7))], "1m")[0] is Direction.CONFLICTED
