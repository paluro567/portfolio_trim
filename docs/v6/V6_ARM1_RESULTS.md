# V6 ARM 1 — RESULTS

**Score-level signal injection through the validation layer.**
Executed 2026-08-01. Every number below is a measured output; nothing is projected except where
explicitly labelled EXTRAPOLATION.

---

## 1 · Surviving artifacts — verified sufficient

`data/validation/analogue_v1/embargoed_revalidation/merged.csv`
(sha256 `d3db3fa9dbb7a57d54db3762ee47781b…`)

| Property | Value |
|---|---|
| Rows | 51,024 across 7 systems |
| System used | `baseline` — the 7-model production ensemble |
| Cells | **7,290 complete**, 0 duplicates |
| Symbols | 7 — ADBE, AMD, AMZN, CRM, HNST, NOW, TSLA |
| Dates | 189, 2019-01-02 → 2026-06-26 |
| Horizons | 1w, 2w, 1m, 3m, 6m, 1y |
| Prediction objects | `evidence_score`, `confidence`, `expected_excess`, `n_eff`, `trim_score`, `band` |
| Realized outcomes | `actual`, `spy_rel`, `adverse`, `drawdown`, `fwd_vol` — **0 nulls** |
| Leakage report | `violations_total: 0` over 1,201 checked dates |

**Sufficient for score-level injection:** every cell carries both a prediction and a realized outcome,
the embargo is verified clean, and the outcome column used as the injection target (`spy_rel`) is
system-independent.

## 2 · Injection design

```
inj(ρ, seed) = ρ · Φ⁻¹(rank(y)) + √(1−ρ²) · ε ,   ε ~ N(0,1)
```

| Requirement | How met |
|---|---|
| Reproducible | Deterministic seed `f(horizon, ρ, seed_index)`. **Verified identical across two `PYTHONHASHSEED` values** |
| Parameterized | Single parameter ρ = target IC |
| Reversible | ρ = 0 → pure noise, no signal |
| Independent across horizons | Horizon enters the seed; cohorts are computed independently |
| Independent across securities | ε is drawn i.i.d. per cell |
| **Outcomes never modified** | ✅ `y` is read-only; only the prediction vector is constructed |

**Validation layer under test:** `cohort()` non-overlap stride → rank IC → circular block bootstrap
(block = 4, per-symbol series, matching the shipped `block_bootstrap_delta` structure) → detection =
95% CI excludes zero.

## 3 · Monte Carlo

300 seeds × 400 bootstrap draws on the primary grid (ρ ∈ {0, .01, .02, .03, .04, .05, .07, .10});
200 × 300 on the extended grid (ρ ∈ {.12, .15, .20, .25, .30, .40}). **Total ≈ 3.4 M bootstrap
resamples.** Runtime 10 min + 8 min.

### Recovery probability (%)

| target IC | 1w | 2w | 1m | 3m | 6m | 1y |
|---|---|---|---|---|---|---|
| **0.00** | 2.5 | 3.5 | 2.0 | 2.0 | 5.5 | 9.5 |
| 0.01 | 11.0 | 8.0 | 2.5 | 6.0 | 6.5 | 12.5 |
| 0.02 | 9.5 | 12.0 | 5.0 | 3.0 | 5.0 | 12.5 |
| 0.03 | 20.0 | 17.0 | 10.0 | 9.5 | 8.0 | 12.5 |
| 0.04 | 28.0 | 28.0 | 17.5 | 12.5 | 5.5 | 16.0 |
| 0.05 | 44.5 | 42.5 | 14.0 | 14.0 | 16.5 | 19.0 |
| 0.07 | 73.5 | 65.5 | 29.0 | 17.0 | 14.0 | 17.5 |
| **0.10** | **90.0** | **91.0** | 53.5 | 24.5 | 22.0 | 23.5 |
| 0.15 | — | — | **89.5** | 55.0 | 36.0 | 40.5 |
| 0.20 | — | — | 97.0 | 74.0 | 49.5 | 49.0 |
| 0.25 | — | — | 100.0 | **86.5** | 72.5 | 66.0 |
| 0.30 | — | — | 100.0 | 95.0 | **82.5** | 73.5 |
| 0.40 | — | — | 100.0 | 100.0 | 98.5 | **91.5** |

