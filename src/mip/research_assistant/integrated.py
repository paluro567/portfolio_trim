"""Phase E — the integrated horizon object.

One object per horizon, carrying FOUR EVIDENCE CHANNELS side by side:

    deterministic  what the platform's own rules say about the security
    historical     what happened after states like this, empirically
    research       what current company-specific research says
    portfolio      what position size does to the decision

They are deliberately NOT averaged. Mechanically combining a heuristic label, an
empirical frequency and a qualitative judgment would invent a precision none of
them has. The integration is an EXPLANATION: what usually followed this state,
and does today's company-specific information make the case stronger or weaker?

The deterministic action is authoritative. ``display_action`` is derived from it
by a fixed rule and can only ever annotate it — the mapping is total, and every
output ends with the deterministic action word.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mip.calibration.contracts import HORIZONS, HorizonCalibration
from mip.product.contracts import Constraint, HorizonVerdict, PositionState
from mip.product.decide import portfolio_adjustment
from mip.research_assistant.contracts import (
    HorizonResearchView,
    InvestmentResearchResult,
    ResearchBias,
)

# §7: the complete set of labels the product may display. Anything outside this
# set is a bug, and a test enumerates the mapping to prove it cannot happen.
ALLOWED_DISPLAY_ACTIONS = frozenset(
    {"ADD", "ADD-BIASED HOLD", "HOLD", "TRIM-BIASED HOLD", "TRIM", "EXIT", "ABSTAIN"}
)

_CONCENTRATION_EFFECT = {
    "BREACH": "FORCES_REDUCTION",
    "CONCENTRATED": "BLOCKS_ADD",
    "NORMAL": "NONE",
    None: "NOT_EVALUABLE",
}


def display_action(deterministic_action: str, bias: ResearchBias | None) -> str:
    """Derive the display label. The deterministic action always wins.

    Research may bias the *presentation* of a HOLD, and nothing else. A
    deterministic ADD, TRIM or EXIT passes through untouched, because research
    has no standing to soften or harden an action the rules already committed
    to.
    """
    if deterministic_action != "HOLD" or bias is None:
        return deterministic_action
    if bias is ResearchBias.ADD_BIASED:
        return "ADD-BIASED HOLD"
    if bias in (ResearchBias.TRIM_BIASED, ResearchBias.EXIT_BIASED):
        # There is no "EXIT-BIASED HOLD" label: a research lean toward exiting a
        # position the rules say to hold is still a lean toward reducing it.
        return "TRIM-BIASED HOLD"
    return "HOLD"


@dataclass(frozen=True, slots=True)
class IntegratedHorizon:
    """The four channels for one horizon, plus the derived display label."""

    horizon: str
    deterministic: dict[str, Any]
    historical: dict[str, Any]
    research: dict[str, Any]
    portfolio: dict[str, Any]
    integrated_view: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "deterministic": self.deterministic,
            "historical": self.historical,
            "horizon": self.horizon,
            "integrated_view": self.integrated_view,
            "portfolio": self.portfolio,
            "research": self.research,
        }


def _research_block(view: HorizonResearchView | None) -> dict[str, Any]:
    if view is None:
        return {
            "available": False,
            "setup": None,
            "bias": None,
            "conviction": None,
            "rationale": None,
            "positive_driver": None,
            "negative_driver": None,
            "invalidation": None,
        }
    return {
        "available": True,
        "setup": view.setup.value,
        "bias": view.research_bias.value,
        "conviction": view.conviction.value,
        "rationale": view.rationale,
        "positive_driver": view.primary_positive_driver,
        "negative_driver": view.primary_negative_driver,
        "invalidation": view.what_changes_it,
    }


def _why(
    verdict: HorizonVerdict,
    calibration: HorizonCalibration,
    view: HorizonResearchView | None,
    concentration_effect: str,
) -> str:
    """The integrated explanation, assembled from what each channel actually said.

    Written in Python rather than asked of the model, because it must state the
    channels' relationship faithfully even when one of them is missing.
    """
    parts = [f"Deterministic view is {verdict.direction.value}, action {verdict.action.value}."]

    if calibration.available:
        parts.append(
            f"Historically, {verdict.direction.value} states: {calibration.summary_line()}."
        )
    else:
        parts.append(
            "No historical calibration is available for this state, so nothing can be said "
            "about what usually followed it."
        )

    if view is not None:
        parts.append(f"Current research reads the setup as {view.setup.value}: {view.rationale}")
    else:
        parts.append("No current research view is available for this horizon.")

    if concentration_effect == "BLOCKS_ADD":
        parts.append("Position size prevents a clean ADD regardless of the security case.")
    elif concentration_effect == "FORCES_REDUCTION":
        parts.append("A portfolio limit is breached, which overrides the security view.")

    return " ".join(parts)


def build_integrated_horizons(
    pos: PositionState,
    verdicts: list[HorizonVerdict],
    constraints: list[Constraint],
    calibrations: dict[str, HorizonCalibration],
    result: InvestmentResearchResult | None,
) -> list[IntegratedHorizon]:
    """One integrated object per horizon, in horizon order."""
    from mip.research_assistant.render import _views_by_horizon

    views = _views_by_horizon(result)
    effect, effect_text = portfolio_adjustment(pos, constraints)
    concentration_effect = _CONCENTRATION_EFFECT.get(effect, "NOT_EVALUABLE")

    by_horizon = {v.horizon: v for v in verdicts}
    out: list[IntegratedHorizon] = []

    for hz in HORIZONS:
        verdict = by_horizon.get(hz)
        if verdict is None:
            continue
        view = views.get(hz)
        calibration = calibrations.get(hz)
        if calibration is None:
            from mip.calibration.contracts import unavailable

            calibration = unavailable(hz, verdict.direction.value, "no calibration supplied")

        label = display_action(verdict.action.value, view.research_bias if view else None)
        assert label in ALLOWED_DISPLAY_ACTIONS, f"illegal display action {label!r}"

        out.append(
            IntegratedHorizon(
                horizon=hz,
                deterministic={
                    "security_view": verdict.direction.value,
                    "action": verdict.action.value,
                    "confidence": verdict.confidence.value,
                },
                historical=calibration.to_dict(),
                research=_research_block(view),
                portfolio={
                    "weight": (float(pos.market_weight) if pos.market_weight is not None else None),
                    "concentration_effect": concentration_effect,
                    "explanation": effect_text,
                },
                integrated_view={
                    "display_action": label,
                    "why": _why(verdict, calibration, view, concentration_effect),
                    "what_changes_it": (
                        view.what_changes_it if view is not None else "no research view available"
                    ),
                },
            )
        )
    return out
