# Investment Decision Review — Should the Platform Buy Norgate Data Now?

**Committee:** Quantitative Research Investment Committee
**Question:** Approve or reject a **$630/yr** survivorship-clean data expenditure **today**.
**Stance:** burden of proof on the investment. The architecture supporting the purchase is not
evidence for it; poor model performance is not evidence against it.

---

## Executive Summary — Recommendation

### **PURCHASE — approve $630 today, conditional on two zero-cost pre-purchase verifications.**

The decisive fact is not that the models perform at coin-flip. It is that **the project has already
computed the resolving power of its own measuring instrument and proved it insufficient.**
[ONEYEAR_DECOMPOSITION.md](ONEYEAR_DECOMPOSITION.md) §6 states the minimum detectable effect
explicitly:

> "CI half-width ≈ 0.11; to resolve a plausibly-real IC of ~0.03–0.05 with a CI excluding zero needs
> SE ≈ 0.02, i.e. **effective N ≈ 2,000+ — hundreds of survivorship-clean names and/or multi-decade
> history**, not 31 names × 4 years."

That sentence is the entire investment case. It is a *proven* statement about the apparatus, not a
speculation about the models. The required inputs — **survivorship-clean names** and **independent
years** — are the two things free data structurally cannot supply, and they are precisely what
$630 buys.

Three consecutive research programs have now terminated on this same constraint:

| Program | Verdict | Terminating cause |
|---|---|---|
| `historical_analogues` v1 | REJECT / revise | Leakage + no signal (a real negative) |
| Conditional Probability Engine | STAYS SHADOW | Incremental CI [−0.008, +0.015] **includes 0** |
| Retire `relative_strength` | "Collect more data" | 1m Δ CI [−0.005, +0.039] **includes 0** |
| 1-year edge decomposition | ARTIFACT / UNSUPPORTED | Every clean-target CI **includes 0**; eff. N ≈ 4 blocks |

Two of those four are not scientific answers. They are **instrument failures** — the project spent
the research budget and received "cannot determine." The modal outcome of a fifth free-data program
is a fifth "cannot determine." The marginal cost of one more indeterminate phase exceeds $630 by an
order of magnitude in the only currency that is actually scarce here: the owner's time.

**What the purchase buys is evaluation capability, not prediction.** Norgate will not improve the
Trim Score by one basis point. It converts the platform from a state where *no result — positive or
negative, old or new — can be certified* into one where results can be certified at the SE the
project itself declared necessary. Everything on the research roadmap is downstream of that.

### Conditions of approval (both are ~30-minute checks, $0)

1. **Tier verification.** Confirm the $630 subscription tier includes (a) **delisted securities**
   with full price history and (b) **point-in-time index constituents**. Norgate's lower tiers do
   not universally include delisted coverage. *If delisted names are excluded, the purchase buys
   literally nothing* — survivorship-freedom is the sole disqualifying axis
   ([PHASE2_DESIGN.md](PHASE2_DESIGN.md) Stage 3).
2. **Delivery-path verification.** Norgate's primary distribution is a Windows-oriented local
   updater (NDU) that the Python API reads from. **This platform runs on macOS.** Confirm a working
   macOS ingestion path (VM, documented workaround, or direct bulk export) *before* paying.

**Contingency, pre-approved:** if either check fails, the same $630 reallocates to **Sharadar
(SEP + TICKERS) via Nasdaq Data Link** — REST-native, macOS-clean, also survivorship-free with
delisting data, and already the designated primary-alternative in Stage 3. The committee is
approving **the budget line and the research unblock**, not a vendor.

**Explicitly NOT approved today:** buying Norgate *and* Sharadar together (~$1.6–3.6k). Buy the one
source that unblocks the MVI, run the study, and let its verdict justify the second.

---

## Stage 1 — Current Evidence

### Proven (direct walk-forward evidence, embargo-hardened)

- **Short-horizon (1w–3m) prediction is coin-flip.** No directional or ranking skill. Confirmed
  across the original walk-forward, the embargoed revalidation, and the CPE study independently.
