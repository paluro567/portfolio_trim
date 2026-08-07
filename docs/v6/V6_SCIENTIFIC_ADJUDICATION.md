# V6 — Independent Scientific Adjudication

**Date:** 2026-08-04 · **Status:** CANONICAL. Resolves the disagreement between `V6_FINAL_SCIENTIFIC_DETERMINATION.md` (Closure) and `V6_RED_TEAM_REVIEW.md` (Red Team).
No experiments executed. Every figure below is a decomposition of completed outputs.

**Outcome in one line: the Red Team is right about the Brier claim and about power, and materially wrong about the model population. The Closure is right about what failed and wrong about what that failure means.**

---

## PART 1 — The dispute, precisely

| # | Closure claims | Red Team claims | Evidence capable of resolving it | **Adjudication** |
|---|---|---|---|---|
| 1 | Losing to constant-50% shows the ensemble has no usable signal | Brier is calibration-sensitive; it cannot speak to discrimination | Algebraic decomposition of Brier | **RED TEAM** |
| 2 | — (not addressed) | The gap is dispersion/overconfidence, not absent discrimination | Same decomposition | **RED TEAM — confirmed at every horizon** |
| 3 | Rank IC reported as a cross-check; nulls treated as informative | IC never tested at adequate power; no CIs exist | Arm 1 MDE vs observed IC | **RED TEAM — and it understated its own case** |
| 4 | A seven-model ensemble was tested | Effectively two models; 3 dead, 2 cross-sectionally constant | Per-model within-date cross-sectional SD in the archived panel | **CLOSURE — the Red Team is wrong here** |
| 5 | The repair isolated relative weighting | `k_h` froze dispersion, the dominant error | Repair spec §1.1 | **RED TEAM** |
| 6 | "Complex weighting is not scientifically justified" | Unsupported | Number and variety of weightings tested | **PARTIAL — overreach, but not for the Red Team's stated reason** |
| 7 | Predictive research retired on evidence | Merely infeasible on this substrate | MDE vs plausible effect size | **RED TEAM** |

---

## PART 2 — Forecasting dimensions, separated

| Dimension | Classification | Basis |
|---|---|---|
| **A. Discrimination** | **UNDERPOWERED** | Observed IC +0.032 (1w) against an empirical MDE₈₀ of 0.10. Cannot separate IC = 0 from IC = 0.05. |
| **B. Calibration** | **FALSIFIED** | Brier excess +0.047 to +0.060 at all six horizons; significant at 5/6 |
| **C. Sharpness / dispersion** | **FALSIFIED (grossly excessive)** | SD(p) = 0.220–0.246 — ±22–25 score points — against near-zero covariance with outcomes |
| **D. Ranking quality** | **UNDERPOWERED** | Same as A; IC sign flips across horizons within noise |
| **E. Directional accuracy** | **INCONCLUSIVE** | 0.470–0.512; no CI ever computed |
| **F. Decision usefulness** | **NOT TESTED** | No returns, costs, turnover, capacity, or abstention analysis exists anywhere in the record |

Failure in B and C is established. It does **not** transfer to A, D, E or F.

---

## PART 3 — Adjudicating the Brier claim

Exact decomposition, `d = p − 0.5`, `ȳ = mean(y)`:

> `Brier − 0.25 = E[d](1−2ȳ)` (bias) `+ E[d²]` (dispersion) `− 2·Cov(d,y)` (discrimination)

| H | n | Brier | excess | bias | dispersion | discrimination | SD(p) | Cov(d,y) | IC |
|---|---|---|---|---|---|---|---|---|---|
| 1w | 1259 | 0.3097 | +0.0597 | −0.0021 | 0.0679 | −0.0061 | 0.228 | **+0.00306** | +0.0316 |
| 2w | 1259 | 0.3059 | +0.0559 | −0.0024 | 0.0605 | −0.0021 | 0.233 | +0.00106 | +0.0115 |
| 1m | 419 | 0.2991 | +0.0491 | −0.0092 | 0.0548 | +0.0035 | 0.220 | −0.00174 | −0.0305 |
| 3m | 178 | 0.3089 | +0.0589 | −0.0068 | 0.0632 | +0.0025 | 0.246 | −0.00126 | −0.0166 |
| 6m | 92 | 0.3095 | +0.0595 | −0.0190 | 0.0664 | +0.0121 | 0.242 | −0.00604 | −0.0521 |
| 1y | 45 | 0.2966 | +0.0466 | −0.0192 | 0.0614 | +0.0044 | 0.239 | −0.00220 | +0.0269 |

