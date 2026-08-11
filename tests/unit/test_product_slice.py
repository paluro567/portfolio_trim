"""Tests for the V4 product vertical slice.

Asserts the evidence-status contract, the directional/action separation, the
confidence caps, and the prohibition on probability language and predictive
scores. No network, no database.
"""

from __future__ import annotations

import json
from dataclasses import replace
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
        market_weight=Decimal("0.06"),
        portfolio_market_value=Decimal("20000"),
        portfolio_positions=52,
        unavailable=(),
    )
    base.update(kw)
    return PositionState(**base)


def _ev(
    name, domain="price/technical", direction=Direction.NEUTRAL, status=Status.DESCRIPTIVE, hz=ALL_H
):
    return Evidence(
        name, domain, status, "1.0", "test", date(2026, 7, 16), hz, "e", "l", direction=direction
    )


def _cons(status=ConstraintStatus.NOT_EVALUABLE):
    """The concentration constraint is the one `decide` inspects for blocking."""
    return [Constraint("Concentration vs hard cap (market value)", status, "o", "t", "r")]


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
    assert directional_view([_ev("a", "price/technical")], "1m")[0] is Direction.NEUTRAL


def test_directional_view_conflicted_surfaces_both_sides():
    ev = [
        replace(_ev("a", "price/technical", Direction.POSITIVE), group="absolute_momentum"),
        replace(_ev("b", "sector", Direction.NEGATIVE), group="sector_relative"),
    ]
    direction, contributing, conflicts = directional_view(ev, "1m")
    assert direction is Direction.CONFLICTED
    assert conflicts  # conflicts remain visible
    assert len(contributing) == 2  # one detail line per phenomenon group


def test_directional_view_agrees():
    pos = directional_view([_ev("a", "price/technical", Direction.POSITIVE)], "1m")
    assert pos[0] is Direction.POSITIVE
    assert directional_view([_ev("b", "sector", Direction.NEGATIVE)], "1m")[0] is Direction.NEGATIVE


# -- confidence caps ---------------------------------------------------------
def test_confidence_high_is_unreachable():
    assert not hasattr(Confidence, "HIGH")


def test_confidence_very_low_when_direction_unavailable():
    c, _ = confidence_for([], "1m", Direction.UNAVAILABLE, [], _pos())
    assert c is Confidence.VERY_LOW


def test_confidence_capped_low_by_conflict():
    ev = [_ev("a", "price/technical", Direction.POSITIVE), _ev("b", "sector", Direction.NEGATIVE)]
    c, basis = confidence_for(ev, "1m", Direction.CONFLICTED, ["conflict"], _pos())
    assert c is Confidence.LOW
    assert any("conflicts" in b for b in basis)


def test_confidence_capped_low_by_missing_portfolio_input():
    ev = [_ev("a", "price/technical"), _ev("b", "sector")]
    c, basis = confidence_for(ev, "1m", Direction.NEUTRAL, [], _pos(unavailable=("weight",)))
    assert c is Confidence.LOW
    assert any("portfolio input missing" in b for b in basis)


def test_confidence_capped_low_because_all_readings_experimental():
    ev = [
        replace(_ev("a", "price/technical"), group="absolute_momentum"),
        replace(_ev("b", "sector"), group="sector_relative"),
    ]
    c, basis = confidence_for(ev, "1m", Direction.NEUTRAL, [], _pos())
    assert c is Confidence.LOW
    assert any("EXPERIMENTAL" in b for b in basis)


# -- action rules ------------------------------------------------------------
def test_neutral_view_yields_hold_not_abstain():
    """Missing portfolio inputs no longer suppress the security view."""
    v = decide([_ev("a", "price/technical")], _cons(), _pos(unavailable=("tax lots",)))
    assert {x.action for x in v} == {Action.HOLD}


def test_hold_when_nothing_missing_and_no_breach():
    v = decide([_ev("a", "price/technical")], _cons(ConstraintStatus.PASS), _pos())
    assert {x.action for x in v} == {Action.HOLD}


def test_positive_view_at_low_exposure_yields_add():
    pos = _pos(market_weight=Decimal("0.005"))
    v = decide([_ev("a", "price/technical", Direction.POSITIVE)], _cons(), pos)
    assert {x.action for x in v} == {Action.ADD}


def test_positive_view_at_high_exposure_downgrades_to_hold():
    """Sizing effect, not a bearish view."""
    pos = _pos(market_weight=Decimal("0.25"))
    v = decide([_ev("a", "price/technical", Direction.POSITIVE)], _cons(), pos)
    assert {x.action for x in v} == {Action.HOLD}
    assert all(x.direction is Direction.POSITIVE for x in v)
    assert any("position-sizing effect" in x.rationale for x in v)


def test_negative_view_at_low_exposure_still_trims():
    """Security evidence can act even when the position is small."""
    pos = _pos(market_weight=Decimal("0.005"))
    v = decide([_ev("a", "price/technical", Direction.NEGATIVE)], _cons(), pos)
    assert {x.action for x in v} == {Action.TRIM}


def test_portfolio_weight_never_changes_the_directional_view():
    ev = [_ev("a", "price/technical", Direction.POSITIVE)]
    seen = set()
    for w in ("0.005", "0.02", "0.11", "0.25"):
        v = decide(ev, _cons(), _pos(market_weight=Decimal(w)))
        seen |= {x.direction for x in v}
    assert seen == {Direction.POSITIVE}


