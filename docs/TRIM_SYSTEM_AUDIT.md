# Quantitative Research Audit — Production Trim Score System

**Evidence base:** the captured walk-forward (`data/validation/conditional_v1/predictions.jsonl`):
every production model's evidence per (symbol, as_of, horizon), 2013→2026, evaluated on the
**2022+ holdout**, ~31 long-history stocks, monthly grid. Realized outcomes from prices only.
**Confidence caveat (applies to everything):** one walk-forward, one 2022–2026 regime era, a small
survivorship-biased cross-section — so per-model incremental CIs are wide (all include zero). Read
the *pattern across metrics*, not any single point estimate.

## Primary question — answered

**Under what conditions does the system genuinely provide useful predictive information?**

Narrowly, and only under this conjunction:
1. **Long horizon (1 year)** — the only horizon with a real ordering signal (rank corr **+0.17**, dir
   acc **0.54**, best Brier). At 1w–3m it is coin-flip or worse (rank corr ≤ 0).
2. **Used as a *ranking* tool, not a directional caller** — and only where ranking works (1y). At 1m
   the top-vs-bottom decile spread is **+0.001** (nil, non-monotonic).
3. **Driven by essentially one model — `macro_regime`.** It is the best standalone predictor (1m acc
   0.541) and the only model whose removal clearly hurts (drop → 0.474 vs 0.499 baseline). The others
   are near-zero or net-negative contributors.
4. **In up/neutral markets.** Bull-market 1m acc **0.512** vs bear-market **0.454** — the edge is
   regime-conditional and *inverts below coin-flip in drawdowns*.
