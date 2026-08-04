# Theory of Constraints Analysis — The Project's True Choke Point

**Objective under evaluation:** *"Build a scientifically rigorous, historically validated, explainable
investment research platform that produces statistically defensible decision support."*

Every judgement below is made only against that objective.

---

## THE CHOKE POINT (stated first)

# The validation framework tests only for false positives. It has no test for false negatives — so the project cannot distinguish "no effect exists" from "our instrument cannot see it."

**Verified, not asserted.** `docs/VALIDATION_GATES.md` defines ten gates. A grep for
`power|detectable|false negative|sensitivity|positive control` across that file returns **zero
matches**. The closest gate, **G8**, is a *disclosure* rule:

> "Every reported cell carries n … Cells below minimum sample sizes are reported as statistically
> unresolved, never as evidence."

G8 requires you to **label** a Type II failure. It does not require you to **avoid** one, and nothing
requires a study to be *capable of resolving anything* before it is run. Combined with the promotion
discipline —

> "The default disposition for a model that fails any gate is shadow mode or rejection — never partial
> credit."

— the framework assigns **the same disposition to an underpowered study and a genuinely null one.** It
is structurally incapable of telling them apart, and it defaults both to rejection.

That is the constraint. Everything else in this document is its consequence.

---

## PART 1 — The system and its dependency graph

```
                        ┌─────────────────────────────────────────┐
                        │  L0  PLATFORM SUBSTRATE                 │
                        │  data engineering · reproducibility     │
                        │  STATUS: DESTROYED (outage, not a       │
                        │  constraint — see Part 2)               │
                        └───────────────────┬─────────────────────┘
                                            │
      ┌─────────────────────┬───────────────┼───────────────┬─────────────────────┐
      ▼                     ▼               ▼               ▼                     ▼
 historical data      identity mgmt    feature eng.    macro/rates          trading calendar
 (survivor-only)      (PIT, built)     (68 features)   (FRED)               (built)
      └─────────────────────┴───────────────┼───────────────┴─────────────────────┘
                                            ▼
                                  ┌──────────────────┐
                                  │ SIGNAL GENERATION│  9 models · all rejected/inconclusive
                                  └────────┬─────────┘
                                            ▼
                                  ┌──────────────────┐
                                  │ PROBABILITY GEN. │  se ≡ |effect/z| → +19pt overclaim
                                  │ + ENSEMBLE       │  weight = (z/effect)², Spearman −1.000
                                  │ + CONFIDENCE     │  ordering: inconclusive
                                  └────────┬─────────┘
                                            ▼
              ╔═══════════════════════════════════════════════════════════╗
              ║   *** THE CONSTRAINT STATION ***                          ║
              ║   HISTORICAL VALIDATION → "a validated claim"             ║
              ║                                                           ║
              ║   Throughput to date: ZERO claims in the project's        ║
              ║   entire history. 5 research phases, 0 promotions.        ║
              ║                                                           ║
              ║   Capacity is unknown because the instrument's minimum    ║
              ║   detectable effect has NEVER BEEN MEASURED.              ║
              ╚═══════════════════════════════════┬═══════════════════════╝
                                                   │  (nothing has ever flowed past here)
                    ┌──────────────────────────────┼──────────────────────────────┐
                    ▼                              ▼                              ▼
           statistical power              explainability                  portfolio simulation
           (σ_true unmeasured)            (built, never                   (ledger destroyed,
                                           shown to a human)               joint-returns blocked)
                    └──────────────────────────────┼──────────────────────────────┘
                                                   ▼
                                          PRODUCT ARCHITECTURE
                                                   ▼
                                             USER VALUE  ← untested, because nothing reached it
```

**The flow stops at one station.** Everything upstream works mechanically: 782 tests, exact combiner
replication to 2.8e-14, functioning reports, a PIT-clean feature store. Everything downstream is
untested *because nothing has ever flowed to it*.

---

## PART 2 — Every subsystem classified

