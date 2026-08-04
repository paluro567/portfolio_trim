# Falsification of the Readiness Review — What Would Change My Recommendation

**Purpose:** not another recommendation. The minimum evidence set that would overturn
[PROJECT_READINESS_REVIEW.md](PROJECT_READINESS_REVIEW.md), plus a decision table binding every
experimental outcome to exactly one decision.

---

## Correction to my own prior review (stated first, because it reshapes everything below)

My prior review — and `ONEYEAR_DECOMPOSITION.md` §6 before it — concluded that free data has reached
its scientific limit. That conclusion was derived from the minimum-detectable-effect analysis for an
**absolute** IC. **It does not transfer to paired comparisons**, and the project's own artifacts show
the gap:

| Test | Estimate | 95% CI | Implied SE |
|---|---|---|---|
| Absolute IC (beta-residual, 1y) | +0.092 | [−0.002, +0.211] | **≈ 0.054** |
| **Paired** delta (retire-`relative_strength`, 1m) | +0.020 | [−0.005, +0.039] | **≈ 0.011** |

A paired test on identical `(symbol, date)` cells cancels the common era, market, concentration, and
shared-survivorship components. The project already achieved **~5x better power** this way without
noticing it was a general capability.

**Consequences, and their limits:**

- A class of decisive question **is** answerable on existing free data: *"is system A better than
  system B on the same sample?"*
- It is **asymmetric.** A paired test can produce a decisive **negative** about the architecture. It
  **cannot** produce a decisive **positive** about signal existence — it compares two systems, it
  does not establish either is better than zero.
- **Residual caveat:** paired designs cancel only the *common* bias. If the ensemble and a trivial
  baseline are *differentially* exposed to survivorship, the delta is still biased — though for two
  price-based systems on identical names, differential bias is far smaller than level bias.

That asymmetry is exactly what a readiness review wants: **it can kill cheaply.** It is the reason
two of the three experiments in Part 5 cost nothing and require no purchase.

---

## PART 1 — The Assumptions That Drove the Rejections

Every rejection in the prior review rests on a named, falsifiable assumption. Listed with the
decision each one carries.

| # | Assumption | Carries the rejection of |
|---|---|---|
| **A1** | A **REST-native, survivorship-clean substitute exists** at comparable cost and adequate quality | Norgate (vendor choice) + Windows VM |
| **A2** | The **existing provider abstraction is adequate for a real vendor**, so only a thin adapter is needed | The months-long ingestion framework |
| **A3** | **Confidence is independently testable** — its defect is construct design, not absent skill | Funding confidence redesign *now* rather than after the purchase |
| **A4** | **The existing data cannot discriminate** between the ensemble and simpler alternatives | Feature engineering + model development |
| **A5** | The **reporting layer's value is testable without predictive skill** | Funding explainability validation *now* |
| **A6** | **Engineering time is the scarce resource**, worth more than ~$600 | The VM *and* the framework (the $1.50–3.00/hr argument) |
| **A7** | **~500 names × 20y actually achieves SE ≤ 0.02** | The data purchase itself (approval, not rejection) |
| **A8** | **Norgate genuinely has no non-VM delivery path** | Windows VM (specifically the *ongoing* form) |

**A4 is now known to be partly false** — see the correction above. That is already a self-inflicted
reversal on the strongest of the rejections, and it is why E-B below exists.

---

## PART 2 — Assumption-by-Assumption Falsification

### A1 — A REST-native survivorship-clean substitute exists

- **Supporting evidence:** `PHASE2_DESIGN.md` Stage 3 rates Sharadar (SEP/SF1/TICKERS via Nasdaq Data
  Link): survivorship *"Free"*, delisting returns *"Yes (SEP delisting)"*, PIT integrity *"Strong,
  dated"*, delivery *"REST + bulk export"*, integration **"Easy (clean API/bulk)"**, and designates
  it **"Primary-alt."** Also rated the *best* source for PIT market cap — which Norgate supplies only
  *"via shares (partial)."*
- **Missing evidence:** Stage 3 was a **desk evaluation, not a data inspection.** Nobody has
  verified: current price; the actual count of delisted securities; whether delisting *returns* are
  populated or NULL for most delisted names; history depth; and the *semantics* of terminal values
  (acquisition cash vs −100% vs unknown). The disqualifying axis has never been checked against
  actual rows.
