# Next Research Project — Research-Program Decision

Not an implementation plan. The single question: **what one unanswered scientific question limits the
platform's reliability and future improvement more than any other?**

## Stage 1 — Current state of knowledge

### Proven (direct walk-forward evidence)
- Short-horizon (1w–3m) prediction is coin-flip; no directional or ranking skill there.
- The platform's **only** measurable skill is **1-year cross-sectional ranking** (rank corr +0.17, acc 0.54).
- `valuation` is inert (0% activation — data cause); `earnings_behavior` is dormant (8%) and anti-drift when active.
- Three models are a **redundant price cluster** (momentum/relative/sector, corr 0.26–0.37).
- `macro_regime` carries **unique** information (uncorrelated with the cluster) and is **not market beta**
  (its aggregate score has ≈0 correlation with SPY's forward return).
- `relative_strength` is redundant **even at 1y** (removing it barely moves the 1y rank corr).
- Confidence tracks **data volume, not signal** (weak discrimination).
- **Every incremental test is underpowered:** one era (2022–2026), ≈31 survivorship-biased names → CIs
  include zero (the retire-`relative_strength` test could not clear the bar for this reason).

### Probable (evidence-supported, unconfirmed)
- `relative_strength` is mildly contrarian-mistimed (−0.287 vs SPY forward, one era).
- The system is fundamentally a long-horizon tool. Removing redundant price copies is ~free.

### Hypotheses (plausible, unproven)
- **The 1-year edge is genuine slow information** (sector/rate regimes paying off), **OR**
- **The 1-year edge is market beta + survivorship drift** — "bullish-rated" stocks simply rode a
  recovering, survivor-only sample up over a year. ← the central unresolved fork.
- Short-horizon is *unbeatable* (efficiency) rather than merely *unbeaten so far*.

### Unknowns (open scientific questions)
- **U1 — Is the 1-year edge real information or beta/survivorship artifact?** (the only skill; cause unknown)
- **U2 — Do any conclusions generalize beyond the survivorship-biased, single-era, ~31-name sample?**
  (measurement validity — the reason everything is underpowered)
- U3 — Is `relative_strength`'s contrarian-mistiming stable across eras?
- U4 — Does confidence contain any exploitable signal, or is it pure volume?
- U5 — Is short-horizon genuinely unpredictable to this information set, or just unbeaten?
- U6 — Would orthogonal families (PEAD, revisions, positioning) clear the incremental bar?

**U1 and U2 are the same question viewed two ways:** we cannot tell if the 1-year edge is real
*because* the evaluation universe is survivorship-biased, single-era, and underpowered. Resolving one
requires resolving the other.

## Stage 2 — Ranked unknowns

| # | Unknown | ↑Understanding | ↑Reliability | ↓Impl. risk | Cost | False-discovery risk | Depends on |
|---|---|---|---|---|---|---|---|
| **U1/U2** | 1y edge: real vs beta/survivorship (+ sample validity) | **High** | **High** | **High** | Low–Med | **Low** (a falsification/decomposition) | none |
| U3 | RS mistiming stable across eras | Med | Low–Med | Med | Low | Med | U1/U2 (power) |
| U4 | Confidence contains signal? | Low–Med | Low | Low | Low | Med | U1 (moot if base has no edge) |
| U6 | Orthogonal families add value? | High *ceiling* | Med | Med | High (needs data) | High | U1 (don't build on an artifact) |
| U5 | Short-horizon unbeatable vs unbeaten | Med | Low | Low | Med | Med | — (low production value) |

## Stage 3 — The one project

**Selected: U1/U2 — Is the platform's only measured edge (1-year ranking) genuine predictive
information, or is it explained by market beta and survivorship in a single bull-recovery sample?**

Every alternative waits because every alternative *depends on this answer*:
- Retiring `relative_strength` (U3), assessing confidence (U4), and adding orthogonal signals (U6) all
  presuppose the base system has a real edge worth refining. **If the 1-year edge is an artifact, all of
  them are optimizing sand** — and the underpowered CIs that blocked the RS decision are themselves a
  symptom of the same sample problem this question confronts.

## Stage 4 — Decision analysis

- **Why the uncertainty exists:** the evaluation universe is the *current* instrument set (survivors
  only), *one* regime (2022–2026 recovery), and *tiny* (≈31 names). The +0.17 1-year rank corr is
  therefore confounded by survivors rising, beta in an up-market, and small-n noise — three confounds
  the current apparatus cannot separate.
- **Why prior work couldn't resolve it:** every phase reused the same captured walk-forward on the
  biased universe. Root-cause analysis refuted *macro*-as-beta but could not test whether the *ensemble's*
  1-year edge is beta (the 1y bootstrap was degenerate; no beta-neutral target; no delisted names). The
  revision framework hit the identical wall (CIs straddling zero).
- **Production decisions that depend on the answer:** whether to trust/deploy the 1-year ranking at all;
  whether the seven-model architecture is worth continued investment; whether *any* revision's measured
  "improvement" is real.
- **What should be blocked until it's resolved:** retiring models, building any new signal (PEAD,
  valuation, positioning), and promoting *any* revision to production.
- **Incorrect decisions likely if it stays unanswered:** promoting revisions that merely fit a beta
  artifact; deploying the 1-year ranking as skill when it may be beta (it will fail live); and killing
  genuinely useful models on the basis of underpowered tests.

## Stage 5 — What would answer it (without designing the experiment)

- **Conclusive:** the 1-year rank correlation (a) remains materially positive on a survivorship-free,
  multi-regime, adequately-powered universe, **and** (b) survives replacing the target with the
  **beta-neutral residual return**, **and** (c) shows a bootstrap CI excluding zero → the edge is **real
  information**. The mirror result → **artifact**.
- **Partial:** the edge persists on a broader/longer universe but cannot be cleanly beta-decomposed →
  "generalizes, cause unresolved."
- **Unresolved:** still only the current biased/underpowered universe → nothing learned.
- **How it reshapes priorities:** if **real** → the roadmap unlocks with a *trustworthy* bar (retire RS
  with power; test orthogonal families against a genuine baseline). If **artifact** → the program pivots
  entirely: the current information set has no demonstrated edge, and no amount of model-work fixes that.

*(Note: the beta-decomposition arm is answerable now from data already in the platform — a beta estimate
from existing price history — with no new models or data. The survivorship/power arm is the harder
generalization test. This is a property of the question, not an implementation recommendation.)*

## Stage 6 — Research value

| Dimension | Estimate |
|---|---|
| Increase in understanding | **High** — resolves whether the platform has any real edge |
| Increase in reliability | **High** — makes every future metric trustworthy |
| Reduction in research risk | **High** — stops us optimizing an artifact |
| Long-term value | **Foundational** — gates the entire roadmap |
| Research cost | **Low–Medium** (analysis-heavy; beta arm needs no new data/models) |
| Duration | ~weeks |
| Confidence in recommendation | **High** |

## Executive summary & research recommendation

**Next project — the only one I would fund with a single month:** determine whether the platform's
1-year ranking edge is **genuine predictive information or a beta/survivorship artifact.** It is the
highest-value question because it targets the system's *only* measured skill, it is the *root cause* of
why every incremental test is underpowered and untrustworthy, and it has **no dependencies** while
*everything else depends on it*. Its false-discovery risk is low (it is a falsification, not a search
for a new effect), and its most important arm costs nothing new to run.

**What becomes easier once it's answered:** if the edge is real, every subsequent revision (retire
redundant models, test orthogonal families) can finally be judged against a *trustworthy* baseline with
adequate power — the retire-`relative_strength` question, for instance, becomes decidable. If the edge
is an artifact, the team is spared months of building models onto a foundation that was never there, and
the program correctly redirects from *accumulating features* to *establishing a genuine, generalizable
information advantage*. Either outcome is decisive; ambiguity here is the single greatest tax on the
platform's future.
