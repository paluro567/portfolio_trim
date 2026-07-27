# Root-Cause Investigation — Why the Trim System Behaves As Observed

Evidence: discriminating experiments on the captured walk-forward (2022+ holdout, per-model scores +
realized outcomes). Where I could design an experiment to separate hypotheses, I ran it. **Two prior
hypotheses were refuted by the data and are corrected below** — that is the point of the exercise.

## The six experiments and what they showed

| Exp | Question | Result |
|---|---|---|
| **E1** cross-sectional score dispersion (1m) | Does macro give every stock the same call (beta) or differentiate? | All models differentiate (std 21–26/100); macro 23.6 — **not** uniform |
| **E2** cross-model score correlation | Which models carry the *same* information? | **Price cluster: momentum↔relative 0.37, sector↔relative 0.36, momentum↔sector 0.26.** Macro ≈ **uncorrelated** with all (≤0.07, −0.14 vs earnings) |
| **E3** standalone rank-corr by horizon | Is any model inverted short-horizon; where does signal live? | At **1y** sector +0.175, rates +0.135, momentum +0.108, relative +0.072 turn positive; **macro is flat (+0.04) at all horizons**; earnings goes *more negative* with horizon |
| **E4** accuracy by regime (1m) | Do models fail only in bear? | macro 0.559 bull / 0.478 bear; rates 0.502 / 0.430; relative 0.477 / 0.481 (fails in *both*) |
| **E5** absolute vs SPY-relative acc (1m) | Is the edge market-timing (abs) or selection (rel)? | For every model **acc_abs ≈ acc_rel** (macro 0.521/0.524) — neither |
| **E6** date-mean score vs SPY forward return | Is a model a market-timing/beta proxy? | **macro +0.015 (≈0 — NOT beta)**; **relative_strength −0.287 (contrarian-mistimed)**; rates −0.127 |

## Corrections to my prior interpretation (intellectual honesty)

- **REFUTED: "macro_regime is market beta."** E6 shows macro's aggregate score has **zero** correlation
  with SPY's forward return (+0.015) — it does *not* time the market. E1 shows it differentiates stocks;
  E5 shows it's no better at absolute than relative. Macro's small edge is **genuine orthogonal
  stock-level information, not beta.** (This closes the R5 question from the revision plan.)
- **WEAKENED: "momentum is inverted (reversal) at 1w."** Its 1w rank-corr is −0.039 — weak noise, not a
  clean sign flip. Momentum is **redundant + near-zero**, not decisively inverted.

## 1. Root-cause report (per model)

- **macro_regime — the only *unique* predictor.** *Why it's the only incremental contributor:* E2 —
  it is the sole model uncorrelated with the redundant price cluster, so it's the only one adding
  information the others don't already have; E6 — it's not beta; E1 — it differentiates stocks. Its edge
  is small but real and **horizon-stable** (E3: ~+0.04 at every horizon). Confidence: **High.**
- **relative_strength — net-negative for *two* reasons.** *Why:* (a) redundancy — E2 shows it is the
  most correlated model in the price cluster (0.37 w/ momentum, 0.36 w/ sector), i.e. a third copy of
  price information; (b) it is **mildly contrarian-mistimed** — E6: when it is collectively bullish the
  market falls next month (−0.287). It chases strength into tops. Confidence: **Moderate-High.**
- **momentum_exhaustion — redundant noise.** *Why:* E2 places it in the price cluster; E3 shows ~0
  rank-corr at short horizons (no clean reversal). It contributes little unique information.
  Confidence: **Moderate.**
- **sector_rotation — redundant.** *Why:* E2 — correlated with momentum (0.26) and relative (0.36);
  same price/relative-return information. Confidence: **Moderate.**
- **earnings_behavior — low activation *and* anti-drift.** *Why:* it fires only ~8% of the time (post-
  report window), and when it fires its rank-corr is negative and **worsens with horizon** (E3:
  −0.06→−0.13). It reads the post-earnings state but its directional call fades moves that then
  continue — i.e. it is missing the *drift*, not capturing it. E4's 0.679 "bull-bear" gap is a 28-sample
  artifact, not signal. Confidence: **Moderate.**
- **valuation — inert.** *Why:* ~1 point-in-time fundamentals snapshot → 0% activation. Unambiguous
  data cause. Confidence: **High.**
- **Confidence only weakly discriminates.** *Why:* confidence = volume × agreement. Volume comes from
  the always-active, long-history models (macro/rates) — but **sample size ≠ signal** here; and E2 shows
  genuine cross-model agreement is rare except inside the price cluster (whose agreement carries no
  information). So confidence tracks *data abundance*, not *predictive edge*. Confidence: **Moderate-High.**
- **Short-horizon collapse.** *Why:* E5 — no model beats coin-flip on absolute *or* relative at 1m;
  E6 — the price models are mildly contrarian-wrong. Short-horizon stock returns are simply
  **efficient/noise to this slow information set.** Not a combination flaw. Confidence: **High.**