5. **On higher-confidence calls.** Confidence terciles: low 0.493 → high **0.518** — weak but
   correctly-signed discrimination (a genuine positive, unlike the CPE's inverted confidence).

**Causal read (correlation vs causation):** the edge is concentrated in (a) the *macro* model, (b)
*bull* markets, (c) *long* horizons, and (d) it *cannot rank stocks at 1m*. That combination points to
the genuine information being **macro/regime market-context timing**, not short-horizon
stock-specific selection. The system is, in effect, a slow risk-on/risk-off tilt that reads as skill
when the market trends up — not a cross-sectional stock-picker.

---

## 1. Executive summary

**Does well (modestly):** long-horizon (≈1y) *ranking*; identifying macro/regime context; producing
*correctly-signed* confidence (higher confidence ≈ more reliable); honest neutrality (models abstain
rather than guess); full explainability.

**Consistently struggles with:** short-horizon (1w–3m) direction — coin-flip, negative rank
correlation; **bear markets** — below coin-flip (0.454), i.e. actively wrong when it matters most;
**probability calibration** — Brier worse than an uninformed 0.5 forecaster at every horizon (0.28–0.32
vs 0.25); **cross-sectional stock differentiation at short horizons** — the decile spread is nil.

## 2. Model report cards (judged by incremental contribution, not weight)

| Model | Activation (holdout) | Standalone 1m acc / rankcorr | Incremental (drop-one, 1m) | Verdict | Confidence |
|---|---|---|---|---|---|
| **macro_regime** | 100% | **0.541 / +0.046** (best) | drop → 0.474 (**most helpful**, +0.025); CI incl. 0 | The one carrying signal; likely market-context/beta, not stock selection | Moderate |
| **interest_rate_sensitivity** | 100% | 0.486 / −0.05 (but 3m 0.530/+0.09) | +0.004; CI incl. 0 | Near-zero at 1m; a faint 3m hint | Low–Moderate |
| **sector_rotation** | 100% | 0.494 / −0.01 | drop → 0.495 (slightly *helps* to remove) | Redundant/near-zero | Moderate |
| **momentum_exhaustion** | 97% | 0.510 / +0.01 | −0.013; CI incl. 0 | Near-zero; possibly mis-pointed at 1w (reversal, not continuation) | Moderate |
| **relative_strength** | 91% | 0.478 / −0.03 (sub-coin) | drop → **0.513** (**most harmful**, −0.014) | Net-negative at 1m; likely double-counts momentum | Moderate |
| **earnings_behavior** | **8%** | 0.459 / −0.06 (n=135) | ~0 (rarely active) | Rarely on; unhelpful when on; explanatory only | Moderate |
| **valuation** | **0%** | — (never active) | 0.000 exactly | **Completely inert** — sparse fundamentals; contributes nothing | High |

Explanatory vs predictive: **all seven are more explanatory than predictive.** Only `macro_regime`
shows any consistent standalone edge; `valuation` and `earnings_behavior` are effectively absent;
`relative_strength` (and to a lesser degree sector/momentum) appear *redundant or net-harmful* at 1m.

## 3. System report card

| Dimension | Grade | Evidence |
|---|---|---|
| Short-term usefulness (1w–1m) | **Poor** | dir acc 0.49, rank corr −0.05→−0.02, Brier 0.30–0.32 |
| Medium-term (3m) | **Poor** | dir acc 0.48, rank corr −0.005 |
| Long-term (1y) | **Fair** | dir acc 0.54, rank corr **+0.17**, Brier 0.28 |
| Ranking ability | **Fair at 1y, Nil at 1m** | 1m decile spread +0.001; 1y rank corr +0.17 |
| Directional prediction | **Poor** | ~coin-flip; abs 0.486 ≈ rel 0.488 |
| Risk identification | **Weak** | worst exactly in bear markets (0.454) — fails when risk matters |
| Explainability | **Strong** | full attribution to models → regimes → features |
| Stability | **Regime-fragile** | bull 0.512 vs bear 0.454; edge is conditional |

## 4. Information coverage map

| Domain | Coverage | Note |
|---|---|---|
| Rates / curve | **Well** | rates model, 100% active |
| Macro regime | **Well** | the one working signal |
| Sector / relative price behavior | **Well (but redundant)** | sector + relative overlap; relative net-negative |
| Own price momentum / technicals | **Well** | momentum model; possibly mis-signed at 1w |
| Earnings *timing* | **Partial** | only ~8% of the time (near reports) |
| Earnings *surprise* outcome | **Partial** | captured as a feature, lightly used |
| Valuation / fundamentals | **Missing in practice** | model 0% active (data too thin) |
| Post-earnings drift (PEAD) | **Missing** | data exists; no dedicated signal |
| Analyst estimate *revisions* | **Missing** | needs vintage data |
| Positioning (short interest, insider) | **Missing** | no source ingested |
| Options-implied expectations | **Missing** | — |
| Event calendar (Fed, releases), guidance, news | **Missing** | documented as unavailable |

Redundant/unused: `valuation` (unused — inert), `relative_strength`/`sector` (redundant with
momentum), `earnings_behavior` (mostly dormant).

## 5. Prioritized research roadmap (ROI = expected predictive value ÷ complexity)

1. **Re-grade and re-scope the tool to where it works** — evaluate/report primarily at **1y** and in
   the **tails/ranking**, not 1w direction. *(Value: medium · Complexity: ~none · highest ROI)*
2. **Investigate `relative_strength` (and sector) as net-negative/redundant** — understand *why*
   before touching it. *(Value: medium · Complexity: low)*
3. **Unlock the inert `valuation` model** — passively accumulate fundamentals; a dark evidence
   category returns for free. *(Value: medium · Complexity: low/time)*
4. **Post-earnings-drift (PEAD) signal** — orthogonal, short-horizon, buildable from data already
   held; directly targets the earnings-window failure. *(Value: high · Complexity: medium)*
5. **Bear-market failure diagnosis** — why does the edge invert below coin-flip in drawdowns? (Is the
   macro signal just long beta?) *(Value: high · Complexity: medium — analysis, not build)*
6. **Analyst estimate revisions** — highest orthogonal ceiling, data-gated. *(Value: high · Complexity:
   high — data acquisition)*
7. **Positioning (short interest / insider)** — orthogonal, free, PIT-clean. *(Value: medium ·
   Complexity: medium)*

**Guiding principle upheld:** the point is not to raise historical accuracy by fitting, but to
understand *why* `macro_regime` is the only signal, *why* the edge is bull-only and long-horizon, and
*why* the short-horizon cross-section is unpredictable — then add genuinely orthogonal information
where the failures are, rather than reshuffling redundant price/macro models.
