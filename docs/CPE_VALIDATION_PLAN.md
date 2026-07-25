# Conditional Probability Engine — Validation Pre-Registration (FROZEN)

**Status:** FROZEN on 2026-07-22, BEFORE any validation result was observed. No
directional-accuracy, calibration, or confidence metric has been computed for
the CPE at the time of writing (only functional smoke tests confirming the
engine runs and routes to shadow). Changes after this point are amendments,
logged with reason, not silent edits.

**Purpose.** Determine whether the Conditional Probability Engine (CPE,
`conditional_probability` v1, template set `cpe-v1`) provides *incremental,
out-of-sample, point-in-time-honest predictive information* about a holding's
forward returns **beyond the existing seven-model system** — or whether it does
not, in which case it remains shadow (or is rejected/revised). This is a
falsification exercise, not an optimization. Per the platform's promotion
discipline (`docs/VALIDATION_GATES.md`), the default disposition of a model that
fails any gate is shadow or rejection, never partial credit.

**Non-goals (declared).** No optimization, no threshold tuning, no metric
improvement, no implementation changes driven by results. Constants are frozen
(§9). The analysis is run once against the criteria below; iterating on the
holdout to obtain a better number invalidates the run.

---

## 1. Hypotheses

**H1 (primary, predictive incremental value).** Combining the CPE with the seven
official models (via the existing correlated fixed-effect decision engine, CPE
promoted out of shadow) yields a *strictly better* out-of-sample forward-return
prediction than the seven-model baseline at the primary horizon (1 month),
measured by signed prediction–realized correlation and directional accuracy,
with a 95% block-bootstrap confidence interval for (combined − baseline) whose
lower bound exceeds 0.

**H1a (standalone signal).** The CPE's standalone directional accuracy exceeds
the naive baselines (50% for absolute direction; the unconditional base rate for
beat-SPY) at the primary horizon, out-of-sample, above the minimum effective
sample floor (§5).

**H1b (calibration).** The CPE's stated probabilities (P(positive), P(beat SPY))
are calibrated: expected calibration error (ECE) ≤ 0.10 over 5 equal-count bins
on the holdout, with reliability-curve slope in [0.7, 1.3].

**H1c (confidence discrimination).** Higher-confidence CPE predictions are more
accurate than lower-confidence ones: top-tercile minus bottom-tercile directional
accuracy > 0 with a 95% block-bootstrap CI excluding 0, and the relationship is
**not inverted** (the specific failure mode of analogue v1).

**H0 (null).** The CPE adds no incremental predictive information: for
(combined − baseline) the block-bootstrap CI includes 0 (or is negative) on the
primary metrics/horizon; and/or H1a fails (standalone accuracy ≤ naive); and/or
H1b fails (miscalibrated); and/or H1c fails (confidence does not discriminate, or
is inverted). H0 is the default belief and is rejected only by the pre-declared
success criteria (§6).

**Stated prior (honest expectation, recorded to prevent post-hoc
rationalization).** The prior is *skeptical*. The analogue v1 study found no
clean ≤1-month signal in any embargoed configuration, and that its only apparent
long-horizon edge was leakage / era persistence. The CPE shares feature
information with every model (declared overlap prior 0.5), so incremental value
is a priori unlikely to be large; the most probable outcome is **no material
incremental value, stays shadow**. The CPE also carries a survivorship bias the
analogue did not fully face (§8.1). We nonetheless test rigorously because the
cross-sectional pooling and the episode-based effective sample are genuinely
different mechanisms from the analogue's nearest-neighbour design.

---

## 2. Systems under test & ablation configurations (Phase 2)

All configurations are run through the identical walk-forward harness (§4) and
scored by the identical metrics (§5). Each isolates one design idea by **forcing
a fixed condition scope** (bypassing the adaptive ladder) except where the ladder
itself is the object of study.

| # | Configuration | Isolates |
|---|---|---|
| B | 7-model baseline (no CPE) | the reference system |
| C0 | CPE standalone (adaptive ladder, as shipped) | the engine as built |
| C1 | market conditions only | market-environment signal (era-persistence check) |
| C2 | market + sector | + sector context |
| C3 | market + company | + own-stock state |
| C4 | market + sector + company | the modal shipped scope |
| C5 | market + sector + company + catalyst | + earnings catalyst |
| C6 | 7-model + CPE combined (promoted) | **the incremental-value test (H1)** |
| A1 | fallback ladder ON vs a fixed single scope | value of the hierarchy |
| A2 | episode-based effective sample vs raw-n | value of the RC1 independence correction |
| A3 | uniform-weight WeightedSample vs plain arrays | confirm architectural no-op (predictively inert by construction) |
| A4 | ConditionContribution diagnostics | confirm predictively inert (context-only; must not change any score) |

