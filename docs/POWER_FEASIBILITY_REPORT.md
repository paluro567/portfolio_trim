# Power Feasibility Report — Would Better Data Make the Question Decisive?

Preregistered precision threshold: **SE ≤ 0.02** on the primary cross-sectional IC, carried forward
from `ONEYEAR_DECOMPOSITION.md` §6.

---

## 1. A correction to the model used in all prior reviews

Every prior estimate in this project — including my own two reviews — discounted breadth by the
**equicorrelation effective-sample formula** `n_eff = n / (1 + (n−1)ρ)` and concluded that 500 names ×
20 years yields SE ≈ 0.021.

**That formula is wrong for this statistic.** It gives the effective sample size for averaging
*correlated levels*. A cross-sectional rank IC is a correlation computed **within** each date, so the
common market factor — the thing ρ measures — is **differenced out by the ranking itself**. Applying
the equicorrelation discount to an IC implies breadth saturates at `1/ρ` names (6.7 names at ρ = 0.15),
which would mean SE ≤ 0.02 is unreachable at any universe size. Running it that way reproduces exactly
that absurdity: it reports SE ≈ 0.118 at 3,000 names.

### The correct decomposition

```
Var( mean IC ) =  σ²_true / Y   +   E[ 1/(n − 3) ] / (Y · m)
                 └── regime ──┘      └──── sampling ────┘
```

- `σ_true` — across-date dispersion of the **true** date-level IC (real regime variation in the signal)
- `Y` — number of **independent time blocks** (annual, given overlapping forward windows)
- `n` — cross-sectional breadth per scoring date
- `m` — independent scoring dates per block (1 for a 1y horizon; up to 12 for 1m)

**The first term does not shrink with breadth.** It is the binding constraint, and it was absent from
every prior estimate.

---

## 2. Estimated from the current panel

### 2.1 σ_true is NOT IDENTIFIABLE from the surviving data

| Horizon | Dates | Mean breadth | Var(observed IC) | Sampling component | Implied Var(true) |
|---|---|---|---|---|---|
| 1w | 189 | 6.7 | 0.1957 | 0.2760 | **−0.0803** |
| 2w | 189 | 6.7 | 0.1787 | 0.2760 | **−0.0973** |
| 1m | 63 | 6.0 | 0.2407 | 0.3333 | **−0.0926** |
| 3m | 27 | 6.0 | 0.1673 | 0.3333 | **−0.1660** |
| 6m | 14 | 6.0 | 0.1450 | 0.3333 | **−0.1883** |
| 1y | 7 | — | *only 7 dates* | — | — |

**Every horizon yields a negative implied variance.** With 6–7 names per date, the sampling term
`1/(n−3)` is 0.25–0.33 and completely swamps any true IC variation. The observed IC dispersion is
*smaller* than pure sampling noise would predict.

**Consequence: the single parameter that determines whether any purchase can succeed is currently
unmeasured — and unmeasurable at this breadth.** Scenarios below therefore parameterize σ_true over a
declared grid rather than pretending to an estimate.

### 2.2 Current achieved standard errors (year-block bootstrap of the pooled rank IC, system A)

| Horizon | IC point | **Achieved SE** | Independent year blocks | n |
|---|---|---|---|---|
| 1w | +0.0143 | 0.0441 | 8 | 1259 |
| 2w | +0.0114 | 0.0241 | 8 | 1259 |
| 1m | −0.0209 | **0.0593** | 8 | 419 |
| 3m | −0.0052 | 0.0647 | 8 | 178 |
| 6m | −0.1067 | 0.1153 | 8 | 92 |
| 1y | −0.1931 | 0.1102 | 7 | 45 |

Current SE at the primary horizon is **~3x** the required 0.02.

### 2.3 Cross-sectional dependence (upper-bound anchor)

