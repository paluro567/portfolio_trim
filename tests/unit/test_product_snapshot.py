"""Tier-1 decision snapshot: presentation-only guarantees.

Two things are asserted here and nothing else:

1. The snapshot never states a conclusion the verdicts do not support - in
   particular it may not let one horizon speak for a report whose horizons
   disagree. The AMD / UNH / PLTR shapes from the 2026-08-13 production cohort
   are used as the fixtures because they are exactly the shapes that broke the
   old executive summary.
2. The snapshot's derived numbers agree with the production functions they claim
   to re-read, so the headline can never contradict the audit trail beneath it.

No test here asserts that any particular action is correct. Actions are decided
in `decide` and are out of scope for this module.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from mip.product import snapshot
from mip.product.contracts import (
    Action,
    Confidence,
    Constraint,
    ConstraintStatus,
    Direction,
    Evidence,
    Status,
)
from mip.product.decide import decide, group_tally
from mip.product.render import render
from tests.unit.test_product_slice import _cons, _pos

ALL_H = ("1w", "1m", "3m", "6m", "1y")


def _ev(name, group, direction, hz=ALL_H, domain="price/technical", value="+0.1000"):
    return Evidence(
        name,
        domain,
        Status.DESCRIPTIVE,
        value,
        "test",
        date(2026, 8, 13),
        hz,
        f"{name} description; 55% of its own history",
        "limitation text",
        direction=direction,
        group=group,
    )


def _verdicts(evidence, pos=None, cons=None):
    return decide(evidence, cons or _cons(), pos or _pos())


# --------------------------------------------------------------- fixtures
def _amd_shaped() -> list[Evidence]:
    """NEGATIVE at 1w/1m, POSITIVE at 3m, CONFLICTED at 6m/1y - the AMD shape."""
    return [
        _ev("ret_21d", "absolute_momentum", Direction.NEGATIVE, ("1w", "1m")),
        _ev("ret_63d", "absolute_momentum", Direction.POSITIVE, ("3m",)),
        _ev("ret_252d", "absolute_momentum", Direction.POSITIVE, ("6m", "1y")),
        _ev(
            "valuation_position",
            "valuation_level",
            Direction.NEGATIVE,
            ("6m", "1y"),
            "valuation",
            "EXPENSIVE (92% of reference set)",
        ),
    ]


def _unh_shaped() -> list[Evidence]:
    """NEGATIVE near, POSITIVE far - the UNH shape that broke the old summary."""
    return [
        _ev("ret_21d", "absolute_momentum", Direction.NEGATIVE, ("1w", "1m")),
        _ev("price_to_ma50", "trend_position", Direction.NEGATIVE, ("1w", "1m")),
        _ev("ret_126d", "absolute_momentum", Direction.POSITIVE, ("6m",)),
        _ev("ret_252d", "absolute_momentum", Direction.POSITIVE, ("1y",)),
    ]


def _pltr_shaped() -> list[Evidence]:
    """POSITIVE near, single-group NEGATIVE at 6m, CONFLICTED at 1y."""
    return [
        _ev("ret_21d", "absolute_momentum", Direction.POSITIVE, ("1w", "1m", "3m")),
        _ev(
            "valuation_position",
            "valuation_level",
            Direction.NEGATIVE,
            ("6m", "1y"),
            "valuation",
            "EXPENSIVE (92% of reference set)",
        ),
        _ev(
            "company_quality_position",
            "company_quality",
            Direction.POSITIVE,
            ("1y",),
            "fundamentals",
            "STRONG (95% of Information Technology peers)",
        ),
    ]


# ------------------------------------------- 1w must not speak for the report
@pytest.mark.parametrize(
    "builder,name", [(_amd_shaped, "AMD"), (_unh_shaped, "UNH"), (_pltr_shaped, "PLTR")]
)
def test_summary_refuses_to_generalise_a_disagreeing_report(builder, name):
    """The old renderer printed verdicts[0].rationale as the report conclusion."""
    verdicts = _verdicts(builder())
    assert len({v.action for v in verdicts}) > 1, f"{name} fixture must disagree"
    text = "\n".join(snapshot.horizon_structure(verdicts))
    assert "No single horizon speaks for this report" in text
    assert "All five horizons agree" not in text


@pytest.mark.parametrize("builder", [_amd_shaped, _unh_shaped, _pltr_shaped])
def test_every_summary_sentence_names_its_horizon(builder):
    verdicts = _verdicts(builder())
    text = "\n".join(snapshot.horizon_structure(verdicts))
    for v in verdicts:
        assert f"**{v.horizon}**" in text or f"{v.horizon} {v.action.value}" in text


def test_unh_shape_never_implies_trim_overall_while_long_horizons_add():
    """The exact failure the Board reported: a TRIM headline over an ADD tail.

    The position is deliberately small: the default fixture weight sits above the
    ADD-suppression reference, which would turn the long horizons into HOLD and
    hide the very shape under test.
    """
    small = _pos(market_weight=Decimal("0.01"), portfolio_positions=52)
    verdicts = _verdicts(_unh_shaped(), pos=small)
    by_h = {v.horizon: v for v in verdicts}
    assert by_h["1w"].action is Action.TRIM
    assert by_h["6m"].action is Action.ADD and by_h["1y"].action is Action.ADD
    head = "\n".join(snapshot.horizon_structure(verdicts))
    # No unqualified global claim of the 1w action may appear.
    assert "the recommended action is **TRIM**" not in head
    assert "1w TRIM" in head and "6m ADD" in head and "1y ADD" in head


def test_uniform_report_is_allowed_to_speak_for_itself():
    ev = [_ev("ret_21d", "absolute_momentum", Direction.NEGATIVE, ALL_H)]
    verdicts = _verdicts(ev)
    assert len({v.action for v in verdicts}) == 1
    assert "All five horizons agree" in "\n".join(snapshot.horizon_structure(verdicts))


# ------------------------------------------------- breadth matches production
@pytest.mark.parametrize("builder", [_amd_shaped, _unh_shaped, _pltr_shaped])
def test_breadth_counts_match_the_production_tally(builder):
    """Snapshot counts and `decide.group_tally` must never disagree."""
    ev = builder()
    for v in _verdicts(ev):
        assert snapshot.group_counts(ev, v.horizon) == group_tally(
            ev, v.horizon, Direction.POSITIVE
        )


@pytest.mark.parametrize("builder", [_amd_shaped, _unh_shaped, _pltr_shaped])
def test_signed_groups_agree_with_the_audit_string(builder):
    """Groups the snapshot calls signed must equal the signed groups in §"Why"."""
    ev = builder()
    for v in _verdicts(ev):
        pos_c, neg_c, _ = snapshot.group_counts(ev, v.horizon)
        assert len(snapshot.signed_groups(v)) == pos_c + neg_c


def test_single_group_verdict_is_visibly_distinguished():
    """A 1-of-N TRIM must not render identically to a 3-of-N TRIM."""
    thin = _verdicts(_pltr_shaped())
    by_h = {v.horizon: v for v in thin}
    ev = _pltr_shaped()
    cell = snapshot.breadth_cell(ev, by_h["6m"])
    assert by_h["6m"].direction is Direction.NEGATIVE
    assert "1 for" in cell and "neutral" in cell

    wide = _verdicts(_unh_shaped())
    wide_cell = snapshot.breadth_cell(_unh_shaped(), {v.horizon: v for v in wide}["1w"])
    assert wide_cell != cell


# -------------------------------------------------- derived, not hardcoded
def test_risk_rows_report_concentration_when_the_weight_is_known():
    """The old table asserted UNAVAILABLE twelve lines below the weight itself."""
    pos = _pos(market_weight=Decimal("0.1054"), portfolio_positions=52)
    rows = snapshot.risk_rows(pos, _amd_shaped(), _verdicts(_amd_shaped(), pos=pos))
    conc = next(r for r in rows if r[0] == "Concentration")
    assert conc[1] != "UNAVAILABLE"
    assert "10.54%" in conc[2]


def test_concentration_ratio_never_reads_as_its_own_contradiction():
    """TSLA at 2.999x printed '3.0x ... below the 3x reference' at one decimal.

    The displayed multiple must not equal the reference while the sentence says
    the position is below it, and must still equal it when it genuinely does.
    """
    from mip.product.decide import ADD_DISCOURAGE_MULTIPLE

    just_under = _pos(market_weight=Decimal("0.057674"), portfolio_positions=52)
    rows = snapshot.risk_rows(just_under, _amd_shaped(), _verdicts(_amd_shaped(), pos=just_under))
    note = next(r for r in rows if r[0] == "Concentration")[2]
    assert "below the 3x reference" in note
    assert "3.0x an equal weight" not in note
    assert "2.999x an equal weight" in note

    exactly_on = _pos(market_weight=Decimal("3") / Decimal("52"), portfolio_positions=52)
    rows = snapshot.risk_rows(exactly_on, _amd_shaped(), _verdicts(_amd_shaped(), pos=exactly_on))
    note = next(r for r in rows if r[0] == "Concentration")[2]
    assert f"at or above the {ADD_DISCOURAGE_MULTIPLE}x reference" in note
    assert "3.0x an equal weight" in note


def test_risk_rows_still_say_unavailable_when_the_weight_really_is():
    pos = _pos(market_weight=None, unavailable=("market-value portfolio weight (1 of 52)",))
    rows = snapshot.risk_rows(pos, _amd_shaped(), _verdicts(_amd_shaped(), pos=pos))
    conc = next(r for r in rows if r[0] == "Concentration")
    assert conc[1] == "UNAVAILABLE"


def test_risk_rows_report_event_state_when_an_event_is_known():
    ev = _amd_shaped() + [
        Evidence(
            "event_state_1y",
            "catalysts",
            Status.DESCRIPTIVE,
            "WITHIN_HORIZON (77d, 2026-10-29)",
            "earnings_observations",
            date(2026, 10, 29),
            ("1y",),
            "scheduled-event state",
            "a date is not a direction",
            group="event_risk",
        )
    ]
    rows = snapshot.risk_rows(_pos(), ev, _verdicts(ev))
    event = next(r for r in rows if r[0] == "Event risk")
    assert event[1] == "NOTED" and "2026-10-29" in event[2]


def test_change_conditions_quote_only_production_thresholds():
    """No invented threshold may appear. 0.70 / 0.30 come from `slice`."""
    from mip.product.slice import OWN_HISTORY_BOTTOM, OWN_HISTORY_TOP

    ev = _amd_shaped()
    text = " ".join(snapshot.change_conditions(_pos(), ev, _verdicts(ev)))
    assert f"{OWN_HISTORY_TOP:.0%}" in text and f"{OWN_HISTORY_BOTTOM:.0%}" in text
    assert "ABSTAIN" not in text


def test_change_conditions_spend_tier1_slots_on_the_thinnest_horizons():
    """A single-group horizon must survive the Tier-1 truncation to three."""
    ev = _pltr_shaped()
    verdicts = _verdicts(ev)
    top3 = snapshot.change_conditions(_pos(), ev, verdicts, limit=3)
    assert len(top3) == 3
    assert any(t.startswith("**6m**") for t in top3), "the 1-group 6m verdict was dropped"


def test_change_conditions_full_listing_covers_every_horizon():
    ev = _pltr_shaped()
    full = snapshot.change_conditions(_pos(), ev, _verdicts(ev))
    for h in ALL_H:
        assert any(t.startswith(f"**{h}**") for t in full)


def test_portfolio_effect_states_whether_it_changed_the_action():
    ev = [_ev("ret_21d", "absolute_momentum", Direction.POSITIVE, ALL_H)]
    concentrated = _pos(market_weight=Decimal("0.20"), portfolio_positions=52)
    text = snapshot.portfolio_effect(concentrated, _cons(), _verdicts(ev, pos=concentrated))
    assert text.startswith("**Yes,") and "ADD on the security view alone" in text

    small = _pos(market_weight=Decimal("0.01"), portfolio_positions=52)
    text2 = snapshot.portfolio_effect(small, _cons(), _verdicts(ev, pos=small))
    assert text2.startswith("**No.**")


# ------------------------------------------------------------- rendered report
def _render(builder, pos=None):
    ev = builder()
    p = pos or _pos()
    return render(p, ev, _cons(), _verdicts(ev, pos=p), {"commit": "test", "feature_date": "x"})


@pytest.mark.parametrize("builder", [_amd_shaped, _unh_shaped, _pltr_shaped])
def test_report_opens_with_the_decision_snapshot(builder):
    out = _render(builder)
    head = out.split("TIER 2")[0]
    for required in (
        "Decision snapshot",
        "Executive summary",
        "Core thesis",
        "Top support",
        "Top concerns",
        "Why the horizons differ",
        "Portfolio effect",
        "Next catalyst",
        "Key risk",
        "What would change the view",
    ):
        assert required in head, f"{required} missing from tier 1"


def test_report_no_longer_carries_the_static_abstain_block():
    out = _render(_amd_shaped)
    assert "ABSTAIN" not in out
    assert "so the AMZN call is included" not in out


def test_report_no_longer_claims_concentration_is_uncomputable_when_it_is_known():
    pos = _pos(market_weight=Decimal("0.1054"), portfolio_positions=52)
    out = _render(_amd_shaped, pos=pos)
    assert "market-value weight not computable" not in out
    assert "no earnings or catalyst data" not in out


def test_repeated_limitation_text_is_printed_once_per_section():
    ev = [
        _ev("ret_21d", "absolute_momentum", Direction.POSITIVE, ALL_H),
        _ev("ret_63d", "absolute_momentum", Direction.POSITIVE, ALL_H),
        _ev("ret_126d", "absolute_momentum", Direction.POSITIVE, ALL_H),
    ]
    out = render(_pos(), ev, _cons(), _verdicts(ev), {"commit": "test", "feature_date": "x"})
    assert out.count("limitation text") == 1


def test_identical_elimination_blocks_are_collapsed():
    out = _render(_unh_shaped)
    block = out.split("Why not the alternative actions")[1].split("## 27")[0]
    assert block.count("EXIT rejected") < 5


def test_table_cells_escape_pipes():
    ev = [
        Evidence(
            "event_move_magnitude",
            "catalysts",
            Status.DESCRIPTIVE,
            "median |move| 7.3%, p90 13.5%",
            "daily_prices",
            date(2026, 8, 13),
            ALL_H,
            "dispersion",
            "dispersion only",
            group="event_risk",
        )
    ]
    out = render(_pos(), ev, _cons(), _verdicts(ev), {"commit": "t", "feature_date": "x"})
    assert "median \\|move\\| 7.3%" in out
    for line in out.splitlines():
        if line.startswith("| `event_move_magnitude`"):
            # 7 real column delimiters; the two escaped pipes must not add cells.
            assert line.count("|") - line.count("\\|") == 7


def test_render_remains_deterministic():
    assert _render(_pltr_shaped) == _render(_pltr_shaped)


def test_snapshot_never_invents_a_confidence_label():
    out = _render(_pltr_shaped)
    assert "HIGH (experimental)" not in out
    for v in _verdicts(_pltr_shaped()):
        assert v.confidence in (Confidence.VERY_LOW, Confidence.LOW, Confidence.MODERATE)


def test_snapshot_layer_cannot_change_an_action():
    """Rendering twice around a snapshot call leaves the verdicts untouched."""
    ev = _pltr_shaped()
    verdicts = _verdicts(ev)
    before = [(v.horizon, v.direction, v.action, v.confidence) for v in verdicts]
    snapshot.core_thesis(_pos(), ev, verdicts)
    snapshot.why_horizons_differ(verdicts)
    snapshot.change_conditions(_pos(), ev, verdicts)
    snapshot.risk_rows(_pos(), ev, verdicts)
    after = [(v.horizon, v.direction, v.action, v.confidence) for v in verdicts]
    assert before == after


def test_core_thesis_marks_a_group_that_flips_sign_within_a_range():
    ev = [
        _ev("ret_21d", "absolute_momentum", Direction.POSITIVE, ("1w",)),
        _ev("ret_63d", "absolute_momentum", Direction.NEGATIVE, ("3m",)),
    ]
    text = snapshot.core_thesis(_pos(), ev, _verdicts(ev))
    assert "`absolute_momentum`(+/-)" in text


def test_constraint_breach_is_reported_as_a_risk_limit_not_a_view():
    ev = [_ev("ret_21d", "absolute_momentum", Direction.POSITIVE, ALL_H)]
    breached = [
        Constraint(
            "Concentration vs hard cap (market value)",
            ConstraintStatus.BREACH,
            "20%",
            "10%",
            "over cap",
        )
    ]
    verdicts = decide(ev, breached, _pos())
    text = snapshot.portfolio_effect(_pos(), breached, verdicts)
    assert "breached deterministic limit" in text
