"""Company quality: one phenomenon, sector-relative, 1y only, experimental."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from mip.product.contracts import Direction, Evidence, Status
from mip.product.decide import confidence_for, directional_view
from mip.product.quality import BANDS, METRICS, MIN_PEERS, QualityAssessment
from mip.product.slice import QUALITY_VOTING_HORIZONS
from tests.unit.test_product_slice import _pos

AS = date(2026, 8, 7)


def _q(state: str, pct=Decimal("0.9")) -> Evidence:
    direction = (
        Direction.POSITIVE
        if state in ("STRONG", "ABOVE_PEER")
        else Direction.NEGATIVE if state in ("WEAK", "BELOW_PEER") else Direction.NEUTRAL
    )
    return Evidence(
        "company_quality_position",
        "fundamentals",
        Status.DESCRIPTIVE,
        state,
        "company_fundamentals",
        AS,
        QUALITY_VOTING_HORIZONS,
        "e",
        "l",
        direction=direction,
        group="company_quality",
    )


# -- one phenomenon -----------------------------------------------------------
def test_quality_is_a_single_phenomenon():
    """Margin and leverage inform the state; they never vote separately."""
    ev = [
        _q("STRONG"),
        replace(_q("STRONG"), name="profit_margin"),
        replace(_q("STRONG"), name="debt_to_equity"),
    ]
    direction, detail, _ = directional_view(ev, "1y")
    assert direction is Direction.POSITIVE
    assert len([d for d in detail if d.startswith("[")]) == 1


def test_duplicate_quality_metrics_do_not_strengthen_confidence():
    one = [_q("STRONG")]
    many = one + [replace(_q("STRONG"), name=f"m{i}") for i in range(4)]
    c1, _ = confidence_for(one, "1y", Direction.POSITIVE, [], _pos())
    c2, _ = confidence_for(many, "1y", Direction.POSITIVE, [], _pos())
    assert c1 is c2


def test_only_profitability_and_leverage_form_the_state():
    fields = {m[0] for m in METRICS}
    assert fields == {"profit_margin", "debt_to_equity"}
    assert "beta" not in fields and "market_cap" not in fields


# -- horizon confinement ------------------------------------------------------
def test_quality_votes_at_one_year_only():
    assert QUALITY_VOTING_HORIZONS == ("1y",)


def test_quality_cannot_vote_at_short_horizons():
    for h in ("1w", "1m", "3m", "6m"):
        assert directional_view([_q("STRONG")], h)[0] is Direction.UNAVAILABLE


def test_quality_votes_at_one_year():
    assert directional_view([_q("STRONG")], "1y")[0] is Direction.POSITIVE
    assert directional_view([_q("WEAK")], "1y")[0] is Direction.NEGATIVE
    assert directional_view([_q("TYPICAL")], "1y")[0] is Direction.NEUTRAL


# -- peer requirements --------------------------------------------------------
def test_minimum_peer_count_is_enforced():
    assert MIN_PEERS >= 5


def test_insufficient_peers_cannot_create_a_signed_vote():
    a = QualityAssessment("UNAVAILABLE", "Energy", 2, None, (), (), AS, "only 2 peers")
    assert a.state == "UNAVAILABLE" and a.composite_percentile is None


def test_unavailable_quality_never_becomes_neutral():
    ev = replace(_q("TYPICAL"), status=Status.UNAVAILABLE, value="-")
    assert directional_view([ev], "1y")[0] is Direction.UNAVAILABLE


def test_bands_are_ordered_and_cover_the_unit_interval():
    edges = [e for e, _ in BANDS]
    assert edges == sorted(edges) and edges[-1] > Decimal("1.0")


# -- constraints and status ---------------------------------------------------
def test_quality_cannot_bypass_portfolio_constraints():
    """A hard breach still overrides a STRONG quality reading."""
    from mip.product.contracts import Action, ConstraintStatus
    from mip.product.decide import decide
    from tests.unit.test_product_slice import _cons

    v = decide([_q("STRONG")], _cons(ConstraintStatus.BREACH), _pos())
    assert {x.action for x in v} == {Action.TRIM}


def test_quality_evidence_is_experimental_and_denies_the_naive_reading():
    from mip.cli._deps import open_session_factory
    from mip.core.db import session_scope
    from mip.product.slice import gather_evidence

    with session_scope(open_session_factory()) as s:
        ev = [e for e in gather_evidence(s, "NVDA", AS) if e.group == "company_quality"]
    assert len(ev) == 1
    text = ev[0].limitations
    assert "EXPERIMENTAL" in text
    assert "NOT THE SAME THING AS A RISING STOCK" in text
    assert "has NOT been measured" in text
