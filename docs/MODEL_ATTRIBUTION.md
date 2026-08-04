# Model Attribution — Parts 2 and 3

Every figure derives from the exactly-replicated production combiner
([ENSEMBLE_VERIFICATION.md](ENSEMBLE_VERIFICATION.md) §1). 7,514 cells; primary horizon 1m.

---

## 1. Per-model decomposition (Part 2)

| Model | Activation | Mean score | SD score | median \|effect\| | median se | mean \|z\| | **mean weight** | p90 weight | **top-weight in % cells** |
|---|---|---|---|---|---|---|---|---|---|
| `sector_rotation` | 0.987 | 45.37 | 21.61 | **7.07e-03** | 2.07e-02 | 0.54 | **0.2903** | 0.4114 | **55.9%** |
| `interest_rate_sensitivity` | 0.986 | 41.38 | 25.21 | 1.08e-02 | 2.34e-02 | 0.75 | 0.2295 | 0.3304 | 17.5% |
| `macro_regime` | 0.975 | 45.09 | 25.82 | 1.10e-02 | 2.46e-02 | 0.89 | 0.1992 | 0.3014 | 17.1% |
| `relative_strength` | 0.828 | 49.87 | 24.67 | 1.22e-02 | 2.55e-02 | 0.74 | 0.1632 | 0.2317 | 3.6% |
| `momentum_exhaustion` | 0.903 | 51.41 | 25.24 | 1.37e-02 | 2.77e-02 | 0.70 | 0.1443 | 0.2292 | 5.6% |
| `earnings_behavior` | **0.103** | 50.57 | 7.43 | **2.10e-02** | 4.44e-02 | 0.59 | **0.0556** | 0.1279 | 0.2% |
| `valuation` | **0.000** | 50.00 | 0.00 | — | — | — | **0.0000** | 0.0000 | 0.0% |

**Weight concentration:** mean HHI 0.261, median 0.236, p90 0.326 → **effective number of contributing
models = 1/HHI = 4.08**, not 7.

### Which models dominate the final score?

`sector_rotation` (mean weight 0.290, top-weighted in **55.9%** of cells) and
`interest_rate_sensitivity` (0.230). Together they carry **52%** of the precision weight.

### Which models rarely matter?

`valuation` — **provably zero**: 100% neutral across 7,938 rows, never enters a single combination.
`earnings_behavior` — 10.3% activation, 5.6% mean weight, top-weighted in 0.2% of cells.

**So the "seven-model" ensemble is a 5-model ensemble with 4.08 effective contributors.**

### Which models frequently oppose one another?

Realized correlation of the per-model `z` at 1m, against the declared prior:

| Pair | Declared | Realized (effect) | Realized (z) |
|---|---|---|---|
| `momentum_exhaustion` ↔ `relative_strength` | 0.50 | +0.477 | **+0.513** |
| `relative_strength` ↔ `sector_rotation` | 0.50 | +0.299 | +0.478 |
| `earnings_behavior` ↔ `sector_rotation` | 0.20 | +0.274 | **+0.283** ← under-declared |
| `momentum_exhaustion` ↔ `sector_rotation` | 0.20 | +0.108 | **+0.276** ← under-declared |
| `earnings_behavior` ↔ `relative_strength` | 0.20 | +0.229 | **+0.245** ← under-declared |
| `interest_rate_sensitivity` ↔ `sector_rotation` | 0.20 | +0.158 | +0.116 |
| `macro_regime` ↔ `momentum_exhaustion` | 0.20 | −0.053 | **−0.130** ← opposes |
| `macro_regime` ↔ `relative_strength` | 0.20 | +0.051 | **−0.066** ← opposes |
| `earnings_behavior` ↔ `macro_regime` | 0.20 | −0.025 | **−0.096** ← opposes |
| **`interest_rate_sensitivity` ↔ `macro_regime`** | **0.50** | **−0.019** | **−0.003** ← *massively over-declared* |

