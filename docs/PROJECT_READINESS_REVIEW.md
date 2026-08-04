# Project Readiness Review — Has This Project Earned Further Investment?

**Committee:** Head of Quantitative Research / Chairman, Investment Committee
**Question:** not "how do we improve this?" but "has the evidence earned the next dollar and the next
month?"
**Stance:** the project must earn continuation. Prior work is not a claim on future funding.

---

## Verdict (stated first)

### The project has earned a **small, sharply-scoped continuation.** It has **not** earned an infrastructure program.

It earned that continuation on its **falsification record**, not its predictive record. This platform
has killed four of its own ideas with rigor — including its own headline result — and that capability
is rare and real. But the proposed investment bundle has quietly changed shape, and the change is the
whole story:

| Proposed investment | Cash | Engineering | Scientific information purchased |
|---|---|---|---|
| Clean survivorship-free data | ~$600/yr | ~2–3 wks (schema/adapters already built) | **~100% of what remains** |
| Parallels + Windows VM | ~$250/yr¹ + ongoing friction | recurring maintenance | **0%** |
| Provider-independent ingestion framework | $0 | **months** | **0%** |
| Continued feature engineering | $0 | months | **0%** (negative — see §4.4) |
| Continued model development | $0 | months | **0%** (negative — see §4.5) |

¹ Parallels subscription + a Windows license, approximate; verify.

**Roughly 95% of the proposed investment buys roughly 0% of the remaining scientific information.**
That is the single finding of this review. A committee's job is to fund the 5% and refuse the 95%.

One correction to my own prior recommendation, applied honestly: the previous review approved $630
for Norgate **conditional on confirming a workable macOS ingestion path**, with a pre-approved
contingency to reallocate to a REST-native vendor if that gate failed. The appearance of "Parallels +
Windows VM" on this list *is* the gate failing. **Consistency therefore requires rejecting Norgate
specifically** and taking the contingency. That is not a reversal; it is the condition executing as
written.

---

## PART 1 — Current State Assessment

### PROVEN

*Criterion for this category: established by direct, embargo-hardened, out-of-sample measurement, or
by arithmetic — and reproducible from committed artifacts.*

**About the predictions:**

1. **Short-horizon (1w–3m) prediction is coin-flip.** Independently reproduced three times: the
   original walk-forward, the embargoed revalidation, and the CPE study. *Why proven:* three
   independent measurements, one of them after a leakage fix that changed other numbers materially.
2. **The 1-year edge is an artifact.** The +0.17 headline was measured against the model's own
   baseline; clean-target IC is +0.047 to +0.092 with every year-block CI including zero. Drop 3 of
   31 symbols → IC −0.002. Yearly: 2025 alone carries +0.41 of it. *Why proven:* two independent
   robustness tests (dominant-symbol exclusion, leave-one-year-out) each collapse it separately.
3. **Three models are one redundant price cluster.** momentum↔relative 0.37, sector↔relative 0.36,
   momentum↔sector 0.26. *Why proven:* direct measurement of realized score correlations (E2).
4. **`valuation` is inert (0% activation).** One PIT fundamentals snapshot exists. *Why proven:*
   unambiguous mechanical cause, not a statistical inference.
5. **The evaluation instrument is underpowered by ~2 orders of magnitude.** Effective sample ≈ 4
   independent annual blocks against a self-computed requirement of ≈ 2,000. *Why proven:* this is
   arithmetic on the block structure, not an estimate.
6. **Confidence does not track skill.** Volume-not-signal in production; **inverted** in the CPE
   (high-conf 1m acc 0.529 < low-conf 0.584); structurally dead in the analogue (`agreement ≡ 1.0`).
   *Why proven:* three independent observations, one of them a sign inversion — which is a stronger
   result than mere absence of discrimination.
7. **The analogue model's long-horizon "promise" was 100% leakage.** 3m 50.8→35.5%, 6m 64.3→44.4%,
   1y 64.3→30.8% after per-horizon embargo. *Why proven:* the fix was validated by a
   price-poisoning test and a leakage report asserting violations == 0.
8. **Free data cannot resolve the open question.** Its only remaining lever (more names, more years)
   adds survivors and survivor-projected history, tightening CIs around a *growing* bias; and the
   bias magnitude is not estimable, because it requires the returns of the missing names. *Why
   proven:* structural, not empirical — systematic error does not shrink with n.

**About the platform (systematically under-weighted in prior reviews):**

9. **The methodology works, and is the project's strongest asset.** 782 test functions;
   price-poisoning PIT tests; per-horizon embargo with an asserted leakage report; pre-registration
   *before* results (`docs/CPE_VALIDATION_PLAN.md`); immutable append-only prediction archive;
   `blocked_source()` refusing to substitute survivor data; a hard `MixedIdentityWorldError`
   guardrail against mixed-identity joins. *Why proven:* the machinery **caught its own errors** —
   the leakage discovery and the headline withdrawal were self-inflicted, which is the only real
   proof a validation framework works.
