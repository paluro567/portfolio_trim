# V6 — External Peer Review Panel Report

**Reviewing for:** a quantitative finance journal · **Date:** 2026-08-04
**Panel involvement in the work:** none.

**Recommendation: REJECT as submitted. Invited to resubmit as a methodology paper after major revision.**
Two of the three headline experiments cannot be re-executed, every confidence interval in the paper is computed by resampling **seven** securities, and the universe is the authors' own holdings.

---

## PART 1 — Scientific validity of each major conclusion

| # | Conclusion | Classification | Reason |
|---|---|---|---|
| C1 | The recovered-SE rule `se=|effect/z|` inverts weighting (`spearman(|effect|,w) = −0.7228`) | **FULLY SUPPORTED** | Algebraic identity confirmed on 36,926 records. Independent of sample size. |
| C2 | Syntactic dependency counting misidentifies feature consumers — 5 of 6 counted consumers were byte-identical under ρ=0.30 injection | **FULLY SUPPORTED** | Direct causal perturbation; a code-level result, immune to the sampling defects below. **The paper's best contribution.** |
| C3 | Arm 2 is structurally infeasible (max 1 genuine live consumer vs 2 required) | **FULLY SUPPORTED** | Perturbation at ±8σ over 150 cells; mechanism explained by disjoint dependency structure. |
| C4 | The ensemble's probability forecasts are worse than an uninformed constant | **PARTIALLY SUPPORTED** | The point estimates are large and consistent, but every CI derives from a 7-cluster bootstrap (Part 2). Direction is credible; stated significance is not. |
| C5 | The Brier excess is dispersion, not absent discrimination (107–132%) | **FULLY SUPPORTED** | Exact algebraic decomposition; no inference required. |
| C6 | The validation layer is unbiased and efficient (Arm 1) | **PARTIALLY SUPPORTED** | The bias result is solid. "Efficient" rests on a bootstrap whose own measured false-positive rate ranges 0.020–0.095 against a nominal 0.05. |
| C7 | The combiner does not destroy signal (Arm 1.5) | **UNSUPPORTED — vacuous** | LOSS = IC(consensus) − IC(combined) with neither arm carrying measurable IC. The experiment has no power to detect loss because there is no signal to lose. |
| C8 | Complex weighting is not scientifically justified | **OVERSTATED** | Three schemes, at frozen calibration scale, on one panel. |
| C9 | Real predictive signal is unresolved | **FULLY SUPPORTED** | Correctly stated; must be the headline, not an annex. |
| C10 | Repairing the defect did not improve discrimination | **UNSUPPORTED** | No interval was ever computed for rank IC. A point-estimate comparison is not a result. |

---

## PART 2 — Statistical validity

### 2.1 Sample size — **DISQUALIFYING for every cross-sectional claim**
The archived panel contains **seven securities**: ADBE, AMD, AMZN, CRM, HNST, NOW, TSLA (2019-01-02 → 2026-06-26). Six are large-cap US technology/growth names; one is a small-cap. A rank correlation computed across seven names on a given date is not a cross-sectional information coefficient in any sense a finance journal recognises. The 1y horizon has **45 cells across 7 names** — roughly 6 observations per security.

### 2.2 Statistical power — **fatal to the null results**
Arm 1's measured empirical MDE₈₀ is 0.10 (1w) to 0.40 (1y). Observed |IC| ≤ 0.052. The study could not detect an IC of 0.03 or 0.05 at **any** horizon. Every null IC result in the paper is uninformative, and the paper does not say so.

### 2.3 Bootstrap methodology — **DISQUALIFYING**
All intervals — Arm 1, Arm 1.5, the recovered-SE repair — use a circular block bootstrap over **per-symbol series**, i.e. resampling from **seven exchangeable clusters**. Cluster/block bootstrap inference is unreliable below roughly 20–30 groups; at 7 the resampling distribution is dominated by which of seven securities is drawn.

The authors' own data confirm the miscalibration. Arm 1 measured false-positive rates against a nominal 0.05:

| H | n | FP rate |
|---|---|---|
| 1w | 1264 | 0.025 |
| 2w | 1264 | 0.035 |
| 1m | 421 | 0.020 |
| 3m | 180 | 0.020 |
| 6m | 94 | 0.055 |
| 1y | 47 | **0.095** |