A3 and A4 are **expected to be exact no-ops** on predictions (uniform weights =
identity; contributions never enter a score). They are run as *falsification of
the claim that they are inert* — any predictive difference is a bug, not a
finding.

Ablation of design ideas is judged by each configuration's standalone metrics and
by (config + 7 models) − baseline, so a component "matters" only if it moves the
*incremental* number, not the standalone number alone.

---

## 3. Universe, data, and point-in-time protocol

- **Universe:** the seeded instrument universe (~78 instruments) — the cross-
  sectional pool. **This is a survivorship-biased set (§8.1).**
- **Scoring targets:** the current portfolio holdings plus a fixed, pre-declared
  symbol list (the universe stocks with ≥ `minimum_history` sessions before the
  first scoring date). The target list is frozen before results.
- **PIT protocol (gates G1–G4):** every feature value and own-percentile
  threshold uses only data ≤ as_of; forward outcomes are truncated at as_of; the
  per-horizon embargo `position(t)+H ≤ position(T)` is enforced by
  `mip.validation.eligibility.label_observable`; the walk-forward emits
  observability diagnostics and asserts **violations_total == 0**; the
  price-poisoning invariance test must pass (evaluating at historical as_of=T is
  invariant to arbitrary corruption of all post-T prices).

---

## 4. Walk-forward design

- **Scoring grid:** monthly as_of dates (first trading day of each month) over
  the evaluation span, per target symbol. Monthly spacing keeps adjacent scoring
  dates from sharing most of their forward windows; the block bootstrap (§5)
  handles the residual dependence.
- **Design vs holdout split (pre-declared):**
  - **Design/characterization period:** 2013-01-01 … 2021-12-31 — used for
    Phases 2–6 exploratory characterization (ablation shape, failure strata,
    reliability-curve inspection).
  - **Confirmatory holdout:** 2022-01-01 … last available session — the primary
    success/promotion decision (§6) is made **only** on the holdout. No
    characterization choice may be revised after inspecting the holdout.
  - Because the CPE learns no parameters from data (all thresholds are declared,
    not fit), every as_of is already OOS by construction; the split exists solely
    to bound *researcher* degrees of freedom.
- **Horizons:** primary **1m (21 sessions)**; secondary 1w, 2w, 3m; exploratory
  6m, 1y (reported but not decision-bearing — long horizons have too few
  independent episodes on this history, per §5 floors and the analogue finding).
- **Determinism (G5):** identical inputs must reproduce byte-identical outputs;
  candidate ordering, calendar lookups, and queries are deterministically ordered
  (sorted match sets); no unseeded randomness (the bootstrap uses a fixed seed).

---

## 5. Metrics (Phases 3 & 4) with pre-declared thresholds

**Realized outcome:** for each (symbol, as_of, horizon), the realized forward
absolute return and the realized excess vs SPY, computed on the embargoed
calendar.

**Directional / rank (per horizon, per config):**
- Directional accuracy (sign of predicted excess vs realized).
- SPY-relative directional accuracy.
- Spearman rank correlation (predicted score vs realized return).
- Signed prediction–realized correlation.

**Probability quality (Phase 3):**
- **Brier score** for P(positive) and P(beat SPY); lower is better.
- **Reliability diagram / calibration curve** with **5 equal-count bins**
  (deliberately coarse — fine bins on limited data are misleading, per the
  analogue lesson). Cells below the sample floor are marked unresolved.
- **Expected calibration error (ECE)**; acceptance threshold **≤ 0.10**.
- **Sharpness** (spread of predicted probabilities away from the base rate) and
  **discrimination** (AUC of predicted probability vs realized binary outcome).
- **Log loss** where all predicted probabilities are strictly interior.

**Confidence quality (Phase 4):**
- Directional accuracy by **confidence tercile** (deciles are under-powered on
  this sample; terciles pre-declared).
- Probability calibration within each confidence tercile.
- Average realized return by confidence tercile.
- Confidence vs effective sample size, and vs historical diversity
  (1 − max(symbol, year concentration)) — descriptive.
- **Inversion test:** sign of the confidence–accuracy relationship must be
  non-negative (analogue v1 was inverted).