10. **Provider independence already exists.** `src/mip/securities/source.py` defines
    `SecuritySource` (Protocol) + frozen DTOs + `FixtureSource` + `blocked_source()`;
    `src/mip/research_data/source.py` defines `OutcomeSource` (Protocol) + `FixtureOutcomeSource` +
    `blocked_outcome_source()`. *Why proven:* read directly from the code. **This matters enormously
    for Part 4.3.**
11. **A working explainability layer exists.** `engine/attribution.py` enforces an exact accounting
    invariant (`trim_score = 50 + Σ contributions + adjustments + clip_residual`);
    `engine/intelligence.py` produces bull/bear theses with full provenance, structured *unknowns*
    with distinct kinds, and band-boundary math; committed examples in
    `data/reports/institutional_examples/`. *Why proven:* built, tested, and rendering real output.
12. **Four research programs, zero promotions.** analogue → reject; CPE → shadow, not promotable;
    retire-`relative_strength` → undecidable; 1y decomposition → artifact. *Why proven:* it is the
    record.

### LIKELY

*Criterion: consistent, directionally stable evidence across multiple measurements, but with CIs that
include zero or a single-era limitation.*

- **`relative_strength` is redundant and mildly contrarian-mistimed** (−0.287 vs SPY forward;
  removal improves dir-acc at *every* horizon, +0.004 to +0.013). *Why not proven:* the 1m CI is
  [−0.005, +0.039] and it reverses in 2 of 5 leave-one-year-out folds. Blocked on power, not on
  hypothesis.
- **Short-horizon returns are efficient with respect to a price+macro information set** — not merely
  unbeaten. *Why likely rather than proven:* the negative is consistent and mechanistically sensible
  (E5, E6), but "unbeatable" is not established by failing to beat it on an underpowered sample.
- **`earnings_behavior` fades genuine post-earnings drift** (~8% activation, rank-corr worsening with
  horizon, −0.06→−0.13). *Why not proven:* small activation sample.
- **Model accumulation has a ~0% marginal success rate in this program.** Two models built after the
  original seven (analogue, CPE) were both rejected, each for a *different* reason, and each
  consumed a full research phase. *Why likely:* n=2 is a pattern, not a law.

### POSSIBLE

*Criterion: a live hypothesis with a plausible mechanism, not yet tested with adequate power.*

- **A real but small selection signal (IC ≈ 0.03–0.05) exists and is currently invisible.** Clean
  targets came in *positive* (+0.047 to +0.092), and the beta-neutral residual was the *strongest*
  target — the pattern a small real effect would produce, and also the pattern noise would produce.
  Genuinely undetermined.
- **`macro_regime` carries unique orthogonal information.** E1/E2/E6 refuted the beta explanation
  specifically. But the decomposition notes this finding "is now also suspect for the same
  concentration/power reasons."
- **The combiner mis-weights.** Correlation priors are *hand-declared* (0.5 / 0.2) while E2
  *measured* the price cluster at 0.26–0.37. Untested.
- **The reporting/explainability layer is the project's actual product**, independent of predictive
  edge. Plausible, elaborately built — and **never validated with a user.** See Part 2, U4.

### UNKNOWN

*Criterion: no evidence either way, and no current means of obtaining it.*

- The **magnitude** of the survivorship uplift. Requires the missing names' returns.
- Whether **any** conclusion generalizes beyond one era (2022–2026), 31 survivors, ~4 blocks.
- Whether **orthogonal families** (insider, short interest, revisions, options) would clear an
  incremental bar — because the bar itself is currently unmeasurable.
- Whether confidence is **repairable in principle** or whether the evidence-volume-based construct is
  fundamentally the wrong shape.
- Whether the platform has any **user-facing value at all**. Never tested.

---

## PART 2 — Remaining Uncertainties, Ranked by Expected Impact on Project Success

Ranked by impact on *whether the project succeeds*, not by scientific interest. Note that the two
highest-ranked items after U1 are **not data-gated** — a fact the roadmap has consistently missed.