- **Genuinely redundant:** the price cluster. `momentum ↔ relative` realized +0.513 against a declared
  0.50 — **the prior is essentially correct**.
- **Genuinely opposing:** `macro_regime` against the price models (−0.066 to −0.130).
- **The largest prior error is an OVER-statement:** `rates ↔ macro` is declared 0.50 and realized
  **−0.003** — treated as half-redundant when it is independent, which *under*-weights their joint
  evidence.
- Only **4 of 15** pairs are under-declared. The priors err in **both** directions.

---

## 2. Contribution during correct vs incorrect predictions

Mean signed contribution (`weight_share × effect`, which sums to the combined effect), split by whether
the ensemble's directional call was right:

| Model | n correct | n incorrect | mean contrib (correct) | mean contrib (incorrect) | **mean \|contrib\| correct − incorrect** |
|---|---|---|---|---|---|
| `interest_rate_sensitivity` | 3498 | 3684 | −6.56e-03 | −9.23e-03 | **−2.82e-03** |
| `macro_regime` | 3456 | 3649 | −1.10e-02 | −1.28e-02 | **−2.53e-03** |
| `sector_rotation` | 3505 | 3707 | −6.72e-04 | −2.51e-03 | **−2.14e-03** |
| `relative_strength` | 3086 | 3209 | −1.58e-03 | −1.45e-03 | **−5.97e-04** |
| `momentum_exhaustion` | 3362 | 3515 | −8.41e-04 | −1.52e-04 | **−2.12e-04** |
| `earnings_behavior` | 406 | 355 | +1.25e-05 | +2.40e-04 | **−1.23e-04** |

### **All six active models push HARDER when the ensemble is WRONG.**

The final column is negative for **every** model without exception. Magnitude of conviction is
**anti-correlated with correctness** — a within-cell restatement of the overconfidence result, and
independent of any weighting choice.

Note also that contributions are predominantly **negative** for five of six models: the ensemble
carries a structural bearish tilt (mean score 37.4–45.0, bullish in only 29–42% of cells).

---

## 3. Leave-one-model-out (Part 3)

Δ = (ensemble **without** the model) − (full ensemble). **Positive Δ dir acc ⇒ removing the model
HELPS.** Primary horizon 1m, paired, block bootstrap.

| Removed model | n | Δ dir acc | 95% CI | Δ Brier | 95% CI |
|---|---|---|---|---|---|
| **`interest_rate_sensitivity`** | 420 | **−0.0381** | **[−0.0678, −0.0070]** | +0.0084 | [−0.0010, +0.0179] |
| `momentum_exhaustion` | 420 | −0.0119 | [−0.0350, +0.0117] | −0.0004 | [−0.0060, +0.0058] |
| `relative_strength` | 420 | −0.0119 | [−0.0374, +0.0164] | +0.0020 | [−0.0045, +0.0082] |
| `sector_rotation` | 378 | −0.0106 | [−0.0443, +0.0208] | −0.0036 | [−0.0123, +0.0061] |
| `macro_regime` | 379 | −0.0026 | [−0.0312, +0.0286] | +0.0016 | [−0.0085, +0.0111] |
| `earnings_behavior` | 420 | +0.0024 | [−0.0070, +0.0117] | −0.0007 | [−0.0017, +0.0003] |
| **`valuation`** | 420 | **+0.0000** | **[+0.0000, +0.0000]** | **+0.0000** | **[+0.0000, +0.0000]** |

**Exactly one CI excludes zero: `interest_rate_sensitivity`.** Removing it costs 3.8 pp of directional
accuracy.

`valuation`'s zero-width CI at exactly zero is not a statistical result — it is proof of an identity.
Removing an always-neutral model is a mathematical no-op.

## 4. Add-one / solo comparison

Δ = (model **alone**) − (full ensemble), 1m:

