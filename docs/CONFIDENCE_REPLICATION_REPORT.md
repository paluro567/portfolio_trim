# Confidence Replication Report

**Question:** is the previously reported confidence inversion reproducible? **No redesign attempted.**
Criteria frozen in [EXPERIMENT_PREREGISTRATION.md](EXPERIMENT_PREREGISTRATION.md) §9.

Measure under test: production `combined_confidence` (system A). Target: `spy_rel` (system-independent).
Non-overlapping cohort. Block bootstrap by symbol, 1000 draws.

---

## 1. Primary result — top-minus-bottom confidence quartile, directional accuracy

| Horizon | n | Top − bottom quartile acc | 95% CI | Spearman(conf, hit) | Monotone? |
|---|---|---|---|---|---|
| 1w | 1259 | +0.0063 | [−0.0793, +0.0860] | +0.017 | No |
| 2w | 1259 | +0.0032 | [−0.0777, +0.0835] | +0.007 | No |
| **1m (primary)** | **419** | **+0.0667** | **[−0.0628, +0.2029]** | **+0.036** | **No** |
| 3m | 178 | −0.0889 | [−0.2756, +0.1078] | −0.039 | Decreasing |
| 6m | 92 | +0.0435 | [−0.1316, +0.2191] | −0.067 | No |
| 1y | 45 | −0.1288 | [−0.4444, +0.2000] | −0.065 | No |

## 2. Classification: **INCONCLUSIVE**

Against the frozen criteria, at the primary horizon:

- **Not a reproducible inversion.** That required a point estimate < 0 **and** CI upper bound < 0.
  The point estimate is **positive** (+0.0667) and the CI spans +0.20.
- **Not flat/uninformative.** That required the CI inside ±0.02. It is ±0.13 wide.
- **Not meaningful positive calibration.** That required CI lower bound > +0.02 and monotonicity.
  Neither holds.
- **Inconclusive:** CI includes 0 and extends far beyond ±0.02. ✔

**The previously reported inversion does not replicate.** The sign is unstable across horizons
(+, +, +, −, +, −), Spearman(confidence, hit) is ≈ 0 everywhere (max |0.067|), and no horizon shows
monotone ordering across quartiles.

**This is a non-replication, not a refutation.** The original inversion (CPE: high-conf 0.529 <
low-conf 0.584) was measured on a *different* confidence measure, a *different* 31-symbol panel, and
a *different* target. The present test cannot overturn it; it can only report that the production
ensemble's own confidence shows no reproducible ordering on the panel that survives.

---

## 3. Alternative confidence measures

| Horizon | `confidence` | `\|score − 50\|` | `n_eff` | participating models |
|---|---|---|---|---|
| 1w | +0.006 | −0.013 | +0.048 | +0.019 |
| 2w | +0.003 | −0.044 | +0.032 | +0.054 |
| 1m | +0.067 | +0.010 | +0.076 | **+0.105** |
| 3m | −0.089 | +0.133 | −0.089 | −0.156 |
| 6m | +0.043 | −0.174 | −0.174 | −0.044 |
| 1y | −0.129 | **−0.477** | +0.129 | −0.038 |

**Not one measure clears its CI at any horizon**, with a single exception: `|score − 50|` at 1y,
−0.4773, CI [−0.8182, −0.1442].

**That exception is discarded, and here is why:** it is 1 significant cell out of **24** exploratory
cells tested (4 measures × 6 horizons), on **n = 45** — precisely the hit rate chance produces at
α = 0.05 over 24 tests. It was not preregistered as confirmatory. Reporting it as a finding would be
the exact error this framework exists to prevent.

**`participating` (a raw count of non-neutral models) is the best-ordering measure at 1m (+0.105)** —
better than the engineered `confidence` (+0.067). Not significant, but worth recording: the elaborate
volume × agreement construct does not beat counting.

## 4. Year-by-year and leave-one-era-out

Both were computed. Neither produced a stable ordering: the per-year top-minus-bottom gap changes sign
repeatedly, and leave-one-year-out never moves the pooled estimate outside its CI. With ~50 cells per
year at 1m, these strata cannot resolve a 2 pp effect. **No stable era-specific pattern exists to
report.**

---

## 5. Is this question logically separable from base predictive skill?

**Partially — and the data now lets me be precise about which part.** Two distinct properties were
conflated in prior discussion, including in my own prior review:

### 5.1 Confidence ORDERING — **not separable, and not resolvable here**

Does higher stated confidence identify the more accurate calls? If base accuracy is ≈ 0.50 everywhere
— and it is (0.508–0.513 at short horizons, *below* 0.50 at 3m/6m/1y) — then a flat confidence
profile is the **correct** behaviour of a confidence measure over a skill-free predictor. There is
nothing to order.

Per the preregistered logic, only a *consistent inversion* would be diagnosable without base skill,
because pure noise over pure noise yields no stable ordering. **No consistent inversion was found.**
Therefore the ordering question **collapses into the base-skill question** and cannot be advanced
independently. **Independent confidence-calibration work is not justified by this evidence.**

### 5.2 Score MAGNITUDE calibration — **fully separable, and decisively broken**

This is a different property, and it *is* answerable without any signal: is `p_up` an honest
probability? A predictor with no skill should emit 0.50. This ensemble does not.

From [PAIRED_BASELINE_RESULTS.md](PAIRED_BASELINE_RESULTS.md) §4:

| Horizon | Ensemble Brier | Always-neutral Brier | Δ | 95% CI |
|---|---|---|---|---|
| 1w | 0.3144 | 0.2500 | +0.0642 | [+0.0493, +0.0778] |
| 1m | 0.3022 | 0.2500 | +0.0519 | [+0.0306, +0.0738] |
| 1y | 0.3693 | 0.2500 | +0.1142 | [+0.0384, +0.1508] |

**Six horizons, every CI excluding zero: the ensemble is systematically overconfident.** It pushes
scores away from 50 while having no directional skill, and every unit of that displacement is a pure
Brier loss. Equal-weight averaging (which shrinks toward 50) scores 0.2583 at 1m and beats it at every
horizon, also with CIs excluding zero.

This independently reproduces the analogue RCA's **RC1** ("the `se` recipe overstates precision ~2x")
and shows it is **not** an analogue-specific bug — it is a property of the production
correlated-fixed-effect combination path.

### 5.3 Consequence for the report layer

The ordering result is inconclusive, so no claim can be made that high-confidence outputs are more or
less reliable than low-confidence ones. The **magnitude** result is decisive and independent of
signal: the numbers shown to a user overstate certainty, at every horizon, with CIs excluding zero.

**A user reading a score of 70 is being told something the evidence does not support.** That is
actionable now, does not depend on resolving base skill, and does not require any purchase.