- **The headline 1-year edge is withdrawn.** The +0.17 rank correlation was measured against
  *the model's own baseline* (`realized_excess`) and pooled time-series with cross-section. Against
  clean targets the within-date IC is **+0.047 to +0.092**, and **every** year-block bootstrap CI
  includes zero (beta-residual +0.092, CI [−0.002, +0.211]).
- **The residual edge is concentration + era, not selection.** Drop the top-3 contributing symbols
  (MARA, TSLA, CCJ) → IC **−0.002**; drop top-5 → **−0.044**. Yearly IC: 2022 −0.03, 2023 +0.03,
  2024 +0.09, **2025 +0.41 (7 dates)**. Remove 2025 → collapse to ~zero.
- **Effective sample ≈ 4 independent annual blocks.** 43 monthly 1y scoring dates collapse under
  overlapping windows; the signal lives in one of the four.
- **The required effective N is ≈ 2,000+.** Stated as a rejection threshold by the project's own
  power analysis, not inferred here.
- **The universe is survivorship-biased and not point-in-time.** 31 names selected as *current*
  instruments with history ≥2013. Delisted/bankrupt/acquired names are **absent by construction**.
- **Three models are one redundant price cluster.** momentum↔relative 0.37, sector↔relative 0.36,
  momentum↔sector 0.26 (E2).
- **`valuation` is inert (0% activation)** — ~1 PIT fundamentals snapshot; unambiguous data cause.
  **`earnings_behavior` is dormant (~8%)** and anti-drift when active.
- **Confidence tracks data volume, not signal.** Weakly discriminating in production; **inverted**
  in the CPE (high-conf 1m acc 0.529 < low-conf 0.584).
- **The evaluation target was mis-specified**, and correcting it removes most of the headline
  (+0.17 → +0.01–0.09). This was a free fix, already applied.
- **Phase 1 and Phase 2A are built, tested, and green.** 20 additive tables on permanent
  `security_id`; 25 native-outcome integration scenarios green; PIT price-poisoning gold-standard
  test passes; `assert_worlds_joinable` hard-blocks legacy-signal ⋈ native-outcome joins;
  `blocked_source()` refuses any survivor-only fallback. **The infrastructure is idle, by design,
  pending a vendor.**

### Probable (evidence-supported, unconfirmed)

- `relative_strength` is redundant and mildly contrarian-mistimed (−0.287 vs SPY forward). Direction
  is consistent at every horizon (+0.004 to +0.013 dir-acc from removal) but reverses in 2 of 5
  leave-one-year-out folds. **Blocked on power, not on hypothesis.**
- `macro_regime` is the only orthogonal-and-predictive channel (E1/E2/E6 refuted the beta
  explanation). But the decomposition explicitly notes this finding "is now also suspect for the same
  concentration/power reasons."
- Short-horizon returns are efficient with respect to this (price + macro) information set — as
  opposed to merely unbeaten so far.
- The ensemble is price/macro-heavy, fundamentals-weak, and blind to positioning, forward
  expectations, and soft information.

### Unknown (genuinely undetermined)

- **Whether any real, small (IC ≈ 0.03–0.05) selection signal exists at any horizon.** The
  decomposition is explicit: this "is genuinely undeterminable here."
- **The magnitude and sign-adjusted size of the survivorship uplift.** Untestable with current data —
  it requires the returns of the names that are missing.
- Whether any prior conclusion generalizes beyond one era (2022–2026), 31 survivors, ~4 blocks.
- Whether `relative_strength` retirement, or *any* revision, is correct.
- Whether orthogonal families (insider, short interest, revisions, options) would clear an
  incremental bar — because the bar itself cannot currently be measured.

---

## Stage 2 — Competing Hypotheses for the Coin-Flip Result

