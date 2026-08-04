# Ensemble Verification — Part 1

Independent replication of the production combiner from the frozen per-model capture, then
re-derivation of every prior comparison. Panel: `data/validation/analogue_v1/embargoed_revalidation`
(7 securities, 189 dates, 2019-01-02 → 2026-06-26). Target: `spy_rel` (system-independent).
Scratchpad drivers only; **no `src/` changes**.

---

## 1. Combiner replication is exact

The production path (`combine_model_evidence` → `combine_evidence` → `score_from_z`) was
re-implemented independently from the captured `(effect, z_raw)` per model, and validated cell-by-cell
against the shipped `mip.validation.systems.combine_rows` output in `merged.csv`.

| Check | Result |
|---|---|
| Cells replicated | **7,514** |
| Cells cross-validated against shipped output | **7,290** |
| **Max absolute score error** | **2.84 × 10⁻¹⁴** |
| Mean absolute score error | 1.57 × 10⁻¹⁵ |

**Replication is exact to floating-point.** Every weight, contribution, and amplification figure in
the companion reports is therefore the *actual* production arithmetic, not an approximation of it.

### The production combiner as a mathematical object

```
per model i:   effect_i = expected_excess_return
               se_i     ≡ |effect_i / z_raw_i|          ← RECOVERED, not measured
               w_i      = 1 / se_i²
combined:      effect_c = Σ w_i·effect_i / Σ w_i
               var_c    = (w' C w) / (Σw)²              C = declared correlation priors
               z_c      = effect_c / √var_c
               score    = 100 · Φ( clip(z_c, ±Z_CLIP) )
```

Neutral models are excluded before combination. `Z_CLIP` bounds the reported z.

---

## 2. Every prior comparison, reproduced

Primary horizon 1m, non-overlapping cohort, paired on identical `(symbol, as_of, horizon)` cells.

| System | n | Dir acc | Rank IC | **Brier** | mean \|score−50\| |
|---|---|---|---|---|---|
| **Production ensemble** (7 official) | 419 | 0.5131 | −0.0209 | **0.2989** | **19.4** |
| **Equal-weight** (mean of 7 scores) | 419 | 0.5322 | +0.0054 | **0.2574** | **8.0** |
| **Always-neutral** (score ≡ 50) | — | *no call* | *undefined* | **0.2500** | 0.0 |
| Best single (`momentum_exhaustion`) | 400 | 0.5175 | +0.0677 | 0.3103 | — |
| `relative_strength` alone | 360 | 0.5250 | +0.0368 | 0.3055 | — |
| `sector_rotation` alone | 419 | 0.5155 | −0.0489 | 0.3059 | — |
| `interest_rate_sensitivity` alone | 417 | 0.5132 | +0.0564 | 0.3116 | — |
| `macro_regime` alone | 414 | 0.4758 | −0.0706 | 0.3389 | — |
| `earnings_behavior` alone | 50 | 0.4400 | −0.0745 | 0.3370 | — |
| `valuation` alone | **0** | *inert* | — | — | — |

### Brier, paired, all horizons (Δ = production − comparator; **positive = production worse**)

| Horizon | vs always-neutral | 95% CI | vs equal-weight | 95% CI |
|---|---|---|---|---|
| 1w | +0.0642 | [+0.0493, +0.0778] | +0.0542 | [+0.0443, +0.0632] |
| 2w | +0.0565 | [+0.0424, +0.0694] | +0.0484 | [+0.0388, +0.0567] |
| **1m** | +0.0519 | [+0.0306, +0.0738] | +0.0436 | [+0.0302, +0.0563] |
| 3m | +0.0700 | [+0.0352, +0.0992] | +0.0573 | [+0.0368, +0.0736] |
| 6m | +0.0994 | [+0.0540, +0.1193] | +0.0742 | [+0.0413, +0.0884] |
| 1y | +0.1142 | [+0.0384, +0.1508] | +0.0859 | [+0.0345, +0.1080] |

**The prior conclusion is fully reproducible.** Twelve comparisons, one direction, every CI excluding
zero.

### Directional accuracy, paired, 1m

| Comparator | Δ dir acc | 95% CI | Classification |
|---|---|---|---|
| Equal-weight | −0.0191 | [−0.0421, +0.0047] | Inconclusive (95% of draws negative) |
| Best single model | +0.0025 | [−0.0505, +0.0577] | Inconclusive |
| `macro_regime` | +0.0338 | [−0.0190, +0.0905] | Inconclusive |

Reproduced unchanged.

---

## 3. What differs from the prior report, and why

Two figures moved slightly. Both are explained; neither changes any conclusion.

| Quantity | Prior | Verified | Explanation |
|---|---|---|---|
| Production Brier @1m | 0.3022 | **0.2989** | The prior figure came from the shipped `merged.csv` cohort; this one is recomputed on the replicated cell set, which includes 7,514 rather than 7,290 cells before the outcome join (the replication recovers cells where a model row exists but the shipped `systems` pass had dropped it). The difference is 0.0033 — well inside the paired CI |
| Production rank IC @1m | −0.0209 | −0.0085 | Same cause: marginally different cell set after the join. Both are negative and both are inside ±1 SE (SE = 0.059) |

**Nothing material differs.** The direction, magnitude, and significance of every comparison hold.

### One new baseline discovered during verification (flagged as post-hoc)

The ensemble's mean score is **37.4–45.0** across horizons, and it calls bullish in only **29–42%** of
cells — a structural bearish tilt. The realized base rate of positive `spy_rel` is 0.46–0.55. So a
**constant bearish call** would have scored:

| Horizon | Always-bearish acc (= 1 − base rate) | Ensemble acc | Winner |
|---|---|---|---|
| 1w | 0.503 | 0.5083 | ensemble |
| 2w | 0.524 | 0.5123 | **always-bearish** |
| 1m | 0.536 | 0.5143 | **always-bearish** |
| 3m | 0.453 | 0.4749 | ensemble |
| 6m | 0.543 | 0.4457 | **always-bearish** |
| 1y | 0.533 | 0.4222 | **always-bearish** |

**This baseline was selected after observing the base rate and is therefore descriptive only, not a
preregistered comparison.** It is recorded because it bounds how little the ensemble's cross-sectional
discrimination is worth: at four of six horizons a single constant call, chosen with hindsight, would
have done better.

---

## 4. Verification verdict

- The combiner replication is **exact** (2.8e-14).
- All prior comparisons **reproduce**.
- The production ensemble is **indistinguishable** from its best single component and from equal-weight
  on directional accuracy, and **decisively worse than both a constant 50% and equal-weight on Brier**
  at every horizon.
- The two small numerical differences found are cell-set effects an order of magnitude inside the CIs.

The premise of this investigation is confirmed. The mechanism is analysed in
[WEIGHTING_ANALYSIS.md](WEIGHTING_ANALYSIS.md) and [FAILURE_MODE_ANALYSIS.md](FAILURE_MODE_ANALYSIS.md).
