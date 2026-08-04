# Decision Engine — Specification

**Status:** design specification, suitable for implementation.
**Depends on:** [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md), [ARCHITECTURE_V2.1_REFINEMENT.md](ARCHITECTURE_V2.1_REFINEMENT.md) (both accepted).
**Scope:** the subsystem that converts policy, evidence, forecasts and investor objectives into one
defensible recommendation per holding per horizon.

---

## PART 1 — Should a Decision Engine exist?

### Yes. `Evidence → Recommendation` is a category error, and it is the specific error V1 made.

Three reasons the middle stage must be explicit.

**1. Preferences enter at the decision, not at the evidence.**
Evidence is investor-independent: *"this position is 28.4% of the portfolio"* is true for everyone.
A decision is investor-dependent: two investors with identical positions and identical evidence should
receive **different** recommendations if their tax situation, mandate, or risk tolerance differ. Going
`Evidence → Recommendation` hard-codes one investor's preferences into the evidence layer — precisely
the contamination the three-layer separation exists to prevent.

**2. Falsification times differ.**
Evidence is falsifiable **now**. A decision is falsifiable only against a **counterfactual plus a
stated objective**. Merge them and the evidence becomes untestable, because any failure can be
attributed to preferences. V1's `TrimAssessment` merged a state claim, a forecast, an action and a
confidence into one number — which is exactly why, when it failed, the platform could not identify
*which part* had failed.

**3. Abstention is a decision-layer concept.**
Evidence always exists. A *decision* may legitimately be "insufficient basis to act." There is no
coherent place for abstention in a direct evidence→recommendation mapping, and abstention is the single
most important output this platform can produce today.

### The three stages, precisely

| Stage | Question | Investor-dependent? | Falsifiable |
|---|---|---|---|
| **Evidence** | *What is true?* | No | Now |
| **Decision** | *Which action best satisfies the objective ordering, given constraints?* | **Yes** | Against a counterfactual + objective |
| **Recommendation** | *What should be communicated to this decision-maker, when, with what caveats?* | **Yes** | By observed behaviour |

The third stage is not packaging. It handles **actionability** (can this investor execute?), **timing**
(act now / schedule / monitor), and **communication order**. A correct decision that cannot be executed
is not a recommendation.

---

## PART 2 — Responsibilities

| Responsibility | Inside the Decision Engine? | Rationale |
|---|---|---|
| Resolve conflicting evidence | **YES** | Conflict resolution requires the objective ordering. Layer 2 must *preserve* conflict, not resolve it |
| Determine when evidence is sufficient | **YES** | Sufficiency is relative to the decision at stake, not a property of the evidence |
| Incorporate portfolio policy | **YES** — as a *consumer* | The policy is a versioned config artifact (Layer 1). The engine applies it; it does not own it |
| Apply investor preferences | **YES — exclusively** | This is the engine's defining responsibility. Preferences must appear nowhere else |
| Handle uncertainty | **YES** | Bounding influence by reliability is a decision rule |
| Determine abstention | **YES — exclusively** | See Part 1 |
| Adjust for horizon | **YES** | Admissibility, constraints and reversibility are horizon-dependent decision inputs |
| Generate recommendation | **YES** | The primary output |
| Generate **explanation** | **YES** — as a *by-product of the trace*, never post-hoc | An explanation reconstructed after the fact is rationalisation. It must be the elimination trace itself |
| Generate confidence | **YES** — assembly only | Components come from the ledger and Layer 2; the engine assembles and applies the ceiling |
| Generate trim score | **YES** | It is the decision's own summary, not an evidence property |
| Generate **scenario analysis** | **NO — Layer 2** | Conditional sensitivities are measurements of state, not decisions |
| Compute reliability | **NO — Reliability Ledger** | The engine must never be able to grant itself influence |
| Produce evidence claims | **NO — Layer 2** | |
| Fit or train anything | **NO — nothing** | The engine has zero learned parameters. See Part 4 |

**Two exclusions are load-bearing.** The engine may not compute reliability (or it could authorise its
own influence), and it may not fit parameters (or it becomes a model, subject to the overfitting and
calibration failures the architecture is designed to escape).

---

## PART 3 — Inputs

