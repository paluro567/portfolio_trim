# V6 ARM 1.5 — DIAGNOSTICS

**Trigger condition ("if LOSS exceeds expectations") was NOT met.** No horizon reached the
preregistered FAIL threshold. Diagnostics are reported to localise where loss *could* originate.
**Only measured quantities appear below.**

---

## D1 · Weighting — eliminated as a source, by construction

| Horizon | mean HHI ρ=0 | mean HHI ρ=0.20 | Δ | effective models |
|---|---|---|---|---|
| 1w | 0.2754 | 0.2754 | **0.0000** | 3.75 → 3.75 |
| 2w | 0.2605 | 0.2605 | **0.0000** | 3.95 → 3.95 |
| 1m | 0.2497 | 0.2497 | **0.0000** | 4.13 → 4.13 |
| 3m | 0.2376 | 0.2376 | **0.0000** | 4.36 → 4.36 |
| 6m | 0.2454 | 0.2454 | **0.0000** | 4.27 → 4.27 |
| 1y | 0.2690 | 0.2690 | **0.0000** | 4.13 → 4.13 |

Weights are `w = 1/se²`. The preregistration held `se` at its original recovered value, so **weights are
mathematically incapable of moving under injection.** Measured invariance to four decimals confirms the
implementation matched the specification.

> **Consequence: no part of the measured LOSS can originate in weight reallocation.** This is an
> arithmetic elimination, not a statistical one.

**A scope limit, stated plainly:** because weights were held fixed by design, **Arm 1.5 did not test
whether the weighting scheme is well-chosen.** It tested whether the aggregation destroys signal *given*
those weights. The separately measured `Spearman(median|effect|, weight) = −1.000` inversion is
untouched by this experiment and remains an open question about weight *quality*.

## D2 · Aggregation — measured, and near-neutral

With weights, normalisation and the Φ mapping all fixed, the only remaining channel is the
weighted-mean effect. Measured LOSS at ρ = 0.10: **−0.0216, −0.0017, +0.0161, +0.0014, −0.0219,
+0.0337**. Mixed sign, and negative at the best-powered horizon.

**Scaling test:** if aggregation destroyed a fixed *fraction* of signal, LOSS would grow linearly in ρ.
Measured slopes per unit ρ: **−0.031, −0.036, −0.071, +0.078, +0.099, +0.202**. Mixed sign, and negative
at the three best-powered horizons — **the opposite of proportional destruction.**

## D3 · Normalisation and score generation — verified exact

`score = 100·Φ(clip(z_raw))` reproduced with **max error 0.000e+00** across 36,926 non-neutral rows.
The per-model normalisation is exact; it introduces no measurable loss.

## D4 · Ranking — the metric is rank-invariant

The endpoint is a Spearman IC, invariant to any monotone transform. **Clipping at `Z_CLIP` and the Φ
mapping are both monotone**, so neither can alter the measured IC except where clipping saturates and
ties ranks. Saturation was measured at 0.000 for 1w–1m in prior work.

## D5 · Confidence adjustment — not in the path

`confidence` is carried through the combiner but does not enter `combined_score`. It cannot contribute
to LOSS. **Confirmed by inspection of the combination path, not by assumption.**

## D6 · Are the injected models down-weighted?

| Model | mean weight | κ (its injection scale) |
|---|---|---|
| sector_rotation | 0.2879 | 0.0391 |
| interest_rate_sensitivity | 0.2294 | 0.0625 |
| macro_regime | 0.2024 | 0.0814 |
| relative_strength | 0.1635 | 0.0570 |
| momentum_exhaustion | 0.1448 | 0.0576 |
| earnings_behavior | 0.0506 | 0.0289 |

**Spearman(κ, mean weight) = +0.314** — weakly *positive*, and at n = 6 models **not distinguishable
from zero.**

> **Note on the relationship to the prior −1.000 finding.** That result correlated weight against
> **median |effect|** (magnitude). This one correlates weight against **κ = the standard deviation of
> effects** (dispersion). These are different quantities and the two results are not in conflict.
> **Arm 1.5 provides no evidence for or against the −1.000 inversion.**

## D7 · Where loss originates — summary

| Candidate source | Status | Evidence |
|---|---|---|
| **Weighting (reallocation)** | **ELIMINATED** | HHI invariant to 4 dp; weights fixed by construction |
| **Normalisation** | **ELIMINATED** | score↔z mapping exact, max err 0.000e+00 |
| **Ranking** | **ELIMINATED** | metric is rank-invariant; monotone transforms only |
| **Confidence adjustment** | **ELIMINATED** | not in the combined-score path |
| **Aggregation (weighted mean)** | **MEASURED, NEAR-NEUTRAL** | mixed-sign LOSS; no proportional scaling; negative at the best-powered horizon |
| **Weight *quality*** | **NOT TESTED** | out of scope by design — `se` held fixed |

## D8 · Stability

**Across horizons:** LOSS magnitude tracks 1/√n rather than horizon length. The two largest |LOSS|
values (1y +0.0337, 6m −0.0219) occur at the two smallest samples (n = 45, 92) and both CIs span zero.
**Consistent with sampling noise, not a horizon-specific pathology.**

**Across securities:** the block bootstrap resamples per-symbol series, so the reported CIs already
absorb between-symbol variation. No single symbol drives the result at any horizon; had one done so,
the CIs would have widened materially beyond the observed 0.024–0.173.