- **Experiment: E-C.** Pull the free sample / trial tier. Count distinct securities with a delisting
  date; measure the **fraction of those with a non-NULL terminal value**; confirm earliest date;
  record real annual price for the minimum adequate bundle.
- **Reversal condition:** delisted coverage absent or thin, **or** > ~20% of delisted names carry no
  terminal value, **or** history < 15 years, **or** price > ~2x Norgate's → **A1 is false. Norgate
  becomes the only adequate vendor, and the VM stops being a luxury and becomes the price of
  admission.** Reverse to approving Norgate.

### A2 — The existing abstraction is adequate for a real vendor

- **Supporting evidence:** verified in code — `SecuritySource` and `OutcomeSource` Protocols with
  frozen DTOs (`SourcePriceBar`, `SourceMarketSnapshot`, `SourceBenchmarkBar`, `SourceTerminal`),
  `FixtureSource`/`FixtureOutcomeSource`, `blocked_source()`/`blocked_outcome_source()`; 25 green
  native-outcome integration scenarios; the Phase 1 pattern already proved the shape once.
- **Missing evidence:** **zero real vendors have ever passed through it.** "Tested against a fixture
  we designed" is materially weaker than "tested against a vendor's actual data shape" — the fixture
  cannot surprise its author.
- **Experiment: E-E.** Write one thin adapter against free-tier vendor data; run the shipped Phase 2A
  path end-to-end (ingest → forward returns → snapshot checksum). Timebox **3 days, hard stop.**
- **Reversal condition:** if real data forces **structural** DTO change (not field additions) — e.g.
  the terminal-value model cannot express the vendor's delisting semantics, or PIT market data
  arrives on an incompatible grain — then A2 is false and a **bounded 2–3 week** adapter/normalization
  investment is justified. *This is a partial reversal only:* it never justifies "months of
  provider-independent framework," because the correct time to generalize is after the **second**
  real integration, not the first.

### A3 — Confidence is independently testable

- **Supporting evidence:** three independent observations — volume-not-signal in production,
  **inversion** in the CPE (high-conf 1m 0.529 < low-conf 0.584), structurally dead in the analogue
  (`agreement ≡ 1.0`). The CPE also found the edge concentrated in *sparse* cells (effN 10–20 →
  0.60 acc; 20–40 → 0.47), i.e. confidence points away from where accuracy lives.
- **Missing evidence — and a logical flaw in my prior review I should own:** calibration requires
  something to calibrate *to*. If base-rate accuracy is 50% everywhere, then high-conf 50% /
  low-conf 50% is the **correct** behavior of a confidence measure on a skill-free predictor, not a
  broken construct. **So A3 depends on A4/U1 unless the inversion is real.** Inversion is the
  loophole: a pure-noise confidence over a pure-noise predictor produces no *consistent ordering*.
  A reproducible inversion implies local skill structure being actively mis-pointed — which is
  diagnosable without a global edge.
- **Experiment: E-D.** Re-analysis only, on the committed captured walk-forwards. Test whether the
  inversion **replicates** across models, horizons, and both studies (analogue + CPE), with a paired
  high-vs-low-confidence delta and a block-bootstrap CI.
- **Reversal condition:** if the inversion does **not** replicate — confidence is flat/noisy rather
  than inverted — then A3 is false, the confidence question **collapses into U1**, and confidence
  redesign should be **demoted from "proceed now" to "delayed behind the purchase."** That reverses
  one of only three approvals in my prior review.

### A4 — Existing data cannot discriminate between the ensemble and simpler alternatives

- **Supporting evidence:** the absolute-IC MDE analysis; four phases with zero promotions.
- **Missing evidence — this assumption is now known to be partly false.** The paired-design power
  gain (SE 0.054 → 0.011) was never applied to the question that actually matters for
  feature/model investment: **does the 9-model ensemble beat trivial baselines?** That comparison has
  never been run, at any power, on any data. It is a paired test. It is free.
- **Experiment: E-B.** On the committed captured walk-forward, paired per-cell comparison of the
  official ensemble against: (a) always-neutral, (b) 12-1 momentum, (c) a single-factor
  market-relative sort, (d) equal-weight of the 7 models. Block-bootstrap the paired deltas by year.
- **Reversal conditions — in both directions:**
  - **Ensemble LOSES** to any trivial baseline with a CI excluding zero → **stronger** rejection of
    feature/model work, and it converts "refactor the methodology" from a hypothetical into the
    active decision. Also re-scopes the purchase: test the *baseline*, not the ensemble.
  - **Ensemble WINS** with a CI excluding zero → **A4 is false in the most consequential direction.**
    First positive result in the project's history. The architecture has demonstrable value, the
    freeze on model development should be **partially lifted**, and the data purchase becomes
    materially more valuable.
  - **TIE** → A4 holds; the freeze stands.

