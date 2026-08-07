# V6 Closure — Independent Scientific Red Team Review

**Date:** 2026-08-04 · No prior involvement. No ownership of any prior conclusion. No experiments executed; all figures are arithmetic on completed evidence.

---

## Headline

**The closure reached a defensible action for substantially the wrong reason.** Its central evidentiary claim — *every ensemble variant loses to a constant-50% forecaster* — is a **calibration** finding that has been recorded and reasoned about as a **signal** finding. The question the closure retires the program over was never measured with adequate resolution, and the record's own Arm 1 numbers prove it could not have been.

---

## PART 1 — Assumptions required for the closure, and their status

| # | Assumption | Status |
|---|---|---|
| A1 | The recovered-SE defect is real and inverts weighting | **Experimentally demonstrated** — `spearman(|effect|, w) = −0.7228` |
| A2 | The defect is mechanically removable | **Experimentally demonstrated** |
| A3 | Repairing it does not improve Brier | **Experimentally demonstrated** (0 PASS / 1 FAIL / 5 INCONCLUSIVE) |
| A4 | The ensemble's *probability outputs* are worse than uninformed | **Experimentally demonstrated** — significant at 5/6 horizons |
| A5 | Brier is an adequate proxy for "does this system contain usable signal" | **FALSE.** Brier is jointly sensitive to calibration and discrimination. A forecaster with real ranking skill and gross overconfidence loses on Brier. |
| A6 | The ensemble has no exploitable predictive signal | **Untested.** See Part 2 G1. |
| A7 | The evaluation panel could have detected such signal if present | **FALSE.** Arm 1's own analytic MDE₈₀ is **0.069 rank IC** at the best horizon, rising to 0.250 at 1y. |
| A8 | The tested configuration is representative of the designed ensemble | **FALSE.** 3 of 7 models emit constant output; of the 4 live, `macro_regime` and `interest_rate_sensitivity` read only **market-scope** features and are therefore **identical across symbols on any date** — they contribute exactly zero cross-sectional discrimination. The cross-sectional ensemble was effectively **two models**. |
| A9 | "Complex weighting is not scientifically justified" generalizes | **Inferred, and unsupported.** Demonstrated only on a substrate with ~2 effective cross-sectional contributors. |
| A10 | Arm 1.5 established the combiner preserves signal | **Indirectly supported at best, arguably vacuous.** LOSS = IC(consensus) − IC(combined) ≈ 0 when *neither* has measurable IC. "Nothing was destroyed" is uninformative when there is nothing to destroy. |
| A11 | Arm 2's retirement is structural | **Experimentally demonstrated** — max 1 genuine live consumer at ±8σ over 150 cells |
| A12 | The repair experiment could have detected an improvement from reduced overconfidence | **FALSE by construction.** See Part 2 G2. |

---

## PART 2 — Logical gaps

### G1 — The null was never tested at adequate power · **MAJOR UNSUPPORTED INFERENCE**

The repair experiment reported rank IC as a "scale-free cross-check" with **no confidence intervals and no decision rule**. Verified: `V6_RECOVERED_SE_REPAIR_PAIRED_RESULTS.csv` contains `ic_A, ic_B, ic_C` and **no CI columns for any of them**.

Against Arm 1's own bootstrap SEs:

| H | n | IC_A | boot SE | t | analytic MDE₈₀ | significant? |
|---|---|---|---|---|---|---|
| 1w | 1259 | +0.0316 | 0.0278 | 1.14 | 0.0690 | no |
| 2w | 1259 | +0.0115 | 0.0278 | 0.42 | 0.0692 | no |
| 1m | 419 | −0.0305 | 0.0472 | −0.65 | 0.1173 | no |
| 3m | 178 | −0.0167 | 0.0689 | −0.24 | 0.1713 | no |
| 6m | 92 | −0.0552 | 0.0882 | −0.63 | 0.2192 | no |
| 1y | 45 | +0.0233 | 0.1007 | 0.23 | 0.2504 | no |

Every IC is inside the noise band. **Critically, the data are equally consistent with IC = 0 and with IC = +0.05 at every horizon.** The panel's floor of detection is 0.069 at its most powerful horizon. A commonly cited range for exploitable cross-sectional equity IC is 0.02–0.05 *(this benchmark is external to the record and is flagged as such)*; that entire range sits **below** the panel's detection floor.

The program built a measuring instrument, correctly established that its resolution is ~0.07, then used a null result from that instrument to retire the search for effects around 0.03.

### G2 — The repair experiment froze the dominant error term · **MAJOR UNSUPPORTED INFERENCE**

The repair spec fixed `k_h` per horizon so that `median|z_repaired| = median|z_original|`. That is a defensible way to isolate *relative weighting* — but it means **score dispersion, which is the entire measured Brier gap, was held constant by design.**