**Share of the excess:**

| H | bias | **dispersion** | discrimination |
|---|---|---|---|
| 1w | −3.5% | **113.8%** | −10.3% |
| 2w | −4.3% | **108.1%** | −3.8% |
| 1m | −18.8% | **111.7%** | +7.1% |
| 3m | −11.5% | **107.3%** | +4.3% |
| 6m | −32.0% | **111.7%** | +20.3% |
| 1y | −41.2% | **131.7%** | +9.4% |

### Ruling

The statement *"every ensemble variant loses to the constant-50% forecaster"* supports a conclusion about **calibration only**.

**Dispersion accounts for 107–132% of the Brier excess at every horizon.** The Red Team's central claim is confirmed quantitatively and without qualification. The system emits ±22–25 score points of confidence while carrying covariance with outcomes of order 0.003. The bias term is *negative* everywhere — it slightly *helps* Brier. The discrimination term is small and **sign-inconsistent**: it helps at 1w/2w and hurts at 1m/3m/6m/1y.

**What this proves:** the platform's emitted probabilities are grossly overconfident and are worse than uninformed. That is a real, decisive, permanent finding.

**What it does not prove:** anything about whether the underlying ranking carries information. A forecaster with IC = +0.05 and SD(p) = 0.23 would produce almost exactly the observed Brier. The metric cannot separate the two, and no metric that can was tested inferentially.

---

## PART 4 — Adjudicating power

Arm 1 **rejected** the analytic formula: measured `empirical/analytic` = 1.28–1.60. The empirical MDE is therefore the governing figure. *(The Red Team quoted the analytic value, 0.069, and so understated the problem.)*

| H | observed IC | SE (Arm 1, matched n) | **empirical MDE₈₀** | detectable? IC=0.03 | detectable? IC=0.05 |
|---|---|---|---|---|---|
| 1w | +0.0316 | 0.0278 | **0.10** | **No** | **No** |
| 2w | +0.0115 | 0.0278 | 0.10 | No | No |
| 1m | −0.0305 | 0.0472 | 0.15 | No | No |
| 3m | −0.0166 | 0.0689 | 0.25 | No | No |
| 6m | −0.0521 | 0.0882 | 0.30 | No | No |
| 1y | +0.0269 | 0.1007 | 0.40 | No | No |

No confidence interval for rank IC exists anywhere in the record — verified: `V6_RECOVERED_SE_REPAIR_PAIRED_RESULTS.csv` carries `ic_A, ic_B, ic_C` and no interval columns.

### Ruling: **ABSENCE OF EVIDENCE.**

At no horizon could the study have detected an IC of 0.03 or 0.05. The best-powered horizon has a detection floor **3.2× above** its own observed point estimate. The observed IC at 1w (+0.032) is precisely the magnitude the design cannot resolve. Null IC results here carry essentially no evidential weight against the existence of modest signal.

---

## PART 5 — Adjudicating the model population · **the Red Team is wrong**

The Red Team asserted that 3 models were dead and 2 of 4 survivors were cross-sectionally constant, leaving "effectively two models." **That describes the RESTORED environment (Arm 2 readiness, 2026-08-01), not the ARCHIVED panel the repair experiment actually ran on.** The two were conflated.

Archived panel, per model — within-date SD of score across symbols:

| Model | records | % neutral | **within-date cross-sectional SD** | classification |
|---|---|---|---|---|
| interest_rate_sensitivity | 7584 | 1.4% | **19.51** | genuinely cross-sectional |
| macro_regime | 7584 | 2.5% | **21.93** | genuinely cross-sectional |
| sector_rotation | 7602 | 1.3% | **20.00** | genuinely cross-sectional |
| momentum_exhaustion | 7938 | 9.7% | **24.47** | genuinely cross-sectional |
| relative_strength | 7938 | 17.2% | **24.98** | genuinely cross-sectional |
| earnings_behavior | 7938 | 89.7% | 19.31 | sporadic (active ~10%) |
| valuation | 7938 | **100%** | — | **dead** |

**Ruling:** the tested configuration had **five fully participating, cross-sectionally varying models**, one sporadic, one dead. The Red Team's inference — that market-scope *feature inputs* imply constant cross-sectional *output* — is false: `interest_rate_sensitivity` and `macro_regime` detect a common regime and then score each symbol by that symbol's own historical sensitivity to it, giving within-date SD of ~20 points.