| Rank | Uncertainty | Impact | Why ranked here | Resolvable now? |
|---|---|---|---|---|
| **U1** | **Does any genuine predictive signal exist in the price+macro information set?** | **Existential** | Every model, feature, report, and infrastructure decision is downstream. If no → the prediction program ends and only the reporting layer survives | **No** — requires clean data. The single legitimate data-gated question |
| **U2** | **Is confidence calibratable at all?** | **Very High** | The product's core promise is "here is how much to trust this." Inverted confidence is worse than no confidence — it actively misleads. Proven broken across three studies, and **better data does not fix it.** If unfixable, the trim score cannot be honestly shipped *even if U1 is positive* | **YES — today, $0, no data needed** |
| **U3** | **Is the reporting/explainability framework valuable even with modest prediction?** | **Very High** | This is the project's **largest blind spot.** A complete attribution + intelligence + institutional-report stack exists and has never been put in front of a human. If it is valuable, the project has a product *regardless of U1* — which changes the entire investment case. If it is not, a negative U1 means full termination | **YES — today, $0, ~1 week** |
| **U4** | **Is the evaluation methodology sufficiently powered?** | High | **Already resolved: proven NO.** Listed for completeness — it is a known defect, not an open question. Its resolution has a known price (~$600) | Resolved (negative) |
| **U5** | **Would better data materially change conclusions?** | High | Prior review estimated ~35% material change / ~45% confirmation / ~85% durable decidability. The decidability is the payoff, not the reversal | Partially — by buying the data |
| **U6** | **Are the current models redundant?** | Medium | **Largely proven** for the price cluster (0.26–0.37). The open remainder is whether removal *helps*, which is U1-gated | Mostly resolved |
| **U7** | **Is the one-year edge real?** | Medium | **Resolved: artifact.** Retained here because re-testing it on clean data is the natural form of the U1 experiment | Resolved (negative) |
| **U8** | **Do orthogonal families clear an incremental bar?** | High ceiling, low current | Highest long-run upside, but **strictly gated on U1** — a bar that cannot be measured cannot be cleared. Building these first is how the CPE burned a phase | No — gated |
| **U9** | **Does the combiner's declared-prior weighting cost anything?** | Low–Medium | Cheap to re-estimate empirically; verdict needs U1's power | Partially — free work, gated verdict |

**The ranking's central implication:** U2 and U3 are the second- and third-most important
uncertainties in the entire project, they are **free**, they require **no new data**, and neither has
been touched. Meanwhile every proposed investment on the list addresses U1 or nothing.

---

## PART 3 — Decision Bottleneck Analysis

Expected uncertainty reduction per lever. **A** = existing free datasets, **B** = better
experimentation, **C** = better statistical analysis, **D** = better historical data (Norgate/
Sharadar/CRSP), **E** = additional engineering.

| Uncertainty | A: Free data | B: Better experiments | C: Better statistics | D: Better data | E: Engineering | Binding lever |
|---|---|---|---|---|---|---|
| **U1** signal exists? | **~0%** — and *negative*: more survivors tighten CIs around a growing bias | ~5% — designs are already good; the CPE was pre-registered and still undecidable | **~10%** — better targets/estimators help at the margin; cannot manufacture independent blocks | **~75%** | ~5% (harness scaling only) | **D** |
| **U2** confidence calibratable? | ~10% | **~35%** — isotonic/Platt recalibration, holdout-fit reliability curves | **~40%** — the defect is *construct design* (volume×agreement), a statistics problem | ~10% (measures it better) | ~15% (implementation) | **B + C — free** |
| **U3** reporting valuable? | 0% | **~80%** — put it in front of a user and record what they do with it | ~0% | 0% | ~10% (polish only) | **B — free, and nothing else works** |
| **U4** power sufficient? | 0% (proven) | ~5% | ~10% (block design at the margin) | **~85%** | ~5% | **D** |
| **U5** would data change conclusions? | 0% | 0% | ~5% | **~95%** (tautological) | 0% | **D** |
| **U6** models redundant? | ~15% (re-estimate priors on captured runs) | ~15% | **~30%** — empirical correlation estimation vs declared priors | ~40% (powered removal tests) | ~5% | **C, then D** |
| **U7** 1y edge real? | 0% | ~5% | ~10% | **~85%** | 0% | **D** |
| **U8** orthogonal families? | ~25% (FINRA + EDGAR are free to *ingest*) | ~10% | ~5% | **~55%** (supplies the judgeable baseline) | ~40% (the ingestion *is* the work) | **D first, then E** |
| **U9** combiner priors? | **~50%** — recomputable from captured walk-forward | ~15% | **~30%** | ~20% | ~10% | **A + C — free** |

**Three conclusions fall out of this table:**

1. **Additional engineering (E) is the binding lever for nothing.** Its highest column entry is 40%,
   on U8, which is itself gated. Engineering is where this project reflexively spends, and it is the
   least productive lever available.
2. **D is the binding lever for exactly four uncertainties (U1, U4, U5, U7) — which are three
   restatements of the same question plus its known defect.** So the data purchase buys one thing:
   the ability to answer U1. That is worth ~$600. It is not worth months.
3. **U2, U3, and U9 — three of the nine — are bottlenecked on free work that has not been done.**

---

## PART 4 — Investment Readiness Review

