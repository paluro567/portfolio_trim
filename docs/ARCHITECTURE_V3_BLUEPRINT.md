# Version 3 — Definitive Blueprint

**Synthesis of:** the scientific reviews, the TOC constraint analysis, the choke-point review,
ARCHITECTURE_V2, the V2.1 refinement, the Decision Engine specification, and the adversarial CTO
review. **This is not a redesign.** It records what survived, deletes what did not, and states plainly
what is still unknown.

**Standing rule for this document:** where a prior review of mine conflicts with the CTO review, the
CTO review wins unless I can point to evidence it missed. I could not, in any material case.

---

## PART 1 — What survived every review

Thirteen ideas were attacked from at least three directions and held. They are **mandatory** in V3.

| # | Survivor | Why it survived |
|---|---|---|
| **1** | **Correct at zero signal** — the system must produce defensible recommendations with no predictive edge | Attacked by nobody, across five reviews. It is the only principle that makes the platform useful given what has actually been measured |
| **2** | **Evidence / Decision / Recommendation as three stages** | Preferences enter at the decision; falsification times differ; abstention has no home in a two-stage design. The CTO attacked the ledger and the score, not this |
| **3** | **No source reports its own precision** | Measured, not argued: `se ≡ \|effect/z\|` ⇒ `weight = (z/effect)²` ⇒ Spearman **exactly −1.000**. An algebraic identity, not a tuning error |
| **4** | **Influence is earned and revocable** | Survived as a principle. The CTO attacked whether the *directional* gate can ever open — a question about the gate's threshold, not about the principle |
| **5** | **Layer-specific ex-post tests** — policy on risk, evidence on descriptive accuracy, forecast on return | Demanding that a policy action predict returns is a category error. The CTO attacked the *circularity* of self-declared objectives, which is fixed in Part 4 — not the layering |
| **6** | **Evaluation contract declared at creation** | The only defence against a recommendation engine becoming unfalsifiable. Unattacked |
| **7** | **Abstention as a first-class, archived, scored output** | Attacked on frequency (a product problem) and gameability (fixable), never on principle |
| **8** | **The elimination trace** — "why not X" answered by the stage and rule that removed X | Survives with **reduced claims**: it explains the mechanism, not the judgment. Still the only structure that can answer "why not exit?" at all |
| **9** | **Immutable archive + byte-level reproducibility** | Universally endorsed. Already the platform's best-built property |
| **10** | **Source-agnostic decision logic** (no `if source == …`) | Makes adding and — critically — **removing** a source cheap and safe |
| **11** | **PIT discipline: embargo, price-poisoning, per-horizon observability** | The platform's strongest existing asset. It caught its own leakage |
| **12** | **Redundancy estimated, never declared** | Measured: declared priors were wrong in *both* directions (`momentum↔relative` 0.50 vs +0.513 correct; `rates↔macro` 0.50 vs **−0.003**) |
| **13** | **Conflict preserved, never averaged** | Averaging disagreement into a point estimate is how false precision is manufactured |

---

## PART 2 — What was rejected, and must never return

| # | Rejected | Why it must never return |
|---|---|---|
| **1** | **The Trim Score — and any cardinal 0–100 composite output** | Its constants (+25/+15/+8) are invented. Users will sort on it and treat differences as meaningful. **A decomposition of an arbitrary number is still arbitrary**, and the audit trail makes the false precision *more* dangerous. This is the single change the CTO review demanded and it is accepted without amendment |
| **2** | **`se ≡ \|effect / z_raw\|`** | Spearman −1.000 across all six active models. The model expressing itself in the smallest numbers won the vote |
| **3** | **`confidence = volume × agreement`** | Both terms measured to carry no predictive information; the price cluster manufactures agreement mechanically (+0.513) |
| **4** | **Declared correlation priors treated as truth** | Wrong in both directions, largest error an over-statement |
| **5** | **Prediction as the organising abstraction** | Ensemble loses to a constant 50% at all six horizons, every CI excluding zero. Shrinkage-optimal λ = 0 with **no interior optimum** |
| **6** | **Scoring policy actions on returns** | A category error that left V1 with nothing testable |
| **7** | **Validation against a self-declared objective alone** | Circular. Declare "keep concentration under 15%," trim above 15%, score 100%, learn nothing. **The most seductive flaw found in any review** |
| **8** | **The claim of "zero learned parameters"** | False. The priority order and ε bands *are* parameters — hand-set, therefore worse than fitted ones, which at least carry an estimation error |
| **9** | **Unattributed cross-horizon differences** | Same features + same rule + different window = noise. Reporting it as insight is what V1's cross-horizon notes did |
| **10** | **`valuation` as currently constituted** | 0.000 activation over 7,938 rows; LOO Δ exactly 0.0000 with a zero-width CI. Provably a no-op |
| **11** | **Historical analogues in the decision path** | Long-horizon performance was 100% leakage (1y 64.3% → 30.8% after embargo) |
| **12** | **Weighted-sum aggregation of incommensurables** | Requires unfalsifiable exchange rates and structurally cannot answer "why not?" |
| **13** | **Deferring the user study** | Recommended in three consecutive reviews and deferred three times. The revealed preference for building over validating is the most predictive fact in the project's file |