Conclusions drawn from the ensemble must be narrowed from "seven models" to **"six participating, five reliably so"** — a real but modest narrowing. They need **not** be narrowed to a degenerate substrate.

One genuine limitation the Red Team missed: the archived panel spans **7 symbols**, not 10. A cross-sectional rank statistic over 7 names is intrinsically noisy, which compounds Part 4.

---

## PART 6 — Adjudicating the recovered-SE experiment

| # | Claim | Ruling |
|---|---|---|
| 1 | The weighting formula was mechanically defective | **SUPPORTED** — `spearman(|effect|, w) = −0.7228`; `w ∝ effect⁻²` |
| 2 | The repair removed the defect | **SUPPORTED** — top-model share 0.878 → 0.628; effective models 3.91 → 4.13 |
| 3 | The repair did not improve Brier | **SUPPORTED** — 0 PASS, 1 FAIL, 5 INCONCLUSIVE |
| 4 | The repair did not improve discrimination | **OVERREACH** — no IC interval was computed; the comparison is a point estimate with no inference |
| 5 | `k_h` limited what the experiment could establish | **SUPPORTED** — matching `median|z|` to the defective system pinned dispersion, which the Part 3 decomposition shows is 107–132% of the error |
| 6 | Equal uncertainty and the repaired estimator were a fair test of complex weighting | **PARTIAL** — a fair test of *these three* weightings at *fixed dispersion* on 5–6 varying models. Not a test of complex weighting in general, and structurally blind to the dominant error channel. |

---

## PART 7 — What was actually falsified

| Item | Classification |
|---|---|
| Recovered-SE weighting formula | **FALSIFIED** |
| Existing probability calibration | **FALSIFIED** |
| Probability sharpness / dispersion | **FALSIFIED** |
| Confidence estimates | **UNSUPPORTED** (never validated against realized accuracy) |
| Current ensemble implementation | **REJECTED FOR CURRENT IMPLEMENTATION ONLY** |
| Complex weighting in general | **UNSUPPORTED** (three weightings, fixed dispersion) |
| Equal weighting | **REJECTED FOR CURRENT IMPLEMENTATION ONLY** |
| Simple baseline (constant-50%) | **UNAFFECTED — best performer tested** |
| Cross-sectional predictive signal in the tested features | **UNDERPOWERED** |
| Predictive signal in any future feature set | **UNRESOLVED** |
| Feasibility of Arm 2 | **RETIRED FOR FEASIBILITY** (structural; max 1 genuine consumer vs 2 required) |
| Overall investment decision-support product | **UNAFFECTED** |

---

## PART 8 — Correct program status

### **STATUS B — Current implementation falsified; the broader predictive question unresolved.**

**Why B and not A** (falsified, permanently retired): falsification requires that the study could have detected the effect had it existed. Part 4 establishes it could not, at any horizon, for any plausible effect size. A null from an instrument with a 0.10 detection floor does not falsify a 0.03 hypothesis.

**Why B and not C** (suspended for substrate): C is true but incomplete. Something *was* falsified — the probability calibration, decisively and permanently. C would let a future reader believe nothing was settled. B records both the genuine falsification and the genuine gap.

**Why B and not D** (continue immediately): Part 10 shows the required sample is ~11× current. Continuing now would repeat the same underpowered exercise.

**Why B and not E:** no more precise status is needed. B is exactly the situation.

The operative *constraint* from C is retained and recorded: the present substrate cannot answer the open question. **That is infeasibility, not falsification, and the record must not conflate them.**

---

## PART 9 — Minimum record corrections

To be enacted as **Amendment A-2026-007**, appended; no prior document silently rewritten.