Mean pairwise correlation of `spy_rel` across the 7 names: 1w 0.214, 2w 0.184, 1m 0.209, 3m 0.232,
6m 0.236, 1y 0.184. These 7 names are large-cap growth/tech, so this **overstates** ρ for a
diversified 500-name universe. It is reported for completeness; per §1 it does **not** enter the IC
precision calculation.

---

## 3. Scenario analysis

Rows marked **✓** meet SE ≤ 0.02.

| Scenario | σ=0.05 | σ=0.10 | σ=0.15 | σ=0.20 |
|---|---|---|---|---|
| **S1** current: 7 names, 8 yrs | 0.1777 | 0.1803 | 0.1846 | 0.1904 |
| **S1b** current 31-name panel, 14 yrs | 0.0522 | 0.0571 | 0.0645 | 0.0735 |
| **S2** 500 names, 20 yrs | **0.0150 ✓** | 0.0245 | 0.0350 | 0.0458 |
| **S3** conservative: 500 nm, 20 yrs, 60% kept | **0.0171 ✓** | 0.0259 | 0.0360 | 0.0466 |
| **S4a** 1500 names, 20 yrs (80% kept) | **0.0129 ✓** | 0.0233 | 0.0342 | 0.0452 |
| **S4b** 500 names, **25** yrs | **0.0134 ✓** | 0.0219 | 0.0313 | 0.0410 |
| **S4c** 3000 names, 25 yrs (70% kept) | **0.0109 ✓** | 0.0205 | 0.0303 | 0.0402 |
| **S5** 500 nm, 20 yrs, 1m horizon (m=12) | **0.0115 ✓** | 0.0225 | 0.0337 | 0.0448 |

MDE at 80% power = 2.486 × SE; at 90% = 3.242 × SE. Example, S2 at σ = 0.15: SE 0.0350 →
**MDE(80%) = 0.087**. A real IC of 0.03–0.05 would be undetectable.

### 3.1 Breadth saturates — the central finding

At Y = 20:

| Names | SE (σ=0.10) | SE (σ=0.15) |
|---|---|---|
| 50 | 0.0395 | 0.0468 |
| 100 | 0.0319 | 0.0405 |
| 200 | 0.0275 | 0.0371 |
| **500** | **0.0245** | **0.0350** |
| 1000 | 0.0235 | 0.0343 |
| 2000 | 0.0229 | 0.0339 |
| 5000 | 0.0226 | 0.0337 |

**Going from 500 to 5,000 names — a 10x larger dataset — improves SE by 7.8%.** Breadth is
effectively exhausted by a few hundred names. The floor is `σ_true/√Y`, and no amount of breadth
crosses it.

### 3.2 The floor set by years alone (infinite breadth)

| σ_true | Y=10 | Y=15 | Y=20 | Y=25 | Y=30 | Y=40 | Y=60 |
|---|---|---|---|---|---|---|---|
| 0.05 | 0.0158 | 0.0129 | 0.0112 | 0.0100 | 0.0091 | 0.0079 | 0.0065 |
| 0.10 | 0.0316 | 0.0258 | **0.0224** | 0.0200 | 0.0183 | 0.0158 | 0.0129 |
| 0.15 | 0.0474 | 0.0387 | **0.0335** | 0.0300 | 0.0274 | 0.0237 | 0.0194 |
| 0.20 | 0.0632 | 0.0516 | 0.0447 | 0.0400 | 0.0365 | 0.0316 | 0.0258 |

### 3.3 Scenario 4 — the minimum dataset that reaches the threshold

| σ_true | Y=15 | Y=20 | Y=25 |
|---|---|---|---|
| 0.05 | 290 names | **185 names** | 140 names |
| 0.10 | **UNREACHABLE** | **UNREACHABLE** | ~marginal (floor 0.0200) |
| 0.15 | **UNREACHABLE** | **UNREACHABLE** | **UNREACHABLE** |
| 0.20 | **UNREACHABLE** | **UNREACHABLE** | **UNREACHABLE** |