---

## PART 3 — What remains uncertain

### Engineering assumptions (untested)

| Assumption | Status |
|---|---|
| Descriptive reliability is measurable at all | **Never attempted for any source.** The V3 ledger's entire spine rests on it |
| The database can be restored and reproduce the archived captures byte-for-byte | Unverified. If it cannot, the historical evidence base is unusable |
| Correlation and risk-contribution estimates are stable enough to anchor Layer 1 | **The CTO's sharpest structural attack.** Layer 1 is claimed as "zero estimation error" but consumes estimated correlations, with a documented `None`-propagation failure below 60 common sessions |
| The walk-forward harness scales ~22× | Unmeasured |

### Scientific assumptions (untested)

| Assumption | Status |
|---|---|
| Any exploitable signal exists in this information set | **Unknown.** 65% confidence it does not |
| The pipeline's minimum detectable effect | **Never measured.** Estimated analytically twice; both estimates were wrong |
| The descriptive/directional split is honest rather than laundering | **I have no test that distinguishes them.** If a descriptive claim changes a trim's magnitude, it has moved money on an unvalidated basis. This is the strongest unanswered objection in the entire file |
| The DIRECTIONAL gate can ever open | Unknown, and possibly never |

### Commercial assumptions (untested)

| Assumption | Status |
|---|---|
| Anyone will pay for this | **Never tested.** ~580 hours, three redesigns, zero users consulted |
| Honest abstention is sellable | **Probably not.** Institutions buy conviction; the differentiator may be commercially negative |
| A buyer exists who is not already served by Aladdin / PORT / FactSet | Undefined |

### Product assumptions (untested)

| Assumption | Status |
|---|---|
| PMs value the elimination trace | Untested |
| An abstention rate above ~50% is tolerable | Untested, and likely to be high |
| A written investment policy can actually be produced | **Never attempted.** Layer 1 — the only working layer — depends on it entirely |
| **Deleting the score improves usability rather than harming it** | **Genuinely open.** Epistemically it is right; ergonomically I do not know. Part 6 makes it an explicit arm of the user study rather than an assumption |

---

## PART 4 — The Version 3 architecture

### Governing principle

> **Correct at zero signal. Every quantity presented to a user is either a measured fact in natural
> units, or an explicitly-labelled claim carrying its own reliability. Nothing in between.**

### The output object — what replaces the Trim Score

V3's per-position output is **an action, a natural-units magnitude, and a trace.** There is no
composite score.

```
NVDA · 1Y · TRIM (mandated)
  Basis:      concentration — 28.4% weight vs 15.0% policy cap  →  13.4pp over
  Magnitude:  reduce by 13.4pp of portfolio (≈ $X at current prices)
  Why not EXIT:   eliminated at Stage 1 — liquidity: 4.2 days to exit exceeds the 2-day limit
  Why not HOLD:   eliminated at Stage 2 — hard cap mandate
  Reverses if:    weight below 15.0%, OR the cap is revised
  Evidence:       3 claims, all CONTEXT tier, contributing 0
  Forecast:       contributed 0.0
  Confidence:     policy-arithmetic (near-certain). Not an evidence claim.
```

**Triage across a book is by partition and natural-units magnitude, never by a synthetic ranking:**

```
MANDATED (hard breach)     3 positions — ordered by percentage points over cap
DEVIATION (soft band)      7 positions — ordered by percentage points from target
WITHIN POLICY             42 positions — no action; 38 abstained on evidence
ESCALATE                   0 positions — no feasible action exists
```

"13.4pp over cap" is sortable, comparable, and cannot be invented. "77" is none of those things.

### Subsystems

