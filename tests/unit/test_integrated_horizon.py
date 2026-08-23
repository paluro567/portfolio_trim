"""The integrated horizon object: four channels, and who is allowed to win.

The load-bearing guarantee is that the deterministic action is authoritative.
Research may annotate the presentation of a HOLD and nothing else — it cannot
soften a TRIM, harden a HOLD into an ADD, or invent a label outside the allowed
set. ``display_action`` is a total function and is enumerated exhaustively here.
"""

from __future__ import annotations

from mip.calibration.contracts import HORIZONS, HorizonCalibration, ValidationStatus, unavailable
from mip.product.contracts import Action
from mip.product.decide import decide
from mip.research_assistant.contracts import ResearchBias
from mip.research_assistant.integrated import (
    ALLOWED_DISPLAY_ACTIONS,
    build_integrated_horizons,
    display_action,
)
from tests.unit._research_support import ev, horizon_views, make_result
from tests.unit.test_product_slice import _cons, _pos


def _build(result=None, calibrations=None, pos=None):
    pos = pos or _pos()
    cons = _cons()
    evidence = [ev("ret_21d")]
    verdicts = decide(evidence, cons, pos)
    cals = (
        calibrations
        if calibrations is not None
        else {hz: unavailable(hz, "NEUTRAL", "gate failed") for hz in HORIZONS}
    )
    return build_integrated_horizons(pos, verdicts, cons, cals, result), verdicts


# ==========================================================================
# DETERMINISTIC ACTION IS AUTHORITATIVE
# ==========================================================================
def test_display_action_mapping_is_total_and_within_the_allowed_set():
    for action in ("ADD", "HOLD", "TRIM", "EXIT", "ABSTAIN"):
        for bias in list(ResearchBias) + [None]:
            label = display_action(action, bias)
            assert label in ALLOWED_DISPLAY_ACTIONS, f"{action}+{bias} -> {label}"


def test_research_can_only_annotate_a_hold():
    assert display_action("HOLD", ResearchBias.ADD_BIASED) == "ADD-BIASED HOLD"
    assert display_action("HOLD", ResearchBias.TRIM_BIASED) == "TRIM-BIASED HOLD"
    assert display_action("HOLD", ResearchBias.NEUTRAL) == "HOLD"
    assert display_action("HOLD", None) == "HOLD"


def test_exit_bias_on_a_hold_maps_to_trim_biased_not_a_new_label():
    """There is no EXIT-BIASED HOLD: a lean toward exiting is a lean toward reducing."""
    assert display_action("HOLD", ResearchBias.EXIT_BIASED) == "TRIM-BIASED HOLD"


def test_research_cannot_soften_or_harden_a_committed_action():
    for action in ("ADD", "TRIM", "EXIT"):
        for bias in ResearchBias:
            assert (
                display_action(action, bias) == action
            ), f"research must not change a deterministic {action}"


def test_integrated_object_preserves_the_deterministic_action_verbatim():
    views = horizon_views(biases=dict.fromkeys(HORIZONS, ResearchBias.ADD_BIASED))
    integrated, verdicts = _build(result=make_result(views=views))
    by_hz = {v.horizon: v for v in verdicts}

    for cell in integrated:
        verdict = by_hz[cell.horizon]
        assert cell.deterministic["action"] == verdict.action.value
        assert cell.deterministic["security_view"] == verdict.direction.value
        # The display label annotates but never replaces.
        assert cell.integrated_view["display_action"].endswith(verdict.action.value)
        assert verdict.action is Action.HOLD


# ==========================================================================
# FOUR SEPARATE CHANNELS
# ==========================================================================
def test_every_horizon_carries_all_four_channels():
    integrated, _ = _build(result=make_result())
    assert [c.horizon for c in integrated] == list(HORIZONS)
    for cell in integrated:
        for channel in ("deterministic", "historical", "research", "portfolio"):
            assert getattr(cell, channel) is not None
        assert cell.integrated_view["display_action"]
        assert cell.integrated_view["why"]


def test_channels_are_not_averaged_into_a_single_number():
    """No composite score may appear; the channels stay side by side."""
    integrated, _ = _build(result=make_result())
    for cell in integrated:
        body = cell.to_dict()
        assert "score" not in json_keys(body)
        assert "composite" not in json_keys(body)
        assert "probability" not in json_keys(body)


def json_keys(obj, acc=None) -> set:
    acc = acc if acc is not None else set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(k)
            json_keys(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            json_keys(v, acc)
    return acc


def test_historical_channel_is_unavailable_when_the_gate_fails():
    integrated, _ = _build(result=make_result())
    for cell in integrated:
        assert cell.historical["validation_status"] == "UNAVAILABLE"
        assert cell.historical["sample_n"] is None
        assert cell.historical["positive_return_rate"] is None
        assert "gate failed" in (cell.historical["unavailable_reason"] or "")


def test_why_states_plainly_when_no_history_exists():
    integrated, _ = _build(result=make_result())
    why = integrated[0].integrated_view["why"]
    assert "No historical calibration is available" in why


def test_why_reports_history_when_it_is_available():
    cals = {
        hz: HorizonCalibration(
            horizon=hz,
            signal_state="NEUTRAL",
            validation_status=ValidationStatus.PROMISING_BUT_UNPROVEN,
            sample_n=412,
            positive_return_rate=0.63,
            spy_outperformance_rate=0.58,
            median_forward_return=0.084,
        )
        for hz in HORIZONS
    }
    integrated, _ = _build(result=make_result(), calibrations=cals)
    why = integrated[0].integrated_view["why"]
    assert "Historically" in why
    assert "63% positive" in why
    assert "N=412" in why


def test_research_channel_reports_absence_rather_than_inventing_a_view():
    integrated, _ = _build(result=None)
    for cell in integrated:
        assert cell.research["available"] is False
        assert cell.research["setup"] is None
        assert cell.research["conviction"] is None
    assert "No current research view" in integrated[0].integrated_view["why"]


def test_portfolio_channel_reports_the_concentration_effect():
    integrated, _ = _build(result=make_result())
    # The default fixture is 6% of a 52-position book: 3.1x equal weight.
    assert integrated[0].portfolio["concentration_effect"] == "BLOCKS_ADD"
    assert "prevents a clean ADD" in integrated[0].integrated_view["why"]


def test_unpriced_position_makes_the_concentration_effect_not_evaluable():
    pos = _pos(market_weight=None, portfolio_market_value=None, market_value=None)
    integrated, _ = _build(result=make_result(), pos=pos)
    assert integrated[0].portfolio["concentration_effect"] == "NOT_EVALUABLE"
    assert integrated[0].portfolio["weight"] is None


def test_missing_horizon_calibration_degrades_to_unavailable():
    integrated, _ = _build(result=make_result(), calibrations={})
    for cell in integrated:
        assert cell.historical["validation_status"] == "UNAVAILABLE"