| Model | n | Δ dir acc | 95% CI | Δ Brier |
|---|---|---|---|---|
| `momentum_exhaustion` | 184 | +0.0272 | [−0.0363, +0.1036] | −0.0102 |
| `sector_rotation` | 321 | +0.0062 | [−0.0456, +0.0547] | +0.0048 |
| `interest_rate_sensitivity` | 378 | +0.0000 | [−0.0495, +0.0443] | +0.0079 |
| `relative_strength` | 126 | −0.0159 | [−0.0929, +0.0571] | +0.0070 |
| `macro_regime` | 391 | −0.0307 | [−0.0875, +0.0250] | +0.0366 |
| `earnings_behavior` | 18 | −0.0556 | degenerate (n=18) | +0.0461 |

**No single model is distinguishable from the full ensemble.** Every CI includes zero. The
`momentum_exhaustion` Brier improvement (−0.0102) is the largest solo gain and is not significant.

---

## 5. Classification

| Model | Classification | Evidence |
|---|---|---|
| `interest_rate_sensitivity` | **HELPFUL** | The only model whose LOO removal degrades directional accuracy with a **CI excluding zero** (−0.0381, [−0.0678, −0.0070]). Carries 23% of weight, 98.6% activation |
| `valuation` | **NEUTRAL (proven, not inferred)** | 100% neutral over 7,938 rows; contributes exactly 0; LOO Δ = 0.0000 with a zero-width CI. Dead weight in the registry |
| `earnings_behavior` | **NEUTRAL (effectively)** | 10.3% activation, 5.6% weight, top-weighted in 0.2% of cells. LOO Δ = +0.0024 [−0.0070, +0.0117] — the only positive-on-removal, but inconclusive and immaterial |
| `macro_regime` | **INCONCLUSIVE** | LOO −0.0026 [−0.0312, +0.0286]; solo the *worst* performer (dir acc 0.4758, Brier 0.3389). Its claimed uniqueness holds (realized z-corr −0.003 to −0.130 vs the others) but no performance consequence is measurable. **Note: the prior "macro is the only unique predictor" claim gains no support here** |
| `momentum_exhaustion` | **INCONCLUSIVE** | LOO −0.0119 [−0.0350, +0.0117]. Best solo rank IC (+0.0677) and best solo Brier delta (−0.0102), neither significant |
| `relative_strength` | **INCONCLUSIVE** | LOO −0.0119 [−0.0374, +0.0164]. Realized z-corr +0.513 with momentum confirms the redundancy, but removal shows no benefit — **the prior retire-RS hypothesis remains undecided, and on this panel removal now leans mildly *negative*** |
| `sector_rotation` | **INCONCLUSIVE** | Dominant by weight (55.9% of cells, 29% mean weight) yet LOO −0.0106 [−0.0443, +0.0208]. Its dominance is a units artifact, not a merit — see [WEIGHTING_ANALYSIS.md](WEIGHTING_ANALYSIS.md) |

### **HARMFUL: none.**

No model's removal improves the ensemble with a CI excluding zero. The failure is **not** attributable
to a bad component.

---

## 6. Attribution summary

1. **One model is demonstrably helpful** (`interest_rate_sensitivity`); one is demonstrably inert
   (`valuation`); one is effectively inert (`earnings_behavior`); four are inconclusive; **none is
   harmful**.
2. **The ensemble has 4.08 effective contributors, not 7.**
3. **Every model pushes harder when the ensemble is wrong.** Six of six, no exceptions.
4. **The dominant model by weight (`sector_rotation`, 55.9% of cells) is dominant for reasons unrelated
   to its accuracy** — it reports the smallest effect magnitudes.
5. **The declared correlation priors are wrong in both directions**, with the single largest error
   being an over-statement (`rates ↔ macro`: 0.50 declared, −0.003 realized).

Because no component is harmful and no single model beats the whole, **the failure cannot be explained
at the level of model membership.** It is a property of how the components are combined and scaled —
analysed next.