| # | Current statement | Disposition | Exact replacement |
|---|---|---|---|
| 1 | "Every ensemble variant loses to a coin flip." | **NARROW** | "Every ensemble variant produces worse *probability forecasts* than an uninformed constant. Decomposition attributes 107–132% of the Brier excess to score dispersion; the discrimination term is small and sign-inconsistent. This is a calibration finding and carries no implication about ranking." |
| 2 | "Complex weighting is not scientifically justified." | **WITHDRAW and REPLACE** | "Three weighting schemes — defective recovered-SE, `n_eff`-precision, and equal — were compared at fixed calibration scale on six participating models. None improved Brier. This does not test complex weighting in general, and the fixed scale made the comparison insensitive to the dominant error channel." |
| 3 | "The predictive ensemble research branch is retired." | **NARROW** | "The current predictive ensemble implementation is withdrawn from the product decision path. The broader question of cross-sectional discrimination is unresolved and suspended for infeasibility, not falsified." |
| 4 | "No predictive edge was established." | **NO CHANGE** | Accurate as written. Establishing an edge was never achieved. |
| 5 | "Real predictive signal remains unresolved." | **NO CHANGE — and promote** | Accurate. Must be moved from an annex into the headline determination, with the measured MDE beside it. |
| 6 | "Arm 2 is permanently retired." | **NO CHANGE** | Fully supported; structural and unrescuable by power. |
| 7 | *(new, required)* | **ADD** | "No confidence interval for rank IC exists anywhere in the V6 record. Every null IC result must be read against the measured empirical MDE₈₀ of 0.10 (1w) to 0.40 (1y)." |
| 8 | Red Team: "effectively two models" | **WITHDRAW** | "Six of seven models participated in the tested archived panel, five with within-date cross-sectional SD of 19.5–25.0 score points. The dead- and constant-model finding applies to the restored environment, not to the repair experiment." |

---

## PART 10 — Is a further test justified?

### **Justified in principle; currently INFEASIBLE.**

A qualifying test would target discrimination directly (cross-sectional rank IC, not Brier), on cross-sectionally live models, with a predeclared MDE, without reviving the ensemble. Such a test is well defined and would change the program decision in either direction.

It cannot be run now. Deriving the requirement from the record's own numbers: Arm 1 measured `empirical MDE₈₀ ≈ 1.45 × 2.49 × SE`. To reach MDE₈₀ = 0.03 requires SE ≈ 0.0083 against the current 0.0278 at 1w — a **≈11× increase in effective sample**, from 1,259 cohort cells over 7 symbols to roughly 14,000. The record establishes no such panel exists or is obtainable at zero cost.

### Minimum prerequisite for any future predictive test

> A cohort panel delivering **bootstrap SE ≤ 0.0085** for cross-sectional rank IC at the target horizon (≈11× the current effective sample), composed of models **verified cross-sectionally live by measurement**, with an **MDE ≤ 0.03 predeclared before execution** and rank IC — not Brier — as the primary endpoint.

Until that prerequisite is met, no predictive test should be authorized, because none can distinguish the hypotheses at issue.

---

## PART 11 — Final adjudication

1. **V6 closure scientifically correct as written: PARTIALLY.** Correct on what failed; overreaching on what that failure means.
2. **Brier failure primarily a calibration finding: YES.** Dispersion = 107–132% of the excess at all six horizons.
3. **Discrimination tested with adequate power: NO.** Detection floor 0.10–0.40 against observed |IC| ≤ 0.052; no CI ever computed.
4. **Effective model population materially smaller than seven: YES, but modestly** — six participated, five reliably; one dead. **Not** the two the Red Team claimed.
5. **Complex weighting falsified in general: NOT TESTED.**
6. **Current ensemble implementation rejected: YES.**
7. **Real predictive signal falsified: UNRESOLVED.**
8. **Arm 2 permanently retired: YES.**
9. **Correct status: B — current implementation falsified; broader predictive question unresolved; suspended for infeasibility.**
10. **Documents requiring amendment:** `V6_FINAL_SCIENTIFIC_DETERMINATION.md`, `V6_RECOVERED_SE_REPAIR_DECISION.md`, `V6_ENSEMBLE_RETIREMENT_REGISTER.md`, `V6_TO_PRODUCT_PROGRAM_HANDOFF.md`, `V6_RED_TEAM_REVIEW.md` (item 8) — via **A-2026-007**, appended, nothing rewritten.
11. **Further predictive testing scientifically justified: YES in principle; INFEASIBLE now.**
12. **Minimum prerequisite:** bootstrap SE ≤ 0.0085 for cross-sectional rank IC (≈11× current sample), cross-sectionally live models, MDE ≤ 0.03 predeclared, rank IC as primary endpoint.
13. **Next authorized product activity:** Phase 1 product validation — unaffected by every finding here.
14. **Next authorized scientific activity:** enact Amendment A-2026-007 and close blocker B-07. **No new predictive experiment is authorized.**
