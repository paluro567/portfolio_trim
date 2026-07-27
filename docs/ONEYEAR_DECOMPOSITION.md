# Is the One-Year Trim Edge Genuine? — Falsification & Decomposition Study

Read-only, point-in-time. Decomposes the headline 1-year result (≈54.3% dir acc, pooled rank corr
+0.17) against clean economic targets, with honest effective-sample power. No production change.

## 1. Executive verdict

**D — ARTIFACT / UNSUPPORTED.** The apparent one-year edge is **not demonstrated genuine
stock-selection information.** In plain English:

- Against **clean targets** (absolute, market-relative, beta-residual, sector-relative), the proper
  **within-date cross-sectional IC is only +0.05 to +0.09** — far below the +0.17 headline, which was
  measured against the *model's own baseline* and pooled time-series with cross-section.
- **It is carried by ~3 symbols.** Beta-residual IC +0.092 → drop the top-3 contributors (MARA, TSLA,
  CCJ) → **−0.002**; drop top-5 → −0.044. The "edge" is a handful of extreme movers, not broad selection.
- **It is carried by one partial year.** Yearly cross-sectional IC: 2022 −0.03, 2023 +0.03, 2024 +0.09,
  **2025 +0.41** (7 dates). Remove 2025 and it collapses to ~zero.
- **Every year-blocked bootstrap CI includes zero** (beta-resid +0.092, CI [−0.002, +0.211]).
- **Effective sample ≈ 4 independent annual blocks** — 43 monthly scoring dates collapse under
  overlapping 1-year windows to four years, and the signal lives in one of them.

Two honest refinements (the controls did *not* explain it away — concentration and era did):
- **NOT pure market beta (H2 refuted as a complete explanation):** beta-neutralizing *increases* the IC
  (+0.092 vs +0.049 absolute) — the score is not simply favoring high-beta in an up-market.
- **NOT pure sector allocation (H3 refuted):** the within-sector IC stays weakly positive (+0.046).

So the edge is not beta or sector — but it is **concentration + era + noise**, on a survivorship-biased
universe, at an effective sample too small to resolve any plausibly-real small effect.

## 2. Existing-test audit (how +0.17 was produced, and its biases)

| Property | Finding | Bias risk |
|---|---|---|
| Target | rank corr was vs *realized_excess* = actual − model's own baseline | **Inflates** vs clean targets (+0.17 → +0.01–0.09 here) |
| Cross-section vs time | pooled over all (symbol, date) cells | Mixes time-series drift with selection — not a clean IC |
| Scoring frequency / dates | monthly; 43 holdout 1y dates | Overlapping 1y windows → dependent |
| Symbols | 31 | Tiny cross-section |
| Effective independent obs | **≈ 4 annual blocks** | Catastrophically low power |
| Universe construction | current instruments (universe.yaml), stocks with history ≥2013 | **Survivorship-biased — survivors only** |
| Delisted / bankrupt / acquired | **absent** | Cannot rule out survivorship uplift |
| Symbol changes / missing future prices | cells without a complete 1y window dropped | Standard, minor |
| Overlapping 1y windows | not independent | Naive CIs would be far too tight |
| Point-in-time universe | **No** | The single biggest unremovable limitation |
| Repeated dominant stocks | Yes — MARA/TSLA/CCJ dominate | Concentration |

## 3. Target comparison (within-date cross-sectional IC, block-bootstrap by year)

| Target | Mean IC | 95% CI (year-block) | Pooled Spearman (headline method) | Verdict |
|---|---|---|---|---|
| Absolute | +0.049 | [−0.072, +0.200] | +0.009 | includes 0 |
| Benchmark-relative | +0.049 | [−0.072, +0.200] | +0.032 | includes 0 |
| **Beta-neutral residual** | **+0.092** | **[−0.002, +0.211]** | +0.081 | strongest, still includes 0 |
| Sector-relative | +0.047 | [−0.058, +0.179] | +0.025 | includes 0 |
| Multi-factor residual (size/mom/value) | — | — | — | **Unresolved — no PIT factor data** |

## 4. Allocation vs selection

