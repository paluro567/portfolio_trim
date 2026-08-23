"""The deterministic payload: what the model is allowed to be told.

The payload is the boundary between "computed by Python" and "interpreted by a
model". These tests pin that boundary: the numbers must arrive intact and
lossless, the caveats must travel with them, and the hash must change when and
only when a deterministic input changes.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from mip.product.contracts import Direction
from mip.product.decide import decide
from mip.research_assistant.payload import build_payload
from tests.unit._research_support import ev
from tests.unit.test_product_slice import _cons, _pos


def _payload(pos=None, evidence=None, cons=None, **kw):
    pos = pos or _pos()
    cons = cons or _cons()
    evidence = evidence if evidence is not None else [ev("ret_21d")]
    verdicts = decide(evidence, cons, pos)
    return build_payload(pos, evidence, cons, verdicts, **kw)


# ------------------------------------------------------------------- fidelity
def test_position_numbers_reach_the_payload_exactly():
    p = _payload()
    position = p.body["position"]
    assert position["quantity"] == "10"
    assert position["average_cost"] == "100"
    assert position["current_price"] == "110"
    assert position["market_value"] == "1100"
    assert position["cost_basis"] == "1000"
    assert position["unrealized_pnl"] == "100"
    assert position["unrealized_pct"] == "0.10"
    assert position["market_weight"] == "0.06"
    assert position["portfolio_positions"] == 52


def test_numbers_travel_as_strings_so_float_rounding_cannot_alter_them():
    body = _payload().body
    encoded = json.dumps(body)
    assert '"market_weight": "0.06"' in encoded
    # No bare floats anywhere in the position block.
    assert all(not isinstance(v, float) for v in body["position"].values())


def test_equal_weight_multiple_is_computed_not_asked_for():
    # 0.06 of a 52-position book is 3.12x an equal weight of 1/52.
    assert _payload().body["position"]["equal_weight_multiple"] == "3.12"


def test_missing_market_weight_yields_no_multiple_rather_than_a_guess():
    p = _payload(pos=_pos(market_weight=None, portfolio_market_value=None))
    assert p.body["position"]["equal_weight_multiple"] is None
    assert p.body["position"]["market_weight"] is None


def test_own_history_percentile_is_parsed_out_of_the_slice_explanation():
    p = _payload(evidence=[ev("ret_21d", explanation="21-session return; 23% of its own history")])
    assert p.body["price_state"]["ret_21d"]["own_history_percentile"] == 23


def test_percentile_absent_when_the_explanation_carries_none():
    p = _payload(evidence=[ev("ret_21d", explanation="21-session return")])
    assert p.body["price_state"]["ret_21d"]["own_history_percentile"] is None


def test_absent_features_are_explicit_nulls_not_omissions():
    body = _payload(evidence=[ev("ret_21d")]).body
    assert "ret_252d" in body["price_state"]
    assert body["price_state"]["ret_252d"] is None


# ----------------------------------------------------------------- verdicts
def test_deterministic_verdicts_travel_with_their_full_audit_trail():
    body = _payload().body
    rows = body["deterministic_verdicts"]
    assert {r["horizon"] for r in rows} == {"1w", "1m", "3m", "6m", "1y"}
    row = rows[0]
    for key in (
        "action",
        "confidence",
        "confidence_basis",
        "conflicts",
        "contributing_groups",
        "elimination_trace",
        "rationale",
        "security_view",
    ):
        assert key in row, key
    assert row["elimination_trace"], "the elimination trace must reach the model"


def test_conflicted_view_is_reported_as_conflicted():
    evidence = [
        ev("ret_21d", "absolute_momentum", Direction.POSITIVE),
        ev("rel_ret_sector_63d", "sector_relative", Direction.NEGATIVE, domain="sector"),
    ]
    body = _payload(evidence=evidence).body
    views = {r["horizon"]: r["security_view"] for r in body["deterministic_verdicts"]}
    assert views["1m"] == "CONFLICTED"


# ------------------------------------------------------------------- caveats
def test_caveats_block_carries_the_honesty_apparatus():
    caveats = _payload().body["caveats"]
    assert "no directional signal" in caveats["validation_status"].lower()
    assert caveats["survivorship_limitation"]
    assert len(caveats["non_pit_limitations"]) >= 3
    assert caveats["evidence_limitations"], "per-item limitations must travel"


def test_unsupported_positions_note_is_carried_when_supplied():
    p = _payload(unsupported_positions_note="options excluded")
    assert p.body["caveats"]["unsupported_positions"] == "options excluded"


def test_fundamentals_snapshot_limitation_is_always_present():
    text = _payload().body["fundamentals"]["snapshot_limitation"]
    assert "no fundamentals history" in text.lower()


def test_identity_carries_the_non_pit_classification_caveat():
    p = _payload(sector="Information Technology")
    identity = p.body["identity"]
    assert identity["sector"] == "Information Technology"
    assert "not point-in-time" in identity["sector_classification_caveat"]


# --------------------------------------------------------------------- hash
def test_hash_is_stable_across_identical_builds():
    assert _payload().content_hash() == _payload().content_hash()


def test_hash_changes_when_a_deterministic_input_changes():
    before = _payload().content_hash()
    after = _payload(pos=_pos(market_price=Decimal("111"))).content_hash()
    assert before != after


def test_hash_changes_when_evidence_direction_changes():
    a = _payload(evidence=[ev("ret_21d", direction=Direction.POSITIVE)]).content_hash()
    b = _payload(evidence=[ev("ret_21d", direction=Direction.NEGATIVE)]).content_hash()
    assert a != b


def test_payload_is_json_serialisable_for_the_prompt():
    text = _payload().as_prompt_json()
    assert json.loads(text)["identity"]["symbol"] == "TEST"


def test_market_context_is_merged_when_supplied():
    p = _payload(
        market_context={"benchmarks": {"SPY": {"ret_21d": "0.01"}}, "macro": {"vix_level": "14"}}
    )
    env = p.body["market_environment"]
    assert env["benchmarks"]["SPY"]["ret_21d"] == "0.01"
    assert env["macro"]["vix_level"] == "14"
    assert env["product_evidence"] is not None


def test_payload_never_contains_a_secret():
    """Nothing resembling a key or a DSN may reach the prompt."""
    text = _payload().as_prompt_json().lower()
    for forbidden in ("api_key", "openai_api_key", "postgresql://", "password", "sk-"):
        assert forbidden not in text, forbidden


def test_build_payload_does_no_io():
    """Pure function: it must work with no session, no network, no filesystem."""
    assert _payload(company_name=None, sector=None, industry=None).symbol == "TEST"


def test_as_of_is_carried_so_research_can_be_time_boxed():
    p = _payload()
    assert p.as_of == date(2026, 7, 16)
    assert p.body["identity"]["as_of"] == "2026-07-16"
