# Root Cause Tree — Part 7

---

## 1. The causal tree

```
                    OBSERVED: always-neutral > equal-weight > production ensemble
                              (Brier 0.2500  <  0.2574  <  0.2989 @1m)
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    │                                                   │
        ROOT CAUSE A (necessary)                          ROOT CAUSE B (sufficient)
        NO EXPLOITABLE SIGNAL                             SCORES OVERSTATE CERTAINTY
        in the score's ordering                           by ~19 points of displacement
                    │                                                   │
    ┌───────────────┴──────────┐                    ┌───────────────────┴──────────────┐
    │                          │                    │                                  │
 dir acc 0.51 at 1w-1m    shrinkage sweep      per-model se ≡ |effect/z|       aggregation in z space,
 BELOW 0.50 at 3m/6m/1y   monotone to λ=0      → |z| ≈ 0.66 per model          then ONE Φ mapping
 rank IC neg 4 of 6       (NO interior             → score ≈ 50 ± 19           → no shrinkage applied
    │                      optimum)                        │                            │
    │                          │                           │                            │
    └──────────┬───────────────┘                           │                  equal-weight averages
               │                                           │                  Φ(z_i) instead → Jensen
               ▼                                           ▼                  pulls toward 50 (λ≈0.4)
     any displacement from 50                 implied accuracy 0.69-0.72                 │
     is a PURE Brier LOSS                     vs realized 0.46-0.51                      │
               │                              = +18 to +26 pp overclaim                  │
               │                                           │                             │
               └───────────────────┬───────────────────────┴─────────────────────────────┘
                                   ▼
                    Brier ordering is MONOTONE IN SCORE DISPERSION
                    (0.0 → 0.2500 ; 8.0 → 0.2574 ; 19.4 → 0.2989)
                                   │
                                   ▼
                    INFERIOR ENSEMBLE at every horizon, all CIs excluding zero
```

### The two roots are logically distinct and both required

- **A alone** would produce a *harmless* ensemble: no signal expressed quietly costs nothing (that is
  always-neutral, Brier 0.2500).
- **B alone** would produce a *useful* ensemble: real signal expressed too loudly still beats a constant.
- **A × B** produces the observed failure: confident statements about nothing. That product is the
  mechanism.

### Contributing (non-root) branches

```
 sparse activation ──► 4.08 effective models, not 7 ──► narrower evidence base
   (valuation 0%, earnings 10.3%)                        (does not cause B)

 weight = (z/effect)² ──► Spearman(|effect|, weight) = -1.000 ──► sector_rotation
   (se is a function of effect)                                   top-weighted 55.9%
                                                                        │
                                                          LOO-harmless ──► NO measurable
                                                                            consequence YET

 structural bearish tilt ──► mean score 37-45, bullish 29-42% ──► dir acc < 0.50 at 3m/6m/1y

 conviction ↑ when wrong ──► all 6 models: mean |contrib| lower on correct predictions
```

---

## 2. Ranked root causes