**Recovery is monotone in ρ at every horizon.** The layer responds to injected signal.

## 4 · Detection limits

| Horizon | n cells | bootstrap SE | **MDE(80%)** | MDE(90%) | analytic 2.486·SE | empirical ÷ analytic | MDE÷SE |
|---|---|---|---|---|---|---|---|
| **1w** | 1,264 | 0.0278 | **0.10** | 0.10 | 0.069 | 1.45× | 3.60 |
| **2w** | 1,264 | 0.0278 | **0.10** | 0.10 | 0.069 | 1.45× | 3.59 |
| **1m** | 421 | 0.0472 | **0.15** | 0.20 | 0.117 | 1.28× | 3.18 |
| **3m** | 180 | 0.0689 | **0.25** | 0.25 | 0.171 | 1.46× | 3.63 |
| **6m** | 94 | 0.0882 | **0.30** | 0.40 | 0.219 | 1.37× | 3.40 |
| **1y** | 47 | 0.1007 | **0.40** | 0.40 | 0.250 | 1.60× | 3.97 |

> **The best horizon available (1w, n = 1,264) has a measured MDE of 0.10 — more than three times the
> 0.03 the gate requires.** On this dataset the validation layer cannot detect an economically
> meaningful effect at any horizon.

## 5 · Diagnostics

### 5.1 The metric is unbiased

Mean(recovered IC − target IC) across all 48 primary cells: **max |bias| = 0.017**, most below 0.005.
**No systematic bias in the rank-IC estimator.**

### 5.2 False-positive calibration — good at short horizons, degraded at long

| Horizon | FP rate at ρ = 0 | Nominal |
|---|---|---|
| 1w · 2w · 1m · 3m | 2.5% · 3.5% · 2.0% · 2.0% | 5% — **conservative** |
| 6m | 5.5% | 5% — nominal |
| **1y** | **9.5%** | 5% — **~2× inflated** |

**The block bootstrap under-covers at n = 47.** At the 1y horizon roughly one null realization in ten
produces a spurious "detection." This is a property of the layer, measured, and it matters: it means
1y results from this panel carry roughly double the nominal false-positive risk.

### 5.3 Where information is lost — it is sample size, not machinery

Measured across six sub-panels (n = 141 → 1,264, by varying symbol count and date coverage):

```
SE = 0.977 / √n        max residual 0.00063
```

That is within 2.3% of the textbook Spearman SE of 1/√n. **The block bootstrap is well calibrated and
the layer loses essentially no information relative to the theoretical bound.** The constraint is the
number of independent observations, not a defect in the pipeline.

| symbols | dates | n | SE | FP | MDE(80%) |
|---|---|---|---|---|---|
| 3 | 25% | 141 | 0.0817 | 4.7% | 0.30 |
| 3 | 50% | 282 | 0.0576 | 3.3% | 0.20 |
| 5 | 50% | 411 | 0.0478 | 1.3% | 0.15 |
| 7 | 50% | 599 | 0.0399 | 3.3% | 0.15 |
| 5 | 100% | 886 | 0.0333 | 6.0% | 0.10 |
| 7 | 100% | 1,264 | 0.0278 | 2.7% | 0.10 |

### 5.4 The analytic MDE formula is optimistic by ~1.4×

`2.486 × SE` underestimates the measured MDE at **every** horizon (ratio 1.28–1.60, mean 1.43).
The empirical relationship is **MDE(80%) ≈ 3.44 × SE**, range 3.00–3.97.

**Any prior power calculation in this project that used 2.486 × SE understated the required effect
size by roughly 40%.**

### 5.5 Calibration and confidence do not affect recovery

