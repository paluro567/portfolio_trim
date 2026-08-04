# V6 — Final Scientific Determination

**Issuing body:** V6 Scientific Program Closure and Repository Integrity Lead
**Effective date:** 2026-08-04 · **Status:** CANONICAL. Closes the V6 research branch.

---

## A. Software-correctness findings

| # | Conclusion | Class | Basis |
|---|---|---|---|
| A1 | **Recovered-SE weighting inversion.** `se = |effect/z_raw|` made `w = (z/effect)²`, so a model reporting a larger effect received a smaller weight. Measured `spearman(|effect|, weight) = −0.7228`. | **ESTABLISHED** | Defect inventory, 36,926 model-cell records |
| A2 | **Unbounded weights as effect → 0.** Weight is `∝ effect⁻²`; near-zero effects drew 11–12× the panel median weight. No exact-zero effect occurred in this panel, so no infinity materialized. | **ESTABLISHED (bounded in practice)** | 253 records at `|effect| < 1e-4` |
| A3 | **The defect is mechanically eliminated by the preregistered repair.** | **ESTABLISHED** | max top-model share 0.878 → 0.628; effective models 3.91 → 4.13; `spearman(n_eff, w)` +0.48 → +0.68 |
| A4 | **The defect is unacceptable as software regardless of performance.** | **ESTABLISHED** | Patched at `src/mip/engine/evidence.py`; absent from active code; 17 regression tests |
| A5 | **Validation-layer sensitivity.** The measurement layer is unbiased and efficient; recovers injected IC without systematic bias. | **ESTABLISHED** | Arm 1; `bias` bitwise identical across 84 cells under the audit |
| A6 | **Combiner information loss.** The combiner does not destroy signal at its frozen endpoint. | **ESTABLISHED** | Arm 1.5; 0 sign flips, 0 CI zero-exclusion flips |
| A7 | **Arm 1 / Arm 1.5 reproducibility.** Both reproduce under corrected average-rank tie handling. | **ESTABLISHED** | Reproducibility audit; Arm 1.5 bit-perfect (0.000e+00) |
| A8 | **Arm 1 extended-grid provenance.** The published recovery curve splices two runs with different bootstrap resolutions and seed streams. | **ESTABLISHED** | A-2026-003 |
| A9 | **Arm 1 published extended-grid values are not reproducible from the audit re-run.** Published 1y recovery at IC 0.15 = 0.405 and 0.40 = 0.915; the audit's re-run gave 0.340 and 0.900. | **UNRESOLVED — see B-07** | This closure, §Part 2 |

## B. Forecasting-performance findings

| # | Conclusion | Class | Basis |
|---|---|---|---|
| B1 | **Recovered-SE causal relevance to performance.** The defect did **not** cause the measured forecasting failure. | **ESTABLISHED (and the prior causal claim WITHDRAWN)** | Repair experiment: 0 PASS, 1 FAIL, 5 INCONCLUSIVE |
| B2 | **Repaired ensemble vs original.** Does not beat it; directionally worse at 5 of 6 horizons, significantly worse at 1w (ΔBrier −0.0062, CI [−0.0109, −0.0005]). | **ESTABLISHED** | Repair experiment primary endpoint |
| B3 | **Ensemble performance.** Every tested ensemble variant loses to the constant-50% forecaster at all 6 horizons, significantly at 5 of 6, by ≈0.05–0.08 Brier. | **ESTABLISHED** | Repair experiment; replicates the prior paired-baseline study |
| B4 | **Equal-weight performance.** Beaten by both the original and the repaired ensemble at all 6 horizons once the calibration scale is held fixed. Its previously reported advantage was attributable to **shrinkage**, not to better weighting. | **ESTABLISHED — prior root-cause finding CONFIRMED** | Repair experiment secondary; `k_h` normalization |
| B5 | **Simple-baseline / constant-50% performance.** The uninformed constant forecaster is the best-performing method tested on the frozen metric. | **ESTABLISHED** | Brier 0.25 vs 0.291–0.336 for every variant |
| B6 | **Complex weighting.** Not scientifically justified. | **ESTABLISHED** | B2 + B3 + B4 |
| B7 | **Calibration overclaim.** Emitted probabilities (`p_up = evidence_score/100`) are worse than an uninformed constant at nearly every horizon; the platform's probability outputs are not calibrated in any useful sense. | **ESTABLISHED** | B3, B5 |
| B8 | **Confidence validity.** `combined_confidence` derives from evidence volume × agreement and has never been validated against realized directional accuracy. It carries no demonstrated directional reliability. | **NARROWED — no directional validity established** | Never tested in V6 |

## C. Retired

| # | Conclusion | Class |
|---|---|---|
| C1 | **Arm 2 feasibility.** Maximum genuine live consumer count is 1 against a requirement of 2; structurally unreachable on this substrate. | **RETIRED — permanently** |
| C2 | Further directional ensemble development. | **RETIRED** |
| C3 | Arm 2 Addendum A (contains the falsified `ret_21d` partition). | **WITHDRAWN** |

## D. Scientific uncertainties that remain UNRESOLVED

| # | Question | Why it is unresolved |
|---|---|---|
| D1 | **Does real predictive signal exist in these features or models?** | **UNRESOLVED.** V6 tested the *plumbing* — measurement layer, combiner, weighting — and one ensemble configuration on one class-B panel. It never tested whether any individual model carries standalone skill. |
| D2 | Would fundamentals-driven models contribute? | Unresolved — 3 of 7 models emit constant output; PIT fundamentals unavailable. |
| D3 | Does feature information propagate to consuming models? | Unresolved and **not further pursued** — the substrate cannot support the test. |
| D4 | Would a differently constituted universe change the result? | Unresolved; prior evidence indicates breadth saturates. |
| D5 | The Arm 1 extended-grid reproduction gap (A9). | Unresolved; see B-07. |

### Explicit scope limit

**This determination concerns one ensemble implementation evaluated on one restored class-B panel of 10 symbols, 3,252 cohort cells, with 3 of 7 models inactive.**

It establishes that *this* ensemble, under *these* weightings, on *this* panel, does not beat an uninformed constant forecaster. **It does not establish — and must not be read as establishing — that markets are unpredictable, that no predictive signal exists in these data, or that the general approach is unworkable.** Those questions (D1–D4) remain open and were never tested.
