# Failure Mode Analysis — Parts 5 and 6

Explaining the ordering **always-neutral > equal-weight > production ensemble**, mechanism by
mechanism, then classifying each by what kind of limitation it is.

---

## 1. The ordering restated as arithmetic

| System | mean \|score − 50\| | effective λ | Brier @1m |
|---|---|---|---|
| Always-neutral | 0.0 | 0.00 | **0.2500** |
| Equal-weight | 8.0 | ≈ 0.41 | 0.2574 |
| Production | 19.4 | 1.00 | 0.2989 |

The ordering is **monotone in score dispersion**, and the shrinkage sweep is monotone increasing in λ at
all six horizons with its optimum at λ = 0. **The three systems are the same non-signal expressed at
three volumes, and the quietest wins.** Every mechanism below either explains the volume or is refuted.

---

## 2. Mechanism-by-mechanism

### M1 — No exploitable signal · **SUPPORTED (dominant)**

**For:** dir acc 0.5083 / 0.5123 / 0.5136 at 1w/2w/1m and **below 0.50** at 3m (0.4622), 6m (0.4549),
1y (0.4592). Pooled rank IC negative at four of six horizons. Shrinkage optimum λ = 0 with **no interior
optimum** — if any information existed, some λ > 0 would beat λ = 0. Six of seven LOO tests inconclusive.
No single model beats the full ensemble. A post-hoc constant bearish call would have won at four of six
horizons.

**Against:** the panel is 7 survivors; CIs on directional accuracy are ±0.05, so a small real effect
could hide. Absence of evidence, not evidence of absence — but the λ = 0 optimum is strong: it says
the score's *magnitude ordering* carries nothing, which is a stricter test than the mean.

### M2 — Miscalibration / overconfidence · **SUPPORTED (proximate cause of the Brier loss)**

**For:** mean |score − 50| ≈ 19–22 → implied accuracy 0.694–0.722 vs realized 0.455–0.514: a stable
**+18 to +26 pp overclaim at every horizon**. Brier 0.2989 vs 0.2500 for a constant forecast, CI
excluding zero at all six horizons.

**Against:** nothing. This is the single most robust finding in the analysis.

### M3 — Scale mismatch (`se ≡ |effect/z|`) · **SUPPORTED (mechanism of the weighting defect)**

**For:** `weight = 1/se² = (z/effect)²`. |z| spans 1.6x across models while |effect| spans 3.0x, so
1/effect² dominates. **Spearman(median |effect|, mean weight) = −1.000** — a perfect rank inversion
over all six active models. `sector_rotation` (smallest effects) is top-weighted in **55.9%** of cells.

**Against:** it is not the cause of the *observed* failure. Its victim (`sector_rotation` dominance) is
LOO-harmless (−0.0106, CI includes 0), and per M1 there is nothing to weight. A real defect with no
measurable consequence *yet*.

### M4 — Sparse activation · **SUPPORTED (contributory)**

**For:** `valuation` 0.000 activation over 7,938 rows — LOO Δ exactly 0.0000 with a zero-width CI, i.e.
provably no contribution. `earnings_behavior` 0.103 activation, 5.6% weight, top-weighted in 0.2% of
cells. Weight HHI 0.261 → **4.08 effective models, not 7.**

**Against:** the ensemble would not be better with them active; it would merely be different. Sparsity
reduces the *effective* ensemble but does not itself cause overconfidence.

### M5 — Noise amplification · **REFUTED**

**Against:** empirical amplification |z_combined| / mean|z_model| = **0.811 / 0.809 / 0.826** at
1w/2w/1m — the combiner **dampens**. The theoretical value under the declared priors (k=6, ρ=0.2) is
**1.732**. Sign cancellation among disagreeing models shrinks the combined effect faster than the
quadratic form shrinks the combined se.

**For:** at 1y amplification reaches 1.195 — a minor contributor at that horizon only.

**Consequence:** the combiner is a *faithful transmitter* of per-model overconfidence, not its source.
The defect sits **upstream**, in each model's own `se`/`z` recipe — independently reproducing the
analogue RCA's **RC1** and proving it generalises beyond the analogue model.

### M6 — Correlated models / redundant evidence · **PARTIALLY SUPPORTED, not causal**

**For:** the price cluster is confirmed — `momentum ↔ relative` realized z-correlation **+0.513**,
`relative ↔ sector` +0.478. Three pairs are under-declared (`earnings ↔ sector` +0.283,
`momentum ↔ sector` +0.276, `earnings ↔ relative` +0.245 against a 0.20 prior).

**Against:** only **4 of 15** pairs are under-declared, and the priors for the genuinely redundant pairs
are essentially **correct** (0.50 declared vs 0.513 realized). The largest single prior error is an
**over**-statement: `rates ↔ macro` declared 0.50, realized **−0.003**. Errors run in both directions, so
redundancy mishandling cannot produce a systematic one-directional overconfidence.

### M7 — Model disagreement / interaction effects · **REFUTED**

**Against:** production and equal-weight agree on ordering at Spearman **0.89–0.98** and on direction
**91–96%** of the time. They disagree in only 6.9–7.9% of cells, and accuracy there is noise (0.414 at
1m on n=29). There is almost no interaction surface.

### M8 — Prediction clipping · **REFUTED (≤3m)**

**Against:** share of cells at `Z_CLIP` is **0.000** at 1w, 2w and 1m, and 0.001 at 3m.

**For:** 0.018 at 6m and 0.098 at 1y — a minor long-horizon contributor.

### M9 — Improper aggregation space · **SUPPORTED (explains the EW gap specifically)**