| # | Hypothesis | Current evidential status |
|---|---|---|
| **A** | Models contain little or no predictive information | **Plausible, not established.** Consistent with every observation, but so are B/C. No test to date has had the power to reject a real IC of 0.03–0.05. "No evidence of an edge" ≠ "evidence of no edge." |
| **B** | The evaluation *dataset* is too weak to detect existing signal | **Strongly supported.** Survivor-only, one era, 31 names. The dataset cannot separate signal from concentration (drop-3 → 0) or era (2025 carries everything). |
| **C** | The evaluation *framework* is underpowered (sample size + survivorship) | **PROVEN.** eff. N ≈ 4 blocks vs a required ≈ 2,000. Explicitly quantified, not asserted. B and C are the same defect seen from two angles. |
| **D** | Real information exists but redundancy suppresses the aggregate | **Partially supported, unresolved.** E2 proves the redundancy (0.26–0.37 price cluster). RS removal improves dir-acc at *every* horizon — but the CI includes zero. The mechanism is demonstrated; the magnitude is unmeasurable. |
| **E** | The 1-year edge is an artifact | **PROVEN, and already acted on.** Concentration + era + noise on a survivor sample. The headline claim is formally withdrawn. |

### Additional hypotheses generated by prior research

| # | Hypothesis | Status | Does Norgate address it? |
|---|---|---|---|
| **F** | The evaluation **target** was mis-specified (rank-corr vs the model's own baseline inflated results ~2–17x) | **PROVEN.** §2 of the decomposition. | Already fixed for free. Norgate adds clean benchmark-/sector-relative and (later) residual targets. |
| **G** | 1-year effects are real but structurally unmeasurable with overlapping monthly windows over 4 calendar years | **Strongly supported.** | **Directly and only.** 20 non-overlapping annual blocks vs 4. |
| **H** | Confidence is a broken construct (volume-not-signal; inverted in CPE; `agreement ≡ 1.0` in analogue) — so confidence-weighted aggregation *dilutes* any real signal | **Supported across two independent studies.** | **NO.** This is a design defect. Norgate measures it better; it does not fix it. |
| **I** | The combiner mis-weights: correlation priors are **hand-declared** (0.5 / 0.2 baseline) while E2 *measured* the price cluster at 0.26–0.37 | **Untested.** | Partially. The re-estimation is free work; its *verdict* needs power. |
| **J** | Any incremental signal, real or not, is unjudgeable — so the research program cannot terminate | **PROVEN by three consecutive indeterminate verdicts.** | **Directly.** This is the hypothesis the purchase targets. |

---

## Stage 3 — Norgate's Expected Value, Per Hypothesis

| H | Evidence unlocked | Uncertainty reduced | Easier to confirm/reject? | Changes conclusion, or just measures it better? | Info gain |
|---|---|---|---|---|---|
| **A** (no signal) | ~500 PIT names × 20y × clean, delisting-aware forward returns; delisted losers truncated at their real terminal value instead of silently dropped | Removes the *only* remaining excuse. If IC ≈ 0 with SE ≈ 0.02, A is **established**, not merely consistent | **Rejectable for the first time.** Currently A is unfalsifiable | **Changes the conclusion's epistemic status** — from "suspected" to "demonstrated." A decisive negative is a genuine, program-redirecting result | **High** |
| **B** (dataset too weak) | Hundreds of names incl. every delisted one; ≥2 full regime cycles (2008, 2020, 2022) | B is **directly tested** — it *is* the intervention | Confirm/reject in one study | If signal appears on clean data that was invisible on dirty data, B is confirmed and every prior negative is re-opened | **Highest** |
| **C** (underpowered framework) | SE improves ~9x on raw scaling; ~2.7x after an honest cross-sectional-correlation discount (below) | **Eliminated as an explanation.** This is arithmetic, not a bet | Not a hypothesis to test — a defect to remove | **Removes the confound**, enabling every other test | **Certain** (the only near-deterministic payoff on the list) |
| **D** (redundancy suppresses) | Same walk-forward, powered: RS-removal Δ = +0.013 with SE shrinking from ~0.011 to ~0.004 | The RS decision becomes **decidable** | Yes — a currently-stalled decision resolves | **Likely changes a live decision** (retire or keep RS). Also lets correlation priors be *estimated* rather than declared (H-I) | **High** |
| **E** (1y edge artifact) | 20 independent annual blocks; PIT universe; no concentration escape | Already concluded — Norgate **certifies** it and quantifies the survivorship component for the first time | Already rejected; this makes it robust | **Mostly measures the same result more accurately.** Low marginal value on its own | **Low–Medium** |
| **F** (target mis-spec) | Clean benchmark-/sector-relative targets; residual returns deferred to Important tier | Small — already corrected | — | Confirmatory | **Low** |
| **G** (1y unmeasurable) | 20 non-overlapping annual blocks instead of 4 | **The single largest reduction.** 5x independent blocks | Yes | Genuinely capable of **changing** the 1y verdict in either direction | **High** |
| **H** (confidence broken) | Better measurement of the same broken construct | **~None** | No | Neither. Requires a redesign, not data | **~Zero** |
| **I** (combiner priors) | Enables empirical correlation estimation across 500 names / 20y instead of 31/4 | Medium | Yes | Could change combination weights materially | **Medium** |
| **J** (program cannot terminate) | The certifying instrument itself | **The entire blocker** | — | **Changes the program's future**, independent of any single result | **Highest, and durable** |

### Where Norgate delivers nothing

Stated plainly, because the committee should not fund on an inflated case:

- It does not improve any model's predictive content.
- It does not fix the confidence construct (H) — the most repeatedly-evidenced *design* defect.
- It does not supply orthogonal information (insider, short interest, revisions, options). Those
  remain separate acquisitions.
- It does not fix `valuation` (needs PIT fundamentals — Sharadar SF1, Wave 2) or
  `earnings_behavior` (needs re-keyed PIT earnings).

**Classification: Norgate is an EVALUATION purchase and a CONFIDENCE purchase. It is not a
prediction purchase.**

---

## Stage 4 — Opportunity Cost

### The power arithmetic (the load-bearing calculation)

SE of a mean cross-sectional IC scales as `1 / sqrt(Y × n_eff)`.

| | Names (n) | Independent years (Y) | Raw N | SE (reported / scaled) |
|---|---|---|---|---|
| Today | 31 survivors | 4 | 124 | ≈ **0.056** (CI half-width 0.11) |
| Norgate MVI | ~500 PIT | 20 | 10,000 | scaled → 0.006 |
| Norgate, **honest discount** | eff. ≈ 46 (ρ≈0.02 residual cross-correlation) | 20 | 910 | ≈ **0.021** |

**The discounted figure lands essentially exactly on the project's own SE ≈ 0.02 requirement, with
no margin.** Two consequences the committee should record:

1. The ~500-name × 20-year target is **the minimum, not a conservative target.** Do not descope it.
2. **Prefer S&P 1500 PIT constituents over S&P 500** if the tier provides them — the extra breadth is
   the only cheap source of margin available.

### Strategy comparison

| | **A — Buy Norgate now → Phase 2 → E1** | **B — Free data first, delay Norgate** |
|---|---|---|
| ↑ Understanding | **High.** Produces the first certifiable result in the platform's history, positive or negative | **Low.** The highest-value free experiment (beta/sector/concentration decomposition) has *already been run*. The free lever is spent |
| ↑ Predictive reliability | **High (indirect).** No model improves; every *claim about* models becomes trustworthy | **≈ Zero.** Systematic bias does not shrink with n. More survivors = a tighter CI around a biased number — **worse than the status quo**, because it manufactures false confidence |
| Engineering effort | ~2–3 weeks. Phase 1 + 2A already shipped: schema, adapters, guardrails, checksums, 25 green scenarios. This is *adapter + ingest + universe build + study run*, not new architecture | Comparable or **greater**. FINRA short interest is cheap; the SEC Form 4 / EDGAR parser is medium-heavy ingestion work |
| Research cost | **$630** + the weeks | **$0** + the same weeks |
| Risk of wrong direction | **Low.** This is a falsification and a measurement build. It cannot overfit forward. Residual risk is procurement (tier / macOS), mitigable pre-purchase for $0 | **High.** New families must clear an *incremental* bar (per the roadmap's own rule) against a baseline the project has proven it cannot measure. Modal outcome: a fourth "CI includes zero" |
| Time to decisive conclusion | ~4–6 weeks including procurement | **Unbounded — structurally.** Not a judgment: the free instrument's ceiling was computed and sits below the required threshold |

**The asymmetry that decides it:** Strategy B's expected time-to-decisive-conclusion is not "longer."
It is **undefined**, because no quantity of free data crosses the SE ≈ 0.02 bar.

### The largest hidden cost — not $630

A 500-name × 20-year × monthly walk-forward is ~120,000 (symbol, as_of) cells against the CPE
study's 5,347 — roughly **22x**. Current full-universe passes run 5–7 minutes for 52 symbols. **The
compute/batching work on the walk-forward harness likely exceeds the subscription cost by a wide
margin.** This is an argument for buying now (so the scaling work starts against real constraints)
and against pretending Phase 2 is a 3-week job with no surprises.

**Also gating, and cheap:** `models/base.py::aggregate_horizon_evidence` does `1.0 / e.se**2` and
raises `ZeroDivisionError` on a zero-dispersion study. It already crashed the sector model on a
deep-history cell. With 20 years of deep history this **will** fire. `combine_evidence` already
drops `se ≤ 0` — the same guard plus a regression test is a half-day, and must land before the
study run.

---

## Stage 5 — Value of Information

**Assumptions, stated explicitly:**
1. The Norgate tier includes delisted securities and PIT constituents (else the analysis voids —
   hence the pre-purchase gate).
2. The MVI is scoped to the **five natively-testable models**: momentum, relative_strength,
   sector_rotation (recomputable from clean `security_price_daily`, per correction 1 of the
   architecture review) plus macro_regime and interest_rate_sensitivity (**identity-neutral** —
   FRED-sourced, no instrument FK, so they migrate free the moment prices are native, per
   PHASE3_IDENTITY_MIGRATION). `valuation` and `earnings_behavior` are excluded — and both
   contribute nothing today anyway.
3. Norgate alone suffices for the MVI. **This is a scope amendment to PHASE2_DESIGN and should be
   recorded:** the design routes market-cap filters through Sharadar, but `min_price` and
   `min_dollar_volume` are computable from Norgate prices × volume, and **PIT index constituents are
   a stronger universe definition than a cap-filtered construction** — vendor-supplied,
   survivorship-clean by construction, and free of a discretionary rule the project would otherwise
   have to defend. Only `min_market_cap` needs Sharadar, and it is not required to answer the MVI
   question.
4. A true effect, if present, is IC ≈ 0.03–0.05 — the size real equity selection signals actually
   have (the project's own stated premise).

**Probabilities (deliberately non-mutually-exclusive; the prompt's four categories overlap):**

| Outcome | P | Reasoning |
|---|---|---|
| **Materially changes a research conclusion** | **~35%** | Most likely single reversal: the RS-retirement decision becomes decidable (Δ +0.013 with SE dropping ~3x). Second: the "macro is the only unique predictor" claim, currently suspect on concentration grounds. Third: clean-target ICs came in *positive* (+0.047 to +0.092) — it is not implausible a real +0.03 survives on 20 clean years |
| **Merely raises confidence in existing conclusions** | **~45%** | The modal outcome: 1y edge confirmed ≈ 0 with a tight CI; price cluster confirmed redundant; short-horizon confirmed efficient. Verdicts unchanged — but *certified* for the first time |
| **Reveals the models have no meaningful predictive information** | **~40%** | Overlaps heavily with the row above. This is the modal *specific* finding. Note this is the outcome that **most justifies the spend**: it terminates a research program that has otherwise consumed four phases without resolution, and it is unreachable without clean data |
| **Enables discoveries impossible with the current dataset** | **~85%** | The highest-probability item and the one carrying the EV. Not "new alpha" — *decidability*. Every future family (short interest, insider, PEAD, valuation on matured fundamentals, revisions) becomes judgeable against a trustworthy baseline for the first time. Structurally impossible with free data |

**Expected value.** Weight the outcomes by what each is worth to the program:

- 45% × *certification of existing conclusions* — worth roughly one avoided repeat phase.
- 35% × *a reversed or newly-decidable conclusion* — worth several phases; it changes what gets
  built.
- 85% × *durable decidability* — worth the entire remaining roadmap, since the roadmap's own
  cross-cutting rule is "the bar is incremental, with a block-bootstrap CI excluding zero," which
  today is unsatisfiable by construction.

Against a $630 cost, **no plausible weighting produces a negative expected value.** The scenario
where the money is wasted is not "the models turn out to be worthless" — that is a *purchased
result*. It is only the procurement-failure scenario, which the two pre-purchase gates close for $0.

**One further asymmetry — there is no option value in waiting.** The price does not decay and the
20-year history does not grow more expensive. Waiting purchases nothing, while forgoing the research
time. If the subscription also permits retaining downloaded history after lapse (a term to confirm
alongside the tier check), then $630 buys a permanent 20-year research corpus with renewal needed
only for ongoing updates — which changes the cost-per-unit-knowledge by another order of magnitude.

---

## Stage 6 — Could Free Data Answer the Same Question?

### **No — and the reason is specific, not the slogan.**

"Survivorship bias" as a phrase is not the argument. The argument is a closed loop with three links:

**Link 1 — Free data's only remaining lever is the one that amplifies the confound.**
The deficiency is `Y × n`. Free data (yfinance) can supply more of both: expand from 78 names to
1,000+ current-listed US names, and extend history to 2005. But every added name is, by
construction, a *survivor*, and every added year makes it worse — the reconstructed "2005 universe"
would be 2026's survivors projected backward, which is the maximal-bias configuration. So free data
shrinks the CI around an estimate whose **bias grows in the same operation.** The result is a tight
confidence interval on a wrong number. **That is worse than today's honest wide interval**, because
it would look like a discovery.

**Link 2 — Systematic error does not shrink with n.** Bootstrap, block-bootstrap, embargo, and
purging all control *variance*. None of them touch *bias*. The project's validation apparatus is
excellent at exactly the class of error it cannot use here: the PIT price-poisoning gold-standard
test, the per-horizon embargo rule, the leakage report asserting violations == 0 — all of these
eliminated look-ahead, and *none of them can eliminate a missing-population bias.* The instrument is
already as good as variance control can make it. It has hit its ceiling.

**Link 3 — The bias magnitude is not even estimable from free data.** To correct for survivorship
you need the returns of the names that are missing. Those names are missing. There is no free source
of **delisting returns** — the terminal value distinguishing an acquisition at a premium from a
bankruptcy at −100%. The design's Stage 3 evaluation rejects Polygon, Tiingo, FMP, and Alpha Vantage
on exactly this axis, not on price. And the platform's own Phase 2A code encodes the honest position:
an unknown terminal value is recorded `UNRESOLVED` and **never assumed −100%**, because assuming it
would fabricate the very number that is missing.

So: free data cannot detect the effect (Link 1), cannot correct for the bias (Link 2), and cannot
measure the bias to adjust for it (Link 3). **That is a scientific limit, not a budget preference.**

### The free experiments that DO have value — and why they still don't come first

Three are genuinely worth doing, and two can run **in parallel** with procurement at no opportunity
cost:

| Experiment | Value | Verdict |
|---|---|---|
| **Re-estimate the combiner's correlation priors** (H-I). Priors are hand-declared 0.5 / 0.2; E2 *measured* the price cluster at 0.26–0.37. Recompute empirically and re-run the combination | Medium. Cheap, uses existing captured walk-forward, no new ingestion | **Run in parallel.** But its verdict is unjudgeable without power — it produces a candidate, not a conclusion |
| **Redesign the confidence construct** (H). Inverted in CPE, `agreement ≡ 1.0` in analogue, volume-not-signal in production. Norgate does **not** fix this | Medium–High. It is a *design* defect, so free data is the correct place to fix it | **Run in parallel.** This is the one item where free work is strictly better than waiting |
| **Short interest (FINRA) / insider Form 4 (EDGAR)** ingestion — the roadmap's top-ranked orthogonal families | High ceiling, but the *judging* is blocked | **Do NOT run first.** The roadmap's own rule is an incremental bar with a CI excluding zero. Building signals that cannot be judged is how the CPE consumed a full phase |

The sequencing conclusion is the whole argument in one line: **the free-data experiments that
matter are the ones that build things, and every one of them needs a working ruler to be worth
building.** The one free experiment that could have decided the central question — the beta /
sector / concentration decomposition — **has already been run**, and its verdict was *"the
apparatus cannot resolve this; rebuild the evaluation foundation."*

The committee is being asked to fund the recommendation its own prior research produced.

---

## Stage 7 — Decision Matrix

Scored 1–5 (5 = best). "Cost" scored so that 5 = cheapest.

| Criterion | Continue Free Data | Purchase Norgate | Evidence |
|---|---|---|---|
| **Expected Scientific Value** | **2** | **5** | The decisive free experiment is already spent (ONEYEAR_DECOMPOSITION) and returned "unresolvable." Norgate is the only path to a certifiable result at the project's own declared SE |
| **Expected Improvement in Correctness** | **1** | **4** | Free data cannot correct a known-direction (upward) bias and would *tighten* CIs around it. Norgate removes the bias at source; it does not improve models (hence 4, not 5) |
| **Expected Reduction in Uncertainty** | **1** | **5** | SE ≈ 0.056 → ≈ 0.021 after an honest cross-correlation discount; 4 → 20 independent annual blocks. This is arithmetic, not forecast |
| **Engineering Leverage** | **2** | **5** | Phase 1 + 2A = 20 tables, 25 green scenarios, PIT poison test, `assert_worlds_joinable`, checksummed snapshots — **all idle**, because `blocked_source()` correctly refuses survivor data. Free data activates none of it; Norgate activates all of it |
| **Cost** | **5** | **4** | $0 vs $630. In the dominant currency — owner-weeks — the two are comparable, and the real hidden cost (22x walk-forward compute) is common to both once studies scale |
| **Risk of Wasted Effort** | **1** | **4** | Free path's modal outcome is a *fourth* "CI includes zero" (analogue, CPE, RS all terminated this way). Norgate's residual risk is procurement — tier and macOS delivery — closable for $0 pre-purchase |
| **Long-Term Platform Value** | **1** | **5** | A 20-year survivorship-clean corpus is a permanent asset; it gives Phase 3's identity migration a real target and makes every future information family judgeable |
| **Total** | **13 / 35** | **32 / 35** | |

---

## Stage 8 — Final Recommendation

### **PURCHASE NORGATE IMMEDIATELY** (subject to the two zero-cost pre-purchase gates).

### Why "Delay until more free-data research is completed" is inferior

Delay would be correct if a free experiment could still move the binding question. **It cannot, and
we know this because that experiment was already run.** The 1-year decomposition was the highest-EV
free study available; it executed cleanly, refuted the beta and sector explanations, isolated
concentration and era — and terminated with an explicit instruction: *"Highest priority next: not a
model. Rebuild the evaluation foundation."* Delaying now means re-deriving a conclusion the project
already owns, at the cost of the same weeks, while $630 sits unspent. Worse, the most attractive
free candidates (short interest, insider) would be judged against a baseline proven unmeasurable —
manufacturing a fourth indeterminate verdict from work that was probably sound. Delay does not
reduce risk here; it converts a $630 risk into a multi-week risk.

*(The two genuinely valuable free items — confidence redesign and empirical correlation priors —
are not arguments for delay. They run in parallel with procurement.)*

### Why "Reject because it is unlikely to change the platform's future" is inferior

Rejection would be correct if the models were **proven** to contain no information. They are not
proven worthless — they are **unmeasured**. Rejection commits the exact inferential error the
project has been disciplined about everywhere else: treating *absence of evidence* as *evidence of
absence*, on an instrument whose own power analysis says it could not have detected a real effect of
realistic size. Rejection also strands roughly four weeks of built, tested, green infrastructure
whose entire purpose was to consume this data, leaves the roadmap's whole orthogonal-family program
permanently unjudgeable, and — most importantly — makes the *negative* conclusion unreachable too.
"The models are worthless" is a valuable, program-redirecting finding, and rejecting the purchase
forecloses proving it just as surely as it forecloses the positive.

---

## Investment Committee Decision

**Would I personally approve $630 today? Yes.**

Not because the architecture supports it — that is not evidence. Not because the models are
performing badly — that argues neither way. **Because the project has computed the resolving power
of its own instrument, found it roughly two orders of magnitude short of what its own research
question requires, identified the exact two inputs that would close the gap (clean names, independent
years), proven that free data can supply neither, and then built and tested the entire consuming
infrastructure — and then stopped, one procurement decision short of being able to answer anything.**

$630 is roughly the cost of writing up *one* indeterminate research phase. This project has produced
three. The marginal dollar is not buying alpha. It is buying the ability to ever again distinguish a
real finding from noise — and every other item on the roadmap is downstream of that capability.

### Conditions attached to the approval

1. **Gate 1 — tier includes delisted securities + PIT index constituents.** If not, the purchase
   buys nothing; reallocate to Sharadar.
2. **Gate 2 — a working macOS ingestion path.** Norgate's updater is Windows-oriented. If
   unresolvable, reallocate to Sharadar (SEP + TICKERS), which is REST-native and clears the same
   two disqualifying axes.
3. **Scope lock.** One vendor, not two. The MVI is answerable from Norgate alone using PIT index
   constituents as the universe (recorded as an amendment to PHASE2_DESIGN Stage 7). Sharadar is
   re-evaluated *after* the first study reports.
4. **Pre-register E1 before the data lands.** The CPE precedent — hypotheses and kill criteria frozen
   in `docs/CPE_VALIDATION_PLAN.md` *before* results — is the strongest methodological habit this
   project has. Repeat it. With 120,000 cells and a fresh dataset, the multiple-comparisons risk is
   the highest it has ever been.
5. **Scope floor: ~500 names × 20 years is the MINIMUM, not the target.** The discounted SE lands at
   ≈ 0.021 against a ≈ 0.02 requirement — no margin. Prefer S&P 1500 PIT constituents if available.
6. **Two engineering items before the study run:** fix `aggregate_horizon_evidence`'s
   `ZeroDivisionError` on `se = 0` (guaranteed to fire on deep history), and budget the ~22x
   walk-forward scaling work honestly.

### What would change this decision to "no"

Only these, and each is checkable for $0 before any money moves:

- The $630 tier **excludes delisted securities or PIT constituents** → the purchase buys a
  better-formatted survivor dataset, which is worth nothing. *(Reallocate, don't cancel.)*
- **No workable macOS delivery path** → same reallocation.
- **License terms forbid storing derived returns or checksummed snapshots** → would break the
  reproducibility model that is the platform's core asset. *(Storing derived returns rather than
  redistributing raw is already the design's stated mitigation; confirm it is permitted.)*
- A demonstration that ~500 clean names × 20 years still lands SE **above** 0.02 → the purchase
  would not clear the project's own bar, and the correct move would be a broader universe tier
  rather than this one. *(The arithmetic above says it lands at ≈ 0.021 — this is the tightest
  genuine risk in the case, and the reason the scope floor is a condition of approval, not a
  suggestion.)*