### 4.1 Purchase Norgate

- **Evidence for:** U1/U4/U5/U7 are D-gated and Norgate clears both disqualifying axes (survivorship
  freedom, delisting returns) per PHASE2_DESIGN Stage 3. The consuming infrastructure is built,
  tested, and idle.
- **Evidence against:** its distribution is a Windows-oriented local updater; this platform is
  macOS. That dependency is what generates investments 4.2 and (partly) 4.3 — i.e. **choosing this
  vendor manufactures ~$250/yr and an indefinite maintenance burden that a REST-native competitor
  does not.** Nothing in the evidence base establishes Norgate as *uniquely* adequate; Stage 3 lists
  Sharadar as "Primary-alt" with **"Easy (clean API/bulk)"** integration and PIT market cap Norgate
  only partially provides.
- **Scientific value:** High — but *identical* to the alternative's. This is a delivery-mechanism
  choice, not a scientific one.
- **Engineering value:** **Negative** relative to the alternative (VM toolchain).
- **Business value:** Neutral.
- **Cost:** $630/yr **+ $250/yr + permanent VM friction = the expensive path to the same data.**
- **Risk:** Medium-high on operations; the ingestion path becomes the most fragile link in the
  research chain and sits outside the test suite.
- **Prerequisites:** a macOS delivery path — **evidently absent.**
- ### Recommendation: **REJECT as specified.** Fund the *capability* via the REST-native path.

### 4.2 Build Windows VM (Parallels)

- **Evidence for:** none independent of 4.1. It is purely derivative.
- **Evidence against:** pays cash *and* accepts a fragile, untestable, manually-maintained toolchain,
  to obtain data available over HTTPS at comparable cost. It also silently violates a property the
  project has otherwise protected everywhere: **reproducibility.** A hand-maintained VM is not a
  reproducible build step, and this platform's core asset is that every artifact is reproducible from
  a checksum.
- **Scientific value:** **Zero.**
- **Engineering value:** **Negative** — permanent maintenance liability, off the CI path.
- **Business value:** Zero.
- **Cost:** ~$250/yr + recurring hours, indefinitely.
- **Risk:** High and *chronic* rather than one-time. Ingestion breaks on OS/VM/vendor updates, at
  unpredictable times, with no test coverage.
- **Prerequisites:** proof that Norgate is the *only* adequate source. **Unproven, and probably
  false.**
- ### Recommendation: **REJECT.**

### 4.3 Build a provider-independent historical ingestion framework

- **Evidence for:** genuine long-run value *if* the platform survives and swaps vendors repeatedly.
- **Evidence against — decisive:** **it already exists.** Verified in the code:
  `SecuritySource` (Protocol) with frozen DTOs, `FixtureSource`, `blocked_source()`; and
  `OutcomeSource` (Protocol) with `FixtureOutcomeSource`, `blocked_outcome_source()`. Phase 1 and
  Phase 2A both ship a vendor-agnostic adapter contract validated against a fixture vendor, with 25
  green native-outcome scenarios. **The proposal is months of work to rebuild an abstraction the
  project already has, correctly, and cheaply.** Beyond that, it is textbook premature abstraction:
  you cannot design a provider-independent layer well with **zero** real providers integrated —
  the second integration is what teaches you where the seams belong, and abstractions built before
  it reliably encode the wrong ones.
- **Scientific value:** **Zero.**
- **Engineering value:** **Strongly negative** — months of the scarcest resource, duplicating
  existing tested code, at the moment when the project's own analysis says the bottleneck is data,
  not code.
- **Business value:** Zero.
- **Cost:** **months.** At 200–400 hours to avoid a ~$600 expense, the implied valuation of the
  owner's time is **$1.50–$3.00/hour.** No committee approves that trade.
- **Risk:** High opportunity cost; high probability of encoding the wrong seams.
- **Prerequisites:** (a) a validated edge worth maintaining over years, (b) evidence of ≥3 vendor
  swaps. **Neither exists.**
- ### Recommendation: **REJECT.** Write one concrete adapter against the existing Protocol. If a second vendor ever arrives, generalize *then*, informed by two real integrations.

### 4.4 Continue feature engineering

- **Evidence for:** none currently. The one identified data-gap fix (fundamentals maturation) is
  **passive** — snapshots accumulate with zero marginal effort.
- **Evidence against:** 68 features and 9 models already exist with **zero validated edge**.
  ONEYEAR_DECOMPOSITION §7 states directly: "*every* model revision ... is premature. There is no
  validated edge to improve, and the evaluation apparatus cannot certify one." Adding features to an
  unmeasurable system cannot produce knowledge — it can only produce unfalsifiable additions.
- **Scientific value:** ~Zero, and negative on multiple-comparisons grounds: more features on an
  underpowered sample raises the false-discovery rate the project has no program-level FDR ledger to
  control (Architecture Review R6).