Decomposing: with zero discrimination, Brier excess over 0.25 equals Var(p).

| H | Brier_A | excess over 0.25 | implied SD(p) |
|---|---|---|---|
| 1w | 0.3097 | +0.0597 | 0.244 (**24.4 score points**) |
| 2w | 0.3059 | +0.0559 | 0.236 |
| 1m | 0.2991 | +0.0491 | 0.222 |
| 3m | 0.3089 | +0.0589 | 0.243 |
| 6m | 0.3095 | +0.0595 | 0.244 |
| 1y | 0.2966 | +0.0466 | 0.216 |

The Brier gap is **quantitatively accounted for, at every horizon, by dispersion alone** — a forecaster emitting ±22–24 score points of confidence with no discrimination. This is a textbook overconfidence signature.

The experiment therefore could not have detected the single largest available improvement (shrinking dispersion), because it pinned dispersion by construction, and then the closure read the resulting Brier gap as evidence about signal.

### G3 — "Complex weighting is not scientifically justified" · **MODERATE OVERREACH**
Demonstrated on a substrate where 3 of 7 models are dead and 2 of the 4 survivors are cross-sectionally constant. There were approximately two things to weight. The finding is real for *this* configuration and does not support the general claim as written.

### G4 — Arm 1.5's contribution · **MODERATE OVERREACH**
"The combiner does not destroy signal" is asserted as a load-bearing established finding. On a panel where no arm has measurable IC, the statement carries almost no information, yet the oversight determination used it as one of two pillars justifying progression.

### G5 — "loses to a coin flip" framing · **MODERATE OVERREACH (wording)**
Accurate as stated about Brier; systematically misleading in context, because every downstream reader will take it as "has no signal." It appears in commit messages, the final determination, and the handoff.

### G6 — Pooled IC vs cross-sectional IC · **MODERATE OVERREACH**
The reported IC is Spearman over pooled symbol-date cells across **10 symbols**. That statistic blends time-series and cross-sectional association and is not the cross-sectional IC that the injection experiments (Arm 1) were designed around. With 10 names, a per-date cross-sectional IC is barely estimable at all. The record does not flag this.

### G7 — Scope discipline · **HARMLESS / to the closure's credit**
`V6_FINAL_SCIENTIFIC_DETERMINATION.md` D1 explicitly records "Does real predictive signal exist? **UNRESOLVED**," and carries an explicit paragraph forbidding the "markets are unpredictable" reading. The detail-level documents are more honest than the decision they support. **This is the closure's central internal contradiction: it retires a program over a question it marks unresolved.**

---

## PART 3 — Alternative explanations consistent with the same evidence

| Alternative | Evidence for it | Weight |
|---|---|---|
| **Insufficient statistical power** | Arm 1's analytic MDE₈₀ = 0.069–0.250; all observed \|t\| ≤ 1.14; n = 45 at 1y | **Strong — arguably the leading explanation** |
| **Incorrect objective function** | Brier gap fully explained by dispersion; discrimination metric never tested inferentially | **Strong** |
| **Poor calibration masking useful ranking** | Implied SD(p) ≈ 0.22–0.24 with ~zero Cov(p,y); this is exactly the signature | **Strong** |
| **Implementation limitations** | 3/7 models dead; 2/4 live models cross-sectionally constant; class-B restored panel | **Strong** |
| **Sparse sample effects** | 10 symbols; 3,252 cohort cells across 6 horizons; 1y n = 45 | **Moderate–strong** |
| **Model correlation** | Declared conservative correlation prior inflates combined SE; effective models ~3.9–4.8 | **Weak–moderate; not isolated by any experiment** |
| **Horizon mismatch** | ICs change sign across horizons with no coherent term structure | **Weak — could equally be noise** |
| **Not previously considered: cross-sectional dilution by market-scope models** | `macro_regime` + `interest_rate_sensitivity` emit identical evidence for every symbol on a date, so they add variance to a cross-sectional score without adding cross-sectional information — mechanically depressing IC and inflating dispersion | **Moderate; directly implied by the consumer-map evidence and never examined** |
| **Genuinely no signal** | All point ICs near zero | **Weak — indistinguishable from the above at this resolution** |

---

## PART 4 — What was actually falsified

| Claim | Verdict |
|---|---|
| **Predictive ensemble implementation** (this code, this config, this panel) | **FALSIFIED as a probability emitter.** Solid. |
| **Uncertainty estimation** | **FALSIFIED.** `se = |effect/z|` inverted weighting and was unbounded. Demonstrated and repaired. |
| **Weighting methodology** | **NOT falsified.** Only three weightings were compared, all at frozen dispersion, on a ~2-effective-model substrate. |
| **Evidence aggregation** | **NOT falsified.** Arm 1.5's null is uninformative absent measurable signal. |
| **Predictive signal** | **NOT falsified. NOT TESTED at adequate power.** The panel cannot resolve the effect sizes at issue. |
| **Investment edge** | **NOT falsified.** Never measured — no returns, costs, turnover, or capacity analysis exists anywhere in the record. |
| **Overall product vision** | **NOT falsified, and largely untouched.** Phase 1 validation and V5 descriptive reliability were never tested by V6. |

