"""Policy artifact, validation, and policy-driven constraint evaluation."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from mip.product.contracts import (
    Action,
    ConstraintStatus,
    Direction,
    Evidence,
    PositionState,
    Status,
)
from mip.product.decide import decide, directional_view
from mip.product.policy import (
    REQUIRED,
    PolicyArtifact,
    PolicyError,
    PolicyUnavailable,
    load_policy,
)
from mip.product.slice import evaluate_constraints

ALL_H = ("1w", "1m", "3m", "6m", "1y")


def _write(tmp_path, body: str):
    p = tmp_path / "personal.yaml"
    p.write_text(body)
    return p


def _valid(cap="12.0", target="8.0") -> str:
    return (
        'policy_version: "1.0.0"\n'
        'effective_date: "2026-08-07"\n'
        "authored_by: owner\n"
        f"portfolio:\n  hard_cap_pct: {cap}\n  core_target_pct: {target}\n"
    )


def _pos(market_weight=Decimal("0.1085"), **kw) -> PositionState:
    base = dict(
        symbol="AMZN",
        as_of=date(2026, 7, 16),
        quantity=Decimal("82"),
        average_cost=Decimal("186.84"),
        market_price=Decimal("249.89"),
        price_date=date(2026, 7, 16),
        market_value=Decimal("20490.98"),
        cost_basis=Decimal("15320.88"),
        unrealized_pnl=Decimal("5170.10"),
        unrealized_pct=Decimal("0.3375"),
        cost_weight=Decimal("0.0904"),
        market_weight=market_weight,
        portfolio_market_value=Decimal("188904.58"),
        portfolio_positions=52,
        unavailable=("tax lots",),
    )
    base.update(kw)
    return PositionState(**base)


def _ev(direction=Direction.NEGATIVE):
    return [
        Evidence(
            "t",
            "price/technical",
            Status.DESCRIPTIVE,
            "1",
            "s",
            date(2026, 7, 16),
            ALL_H,
            "e",
            "l",
            direction=direction,
        )
    ]


# -- creation, serialization, versioning -------------------------------------
def test_policy_artifact_creation_and_serialization(tmp_path):
    pol = load_policy(_write(tmp_path, _valid()))
    assert isinstance(pol, PolicyArtifact)
    assert pol.hard_cap_pct == Decimal("12.0") and pol.core_target_pct == Decimal("8.0")
    assert pol.effective_date == date(2026, 8, 7)
    d = pol.to_dict()
    assert d["status"] == "SUPPLIED" and d["policy_version"] == "1.0.0"
    assert len(d["content_hash"]) == 64
    json.dumps(d)


def test_policy_versioning_changes_the_content_hash(tmp_path):
    a = load_policy(_write(tmp_path, _valid()))
    b = load_policy(_write(tmp_path, _valid(cap="15.0")))
    assert a.content_hash != b.content_hash


def test_policy_is_immutable(tmp_path):
    pol = load_policy(_write(tmp_path, _valid()))
    with pytest.raises((AttributeError, TypeError, ValueError)):
        pol.hard_cap_pct = Decimal("99")


# -- rejection of invalid configurations -------------------------------------
@pytest.mark.parametrize(
    "cap,target",
    [("0", "0"), ("-5", "1"), ("101", "10"), ("abc", "5"), ("12", "-1"), ("12", "0")],
)
def test_invalid_percentages_are_rejected(tmp_path, cap, target):
    with pytest.raises(PolicyError):
        load_policy(_write(tmp_path, _valid(cap=cap, target=target)))


def test_target_above_hard_cap_is_rejected(tmp_path):
    with pytest.raises(PolicyError) as exc:
        load_policy(_write(tmp_path, _valid(cap="10.0", target="12.0")))
    assert "must not exceed" in str(exc.value)


def test_invalid_effective_date_is_rejected(tmp_path):
    body = _valid().replace('effective_date: "2026-08-07"', 'effective_date: "not-a-date"')
    with pytest.raises(PolicyError):
        load_policy(_write(tmp_path, body))


def test_missing_version_is_unavailable_not_invented(tmp_path):
    body = _valid().replace('policy_version: "1.0.0"\n', "")
    pol = load_policy(_write(tmp_path, body))
    assert isinstance(pol, PolicyUnavailable) and "policy_version" in pol.missing


def test_missing_policy_file_is_unavailable(tmp_path):
    pol = load_policy(tmp_path / "nope.yaml")
    assert isinstance(pol, PolicyUnavailable)
    assert set(REQUIRED).issubset(set(pol.missing))


def test_shipped_template_supplies_no_values():
    """The repository template must never carry invented preferences."""
    pol = load_policy()
    assert isinstance(pol, PolicyUnavailable)
    assert "hard_cap_pct" in pol.missing and "core_target_pct" in pol.missing


# -- market value vs cost basis ----------------------------------------------
def test_market_value_weight_is_distinct_from_cost_basis_weight():
    pos = _pos()
    assert pos.market_weight != pos.cost_weight
    assert pos.market_weight == Decimal("0.1085")


def test_cost_basis_is_never_reported_as_concentration(tmp_path):
    cs = evaluate_constraints(_pos(), load_policy(_write(tmp_path, _valid())))
    cb = next(c for c in cs if c.name == "Concentration (cost basis)")
    assert cb.status is ConstraintStatus.NOT_EVALUABLE
    assert "NOT a concentration measure" in cb.reason


def test_missing_market_weight_keeps_concentration_not_evaluable(tmp_path):
    cs = evaluate_constraints(_pos(market_weight=None), load_policy(_write(tmp_path, _valid())))
    cap = next(c for c in cs if c.name.startswith("Concentration vs hard cap"))
    assert cap.status is ConstraintStatus.NOT_EVALUABLE
    assert "not a substitute" in cap.reason


# -- PASS / BREACH / NOT_EVALUABLE -------------------------------------------
def test_concentration_pass(tmp_path):
    cs = evaluate_constraints(_pos(), load_policy(_write(tmp_path, _valid(cap="12.0"))))
    cap = next(c for c in cs if c.name.startswith("Concentration vs hard cap"))
    assert cap.status is ConstraintStatus.PASS and cap.observed == "10.85%"


def test_concentration_breach(tmp_path):
    cs = evaluate_constraints(
        _pos(), load_policy(_write(tmp_path, _valid(cap="10.0", target="8.0")))
    )
    cap = next(c for c in cs if c.name.startswith("Concentration vs hard cap"))
    assert cap.status is ConstraintStatus.BREACH


def test_concentration_not_evaluable_without_policy():
    cs = evaluate_constraints(_pos(), load_policy())
    cap = next(c for c in cs if c.name.startswith("Concentration vs hard cap"))
    assert cap.status is ConstraintStatus.NOT_EVALUABLE
    assert "does not invent" in cap.reason


def test_target_deviation_evaluable_only_with_policy(tmp_path):
    with_pol = evaluate_constraints(_pos(), load_policy(_write(tmp_path, _valid())))
    dev = next(c for c in with_pol if c.name.startswith("Deviation from core target"))
    assert dev.status is ConstraintStatus.PASS and "above target" in dev.reason
    without = evaluate_constraints(_pos(), load_policy())
    dev2 = next(c for c in without if c.name.startswith("Deviation from core target"))
    assert dev2.status is ConstraintStatus.NOT_EVALUABLE


# -- action integration ------------------------------------------------------
def test_breach_overrides_positive_directional_evidence(tmp_path):
    pol = load_policy(_write(tmp_path, _valid(cap="10.0", target="8.0")))
    v = decide(_ev(Direction.POSITIVE), evaluate_constraints(_pos(), pol), _pos())
    assert {x.action for x in v} == {Action.TRIM}


def test_pass_with_negative_evidence_still_holds(tmp_path):
    """NEGATIVE direction + within policy + experimental only -> HOLD."""
    pol = load_policy(_write(tmp_path, _valid(cap="12.0")))
    v = decide(_ev(Direction.NEGATIVE), evaluate_constraints(_pos(), pol), _pos())
    assert {x.action for x in v} == {Action.HOLD}
    assert all(x.direction is Direction.NEGATIVE for x in v)


def test_no_policy_still_abstains():
    v = decide(_ev(), evaluate_constraints(_pos(), load_policy()), _pos())
    assert {x.action for x in v} == {Action.ABSTAIN}


def test_policy_does_not_rewrite_directional_view(tmp_path):
    ev = _ev(Direction.NEGATIVE)
    before = directional_view(ev, "1m")[0]
    pol = load_policy(_write(tmp_path, _valid(cap="10.0", target="8.0")))
    after = [v.direction for v in decide(ev, evaluate_constraints(_pos(), pol), _pos())]
    assert before is Direction.NEGATIVE and all(d is Direction.NEGATIVE for d in after)


def test_elimination_trace_consistent_under_breach(tmp_path):
    pol = load_policy(_write(tmp_path, _valid(cap="10.0", target="8.0")))
    for v in decide(_ev(), evaluate_constraints(_pos(), pol), _pos()):
        rejected = {a for a, _ in v.eliminations}
        assert v.action.value not in rejected
        assert {"ADD", "HOLD", "EXIT", "ABSTAIN"} == rejected


def test_policy_provenance_reaches_the_report_bundle():
    from pathlib import Path

    p = Path("data/product_reports/2026-07-16/AMZN/inputs.json")
    if not p.exists():
        pytest.skip("report not generated")
    pol = json.loads(p.read_text())["meta"]["policy"]
    assert pol["status"] in {"SUPPLIED", "UNAVAILABLE"}
    if pol["status"] == "UNAVAILABLE":
        assert pol["missing"] and pol["path"]