| # | Subsystem | Exists to | Consumes | Produces |
|---|---|---|---|---|
| **S1** | **Substrate** — identity, PIT data, migrations, backups, reproducibility | Make every other subsystem's output reconstructable | Vendor + broker feeds | Versioned, checksummed data |
| **S2** | **Measurement** — position state, realised risk, correlation, tax lots, liquidity | Supply facts with zero forecast content | S1 | `PositionState` |
| **S3** | **Policy Artifact** — versioned, human-authored, **externally reviewed** targets, caps, bands, tax rules, objective ordering, ε | Hold every preference in the system, in one auditable, dated place | Human authorship | `PolicyArtifact@version` |
| **S4** | **Evidence Layer** — sources implementing one Protocol, emitting claims with observed effect and dispersion, no self-reported precision | Characterise *state*, never forecast | S1, S2 | `EvidenceClaim` |
| **S5** | **Reliability Ledger** — descriptive and directional reliability per source × horizon × regime; four-tier ladder with automatic demotion | Decide how much anything is allowed to matter | S8 archive, realised outcomes | `ReliabilityRecord`, influence tiers |
| **S6** | **Forecast Layer** — dormant | Supply directional expectation *if and only if* it ever earns DIRECTIONAL tier | S4, S5 | `Forecast` (currently: none admitted) |
| **S7** | **Decision Engine** — constrained lexicographic with bounded modulation; no composite score | Convert facts + preferences + claims into one action and its trace | S2, S3, S4, S5, S6 | `PositionDecision` + `DecisionTrace` |
| **S8** | **Decision Archive** — immutable, append-only, contract-stamped | Make every recommendation falsifiable at a declared future time | S7 | Archived decisions |
| **S9** | **Evaluation Suite** — layer-specific tests, counterfactual set, **external benchmark**, **terminal-wealth disclosure** | Prevent the platform from grading its own homework | S8, realised outcomes | Scorecards, ledger updates |
| **S10** | **Reporting** — decision-ordered, natural units, both sides of the evidence | Communicate to a human who must act | S7, S9 | Reports |
| **S11** | **Governance** — tier-cap changes, policy revisions, promotion decisions as immutable events requiring the same evidentiary standard as earning influence | Stop the architecture from being edited into V1 | Human + S5 | Governance log |

**S11 is new in V3**, and it exists solely because of the CTO's observation that the tier caps — the only structural defence against overclaiming — currently live in a YAML file that anyone can edit in thirty seconds.

### How they interact

```
   S1 SUBSTRATE ─────────────┬──────────────────────────────┐
                             ▼                              ▼
                     S2 MEASUREMENT                  S4 EVIDENCE LAYER
                     (facts, no forecast)            (state claims, no precision)
                             │                              │
   S3 POLICY ARTIFACT ───────┤                              ▼
   (all preferences,         │                      S5 RELIABILITY LEDGER ◄──── S9
    externally reviewed)     │                      (sets influence ceilings)     │
                             │                              │                     │
                             │                      S6 FORECAST (dormant)         │
                             ▼                              ▼                     │
                    ┌────────────────────────────────────────────┐               │
                    │           S7 DECISION ENGINE               │               │
                    │  constraints → mandates → lexicographic →   │               │
                    │  bounded modulation → abstention → trace    │               │
                    └──────────────────┬─────────────────────────┘               │
                                       ▼                                          │
                              S8 DECISION ARCHIVE ────────► S9 EVALUATION ────────┘
                                       │                    (external benchmark +
                                       ▼                     terminal-wealth
                                 S10 REPORTING               disclosure)
                                       │
                                 S11 GOVERNANCE (gates changes to S3 and S5)
```

**The load-bearing property:** delete S4, S5 and S6 and the system still runs — S2 + S3 + S7 produce
complete, defensible, natural-units recommendations. Nothing else in the architecture has that
property, and it is why V3 is buildable before any research question is settled.

---

## PART 5 — Existing subsystems mapped

| Subsystem | Verdict | Why |
|---|---|---|
| Historical Research Engine (PIT, embargo, poison tests) | **KEEP** | Best asset in the project. Untouched |
| Feature Store | **KEEP** | Works; PIT-clean |
| Data ingestion | **KEEP** (restore first) | Schema survives; database destroyed |
| Portfolio analytics | **KEEP — promote to S2, the spine** | Becomes the layer everything else is optional to |
| Immutable prediction archive | **KEEP — extend to S8** | Exists; gains the contract stamp and the feedback edge it was always shaped for |
| Attribution / explainability | **MODIFY** | Retain the exact-accounting invariant; retarget from score decomposition to elimination trace |
| Validation framework | **MODIFY** | Add a sensitivity gate, an **external benchmark**, and the terminal-wealth disclosure |
| Backtesting / walk-forward | **MODIFY** | Add staged positive controls and an MDE surface |
| Report generation | **MODIFY** | Natural units, partition-based triage, no composite score |
| Evidence models (rates, macro, momentum, sector, relative) | **MODIFY** | Retained as claim producers; strip `se`, `z`, and the 0–100 score |
| Ensemble combiner | **REPLACE** | The measured defect. `weight = (z/effect)²` |
| Confidence engine | **REPLACE** | `volume × agreement`; both terms carry no information |
| Trim score engine | **DELETE** | Not replaced. Nothing takes its place |
| Cross-horizon notes | **DELETE** | Reported noise as insight |
| `valuation` model | **DELETE from the registry** | Provable no-op. Re-admit only when PIT fundamentals exist |
| Historical analogues (decision path) | **DELETE** | 100% leakage at long horizons |
| Conditional Probability Engine (decision path) | **DELETE** | Edge was era persistence; confidence inverted |
| Declared correlation priors | **DELETE** | Wrong in both directions |
| Decision Engine spec | **MODIFY** | Adopt, minus the Trim Score; add S11 governance |
| Reliability Ledger spec | **KEEP as spec** | But it is a *specification with an empty implementation*, and descriptive reliability has never been measured |

