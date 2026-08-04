# V6 ARM 1.5 — COMBINER-LEVEL INJECTION · RESULTS

**Executed exactly as preregistered in `V6_ARM1_SCIENTIFIC_REVIEW.md` Part 5.**
No endpoint, hypothesis, or criterion was altered. Runtime 24.2 s. Commit `1b2aec9f935a`.

---

## PART 1 — Prerequisites verified

| Required artifact | Status |
|---|---|
| Per-model outputs | ✅ **54,522 rows**, 7 official models |
| Combiner inputs (`score`, `confidence`, `neutral`, `excess`, `expected`, `z_raw`, `n_eff`) | ✅ all present |
| Recovered effect values | ✅ 36,926 non-neutral, range [−1.14, +1.99] |
| Recovered z statistics | ✅ range [−33.6, +8.06] |
| Recovered SE = \|effect/z\| | ✅ range [2.0e-03, 1.85], **0 non-positive** |
| Recovered weights `1/se²` | ✅ all finite |
| Recovered confidence | ✅ range [0.013, 0.910] |
| Score-generation input | ✅ **`score = 100·Φ(clip(z_raw))` exactly — max err 0.000e+00** |
| Combiner runs independently of feature generation | ✅ verified: consumes only the fields above; no feature-store or price access |

**No prerequisite missing. No simulated data substituted.**

## STOPPING RULES — both checked before analysis

| Rule | Result |
|---|---|
| Combiner replication must not drift from 2.84e-14 | **max \|replicated − `combine_rows`\| = 1.42e-14** over 250 cells → **OK** |
| False-positive rate at ρ = 0.00 must not exceed 0.10 | **0/6 horizons** show a LOSS CI excluding zero → **FP = 0.000** → **harness valid** |

## PART 2 — Injection as executed

```
effect_m,i(ρ) = effect_m,i + κ_m · ρ · Φ⁻¹(rank(y_i))
z_raw_m,i(ρ)  = effect_m,i(ρ) / se_m,i          ← se HELD AT ORIGINAL RECOVERED VALUE
score_m,i(ρ)  = 100 · Φ(clip(z_raw_m,i(ρ)))     ← the verified production mapping
```

- **`se` preserved.** Recomputing it would re-derive `se ≡ |effect/z|` and circularly erase the defect under test.
- **Outcomes preserved.** `spy_rel` is read-only throughout.
- **Feature layer untouched.** Injection enters only at the per-model evidence stream.
- **κ_m** = each model's own effect dispersion, computed within horizon so no model is privileged.
- ρ ∈ {0.00, 0.03, 0.05, 0.07, 0.10, 0.15, 0.20}. Cohort non-overlap identical to Arm 1.

## PART 3 — Information loss

`LOSS(ρ) = IC(equal-weight consensus of injected model scores) − IC(combined score)`
Block bootstrap: 1,000 draws, block = 4, per-symbol circular, seed 20260801.

### At the primary ρ = 0.10

| Horizon | n | IC consensus | IC combined | **LOSS** | 95% CI |
|---|---|---|---|---|---|
| 1w | 1,259 | +0.2626 | +0.2841 | **−0.0216** | [−0.0402, −0.0016] |
| 2w | 1,259 | +0.2524 | +0.2541 | **−0.0017** | [−0.0138, +0.0110] |
| 1m | 419 | +0.2222 | +0.2061 | **+0.0161** | [−0.0104, +0.0433] |
| 3m | 178 | +0.1661 | +0.1647 | **+0.0014** | [−0.0193, +0.0282] |
| 6m | 92 | +0.0670 | +0.0889 | **−0.0219** | [−0.0698, +0.0308] |
| 1y | 45 | +0.1505 | +0.1167 | **+0.0337** | [−0.0617, +0.1110] |

**A negative LOSS means the combiner *outperformed* the equal-weight consensus.**

### Stability across ρ

| Horizon | LOSS @ ρ=0 | LOSS @ ρ=0.20 | slope per unit ρ |
|---|---|---|---|
| 1w | −0.0152 | −0.0214 | −0.031 |
| 2w | +0.0015 | −0.0044 | −0.036 |
| 1m | +0.0218 | +0.0084 | −0.071 |
| 3m | −0.0069 | +0.0072 | +0.078 |
| 6m | −0.0088 | +0.0038 | +0.099 |
| 1y | +0.0399 | +0.0855 | +0.202 |

**LOSS does not grow proportionally with injected signal at any horizon.** Slopes are small and of
mixed sign; at 1w, 2w and 1m the loss *decreases* as more signal is injected. **The combiner does not
scale its destruction with the amount of signal present.**

## PART 4 — PRIMARY DECISION

Frozen rule applied mechanically. **PASS** if CI upper < 0.02 · **FAIL** if CI lower > 0.02 · else
**INCONCLUSIVE**.

