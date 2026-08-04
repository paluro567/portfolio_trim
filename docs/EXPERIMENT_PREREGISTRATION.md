# Preregistration — Paired Baseline Comparison, Power Feasibility, Confidence Replication

**Frozen:** 2026-07-29, **before** any comparative result was computed. The Part 1 audit (dataset
inventory and blocking flaws) was completed first, because it determines which systems are
constructible at all. No success criterion below may be altered after results are viewed.

---

## 0. Audit-driven scope restriction (read first)

Two blocking flaws were found during Part 1. They restrict — but do not eliminate — what can be
preregistered. Full detail in [PAIRED_BASELINE_RESULTS.md](PAIRED_BASELINE_RESULTS.md) §1.

**F1 — The production database has been destroyed.** `mip`, `mip_scratch` retain only an *empty*
`alembic_version` table; `mip_test` has zero tables. No `daily_prices`, `instruments`,
`feature_store_daily`, `predictions`, `security_master`, or Phase 2A tables exist.

*Consequences for this preregistration:*
- A true **12-1 cross-sectional momentum** baseline is **NOT constructible** (needs price history).
  Substituted by system **F** below, with the substitution declared here rather than discovered later.
- Broad-panel cross-sectional correlation cannot be measured; Part 4 parameterizes ρ instead of
  estimating it from a wide panel.
- The 31-symbol `conditional_v1` capture cannot be given outcomes (outcomes are computed from prices).
- **Sector** stability analysis is **not executable** (the sector map lived in the DB).

**F2 — The shipped harness's target is system-dependent.** `mip/validation/metrics.py::prepare()`
computes `realized_excess = actual − (expected_return − expected_excess)`, i.e. each system is scored
against **its own model-implied baseline**, and `hit` is derived from it. Two consequences:
1. A paired `hit` difference between two systems compares performance against **two different
   targets** — not a valid paired comparison.
2. It is the same target mis-specification `ONEYEAR_DECOMPOSITION.md` §2 identified as inflating the
   withdrawn +0.17 headline (+0.17 vs +0.01–0.09 on clean targets).

*Consequence:* `realized_excess` and the shipped `hit` are **excluded from all primary and secondary
metrics** below. They are reported once, as a diagnostic, to quantify the distortion.

**Executable data (the only panel with both per-model scores and realized outcomes):**
`data/validation/analogue_v1/embargoed_revalidation/` — 7 symbols (ADBE, AMD, AMZN, CRM, HNST, NOW,
TSLA), 189 scoring dates 2019-01-02 → 2026-06-26, 6 horizons, 7,290 complete cells per system,
per-model captures for all 7 official models, and the embargo-hardened (leakage-free) grid.

---

## 1. Primary question

> Does the current production ensemble provide **incremental** predictive value over substantially
> simpler alternatives, evaluated on **identical** symbol-date-horizon cells?

---

## 2. Candidate systems

All reconstructed through the **production** combination path
(`mip.engine.evidence.combine_model_evidence` + `mip.engine.trim.assess_trim`) via the shipped
`mip.validation.systems.combine_rows`. No combiner is reimplemented.

| ID | System | Construction | Constructible? |
|---|---|---|---|
| **A** | **Production ensemble** | The 7 official models (`earnings_behavior`, `interest_rate_sensitivity`, `macro_regime`, `momentum_exhaustion`, `relative_strength`, `sector_rotation`, `valuation`). Matches production exactly: `SHADOW_MODELS = {historical_analogues, conditional_probability}` are excluded | **Yes** |
| **B** | **Always-neutral** | `evidence_score ≡ 50.0` on every cell | **Yes** (with a stated limitation, §4) |
| **C** | **12-1 cross-sectional momentum** | ~~Prior 12-month return skipping the most recent month, cross-sectionally ranked~~ | **NO — blocked by F1** |
| **D** | **Strongest individual production model** | Each of the 7 official models alone, through the same combiner. The "strongest" is designated by holdout rank-IC at 1m **and this designation is itself a post-hoc selection** — see §7 | **Yes** |
| **E** | **Equal-weight combination** | Arithmetic mean of the 7 official model scores, bypassing the correlated fixed-effect weighting. Isolates *production weighting* from *model content* | **Yes** |
| **F** | **`momentum_exhaustion` alone** | The project's already-implemented price-momentum model, standing in for C. **Declared substitution.** It is *not* 12-1 momentum: it is an own-price momentum/technical/volatility model. Its role is "the simplest already-implemented price-only system" | **Yes** |