- **1-year strength.** *Why (and the key open question):* E3 — the edge at 1y is carried by
  **sector/rates/momentum turning positive**, *not* macro. Two live explanations remain:
  (a) real slow effects (sector/rate regimes, short-term-contrarian-then-trend) paying off over a year;
  (b) **beta/survivorship drift** — bullish-rated stocks simply rode the 2022–2026 recovery in a sample
  that ended higher. **These are not yet separated.** Confidence in *cause*: **Low — this is the
  central unresolved question.**

## 2. Information architecture (the dependency map)

```
        PRICE / RELATIVE-RETURN CLUSTER            INDEPENDENT SIGNALS
        (mutually correlated 0.26–0.37,            (≈ uncorrelated with the cluster
         collectively redundant, ~coin-flip)        and with each other)

        momentum_exhaustion ─┐                      macro_regime   ← UNIQUE + predictive (small, real)
        relative_strength  ──┼─ same info           interest_rate  ← semi-independent, weak
        sector_rotation    ─┘  (relative worst:      earnings       ← independent, low-activation, anti-drift
                               contrarian-mistimed)   valuation      ← independent but DARK (no data)
```

- **Redundant information:** the price cluster — three models expressing one thing. Adding the third
  (relative_strength) *subtracts* value (correlated noise + mistiming).
- **Unique information:** macro (and, faintly, rates). Macro is the only unique-and-predictive channel.
- **Blind spots (information that never reaches the score):** valuation (dark), earnings *drift* (state
  captured, drift not), and everything genuinely orthogonal the system doesn't ingest (expectations
  revisions, positioning, options) — but those are out of scope for *this* explanatory phase.

## 3. Failure taxonomy

| Failure | Category | Root cause (evidenced) |
|---|---|---|
| 1w–3m coin-flip | **Market efficiency / horizon** | slow info set vs efficient short-horizon cross-section (E5, E6) |
| relative_strength net-negative | **Redundant + mistimed information** | price-cluster copy (E2) + contrarian at tops (E6) |
| bear-market inversion | **Conditional/mistimed signal** | price/rates models mildly contrarian; macro fades in bear (E4, E6) |
| earnings unhelpful | **Delayed/incorrect information use** | captures post-earnings state, misses drift; anti-predictive at horizon (E3) |
| valuation silent | **Missing information** | no PIT fundamentals |
| confidence weak | **Volume ≠ signal** | confidence tracks data abundance, not edge |

**Common thread:** the system's failures are overwhelmingly **redundancy + market efficiency**, not a
plumbing defect. Three of seven models are one information source; one is dark; the genuine edge is a
single small orthogonal channel (macro) plus a long-horizon effect whose *cause is unproven*.

## 4. Ranked research opportunities (understanding × P(improves correctness) ÷ cost)

1. **Decompose the 1-year edge: real slow information vs beta/survivorship drift.** Highest
   understanding-per-cost; it determines whether the system has *any* genuine edge. Cheap (existing
   framework + a survivorship-clean universe + beta-adjusted 1y target + 1y abs-vs-rel).
2. **Confirm relative_strength's contrarian-mistiming across eras** (is E6's −0.287 stable or
   2022-specific?). Cheap; decides the retire question.
3. **Characterize why macro is orthogonal-yet-small** — what does macro actually key on that the price
   models don't, and is its edge stable out of the 2022–2026 regime? Cheap.
4. **Diagnose earnings anti-drift** — does the model fade genuine PEAD? (compares the model's post-
   earnings call to the realized drift). Cheap, and informs any future earnings work.

(These are *research* questions — understanding — not builds.)

## 5. Final recommendation — the ONE project I would fund

**Fund #1: decompose the 1-year edge into real information vs beta/survivorship drift.**

**Why:** it is the only horizon at which the system shows *any* skill (rank-corr +0.17), and E3 just
showed that edge is carried by the price/sector/rate models — the same models that are near-zero-to-
negative at short horizons and mildly *contrarian* (E6). That pattern is exactly what **market beta in
a recovering, survivorship-biased sample** would produce: "bullish-rated" ≈ "rode the up-market for a
year." Until this is separated, **we do not know whether the platform has a genuine edge or is a
dressed-up long-beta tilt** — and every downstream decision (what to build, what to retire, whether to
trust the 1y ranking) hinges on the answer. It is also the cheapest decisive experiment available.

**Why not the others:**
- *Retire relative_strength / build PEAD / unlock valuation* — all presuppose the system has a real
  edge worth improving. If the 1y edge is beta, we'd be adding signals to a beta machine — wasted
  capital. Sequence demands the decomposition first.
- *Macro-is-beta* — **already answered** (E6: macro is not beta). No longer worth funding.
- *Short-horizon fixes* — the evidence (E5/E6) says short-horizon is efficient to this information set;
  more research there buys little understanding.

**The scientific bottom line:** the system behaves as observed because **it holds one small piece of
unique predictive information (macro), two-and-a-half redundant copies of price information (one of
which is contrarian-mistimed), one dark model (valuation), and one mis-used model (earnings) — and its
only measurable skill sits at a horizon whose cause (real vs beta) is still unproven.** Resolve that
last unknown before anything is built.