The closure's own retirement register conflates the first two with the middle four in its framing, even while the determination document separates them correctly.

---

## PART 5 — The strongest case for continuing, from completed evidence only

1. **The program measured its own instrument's resolution and then ignored it.** Arm 1 is the most rigorous artifact produced: it established analytic MDE₈₀ of 0.069 (1w) to 0.250 (1y). Every subsequent null was reported against that instrument **without once stating that the null band swallows the entire range of effect sizes worth having.**

2. **The decisive metric answers a different question than the one asked.** The Brier excess is arithmetically equal to score dispersion at all six horizons. What was demonstrated is that the platform is *grossly overconfident*. Whether it *ranks* is a separate question that a calibration metric cannot answer, and the discrimination metric was reported without a single confidence interval.

3. **The verdict was rendered on a crippled configuration.** 3 of 7 models emit constant output. 2 of the 4 survivors are cross-sectionally constant by construction. The "7-model ensemble" was, for cross-sectional purposes, a 2-model ensemble diluted by two constant terms. No result from that configuration licenses a conclusion about the ensemble that was designed.

4. **The repair experiment was structurally incapable of producing the outcome that would have changed the decision.** Fixing `k_h` to the defective system's median |z| froze dispersion — the entire measured error. A result obtained under a constraint that forecloses the main improvement channel cannot be used to close the question that channel bears on.

5. **The closure contradicts itself.** It marks "does real predictive signal exist?" **UNRESOLVED**, then retires the research that would resolve it, citing evidence that does not address it.

**This argument does not claim the ensemble works.** It claims the record does not establish that it does not, and that the closure's stated grounds are the wrong grounds.

---

## PART 6 — Final verdict

**1. Is retiring the predictive research scientifically justified?**
**No — not on the grounds given.** Retiring the *product claim of calibrated directional probabilities* is fully justified and should be permanent. Retiring *predictive research* is not supported: the decisive question is marked unresolved in the closure's own determination, and the panel's demonstrated resolution (MDE₈₀ ≥ 0.069) cannot reach the effect sizes at issue.

A defensible **resource** argument for stopping does exist — a 10-symbol class-B panel with 3 dead models cannot answer the question, and the record shows the required substrate is unavailable. **But that is a feasibility decision, not a falsification, and the record presents it as the latter.**

**2. Is it merely the current implementation that failed?**
**Yes — plus the evaluation apparatus.** What failed: the uncertainty estimator (real, repaired), the calibration of emitted probabilities (real, decisive), and the ability of the panel to test the hypothesis at all (real, and never acknowledged as a limitation).

**3. Least supported conclusion**
**"Complex weighting is not scientifically justified"** (B6), closely followed by **"every tested ensemble variant lost to the constant-50% forecaster"** *presented as a signal finding*. B6 rests on three weightings, at frozen dispersion, on a substrate with ~2 effective cross-sectional contributors.

**4. Strongest conclusion**
**Arm 2's structural retirement.** Maximum 1 genuine live consumer against a requirement of 2, established by direct causal perturbation at up to ±8σ across 150 cells, with the mechanism fully explained by the models' disjoint dependency structure. It is measured, mechanistic, and cannot be rescued by more power. The **defect inventory** (`spearman(|effect|, w) = −0.7228`) is a close second.

**5. Required revision before I would accept this for publication**

- **R1.** Restate the headline as a **calibration** result. Report the decomposition showing Brier excess ≈ Var(p) at all six horizons. Remove "loses to a coin flip" wherever it implies absence of signal.
- **R2.** Report **confidence intervals for rank IC** in the repair experiment, and print the panel's MDE alongside **every** null claim in the record. No null may be stated without its detection floor.
- **R3.** Disclose prominently — in the determination, not only in the readiness annexes — that **3 of 7 models were dead and 2 of the 4 survivors are cross-sectionally constant**, and restrict every ensemble-level conclusion to that configuration.
- **R4.** Withdraw or heavily qualify B6 ("complex weighting is not scientifically justified").
- **R5.** State explicitly that the `k_h` normalization froze score dispersion, and that the experiment was therefore insensitive to the largest available improvement.
- **R6.** Reclassify the decision as **"suspended for infeasibility on the available substrate"** rather than **"retired on evidence."** The action can stand; the justification cannot.

Absent R1–R3 and R6, the closure would mislead any future reader into believing a question was answered that the closure itself records as open.