| Rank | Root cause | Confidence | Supporting evidence | Contradicting evidence |
|---|---|---|---|---|
| **1** | **Scores overstate certainty by ~19 points (B)** | **VERY HIGH** | Implied acc 0.694–0.722 vs realized 0.455–0.514 — an **+18 to +26 pp overclaim at all 6 horizons**. Brier 0.2989 vs 0.2500, CI excluding zero at all 6. Shrinkage sweep monotone. Per-model \|z\| ≈ 0.66 already produces the displacement | None |
| **2** | **No exploitable signal in the score's ordering (A)** | **HIGH** | Shrinkage optimum λ = **0** with **no interior optimum** at any horizon — a stricter test than the mean. dir acc below 0.50 at 3 of 6 horizons; rank IC negative at 4 of 6; 6 of 7 LOO inconclusive; no single model beats the whole | 7-survivor panel; dir-acc CIs ±0.05 could hide a small real effect. Cannot be *proven*, only strongly indicated |
| **3** | **Aggregation-space mismatch explains the equal-weight gap (B-branch)** | **VERY HIGH** | Rescaling production to equal-weight's dispersion closes **96.3%–103.6%** of the Brier gap at every horizon. Ordering agreement 0.89–0.98; sign agreement 91–96%; rank-IC delta has no consistent sign | None. This is the tightest quantitative result in the analysis |
| **4** | **`se ≡ \|effect/z\|` degenerates inverse-variance weighting into inverse-effect² weighting** | **VERY HIGH** (as a defect) / **LOW** (as a cause of *this* failure) | **Spearman = exactly −1.000** across all 6 active models; \|z\| spans 1.6x while \|effect\| spans 3.0x; `sector_rotation` top-weighted in 55.9% of cells | Its beneficiary is LOO-harmless (−0.0106, CI includes 0). Fixing it could not have helped, because per cause 2 there is nothing to weight |
| **5** | **Sparse activation shrinks the ensemble to 4.08 effective models** | **HIGH** (as a fact) / **LOW** (as a cause) | `valuation` 0.000 over 7,938 rows, LOO Δ = 0.0000 with zero-width CI; `earnings` 0.103; weight HHI 0.261 | Activating them would change the ensemble, not obviously improve it |
| **6** | **Structural bearish tilt** | **MODERATE** | Mean score 37.4–45.0; bullish 29–42%; 5 of 6 models negative mean contribution; coincides with sub-0.50 accuracy at 3m/6m/1y | Base rate of positive `spy_rel` is 0.46–0.55, so the tilt is roughly *correct* in direction — which sharpens cause 2 rather than adding a new one |
| **7** | **Conviction anti-correlates with correctness** | **MODERATE** | All 6 models: mean \|contribution\| lower on correct than incorrect predictions, no exceptions | Small magnitudes; no per-model CI computed. A consistent pattern, not a significance claim |
| **8** | **Correlation priors are misspecified** | **MODERATE** (as a fact) / **VERY LOW** (as a cause) | 4 of 15 pairs under-declared; `earnings ↔ sector` +0.283 vs 0.20 | Errors run **both** ways; the genuinely redundant pair is declared **correctly** (0.50 vs realized 0.513); the largest error is an *over*-statement (`rates ↔ macro`: 0.50 vs −0.003). Cannot generate one-directional overconfidence |

### Refuted, with the evidence that refuted them

| Hypothesis | Refuting evidence |
|---|---|
| **Noise amplification** | Empirical amplification **0.811 / 0.809 / 0.826** at 1w/2w/1m — the combiner **dampens** z. Theoretical value at k=6, ρ=0.2 is **1.732** |
| **Prediction clipping** | Share at `Z_CLIP` = **0.000** at 1w, 2w, 1m; 0.001 at 3m |
| **Model disagreement / interaction** | Ordering agreement 0.89–0.98; only 6.9–7.9% directional disagreement; accuracy there is noise |
| **Ranking instability** | Winsorized comparisons identical to 4 dp; two differently-weighted systems rank cells at ρ 0.89–0.98 |
| **Overfitting** | Zero fitted parameters — priors are hand-declared constants, weights computed per cell |
| **A harmful component model** | No model's removal improves the ensemble with a CI excluding zero. `interest_rate_sensitivity` removal *hurts* (−0.0381, CI [−0.0678, −0.0070]) |
| **One model dominating harmfully** | `sector_rotation` dominates 55.9% of cells, yet its LOO removal is harmless |

---

## 3. The chain in one paragraph

Each model recovers its standard error as `|effect / z_raw|`, which (a) fixes typical per-model `|z|`
near 0.66 and therefore guarantees a score roughly 19 points from neutral, and (b) makes the
inverse-variance weight algebraically equal to `(z/effect)²`, so weight ranks models by the inverse
square of their effect magnitude — a perfect rank inversion against effect size. The combiner then
faithfully transmits that displacement rather than amplifying it (empirical factor 0.81, not the
theoretical 1.73), and maps it once through Φ with no shrinkage. Because the score's ordering carries no
exploitable information — shrinkage sweep monotone with its optimum at λ = 0 — every point of that
19-point displacement is a pure Brier loss. Equal-weight averages in probability space instead, which
by Jensen applies λ ≈ 0.4 shrinkage and thereby recovers 96–104% of the gap; always-neutral applies
λ = 0 and wins outright. **The ordering of the three systems is exactly the ordering of their score
dispersion, because dispersion is the only thing that differs and there is no signal to reward it.**