def test_deterministic_constraint_overrides_experimental_direction():
    """A BREACH forces TRIM even when directional evidence is POSITIVE."""
    ev = [_ev("a", "price/technical", Direction.POSITIVE)]
    v = decide(ev, _cons(ConstraintStatus.BREACH), _pos(unavailable=("tax lots",)))
    assert {x.action for x in v} == {Action.TRIM}
    assert all(x.direction is Direction.POSITIVE for x in v)
    assert any("risk-limit decision" in x.rationale for x in v)


def test_all_five_horizons_present():
    v = decide([_ev("a", "price/technical")], _cons(), _pos())
    assert [x.horizon for x in v] == list(ALL_H)


def test_elimination_trace_covers_every_unselected_action():
    v = decide([_ev("a", "price/technical")], _cons(), _pos(unavailable=("tax lots",)))
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


# -- group independence and evidence semantics (production loop hardening) -----
def test_correlated_items_count_as_one_group():
    """Four momentum windows agreeing is ONE phenomenon, not four."""
    ev = [_ev(f"ret_{n}d", "price/technical", Direction.POSITIVE) for n in (21, 63, 126, 252)]
    ev = [replace(e, group="absolute_momentum") for e in ev]
    direction, detail, conflicts = directional_view(ev, "1m")
    assert direction is Direction.POSITIVE
    assert len([d for d in detail if d.startswith("[")]) == 1  # one group vote


def test_two_distinct_groups_disagreeing_is_conflicted():
    ev = [
        replace(_ev("a", "price/technical", Direction.POSITIVE), group="absolute_momentum"),
        replace(_ev("b", "sector", Direction.NEGATIVE), group="sector_relative"),
    ]
    assert directional_view(ev, "1m")[0] is Direction.CONFLICTED


def test_duplicating_evidence_does_not_strengthen_confidence():
    one = [replace(_ev("a", "price/technical", Direction.POSITIVE), group="absolute_momentum")]
    many = one + [
        replace(_ev(f"a{i}", "price/technical", Direction.POSITIVE), group="absolute_momentum")
        for i in range(5)
    ]
    c1, _ = confidence_for(one, "1m", Direction.POSITIVE, [], _pos())
    c2, _ = confidence_for(many, "1m", Direction.POSITIVE, [], _pos())
    assert c1 is c2


def test_unavailable_evidence_never_becomes_neutral():
    ev = [replace(_ev("a", "price/technical"), status=Status.UNAVAILABLE)]
    assert directional_view(ev, "1m")[0] is Direction.UNAVAILABLE


def test_evidence_groups_have_no_default_bucket():
    """Every domain must map to a named phenomenon; 'other' is a defect."""
    from mip.product.slice import DOMAIN_GROUP

    for dom in (
        "sector",
        "market/regime",
        "catalysts",
        "earnings",
        "historical",
        "fundamentals",
        "valuation",
    ):
        assert dom in DOMAIN_GROUP and DOMAIN_GROUP[dom] != "other"


# -- acceptance blockers B1/B2 (bug-fix release) ------------------------------
def test_historical_sample_size_is_interpolated_not_literal():
    """B1: the n= count must be a real integer, never the template text."""
    from mip.cli._deps import open_session_factory
    from mip.core.db import session_scope
    from mip.product.slice import _historical

    with session_scope(open_session_factory()) as s:
        items = _historical(s, "AMZN", date(2026, 8, 11))
    available = [e for e in items if e.status is not Status.UNAVAILABLE]
    assert available, "AMZN must have historical evidence"
    for e in available:
        assert "{len(fwd)}" not in e.value
        n = int(e.value.split("n=")[1])
        assert n > 100


def test_unavailable_history_carries_no_fabricated_sample_size():
    """B1: an unavailable series must not display an n at all."""
    from mip.cli._deps import open_session_factory
    from mip.core.db import session_scope
    from mip.product.slice import _historical

    with session_scope(open_session_factory()) as s:
        items = _historical(s, "RZLV", date(2026, 8, 11))
    for e in items:
        if e.status is Status.UNAVAILABLE:
            assert "n=" not in e.value and e.missing_reason


def test_headline_counts_only_supporting_groups():
    """B2: neutral groups must never be described as supporting the view."""
    from mip.product.decide import group_tally

    ev = [
        replace(_ev("a", "price/technical", Direction.NEGATIVE), group="absolute_momentum"),
        replace(_ev("b", "sector"), group="sector_relative"),
        replace(_ev("c", "valuation"), group="valuation_level"),
    ]
    supporting, opposing, neutral = group_tally(ev, "1m", Direction.NEGATIVE)
    assert (supporting, opposing, neutral) == (1, 0, 2)


def test_crm_3m_headline_no_longer_overstates_agreement():
    """B2 regression: the exact acceptance-review failure case."""
    from pathlib import Path

    from mip.cli._deps import open_session_factory
    from mip.core.db import session_scope
    from mip.product.decide import decide
    from mip.product.policy import load_policy
    from mip.product.slice import evaluate_constraints, gather_evidence, load_position

    bal = Path("data/peter_real_opening_balances_2026-07-16.csv")
    with session_scope(open_session_factory()) as s:
        pos = load_position(s, "CRM", date(2026, 8, 11), bal)
        ev = gather_evidence(s, "CRM", date(2026, 8, 11))
        v = decide(ev, evaluate_constraints(s and pos, load_policy()), pos)
    r = next(x for x in v if x.horizon == "3m").rationale
    assert "negative on 8 independent reading" not in r
    assert "1 of 8 evidence group(s)" in r and "neutral" in r