| Input | Source | How it influences the decision |
|---|---|---|
| **Position state** — weight, cost basis, lots, unrealised P&L | L1 measurement | Determines *whether a decision is even required*. Drives policy-deviation magnitude |
| **Target allocation, caps, bands** | Policy artifact | **Mandates** actions on hard breach; **admits** actions within bands |
| **Hard constraints** — mandate limits, restricted list | Policy artifact | Binding. Prunes the action set before anything else runs |
| **Liquidity** — ADV, days-to-exit, spread | L1 measurement | Prunes infeasible magnitudes; sets timing (immediate vs scheduled) |
| **Tax information** — lot ages, unrealised gain, wash-sale windows | L1 measurement | A lexicographic objective (P4). Can defer or stage an action; **cannot veto a hard breach** |
| **Risk limits** — concentration, HHI, correlation cluster, risk contribution | L1 measurement + policy | Lexicographic objective P3. The dominant discriminator today |
| **Evidence claims** | L2 | Modulate choice, magnitude, urgency and conviction **within** the feasible set. Bounded by tier |
| **Forecast objects** | L3 | Tie-break within the feasible set — **only** at DIRECTIONAL tier. Currently never fires |
| **Reliability Ledger** | Ledger | Sets the **influence ceiling** for every source. The engine reads it and can never write it |
| **Catalysts** — dated, confirmed | L1/L2 | Alter *admissibility by horizon* and set urgency. Never a return input |
| **Market regime** | L2 | Selects the reliability cell to read; may trigger DIRECTIONAL→ADVISORY demotion |
| **Investor profile** — objective ordering, tolerances, horizon priorities | **Policy artifact** | Supplies the lexicographic ordering and tolerance bands ε. **The only place preferences enter** |
| **Correlation / cluster membership** | L1 measurement | Feeds P3; a position may be trimmed for its *cluster's* concentration, not its own |
| **Historical analogues** | L2, CONTEXT tier | Displayed. Contribute **zero** to the decision until promoted |
| **Macro environment** | L2 | Evidence like any other; no privileged status |
| **Prior decision** (archived) | Archive | Produces `what_changed` and enforces stability suppression |

---

## PART 4 — Decision logic

### Chosen architecture: **Constrained lexicographic decision with bounded evidence modulation, and a dormant expected-utility stage.**

### Why not the alternatives

| Candidate | Rejected because |
|---|---|
| **Weighted evidence / MCDA** | Requires exchange rates between incommensurable quantities (*how much tax drag equals how much concentration risk?*). Those weights are unfalsifiable, and — decisively — **a weighted sum cannot answer "why not?"**, because every option received a little of everything |
| **Expected utility / Bayesian** | Requires a trusted probability distribution over outcomes. That is precisely what the platform does not have. Using EU with uncalibrated probabilities is the V1 failure in new clothing |
| **Pure rule engine** | Auditable and graceful, but cannot express gradation, and grows into an unmaintainable thicket |
| **Hierarchical rules alone** | Too rigid: ignores near-misses, so a position at 14.9% against a 15% cap is treated identically to one at 4% |

### Why lexicographic ordering wins

1. **It requires only a priority order, which an investor can actually state** — not an exchange rate they cannot.
2. **It matches how institutional mandates already work.** You do not trade a hard limit against alpha; you satisfy the limit.
3. **It produces an elimination trace for free.** Every rejected action carries the stage and rule that eliminated it — which is exactly the "why not?" a PM asks and which a weighted sum structurally cannot provide.
4. **It degrades correctly to zero signal.** With no admissible evidence it resolves on policy and risk alone and is still fully defensible.

**Tolerance bands (ε) fix the rigidity:** within ε of a higher-priority objective's optimum, lower
priorities are permitted to discriminate. This makes the ordering *lexicographic-with-slack* rather
than brittle.

### The algorithm