| Horizon | LOSS | CI | **Verdict** |
|---|---|---|---|
| 1w | −0.0216 | [−0.0402, −0.0016] | **PASS** |
| 2w | −0.0017 | [−0.0138, +0.0110] | **PASS** |
| 1m | +0.0161 | [−0.0104, +0.0433] | INCONCLUSIVE |
| 3m | +0.0014 | [−0.0193, +0.0282] | INCONCLUSIVE |
| 6m | −0.0219 | [−0.0698, +0.0308] | INCONCLUSIVE |
| 1y | +0.0337 | [−0.0617, +0.1110] | INCONCLUSIVE |

# PASS = 2 · INCONCLUSIVE = 4 · **FAIL = 0**

**No horizon triggers FAIL. The preregistered failure condition — LOSS CI lower bound > 0.02 — is not
met anywhere, including at every ρ tested, not only the primary.**

### Preregistration gap — recorded, not resolved post hoc

The preregistration names **one** primary endpoint ("LOSS at ρ = 0.10") but the experiment yields
**six**, one per horizon, and **no pooling rule was preregistered.** The rule is therefore applied
mechanically at each horizon and reported as a distribution. **No pooled verdict is claimed and no
horizon was selected after seeing results.**

### Secondary PASS/FAIL component

The preregistration's PASS also requires combined-score MDE ≤ 1.25 × Arm 1's score-level MDE, and FAIL
triggers above 2×. Measured ratios: **0.30, 0.30, 0.47, 0.40, 0.50, 0.50** — below 1.25 everywhere and
nowhere near the 2× failure trigger.

> **Comparability caveat, stated plainly:** Arm 1's MDE is an 80%-power Monte-Carlo threshold; Arm 1.5's
> injection is deterministic, so its threshold is a **single-realisation** detection point. A
> single-realisation threshold is naturally lower than an 80%-power one. **The ratios establish that the
> failure trigger is not met; they do not establish that the combiner improves detection.**

## PART 5 — Diagnostics

The trigger condition ("if LOSS exceeds expectations") **was not met**. Diagnostics are reported anyway
because they localise where loss could originate. Full detail in `V6_ARM15_DIAGNOSTICS.md`.

**The decisive diagnostic: weights are exactly invariant under injection.**

| Horizon | mean HHI ρ=0 → ρ=0.20 | effective models |
|---|---|---|
| 1w | 0.2754 → 0.2754 | 3.75 → 3.75 |
| 2w | 0.2605 → 0.2605 | 3.95 → 3.95 |
| 1m | 0.2497 → 0.2497 | 4.13 → 4.13 |
| 3m | 0.2376 → 0.2376 | 4.36 → 4.36 |
| 6m | 0.2454 → 0.2454 | 4.27 → 4.27 |
| 1y | 0.2690 → 0.2690 | 4.13 → 4.13 |

Identical to four decimal places. This is the direct arithmetic consequence of the preregistered
decision to hold `se` fixed: weights are `1/se²`, so they **cannot** move. **Therefore no part of the
measured LOSS originates in weight reallocation.**

**Injected models are not down-weighted.** Spearman(κ_m, mean weight) = **+0.314** across 6 models —
weakly *positive* and, at n = 6, not distinguishable from zero.

## PART 7 — Program update

### 1 · Did the combiner materially destroy information?

**No.** Across 42 measured cells (6 horizons × 7 ρ values), **the preregistered failure condition was
never met**. At the primary ρ = 0.10 the largest positive LOSS is +0.0337 (1y, n = 45) with a CI
spanning [−0.0617, +0.1110]. At the two best-powered horizons the LOSS is **negative** — the combiner
outperformed equal-weight consensus, significantly so at 1w (CI entirely below zero).

### 2 · Is the measured loss statistically distinguishable from zero?

**At only one of six horizons, and in the direction opposite to destruction.**

- **1w:** LOSS = −0.0216, CI [−0.0402, −0.0016] — **excludes zero on the negative side.** The combiner *added* information.
- **All other horizons:** CI includes zero.

**No horizon shows a positive loss distinguishable from zero.**

### 3 · Is Arm 2 still required?

**Yes — and its interpretation is now sharper.** Arm 1.5 measured only the model-output → combiner →
score segment. The feature → model segment is untouched. Since the aggregation term is now measured at
approximately zero, **any information loss Arm 2 subsequently finds is attributable to the
feature→model layer** rather than being an ambiguous sum. Arm 1.5 has decomposed Arm 2 in advance,
which was its stated purpose.

### 4 · Does this strengthen or weaken the case that feature generation is now the dominant uncertainty?

**Strengthens it, by elimination.** Arm 1 cleared the validation layer (unbiased, efficient to within
2.3% of `1/√n`). Arm 1.5 now clears the aggregation layer at the two best-powered horizons and finds
no distinguishable destruction anywhere. **Two of the three downstream segments have been measured and
neither destroys signal.** The feature→model segment is the only one never tested.

**Bounded by the evidence:** four horizons returned INCONCLUSIVE, all with n ≤ 419. This is an
elimination argument resting on two well-powered horizons, not on six.

### 5 · Single highest-value remaining experiment

**Arm 2 — feature-level injection through the full model pipeline.**

It is now the only experiment that addresses the last untested segment, and Arm 1.5 has made its result
interpretable rather than ambiguous. It remains blocked on research-data restoration.
