# Data vs Method — Part 8 Decision Gate and Final Report

---

## Part 8 — Decision gate

### The ensemble failed primarily because of **METHODOLOGY**, not data.

Stated explicitly, as required.

The observed failure — always-neutral > equal-weight > production — is **fully accounted for** by two
mechanisms, both of which are properties of code in this repository:

1. **Calibration (methodology).** `se ≡ |effect / z_raw|` fixes typical per-model `|z|` near 0.66, which
   maps through Φ to a score ~19 points from neutral. Implied accuracy 0.694–0.722 against realized
   0.455–0.514: an **+18 to +26 pp overclaim at every horizon**.
2. **Aggregation space (architecture).** Averaging evidence in `z` space and mapping once through Φ
   applies no shrinkage, whereas averaging `Φ(z_i)` applies λ ≈ 0.4 by Jensen. Rescaling production to
   equal-weight's dispersion closes **96.3%–103.6%** of the Brier gap.

Neither depends on which securities are in the panel. The first is a formula; the second is an
inequality.

### Relative importance

| Cause | Type | Share of the explained failure | Basis |
|---|---|---|---|
| **Score dispersion / calibration** | **Methodology** | **~70%** | Alone it accounts for the entire ensemble-vs-neutral gap (Brier 0.2989 vs 0.2500). The shrinkage sweep is monotone with optimum λ=0 at all six horizons |
| **Aggregation space** | **Architecture** | **~25%** | Accounts for 96–104% of the ensemble-vs-*equal-weight* gap specifically — the narrower of the two comparisons |
| **No signal** | **Statistical / possibly data** | **necessary condition, not a share** | Without it, dispersion would be a virtue. It makes the other two costly rather than harmless. It is the *precondition*, and the only cause where data could matter |
| **Weighting (`weight = (z/effect)²`)** | **Architecture** | **~5%** | A provable defect (Spearman **exactly** −1.000) with **no measurable consequence on this panel** — its beneficiary is LOO-harmless |
| Sparse activation, bearish tilt, prior misspecification | Mixed | **~0% each** | Real, documented, none causal |

**Explicitly: the failure is NOT primarily a weighting problem.** That was the premise handed to this
investigation and it does not survive. The weighting is genuinely defective, but production and
equal-weight rank cells at Spearman 0.89–0.98 and agree directionally 91–96% of the time — the weighting
choice is almost informationally irrelevant here. What differs is volume, not content.

**And it is NOT primarily a data problem.** Of eleven mechanisms examined, the five classified
"definitely not changed by cleaner data" include **both** that fully explain the failure.

---

## Final report — the six required answers

### 1. Why did the production ensemble lose?

Because it made confident statements about nothing. Its scores sit ~19 points from neutral (implied
~70% accuracy) while its realized directional accuracy is ~51% — and below 50% at 3m, 6m and 1y. With
no exploitable ordering in the score (shrinkage sweep monotone, optimum λ = 0, no interior optimum),
**every point of displacement from 50 is a pure Brier loss.** It therefore loses to a constant 50%
forecast at all six horizons, every CI excluding zero.

The combiner is not the culprit: it *dampens* z (empirical factor 0.811 at 1w vs a theoretical 1.732)
and faithfully transmits per-model overconfidence rather than creating it. The defect is upstream, in
each model's `se ≡ |effect/z|` recipe — independently reproducing the analogue RCA's **RC1** and proving
it is not analogue-specific.

### 2. Why did equal-weight win?

**Not on information. Entirely on shrinkage.** Averaging already-mapped scores `Φ(z_i)` rather than
averaging in z space applies λ ≈ 0.4 shrinkage by Jensen's inequality. Rescaling production's dispersion
to match equal-weight's — one scalar, no reweighting — recovers **96.3%–103.6%** of the Brier gap.
Ordering agreement is Spearman 0.89–0.98, directional sign agreement 91–96%, and the rank-IC delta has
no consistent sign across horizons.

Equal-weight is a **quieter presentation of the same non-signal**, and it is still not right: the
Brier-optimal λ is **0**.

### 3. Which models genuinely help?

**One: `interest_rate_sensitivity`.** It is the only model whose leave-one-out removal degrades
directional accuracy with a confidence interval excluding zero (**−0.0381, CI [−0.0678, −0.0070]**),
at 98.6% activation and 23% of mean weight.

Everything else is **inconclusive** (`macro_regime`, `momentum_exhaustion`, `relative_strength`,
`sector_rotation`) — every CI includes zero, and no single model beats the full ensemble.