```
STAGE 0  ADMISSIBILITY
   admissible_evidence ← {c ∈ claims : c.admissible_at(horizon) ∧ tier(c) ≥ CONTEXT}
   directional_forecast ← forecast if tier(forecast) = DIRECTIONAL else ∅

STAGE 1  HARD CONSTRAINTS                                    [binding · prunes the action set]
   A ← {ADD, HOLD, TRIM, EXIT} × magnitudes
   remove actions violating: mandate limits, restricted list,
                             liquidity floor (days_to_exit ≤ limit),
                             wash-sale window, minimum trade size
   if A = ∅ → emit ESCALATE (a real, archived outcome — never a silent HOLD)

STAGE 2  MANDATED ACTIONS                                    [policy breach ⇒ action determined]
   if hard cap breached      → action := TRIM, magnitude := to-cap   (mandate)
   if below minimum position → action := EXIT or ADD                 (mandate)
   if mandate exists: evidence may set URGENCY and magnitude WITHIN the mandated band only.
                      It may NOT flip the action. Record mandate_basis.

STAGE 3  LEXICOGRAPHIC RESOLUTION                            [no mandate]
   for each objective P₁..Pₙ in investor-declared priority order:
       score every surviving action on Pᵢ
       A ← {a ∈ A : Pᵢ(a) within εᵢ of best}
       if |A| = 1: break
   default order:  P1 capital-preservation constraints
                   P2 policy compliance (soft bands)
                   P3 risk budget (concentration, cluster, contribution)
                   P4 tax efficiency
                   P5 evidence-informed positioning
                   P6 transaction-cost minimisation
   Record, for every eliminated action, the objective and threshold that eliminated it.

STAGE 4  BOUNDED EVIDENCE MODULATION
   for each admissible claim c:
       Δ ← contribution(c) capped by tier:
              CONTEXT     → 0            (displayed, never counted)
              ADVISORY    → ±10 pts, may adjust magnitude/urgency, MAY NOT flip the action
              DIRECTIONAL → ±20 pts, may flip within the feasible set
       accumulate into evidence_contribution
   Conflicts are NOT averaged: opposing admissible claims widen the outcome band and
   lower recommendation_confidence.

STAGE 5  FORECAST STAGE                                      [DORMANT until a forecast is promoted]
   if directional_forecast ≠ ∅:
        expected-utility tie-break among surviving actions
   else:
        forecast_contribution := 0.0        ← printed on every recommendation today

STAGE 6  ABSTENTION CHECK
   if |A| > 1 ∧ no admissible evidence discriminates ∧ no mandate:
        action := HOLD, abstained := True, abstention_reason := <specific>
   Abstention is archived and scored (Part 8). It is never free.

STAGE 7  SCORE ASSEMBLY       action_strength = 50 + Σ contributions   (must sum EXACTLY)
STAGE 8  CONFIDENCE ASSEMBLY  six components; ceiling = max reliability of contributing sources
STAGE 9  BOUNDARY CONDITIONS  per contribution, the threshold at which the action changes
STAGE 10 HORIZON RECONCILIATION  attribute every cross-horizon difference or suppress it
STAGE 11 RECOMMENDATION PACKAGING  actionability, timing, explanation, evaluation contract
```

**The engine has zero learned parameters.** Everything configurable — the priority order, ε bands, tier
caps, rubric points — is declared in a versioned artifact, not fitted.

---

## PART 5 — The Trim Score

### Definition

> **`action_strength` ∈ [0, 100]: the strength of the case for reducing exposure to this position at
> this horizon, given policy, admissible evidence and binding constraints.**
> 50 = no case in either direction. >50 = case to reduce. <50 = case to add.
> It is a **rubric-anchored ordinal**, not a probability, and it is never produced by mapping a z-score
> through Φ.

### What it is not

| Not | Why they are different |
|---|---|
| **A return prediction** | It answers *"how strong is the case to act?"*, not *"which way will it go?"* A position can score 85 with `forecast_contribution = 0.0` |
| **Confidence** | The score is the **strength of the case**; confidence is **how much to trust that assessment**. 80 with confidence 0.25 = *"strong case, weakly supported"* — a meaningful and common state |
| **Risk** | Risk is an *input*. A volatile position at 2% weight, inside policy, scores near 50 |
| **Expected return** | Orthogonal. A position with the best outlook in the book still scores high if it is 30% of it |

### Composition — rubric-based and exactly decomposable

```
action_strength = 50
                + policy_contribution      (rubric: cap breach +25 · band breach +15 · drift +8,
                                            scaled by breach magnitude)
                + risk_contribution        (cluster concentration, risk-contribution excess)
                + tax_contribution         (can be NEGATIVE — a large embedded gain reduces the case)
                + liquidity_contribution
                + evidence_contribution    (bounded by tier: 0 / ±10 / ±20)
                + forecast_contribution    (0.0 today, always)
```