### A5 — The reporting layer's value is testable without predictive skill

- **Supporting evidence:** the layer exists and is unusually complete — an exact attribution
  invariant, structured `unknowns` with distinct kinds, provenance-carrying theses, committed
  institutional examples for AMD/NVDA/SPCX.
- **Missing evidence:** any human contact whatsoever. And a specific confound: **self-assessment by
  the author is heavily biased** — "I find this interesting" is not "this changed my decision."
- **Experiment: E-F (slow) / E-F′ (fast, weaker).**
  - **E-F:** pre-committed decision log. For each of N ≥ 15 real portfolio decisions, record the
    intended action **before** reading the report and **after**; count changed decisions and whether
    the change is attributable to a *named* report section. 2–4 weeks calendar, ~0 engineering.
  - **E-F′:** retrospective audit against the archived predictions and existing examples — would the
    reports' stated reasoning have implied different actions than a naive rule? Instant, but
    **materially weaker** (no counterfactual, full hindsight contamination).
- **Reversal condition:** 0 of N decisions changed → A5 is false in the sense that matters, U3 is
  negative, and **a negative U1 escalates from "pivot" to full termination (S6).** Conversely, ≥ 1/3
  of decisions changed with attributable sections → the project has a product independent of any
  edge, and the entire investment case stops depending on U1.

### A6 — Engineering time is the scarce resource

- **Supporting evidence:** none in the repository. This is an assumption about the **owner**, not the
  code. It is the load-bearing premise of the "$1.50–3.00/hour" argument that rejected both the VM
  and the framework.
- **Missing evidence:** whether building is instrumentally or intrinsically valuable here.
- **Experiment: none exists.** **No experiment can test this — it requires the owner to state it.**
  This is the most likely-wrong and least-testable assumption in the review, so it is stated as a
  direct question rather than dressed as an inference.
- **Reversal condition:** if building is intrinsically valuable and time is not scarce, the
  opportunity-cost argument collapses. The VM and framework rejections weaken to *"costs cash, buys
  no information"* — still true, but no longer disqualifying. **The correct decision rule would then
  shift from "minimize engineering" to "minimize cash and maximize what is interesting to build,"
  which is a legitimately different program.** I cannot make that call.

### A7 — ~500 names × 20y achieves SE ≤ 0.02

- **Supporting evidence:** my own scaling arithmetic — SE ∝ 1/√(Y×n_eff); with ρ ≈ 0.02 residual
  cross-correlation, n_eff ≈ 46, giving SE ≈ **0.021** against a self-declared 0.02 requirement.
- **Missing evidence:** **ρ was assumed, not measured.** It is estimable *today* from the existing
  78-name panel — a cross-sectional correlation needs breadth, not clean history, and 78 survivors
  are adequate for estimating it. Nobody has done this. **The entire purchase rests on an unmeasured
  parameter that is free to measure.**
- **Experiment: E-A.** Estimate average pairwise residual-return correlation from the existing panel
  (after beta and sector neutralization) at each horizon. Plug into effective breadth
  `n/(1+(n−1)ρ)`. Bootstrap synthetic panels at (n=500, Y=20) to get the *achieved* SE and the
  minimum detectable IC. Report the universe size required for SE ≤ 0.02 with margin.
- **Reversal condition:** if projected SE > 0.03 even at 500×20, and no attainable universe reaches
  ≤ 0.025 → **A7 is false, the purchase cannot clear the project's own bar, and the correct decision
  is to reject the purchase and terminate the prediction program** — invoking stop condition S4
  pre-emptively, for one day of work instead of $600 plus three weeks plus a season.

### A8 — Norgate has no non-VM delivery path

- **Supporting evidence:** its distribution is a Windows-oriented local updater (NDU) that the Python
  API reads from; the appearance of "Parallels" on the investment list implies the owner reached the
  same conclusion.
- **Missing evidence:** never actually investigated. Untested alternatives: a **one-time cloud
  Windows instance** (~$5–20 for a few hours) to produce a 20-year bulk export; a vendor-side direct
  download; CrossOver/Wine. A research corpus is a *bulk historical export*, not a daily live feed —
  it needs to be produced **once**, not maintained.