**Systems C's absence is a material limitation, not a technicality.** F is a weaker comparator than C
would have been, because F was built and tuned inside this project while C is a literature-standard
external null. This is recorded as a known weakness of the present study.

---

## 3. Targets (system-independent, by construction)

| ID | Target | Definition | Role |
|---|---|---|---|
| **T1** | **Benchmark-relative forward return** | `spy_rel` — the cell's forward return minus SPY's over the identical window | **PRIMARY.** It is the selection question and is identical across systems |
| **T2** | Absolute forward return | `actual` | Secondary |
| **T3** | *Model-implied excess* | `realized_excess` | **EXCLUDED from inference** (F2). Reported once as a diagnostic |

---

## 4. Metrics

**Primary metric:** paired difference in **directional accuracy against T1**, where a system's
directional call is `evidence_score > 50` predicting `spy_rel > 0`.

**Secondary metrics:**
1. **Rank IC** — Spearman(evidence_score, spy_rel). Reported both pooled and within-date. *With 7
   symbols per date, within-date IC is extremely thin; pooled is the operative figure and its
   time-series/cross-section confound is acknowledged.*
2. **Brier score** on `p_up = evidence_score/100` against `1[spy_rel > 0]`.
3. **Top-minus-bottom tercile spread** in mean `spy_rel`. Terciles (not deciles) because 7 symbols per
   date cannot support 10 buckets.
4. **High-conviction hit rate** — directional accuracy in the top confidence quartile.

**Excluded metrics and why:**
- **Turnover-adjusted portfolio outcomes:** excluded. The portfolio simulation is **not trustworthy**
  on this panel — `PortfolioAnalyzer` requires ≥60 common sessions for joint returns, the real
  portfolio's risk decomposition is `None` platform-wide, and the DB holding the ledger is destroyed
  (F1). Preregistered as **not evaluated**, not as "evaluated and null."
- **Sector stability:** excluded — F1 destroyed the sector map.

---

## 5. Evaluation horizons

**Primary horizon: 1m**, designated in advance because it is the production focus horizon
(`ReportOptions.focus_horizon = "1m"`). Horizons 1w, 2w, 3m, 6m, 1y are **secondary and
exploratory**; no significance is claimed for them and they are not used to select the headline
result.

---

## 6. Minimum economically meaningful difference (MEMD)

Declared before results:

| Metric | MEMD | Justification |
|---|---|---|
| Directional accuracy | **±0.02** (2 pp) | The project's own RS-retirement study treated +0.013 as "small but directionally consistent"; a hold/trim decision changing on less than 2 pp of accuracy is not actionable against decision friction |
| Rank IC | **±0.02** | Below the 0.03–0.05 band the project identifies as the size of real equity-selection signals |

MEMD enables **equivalence** conclusions, so that an insignificant result is not misread as proof of
equality (§8).

---

## 7. Statistical procedure

- **Pairing:** inner join on `(symbol, as_of, horizon)`. Only cells present in **both** systems enter.
- **Non-overlap:** the shipped `metrics.cohort()` stride (`ceil(horizon_sessions / 10)`) so
  consecutive forward windows within a symbol do not overlap.
- **Resampling:** the shipped `metrics.block_bootstrap_delta` — circular block bootstrap (block = 4,
  1000 draws, seed 7) over **per-symbol cohort series of the paired difference**. Additionally a
  **year-block** bootstrap, resampling whole calendar years, to absorb common market regimes.
  Rows are never treated as independent.
- **Reported interval:** 95% percentile CI of the paired difference. A p-value is reported only as the
  bootstrap two-sided share crossing zero; no parametric test is claimed.
- **Multiple comparisons:** the confirmatory family is **4 comparisons** — A vs each of B, D, E, F at
  the 1m horizon on T1. **Holm-Bonferroni** within that family. All other cells (other horizons, T2,
  secondary metrics) are exploratory and labelled as such.
- **Designation of D:** choosing the "strongest" single model by holdout performance is a **post-hoc
  selection over 7 candidates** and biases D *upward* as a comparator — i.e. it makes A's job
  *harder*, which is conservative for A's claim. Declared here; per-model results reported for all 7
  so the selection is auditable.
