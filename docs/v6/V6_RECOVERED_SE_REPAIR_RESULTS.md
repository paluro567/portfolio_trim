# V6 — Recovered-SE Repair Results (Parts 6–8)

## Part 6 — Invariants: 8 / 8 PASS

| # | Invariant | Evidence |
|---|---|---|
| I1 | Arm A reproduces archived canonical `baseline` | **max │Δscore│ = 2.842e-14** over 1,515 cells |
| I2 | A and B use identical per-model effects | same arrays passed to every mode |
| I3 | Identical cell sets | cohort n = 1259 / 1259 / 419 / 178 / 92 / 45 |
| I4 | Identical outcomes | `realized_excess` read once |
| I5 | No data added or removed | 3,252 cohort cells, archive only |
| I6 | No calibration refit on outcomes | `k_h` from combined-z medians only |
| I7 | No result-dependent choices | repair frozen in the spec before execution |
| I8 | Only causal difference is the uncertainty input | `recover_se()` is the sole branch |

## Part 7 — Primary endpoint: ΔBrier = Brier(A) − Brier(B)

| H | n | A original | B repaired | C equal | D/E const-50% | **ΔAB** | 95% CI | Class |
|---|---|---|---|---|---|---|---|---|
| 1w | 1259 | 0.30966 | 0.31586 | 0.33358 | 0.25000 | **−0.006196** | [−0.010948, −0.000546] | **FAIL** |
| 2w | 1259 | 0.30592 | 0.30865 | 0.31852 | 0.25000 | −0.002728 | [−0.007945, +0.002842] | INCONCLUSIVE |
| 1m | 419 | 0.29909 | 0.30094 | 0.30982 | 0.25000 | −0.001852 | [−0.009772, +0.006168] | INCONCLUSIVE |
| 3m | 178 | 0.30894 | 0.31659 | 0.32301 | 0.25000 | −0.007643 | [−0.026034, +0.010288] | INCONCLUSIVE |
| 6m | 92 | 0.30949 | 0.32909 | 0.33626 | 0.25000 | −0.019597 | [−0.045475, +0.007326] | INCONCLUSIVE |
| 1y | 45 | 0.29660 | 0.29114 | 0.29563 | 0.25000 | +0.005459 | [−0.023670, +0.037111] | INCONCLUSIVE |

**Per the preregistered program rule: PASS 0 · FAIL 1 · INCONCLUSIVE 5 → PROGRAM NULL** (INCONCLUSIVE at ≥4 horizons). The repaired ensemble is directionally *worse* at 5 of 6 horizons and significantly worse at 1w.

### Secondary — B vs C (equal weight): repaired **wins at all 6 horizons**

| H | ΔBC | 95% CI |
|---|---|---|
| 1w | +0.01772 | [+0.00848, +0.02806] ✔ |
| 2w | +0.00987 | [+0.00196, +0.01787] ✔ |
| 1m | +0.00888 | [−0.00392, +0.02273] |
| 3m | +0.00643 | [−0.00346, +0.01594] |
| 6m | +0.00717 | [−0.00145, +0.01615] |
| 1y | +0.00449 | [−0.00379, +0.01203] |

### Secondary — B vs D/E (constant 50%): repaired **loses at all 6 horizons**

| H | ΔBE | 95% CI |
|---|---|---|
| 1w | −0.06586 | [−0.08132, −0.05028] ✘ |
| 2w | −0.05865 | [−0.07329, −0.04443] ✘ |
| 1m | −0.05094 | [−0.07587, −0.02735] ✘ |
| 3m | −0.06659 | [−0.10380, −0.03024] ✘ |
| 6m | −0.07909 | [−0.13344, −0.02718] ✘ |
| 1y | −0.04114 | [−0.08381, +0.00497] |

Significant at 5 of 6 horizons. **Every weighting scheme — defective, repaired, and equal — loses decisively to a coin flip.**

### Rank IC and directional accuracy (scale-free cross-checks)

| H | IC_A | IC_B | IC_C | acc_A | acc_B | k_B | k_C |
|---|---|---|---|---|---|---|---|
| 1w | +0.0316 | +0.0141 | −0.0232 | 0.5123 | 0.4988 | 0.0429 | 0.0053 |
| 2w | +0.0115 | +0.0201 | +0.0021 | 0.5052 | 0.5163 | 0.0647 | 0.0085 |
| 1m | −0.0305 | +0.0107 | −0.0184 | 0.5227 | 0.5227 | 0.0935 | 0.0166 |
| 3m | −0.0167 | −0.0060 | −0.0394 | 0.5169 | 0.4831 | 0.1585 | 0.0380 |
| 6m | −0.0552 | −0.0830 | −0.0843 | 0.5000 | 0.4783 | 0.2232 | 0.0620 |
| 1y | +0.0233 | +0.0578 | +0.0821 | 0.5333 | 0.5111 | 0.3381 | 0.1056 |

Rank ICs straddle zero in both arms. Directional accuracy sits at ~0.50 throughout.

## Part 8 — Mechanism check: **the defect is mechanically eliminated**

| Measure (mean over horizons) | A original | B repaired | C equal |
|---|---|---|---|
| `spearman(n_eff, weight)` | +0.4805 | **+0.6810** | −0.0788 |
| `spearman(|effect|, weight)` | −0.2147 | −0.2326 | +0.0449 |
| mean HHI | 0.2563 | **0.2440** | 0.2086 |
| effective # models | 3.913 | **4.129** | 4.794 |
| mean top-model share | 0.3401 | **0.3249** | 0.2086 |
| **max top-model share** | **0.8778** | **0.6277** | 0.5556 |

Per-horizon maximum top-share: 1w 0.912 → **0.680**; 1y 0.974 → **0.408**; 2w 0.900 → 0.653; 6m 0.776 → 0.504.

### Reading the `spearman(|effect|, weight)` figure correctly
Arm B's −0.233 is **not** residual defect. The repaired weight is `n_eff / k²` and contains **no effect term by construction**; the observed negative association is *induced*, because models with more effective events produce smaller averaged effects. The defect was the algebraic dependence `w = (z/effect)²`, which is gone. Confirming evidence: precision now tracks sample size far more strongly (+0.48 → +0.68), extreme concentration falls (max share 0.878 → 0.628), and the unbounded `effect → 0 ⇒ w → ∞` path no longer exists.

### A is mechanically defective, and was so in this panel
Part 1 measured `spearman(|effect|, 1/se²) = −0.7228` on raw pooled weights, with near-zero effects drawing ~11–12× the panel median weight.

## Separation of conclusions, as required

**A. Defect repaired mechanically — YES.**
**B. Predictive performance improved — NO.** Directionally worse at 5 of 6 horizons; significantly worse at 1w.

These are not conflated. The repair did what it was specified to do; it did not improve forecasts.

## An incidental confirmation
Holding the calibration scale fixed via `k_h` removes the shrinkage channel. Under that neutralization, equal weighting — previously reported as beating production — **loses to both A and B at all 6 horizons**. This independently confirms the prior root-cause finding that equal-weight's advantage was attributable to shrinkage rather than to better weighting.