- **Experiment: folded into E-C.** Read the vendor's actual delivery/export documentation and licence
  terms on bulk export and retention.
- **Reversal condition:** if a one-time bulk export is feasible → **"Parallels + maintain a Windows
  VM" is a false dichotomy.** Approve a ~$20 one-time cloud export; keep the Parallels rejection.
  This is a partial reversal that reinstates Norgate as a viable vendor while still rejecting the
  ongoing VM.

---

## PART 3 — Decision Table

A full cross-product of six experiments is 2⁶ cells and useless. The table is therefore
**hierarchical**: gates are ordered by how decisively they dominate, so each outcome maps to exactly
one decision, and later gates are only reached when earlier ones do not already decide.

### Gate 1 — E-A: can the measurement *ever* clear the bar?

| Outcome | Decision |
|---|---|
| **A1.** Projected SE ≤ 0.020 at an attainable universe | → **Proceed to Gate 2** |
| **A2.** SE 0.020–0.030, but ≤ 0.025 reachable at a broader attainable universe | → **Proceed to Gate 2, with the universe floor raised to that size as a purchase condition** |
| **A3.** SE > 0.030 at every attainable universe | → **TERMINATE THE PREDICTION PROGRAM.** No purchase, no VM, no framework. Invoke S4 pre-emptively. Retain the harness and proceed to E-F to decide whether the reporting product survives |

### Gate 2 — E-B: does the architecture beat trivial baselines on data already held?

| Outcome | Decision |
|---|---|
| **B1.** Ensemble **beats** all trivial baselines, paired CI excluding zero | → **PURCHASE at the best attainable quality** (proceed to Gate 3). **Partially lift the model-development freeze.** First positive result in the project's history — it raises the value of everything downstream |
| **B2.** **TIE** — paired CIs include zero against all baselines | → **Proceed to Gate 3.** Purchase gated on vendor. Freeze on features/models **stands** |
| **B3.** Ensemble **loses** to any trivial baseline, paired CI excluding zero | → **REFACTOR THE METHODOLOGY.** Retire the 9-model ensemble as the primary system; install the winning simple baseline as the new null and the new candidate. Re-scope any purchase to test *that*. Keep the harness, the archive, and the reporting layer. This is distinct from termination: the apparatus is vindicated, the models are not |

### Gate 3 — E-C: which vendor, at what true total cost?

| Outcome | Decision |
|---|---|
| **C1.** REST-native vendor adequate (delisted coverage + terminal values + ≥15y) at ≤ ~2x Norgate | → **PURCHASE THE REST VENDOR.** Reject Parallels and the VM. *(Prior recommendation confirmed.)* |
| **C2.** No adequate REST vendor, but Norgate bulk export is feasible without a maintained VM | → **PURCHASE NORGATE + a one-time ~$20 cloud export.** Reject Parallels. *(Partial reversal.)* |
| **C3.** No adequate REST vendor **and** Norgate genuinely requires a maintained Windows VM | → **REVERSE: APPROVE NORGATE + PARALLELS + VM.** With Gate 1 passed and Gate 2 not lost, the measurement is worth having and the VM is the price of admission, not a luxury |
| **C4.** No affordable vendor clears the survivorship/delisting-return axis at all | → **TERMINATE THE PREDICTION PROGRAM.** There is no affordable path to an adequate instrument; the question is permanently unanswerable at this budget |

### Secondary gates (refine a branch; never override Gates 1–3)

| Experiment | Outcome | Decision |
|---|---|---|
| **E-D** confidence inversion | Replicates across models/horizons | Confidence redesign **stays funded now** *(prior recommendation confirmed)* |
| | Does not replicate — flat, not inverted | **Demote confidence redesign to "delayed"** behind the purchase; it collapses into U1 |
| **E-E** real-vendor adapter smoke test | Passes within 3 days | Adapter cost confirmed at days. **Framework rejection stands** |
| | Requires structural DTO change | Approve a **bounded 2–3 week** normalization layer. Framework-as-months **still rejected** |
| **E-F** decision log | ≥ 1/3 of decisions changed, attributable | Reporting layer is a **product**. Investment case no longer depends on U1; a negative U1 becomes a **pivot** |
| | 0 of N changed | U3 negative. A negative U1 becomes **FULL TERMINATION** (S6) |