Every term is attributable to a rule and a threshold. The sum is exact — enforced by test, as the
current attribution engine already does.

### Horizons: **five separate scores, not one score with adjustments**

Separate, because the *inputs* genuinely differ: admissible evidence, binding constraints, reversibility
cost and event proximity are all horizon-specific. A single adjusted score would misrepresent that as a
decay function.

Constrained by the V2.1 invariant: **every cross-horizon difference must carry a `DifferenceCause`
(OBJECTIVE | ADMISSIBLE_EVIDENCE | BINDING_CONSTRAINT | REVERSIBILITY). Unattributable differences are
suppressed and the scores equalised to the longer horizon.** The enum has no `NOISE` member.

---

## PART 6 — Recommendation generation, end to end

Per `(position, horizon)`:

| # | Stage | Output | Failure mode it prevents |
|---|---|---|---|
| 1 | **Load position state** | Measured weight, lots, P&L, liquidity | Deciding on stale state |
| 2 | **Load policy** (versioned) | Targets, caps, bands, ordering, ε | Preferences leaking into evidence |
| 3 | **Collect evidence claims** | Claims + tiers from the ledger | Unvetted sources influencing |
| 4 | **Filter by horizon admissibility** | Admissible subset | A 1Y valuation claim driving a 1W call |
| 5 | **Read the Reliability Ledger** | Per-source influence ceilings | Self-authorised influence |
| 6 | **Prune by hard constraints** (Stage 1) | Feasible action set | Recommending the unexecutable |
| 7 | **Check for mandate** (Stage 2) | Mandated action, or none | Evidence overriding a hard limit |
| 8 | **Lexicographic resolution** (Stage 3) | Surviving set + elimination trace | Unfalsifiable weighted trade-offs |
| 9 | **Evidence modulation** (Stage 4) | Adjusted magnitude, urgency, conviction | Unbounded influence |
| 10 | **Forecast stage** (Stage 5) | Tie-break *or* `contribution = 0.0` | Silent forecast creep |
| 11 | **Abstention check** (Stage 6) | Action or explicit abstention | Manufacturing a view |
| 12 | **Assemble score** (Stage 7) | `action_strength` + decomposition | Unattributable numbers |
| 13 | **Assemble confidence** (Stage 8) | Six-component profile + ceiling | The +18–26 pp overclaim |
| 14 | **Compute boundaries** (Stage 9) | Thresholds, nearest binding | "Trust me" recommendations |
| 15 | **Reconcile horizons** (Stage 10) | Term structure + causes | Reporting noise as insight |
| 16 | **Diff vs archive** | `what_changed` + `change_driver` | Churn without cause |
| 17 | **Stability suppression** | Suppress if `change_driver = NONE` | Recommendation flip-flop |
| 18 | **Actionability & timing** | IMMEDIATE / SCHEDULED / OPPORTUNISTIC / MONITOR | Correct-but-unexecutable advice |
| 19 | **Stamp evaluation contract** | Declared ex-post test | Unfalsifiability |
| 20 | **Archive immutably** | Append-only decision record | Retrospective revision |

---

## PART 7 — Explainability

The explanation is **the elimination trace**, emitted by the engine as it runs. It is never
reconstructed afterwards — a post-hoc explanation is rationalisation, and it can drift from the actual
computation.

| Question | Mechanism | Example |
|---|---|---|
| **Why?** | Contribution decomposition + mandate basis | *"TRIM. Policy +25 (cap breach: 28.4% vs 15%). Risk +6 (cluster 0.71). Tax −4 (embedded gain). Evidence 0 (all sources CONTEXT tier). Forecast 0.0. Score 77."* |
| **Why not?** | **Elimination trace** — every rejected action with the stage, rule and threshold that removed it | *"EXIT eliminated at Stage 1 — liquidity: 4.2 days to exit exceeds the 2-day limit. HOLD eliminated at Stage 2 — hard cap mandate."* |
| **What changed?** | Diff vs the archived prior decision, with `change_driver` | *"Score 71 → 77. Driver: POSITION_DRIFT — weight rose 26.1% → 28.4% on price appreciation. No new evidence; no reliability change."* |
| **What would change my mind?** | Boundary conditions + nearest binding + monitoring triggers | *"HOLD below 15.0% weight (−13.4pp, ≈ −47% price move or a 3.1pp portfolio inflow). Nearest boundary: cluster correlation below 0.55 would remove +6."* |