- **Engineering value:** Low.
- **Business value:** Zero.
- **Cost:** months. **Risk:** high — the CPE failure mode, repeated.
- **Prerequisites:** U1 resolved positively.
- ### Recommendation: **REJECT** until U1 is answered. (Exception: let the fundamentals snapshots keep accruing — zero-effort, already in motion.)

### 4.5 Continue model development

- **Evidence for:** none.
- **Evidence against:** the strongest negative record in the project. Two models built after the
  original seven, two rejections, **two full research phases consumed**, each failing for a
  *different* reason (leakage; redundancy + inverted confidence). RESEARCH_ROADMAP's own governing
  lesson: "re-expressing information the ensemble already has adds nothing."
- **Scientific value:** ~Zero. **Engineering value:** Low. **Business value:** Zero.
- **Cost:** months per model. **Risk:** highest on the list — an empirically ~0% promotion rate.
- **Prerequisites:** U1 positive **and** a genuinely orthogonal information family **and** a
  measurable incremental bar.
- ### Recommendation: **REJECT.** Hard freeze. This is the single largest source of wasted effort in the project's history.

### 4.6 Improve confidence calibration

- **Evidence for:** the strongest evidential case on the entire list. Broken in **three** independent
  studies: volume-not-signal in production, **inverted** in the CPE (0.529 vs 0.584), structurally
  dead in the analogue (`agreement ≡ 1.0`). Prior work also documents the mechanism — confidence
  derives from evidence *volume*, contributed mainly by always-active long-history models, so it
  measures data abundance rather than skill. Critically: **better data does not fix this**, so it
  cannot be deferred behind the purchase. And an *inverted* confidence signal is worse than none —
  it points users at the least reliable calls.
- **Evidence against:** it is only worth fixing if something is eventually shipped. Weak objection —
  it is also a *precondition* for shipping honestly.
- **Scientific value:** High — and it is the one high-value item with **no data dependency.**
- **Engineering value:** High — a bounded, testable, self-contained change.
- **Business value:** **Highest on the list.** Honest uncertainty communication is the product.
- **Cost:** Low — days to ~2 weeks. **Risk:** Low.
- **Prerequisites:** none.
- ### Recommendation: **PROCEED NOW.** Best value-per-dollar in the entire program.

### 4.7 Improve explainability

- **Evidence for:** the layer already exists and is unusually good — an exact attribution accounting
  invariant, structured *unknowns* with distinct kinds (including honest not-modeled dimensions),
  provenance-carrying theses, committed institutional examples. It is the project's most plausible
  *product*, and it is the one asset whose value **does not depend on U1.**
- **Evidence against:** **it has never been validated with a human.** Its value is entirely
  hypothesized. And more *engineering* on it is not the missing input — *evidence of usefulness* is.
- **Scientific value:** Low directly; **very high indirectly** — it resolves U3, the project's
  largest blind spot, and U3 determines whether a negative U1 means "pivot" or "terminate."
- **Engineering value:** Low (little is missing).
- **Business value:** **Potentially the highest of any item**, and completely unmeasured.
- **Cost:** ~1 week, $0 — if scoped as **validation, not construction.**
- **Risk:** Low. **Prerequisites:** none.
- ### Recommendation: **PROCEED NOW, scoped strictly to validation.** Use the platform's own reports on the real 52-name portfolio for a month; record which sections drive an actual decision, which are ignored, and which mislead. **Do not write new report code before that evidence exists.**

### 4.8 Expand the historical universe

- **Evidence for:** the power arithmetic — SE ∝ 1/√(Y×n_eff); 4×31 today vs the ≈2,000 effective-N
  requirement.
- **Evidence against — a critical distinction:** expanding via **free/survivor** data is **actively
  harmful.** It tightens CIs around a growing bias, manufacturing false confidence — strictly worse
  than today's honest wide intervals. Expansion is only valuable through a survivorship-clean source.
- **Scientific value:** **Highest on the list** — via clean data only.
- **Engineering value:** Medium; activates ~4 weeks of built, idle infrastructure.
- **Business value:** Indirect.
- **Cost:** ~$600 + 2–3 weeks. **Plus the genuine hidden cost:** ~500 names × 20y monthly ≈ 120,000
  walk-forward cells against the CPE's 5,347 (~22x) — the harness scaling work probably exceeds the
  subscription.
- **Risk:** Medium. Note the tightest real risk, from the prior review's arithmetic: after an honest
  cross-sectional-correlation discount (ρ≈0.02 → n_eff ≈ 46), SE lands at **≈ 0.021 against a 0.02
  requirement — no margin.** So ~500 names × 20y is a **floor, not a target**; prefer the broadest
  clean universe available.
