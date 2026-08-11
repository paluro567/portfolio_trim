"""Event risk: horizon awareness, non-directionality, and the ADD guardrail."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from mip.product.contracts import Action, ConstraintStatus, Direction, Evidence, Status
from mip.product.decide import (
    NON_DIRECTIONAL_GROUPS,
    decide,
    directional_view,
    event_state_for,
)
from mip.product.event import (
    APPROACHING_DAYS,
    HORIZON_DAYS,
    IMMINENT_DAYS,
    classify,
)
from tests.unit.test_product_slice import _cons, _ev, _pos

AS = date(2026, 8, 7)


def _event(horizon: str, value: str, status: Status = Status.DESCRIPTIVE) -> Evidence:
    return Evidence(
        f"event_state_{horizon}",
        "catalysts",
        status,
        value,
        "earnings_observations",
        AS,
        (horizon,),
        "e",
        "l",
        missing_reason=None if status is Status.DESCRIPTIVE else "no data",
        direction=Direction.NEUTRAL,
        group="event_risk",
    )


# -- horizon awareness --------------------------------------------------------
def test_event_beyond_window_is_outside_that_horizon():
    """An event 83 days out is not inside a one-month horizon."""
    st = classify(date(2026, 10, 29), AS, "1m", True)
    assert st.status == "OUTSIDE_HORIZON" and st.days_to_event == 83


def test_same_event_is_inside_a_longer_horizon():
    assert classify(date(2026, 10, 29), AS, "3m", True).status == "WITHIN_HORIZON"


def test_horizon_windows_are_ordered():
    d = [HORIZON_DAYS[h] for h in ("1w", "1m", "3m", "6m", "1y")]
    assert d == sorted(d) and d[0] == 7


def test_imminent_and_approaching_cutoffs():
    assert classify(date(2026, 8, 10), AS, "1w", True).status == "IMMINENT"
    assert classify(date(2026, 8, 25), AS, "1m", True).status == "APPROACHING"
    assert IMMINENT_DAYS < APPROACHING_DAYS


def test_missing_event_never_becomes_no_event():
    """Absence of a known date is not evidence that no event will occur."""
    assert classify(None, AS, "1w", any_history=False).status == "UNAVAILABLE"
    assert classify(None, AS, "1w", any_history=True).status == "NO_KNOWN_EVENT"


# -- non-directionality -------------------------------------------------------
def test_event_risk_is_excluded_from_the_directional_view():
    assert "event_risk" in NON_DIRECTIONAL_GROUPS
    assert directional_view([_event("1w", "IMMINENT (3d)")], "1w")[0] is Direction.UNAVAILABLE


def test_event_proximity_cannot_create_direction():
    mom = replace(_ev("ret_21d", "price/technical", Direction.POSITIVE), group="absolute_momentum")
    with_event = directional_view([mom, _event("1w", "IMMINENT (3d)")], "1w")[0]
    without = directional_view([mom], "1w")[0]
    assert with_event is without is Direction.POSITIVE


def test_unavailable_event_reports_unavailable_not_neutral():
    status, _ = event_state_for([_event("1w", "-", Status.UNAVAILABLE)], "1w")
    assert status == "UNAVAILABLE"


# -- action guardrail ---------------------------------------------------------
def _run(evidence, cons=None):
    return decide(
        evidence, cons or _cons(ConstraintStatus.PASS), _pos(market_weight=Decimal("0.01"))
    )


def test_imminent_event_suppresses_add_to_hold():
    mom = replace(_ev("ret_21d", "price/technical", Direction.POSITIVE), group="absolute_momentum")
    without = _run([mom])
    with_ev = _run([mom, _event("1w", "IMMINENT (3d)")])
    assert without[0].action is Action.ADD
    assert with_ev[0].action is Action.HOLD
    assert with_ev[0].direction is without[0].direction  # view untouched


def test_imminent_event_never_forces_trim_or_exit():
    neg = replace(_ev("ret_21d", "price/technical", Direction.NEGATIVE), group="absolute_momentum")
    v = _run([neg, _event("1w", "IMMINENT (3d)")])
    assert v[0].action is Action.TRIM  # from the negative view, not the event
    assert v[0].action is not Action.EXIT


def test_distant_event_does_not_suppress_add():
    mom = replace(_ev("ret_21d", "price/technical", Direction.POSITIVE), group="absolute_momentum")
    assert _run([mom, _event("1w", "OUTSIDE_HORIZON (83d)")])[0].action is Action.ADD


def test_guardrail_explanation_names_the_event_and_denies_direction():
    mom = replace(_ev("ret_21d", "price/technical", Direction.POSITIVE), group="absolute_momentum")
    r = _run([mom, _event("1w", "IMMINENT (3d)")])[0].rationale
    assert "IMMINENT" in r
    assert "unchanged" in r and "not a view on the outcome" in r


# -- acceptance blocker B3 (bug-fix release) ---------------------------------
def test_portfolio_triage_reads_the_current_event_contract():
    """B3: the triage must read event_state_{h}, not the retired field name."""
    import inspect

    from mip.product import portfolio_view as pv

    src = inspect.getsource(pv)
    assert "next_earnings_date" not in src
    assert "event_state_1y" in src


def test_next_event_extracts_date_and_days():
    from mip.product.portfolio_view import _next_event

    ev = [_event("1y", "WITHIN_HORIZON (79d, 2026-10-29)")]
    label, days = _next_event(ev)
    assert label == "2026-10-29 (79d)" and days == 79


def test_next_event_unknown_stays_unknown():
    """B3: absence must never become a fabricated date."""
    from mip.product.portfolio_view import _next_event

    label, days = _next_event([_event("1y", "-", Status.UNAVAILABLE)])
    assert label == "unknown" and days is None
    assert _next_event([])[0] == "unknown"


def test_no_known_event_is_reported_without_a_date():
    from mip.product.portfolio_view import _next_event

    label, days = _next_event([_event("1y", "NO_KNOWN_EVENT")])
    assert days is None and "no known event" in label


def test_imminent_event_reaches_the_attention_ranking():
    """B3: proximity must be able to raise research priority again."""
    from decimal import Decimal

    from mip.product.portfolio_view import summarise
    from tests.unit.test_product_slice import _pos

    ev = [_event("1y", "IMMINENT (3d, 2026-08-14)")]
    row = summarise("TEST", _pos(market_weight=Decimal("0.01")), ev, [], None)
    assert row.catalyst == "2026-08-14 (3d)"
    assert any("earnings in 3d" in w for w in row.priority_why)


def test_portfolio_event_agrees_with_the_holding_report():
    """B3: the triage value must match the holding's own event evidence."""
    from datetime import date as _d

    from mip.cli._deps import open_session_factory
    from mip.core.db import session_scope
    from mip.product.portfolio_view import _next_event
    from mip.product.slice import gather_evidence

    with session_scope(open_session_factory()) as s:
        ev = gather_evidence(s, "AMZN", _d(2026, 8, 11))
    label, _ = _next_event(ev)
    item = next(e for e in ev if e.name == "event_state_1y")
    assert label.split(" ")[0] in item.value