"Unreachable" means the year-floor `σ_true/√Y` already exceeds 0.02 — **no universe size, at any
price, reaches the preregistered threshold.** At σ = 0.15 even a relaxed SE ≤ 0.03 target is
unreachable below Y = 25.

---

## 4. Explicit sensitivity tests

| Stress | Effect | Magnitude |
|---|---|---|
| **Higher cross-sectional correlation** | **None on IC precision** — differenced out by within-date ranking (§1). This overturns the premise of all prior estimates | 0% |
| **Fewer independent regimes** (Y: 20→15) | Raises the floor by 15% (σ=0.10: 0.0224 → 0.0258). **The dominant lever** | High |
| **Feature-data attrition** (60% kept) | S2 → S3 at σ=0.10: 0.0245 → 0.0259 | +5.7% |
| **Uneven history across securities** | Reduces effective Y for young names; equivalent to a lower Y. Directionally the same as the Y stress | Moderate |
| **Delisted-security coverage** | Affects **bias**, not variance. Does not change any SE above — it changes whether the estimate is *centred correctly* | 0% on SE |
| **Sector concentration** | Reduces effective breadth; per §3.1 breadth is already saturated, so the impact is small | Low |
| **σ_true (unmeasured)** | S2 spans 0.0150 → 0.0458 across the plausible grid — **a 3x swing, and the decision boundary sits inside it** | **Dominant** |

**Ranked:** σ_true (unmeasured) ≫ independent years ≫ attrition > sector concentration > ρ (zero).

---

## 5. Would a Norgate-level dataset move the project from inconclusive to decisive?

# **UNCLEAR**

Not "probably", not "probably not". The honest answer is that **it depends on one parameter that has
never been measured, and across that parameter's plausible range the answer flips completely.**

Numerically:

| σ_true | 500 names × 20y | Verdict |
|---|---|---|
| 0.05 | SE 0.0150 | **Decisive.** MDE(80%) = 0.037 |
| 0.10 | SE 0.0245 | **Marginal.** Misses 0.02; MDE(80%) = 0.061 — cannot detect an IC of 0.03–0.05 |
| 0.15 | SE 0.0350 | **Not decisive.** MDE(80%) = 0.087. Unreachable at any breadth |
| 0.20 | SE 0.0458 | **Not decisive at any price** |

Published monthly cross-sectional ICs for real equity signals typically show a time-series SD of
roughly 0.08–0.15. **If that range holds here, the purchase does NOT reach the preregistered
threshold — at any universe size.** That is the opposite of what my two prior reviews concluded, and
the reversal comes entirely from correcting the variance model in §1.

### What this does *not* say

- It does **not** say the data is worthless. Survivorship-clean data fixes **bias**, and bias is
  invisible to every SE above. A biased estimate with a tight CI is worse than an honest wide one.
- It does **not** say the project should stop. It says **the purchase is not yet justified, because a
  cheaper measurement determines whether the purchase can work at all.**

### 5.1 The parameter is measurable for free — and this is the decisive insight

σ_true requires **breadth**, not **cleanliness**. Survivorship bias distorts the *level* of the IC; it
has far less effect on the *cross-date dispersion* of the IC. Therefore:

> **A free, survivor-biased, ~500-name panel built from yfinance is sufficient to identify σ_true to
> within a useful band — and σ_true determines whether any purchase can ever reach the threshold.**

This is the first experiment that should run. It costs $0, needs no vendor, no VM, and no new
architecture, and it converts the central investment question from a judgment into an arithmetic
check. It also happens to be the one experiment neither this project nor either of my prior reviews
proposed.

**Caveat, stated plainly:** survivorship inflates realized dispersion somewhat (survivors' returns
are more extreme in the up direction), so a survivor-panel estimate of σ_true is likely an **upper
bound**. An upper bound is exactly what is needed: if even the *pessimistic* σ_true clears the
threshold, the purchase is justified; if the *optimistic* end fails, it is not.
