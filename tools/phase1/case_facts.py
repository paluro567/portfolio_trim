"""Phase 1 study case facts — INPUTS ONLY.

Transcribed once from the frozen participant packets. Contains no derived value
and no narrative. Every derived figure is recomputed by verify_reports.py and
checked against what the packets actually state.

Authority: docs/phase1/01_participant/*.md remain the authoritative presentation
artifacts. This file is an input mirror for verification, never a generator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal as D


@dataclass(frozen=True)
class Policy:
    name: str
    portfolio_value: D
    n_positions: int
    hard_cap_pct: D
    core_target_pct: D
    band_pp: D
    sector_cap_pct: D
    liquidity_limit_days: D
    gains_budget: D
    gains_used: D

    @property
    def gains_remaining(self) -> D:
        return self.gains_budget - self.gains_used


MERIDIAN = Policy(
    name="Meridian",
    portfolio_value=D("12000000"),
    n_positions=24,
    hard_cap_pct=D("15.0"),
    core_target_pct=D("5.0"),
    band_pp=D("2.0"),
    sector_cap_pct=D("30.0"),
    liquidity_limit_days=D("2.0"),
    gains_budget=D("180000"),
    gains_used=D("120000"),
)


@dataclass(frozen=True)
class CaseFacts:
    case_id: str
    name: str
    has_report: bool
    weight_pct: D
    position_value: D
    target_pct: D | None
    cost_basis: D
    unrealised: D            # signed: + gain, - loss
    adv_20d: D
    sector_exposure_pct: D
    prior_weight_pct: D
    lots_short_pct: D = D("0")
    correlations: tuple = ()
    catalyst_days: int | None = None
    # Which limit governs the mandate, if any.
    mandate: str | None = None        # "CAP" | "BAND" | None


CASES: dict[str, CaseFacts] = {
    "A": CaseFacts("A", "NOVA", True, D("28.4"), D("3410000"), None,
                   D("830000"), D("2580000"), D("210000000"), D("34.1"),
                   D("26.1"), correlations=(D("0.71"), D("0.66")), mandate="CAP"),
    "B": CaseFacts("B", "HELIX", True, D("3.1"), D("372000"), D("5.0"),
                   D("410000"), D("-38000"), D("44000000"), D("3.1"),
                   D("3.4"), lots_short_pct=D("100"), catalyst_days=4, mandate=None),
    "C": CaseFacts("C", "ATLAS", True, D("19.2"), D("2300000"), None,
                   D("520000"), D("1780000"), D("95000000"), D("26.8"),
                   D("17.9"), lots_short_pct=D("22"), mandate="CAP"),
    "D": CaseFacts("D", "VERTEX", True, D("2.8"), D("336000"), D("3.0"),
                   D("600000"), D("-264000"), D("18000000"), D("8.2"),
                   D("2.9"), mandate=None),
    "E": CaseFacts("E", "ORION", True, D("8.1"), D("972000"), D("8.0"),
                   D("700000"), D("272000"), D("61000000"), D("19.4"),
                   D("8.3"), mandate=None),
    "F": CaseFacts("F", "PINNACLE", False, D("6.2"), D("744000"), D("6.0"),
                   D("690000"), D("54000"), D("27000000"), D("11.1"),
                   D("6.0"), mandate=None),
    "G": CaseFacts("G", "CASCADE", True, D("11.2"), D("1340000"), D("5.0"),
                   D("820000"), D("524000"), D("38000000"), D("14.6"),
                   D("10.6"), mandate="BAND"),
}

# ---------------------------------------------------------------------------
# AUTHORED NARRATIVE — declared explicitly so the verifier never treats these
# as derivable. Anything listed here is prose, not arithmetic.
# ---------------------------------------------------------------------------
AUTHORED_NARRATIVE = {
    "evidence_claim_text",
    "elimination_rule_wording",
    "abstention_statement",
    "confidence_statement",
    "what_changed_prose",
    "catalyst_source_attribution",
    "action_strength_score",          # Case G only; deleted in V3
    "action_strength_decomposition",  # Case G only
    "terminal_wealth_text",           # fixed constant, Amendment 001 A-004
}

# Quantities that CANNOT be recomputed from the facts above, with the reason.
NOT_RECOMPUTABLE = {
    "portfolio_hhi_total":
        "requires all 24 position weights; only 1 is specified per case "
        "(Amendment 002 D-02 — replaced by own-contribution w^2)",
    "sector_exposure_after_action":
        "assumes the whole reduction leaves the sector; not verifiable from "
        "single-position facts (reported, not asserted)",
    "correlation_cluster_delta":
        "requires the full covariance matrix",
}