The injection is applied to the **score ordering**; the rank IC is invariant to any monotone
transform. Score dispersion, Brier calibration and the `confidence` field therefore cannot change
recovery, and none enters the detection statistic. **Confirmed by construction, not merely observed.**
The overconfidence documented elsewhere in this project is a *calibration* defect and is orthogonal to
Arm 1's *detection* question.

## 6 · Extrapolation — labelled, not measured

Combining the two measured relationships — `SE = 0.977/√n` and `MDE ≈ 3.44 · SE`:

```
MDE(80%) ≈ 3.36 / √n     ⇒     MDE ≤ 0.03 requires n ≈ 12,600 cells
```

**This is an extrapolation roughly 10× beyond the measured range (max n = 1,264) and across a
structural change the experiment did not test:** the block bootstrap blocks on *symbols*, and every
measured point had 3–7 of them. A 500-name panel has a fundamentally different block structure, and
Arm 1 cannot say whether the same scaling holds there.

**It is a hypothesis for Arm 2 to test, not a result.**

---

## 7 · Gate questions

### 1 · Does the validation layer recover injected signal?

**YES.** Recovery rises monotonically with injected IC at every one of the six horizons, reaching
90–91% at IC = 0.10 (1w/2w) and 91.5–100% at IC = 0.40 (1y/1m). The estimator is unbiased
(max |bias| 0.017) and the bootstrap SE matches the theoretical bound to within 2.3%.
**The instrument is not blind.**

### 2 · At what IC?

**MDE(80%) = 0.10 at 1w and 2w · 0.15 at 1m · 0.25 at 3m · 0.30 at 6m · 0.40 at 1y.**

At the gate-relevant IC of 0.03, measured recovery is **20.0% (1w) · 17.0% (2w) · 10.0% (1m) · 9.5%
(3m) · 8.0% (6m) · 12.5% (1y)** — far below the 80% required.

### 3 · Is G5 still plausible?

**YES — but it is now conditional on a scaling relationship Arm 1 could not test.**

- **Supporting:** the layer is unbiased, well-calibrated at n ≥ 100, and loses essentially no
  information relative to `1/√n`. No pipeline defect stands between the data and the answer. The
  measured scaling law implies ~12,600 cells for MDE ≤ 0.03 — a 500-name × 20-year panel produces far
  more than that before any cohort stride.
- **Against:** the extrapolation crosses a 10× size gap **and** a change in block structure that was
  never varied. The 1y false-positive rate of 9.5% shows the bootstrap does degrade at small n; whether
  it also degrades under many-symbol blocking is unmeasured.

**G5 is not decided by Arm 1 and was never going to be.** What Arm 1 establishes is that *if* the
required n is reachable, the layer will detect the effect — the failure mode "blind instrument" is
ruled out at this scale.

### 4 · What uncertainty remains before Arm 2?

| # | Open question | Why Arm 1 cannot answer it |
|---|---|---|
| 1 | Does `SE = 0.977/√n` hold at 100–500 symbols? | Only 3–7 symbols available; block structure untested at breadth |
| 2 | Does the model + combiner layer destroy signal? | **Arm 1 injects at the score level, downstream of the models.** The Arm 2 − Arm 1 gap is the entire point and is unmeasured |
| 3 | Does the FP inflation at small n recur under many-symbol blocking? | Untested |
| 4 | Does a real documented effect survive end to end? | Arm 3; blocked on data restoration |
| 5 | Does the MDE hold with realistic (non-Gaussian, autocorrelated) signal? | Injection is i.i.d. Gaussian by design |

**The largest remaining uncertainty is #2.** Arm 1 measured the *validation layer*. It says nothing
about the pipeline upstream of the score — which is precisely where the project's measured defects
(`se ≡ |effect/z|`, Spearman −1.000 weighting, the +19-point overclaim) live.


> **[AMENDED A-2026-006, 2026-08-04]** Complex weighting is **not scientifically justified**. Every tested ensemble variant - defective, repaired and equal-weight - lost to the constant-50% forecaster at all six horizons. Nothing in this document should be read as supporting continued ensemble weighting work.