- **Prerequisites:** a clean vendor with a maintainable delivery path; the
  `aggregate_horizon_evidence` `ZeroDivisionError` on `se = 0` fixed (guaranteed to fire on 20y deep
  history).
- ### Recommendation: **PROCEED NOW via a REST-native survivorship-clean vendor.** Reject any expansion using survivor data.

### Summary

| # | Investment | Recommendation |
|---|---|---|
| 1 | Purchase Norgate | **Reject as specified** — fund the capability, change the vendor |
| 2 | Windows VM / Parallels | **Reject** |
| 3 | Provider-independent ingestion framework | **Reject** — it already exists |
| 4 | Continue feature engineering | **Reject** (freeze; passive fundamentals excepted) |
| 5 | Continue model development | **Reject** (hard freeze) |
| 6 | Improve confidence calibration | **PROCEED NOW** |
| 7 | Improve explainability | **PROCEED NOW** — validation only, not construction |
| 8 | Expand historical universe | **PROCEED NOW** — clean vendor only |

Two of the three approvals are **free**. The third is ~$600. Every rejected item is an engineering
program.

---

## PART 5 — Minimal Scientific Dependency Graph

Dependencies are **evidential**, not chronological. An arrow means *the parent's evidence must exist
or the child is unjustified.*

```
      ┌─────────────────────── ROOT: no evidential prerequisites ───────────────────────┐
      │                                                                                 │
 [N1] Can confidence be                [N2] Is the reporting layer          [N3] Do declared combiner
      calibrated at all?                    useful to a human?                   priors cost anything?
      (free · U2)                           (free · U3)                          (free · U9)
      │                                     │                                    │
      │                                     ├────────────► if NO and N5 is NO ──► TERMINATE (§6, S6)
      │                                     └────────────► if YES ─────────────► the project HAS a
      │                                                                          product independent
      │                                                                          of any edge
      ▼
 [N4] Confidence is honest ──────────────┐
      (precondition for SHIPPING         │
       anything, regardless of edge)     │
                                         │
 ══════════════════════════ THE ONE DATA-GATED BRANCH ══════════════════════════
                                         │
 [N0] Acquire survivorship-clean data ≥500 names × ≥20 independent years
      prereq: a maintainable delivery path (NOT a hand-maintained VM)
      prereq: se=0 guard in aggregate_horizon_evidence
      │
      ▼
 [N5] Does ANY signal exist in price+macro? (U1 — the existential question)
      │
      ├── NO ──► prediction program ENDS. Value = N2 + the falsification machinery.
      │          Everything below is permanently unjustified.
      │
      └── YES ─┬──► [N6] Powered model-revision decisions become decidable
               │         (retire relative_strength; empirical priors from N3)
               │
               ├──► [N7] Is there a measurable INCREMENTAL bar?
               │         │
               │         └──► [N8] Orthogonal families (insider, short interest,
               │                    revisions, options) — ingestion justified HERE,
               │                    not before
               │                    │
               │                    └──► [N9] Feature engineering / new models
               │                              justified ONLY at this depth
               │
               └──► [N10] A maintained multi-year research program exists
                          │
                          └──► [N11] Provider-independent framework generalization
                                     justified — requires ≥2 real integrations
                                     AND a validated edge worth maintaining
```

### Depth of each proposed investment, and its unmet dependencies

| Investment | Graph node | Unmet dependencies | Justified today? |
|---|---|---|---|
| Confidence calibration | **N1** | **none** | **YES** |
| Explainability validation | **N2** | **none** | **YES** |
| Empirical combiner priors | **N3** | none (verdict needs N5) | **YES, as a candidate** |
| Clean data purchase | **N0** | a maintainable delivery path | **YES** |
| The decisive experiment | **N5** | N0 | YES, immediately after N0 |
| Feature engineering | **N9** | N0, N5, N7 — **three** | **NO** |
| Model development | **N9** | N0, N5, N7 — **three** | **NO** |
| Windows VM | *off-graph* | requires "Norgate is uniquely adequate" — **unproven and probably false** | **NO** |
| Provider-independent framework | **N11** | N0, N5, N10, + ≥2 integrations — **four** | **NO** |

**The graph is the argument.** The two free investments sit at the root with zero prerequisites. The
two most expensive proposals sit at the deepest nodes with three and four unmet dependencies
respectively. The Windows VM is not on the graph at all — it descends from a premise no evidence
supports.

---

## PART 6 — Stop Conditions

*The most important section, and the one the project currently lacks. **These must be pre-registered
before the data is purchased** — the same discipline the CPE applied, which is this project's single
best habit. Declaring them after seeing results is worthless.*