**"Why not?" is the differentiator, and it is the direct payoff of choosing a lexicographic engine.**
A weighted-sum engine cannot answer it: every option received a fraction of every criterion, so there
is no stage at which anything was *eliminated*. Institutional PMs ask "why not exit?" at least as often
as "why trim?", and no scoring system this platform has built could ever answer it.

---

## PART 8 — Scientific validation

The engine's own claim is: *"given these inputs and this declared objective ordering, this is the action
that best satisfies it."* That is falsifiable four ways.

### 1. Mechanical invariants — machine-checkable, every run

| Invariant | Test |
|---|---|
| **Determinism** | Same inputs + same policy version ⇒ byte-identical decision |
| **Exact decomposition** | `action_strength = 50 + Σ contributions` to floating-point |
| **Influence ceiling** | No source contributes more than its tier permits |
| **No preference leakage** | AST test: the engine imports the policy artifact; Layer 2 imports **nothing** from the policy |
| **No self-authorisation** | AST test: the engine never writes to the Reliability Ledger |
| **Mandate supremacy** | No evidence configuration can flip a mandated action |
| **Horizon attribution** | Every emitted cross-horizon difference carries a `DifferenceCause` |

### 2. Objective-specific scoring — the key move

**Score the engine on the objective it claims to optimise, not on return.**

| If the declared objective is | Score it on | Requires forecasting? |
|---|---|---|
| Keep concentration under 15% | Realised max concentration over the period | **No** |
| Minimise tax drag | Realised taxes paid vs counterfactual | **No** |
| Keep cluster correlation under 0.6 | Realised cluster correlation | **No** |
| Reduce drawdown contribution | Realised contribution to portfolio drawdown | **No** |

This is fully falsifiable and needs no predictive skill. It is also the test V1 never had, because V1
never declared an objective other than "be right about returns."

### 3. Counterfactual dominance

Every decision is scored against three declared counterfactuals: **do-nothing**, **policy-only**, and
**naive rebalance** — net of costs and taxes. The **policy-only** comparison is the important one: it
isolates whether Layers 2 and 3 add anything at all. Success = beating policy-only on the *declared
objective* with a block-bootstrap CI excluding zero.

### 4. Confidence, abstention and stability

- **Confidence** — calibration curve of `recommendation_confidence` against realised
  objective-satisfaction. Failure: high-confidence decisions do not satisfy their objective more often
  than low-confidence ones.
- **Abstention** — scored, never free. Abstaining when the outcome was unremarkable is **correct**;
  abstaining when it was extreme *and foreseeable from CONTEXT-tier evidence* is a **miss**. Report an
  abstention-precision/recall pair.
- **Stability** — churn rate with `change_driver = NONE` must be **zero** by construction; the observed
  rate is a regression test on the suppression rule.

### What constitutes success

> Over ≥ 100 archived decisions spanning ≥ 2 regimes: mechanical invariants hold 100%; the engine beats
> the **policy-only** counterfactual on its declared objective with a CI excluding zero; confidence is
> monotone against objective-satisfaction; abstention precision exceeds the base rate; and
> `change_driver = NONE` churn is zero.

**None of that requires the platform to predict returns.**

---

## PART 9 — Extensibility

New evidence domains integrate without redesign because **the engine is source-agnostic by
construction**.

```python
class EvidenceSource(Protocol):
    name: str
    version: int
    def claims(self, ctx: DecisionContext) -> Iterable[EvidenceClaim]: ...
    def admissible_horizons(self) -> frozenset[Horizon]: ...
```

**Integration path — no engine change at any step:**

1. Implement the Protocol. Register it. It enters at **SHADOW** automatically.
2. The Reliability Ledger begins scoring it (descriptive first, directional in parallel).
3. On passing the CONTEXT gate it appears in reports, contributing **0**.
4. On ADVISORY it may modulate magnitude and urgency, capped at ±10.
5. On DIRECTIONAL it may flip actions, capped at ±20.

**Enforced by test — no source-specific logic anywhere in the engine:**