---

## PART 6 — The next twelve months

Sequenced so that **the cheapest experiment that can kill the project runs first.**

### Phase 0 — Restore (Weeks 1–2) · ~25 h · $120

**Objective:** make the platform able to run anything.
**Deliverables:** rebuilt data layer; automated offsite backup; a restore drill; byte-level
reproduction of the archived captures.
**Success:** the archived validation artifacts reproduce exactly.
**Dependencies:** none. **Why first:** unconditional blocker; a permanent data loss has already
occurred.

### Phase 1 — The user study (Weeks 3–4) · ~15 h · $300 · **HARD GATE**

**Objective:** find out whether anyone wants this before spending anything else.
**Deliverables:** pre-registered protocol; ≥ 5 participants who manage real money; measurement of
**decisions changed**, not stated interest; an explicit arm testing **score vs no-score** presentation.
**Success (declared in advance):** ≥ 1 in 3 sessions produce a decision the participant would not
otherwise have made, attributable to a named report section.
**Failure:** the project stops. **It does not iterate on the architecture again.**
**Why here:** this test has been recommended in three consecutive reviews and deferred three times.
Running it fourth would be the defining failure of this project.

### Phase 2 — Policy artifact + Layer 1 (Months 2–3) · ~80 h · $0

**Objective:** ship a complete, defensible recommendation system with **no evidence and no forecast**.
**Deliverables:** written, externally-reviewed investment policy (S3); measurement layer (S2); decision
engine constraints/mandates/lexicographic stages (S7); archive with contracts (S8); partition-based
reports (S10); governance log (S11).
**Success:** every position receives an action with a natural-units basis and a complete elimination
trace; zero composite scores anywhere; 100% mechanical invariants.
**Why here:** it is the only part of the system whose correctness does not depend on an unresolved
research question.

### Phase 3 — Measurement infrastructure (Months 4–6) · ~120 h · $0

**Objective:** find out what this platform can actually see, and whether any source is descriptively reliable.
**Deliverables:** three-arm staged positive control (score-level, feature-level, real anomaly) → an MDE
surface; the first **descriptive** reliability measurements; sensitivity gate (G11); re-interpretation of
all five historical results against the measured MDE.
**Success:** an MDE surface exists; ≥ 1 source clears the CONTEXT gate on descriptive reliability.
**Why here:** it resolves the remaining scientific uncertainty, and — importantly — **it is designed to
be able to refute the whole programme.**

### Phase 4 — Evidence at CONTEXT tier (Months 7–9) · ~80 h · $0

**Objective:** admit evidence as displayed context, contributing zero.
**Deliverables:** S4 sources emitting claims without self-reported precision; S5 ledger populated with
real descriptive scores; both-sides evidence display.
**Success:** evidence appears in reports; `forecast_contribution = 0.0` and `evidence_contribution = 0`
on every decision; the second user study shows evidence display changes decisions.
**Why here:** evidence is admitted only after its reliability can be measured — never before.

### Phase 5 — Evaluation loop and interim verdict (Months 10–12) · ~90 h · $0

**Objective:** close the loop and make an evidence-based continuation decision.
**Deliverables:** layer-specific scoring; the three counterfactuals; **external benchmark**;
**terminal-wealth disclosure**; abstention scoring; the 12-month go/no-go.
**Success:** ≥ 100 archived decisions scored; the engine beats the policy-only counterfactual on its
declared objective; terminal-wealth disclosure reported honestly whatever it says.
**Why here:** a year of decisions is the minimum to evaluate anything, and the interim gate must not
require two regime transitions.

**Forecasts are not built in year one. That is deliberate and it is the point.**

### Why this order minimises risk

