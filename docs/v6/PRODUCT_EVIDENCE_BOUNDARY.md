# Product Evidence Boundary

**Date:** 2026-08-04 · Governs what the portfolio decision-support product may assert.

## Two standards, deliberately different

| | **Publication-quality cross-sectional claim** | **Personal portfolio decision-support** |
|---|---|---|
| **Required sample** | ≥100 securities, ≥30 independent resampling clusters, MDE ≤ 0.03 predeclared | The user's actual holdings. Breadth is irrelevant — the product describes *their* portfolio. |
| **Universe** | Survivorship-controlled, PIT constituents, delisted included | The holdings themselves. Selection bias is **not a defect** here: the user wants facts about what they own. |
| **Data quality** | PIT-clean, corporate actions, identifier history, PIT fundamentals | PIT-clean prices and corporate actions. Fundamentals optional if no claim depends on them. |
| **Reproducibility** | Durable harness, environment lock, hashed provenance, independent re-execution | Deterministic report generation, hashed inputs, an archived copy of every delivered report. |
| **Acceptable inference** | Rank IC primary, calibration evaluated separately, multiplicity handled | **Descriptive only.** Counts, distributions, concentrations, exposures, dates, historical analogues explicitly labelled as history — not forecast. |
| **Acceptable limitations** | Stated scope, stated MDE beside every null | Explicit statement that **no directional reliability has been established** — displayed, not buried. |
| **Prohibited claims** | Any generalisation beyond the tested universe | Probabilities, expected returns, directional recommendations, confidence scores, composite scores implying edge. |

**The product is not held to journal standards where they are irrelevant.** A seven-holding universe is fatal to a cross-sectional claim and entirely appropriate for describing seven holdings.

**The product is held to honesty standards regardless.** Not being published is not licence to present unsupported predictive claims to a user acting on them with real money.

## PART 6 — Product component decisions

| Component | Decision | Condition |
|---|---|---|
| **Phase 1 user validation** | **PROCEED** | Unaffected by every V6 finding. It tests whether honest descriptive reports are useful — the surviving product hypothesis. |
| **Policy engine** | **PROCEED** | Built on "correct at zero signal." V6 supplies exactly the zero-signal case it was designed for. |
| **Concentration analysis** | **PROCEED** | Deterministic portfolio arithmetic. No predictive content. |
| **Liquidity analysis** | **PROCEED** | Deterministic. |
| **Tax-lot analysis** | **PROCEED** | Deterministic; arguably the highest-certainty user value in the product. |
| **Descriptive evidence** | **PROCEED WITH LIMITATIONS** | Must be labelled descriptive. No implied direction, no aggregation into a score that reads as a forecast. |
| **Catalyst reporting** | **PROCEED WITH LIMITATIONS** | Dates and facts only. No implied directional consequence. |
| **Abstention** | **PROCEED** | Now the honest default rather than a fallback. |
| **Reliability ledger** | **PROCEED WITH LIMITATIONS** | SHADOW and CONTEXT tiers only. **No promotion to ADVISORY or DIRECTIONAL** — the required evidence was never produced. |
| **Multi-horizon reports** | **PROCEED WITH LIMITATIONS** | Descriptive per horizon. No per-horizon probability or score. |
| **Directional recommendations** | **EXCLUDE** | Implementation rejected; discrimination unresolved. |
| **Calibrated probabilities** | **EXCLUDE** | Falsified: SD(p) 0.220–0.246 against Cov(d,y) ≈ 0.003. |
| **Synthetic confidence** | **EXCLUDE** | Never validated against realised accuracy. |