**Uncertainty (G6, G8, G10):** all comparisons use a **block bootstrap** with
blocks defined by calendar episode / era (never independence-assuming intervals);
every reported cell carries n and effective n; era-blocked results are reported
with an effective sample that accounts for cross-symbol duplication.

**Sample floors (G8):** a metric cell is *evidence* only with **effective n ≥
10** (and raw n ≥ 30); below that it is reported as *statistically unresolved*,
never as a positive or negative finding.

---

## 6. Success / promotion / failure criteria (decided on the HOLDOUT)

**Success (H1 rejects H0 — "the engine adds information"):** on the holdout, at
the primary 1m horizon, **all** of:
1. (Combined C6 − Baseline B) signed prediction–realized correlation **and**
   directional accuracy improvements each have a 95% block-bootstrap CI lower
   bound **> 0**.
2. CPE standalone (C0) beats the naive baseline (H1a) above the sample floor.
3. Calibration acceptable (H1b: ECE ≤ 0.10, slope ∈ [0.7, 1.3]).
4. Confidence discriminates and is not inverted (H1c).

**Promotion (stricter — required to leave shadow):** Success **plus every gate**
in `docs/VALIDATION_GATES.md` (G1–G10), **plus**:
5. No dependence on a single era, single symbol, or single condition template
   (leave-one-out and era-blocked analyses do not collapse the incremental
   value).
6. **No degradation** of the official combined system on any secondary horizon
   (combined − baseline ≥ 0 within bootstrap noise everywhere; strictly > 0 at
   the primary horizon).
7. Incremental value survives after the survivorship-bias probe (§8.1): the
   effect is not explained away when restricted to the mechanism controls
   available.

**Failure (stays shadow / rejection / revision):** any of — H0 not rejected;
any gate fails; miscalibrated; confidence uninformative or inverted; incremental
value concentrated in one era/symbol/condition; degrades the combined system;
positive result only at long horizons where the sample floor is not met. Long-
horizon-only "success" is treated as failure (analogue precedent: long-horizon
promise was leakage).

**Multiple-comparisons discipline:** the decision rests on the **pre-declared
primary metric at the primary horizon on the holdout**. Secondary horizons and
metrics are supporting context; a positive secondary result cannot substitute
for a null primary. No horizon/metric is promoted to "primary" after the fact.

---

## 7. Statistical assumptions

1. Pooled forward returns are summarized by their (weighted) mean, quantiles, and
   sign probabilities; the primary effect is the mean difference conditional −
   baseline.
2. Overlapping forward windows and same-date cross-symbol clustering are handled
   by the **episode-based effective sample** (distinct calendar episodes), a
   conservative independence measure; standard errors and Wilson intervals use
   effective n, never raw n.
3. The decision engine's cross-model combination is a correlated fixed-effect
   meta-analysis with a **declared** conservative correlation prior (0.5 CPE-vs-
   all); it can only inflate uncertainty, never fabricate precision.
4. Block bootstrap approximates the sampling distribution of metric differences
   under residual serial/cross-sectional dependence.
5. PIT correctness (G1–G4) holds by construction and is asserted, not assumed.
6. A single true effect per (symbol, horizon) is assumed by the fixed-effect
   combination (no random-effects heterogeneity modeled) — a known simplification.

---

## 8. Known sources of bias

**8.1 Survivorship bias (the primary threat).** The cross-sectional pool is the
*current* instrument universe. Historical matches therefore include only symbols
that survived to today; delisted/failed names are absent. This biases pooled
forward returns upward and can manufacture apparent conditional edge. The
unconditional baseline is drawn from the *same* survivorship-biased universe, so
the **incremental** effect (conditional − baseline) partially controls for it,
but not fully (survivorship can interact with the conditions, e.g. momentum
buckets over-selecting eventual winners). This bias cannot be removed with the
current universe seeding; it is disclosed as a hard limitation and probed by
checking whether the incremental effect concentrates in the highest-momentum /
most-extended buckets (the ones most exposed to survivorship).

**8.2 Era persistence.** Market conditions are shared across symbols on a date;
pooled correlation can be high while independent information ≈ number of eras.
The episode-based effective sample addresses this within the CPE, but the C1
(market-only) ablation and era-blocked analysis are the explicit tests.

**8.3 Feature-information overlap with the seven models.** The CPE conditions on
the same features the regime models use. Apparent incremental value may be a re-
expression of existing signal; the decision engine's overlap prior guards the
combination, and C6 − B is the honest test.

**8.4 Own-percentile thresholds fixed at as_of.** Historical events are bucketed
by the symbol's full-history-to-date distribution (PIT-legal, not locally re-
normalized per event) — inherited from the momentum model's documented limitation.

