# Amendment A-2026-007 — Post-Peer-Review Corrections

**Issuing body:** Research Program Rebaseline Committee · **Effective:** 2026-08-04 · **Version:** 1.0
**Amends:** the V6 canonical record following external peer review. **Appended, not applied in place. No prior document is rewritten. All originals stand in `docs/v6/archive/original_pre_amendment/` with recorded hashes.**

## Corrections

| # | Document | Original claim | Action | Exact replacement | Type |
|---|---|---|---|---|---|
| 1 | `V6_FINAL_SCIENTIFIC_DETERMINATION.md` B3 | "Every tested ensemble variant loses to the constant-50% forecaster at all 6 horizons, significantly at 5 of 6." | **NARROW** | "On a seven-security panel, every tested ensemble variant produced worse *probability forecasts* than a constant-50% forecaster at all six horizons. Decomposition attributes 107–132% of the Brier excess to score dispersion (SD(p) = 0.220–0.246); the discrimination term is small and sign-inconsistent. Reported significance derives from a bootstrap over seven clusters and is not reliable. This is a calibration finding on one panel and supports no cross-sectional claim." | Statistical |
| 2 | `V6_FINAL_SCIENTIFIC_DETERMINATION.md` B6 | "Complex weighting is not scientifically justified." | **WITHDRAW** | "Three weighting schemes were compared at fixed calibration scale on one seven-security panel. None improved Brier. Complex weighting is **not tested** in any general sense." | Scientific |
| 3 | `V6_FINAL_SCIENTIFIC_DETERMINATION.md` B4 | "Equal-weight … beaten by both the original and the repaired ensemble at all 6 horizons." | **NARROW** | Prefix: "Descriptive result on the seven-security panel; intervals unreliable (7-cluster bootstrap)." | Statistical |
| 4 | `V6_FINAL_SCIENTIFIC_DETERMINATION.md` A5 | "The measurement layer is unbiased and efficient." | **NARROW** | "The measurement layer is **unbiased** (bias bitwise identical across 84 cells). Its **efficiency claim is suspended**: the block bootstrap resamples seven clusters and its measured false-positive rate ranges 0.020–0.095 against a nominal 0.05." | Statistical |
| 5 | `V6_ARM15_RESULTS.md` — headline | "The combiner does not destroy signal." | **SUSPEND** | "No information loss was detected. The panel carries no measurable IC at any horizon, so this test had no power to detect loss. The result is **uninformative**, not negative." | Scientific |
| 6 | All documents | "cross-sectional IC" / "cross-sectional discrimination" | **REPLACE (terminology)** | "**pooled symbol-date rank correlation**" — with seven securities the statistic is predominantly time-series. | Documentary |
| 7 | `V6_ARM1_RESULTS.md`, `V6_ARM1_MDE_TABLE.csv` | MDE reported without accompanying null-interpretation guidance | **REPLACE (add)** | "Empirical MDE₈₀ ranges 0.10 (1w) to 0.40 (1y). An IC of 0.03–0.05 was undetectable at every horizon. **No null IC result in this record constitutes evidence of absence.**" | Statistical |
| 8 | `V6_RECOVERED_SE_REPAIR_DECISION.md` | "constant-50% forecaster" as the trivial benchmark | **NARROW** | "Constant-50% is the point-in-time-legitimate trivial benchmark but not the strongest. The realised base rate falls to ȳ = 0.356 at 1y, where a constant p = ȳ scores Brier 0.2291 versus 0.2500. The ensemble loses to both; p = ȳ is in-sample and not a legitimate competitor." | Statistical |
| 9 | Data section, all documents | universe described without provenance | **REPLACE (add)** | "The research universe is **seven securities selected as the author's portfolio holdings** (ADBE, AMD, AMZN, CRM, HNST, NOW, TSLA), 2019-01-02 → 2026-06-26. Selection is conditioned on being held at the study date. This is selection-on-the-outcome and precludes any cross-sectional generalisation." | Scientific |
| 10 | `V6_RED_TEAM_REVIEW.md` item 8 | "effectively two models" | **WITHDRAW** | "Six of seven models participated in the tested archived panel, five with within-date cross-sectional SD of 19.5–25.0 score points. The dead/constant-model finding applies to the restored environment, not to the repair experiment." | Scientific |
| 11 | Programme-wide | Arm 1 and Arm 1.5 presented as reproducible | **SUSPEND** | "Arm 1 and Arm 1.5 are **not independently reproducible**: their harnesses are absent from any durable location. Their results stand as recorded but cannot presently be re-executed." | Documentary |
| 12 | `V6_ARM1_MDE_TABLE.csv`, extended grid | published values | **RETAIN, flagged** | Blocker **B-07 remains open**: the authors' own audit re-run yielded 0.340 and 0.900 where the published file holds 0.405 and 0.915. Unresolved. | Statistical |

## Claims explicitly RETAINED unchanged

| Claim | Why it survives |
|---|---|
| Recovered-SE inversion, `spearman(|effect|, w) = −0.7228`; `w ∝ effect⁻²` | Algebraic identity; no sampling inference |
| 5 of 6 nominal `ret_21d` consumers byte-identical under ρ=0.30 injection | Deterministic software fact |
| Max 1 genuine live consumer across 23 features at ±8σ, 150 cells | Mechanistic causal result |
| Brier decomposition: dispersion = 107–132% of excess | Exact algebra on completed outputs |
| Arm 2 permanently retired | Structural; unrescuable by power |
| Production defect patched; 551 tests pass | Deterministic software fact |

## Signatures
| Role | Name | Date | Signature |
|---|---|---|---|
| Rebaseline Committee Chair | — | — | *unsigned* |
| External Peer Review Panel | — | — | *unsigned* |

## Hash field
*Pending — the working tree carries uncommitted paths; a hash over an uncommitted tree binds nothing.*