Anti-conservative by ~1.9× at 1y, conservative by 2.5× at 1m. The procedure is miscalibrated in **both directions** depending on horizon. The paper reports these numbers as evidence the bootstrap works. They are evidence it does not.

### 2.4 Multiple comparisons — **inadequately handled**
Six horizons × several metrics × four arms. The repair experiment's program rule (≥3 horizons) is sensible, but the headline "significant at 5 of 6 horizons" carries no multiplicity adjustment, and the six horizons are computed on the same seven securities over overlapping calendar spans — they are strongly dependent tests presented as corroborating.

### 2.5 Benchmark choice — **weakest available benchmark selected**
The constant-50% forecaster is not the strongest trivial benchmark. The realised base rate falls from 0.492 (1w) to **0.356 (1y)**, so a constant `p = ȳ` achieves Brier 0.2291 at 1y versus 0.2500 for p = 0.5:

| H | ȳ | Brier @ p=0.5 | Brier @ p=ȳ |
|---|---|---|---|
| 1w | 0.492 | 0.2500 | 0.2499 |
| 6m | 0.391 | 0.2500 | 0.2382 |
| 1y | 0.356 | 0.2500 | **0.2291** |

p = ȳ is in-sample and therefore not a legitimate PIT competitor — but the paper must say so and report it, rather than silently benchmarking against the weakest constant.

### 2.6 Estimator assumptions
Arm 1's injection is `ρ·Φ⁻¹(rank(y)) + √(1−ρ²)·ε` — Gaussian, homoscedastic, serially independent given the block structure. Real scores are `100·Φ(z)` with `|z| ≤ 4`, discrete-ish, autocorrelated, and clipped at [0.01, 0.99]. The MDE derived under the synthetic structure is assumed to transfer to the real one. This is never tested and is a material assumption.

### 2.7 Bias
Base rate 0.356 at 1y means SPY outperformed most holdings over most long windows in this sample. Any directional system is competing against a strong drift the sample does not represent generally.

**Verdict: 2.1, 2.3 and 2.2 individually invalidate every inferential conclusion in the paper. The algebraic and code-level results (C1, C2, C3, C5) survive intact, because none of them requires sampling inference.**

---

## PART 3 — Methodological validity

| Issue | Finding |
|---|---|
| **Survivorship / selection** | **SEVERE.** The universe is the authors' current portfolio holdings. Securities were selected by virtue of being held *today*, over a window beginning 2019. This is textbook selection-on-the-outcome. The programme elsewhere identifies "PIT survivorship-clean universe" as an unmet goal, then reports cross-sectional statistics on a hand-selected survivor set. |
| **Hidden assumption** | The pooled symbol-date rank correlation is treated throughout as a "cross-sectional IC." With 7 names it is overwhelmingly a **time-series** statistic. Terminology must change. |
| **Leakage** | **None found in the injection design.** Outcomes are never modified; embargo `pos(t)+H ≤ pos(T)` is enforced; the price-poisoning test is a genuine PIT control. This is the methodologically strongest part of the work. |
| **Circularity** | **Moderate, in Arm 1.** The validation layer is validated by injecting a signal constructed from the outcomes and confirming the layer detects it. Valid as a power study; it cannot establish that the layer measures *real* score-outcome structure correctly. |
| **Confirmation bias** | **Low, and to the authors' credit.** The programme repeatedly published results against its own interest and convened adversarial reviews. |
| **Researcher degrees of freedom** | **HIGH but largely mitigated.** Many architecture iterations and committees precede the experiments; most preregistrations were written after seeing earlier results. Mitigating: nearly every reported outcome is negative, the direction that p-hacking does not produce. The recovered-SE repair spec was demonstrably frozen before results. |

---

## PART 4 — Reproducibility

| Artifact | Status |
|---|---|
| Arm 1 harness (`v6_arm1.py`, `v6_arm1b.py`) | **DESTROYED** — not in any durable location |
| Arm 1.5 harness (`a15_run.py`) | **DESTROYED** — temp directory wiped |
| Recovered-SE harness (`tools/v6/recovered_se_repair.py`) | Present |
| Archived panel (`merged.csv`, md5 `aa1c82bd…`) | Present, hashed |
| `uv.lock`, Python 3.13.14 | Present |
| `MANIFEST.sha256` | Present |
| Database snapshot at experiment time | **Absent** — the DB was destroyed and rebuilt; no snapshot identifier |
| Arm 1 extended-grid values | **NOT REPRODUCIBLE — blocker B-07.** The authors' own audit re-run produced 0.340 and 0.900 where the published file holds 0.405 and 0.915. Unresolved. |