- No `if source == "..."` — AST-enforced, as the existing boundary tests already do for other modules.
- The engine consumes `(claim, direction, magnitude, tier)`; it never learns source names.
- Tier caps live in configuration, not code.
- Adding a source requires **zero** engine edits, **zero** migrations, and **zero** re-validation of
  existing sources.

**Removing a source is equally cheap:** demotion to SHADOW is a ledger write. The engine needs no
knowledge that it happened — which is what makes automatic demotion safe.

---

## PART 10 — Specification summary

### Interfaces

```python
class DecisionEngine:
    def __init__(self, policy: PolicyArtifact, ledger: ReliabilityLedgerReader,
                 config: DecisionConfig) -> None: ...

    def decide(self, ctx: DecisionContext, horizon: Horizon) -> PositionDecision: ...
    def decide_all_horizons(self, ctx: DecisionContext) -> HorizonTermStructure: ...
    def explain(self, decision: PositionDecision) -> Explanation: ...   # from the stored trace
```

`ReliabilityLedgerReader` is **read-only by type**, which makes self-authorisation a compile-time
impossibility rather than a convention.

### Data model

`PositionDecision` (per ARCHITECTURE_V2.1 §4) plus:

```python
@dataclass(frozen=True)
class EliminationTrace:
    rejected_action: Action
    eliminated_at_stage: int
    rule: str
    threshold: str
    actual_value: str

@dataclass(frozen=True)
class DecisionTrace:
    stages: tuple[StageRecord, ...]      # every stage, its inputs and its survivors
    eliminations: tuple[EliminationTrace, ...]
    mandate_basis: str | None
    abstention_reason: str | None
    policy_version: str
    ledger_snapshot_id: str              # exactly which reliability state was read
```

### Configuration (versioned artifact, never fitted)

```yaml
decision_config_version: "1.0.0"
objective_order: [capital_preservation, policy_compliance, risk_budget,
                  tax_efficiency, evidence_positioning, transaction_cost]
tolerance_bands: {capital_preservation: 0.0, policy_compliance: 0.02,
                  risk_budget: 0.05, tax_efficiency: 0.10}
tier_caps: {CONTEXT: 0, ADVISORY: 10, DIRECTIONAL: 20}
rubric: {hard_cap_breach: 25, soft_band_breach: 15, drift_beyond_tolerance: 8}
abstention: {require_discriminating_evidence: true, min_tier: ADVISORY}
```

---

## "Is the Decision Engine now the central intellectual property of this platform?"

# No.

The Decision Engine is the platform's **central deliverable**. It is not its central innovation, and
claiming otherwise would repeat the project's oldest mistake — mistaking the elaborate component for
the valuable one.

**A constrained lexicographic engine over a written policy is good engineering, not novel IP.** It is
how institutional mandates have worked for decades. A competent engineer with a written investment
policy could build a defensible version in a fortnight. Its quality is also almost entirely determined
by its inputs: feed this engine an uncalibrated reliability ledger and it reproduces V1 exactly, with a
better audit trail.

### The central innovation is the **Reliability Ledger**.

It is the only component that does something the field does not routinely do:

1. **It separates descriptive from directional reliability** — permitting a source to inform *risk and
   exposure* without ever claiming to predict returns. Almost every commercial platform conflates these,
   which is why almost every one overclaims.
2. **It makes influence earned, revocable, and versioned** — SHADOW → CONTEXT → ADVISORY → DIRECTIONAL,
   with **automatic demotion** on decay, staleness and regime break. Most platforms admit signals by
   assertion and never remove them.
3. **It makes `forecast_contribution = 0.0` a printable, auditable fact** rather than an embarrassment
   to be hidden behind a confident-looking number.
4. **It is what makes the Decision Engine structurally incapable of overclaiming** — the property that
   every measured failure in this project's history traces back to the absence of.

**The engine embodies structural honesty; the ledger enforces it.** Enforcement is the scarce part.

### The practical consequence

If forced to choose what to build first and what to protect: **build the ledger's measurement machinery
before the engine's cleverness.** An honest ledger with a crude engine produces defensible
recommendations. A sophisticated engine with a dishonest ledger produces V1 — which is exactly what
~580 engineering hours have already demonstrated.

And note what that implies for sequencing: the ledger cannot be populated until descriptive reliability
is measured, and **descriptive reliability has never been measured for any source in this project.**
That measurement — not this specification — is the next thing standing between the platform and its
first defensible recommendation.