**8.5 Fundamentals sparsity.** Valuation conditions are suppressed (≈1 snapshot);
"company" excludes valuation in practice, so C4/C5 are effectively valuation-free.

**8.6 Multiple comparisons.** Many horizons × configs × metrics inflate false-
positive risk; controlled by the pre-declared single primary decision (§6).

**8.7 Fat-tailed long-horizon means.** The mean-based primary effect is sensitive
to extreme winners at 6m/1y; large standard errors should down-weight these, but
they are also the most survivorship-exposed — hence long horizons are non-
decision-bearing.

**8.8 Fallback-level endogeneity.** The ladder rung is chosen by sample support
(not by realized outcome — G-compliant), but the chosen scope correlates with the
target's state; failure analysis stratifies by fallback depth.

---

## 9. Remaining degrees of freedom (frozen constants — `cpe-v1`)

Declared before validation; **not to be tuned on any evaluation data**:

- Condition templates and families: template set `cpe-v1` (13 templates).
- Bucket cuts: high 0.80 / low 0.20; rate-direction band 0.25; catalyst window
  10 sessions; own-percentile `min_history` 252.
- Primary evidence statistic: absolute (conditional mean − baseline mean).
- Ladder support thresholds: `min_raw_matches` 40, `min_episodes` 12,
  `min_distinct_years` 3, `max_symbol_concentration` 0.50,
  `max_year_concentration` 0.60.
- Model gating: `MIN_EFFECTIVE` 5, `PRIOR_EPISODES` 20 (confidence prior),
  `Z_CLIP` 4, exceedance thresholds ±5%.
- Decision combination: correlation prior 0.5 (CPE vs all), `PRIOR_EVENTS` 30.
- Confidence formula: `volume × diversity`, `volume = eff/(eff+20)`,
  `diversity = 1 − max(symbol, year concentration)`.

Any change to the above is a new template/engine version and requires a fresh
pre-registration.

---

## 10. Calibration expectations (pre-stated)

- Incremental value: expected **small to null**, most likely null at ≤1m
  (analogue precedent + information overlap).
- Probabilities: expected mildly **overconfident** (mean-based effect, fat tails,
  survivorship) — i.e. reliability slope possibly < 1.
- Confidence: discrimination **uncertain**; the pre-registered concern is
  inversion (analogue failure). We would treat even flat (non-inverted, non-
  discriminating) confidence as a partial negative.
- Effective sample: expected to fall sharply with horizon (already observed
  functionally: 60→4 across 1w→1y for one symbol), so 6m/1y are expected
  unresolved.

---

## 11. Failure-analysis strata (Phase 5, pre-declared)

Stratify accuracy, calibration, and incremental value by: realized market regime
(bull/bear via SPY-200d), volatility regime (VIX high/normal), earnings-window vs
not, sector, individual symbol, effective-sample tier, and fallback depth. A
failure is "systematic" if it concentrates in an interpretable stratum
(e.g. bear markets, high-vol, or fallback-heavy predictions). Report per-symbol
and per-period tables (G9); aggregate benefit must not conceal per-symbol
degradation.

---

## 12. Explainability review criteria (Phase 6)

For each statistic currently in the CPE report/context, judge: does it change an
investment decision, and is it statistically supportable at typical sample sizes?
Candidates for suppression a priori: statistics that are (a) redundant with a
stronger one, (b) routinely below the sample floor (e.g. 1y percentiles), or
(c) not actionable. The bias is toward **fewer, stronger** statistics. No report
change is implemented in this phase; recommendations are recorded for a later
decision.

---

## 13. Limitations

Small cross-section (~78, survivorship-biased); no PIT fundamentals (valuation
inert); mean-based primary statistic (fat-tail-sensitive); monthly scoring grid
(compute-bounded, fewer independent long-horizon samples); single-effect
combination (no heterogeneity); the holdout is a single contiguous period (regime-
specific risk); the universe and target list are US-equity/ETF, USD, NYSE-calendar
only.

---

## 14. Reproduction (to be completed at run time, not before)

Harness: `mip.validation.{walkforward,systems,realized,metrics,analyze}` with the
CPE registered as a system; artifacts under `data/validation/conditional_v1/`
(design and holdout subdirectories); `leakage_report.json` asserting
violations == 0; commands and exact artifact paths recorded in the final report
(`docs/` or `data/validation/conditional_v1/REPORT.md`). Random seed fixed and
recorded. This section is filled after execution; the criteria above are not.