Two findings worth flagging against prior beliefs: the claim that **`macro_regime` is the only unique
predictor** gains no support here (its uniqueness holds — realized z-correlation −0.003 to −0.130
against the others — but it is the *worst* solo performer, dir acc 0.4758, Brier 0.3389); and the
**retire-`relative_strength`** hypothesis remains undecided, with removal now leaning mildly *negative*
(−0.0119).

### 4. Which models genuinely hurt?

**None.** No model's removal improves the ensemble with a CI excluding zero.

Two are **provably or effectively inert** rather than harmful:
- **`valuation`** — 0.000 activation across 7,938 rows; LOO Δ **exactly 0.0000 with a zero-width CI**.
  It is a mathematical no-op, dead weight in the registry.
- **`earnings_behavior`** — 0.103 activation, 5.6% weight, top-weighted in 0.2% of cells; LOO
  Δ = +0.0024 [−0.0070, +0.0117], the only positive-on-removal but immaterial.

**The failure is not attributable to a bad component.** It is a property of scaling and aggregation.

### 5. Is the bottleneck primarily the data or the methodology?

## **Methodology.**

| Mechanism | Type | Cleaner data changes it? |
|---|---|---|
| Miscalibration / overconfidence | Methodology | **Definitely not** |
| Aggregation space | Architecture | **Definitely not** |
| Weight = inverse effect² | Architecture | **Definitely not** |
| Noise amplification (refuted) | Architecture | **Definitely not** |
| Clipping (refuted) | Architecture | **Definitely not** |
| Model disagreement (refuted) | Architecture | Probably not |
| Ranking instability (refuted) | Statistical | Probably not |
| Redundancy / priors | Statistical | Possibly |
| Conviction↔correctness | Statistical | Possibly |
| Bearish tilt | Data (partly) | Possibly |
| Sparse activation (`valuation`) | **Data** | Possibly — but needs **PIT fundamentals**, which Norgate does not supply |
| **No exploitable signal** | **Statistical** | **Possibly** — the one place data matters |

**Five of eleven mechanisms are data-invariant, and they include both that explain the failure.** Only
the precondition — whether any signal exists — is a question data can address, and even there
`POWER_FEASIBILITY_REPORT.md` shows decisiveness hinges on σ_true, which is still unmeasured.

### 6. Would purchasing Norgate today likely change the conclusion?

## **Probably not.**

**What it would change:** the *precision* of the no-signal measurement (mechanism M1), and the estimate
of the outcome base rate, which slightly softens the cost of the structural bearish tilt (M11). It
would also let the correlation priors be estimated rather than declared (M6).

**What it would not change — and this is the decisive part:**

- The ~19-point score displacement. That is `se ≡ |effect/z|` plus `100·Φ(z)`, computed identically on
  any dataset.
- The 96–104% of the equal-weight gap attributable to aggregation space. That is Jensen's inequality.
- Spearman(|effect|, weight) = **exactly −1.000**. That is an algebraic identity of the weight
  definition.
- `valuation`'s inertness — that needs **PIT fundamentals**, and Norgate supplies prices, corporate
  actions, delisting returns and index constituents, **not** fundamentals vintages.

**Run on survivorship-clean data today, the production ensemble would still lose to a constant 50%
forecast at every horizon, for exactly the reasons measured here.** The bottleneck Norgate addresses
(outcome correctness and measurement precision) is real and is *not* the bottleneck that caused this
failure.

---

## What remains unknown

1. **Whether any signal exists.** The λ = 0 optimum is a strong indication but a 7-survivor panel with
   dir-acc CIs of ±0.05 cannot prove absence.
2. **Whether the overconfidence is uniform across models or driven by particular ones.** Per-model
   calibration curves were not computed; only the ensemble-level overclaim is established.
3. **Whether `interest_rate_sensitivity`'s helpfulness replicates.** One CI excluding zero on one narrow
   panel, from a family of seven LOO tests — nominally significant, but 1-of-7 at α = 0.05 warrants
   caution and no multiplicity correction was applied to the LOO family.
4. **Whether the conviction↔correctness anti-correlation is significant.** A six-of-six directional
   pattern with no per-model CI.
5. **Whether the correlation priors' errors matter once there is signal.** Currently unmeasurable —
   nothing to misweight.
6. **The magnitude of survivorship effects on any of this.** All 7 names survived; 6 of 7 are large-cap
   tech/growth.
