# Weighting Analysis — Part 4

Why did equal weighting outperform production weighting? Each hypothesis tested independently.
**No redesign proposed.**

---

## 0. The headline answer, established first

> ## Equal-weight did not win on information. It won **entirely** on shrinkage.

Production's scores are ~2.5x more dispersed than equal-weight's. Rescaling production's dispersion to
match equal-weight's — a single scalar, no reweighting, no new information — **closes the entire Brier
gap at every horizon.**

| Horizon | n | disp. production | disp. equal-wt | implied λ | Brier prod | Brier EW | **Brier prod SHRUNK to EW dispersion** | **% of gap explained by shrinkage** |
|---|---|---|---|---|---|---|---|---|
| 1w | 1259 | 22.21 | 8.33 | 0.375 | 0.3144 | 0.2600 | **0.2583** | **103.2%** |
| 2w | 1259 | 20.70 | 8.35 | 0.404 | 0.3068 | 0.2582 | **0.2584** | **99.6%** |
| **1m** | 420 | 19.41 | 8.04 | 0.414 | 0.2985 | 0.2574 | **0.2570** | **101.0%** |
| 3m | 179 | 20.97 | 8.62 | 0.411 | 0.3241 | 0.2629 | **0.2651** | **96.3%** |
| 6m | 92 | 21.51 | 8.52 | 0.396 | 0.3473 | 0.2749 | **0.2723** | **103.6%** |
| 1y | 45 | 21.07 | 7.54 | 0.358 | 0.4046 | 0.2878 | **0.2895** | **98.6%** |

**96.3%–103.6% of the gap is scale.** Values above 100% mean that once dispersion is matched,
production is *marginally better* than equal-weight.

### The two systems contain the same information

| Horizon | rank IC production | rank IC equal-wt | Δ (EW − prod) | **ordering agreement (Spearman)** | **directional sign agreement** |
|---|---|---|---|---|---|
| 1w | +0.0143 | −0.0034 | −0.0177 | **0.9305** | **0.9206** |
| 2w | +0.0114 | +0.0150 | +0.0036 | **0.9630** | 0.9245 |
| 1m | −0.0085 | +0.0076 | +0.0160 | **0.9701** | 0.9310 |
| 3m | −0.0145 | +0.0021 | +0.0166 | **0.9808** | 0.9497 |
| 6m | −0.0751 | −0.1066 | −0.0315 | 0.9356 | 0.9565 |
| 1y | −0.3052 | −0.2481 | +0.0571 | 0.8899 | 0.9111 |

The systems rank cells **0.89–0.98** identically and agree on direction **91–96%** of the time. The rank
IC delta has **no consistent sign** (−0.018, +0.004, +0.016, +0.017, −0.032, +0.057).

On the 6.9–7.9% of cells where they disagree, production wins at 1w/2w (0.580, 0.558) and loses at 1m
(0.414, n=29) — noise.

### Why equal-weight shrinks by accident

Production averages **evidence** in `z` space, then maps once through Φ. Equal-weight averages the
**already-mapped scores**, i.e. `mean(Φ(z_i))` instead of `Φ(f(z_i))`. Because Φ is S-shaped, averaging
in probability space with mixed-sign inputs pulls toward 0.5 (Jensen). With ~5 active models of mixed
sign, that is a λ ≈ 0.4 shrinkage — **an accidental property of the aggregation space, not a better
model of the evidence.**

---

## 1. Hypothesis tests

### H1 — Excessive confidence / miscalibration: **SUPPORTED (primary)**

| Horizon | mean \|score − 50\| | **implied accuracy** | **realized dir acc** | overclaim |
|---|---|---|---|---|
| 1w | 22.21 | **0.7221** | 0.5083 | **+21.4 pp** |
| 2w | 20.70 | 0.7070 | 0.5123 | +19.5 pp |
| 1m | 19.39 | 0.6939 | 0.5136 | +18.0 pp |
| 3m | 21.01 | 0.7100 | 0.4622 | **+24.8 pp** |
| 6m | 21.67 | 0.7162 | 0.4549 | +26.1 pp |
| 1y | 21.17 | 0.7103 | 0.4592 | +25.1 pp |

**The ensemble claims ~70% accuracy and delivers ~51%** — a stable ~18–26 pp overclaim at every
horizon. This is the direct cause of the Brier deficit.