**For:** production averages in `z` space then maps once through Φ; equal-weight averages `Φ(z_i)`
directly. Averaging in probability space with mixed-sign inputs pulls toward 0.5 by Jensen — worth
λ ≈ 0.4. Rescaling production to equal-weight's dispersion closes **96.3%–103.6%** of the Brier gap,
so the aggregation-space difference **is** the whole gap.

**Against:** it is not a defect so much as an accident. Equal-weight's shrinkage is unprincipled; it is
right only because the true optimum (λ=0) lies in that direction.

### M10 — Ranking instability · **REFUTED**

**Against:** ordering agreement 0.89–0.98 between two differently-weighted systems, and the winsorized
comparison is **identical to 4 decimal places**. Rankings are stable; they are just uninformative.

### M11 — Structural directional bias · **SUPPORTED (new, contributory at long horizons)**

**For:** mean ensemble score 37.4–45.0 at every horizon; bullish in only **29–42%** of cells. Five of
six models carry negative mean contributions. At 3m/6m/1y this coincides with dir acc *below* 0.50.

**Against:** the realized base rate of positive `spy_rel` is 0.46–0.55, so a bearish tilt is roughly
*correct in direction* on this panel — which makes it worse, not better, that the ensemble still only
reaches 0.514: the tilt is right and the discrimination is nil.

### M12 — Conviction anti-correlates with correctness · **SUPPORTED (novel)**

**For:** for **all six** active models, mean |contribution| is lower on correct predictions than on
incorrect ones (`rates` −2.82e-03, `macro` −2.53e-03, `sector` −2.14e-03, `relative` −5.97e-04,
`momentum` −2.12e-04, `earnings` −1.23e-04). No exceptions.

**Against:** magnitudes are small and no CI was computed per model. Reported as a consistent
six-of-six pattern, not a significance claim.

---

## 3. Part 6 — Would cleaner data change this?

| # | Mechanism | Limitation type | **Would survivorship-clean data change the conclusion?** | Why |
|---|---|---|---|---|
| **M2** | Miscalibration / overconfidence | **Methodology-limited** | **DEFINITELY NOT** | `se ≡ \|effect/z\|` and `score = 100·Φ(z)` are formulas. The 18–26 pp overclaim is produced by code, not by which securities are in the panel. Clean data would re-measure the same defect on more names |
| **M3** | Scale mismatch (weight = inverse effect²) | **Architecture-limited** | **DEFINITELY NOT** | Spearman −1.000 is an algebraic identity of the weight definition. It holds for any dataset |
| **M5** | Noise amplification | **Architecture-limited** | **DEFINITELY NOT** (already refuted) | Amplification is a function of k and the declared priors, not of the data |
| **M8** | Prediction clipping | **Architecture-limited** | **DEFINITELY NOT** | `Z_CLIP` is a constant |
| **M9** | Improper aggregation space | **Architecture-limited** | **DEFINITELY NOT** | Jensen's inequality does not depend on the sample |
| **M7** | Model disagreement / interaction | **Architecture-limited** | **PROBABLY NOT** | Cross-model agreement is driven by shared features; a wider panel changes the estimate slightly, not the ~95% agreement |
| **M10** | Ranking instability | **Statistical-limited** | **PROBABLY NOT** | Already refuted; more data would confirm stability |
| **M6** | Correlated / redundant models | **Statistical-limited** | **POSSIBLY** | Realized correlations are estimated on 7 names. A broad clean panel would estimate the priors properly — genuinely useful, but the priors err in both directions so it does not overturn M2 |
| **M12** | Conviction anti-correlates with correctness | **Statistical-limited** | **POSSIBLY** | A six-of-six pattern on one narrow panel. Wider data would confirm or dissolve it |
| **M11** | Structural bearish tilt | **Data-limited (partly)** | **POSSIBLY** | The tilt's *cost* depends on the outcome base rate. On a clean panel including delisted losers the base rate falls, and a bearish tilt would be penalised **less**. This is the one mechanism where clean data plausibly moves the number in the ensemble's favour |
| **M4** | Sparse activation | **Data-limited** (`valuation`) / **Architecture-limited** (`earnings`) | **POSSIBLY** for `valuation` only | `valuation` is inert for a pure data reason (~1 PIT fundamentals snapshot). But Norgate supplies prices/delisting, **not** PIT fundamentals — so *Norgate specifically* would not fix it |
| **M1** | No exploitable signal | **Statistical-limited** | **POSSIBLY** | Clean, broader data would measure it far more precisely. But per `POWER_FEASIBILITY_REPORT.md`, whether it becomes *decisive* depends on σ_true, which is unmeasured |

### Tally

| Verdict | Mechanisms |
|---|---|
| **Definitely not** | M2, M3, M5, M8, M9 — **including both mechanisms that fully explain the observed failure** |
| Probably not | M7, M10 |
| Possibly | M1, M4 (valuation only), M6, M11, M12 |
| Probably / Definitely | **none** |

---

## 4. Conclusion of Part 6

**The two mechanisms that account for the entire observed failure are M2 (overconfidence) and M9
(aggregation space) — and cleaner data would change neither.**

- M2 is a formula: `se ≡ |effect/z|` guarantees the per-model z that maps to a ~19-point displacement,
  regardless of which securities are in the panel.
- M9 is Jensen's inequality: it accounts for 96–104% of the equal-weight gap and is sample-independent.
- M3, the weighting defect, is an algebraic identity (Spearman **exactly** −1.000) and equally
  data-invariant.

Survivorship-clean data would address **M1** (measure the no-signal verdict precisely), part of **M4**
(only via PIT fundamentals, which Norgate does not supply), and **M11** (the tilt's cost). It would
change **nothing** about why the ensemble lost to a constant 50%.

**Norgate does not address the actual bottleneck.** The bottleneck is the calibration and aggregation
methodology, which is entirely inside this repository.
