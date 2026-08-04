# GATE REGISTER

Seven formal gates. **A gate's pass condition is mechanical.** No gate may be passed by judgement where
a threshold exists.

---

## G1 — Phase 1 product validation

| | |
|---|---|
| **Inputs** | 5 completed sessions · 25 confirmatory + 5 sham + 5 score observations · 3 blinded evaluator scorings · signed `constraints_v1.0.md` |
| **Evidence** | Completed `analysis_report_template.md` §§1–11 |
| **PASS** | All six frozen conditions: net rate ≥30% · ≥3/5 participants · ≥2 distinct sections · HARM ≤25% · ≥2 IMPROVED in ≥2 participants · UNRESOLVED ≤30% ∧ blinding ≤65% |
| **FAIL** | Any one: net <15% · ≥4/5 unmoved · recruitment failure · HARM >40% · any participant ≥2 DEGRADED |
| **AMBIGUOUS** | All other combinations |
| **Authority** | Mechanical from §7.3. Analyst computes; moderator co-signs. **No override.** Dissent recorded, result stands |
| **Artifacts** | Signed final report · deviation logs · disagreement log · hashes |
| **Unlocks** | G2 → V4 production engineering |
| **Blocks permanently on FAIL** | All V4 production engineering. 90-day pause. Resumption requires a new hypothesis and a different sponsor. **A FAIL may not be answered by rewriting the report and re-testing** |

## G2 — V4 engineering authorization

| | |
|---|---|
| **Inputs** | G1 = PASS · V4 architecture set (10 docs) · repo inventory |
| **PASS** | G1 PASS **and** the architecture set is unamended since the CIO review |
| **FAIL** | G1 FAIL |
| **AMBIGUOUS** | G1 AMBIGUOUS → **only the single authorised follow-up proceeds**; no V4 code |
| **Authority** | Program Execution Director on the mechanical G1 result |
| **Unlocks** | V4 P0–P9 |
| **Blocks on FAIL** | Everything in Track B2 |

## G3 — Evidence source reaches descriptive CONTEXT

| | |
|---|---|
| **Inputs** | ≥1 `EvidenceSource` instrumented at SHADOW · ≥20 calendar episodes · independent verification path |
| **Evidence** | V5 scorecard: coverage · completeness · PIT integrity · reproducibility · revision rate · **state agreement** |
| **PASS** | `state_agreement ≥ 0.80` **and** PIT poisoning passes **and** reproducibility byte-identical **and** `episodes ≥ 20` **and** `completeness ≥ 0.95` on claimed cells |
| **FAIL** | Any mandatory criterion missed on **two** consecutive quarterly recomputations |
| **AMBIGUOUS** | Single-quarter miss → remains SHADOW, recompute next quarter |
| **Authority** | Reliability Ledger writer (not the Decision Engine, not the architect acting as engine owner) |
| **Unlocks** | The source is displayed in reports at **zero contribution** |
| **Blocks on FAIL** | That source. Not the programme |

## G4 — Evidence source reaches ADVISORY

| | |
|---|---|
| **Inputs** | G3 passed for that source · ≥2 distinct regimes observed · episode floor met |
| **PASS** | G3 **and** descriptive stability across ≥2 regimes **and** `episodes ≥ 40` **and** revision rate ≤ 0.10 |
| **FAIL** | Stability fails in ≥2 regimes, or revision rate >0.25 |
| **AMBIGUOUS** | Only one regime observed → hold at CONTEXT until a second exists |
| **Authority** | Ledger writer |
| **Unlocks** | The source may modulate **conviction, magnitude, urgency** — **never flip an action**. Contributes to frozen-decision condition 5B |
| **Blocks on FAIL** | Automatic demotion to CONTEXT |

> **Interpretation recorded (F1):** the directional MDE is a *directional*-promotion input. Descriptive
> ADVISORY requires the episode floor above. Frozen decision 5 requires **G4 ∧ G5** before purchase
> regardless, so no sequencing changes.

## G5 — MDE and pipeline sensitivity acceptable

| | |
|---|---|
| **Inputs** | V6 three-arm positive control complete · full sweep executed |
| **Evidence** | MDE surface (effect × breadth × years × horizon) · Arm2−Arm1 loss · false-positive calibration |
| **PASS** | **MDE ≤ 0.03 IC at an attainable configuration** (≤500 names × ≤20 years) at 80% power |
| **FAIL** | **MDE > 0.05 IC at every attainable configuration** → clean data can never be decisive |
| **AMBIGUOUS** | MDE 0.03–0.05 → purchase permitted **only** with the reduced claim declared in advance |
| **Authority** | Program Execution Director on the sweep output. Pre-registered before the sweep runs |
| **Unlocks** | Condition 5A of the frozen decisions |
| **Blocks permanently on FAIL** | **G6 and G7.** No data purchase is ever authorised. The prediction programme terminates and the product is redefined |

## G6 — Commercial clean-data purchase authorization

| | |
|---|---|
| **Inputs** | G4 (≥1 source) **and** G5 · remaining-blocker analysis · provider capability matrix |
| **PASS** | **All four**: (1) ≥1 source at ADVISORY · (2) G5 PASS or declared-AMBIGUOUS · (3) survivorship / delisting / identity / PIT-universe are demonstrably the **remaining** blockers to DIRECTIONAL · (4) a provider meets every mandatory capability within cost and engineering ceilings |
| **FAIL** | Any condition unmet |
| **AMBIGUOUS** | Conditions 1–3 met, no provider qualifies → **do not purchase**; re-scan quarterly |
| **Authority** | **Sponsor (CIO).** The only gate reserved to the sponsor |
| **Artifacts** | Signed authorization citing the specific ADVISORY source and the MDE figure |
| **Unlocks** | V7 |
| **Blocks on FAIL** | V7 and G7 |

## G7 — First DIRECTIONAL promotion

| | |
|---|---|
| **Inputs** | Clean dataset ingested and validated · V7 walk-forward complete on the ADVISORY source |
| **PASS** | Directional score with a block-bootstrap CI **excluding zero** on an embargoed holdout, **sustained ≥4 quarters**, Brier skill >0 |
| **FAIL** | CI includes zero after the full study **at adequate power** → the source does not predict returns |
| **AMBIGUOUS** | Underpowered despite clean data → **invoke the S4 rule: this is a stop, not a request for more data** |
| **Authority** | Ledger writer; sponsor countersigns the first-ever promotion |
| **Unlocks** | Evidence may flip actions. Horizon differentiation by evidence. **The vision becomes reachable** |
| **Blocks on FAIL** | The platform is permanently a policy-and-explanation engine. **Formal product redefinition** |

## Gate dependency summary

```
G1 ──PASS──> G2 ──> V4 P0-P9
G3 ──> G4 ──┐
G5 ─────────┴──> G6 ──> V7 ──> G7
```

**G3, G4 and G5 do not depend on G1 or G2.** Science proceeds in parallel with product validation.