**Shrinkage sweep — the decisive test.** Brier as scores are pulled toward 50 (`λ = 1` is production,
`λ = 0` is always-neutral):

| Horizon | λ=0 | λ=0.25 | λ=0.5 | λ=0.75 | λ=1.0 |
|---|---|---|---|---|---|
| 1w | **0.2500** | 0.2534 | 0.2652 | 0.2856 | 0.3144 |
| 2w | **0.2500** | 0.2529 | 0.2633 | 0.2812 | 0.3068 |
| 1m | **0.2500** | 0.2523 | 0.2612 | 0.2767 | 0.2989 |
| 3m | **0.2500** | 0.2557 | 0.2692 | 0.2906 | 0.3199 |
| 6m | **0.2500** | 0.2599 | 0.2785 | 0.3058 | 0.3412 |
| 1y | **0.2500** | 0.2635 | 0.2859 | 0.3173 | 0.3560 |

**Monotone increasing at every horizon. The optimum is λ = 0 — there is no interior optimum.** The
score carries no information justifying *any* displacement from neutral. Equal-weight's λ ≈ 0.4 is
merely *less wrong*, not right.

### H2 — Poor scaling: **SUPPORTED, and the mechanism is an algebraic identity**

`se` is **recovered** as `|effect / z_raw|`, so:

```
weight = 1/se²  =  (z_raw / effect)²
```

Since `se` is *defined* by the effect, inverse-variance weighting degenerates. Across the six active
models, `|z|` spans only 0.54–0.89 (1.6x) while `median |effect|` spans 3.0x — so the 1/effect² term
dominates:

| Model | median \|effect\| | median se | **mean weight** |
|---|---|---|---|
| `sector_rotation` | **7.07e-03** (smallest) | 2.07e-02 | **0.2903** (largest) |
| `interest_rate_sensitivity` | 1.08e-02 | 2.34e-02 | 0.2295 |
| `macro_regime` | 1.10e-02 | 2.46e-02 | 0.1992 |
| `relative_strength` | 1.22e-02 | 2.55e-02 | 0.1632 |
| `momentum_exhaustion` | 1.37e-02 | 2.77e-02 | 0.1443 |
| `earnings_behavior` | **2.10e-02** (largest) | 4.44e-02 | **0.0556** (smallest) |

## **Spearman(median \|effect\|, mean weight share) = −1.000**

A **perfect rank inversion across all six models.** The model that expresses its view in the smallest
numbers wins the vote. `sector_rotation` is top-weighted in **55.9%** of cells for this reason alone —
and its LOO removal is harmless (−0.0106, CI includes zero), confirming the weight is unearned.

**The weighting measures units, not precision.** This is a genuine architectural defect — but see §2:
correcting it could not have produced a better ensemble, because there is nothing to weight.

### H3 — Redundant models / incorrect weighting assumptions: **PARTIALLY SUPPORTED, not causal**

Only **4 of 15** pairs are under-declared by realized z-correlation. The priors err in **both**
directions, and the largest single error is an **over**-statement:

- `momentum ↔ relative`: declared 0.50, realized **+0.513** — essentially correct.
- `relative ↔ sector`: declared 0.50, realized +0.478 — correct.
- `rates ↔ macro`: declared 0.50, realized **−0.003** — **massively over-declared**.
- `earnings ↔ sector` +0.283, `momentum ↔ sector` +0.276, `earnings ↔ relative` +0.245 — under-declared
  against 0.20, but modestly.

Redundancy is real (the price cluster is confirmed at +0.513) and the priors are imperfect, but they are
**not systematically too permissive**, so this cannot be the cause of overconfidence.

### H4 — Noise amplification: **REFUTED**

If low correlation priors were faking precision, combined `|z|` would exceed the average per-model
`|z|` by `√(k/(1+(k−1)ρ))` — **1.732** at k=6, ρ=0.2.

| Horizon | mean k | mean \|z\| per model | mean \|z\| combined | **empirical amplification** |
|---|---|---|---|---|
| 1w | 4.93 | 0.806 | 0.667 | **0.811** |
| 2w | 4.92 | 0.739 | 0.608 | **0.809** |
| 1m | 4.92 | 0.663 | 0.556 | **0.826** |
| 3m | 4.91 | 0.649 | 0.632 | 0.921 |
| 6m | 4.89 | 0.669 | 0.814 | 1.001 |
| 1y | 4.87 | 0.811 | 1.712 | 1.195 |

