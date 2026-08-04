# Next Investment Decision

Evidence: [PAIRED_BASELINE_RESULTS.md](PAIRED_BASELINE_RESULTS.md),
[POWER_FEASIBILITY_REPORT.md](POWER_FEASIBILITY_REPORT.md),
[CONFIDENCE_REPLICATION_REPORT.md](CONFIDENCE_REPLICATION_REPORT.md),
[DATA_PROVIDER_REQUIREMENTS.md](DATA_PROVIDER_REQUIREMENTS.md), against criteria frozen in
[EXPERIMENT_PREREGISTRATION.md](EXPERIMENT_PREREGISTRATION.md).

---

## Part 7 — Decision table

Exhaustive: every branch terminates in exactly one action. Gates are ordered so that a resolved gate
short-circuits the rest.

### Gate 0 — Data integrity (resolved: FAILED)

| Outcome | Decision |
|---|---|
| **Production DB destroyed** — `mip`/`mip_scratch` hold only an empty `alembic_version`; `mip_test` empty. **← ACTUAL** | **Do not purchase, do not build. Rebuild the free panel first.** No vendor decision can be made or executed on a platform with no data layer. The schema (16 migrations) and the portfolio CSV survive; prices/macro are re-ingestible; the PIT fundamentals snapshot and the prediction archive are permanently lost |
| DB intact | Proceed to Gate 1 |

### Gate 1 — Paired baseline outcome (resolved)

| Outcome | Decision |
|---|---|
| Ensemble clearly beats simple baselines **and** expanded data would reduce uncertainty | Acquire the least operationally burdensome dataset satisfying Mandatory requirements; run the decisive clean-universe validation |
| **Ensemble ties a simple baseline on the primary metric, and LOSES decisively on calibration** **← ACTUAL** | **Freeze the ensemble. Adopt equal-weight as the research null. Do not fund additional model complexity.** Additionally: the calibration loss (CI excluding zero at all 6 horizons) is itself actionable — see Gate 3 |
| Ensemble loses to a simple baseline on the primary metric | Refactor the methodology around the winning baseline; reject further feature/model investment |
| Inconclusive, **but** power analysis shows expanded data would be decisive | Acquire better data solely for the preregistered decisive experiment |
| Inconclusive **and** expanded data would probably remain underpowered | Do not purchase for prediction research; redefine the product or stop the prediction program |

### Gate 2 — Power feasibility (resolved: UNCLEAR, and resolvable for free)

| Outcome | Decision |
|---|---|
| σ_true ≤ 0.10 → a 200–500 name × 20y clean dataset reaches SE ≤ 0.02 | **Purchase** the lowest-total-operating-cost vendor passing all Gates in DATA_PROVIDER_REQUIREMENTS §3, and run the decisive study |
| σ_true ≥ 0.15 → the SE floor `σ_true/√Y` exceeds the threshold at **any** breadth | **Do not purchase for prediction research.** The absolute-signal question is unanswerable at any affordable data budget → invoke the stop condition in §5 |
| 0.10 < σ_true < 0.15 | Purchase **only** with the target relaxed to SE ≤ 0.03 and the reduced claim stated in advance; otherwise stop |
| **σ_true unmeasured — and unmeasurable at 7-name breadth (implied variance negative at every horizon)** **← ACTUAL** | **MEASURE σ_true ON A FREE BROAD PANEL FIRST.** $0. It needs breadth, not cleanliness |

### Gate 3 — Confidence (resolved)

| Outcome | Decision |
|---|---|
| Confidence inversion reproducible | Remove confidence from user-facing reports until a replacement is independently validated |
| Confidence flat **because** predictive skill is absent | Treat confidence as downstream of signal; stop independent calibration work |
| **Ordering INCONCLUSIVE, but score MAGNITUDE decisively overconfident (Brier worse than a constant 50% at all 6 horizons, every CI excluding zero)** **← ACTUAL** | **Stop independent confidence-*ordering* work** (it collapses into the signal question). **Separately: shrink displayed scores toward neutral, or suppress the numeric score**, because the magnitude claim is refuted independently of signal |
| Meaningful positive calibration | Retain and promote confidence as a first-class output |

### Gate 4 — Additional branches required for exhaustiveness

