# Research-Driven Revision Plan — Trim Score Platform

Built on `docs/TRIM_SYSTEM_AUDIT.md` (assumed correct). Objective: revisions with the highest
probability of **genuine out-of-sample** improvement, minimizing overfitting. Not in-sample accuracy.

**The one honest meta-finding that governs everything:** the highest-*confidence* improvements are not
new models — they are **corrections and re-scoping grounded in this system's own walk-forward
evidence**. The genuine new-information bets (PEAD, valuation, revisions, positioning) are worth
pursuing but each carries real generalization risk, and the CPE already proved that a sensible,
orthogonal-looking idea can fail the incremental bar. So the plan is ruthless: bet the fund on the
corrections; treat every new signal as a shadow experiment that must earn promotion.

## Executive summary — the five highest-probability revisions

1. **Re-scope the tool to long-horizon ranking; stop deploying it as a short-horizon directional
   caller.** (Deployment correction — near-zero cost, evidence-grounded, ~zero overfitting risk.)
2. **Validate-then-retire the net-negative / redundant model (`relative_strength` first).**
   (Denoising — grounded in leave-one-out evidence; a *removal* cannot overfit forward.)
3. **Post-earnings-announcement drift (PEAD) signal.** (New orthogonal information the system has the
   data for; the most durable anomaly in the literature; fixes the dormant earnings channel.)
4. **Unlock the inert `valuation` model** by accumulating point-in-time fundamentals. (A real,
   horizon-matched long-run premium; passive; already in motion.)
