"""Tests for the V4 product vertical slice.

Asserts the evidence-status contract, the directional/action separation, the
confidence caps, and the prohibition on probability language and predictive
scores. No network, no database.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from mip.product.contracts import (
    HORIZONS,
    Action,
    Confidence,
    Constraint,
    ConstraintStatus,
    Direction,
    Evidence,
    PositionState,
    Status,
)
from mip.product.decide import confidence_for, decide, directional_view
from mip.product.render import DISCLOSURE, render

ALL_H = tuple(h for h, _ in HORIZONS)
REPORT = Path("data/product_reports/2026-07-16/AMZN/AMZN_2026-07-16.md")
INPUTS = Path("data/product_reports/2026-07-16/AMZN/inputs.json")


def _pos(**kw) -> PositionState:
    base = dict(
        symbol="TEST",
        as_of=date(2026, 7, 16),
        quantity=Decimal("10"),
        average_cost=Decimal("100"),
        market_price=Decimal("110"),
        price_date=date(2026, 7, 16),
        market_value=Decimal("1100"),
        cost_basis=Decimal("1000"),
        unrealized_pnl=Decimal("100"),
        unrealized_pct=Decimal("0.10"),
        cost_weight=Decimal("0.05"),
        portfolio_positions=52,
        unavailable=(),
    )
    base.update(kw)
    return PositionState(**base)


def _ev(name, domain, direction=Direction.NEUTRAL, status=Status.DESCRIPTIVE, hz=ALL_H):
    return Evidence(
        name, domain, status, "1.0", "test", date(2026, 7, 16), hz, "e", "l", direction=direction
    )


def _cons(status=ConstraintStatus.NOT_EVALUABLE):
    return [Constraint("c", status, "o", "t", "r")]


# -- PositionState -----------------------------------------------------------
def test_position_state_construction_and_serialization():
    p = _pos()
    d = p.to_dict()
    assert d["symbol"] == "TEST" and d["quantity"] == "10"
    assert all(not isinstance(v, float) for v in d.values())
    json.dumps(d)


def test_position_state_missing_inputs_are_explicit():
    p = _pos(
        market_price=None,
        market_value=None,
        unrealized_pnl=None,
        unrealized_pct=None,
        unavailable=("market price",),
    )
    assert p.to_dict()["market_price"] is None
    assert p.unavailable == ("market price",)


# -- evidence status contract -----------------------------------------------
def test_evidence_status_serialization_round_trip():
    e = _ev("x", "price/technical")
    d = e.to_dict()
    assert d["status"] == "DESCRIPTIVE" and d["direction"] == "NEUTRAL"
    assert json.loads(json.dumps(d)) == d


def test_unavailable_evidence_carries_a_reason():
    e = Evidence(
        "x", "d", Status.UNAVAILABLE, "—", "—", None, ALL_H, "e", "l", missing_reason="no data"
    )
    assert e.status is Status.UNAVAILABLE and e.missing_reason


# -- directional view rules --------------------------------------------------
def test_directional_view_unavailable_when_no_evidence():
    assert directional_view([], "1m")[0] is Direction.UNAVAILABLE


def test_directional_view_neutral_when_no_signed_evidence():
    assert directional_view([_ev("a", "d")], "1m")[0] is Direction.NEUTRAL


def test_directional_view_conflicted_surfaces_both_sides():
    ev = [_ev("a", "d", Direction.POSITIVE), _ev("b", "d", Direction.NEGATIVE)]
    direction, contributing, conflicts = directional_view(ev, "1m")
    assert direction is Direction.CONFLICTED
    assert conflicts and len(contributing) == 2  # conflicts remain visible


def test_directional_view_agrees():
    assert directional_view([_ev("a", "d", Direction.POSITIVE)], "1m")[0] is Direction.POSITIVE
    assert directional_view([_ev("a", "d", Direction.NEGATIVE)], "1m")[0] is Direction.NEGATIVE


# -- confidence caps ---------------------------------------------------------
def test_confidence_high_is_unreachable():
    assert not hasattr(Confidence, "HIGH")


def test_confidence_very_low_when_direction_unavailable():
    c, _ = confidence_for([], "1m", Direction.UNAVAILABLE, [], _pos())
    assert c is Confidence.VERY_LOW


def test_confidence_capped_low_by_conflict():
    ev = [_ev("a", "x", Direction.POSITIVE), _ev("b", "y", Direction.NEGATIVE)]
    c, basis = confidence_for(ev, "1m", Direction.CONFLICTED, ["conflict"], _pos())
    assert c is Confidence.LOW
    assert any("conflicting" in b for b in basis)


def test_confidence_capped_low_by_missing_portfolio_input():
    ev = [_ev("a", "x"), _ev("b", "y")]
    c, basis = confidence_for(ev, "1m", Direction.NEUTRAL, [], _pos(unavailable=("weight",)))
    assert c is Confidence.LOW
    assert any("material portfolio input missing" in b for b in basis)


def test_confidence_capped_low_because_all_readings_experimental():
    ev = [_ev("a", "x"), _ev("b", "y")]
    c, basis = confidence_for(ev, "1m", Direction.NEUTRAL, [], _pos())
    assert c is Confidence.LOW
    assert any("EXPERIMENTAL" in b for b in basis)


# -- action rules ------------------------------------------------------------
def test_abstain_when_required_portfolio_information_unavailable():
    v = decide([_ev("a", "x")], _cons(), _pos(unavailable=("tax lots",)))
    assert {x.action for x in v} == {Action.ABSTAIN}


def test_hold_when_nothing_missing_and_no_breach():
    v = decide([_ev("a", "x")], _cons(ConstraintStatus.PASS), _pos())
    assert {x.action for x in v} == {Action.HOLD}


def test_deterministic_constraint_overrides_experimental_direction():
    """A BREACH forces TRIM even when directional evidence is POSITIVE."""
    ev = [_ev("a", "x", Direction.POSITIVE)]
    v = decide(ev, _cons(ConstraintStatus.BREACH), _pos(unavailable=("tax lots",)))
    assert {x.action for x in v} == {Action.TRIM}


def test_all_five_horizons_present():
    v = decide([_ev("a", "x")], _cons(), _pos())
    assert [x.horizon for x in v] == list(ALL_H)


def test_elimination_trace_covers_every_unselected_action():
    v = decide([_ev("a", "x")], _cons(), _pos(unavailable=("tax lots",)))
    for verdict in v:
        rejected = {a for a, _ in verdict.eliminations}
        assert verdict.action.value not in rejected
        assert rejected and all(r for r in rejected)


# -- rendering ---------------------------------------------------------------
def _render_sample() -> str:
    pos = _pos(unavailable=("weight",))
    ev = [
        _ev("a", "price/technical"),
        Evidence(
            "z",
            "valuation",
            Status.UNAVAILABLE,
            "—",
            "—",
            None,
            ALL_H,
            "e",
            "l",
            missing_reason="no fundamentals",
        ),
    ]
    return render(
        pos,
        ev,
        _cons(),
        decide(ev, _cons(), pos),
        {"commit": "abc1234", "feature_date": "2026-07-16"},
    )


def test_unavailable_sections_render_explicitly():
    out = _render_sample()
    assert "UNAVAILABLE" in out and "no fundamentals" in out


def test_render_is_deterministic():
    assert _render_sample() == _render_sample()


def test_report_carries_the_confidence_disclosure():
    assert DISCLOSURE in _render_sample()


# -- prohibited language (product evidence boundary) -------------------------
@pytest.mark.skipif(not REPORT.exists(), reason="report not generated")
def test_generated_report_makes_no_probability_claim():
    """Prohibited vocabulary must not appear as a CLAIM.

    The mandated disclosure sentence and the standing disclaimer both contain
    the words "probability" and "expected return" while explicitly denying
    them. Those sentences are removed before the check so the test detects
    assertions rather than denials.
    """
    text = REPORT.read_text().lower()
    for disclaimer in (
        DISCLOSURE.lower(),
        "this report contains no probability estimate, no expected return, "
        "and no predictive score.",
    ):
        text = text.replace(disclaimer, " ")
    for banned in (
        "probability of",
        "probability that",
        "expected return",
        "we forecast",
        "will rise",
        "will fall",
        "price target",
        "we expect the",
        "is likely to",
    ):
        assert banned not in text, f"prohibited claim present: {banned}"


@pytest.mark.skipif(not REPORT.exists(), reason="report not generated")
def test_generated_report_has_no_arbitrary_predictive_score():
    text = REPORT.read_text()
    assert "trim score" not in text.lower()
    assert "/100" not in text
    assert "No item in this report is VALIDATED" in text


@pytest.mark.skipif(not REPORT.exists(), reason="report not generated")
def test_generated_report_has_every_required_section():
    text = REPORT.read_text()
    for heading in (
        "Executive summary",
        "Current position state",
        "Portfolio context",
        "Market and regime context",
        "Price and technical evidence",
        "Historical evidence",
        "Historical analogues",
        "Risk factors",
        "Deterministic constraints",
        "Why this action",
        "Why not the alternative actions",
        "What would change",
        "Missing evidence",
        "Evidence-status disclosure",
        "Limitations",
    ):
        assert heading in text, f"missing section: {heading}"


@pytest.mark.skipif(not INPUTS.exists(), reason="inputs not archived")
def test_archived_provenance_bundle_is_complete():
    b = json.loads(INPUTS.read_text())
    assert set(b) == {"meta", "position", "constraints", "evidence", "verdicts"}
    assert b["meta"]["commit"] and b["meta"]["balances_sha256"]
    assert len(b["verdicts"]) == 5
    assert all(
        e["status"] in {"VALIDATED", "DESCRIPTIVE", "EXPERIMENTAL", "UNAVAILABLE"}
        for e in b["evidence"]
    )
