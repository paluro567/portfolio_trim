# V6 — Post-Peer-Review Rebaseline

**Date:** 2026-08-04 · **Companion amendments:** `V6_AMENDMENT_007_PEER_REVIEW.md`

## PART 1 — Claim classification

| Finding | Class | Allowable scope |
|---|---|---|
| **Recovered-SE inversion** (`spearman(|effect|,w) = −0.7228`, `w ∝ effect⁻²`) | **B — Algebraic** | Universal. Holds for any input. Sample-independent. |
| **Brier decomposition** (dispersion = 107–132% of excess) | **B — Algebraic** | The decomposition is universal; the *values* are D-scope (seven securities). |
| **Calibration overclaim** (SD(p) 0.220–0.246 against Cov(d,y) ≈ 0.003) | **D — Descriptive, seven-stock panel** | The platform's emitted probabilities are grossly overconfident **on this panel**. Sufficient to bar them from product reports; insufficient for a general claim. |
| **Consumer dependency findings** (5 of 6 inert; max 1 genuine consumer at ±8σ) | **C — Mechanistic causal** | Applies to this codebase with full force; the *method* generalises to any research pipeline. |
| **Combiner information-loss claim** (Arm 1.5) | **G — Unresolved** *(reclassified from "established")* | **No allowable scope.** No power to detect loss where no signal exists. Uninformative. |
| **Arm 1 MDE findings** (empirical 0.10–0.40) | **D — Descriptive, with E-scope caveat** | Valid as a measured property of this panel and procedure. The bootstrap generating them is itself miscalibrated (FP 0.020–0.095 vs 0.05). |
| **Ensemble underperformance** | **E — Inferential, invalidated by sampling** | Direction credible; stated significance not. Descriptive only. |
| **Equal-weight comparison** | **E — Invalidated** | Descriptive on this panel; no general conclusion. |
| **Simple-baseline comparison** | **E — Invalidated, and benchmark understated** | p = ȳ beats p = 0.5 at every horizon (0.2291 vs 0.2500 at 1y). |
| **Confidence validity** | **G — Unresolved** | Never tested against realised accuracy. Not falsified — **untested**. |
| **Predictive discrimination** | **G — Unresolved (underpowered)** | Observed |IC| ≤ 0.052 against a 0.10–0.40 detection floor. Absence of evidence. |
| **Real predictive signal** | **G — Unresolved** | Untouched by V6. |
| **Arm 2 feasibility** | **C — Mechanistic causal** | Fully supported. Permanently retired. |
| **"Complex weighting is not justified"** | **F — Requires withdrawal** | Three schemes, fixed scale, one panel. |
| **Production patch + 551 passing tests** | **A — Deterministic software fact** | Universal. |

## PART 4 — Status of V6

### **STATUS C — Mechanistic software and methodology study only.**

**Not A** (valid broad predictive research): peer review establishes the sample cannot support cross-sectional claims.
**Not B** (valid seven-security case study): B would license descriptive predictive claims about these seven names. Even that is unsafe — the intervals are 7-cluster and the universe is holdings-selected, so even the case-study reading is contaminated by selection.
**Not D** (invalid, withdrawn entirely): the algebraic, deterministic and mechanistic results survive peer review intact and are genuinely useful.
**Not E:** C is exact.

V6's durable contribution is **methodological and diagnostic**, not empirical.

### Where V6 components may remain

| Venue | Permitted | Prohibited |
|---|---|---|
| **Production code** | The patched equal-uncertainty estimator; the removal of `se=|effect/z|`; the 17 regression tests | Any restoration of the defective formula; any weighting justified by V6 performance evidence |
| **Research archive** | Everything, with amendments attached | Silent deletion of any original |
| **Product reports** | Descriptive evidence, catalyst facts, abstention, explicit statement that directional reliability is unestablished | Calibrated probabilities, directional recommendations, synthetic confidence, composite probability claims |
| **Reliability ledger** | SHADOW and CONTEXT tiers | Promotion of any model to ADVISORY or DIRECTIONAL — the evidence required was never produced |
| **Future scientific work** | The injection framework, the two-stage causal consumer definition, the Brier decomposition discipline, the MDE-beside-every-null rule | Reuse of the seven-security panel for any inferential claim |

## PART 5 — Is a future adequately powered discrimination study justified?

### Classification: **JUSTIFIED LATER** — not required now, not optional, not unjustified.

| Dimension | Estimate | Basis |
|---|---|---|
| **Sample required** | ≈11× current effective sample; bootstrap SE ≤ 0.0085 for the primary endpoint | Arm 1: empirical MDE₈₀ ≈ 1.45 × 2.49 × SE; target MDE ≤ 0.03 |
| **Universe** | ≥100 survivorship-controlled securities **including delisted names**, PIT constituents | Peer review M1, M9 |
| **Independent resampling units** | ≥30 clusters (vs 7 today) | Peer review 2.3 |
| **Engineering effort** | **Moderate.** The pipeline already scales: 69 features / 855k rows in 44s for 10 symbols; ingestion 38,086 rows in 9s. Model scoring at 0.63 s/cell is the bottleneck — ~6–7 h per full pass at 100 symbols. New build required: durable harness, PIT survivorship-clean security master, delisting handling. |
| **Data requirement** | Delisted securities, PIT index constituents, corporate actions, identifier history. **Not obtainable from the current free price feed.** |
| **Cash** | Non-zero and unavoidable — survivorship control cannot be synthesised from surviving names |
| **Probability of a decisive answer** | **High (~0.8).** With MDE ≤ 0.03 predeclared, both outcomes are decisive: detection or a genuine null with power. |
| **EVI** | **High but gated.** It is the only path that resolves the one question V6 left open. |

**Why "later" and not "now":** the binding constraint on the *platform* is whether users find honest, non-predictive reports useful. That is Phase 1, it costs no data, and a negative Phase 1 result would make the discrimination study irrelevant. Sequencing the expensive study behind the cheap one is strictly dominant.

## PART 8 — Data-acquisition gate

### Classification: **REQUIRED BEFORE BROAD DISCRIMINATION TESTING** — not required immediately.

| Requirement | Status |
|---|---|
| Survivorship-controlled universe | **Unmet.** Current universe is 7 holdings; restored panel 10 symbols, all survivors. |
| Delisted securities | **Unmet and unobtainable free.** The decisive gap. |
| PIT index constituents | Unmet |
| Corporate actions | Partially met (adjusted prices in use) |
| PIT fundamentals | Unmet — 3 models are dead without them |
| Identifier history | Unmet |
| Breadth for valid inference | Unmet — 7 clusters vs ≥30 required |

**Peer review does change the gate**, but in sequencing, not in kind: survivorship control moves from "desirable" to **strictly necessary for any inferential claim**. It remains **unauthorised**, because the study it serves is not yet authorised. No purchase may precede a frozen study design.