| Outcome | Decision |
|---|---|
| A vendor passes every Mandatory Gate but only via a maintained Windows VM, **and** Gate 2 passed | Purchase; use a **one-time** cloud Windows instance for bulk export. Reject a *maintained* VM (DATA_PROVIDER_REQUIREMENTS §4) |
| No vendor passes M1/M2 (delisted coverage, terminal-value fill ≥ 80%) at any affordable price | Do not purchase. The correctness question is permanently unanswerable → terminate the prediction program; retain the reporting layer pending its own validation |
| Free-panel rebuild fails to reproduce the archived captures | **Halt all research.** Reproducibility is the platform's core asset; a rebuild that does not reproduce known artifacts invalidates the evidence base this decision rests on |
| σ_true resolves favourably but the ensemble still ties equal-weight on clean data | Retire the correlated-fixed-effect combiner in favour of equal-weight; the 9-model architecture is unjustified complexity |

---

## Required answers

### Did the current ensemble beat simple alternatives?

**No.**

- **Directional accuracy (primary metric, 1m, `spy_rel`, paired):** indistinguishable from every
  comparator. vs equal-weight **−0.0191** [−0.0421, +0.0047]; vs best single model **+0.0025**
  [−0.0505, +0.0577]. All 7 comparisons inconclusive; Holm changes nothing.
- **Calibration:** the ensemble is **decisively worse** than both a constant 50% forecast and an
  equal-weighted average of its own components — **12 comparisons, one direction, every CI excluding
  zero** (Brier Δ +0.0436 to +0.1142).
- **Ensemble vs its own best component:** no measurable difference. Nine models add nothing over one.
- **Production weighting vs arithmetic mean:** the arithmetic mean **wins** (95% of dir-acc draws, and
  Brier CIs exclude zero at every horizon).
- **`valuation` contributes exactly zero** — 100% neutral across 7,938 cells.
- On the embargoed grid with a system-independent target, the ensemble is **below coin-flip at 3m, 6m
  and 1y**, and pooled rank IC is negative at four of six horizons. The 1y tercile spread is −0.60.

### Is the current dataset sufficient for paired model decisions?

**Partially — and it already delivered one decisive verdict.** The paired design achieved SE ≈ 0.011
on Brier deltas, enough to reject the ensemble's calibration with CIs excluding zero at six horizons.
It was **not** sufficient for directional-accuracy deltas (CIs ±0.05, 2–5x the MEMD). So: sufficient
for *calibration* decisions, insufficient for *accuracy* decisions. And the panel that produced this
(7 names) is narrower than the 31-name panel that already returned "inconclusive" — a null here
carries less weight than the existing nulls, though the calibration result is a *positive* finding and
stands on its own.

### Would a broader survivorship-clean dataset likely make the absolute-signal question decisive?

**Unclear — and this is a reversal of my two prior reviews, caused by correcting their arithmetic.**

Both earlier reviews discounted breadth with the equicorrelation formula `n/(1+(n−1)ρ)`. That is the
formula for averaging correlated *levels*; a cross-sectional IC differences the common factor out by
ranking. The correct decomposition is
`Var(mean IC) = σ²_true/Y + E[1/(n−3)]/(Y·m)`, whose first term **does not shrink with breadth**.

Consequences:

- **Breadth saturates.** 500 → 5,000 names improves SE by **7.8%**. The prior recommendation to prefer
  a 1,500-name universe "for margin" was buying ~5% for 3x the data.
- **The SE floor is `σ_true/√Y`.** At σ_true = 0.15, Y = 20 → floor 0.0335: the preregistered 0.02
  threshold is **unreachable at any universe size or price**, and even 0.03 is unreachable below Y=25.
- At σ_true = 0.05, 185 names × 20y suffices. At σ_true = 0.10 it is marginal. The decision boundary
  sits **inside** the plausible range (published monthly IC time-series SD ≈ 0.08–0.15).
- **σ_true cannot be measured on the surviving panel** — implied variance is negative at all six
  horizons, because at 6–7 names the sampling term (0.25–0.33) swamps it.

### Which exact data capabilities are required?

Mandatory (all deferred until Gate 2 resolves): **M1** delisted securities, **M2** terminal
values with ≥ 80% fill and documented method, **M3** ≥ 20 years depth, **M4** corporate actions with
raw retained, **M5** PIT identity history, **M6** reproducible vintages, **M7** ~200–500 securities
(*revised down* from 500–1500 on the saturation finding).

Optional, contrary to prior assumption: **PIT fundamentals** (`valuation` contributes zero), **PIT
earnings** (10% activation, anti-predictive), **PIT market cap** (not needed for the MVI), **> 500
names** (7.8% gain), **macOS compatibility** (an operating cost, not a scientific requirement).

### Is Norgate-level data now the next best investment?