5. **Diagnose the bear-market inversion / macro-is-beta hypothesis** before trusting the long-horizon
   edge. (A gating research question, not a build — but it decides whether #1 is real or an artifact.)

Everything else (analyst revisions, positioning, short-term-reversal, sentiment) is Phase 2/3.

## Stage 1 — Root-cause analysis

| Audited weakness | Root cause | Evidence |
|---|---|---|
| Short-horizon (1w–3m) ≈ coin-flip, negative rank corr | **Market efficiency + wrong horizon** — the system's information is slow; short-horizon cross-section is near-random to it | rank corr −0.05→0; 1m decile spread +0.001 |
| Only `macro_regime` carries signal; edge is bull-only | **Redundant models + macro-as-beta** — the "skill" is largely market-context/beta, not stock selection | macro drop → 0.474; bull 0.512 vs bear 0.454 |
| `relative_strength` net-negative at 1m | **Redundancy** — double-counts momentum/price info; adds noise | drop → 0.513 (best LOO); standalone 0.478 |
| `valuation` 0% active | **Missing information** — ~1 PIT fundamentals snapshot | 0% activation |
| `earnings_behavior` 8% active, unhelpful when on | **Poor activation + weak use of surprise** — timing only, no drift | 8% active; 0.459 when active |
| Bear-market accuracy 0.454 | **Incorrect assumption** — signal is conditional/beta-like and breaks in drawdowns | below coin-flip in bear |
| Brier > 0.25 everywhere | **Calibration weakness** — scores aren't probabilities | 0.28–0.32 |

## Stage 2 — What information was actually missing (empirical, not assumed)

The failures cluster by *what the system cannot see*: (a) **the earnings-expectations outcome and its
drift** (earnings channel dormant → misses post-report moves); (b) **valuation / fundamentals** (model
dark → misses the one factor horizon-matched to its 1y strength); (c) **stock-specific
differentiation at short horizons** — which is *market-efficient and may simply be unavailable* with
free daily data (the honest, uncomfortable answer: some failures are not fixable, they're the market).
Crucially, the redundant models (`relative_strength`, `sector`) are *not* a missing-information
problem — they're a **too-much-of-the-same-information** problem.

## Stage 3–6 — Revision research reports (survivors of the ruthlessness filter)

### R1 — Re-scope to long-horizon ranking (deployment correction)
- **Problem:** the tool is deployed/graded as a short-horizon directional caller, where it is coin-flip.
- **Root cause:** wrong horizon + wrong objective (direction vs ranking).
- **Evidence:** 1y rank corr **+0.17**, acc 0.54; 1m decile spread nil.
- **Market phenomenon:** slow macro/valuation/regime information expresses over quarters-to-years, not days.
- **Expected improvement:** large gain in *realized usefulness* (stop acting on noise); no new alpha claimed.
- **Generalization confidence: High** for "don't use at 1w"; **Moderate** for "the 1y edge is real" — it
  could be survivorship/beta (see R5). **Overfitting risk: ~none** (nothing is fitted).
- **When it fails / kill-criterion:** if the 1y rank corr collapses on a survivorship-clean, wider
  universe → the long-horizon edge was an artifact, and the tool has *no* deployable horizon.

### R2 — Validate-then-retire redundant / net-negative models (`relative_strength` first)
- **Problem:** `relative_strength` (and likely `sector`) add noise, not information.
- **Root cause:** redundancy — they re-express momentum/price already in the ensemble.
- **Evidence:** dropping `relative_strength` *improves* accuracy (0.513 vs 0.499); standalone sub-coin.
- **Market phenomenon:** none — that's the point; combining correlated near-zero signals raises variance.
- **Expected improvement:** small, robust denoising (a variance reduction, not a fit).
- **Generalization confidence: Moderate** (LOO CI includes 0; consistent across metrics).
  **Overfitting risk: Low** — a removal, decided by a *pre-registered cross-regime* test, cannot curve-fit forward.
- **Discipline:** this is **not** weight-tuning. The decision rule is declared first — remove only if
  incremental value ≤ 0 across *both* sub-periods *and* bull/bear regimes, not just the aggregate.
- **When it fails / kill-criterion:** if `relative_strength` is net-positive in any major regime, keep it.

### R3 — Post-earnings-announcement drift (PEAD)
- **Problem:** the earnings channel is dormant (8%) and unhelpful; the system misses post-report moves.
- **Root cause:** missing information — surprise is stored but drift is not modeled.
- **Evidence (academic + empirical):** Ball & Brown (1968), Bernard & Thomas (1989) — stocks drift in
  the direction of earnings surprise for ~60 days; one of the most replicated anomalies across decades
  and markets. **Orthogonal** to price/macro (an expectations-outcome effect). Data already held.
- **Expected improvement:** modest incremental at 1m–3m in the post-earnings window specifically.
- **Generalization confidence: Moderate-High** the phenomenon is real; **Moderate** it clears the
  ensemble's incremental bar net of everything. **Overfitting risk: Low-Moderate** (a pre-specified,
  theory-driven signal, not a fitted one) — provided the surprise definition and window are declared first.
- **When it fails / kill-criterion:** PEAD has weakened post-2000 and concentrates in small/illiquid
  names and the first days after the print; if the incremental CI includes 0 in shadow → reject.

### R4 — Unlock the `valuation` model (accumulate PIT fundamentals)
- **Problem:** a whole evidence category is dark.
- **Root cause:** missing information (sparse snapshots).
- **Evidence:** value (cheap−expensive) is a documented long-run premium (Fama-French HML), and it is
  **horizon-matched** to the system's only strength (1y). Cost is mostly *time* (snapshots accrue daily).
- **Generalization confidence: Moderate** — value is real long-run but regime-dependent and endured a
  poor 2010s; the model uses *own-history* (time-series) value, weaker than cross-sectional value.
  **Overfitting risk: Low** (pre-existing model, no new fit).
- **When it fails / kill-criterion:** if, once activated, it shows no incremental 1y value across a full
  cycle → the time-series-value framing is too weak; consider cross-sectional value instead.

### R5 — Diagnose bear-market inversion / "macro = beta" (research question, not a build)
- **Problem:** accuracy inverts below coin-flip in bear markets (0.454); the edge may be long beta.
- **Why it's here:** if the macro signal is just market direction, then R1's 1y edge is *market beta*,
  not skill — and every downstream decision changes. This diagnosis gates the value of R1.
- **Method:** regime-conditional attribution; is macro's contribution ≈ the market's own forward return?
  Beta-adjust the target and re-measure rank corr.
- **Explicitly NOT recommended:** a bear-market "regime gate" as a *fix* — too few bear samples; any
  such gate would overfit the 2022 drawdown. Diagnose, don't patch.

## Stage 5 — Priority matrix (ROI = Δpredictive × Δconfidence × Δexplainability × generalization ÷ complexity)

| Revision | Expected improvement | Confidence | Complexity | Overfitting risk | Priority |
|---|---|---|---|---|---|
| R1 Re-scope to 1y ranking | High (usefulness) | High | Very low | ~None | **1** |
| R2 Retire redundant model | Small–moderate | Moderate | Low | Low | **2** |
| R3 PEAD signal | Modest (native window) | Moderate | Medium | Low–Med | **3** |
| R4 Unlock valuation | Modest (1y) | Moderate | Low (time-gated) | Low | **4** |
| R5 Bear/beta diagnosis | Gates R1 | High (as diagnosis) | Low–Med | N/A | **5** |
| Analyst revisions | High ceiling | Low (data-gated) | High | Medium | 6 |
| Positioning (short int./insider) | Moderate | Moderate | Medium | Medium | 7 |
| Short-term reversal @1w | Uncertain | Low | Medium | Medium-High | 8 |

## Rejected (ruthlessness on display — would NOT bet the fund)

- **Tuning weights / correlation priors** — forbidden; pure in-sample fitting.
- **More technical / momentum / macro variants** — duplicate existing models; audit shows them near-zero.
- **A bear-market regime gate** — tiny bear sample → overfits one drawdown.
- **Re-introducing CPE / analogue** — already rejected OOS; no incremental value.
- **News / sentiment / LLM market predictions** — unverifiable orthogonality, high cost, weak evidence.
- **Any change justified only by improved in-sample/holdout accuracy** — that's the CPE trap.

## Stage 7 — Validation plan (reuse the research framework you built)

Every revision runs as a **shadow experiment** through `mip research experiment`, with a **frozen
pre-registration** before results are seen. Promotion requires **all** of:
- **Must improve:** incremental (combined−baseline) directional/rank metric at the revision's *native
  horizon*, block-bootstrap 95% CI lower bound **> 0**, on the untouched holdout.
- **Must not worsen:** calibration (Brier/ECE), the existing 1y rank correlation, and confidence
  discrimination must stay non-inverted.
- **Regime robustness:** the improvement must not live in a single era or a single symbol (era-blocked
  + per-symbol tables); for R2, net value ≤ 0 required across *both* regimes before removal.
- **Overfitting detection:** design-vs-holdout split; the effect must appear in the design period too,
  and survive dropping the dominant episode/symbol.
- **Magnitude bar:** declare it before running (e.g. incremental rank-corr improvement whose CI clears
  0 *and* whose point estimate exceeds the noise floor observed in the null re-shuffles).
- **Kill switch:** any revision whose incremental CI includes 0, or that degrades a "must-not-worsen"
  metric, is rejected and archived — exactly as the CPE was.

## Implementation roadmap

**Phase 1 — highest-probability, do first (grounded in this system's own evidence):**
- R1 re-scope to long-horizon ranking (+ the survivorship-clean-universe check that validates it).
- R2 pre-registered cross-regime test of `relative_strength` (and `sector`) → retire if net ≤ 0.
- R5 the macro-is-beta diagnosis (gates R1's interpretation).

**Phase 2 — research projects needing validation before trust:**
- R3 PEAD as a shadow experiment. R4 valuation reactivation once fundamentals mature.

**Phase 3 — speculative / data-gated ceilings:**
- Analyst estimate revisions (procure vintage data first). Positioning (short interest, insider).
  Short-term reversal at 1w (only if it survives cost/liquidity realism).

**The fund-manager bottom line:** I would bet on Phase 1 today — it corrects demonstrated defects at
near-zero overfitting risk. I would *fund* Phase 2 as genuine research with real but unguaranteed upside.
I would *not* stake capital on Phase 3 until the data and the shadow validation exist. And I would
refuse any change whose only evidence is that it looked better on history.