**Coverage check:** Gate 1 has three mutually exclusive outcomes covering the real line of projected
SE. Gate 2 has three covering {beats, indistinguishable, loses}. Gate 3 has four covering
{REST works, Norgate-without-VM, Norgate-with-VM, nothing works}. Every path terminates in exactly
one of: *purchase REST*, *purchase Norgate no-VM*, *purchase Norgate + VM*, *refactor methodology*,
*terminate prediction program*, *full termination*.

---

## PART 4 — Experiments Ranked by Expected Value of Information

All estimates are judgments, stated as such. "Uncertainty reduction" is against the assumption each
experiment targets. **Every experiment in the top four costs $0 and uses data already committed to
the repository.**

| Rank | Experiment | Targets | Time | Cash | Uncertainty reduction | P(changes direction) | EVI |
|---|---|---|---|---|---|---|---|
| **1** | **E-C — vendor due diligence** (delisted row counts, terminal-value fill rate, depth, real price, bulk-export/licence terms) | A1, A8 | **~4 hrs** | $0 | **~90%** on the vendor question — replaces a desk evaluation with row counts | **~30%** | **Highest.** Best EVI *per hour* in the set. Can reinstate Norgate, kill the VM, or reveal no adequate vendor exists — before any money moves |
| **2** | **E-A — power feasibility simulation** (measure ρ from the existing 78-name panel; bootstrap achieved SE at 500×20) | A7 | **~1 day** | $0 | **~85%** on whether the purchase can work at all | **~25%** | **Very high.** A one-day pre-mortem on a $600 + 3-week + one-season commitment. The purchase currently rests on an *assumed* ρ that is free to measure |
| **3** | **E-B — trivial-baseline paired comparison** (ensemble vs always-neutral / 12-1 momentum / single-factor sort / equal-weight, paired, year-blocked) | A4 | **~2 days** | $0 | **~60%** on architecture justification. Asymmetric: can be decisively negative, cannot be decisively positive about signal | **~35%** | **Very high.** Highest single probability of changing direction. Tests the never-tested question, using the 5x-better-powered design the project already demonstrated |
| **4** | **E-D — confidence inversion replication** (paired high-vs-low-conf delta across both captured studies) | A3 | **~1 day** | $0 | **~70%** on whether confidence is independently fundable | **~20%** | **High.** Cheap; can demote one of only three approvals |
| **5** | **E-E — real-vendor adapter smoke test** (one thin adapter, free tier, end-to-end through Phase 2A) | A2 | **~3 days** (hard timebox) | $0 | **~75%** on adapter cost | **~15%** | **Medium-high.** Also a prerequisite for the purchase, so its cost is not additive |
| **6** | **E-F — explainability decision log** | A5 | **2–4 wks calendar**, ~0 eng | $0 | **~80%** on U3 | ~25%, but only inside the terminate branch | **Medium.** High value, poor latency → **run in parallel as background; never gate on it** |
| **7** | **E-F′ — retrospective report audit** | A5 (weakly) | ~4 hrs | $0 | **~25%** — hindsight-contaminated, no counterfactual | ~10% | **Low.** Only worth running if E-F is not executable |
| **—** | *The purchase itself + the U1 experiment* | U1 | ~3 wks + 22x compute | ~$600–800 | ~75% on U1 | high | **Not ranked here** — it is the decision the ranked experiments exist to gate |

**Two structural observations:**

- The top four experiments cost **$0** and total **~4.5 days**. None requires the purchase, the VM,
  or any new engineering.
- **Every one of the top four can produce a decision that saves the purchase entirely.** That is the
  definition of high EVI in a readiness review: cheap tests that can stop expensive commitments.

---

## PART 5 — The Smallest Possible Research Plan

> *"What are the next three experiments that will most increase confidence that the project is — or
> is not — worth further investment?"*

### Total: ~4 days, $0, zero new infrastructure. All three run on data and code already committed.

### Experiment 1 — E-C · Vendor due diligence *(~4 hours)*

**Question:** does an adequate survivorship-clean source exist on a delivery path that does not
require a maintained Windows VM, and at what real price?

**Method:** pull the free/sample tier of the candidate REST vendor. Report four numbers and two
facts: count of securities with a delisting date; **fraction of those with a non-NULL terminal
value**; earliest date; real annual price for the minimum adequate bundle; plus the licence position
on (a) bulk export and (b) retaining downloaded history after lapse. Separately, read the Norgate
delivery documentation for a one-time bulk-export path.