- **Missing-data policy:** a cell enters a system only if every model that system requires produced a
  row. Neutral rows are retained (neutrality is a legitimate model output the combiner handles).
  Attrition reported at each step. **Sensitivity:** the primary comparison is re-run under
  (i) complete-cases-across-all-systems and (ii) per-pair inner join, and both reported.
- **Tie-breaking:** `evidence_score` exactly 50.0 → no directional call → excluded from directional
  accuracy. **Consequence, stated in advance:** system B (always-neutral) is *by construction*
  excluded from the directional-accuracy metric and its rank IC is undefined (zero variance). B is
  therefore evaluated **only** on Brier score, where it is the exact uninformed reference. This is a
  property of the comparator, not a result.
- **Outlier sensitivity:** primary comparison re-run with `spy_rel` winsorized at 1%/99%.

---

## 8. Decision criteria (frozen)

Applied to the primary metric, primary horizon, primary target, post-Holm:

| Classification | Criterion |
|---|---|
| **Ensemble clearly superior** | Paired Δ CI **lower** bound > **+0.02** |
| **Baseline clearly superior** | Paired Δ CI **upper** bound < **−0.02** |
| **Practically equivalent** | CI contained **entirely within** [−0.02, +0.02] |
| **Inconclusive** | CI includes 0 **and** extends beyond ±0.02 |

Failure criteria for the ensemble: any comparator achieving "baseline clearly superior."
Success criteria for the ensemble: "clearly superior" against **all four** comparators.

---

## 9. Confidence replication (Part 5) — frozen separately

**Question:** is the previously observed confidence inversion reproducible? **No redesign is
attempted.**

- **Measure under test:** `combined_confidence` from system A.
- **Alternatives compared:** (i) `|evidence_score − 50|` (distance from neutral), (ii) model
  agreement proxy = count of participating non-neutral models, (iii) `n_eff`. *Historical empirical
  reliability is NOT tested* — it cannot be computed out-of-sample on this panel without a
  fitting stage the panel is too small to support honestly.
- **Tests:** quartile bins; Spearman(confidence, hit) monotonicity; reliability curve;
  block-bootstrap CI on the top-minus-bottom-quartile accuracy difference; per-year; leave-one-era-out.
- **Classification (frozen):**

| Classification | Criterion (top-quartile minus bottom-quartile accuracy, on T1) |
|---|---|
| **Reproducible inversion** | Point estimate < 0 **and** CI upper bound < 0 |
| **Meaningful positive calibration** | CI lower bound > +0.02 **and** monotone across bins |
| **Weak positive ordering** | Point > 0 but CI includes 0 |
| **Flat / uninformative** | CI contained within ±0.02 |
| **Inconclusive** | CI includes 0 and spans beyond ±0.02 |

**Logical separability (declared before results):** confidence calibration is **partially** separable
from base skill. If base accuracy ≈ 0.50 everywhere, a *flat* confidence profile is the **correct**
behaviour of a confidence measure over a skill-free predictor and carries no information about the
confidence construct. Only a **consistent inversion** is diagnosable without base skill, because
pure noise over pure noise yields no stable ordering. Therefore: *inversion* → an independent defect;
*flat* → the question collapses into base skill and independent calibration work is unjustified.

---

## 10. Power feasibility (Part 4) — frozen precision threshold

**Preregistered precision threshold:** **SE ≤ 0.02** on the primary cross-sectional IC — carried
forward from `ONEYEAR_DECOMPOSITION.md` §6 ("needs SE ≈ 0.02, i.e. effective N ≈ 2,000+").

Scenarios 1–4 as specified in the task. Because F1 prevents measuring ρ on a broad panel, ρ is
**parameterized over a declared grid** and the 7-symbol panel provides only an upper-bound anchor
(7 correlated large-cap growth names overstate ρ for a diversified 500-name universe, so the
resulting power estimate is **conservative**). Every reported figure carries its assumption.

---

## 11. What this study cannot answer (declared in advance)

- Whether the ensemble beats a **literature-standard external** baseline (12-1 momentum) — blocked
  by F1.
- Whether **any** system has an absolute edge above zero — a paired design compares systems and
  cannot establish either exceeds zero.
- Anything about **sector** stability — blocked by F1.
- Anything about **survivorship** — all 7 symbols are survivors; 6 of 7 are large-cap tech/growth.
- Whether results generalize beyond 7 symbols. **They almost certainly do not.** This panel is
  narrower than the 31-symbol panel that already produced "inconclusive," so a null result here
  carries *less* weight than the existing nulls, while a *clear* result would carry real weight.