| Subsystem | Classification | Why | Evidence | Remaining uncertainty |
|---|---|---|---|---|
| **Historical validation (MDE unknown)** | **CURRENT BOTTLENECK** | Zero claims have ever passed. Capacity unmeasured; underpowered and null results are indistinguishable and receive the same disposition | 10 gates, all Type I; zero grep matches for power/sensitivity/false-negative; G8 discloses rather than requires; 3 of the last 4 phases ended "cannot determine" | Whether capacity is genuinely low or merely unknown — **that is exactly what is unmeasured** |
| Data engineering / reproducibility | **PREREQUISITE, not a constraint** | An **outage**, not a capacity limit. Restoring it returns the system to its previously-blocked state; throughput does not improve | `mip`/`mip_scratch` hold only an empty `alembic_version`; PIT fundamentals snapshot and prediction archive permanently lost | None. It is 20 h of restoration |
| Statistical power (σ_true) | **Emerging — and a *proxy* for the constraint** | It is one (assumption-laden) analytical route to the quantity the constraint concerns. The analytical route has already failed twice | Equicorrelation formula misapplied to a correlation statistic, in two consecutive reviews; σ_true unidentifiable at 7-name breadth (negative implied variance at all 6 horizons) | Whether the variance model is even correctly specified |
| Probability generation / calibration | **Minor bottleneck (downstream)** | Real and measured, but it is a *finding* the constraint should have surfaced, not the constraint | +18–26 pp overclaim at all 6 horizons, CIs excluding zero; shrinkage optimum λ=0 | Whether it generalises past 7 tech names |
| Ensemble methodology / weighting | **Not currently limiting** | Provably degenerate, with **no measurable consequence** | `weight = (z/effect)²`; Spearman exactly −1.000; yet its beneficiary is LOO-harmless (−0.0106, CI includes 0) | None |
| Confidence estimation | **Not currently limiting** | Ordering inconclusive; the question collapses into base skill | +0.0667 [−0.0628, +0.2029]; sign flips across horizons; did not replicate | Underpowered either way — itself a symptom of the constraint |
| Historical data acquisition | **Not currently limiting** | Survivorship is real but does **not** cause the measured failure; and breadth saturates | 5 of 11 failure mechanisms data-invariant, incl. both causal ones; 500→5,000 names buys 7.8% | Conditional on the constraint being removed first |
| Signal generation / models | **Not currently limiting** | Cannot be judged without a working judge. ~0% historical promotion rate | 9 models, 0 promotions; no LOO removal helps with a CI excluding zero | Whether any model has real signal — unanswerable today |
| Feature engineering | **Not currently limiting** | 68 features, zero validated claims | — | — |
| Identity management | **Not currently limiting** | Built, tested, correct (Phase 1) | 8/8 acceptance scenarios | — |
| Explainability | **Emerging (parallel track)** | Genuinely parallel in *construction*; its **value** is gated by the objective's "statistically defensible" clause | Built, tested, committed examples; **never shown to a human** | Everything. The weakest link in "all downstream" — see Part 10 |
| Portfolio simulation | **Not currently limiting** | Ledger destroyed; joint-returns blocked below 60 common sessions | — | — |
| Product architecture | **Not currently limiting** | Excellent: Protocols, guardrails, checksums, 782 tests | — | — |
| User value | **Not currently limiting** | Untested because nothing reached it | — | — |

---

## PART 3 — TOC: the magic-solve test

*"If this subsystem were solved tomorrow, how much faster would the project progress?"*

| Subsystem | Sci. value | Product value | Eng. velocity | Uncertainty ↓ | Leverage | Return/hr | Return/$ |
|---|---|---|---|---|---|---|---|
| **Validation MDE known** | **Transformative** | High | **Transformative** | **Very high** | **Foundational** | **Very high** | **Very high** |
| Data engineering restored | Enabling | Low | Enabling | Low | Prerequisite | High | High |
| Calibration fixed | Low | **High** | Low | Low | Medium | High | ∞ ($0) |
| Explainability validated | Low | **Very high** | None | Medium | Medium (parallel) | Medium | Medium |
| Statistical power (σ_true) | Medium | None | Low | Medium | Medium | Medium | Medium |
| Historical data clean | Medium | Low | Low | Medium | Medium | Low | **Low** |
| Ensemble weighting fixed | ~Zero | ~Zero | None | ~Zero | Low | ~Zero | — |
| More models / features | ~Zero | ~Zero | Negative | ~Zero | Negative | **Negative** | — |
| Portfolio simulation | ~Zero | Low | None | ~Zero | Low | ~Zero | — |

### The magic-solve test, applied honestly

- **Solve the data problem tomorrow** (free Norgate, free Sharadar, 20 years, 3,000 names): you run the
  decisive study, get a CI, and **still cannot tell whether a null means "no effect" or "not visible."**
  You have bought a more expensive version of the same ambiguity.
- **Solve calibration tomorrow:** the scores become honest. Excellent for the product. **Zero** additional
  validated claims — you have made an unreadable instrument honest about being unreadable.