**Two of the three published experiments cannot be re-executed by anyone, including the authors.** Arm 1's published numbers are not reproducible even internally, a failure the authors discovered and correctly documented but could not resolve. This alone bars publication.

---

## PART 5 — Publication decision

### **REJECT as submitted.** Resubmission invited as a *methodology* paper after major revision.

**As an empirical finance paper: reject, without a path to acceptance on this data.** No revision rescues N=7 self-selected securities. The central empirical claims are not merely underpowered — they are computed on a universe that cannot support them.

**As a methodology paper: major revision, with genuine promise.** Stripped of its empirical claims, the work contains three contributions a journal would want:
1. A two-stage (static + causal-perturbation) operational definition of software dependency, with a striking demonstration that syntactic counting is wrong — 5 of 6 identified "consumers" were inert.
2. A worked case of silent estimator corruption: `se = |effect/z|` inverting precision weights, with the inversion measured rather than argued.
3. The discipline of decomposing Brier into bias/dispersion/discrimination before drawing conclusions about signal — and a live example of a research programme nearly reaching the wrong conclusion for want of it.

None of these depends on the sample.

---

## PART 6 — Final review

**1. Strongest scientific result**
The causal-perturbation refutation of syntactic dependency counting: **5 of 6 nominal consumers of `ret_21d` were byte-identical under a ρ=0.30 injection**, and the maximum genuine consumer count across 23 candidate features at ±8σ over 150 cells is **1**. Deterministic, mechanistic, sample-independent, and generalizable to any research pipeline. The recovered-SE inversion (−0.7228) is a close second.

**2. Weakest scientific result**
**Arm 1.5.** "The combiner does not destroy signal" is vacuous when no arm carries measurable signal — the experiment cannot detect a loss of something absent. Its harness has also been destroyed. It is nonetheless load-bearing in the programme's progression logic.

**3. What prevents publication**
Four independent bars, any one sufficient: (i) N=7 securities selected as current holdings; (ii) every confidence interval bootstrapped over 7 clusters, with the authors' own FP rates of 0.020–0.095 against nominal 0.05 proving miscalibration; (iii) Arm 1 and Arm 1.5 harnesses destroyed; (iv) unresolved blocker B-07 — the published Arm 1 values are not reproducible even by the authors.

**4. Mandatory revisions**
- **M1.** Remove every cross-sectional empirical claim, or re-run on a survivorship-controlled universe of ≥100 securities.
- **M2.** Replace or abandon the 7-cluster bootstrap. Report the measured FP rates (0.020–0.095) as a limitation, not as validation. Any interval that survives must state its cluster count.
- **M3.** Retitle "cross-sectional IC" as **pooled symbol-date rank correlation** throughout.
- **M4.** Print the measured MDE beside **every** null result. State plainly that IC = 0.03–0.05 was undetectable at all six horizons.
- **M5.** Restore and publish the Arm 1 and Arm 1.5 harnesses, or withdraw both experiments.
- **M6.** Resolve B-07 or formally withdraw the Arm 1 extended grid.
- **M7.** Reframe the Brier result as calibration; report the bias/dispersion/discrimination decomposition in the main text.
- **M8.** Withdraw "complex weighting is not scientifically justified."
- **M9.** Disclose the universe-selection mechanism (current holdings) in the data section, prominently.
- **M10.** Report the `p = ȳ` benchmark alongside `p = 0.5`, noting the former is in-sample.

**5. Would you accept this work for publication?**
**No.** Not as submitted, and not as an empirical result on this data at any level of revision.

We would review a resubmitted **methodology** paper with interest, and we note something the authors deserve credit for: the programme repeatedly discovered and published findings against its own interest, and its own internal audit caught the reproducibility failure we would otherwise have raised as our lead objection. The scientific conduct here is markedly better than the scientific evidence. Our objection is to the sample and the inference drawn from it, not to the integrity of the work.