Beta and sector controls do **not** remove the ranking: within-sector beta-residual IC is +0.046
(positive), and beta-residual is the strongest global target. So the signal is **not** merely sector or
market allocation — but the residual is tiny and within noise. This refutes H2/H3 as complete
explanations without establishing genuine selection.

## 5. Survivorship & concentration

- **Universe is not point-in-time** — current survivors only; delisted/bankrupt/acquired names absent.
  This cannot be corrected with available data and can only have *inflated* the result.
- **Contribution is concentrated:** top-5 to the beta-resid relationship are MARA, TSLA, CCJ, GOOG, SCCO
  (crypto-miner, EV, uranium, mega-cap, copper — extreme movers). Dominant-exclusion collapses the IC:
  drop-1 → +0.048, **drop-3 → −0.002**, drop-5 → −0.044.

## 6. Robustness

| Test | Result |
|---|---|
| Leave-one-year-out | signal lives entirely in 2025 (+0.41); 2022–2024 ≈ 0 → collapses without 2025 |
| Dominant-symbol exclusion | collapses to ~0 after removing 3 of 31 names |
| Year-block bootstrap | every target's CI includes zero |
| Effective sample | ≈ 4 independent annual blocks |
| Minimum detectable effect | CI half-width ≈ 0.11; to resolve a plausibly-real IC of ~0.03–0.05 with a CI excluding zero needs SE ≈ 0.02, i.e. effective N ≈ 2,000+ — **hundreds of survivorship-clean names and/or multi-decade history**, not 31 names × 4 years |
| Permutation within date | consistent with the above (means near zero, wide spread) |

## 7. Scientific decision memo

- **Is the 1-year edge real?** No — not as genuine stock-selection information. It fails dominant-symbol
  exclusion, fails leave-one-year-out, and every robust CI includes zero.
- **What kind of edge is it?** A concentration/era artifact — a few extreme-mover names in one partial
  year (2025), on a survivor-only universe. It is *not* beta or sector allocation (those were controlled
  and it survived them), but that only means we cannot even attribute it to a systematic exposure — it
  is essentially noise plus concentration.
- **Confidence:** High that it is *unsupported as genuine selection*; the concentration and era results
  are unambiguous and the power is provably tiny.
- **What remains unresolved:** whether a *real, small* residual signal exists is genuinely
  undeterminable here — the sample (31 survivors × 4 independent years) cannot resolve an effect of the
  size equity selection signals actually have. Survivorship cannot be tested at all.
- **Previous conclusions that must be revised:** the platform's headline claim — "its one measurable
  skill is 1-year ranking (+0.17)" — is **withdrawn.** The platform has **no demonstrated genuine
  stock-selection edge at any horizon.** The earlier "macro is the only unique predictor" finding is
  now also suspect for the same concentration/power reasons.
- **What is now blocked:** *every* model revision — retire `relative_strength`, PEAD, valuation,
  orthogonal families — is premature. There is no validated edge to improve, and the evaluation
  apparatus cannot certify one.
- **Highest priority next:** not a model. **Rebuild the evaluation foundation** — a survivorship-clean,
  point-in-time universe of *hundreds* of names (and/or far longer history) sufficient to detect a
  plausibly-small stock-selection IC. Until the apparatus can resolve an effect of realistic size, no
  edge — old or new — can be validated.

## 8. Knowledge update

- **Confirmed:** the 1-year headline is concentration- and era-driven; effective sample ≈ 4 independent
  years; universe is survivorship-biased and not point-in-time.
- **Refuted:** H2 (pure market beta) and H3 (pure sector) as *complete* explanations — the ranking
  survives beta/sector controls. Also refuted: the prior belief that the platform has a genuine 1-year
  selection edge.
- **Confirmed (H4/H5/H6):** survivorship/concentration, era concentration, and statistical-artifact/
  small-sample explanations all hold.
- **Weakened:** any hypothesis that the current 7-model architecture contains latent stock-selection
  skill worth refining.
- **New dependency (now proven, not suspected):** every future incremental claim is gated on an
  evaluation universe with adequate cross-sectional breadth and survivorship integrity. This is the
  binding constraint on the entire program.
- **Current confidence:** High in the negative verdict; the burden of proof was on the +0.17 result and
  it did not survive.