Cheapest kill first (Phase 1, $300). Then the only thing that works today (Phase 2), which ships a real
product independent of every open research question. Then the measurement that could refute the
programme (Phase 3). Evidence is admitted only after it can be measured (Phase 4). Evaluation closes the
loop (Phase 5). **At no point is capital committed to a capability whose value has not already been
demonstrated by the preceding phase.**

---

## PART 7 — Data requirements

### Is data now the primary bottleneck? **No — and V3 makes that more true, not less.**

The decisive and underappreciated point: **survivorship bias barely affects Layer 1.** You are
estimating the risk and concentration of positions you *currently hold*, which are by definition
extant. Survivorship bias corrupts *backtesting a strategy across a universe*; it does not corrupt
*measuring the present risk of a present portfolio*. Since V3's working layer is exactly the latter, the
data question is demoted again.

| Rank | Gap | Impact | Needed before 1.0? | Notes |
|---|---|---|---|---|
| **1** | **The investment policy document** | **Blocking** | **YES** | Not a data source — the largest gap in the project. Layer 1 is the only working layer and is meaningless without it |
| **2** | **Corporate actions + cost basis accuracy** | **High** | **YES** | Tax efficiency ranks P4 in the objective ordering. A wrong cost basis produces a confidently wrong tax-aware recommendation |
| **3** | **Liquidity data (ADV, spread)** | Medium-high | **YES** | Stage 1 hard constraints prune on days-to-exit. Without it, the engine recommends the unexecutable |
| **4** | Sufficient price history for stable correlation | Medium | **YES** | The CTO's seam attack: Layer 1 consumes estimated correlations. The ≥ 60-session requirement is a real constraint |
| **5** | PIT fundamentals | Low **now** | **No** | Only unlocks valuation evidence, which is deleted from the registry. Revisit at Phase 4+ |
| **6** | **Survivorship-clean history** | Low **now** | **No** | Required **only** for DIRECTIONAL promotion, which is gated behind the Phase 3 MDE result — and may never be reachable. Do not purchase before Phase 3 reports |
| **7** | Analyst revisions, positioning, options | Low | **No** | New information families. Years away, and only if Phase 3 shows the instrument can see anything |

**Essential before 1.0: items 1–4, of which only 2–4 are data and all three are already obtainable
free.** Item 1 is not an engineering task at all.

---

## PART 8 — Final verdict

### Would I build V3 exactly as specified? **Almost. One final modification.**

The strongest attack in the CTO review remains unanswered by everything above:

> *"It will systematically trim winners and hold losers — and pass its own validation while doing it. A
> system that is correct by its own metric and wrong for its owner is the most dangerous kind, because
> nothing in the framework will ever flag it."*

That is correct. Layer-specific scoring grades the policy layer on realised **risk**, which is the right
test for the claim it makes — and precisely because it is the right test, it will never notice that the
owner got poorer.

### The final modification: the Terminal-Wealth Disclosure

> **Every evaluation cycle must report, permanently and non-optionally, the realised terminal wealth of
> following the platform's recommendations versus the do-nothing counterfactual — even though the
> platform does not optimise for it, and even when the comparison is unfavourable.**

Three properties make this the right fix rather than a reintroduction of prediction:

1. **It is a disclosure, not an objective.** Making terminal wealth the objective would put forecasting
   back at the centre — the error V1 made. Making it a *permanent mandatory report* keeps the objective
   honest while removing the system's ability to hide behind it.
2. **It is measurable without any predictive skill.** It is arithmetic on realised prices.
3. **It cannot be gamed by the objective ordering**, because it is not derived from the objective. It is
   the one number in the entire evaluation suite that the platform does not get to define.

Combined with the external benchmark, this closes the circularity that was the most seductive flaw
found in any review: **the platform may declare its own objective, but it may not be the sole author of
its own scorecard.**

### With that addition, V3 stands. What it actually is

A system that, on the day it ships, will tell a portfolio manager: *"Your position is 13.4 percentage
points over your stated cap. Here is what you cannot do and why. Here is what would reverse this. We
have three pieces of relevant context and no reliable view on direction. Following our advice over the
past year would have left you here; doing nothing would have left you there."*

That is a modest product. It is also, on the evidence assembled across six reviews, **the most that can
be honestly built** — and it is more than this project has ever produced.

### The condition that outranks the blueprint

**None of this is authorised until Phase 1 passes.** If ≥ 5 people who manage real money do not change
a decision because of these reports, the correct action is to stop — and this document, the
architecture it describes, and the 580 hours behind it become a well-documented negative result.

That would be a genuine scientific contribution. It would not be a product, and V3 must not be built as
though the difference does not matter.