**The combiner DAMPENS z at short horizons (0.81x), it does not amplify it.** Theoretical 1.73 vs
empirical 0.83 at 1m. Sign cancellation among disagreeing models shrinks `effect_c` faster than the
quadratic form shrinks `se_c`.

**Consequence: the combiner is not the source of the overconfidence — it is a faithful transmitter of
it.** Per-model `|z| ≈ 0.66` already maps to a score ~19 points from neutral. The defect is
**upstream, in each model's own `se`/`z` recipe** — independently confirming the analogue RCA's **RC1**
("the `se` recipe overstates precision ~2x") and showing it is not analogue-specific.

### H5 — Prediction clipping: **REFUTED at the horizons that matter**

| Horizon | share of cells at `Z_CLIP` |
|---|---|
| 1w | 0.000 |
| 2w | 0.000 |
| 1m | 0.000 |
| 3m | 0.001 |
| 6m | 0.018 |
| 1y | 0.098 |

Clipping is **never** active at 1w–1m and touches 1.8% at 6m. It cannot explain a failure present at
every horizon. (It does bite at 1y, where 9.8% saturate — a minor contributor there only.)

### H6 — One model dominating: **SUPPORTED as a fact, REFUTED as a cause**

`sector_rotation` holds the largest weight in **55.9%** of cells and 29% of mean weight. Effective
models = 1/HHI = **4.08**, not 7. So dominance is real.

But its LOO removal is **harmless** (−0.0106, CI [−0.0443, +0.0208]), and no single model beats the full
ensemble. Dominance redistributed weight without changing the outcome.

### H7 — Interaction effects / model disagreement: **REFUTED as material**

The systems disagree on direction in only **6.9–7.9%** of cells, and accuracy on those cells is noise
(0.580, 0.558, 0.414 at 1w/2w/1m; n=29 at 1m). Ordering agreement is 0.89–0.98. **There is almost no
interaction surface for weighting to act on.**

### H8 — Overfitting: **REFUTED (not applicable)**

Nothing is fitted. The correlation priors are **hand-declared constants** (0.2 / 0.5) and the weights
are computed per cell from that cell's own `(effect, z)`. There are no estimated parameters, so
production weighting cannot be overfit. Its failure is *misspecification*, not overfitting.

---

## 2. Summary of hypotheses

| Hypothesis | Verdict | Key evidence |
|---|---|---|
| Excessive confidence / miscalibration | **SUPPORTED — primary** | Implied 0.69–0.72 vs realized 0.51; shrinkage sweep monotone to λ=0 |
| Poor scaling | **SUPPORTED — mechanism** | `weight = (z/effect)²`; Spearman(\|effect\|, weight) = **−1.000** |
| Sparse activation | **SUPPORTED — contributory** | `valuation` 0%; `earnings` 10.3%; 4.08 effective models |
| Redundant models / wrong priors | **PARTIALLY SUPPORTED, not causal** | 4/15 under-declared; largest error is an over-statement (−0.003 vs 0.50) |
| Noise amplification | **REFUTED** | Empirical 0.81–0.83 vs theoretical 1.73 — dampening, not amplifying |
| Prediction clipping | **REFUTED (≤3m)** | 0.000 saturated at 1w–1m |
| One model dominating | **Fact yes, cause no** | 55.9% dominance but LOO harmless |
| Interaction effects | **REFUTED** | 93–98% ordering agreement; 7% disagreement |
| Overfitting | **REFUTED (N/A)** | Zero fitted parameters |

---

## 3. Why equal weighting won — final statement

**Not because its weights are better.** Production and equal-weight rank cells 0.89–0.98 identically,
agree directionally 91–96% of the time, and show no consistent rank-IC difference. The weighting choice
is almost informationally irrelevant on this panel.

**Because it applies λ ≈ 0.4 shrinkage as a side effect** of averaging in probability space rather than
z space. Since the underlying score has ~0 skill, any shrinkage improves Brier, and 96–104% of the
observed gap is exactly that.

**And equal-weight is still not right.** The Brier-optimal λ is **0** at every horizon. Equal-weight is
a less-overconfident presentation of the same non-signal. The correct reading of "equal-weight beat
production" is **not** "the weighting is broken" — it is **"the score has nothing in it, and the system
that says so more quietly scores better."**