**A necessary preamble.** The project has already brushed a stop condition: **four research phases,
zero promotions, headline result withdrawn.** A less disciplined program would already have stopped.
The reason it should not is specific and does not generalize: the *cause* of the failures was
diagnosed as a **proven instrument defect**, and instrument defects cost ~$600 to fix, whereas
hypothesis failures cannot be bought out of.

**That excuse is now spent. It was valid for the first four failures and will not be valid for the
fifth.** Once SE ≤ 0.025 is achieved, results are dispositive and "underpowered" is no longer
available as an explanation. Every condition below is written to be checkable on that footing.

### S1 — No measurable predictive signal → **terminate the prediction program**

**Sufficient evidence:** on ≥500 survivorship-clean names over ≥20 independent annual blocks, with
achieved SE ≤ 0.025, the best-performing available signal shows an IC 95% CI including zero **at
every horizon** *and* a point estimate < 0.02 at every horizon, *and* this holds against absolute,
benchmark-relative, and sector-relative targets.
**Then:** the price+macro information set has no exploitable stock-selection value. Stop all
predictive modeling. The reporting/falsification platform may survive (see S6).
*Why sufficient:* it is the project's own pre-declared threshold, on the sample size its own power
analysis specified, across all three clean targets, with the confound removed.

### S2 — Confidence cannot be calibrated → **stop shipping a decision tool**

**Sufficient evidence:** after a principled redesign (not a reparameterization), on a clean holdout,
the high-confidence bucket's directional accuracy is **not** materially greater than the
low-confidence bucket's, **and** ECE > 0.10.
**Then:** the platform cannot honestly communicate how much to trust any output. Stop presenting it
as decision support — **even if S1 is passed.** A system with real edge and inverted confidence
points users at its own worst calls.
*Why sufficient:* two independent studies already show inversion. A third failure after a deliberate
redesign establishes the construct is wrong in kind, not in tuning.

### S3 — Cannot beat trivial baselines → **terminate the modeling apparatus**

**Sufficient evidence:** on the clean holdout, the 7-model ensemble fails to beat **all three** of
(a) equal-weight/always-neutral, (b) simple 12-1 momentum, (c) a single-factor market-relative sort,
with a CI excluding zero.
**Then:** nine models, 68 features, and an evidence-combination engine are unjustified complexity.
Stop. Retain the evaluation harness.
*Why sufficient:* this is the minimum bar for the architecture's existence. A platform that cannot
beat 12-1 momentum has no claim on further engineering, whatever its internal elegance.

### S4 — Statistically inconclusive *at adequate power* → **stop; the effect is unexploitable**

**Sufficient evidence:** achieved SE ≤ 0.02 and the result is *still* inconclusive — CI straddling
zero with a point estimate in the 0.02–0.04 band.
**Then:** stop. This is **not** a "collect more data" verdict, and must not be allowed to become one.
It means any real effect is smaller than this platform's realistic data budget can ever resolve or
exploit. **This is the condition most likely to be rationalized away**, and it is therefore the most
important one to fix in advance.
*Why sufficient:* the requirement was self-specified at SE ≈ 0.02. Meeting it and still learning
nothing is a definitive answer about *feasibility*, not a request for a bigger sample.

### S5 — Research-productivity ceiling → **terminate the prediction program**

**Sufficient evidence:** **two further complete research phases after clean data lands with zero
promotion-gate passes.** The record is currently 4 phases / 0 promotions, excused by the instrument.
With the instrument fixed, phases 5 and 6 returning nothing is a verdict on the *hypothesis space*,
not the apparatus.
*Why sufficient:* it converts an open-ended program into a bounded one with a declared budget, which
is the only structure under which "we should stop" can ever actually be said.

### S6 — Full termination

**Sufficient evidence:** **S1 (or S3) AND a negative U3** — no measurable signal on clean data,
*and* the reporting/explainability layer is validated with a real user and found not to change any
decision.
**Then:** nothing of value remains. Archive the repository as a well-engineered negative result —
which it genuinely would be — and stop.
*Why sufficient:* these are the project's only two candidate value propositions. Both failing is
exhaustive. **Note the asymmetry: S1 alone is NOT sufficient for full termination**, which is
precisely why U3 must be tested *before* the U1 experiment reports, not after.

### What does NOT constitute a stop condition

Stated explicitly, to prevent the reverse error:

- Coin-flip performance **on the current underpowered survivor sample.** Already observed; already
  explained by a proven instrument defect. Not evidence of absence.
- Individual model rejections. Analogue and CPE were **correct** outcomes — the framework working.
- A negative U1 **alone**, if U3 is positive. That is a *pivot*, not a termination.

---

## PART 7 — Final Investment Committee Decision

### Recommendation: **4 — CHANGE RESEARCH DIRECTION**