**No — not now.** Not because it is the wrong data. Because a **$0, 1–2 day** measurement determines
whether *any* dataset can answer the question, and that measurement has never been run. Buying first
risks spending cash, a VM, and ~3 engineering weeks to reach a *more expensive* "inconclusive."

If σ_true resolves favourably, the purchase becomes justified — and **cheaper than previously scoped**
(~200–500 names, not 500–1500).

### Is a maintained Windows VM scientifically justified, or merely a vendor-specific operating cost?

**Merely a vendor-specific operating cost — and premature at any price.** No Mandatory requirement is
vendor-specific; a VM-requiring vendor and an HTTPS vendor score identically on every scientific row.
A research corpus is built **once**, so if a Windows environment is needed at all, a one-time cloud
instance (~$5–20) satisfies it; a *maintained* VM buys only daily updates no experiment needs, and it
sits outside the test suite, weakening the reproducibility discipline (M6) that is this platform's
best asset.

### What is the single next action?

> ## Rebuild the free price panel and estimate σ_true — the across-date dispersion of the true date-level IC — on a broad (~500-name) survivor universe.
>
> ~1–2 days, **$0**, no vendor, no VM, no new architecture. Re-ingest prices from yfinance into the
> existing schema (16 migrations survive), verify the rebuild reproduces the archived captures, then
> compute date-level ICs and decompose their variance.
>
> **σ_true needs breadth, not cleanliness.** Survivorship distorts the *level* of the IC far more than
> its cross-date *dispersion*, and it biases the estimate **upward** — an upper bound, which is exactly
> the conservative direction needed. This single number determines whether every Mandatory data
> requirement is worth buying.

Nothing else is recommended. Not the purchase, not the VM, not the ingestion framework, not a model,
not a feature, not a confidence redesign.

### What result would cause the project to stop?

Four conditions, in evidential order. **S1 is now met** and is the reason the ensemble is frozen rather
than the project terminated.

| # | Condition | Sufficient evidence | Status |
|---|---|---|---|
| **S1** | **The ensemble cannot beat trivial baselines** | Paired, on identical cells, system-independent target: indistinguishable from its best single component and from equal-weight on accuracy; **decisively worse than a constant 50% on calibration at all 6 horizons, CIs excluding zero** | **MET.** → freeze the ensemble; stop funding model complexity. Does **not** terminate the project — it terminates *this architecture's* claim on further investment |
| **S2** | **The absolute-signal question is unanswerable at any affordable budget** | σ_true ≥ 0.15 on the free broad panel ⇒ SE floor ≥ 0.0335 at Y=20 ⇒ the preregistered threshold is unreachable at any breadth | **PENDING — the single next action decides it.** If met: do not purchase; terminate the prediction program |
| **S3** | **No vendor can supply survivorship-clean outcomes** | No affordable vendor passes M1/M2 (delisted coverage; ≥ 80% terminal-value fill) | Untested; deferred behind S2 |
| **S4** | **Nothing of value remains** | S2 met **and** the reporting/explainability layer, validated against real decisions, changes none | Untested. **Note the asymmetry: S2 alone is a pivot, not a termination** |

**What is explicitly NOT a stop condition:** the inconclusive directional-accuracy results above (the
panel is 7 names — weaker than the 31-name panel that already returned inconclusive); the confidence
non-replication (underpowered, CIs ±0.13); or the loss of the database (recoverable for prices, and
the schema survives).

---

## What remains unknown

Stated plainly, because the evidence does not reach these:

1. **σ_true** — the parameter that decides the entire investment question. Unmeasured, and
   unmeasurable at 7-name breadth.
2. **Whether any system has skill above zero.** A paired design compares systems; it cannot establish
   either exceeds zero. Directional accuracies cluster at 0.51–0.53 with the ensemble below 0.50 at
   three of six horizons — suggestive, not decisive.
3. **Whether the ensemble beats a literature-standard external baseline** (true 12-1 cross-sectional
   momentum). Blocked by the destroyed database; the in-project substitute is a weaker comparator.
4. **The magnitude of survivorship bias.** Requires the missing names' returns.
5. **Whether the confidence *ordering* is inverted, flat, or weakly positive.** The test spans
   [−0.06, +0.20]; all three remain live.
6. **Sector stability of any result.** The sector map was destroyed.
7. **Whether the reporting layer has value.** Never tested with a human.
8. **Whether the serial dependence of date-level ICs is closer to annual (conservative, assumed here)
   or monthly (optimistic).** This shifts the σ_true term by up to √12 and is the second-largest
   unmeasured lever after σ_true itself.