**Why first:** highest EVI per hour in the set, and it is the **only** experiment whose outcome can
reinstate a vendor I rejected. It also resolves the two assumptions (A1, A8) that carry the largest
*cash-and-months* consequences. Cheapest possible way to find out whether the argument I made against
the VM was even applicable.

**Engineering required:** none. One API pull and two documents.

### Experiment 2 — E-A · Power feasibility simulation *(~1 day)*

**Question:** at an attainable universe, does the purchase reach SE ≤ 0.02 — the project's own
declared requirement?

**Method:** from the existing 78-name panel, estimate average pairwise residual-return correlation ρ
per horizon after beta and sector neutralization. Compute effective breadth `n/(1+(n−1)ρ)`. Bootstrap
synthetic panels at (n = 500, Y = 20) and at the largest attainable universe; report achieved SE, the
minimum detectable IC, and the universe size needed for SE ≤ 0.02 **with margin**.

**Why second:** my own arithmetic put achieved SE at 0.021 against a 0.02 bar — **no margin** — on an
**assumed** ρ. Measuring ρ needs cross-sectional breadth, not clean history, so 78 survivors suffice.
This is a one-day pre-mortem on the entire purchase, and it is the one experiment that can invoke a
stop condition *before* any money is spent.

**Engineering required:** analysis scripts only, in scratchpad, on the existing feature store. **No
`src/` changes** (consistent with the standing preference that research phases add no files under
`src/`).

### Experiment 3 — E-B · Trivial-baseline paired comparison *(~2 days)*

**Question:** does the 9-model ensemble beat simple alternatives on the data already held?

**Method:** on the committed captured walk-forwards, construct per-cell paired deltas of the official
7-model ensemble against (a) always-neutral, (b) 12-1 momentum, (c) a single-factor market-relative
sort, (d) equal-weight of the 7 models. Block-bootstrap by year. Report per-horizon paired deltas
with CIs. Pre-register the comparison set and the kill criteria **before** running it.

**Why third:** it is the highest-probability direction-changer (~35%) and it tests a question **never
asked at any power** — whether nine models, 68 features, and an evidence-combination engine earn
their complexity. The paired design is ~5x better powered than the absolute IC that produced the
"free data is exhausted" verdict, so this is *decidable now*. And it cuts both ways: a loss makes
"refactor the methodology" the active decision; a win is the first positive result in the project's
history and partially lifts the model freeze.

**Engineering required:** the baselines are trivial to compute from existing features. Reuses
`mip.validation.{systems, realized, metrics}`, already shipped for exactly this purpose.

### Explicitly excluded from the plan

- **The data purchase** — gated on Experiments 1 and 2.
- **Confidence redesign (E-D)** — it was approved in the prior review, but E-D shows that approval is
  itself contingent. Run E-D *after* the three above; it is cheap and no longer urgent.
- **Explainability decision log (E-F)** — start the log in the background immediately (it costs no
  engineering and only accrues calendar time), but **gate nothing on it**.
- **All other engineering.** No VM, no framework, no adapters, no features, no models. The one
  engineering item that would be required — the `aggregate_horizon_evidence` `se = 0` guard — is
  needed only for the *post-purchase* study, not for any of these three.

### What the plan delivers

After ~4 days and $0, every branch of the Part 3 decision table is reachable, and the project will
know which of these it is:

- **Terminate the prediction program** (E-A fails: the instrument can never clear its own bar)
- **Refactor the methodology** (E-B: the ensemble loses to a trivial baseline)
- **Purchase REST vendor** / **Purchase Norgate without a VM** / **Approve Norgate + VM** (E-C)
- **Partially lift the model freeze** (E-B: the ensemble wins)

That is the whole point: **~4 days of free re-analysis can decide a $600 purchase, a $250/yr VM, and
a multi-month engineering program** — and can do so in the direction of *not spending*, which is the
outcome a readiness review should be built to detect.

---

## The one thing no experiment can settle

**A6 — is engineering time actually the scarce resource here?**

The "$1.50–3.00/hour" argument that rejected both the VM and the framework assumes the owner's
engineering hours have valuable alternative use. If building is *intrinsically* valuable — a
learning or craft objective rather than an instrumental one — that argument collapses. The VM and the
framework would still buy zero scientific information, but "wastes months" stops being
disqualifying, and the correct decision rule shifts from *minimize engineering* to *minimize cash and
maximize what is worth building.*

That is a different program with a different optimum, and it is not mine to decide. **It needs a
direct answer, not an inference.**