Not "continue as planned," because the plan has accreted an infrastructure program the evidence does
not support. Not "buy Norgate now," because that specific vendor drags a Windows VM behind it and my
own prior approval was explicitly conditional on a macOS path that does not exist. Not "delay,"
because the decisive free experiment was already run and returned *"rebuild the evaluation
foundation."* Not "terminate," because the project's falsification record is genuinely valuable and
two of its three candidate value propositions have never been tested. Not "refactor the
methodology" — **the methodology is the best thing here** and refactoring it would be the one
unambiguous act of vandalism available.

**Precisely defined, the change of direction is:**

1. **Reject the bundle.** No Parallels, no Windows VM, no months-long ingestion framework (it
   already exists as two tested Protocols), no new features, no new models. **Hard freeze on model
   and feature development.**
2. **Fund the two free root-node items immediately** — confidence-construct redesign (U2) and
   explainability *validation with a human* (U3). Neither needs data. Both are unstarted. U3 in
   particular may reveal the project's actual product.
3. **Acquire clean data through the cheapest maintainable REST-native path** (Sharadar SEP +
   TICKERS via Nasdaq Data Link is the designated Primary-alt, rated "Easy" integration; **verify
   current pricing and delisted-name coverage before paying** — it may exceed $630, and that is
   still the right trade against a VM). Budget ~$600–800/yr. One vendor. Not two.
4. **Pre-register Part 6's stop conditions before the data lands.** Non-negotiable, and the reason
   this is a redirection rather than a continuation: the program acquires a declared budget and an
   exit.
5. **Run exactly ONE decisive experiment** — the U1 falsification on ≥500 clean names × ≥20 annual
   blocks, using only the five natively-testable models (momentum, relative_strength,
   sector_rotation from clean prices; macro_regime and interest_rate_sensitivity, which are
   identity-neutral and migrate free). Then **stop and re-convene.**
6. **Reframe the project's stated purpose** from "build a predictive scoring platform" to *"build an
   apparatus that can determine, honestly and cheaply, whether a proposed signal has value — and
   explain its reasoning."* That is what the project has actually demonstrated it can do. Four
   rigorous negative results and a self-caught leakage bug are the evidence.

### Confidence score: **78%**

**What the 22% consists of** — stated plainly rather than padded:

- **~8%** — the power margin is genuinely thin. My own arithmetic puts achieved SE at ≈ 0.021
  against a 0.02 requirement, with no margin. If cross-sectional correlation is worse than the
  ρ≈0.02 assumed, the decisive experiment could land in S4 territory and the $600 buys a
  more-expensive "cannot determine."
- **~7%** — vendor-delivery risk on the substitute. Sharadar's actual delisted coverage, history
  depth, and current price all need verification, and a REST-native vendor could still disappoint on
  delisting-return semantics, which is the disqualifying axis.
- **~5%** — I may be too generous. The disciplined reading of "four phases, zero promotions,
  headline withdrawn" is *terminate now*, and I am declining it on the strength of a diagnosed
  instrument defect. That diagnosis is well-evidenced, but it is still the project arguing its own
  appeal.
- **~2%** — U3 could be positive for the wrong reason: a report the owner finds interesting is not
  the same as a report that improves a decision.

### "If I spend the next six months following your recommendation, how much confidence do you have that it maximizes the probability of building a genuinely valuable quantitative research platform?"

**High — ~78% that this is the value-maximizing path.** But the honest answer requires separating
that from a question you did not quite ask, because conflating them is how research programs waste
years:

| Six-month outcome | P | Verdict |
|---|---|---|
| A **validated predictive edge** (CI excluding zero on clean data) | **~15%** | The dream case. Low probability, and the evidence says so |
| A **decisive negative** — no edge, proven at adequate power | **~55%** | A **successful** research outcome. It ends four phases of ambiguity and redirects the program correctly |
| **Still inconclusive** (S4 territory) | **~20%** | The real failure mode — and the one Part 6 exists to force a stop on rather than rationalize |
| Blocked on procurement/delivery | **~10%** | Recoverable; cheap to detect early |

So: **~70% probability of a decisive answer in six months, versus ~15% probability of a
predictive edge.** My recommendation maximizes the former, and I want the committee to fund it on
that basis and not on the latter.

The most likely genuinely valuable thing this project becomes is **not** an alpha engine. It is a
rigorous, honest, well-tested apparatus that can cheaply determine what *doesn't* work and explain
why — which, on the evidence, it already is. Four correct rejections, a self-caught leakage bug, and
a voluntarily withdrawn headline result are a better track record than most quantitative research
programs of this size ever produce. **That asset is real today, it cost nothing extra, and the
proposed investment bundle would have spent months burying it under infrastructure built in
anticipation of a signal nobody has yet demonstrated exists.**

Fund the $600 and the two free experiments. Freeze everything else. Re-convene in six months against
pre-registered stop conditions.