- **Solve the weighting tomorrow:** nothing changes. Measured: its beneficiary is LOO-harmless.
- **Solve the MDE tomorrow:** every one of the project's five historical results becomes **interpretable
  for the first time**, at zero marginal cost. Every future study becomes rejectable *before* it is run.
  Every data purchase becomes exactly priceable. And the project acquires, for the first time, a
  principled way to **stop**.

---

## PART 4 — Which previous recommendations addressed the constraint?

| Recommendation | Est. hours | Addressed the constraint? | Verdict |
|---|---|---|---|
| Purchase Norgate (my review #1) | ~5 (analysis) | **No** | Optimized a non-constraint. Recommended a purchase to feed an instrument of unknown sensitivity |
| Windows VM / Parallels | 0 (rejected) | **No** | Correctly rejected — but for the wrong reason (operating cost, not sensitivity) |
| REST-native provider substitution | ~3 | **No** | A vendor-selection optimization at a non-constraint station |
| Provider-independent ingestion framework | 0 (rejected) | **No** | Correctly rejected |
| Analytical power analysis (σ_true) | ~12 | **Partially — and it failed** | The right *target*, the wrong *method*. Attempted to **compute** what should have been **measured**, and got it wrong twice |
| Calibration / confidence work | ~10 | **No** | A downstream finding. Real, but it polishes output the instrument cannot certify |
| Weighting investigation | ~15 | **No** | Optimized a non-constraint. Concluded, correctly, that the weighting has no measurable consequence |
| Root-cause / attribution analysis | ~25 | **No — but it produced the evidence that located the constraint** | Diagnostic overhead. Valuable in retrospect |
| Paired baseline experiment | ~12 | **No** | Produced yet another set of inconclusive CIs — a *symptom* of the constraint, mistaken for a finding |
| Harness hardening (embargo, PIT poison) | ~40 | **No — it hardened the WRONG failure mode** | Improved the instrument's **Type I** properties only. This is the most instructive miss in the project |
| Phase 1 security master | ~60 | **No** | Infrastructure for a study that cannot yet be interpreted |
| Phase 2A native outcomes | ~60 | **No** | Same |
| Phase 3 identity migration (design) | ~15 | **No** | Same |
| Analogue model (build → RCA) | ~120 | **No** | Built, then killed. Correct Type I defence; no Type II diagnosis |
| Conditional Probability Engine | ~80 | **No** | Same |
| Portfolio / intelligence / reporting layers | ~120 | **No** (parallel) | Product work at a station nothing reaches |

### **Estimated hours spent optimizing non-constraints: ~575 of ~580.**

These are estimates from the project record, not measured. The point does not depend on precision.
**Not one hour in the project's history has been spent measuring whether its measurement pipeline can
detect a known effect.**

The most expensive single miss is the **harness hardening (~40 h)**: the project correctly identified
that its instrument was untrustworthy, invested seriously in fixing it — and fixed only the half that
produces *visible* wounds.

---

## PART 5 — Why every other candidate is downstream

**The choke point:** *the project cannot establish the sensitivity of its own measurement pipeline, so
no negative result it produces is interpretable.*

| Candidate | Why it is downstream |
|---|---|
| **Historical data / Norgate** | You buy data to feed an instrument. Sensitivity determines *how much* data is needed — the MDE sweep prices the purchase exactly. Buying first is buying a quantity you cannot specify |
| **Statistical power / σ_true** | The closest competitor, and genuinely the same concern — but it is an **analytical model** of the instrument, while the MDE is a **direct measurement** of it. The analytical route has already failed twice in this project. Measurement dominates estimation, and needs no variance-model assumption |
| **Calibration / probability generation** | A property of the output. It is precisely the kind of defect an MDE sweep *surfaces* — inject a known IC, watch the ordering survive while the probabilities come out badly scaled. A finding of the constraint work, not a rival to it |
| **Ensemble / weighting** | Measured to have no consequence (LOO-harmless despite Spearman −1.000). A non-constraint by direct test |
| **Signal generation / models** | Cannot judge a contestant without a working judge. 9 models, 0 promotions |
| **Feature engineering** | Three gates deep |
| **Data engineering** | A **prerequisite**, not a constraint — restoring it returns the system to its previously blocked state. TOC distinguishes an outage from a capacity limit |
| **Explainability / product / user value** | The objective's core is *"statistically defensible decision support."* Explaining a claim that cannot be certified is decoration. Its construction is parallel; its **value** is gated. **This is the weakest link in the argument — see Part 10** |
| **Portfolio simulation** | Downstream of a validated signal that does not exist |

---

## PART 6 — Five Whys

```
PROBLEM:  5+ research phases. 0 validated claims. Every headline result eventually withdrawn.
   │
   ▼ Why?
Every phase ended either "artifact" (caught) or "cannot determine" (uncaught).
   │
   ▼ Why the "cannot determine"?
Confidence intervals routinely included zero at the effect sizes the project cares about
(RS retirement [−0.005,+0.039]; CPE [−0.008,+0.015]; paired baselines all inconclusive;
 confidence replication [−0.063,+0.203]).
   │
   ▼ Why did that keep happening?
Studies were launched without knowing what effect size the pipeline could detect.
   │
   ▼ Why was that unknown?
Minimum detectable effect was only ever ESTIMATED analytically — never measured.
And the estimate was WRONG TWICE (equicorrelation discount misapplied to a correlation
statistic, in two consecutive committee reviews).
   │
   ▼ Why was it estimated rather than measured?
Because nothing required it. VALIDATION_GATES.md defines ten gates; grep for
power|detectable|false negative|sensitivity|positive control returns ZERO matches.
G8 requires DISCLOSING small n, not ACHIEVING adequate n.
   │
   ▼ Why is the framework asymmetric?
Because it is scar tissue. Every gate was added in reaction to a Type I failure the project
had actually SUFFERED and SEEN — the analogue leakage (G2/G3/G4), the +0.17 artifact
(G6/G9/G10), the inverted confidence (G7). Type II failures leave no visible wound: an
underpowered study looks exactly like a successful refutation. So nothing was ever built
against them, and they accumulated silently for the project's entire history.
   │
   ▼ Why? — ROOT REACHED. A further "why" adds nothing.
```

**Root cause: the framework defends against the errors the project has seen, and Type II error is
invisible by construction.**

---

## PART 7 — Counterfactual

### Unlimited resources for everything EXCEPT the choke point — would the project still fail?

# Yes.

And this is not a thought experiment: **the project has already run this counterfactual at small scale
and it failed.** Between the analogue study and today it acquired *more* data (7 → 31 names), *more*
models (7 → 9), *more* rigor (per-horizon embargo, PIT poisoning, pre-registration, immutable
archives) — and produced *more* unresolved results, not fewer.

With unlimited resources: 3,000 clean names, 25 years, twenty models, a team of engineers. Every study
still returns a CI. Every CI that includes zero still means either "no effect" or "not visible," and the
framework still assigns both to rejection. You would have industrialised the production of ambiguity.

### Only the choke point solved, everything else unchanged — would the project progress substantially?

# Yes, immediately and at zero marginal cost.

The moment the MDE is measured, on the panel that already exists:

1. **All five historical results become interpretable retroactively.** Each null resolves into either
   *"genuinely null — the effect is smaller than X, and we could have seen X"* (real knowledge) or
   *"was never testable"* (a redirect, and a refund on the conclusion). This is free — the data is
   already captured.
2. **Every future study becomes rejectable before it is run.** No further phase can be spent
   discovering after the fact that it never had the power to conclude.
3. **Every data purchase becomes exactly priceable.** Sweep breadth and years in the injection harness
   until detection succeeds; that is the specification. No vendor catalogue required, no σ_true model
   assumption required.
4. **The project acquires a principled way to stop** — if no attainable configuration detects an IC of
   0.03, the objective is unreachable at this budget, and that is a decisive, fundable answer.

**Everything else stays broken and the project still progresses**, because for the first time it would
know what its own results mean.

---

## PART 8 — Investment audit against the choke point

| Investment | Directly removes it? | Indirectly helps? | No effect? | **Distracts?** |
|---|---|---|---|---|
| **Synthetic positive control / MDE sweep** | ✅ **YES — the only item that does** | | | |
| Restore data layer + backups | | ✅ (hard prerequisite for the sweep) | | |
| Codify a power/sensitivity gate (G11) | ✅ (institutionalises the removal) | | | |
| σ_true analytical estimation | | ✅ (weakly — a proxy, already failed twice) | | |
| Calibration work | | ✅ (weakly — surfaced *by* the sweep) | | ⚠️ if done first |
| Human evaluation of explainability | | | ✅ (parallel track) | ⚠️ competes for the same 100 h |
| **Purchase Norgate** | ❌ | ❌ | | ⚠️ **DISTRACTS** — feeds an instrument of unknown sensitivity, and consumes the hours that would measure it |
| **Windows VM / Parallels** | ❌ | ❌ | | ⚠️ **DISTRACTS** — zero scientific content, plus ongoing maintenance drag |
| REST-native provider | ❌ | ❌ | | ⚠️ Distracts (same, cheaper) |
| Additional historical datasets | ❌ | ❌ | ✅ (breadth saturates: 7.8%) | ⚠️ |
| Ensemble/weighting rework | ❌ | ❌ | ✅ (measured: no consequence) | ⚠️ |
| New models / features | ❌ | ❌ | | ⚠️ **DISTRACTS heavily** |
| Portfolio simulation | ❌ | ❌ | ✅ | ⚠️ |

---

## PART 9 — The next 100 engineering hours

Every hour must remove or validate the constraint. Work that does not is rejected.

| Hours | Work | Why it is constraint work |
|---|---|---|
| **20** | **Restore the platform to runnable** — re-ingest prices + macro into the surviving 16-migration schema; verify the rebuild reproduces the archived captures byte-for-byte; automate backups | Hard prerequisite: the sweep cannot run otherwise. The reproduction check is *itself* an instrument test |
| **25** | **Build the synthetic-signal injection harness** — inject a known cross-sectional IC of specified size into the score stream, upstream of the existing validation path, so the *entire* pipeline (combiner → cohort → block bootstrap → gates) is exercised end-to-end | This is the instrument test. Assumption-free: no variance model, no σ_true, no vendor |
| **25** | **Run the MDE sweep** — injected IC × {0.01, 0.02, 0.03, 0.05, 0.10, 0.15} × breadth {7, 31, 100, 500} × years {4, 8, 15, 20} × 6 horizons. Report, for each configuration, the detection rate at 80% and 90% power | Produces the number the project has never had: **what can we actually see?** It also empirically prices any future data purchase |
| **15** | **Re-interpret every historical result against the measured MDE** — analogue, CPE, RS retirement, 1y decomposition, paired baselines, confidence replication | Free knowledge from data already captured. Converts five ambiguous nulls into either real findings or acknowledged non-experiments |
| **10** | **Codify G11 — a sensitivity gate** — no study may be run, and no disposition assigned, without a declared MDE and a demonstration that the configuration achieves it. Amend the promotion discipline so "underpowered" and "null" receive **different** dispositions | Institutionalises the fix so the constraint cannot silently re-form. Without this, the next phase repeats the pattern |
| **5** | Contingency | The restoration will surface surprises |
| **100** | | |

### Explicitly rejected from this budget

Norgate · Windows VM · Parallels · any data purchase · calibration work · human evaluation · new models
· new features · portfolio simulation · weighting rework.

**Note a deliberate change from my previous memo.** That memo funded calibration (20 h) and human
evaluation (15 h). Under TOC discipline both are **rejected here**, and the reason is not that they are
bad: it is that an investment-committee lens optimises a *portfolio of returns across stations*, while
TOC optimises *throughput at one station* and explicitly refuses local optima elsewhere. The two lenses
produce different allocations from identical evidence. I am applying the lens I was asked to apply, and
flagging the disagreement rather than papering over it.

---

## PART 10 — Falsification

### The strongest competing choke point

> **The information set itself contains no exploitable signal. The constraint is not the instrument —
> it is the material.**

**Evidence for it:** 5 phases, 0 promotions. The shrinkage sweep optimum is λ = 0 at every horizon with
**no interior optimum** — a strict test that the score's *ordering* carries nothing. Directional accuracy
is below 0.50 at three of six horizons. Short-horizon efficiency with respect to a price+macro
information set is also the theoretically expected result. If this is true, the MDE sweep will confirm
the instrument is fine and the project has simply been looking at an empty room with a working
telescope.

### The second competitor (weaker but real)

> **The objective is wrong. The project's value is explanatory, not predictive**, and the entire
> "statistically defensible decision support" clause is the thing to renegotiate.

This is the weakest link in my "everything is downstream" argument, and I flag it as such: the
explainability layer is genuinely parallel in construction, and it has **never been shown to a human** in
the project's entire history. If it turns out that users value the structured reasoning and ignore the
number, then the constraint is *product definition*, not measurement.

### The experiment that distinguishes them

**The same one.** The MDE sweep separates all three:

| Sweep result | Choke point is |
|---|---|
| Pipeline recovers an injected **IC = 0.03** on the *existing* panel with a CI excluding zero | **The information set.** The instrument is adequate; every historical null is real; stop prediction research |
| Pipeline needs **IC ≥ 0.10** to detect on the existing panel, but detects 0.03 at 500 names × 20 years | **The instrument, and it is fixable by data.** Buy data — and the sweep has just specified exactly how much |
| Pipeline cannot detect **IC = 0.03 at any attainable configuration** | **The instrument, and it is unfixable.** The objective is unreachable at this budget. Terminate the prediction program on evidence |

That the same 25-hour experiment resolves the choke point *and* its strongest competitor is the
strongest argument for running it first.

### The exact result that makes me abandon this conclusion

**If the sweep shows the pipeline detects an injected IC of 0.03 with ≥80% power on the existing
7-name / 8-year panel**, then the instrument was never the constraint, every historical null was a real
refutation, and the choke point moves immediately to the information set — with "stop prediction
research" as the live recommendation.

I consider this outcome **unlikely (~15%)** given a measured SE of 0.059 on the pooled 1m rank IC, but
it is exactly the result that would prove me wrong, and the experiment is designed to produce it if it
is true.

---

## PART 11 — Final memorandum

### 1. What is the project's true choke point?

The validation framework tests only for false positives. There is no test for false negatives, so the
project cannot distinguish "no effect exists" from "our instrument cannot see it" — and it has never
measured what its own pipeline can detect.

### 2. Why is it the choke point?

Because throughput at the validation station has been **zero for the project's entire history**, and the
reason is unknown-by-construction. Ten gates, verified: all Type I. G8 discloses small samples rather
than requiring adequate ones. The promotion discipline assigns underpowered and null studies the *same*
disposition. Three of the last four phases ended "cannot determine," and the project responded by
building more upstream capacity — more models, more data infrastructure, more rigor against leakage —
none of which can raise throughput at a station whose capacity is unmeasured.

### 3. Which previous recommendations addressed it?

**Essentially none.** The analytical power analysis aimed at the right target with the wrong method
(computing what should be measured) and produced a wrong answer twice. The harness hardening was
serious, correct instrument work — on the Type I half only.

### 4. Which optimized downstream symptoms?

Nearly all of it: ~575 of ~580 estimated hours. Norgate evaluation, the VM question, provider
selection, the weighting investigation, calibration work, Phase 1, Phase 2A, Phase 3 design, the
analogue model, the CPE, the paired baseline study, the portfolio and reporting layers. Several were
excellent work. None raised throughput at the constraint.

### 5. Is purchasing Norgate upstream or downstream of the choke point?

**Downstream — and currently a distraction.** Data feeds the instrument; sensitivity determines how much
is needed. The MDE sweep would *specify the purchase exactly*, replacing a vendor-catalogue decision
with a measured requirement.

### 6. Is maintaining a Windows VM scientifically justified?

**No — downstream of downstream.** It is a delivery mechanism for one vendor whose purchase is itself
downstream of an unmeasured gate. Zero scientific content at every node.

### 7. If the choke point were solved tomorrow, what becomes the next bottleneck?

**The information set** — whether price + macro contains any exploitable signal at all. The sweep will
have made that question answerable for the first time, and if the answer is no, the next constraint
after that is **product definition**: whether the explanatory layer is the real product. That question
is already ripe and has never been tested.

### 8. What should the next 100 hours accomplish?

A single deliverable: **a measured minimum-detectable-effect curve for this pipeline**, across effect
size × breadth × years × horizon — plus the retroactive re-interpretation of all five historical results
against it, and a G11 sensitivity gate so the constraint cannot silently re-form.

### 9. What single experiment would most reduce uncertainty?

**Inject a known signal and see whether the platform finds it.** Sweep the injected IC downward until
detection fails. That boundary is the number this project has been missing since its first research
phase, and it resolves the choke point and its strongest competitor simultaneously.

### 10. If this were my own project, on evenings and weekends, what would I do next?

Restore the database and turn on backups — the platform currently cannot run anything and has already
lost data permanently. Then write roughly fifty lines that add a known cross-sectional IC to the score
stream, run it through the existing validation path, and find the effect size at which the platform
stops seeing it.

Then I would take that number and re-read every research report this project has produced, and find out
how many of its conclusions it was ever entitled to.

I would not open a vendor website. I would not install Parallels. I would not write another model.

---

### The one-line version

**The project built an exquisite instrument for not fooling itself, and never checked whether it could
see anything — so it has spent its entire history unable to tell an empty room from a blind telescope,
and the next hundred hours should be spent turning on the light.**
