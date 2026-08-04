# Architecture V2.1 — Refinement

**Amends** [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md). Changes only; the unamended design stands.

---

## PART 1 — Critique of my own design

The V2 review made **one systematic error**, and most of its excesses descend from it:

> ### I applied a *predictive-reliability* gate to evidence whose value is not predictive.

I proved that no source predicts returns out-of-sample, and then concluded that no source should
influence a recommendation. That does not follow. Evidence has at least three distinct uses, and only
one of them requires forecasting skill:

| Use of evidence | Requires predictive skill? | V2 treatment | Correct treatment |
|---|---|---|---|
| **Exposure characterisation** — *what am I actually holding?* | **No** | Gated to zero | Admissible on descriptive reliability alone |
| **Asymmetry / risk shaping** — *how bad is the bad case?* | **No** | Gated to zero | Admissible on descriptive reliability |
| **Directional expectation** — *which way will it go?* | **Yes** | Correctly gated | Keep the gate |

A PM genuinely wants to know that a holding sits at the 94th percentile of its own 10-year valuation
range, **even if valuation has zero return-predictive power**. That fact changes the bear case, the
monitoring plan, and the conviction behind a policy action. V2 suppressed it.

### Every place I was over-conservative

| # | V2 position | Why I took it | Do I still hold it? | Where it belongs instead |
|---|---|---|---|---|
| 1 | **Evidence weight ceilings ≈ 0.00 at every horizon** | No source has demonstrated OOS reliability | **NO — reversed.** Conflated predictive weight with informational value | Split reliability into *descriptive* and *directional*. Evidence earns risk/conviction influence on the first, direction only on the second |
| 2 | **"At 1W the answer is almost always HOLD"** | Short-horizon prediction is coin-flip (0.5083, reproduced 3×) | **NO — reversed.** Defensible and useless | 1W decisions are driven by **calendar and liquidity**, not forecast. Earnings in 3 days is a *fact*, not a prediction |
| 3 | **Catalysts restricted to near-nothing** | The catalyst evidence family measured inert (7 cells) | **PARTLY.** I killed the *category* over one model's failure | Catalysts belong in Layer 1/2 as **dated event risk**, not in Layer 3 as a return predictor. The CPE result refuted catalysts-as-forecast, not catalysts-as-calendar |
| 4 | **Numeric score moved to last, suppressed** | Scores claim ~70% accuracy, deliver ~51% | **NO — reversed.** A PM scanning 50 positions needs an ordinal | Keep it prominent, but redefine it as an **action-strength ordinal**, decomposable by layer, never a probability |
| 5 | **Bull/Base/Bear excluded as fabrication** | Narrative scenarios from skill-less models | **PARTLY.** Right about narrative forecasts, wrong about scenario analysis | **Conditional sensitivity** is legitimate and requires no forecast: *"realised beta to a +100bp rate move implies −11%."* That is measurement |
| 6 | **Analogues excluded entirely** | 100% leakage at long horizons | **PARTLY.** Correct for the forecast path | Descriptive analogues — *"the last 5 times this position was at this weight and drawdown, realised dispersion was X"* — are historical fact, admissible as context |
| 7 | **Policy as "spine", evidence as "enhancement"** | Policy is deterministic and always available | **NO — reframed.** This drifts toward a passive rebalancer | Policy and evidence answer **different questions**; neither is subordinate. See Part 2 |

### The reframing that replaces the "spine/enhancement" hierarchy

- **Policy** answers *"what action does my current exposure warrant?"* → needs no forecast
- **Evidence** answers *"what am I actually exposed to, and how asymmetric is it?"* → needs no forecast
- **Forecast** answers *"which way will it go?"* → **this alone requires demonstrated predictive skill**

V2 subordinated the first two to the third's evidentiary standard. That was the error.

---

## PART 2 — Critique of the three-layer architecture

**The proposed architecture is correct and I adopt it.** Four modifications.

### M1 — Layer 2 needs its own reliability standard, not Layer 3's

This is the most important change in V2.1. "Every source earns influence through demonstrated
historical reliability" is right — but *reliability at what?* If reliability means return prediction,
Layer 2 collapses into Layer 3 and nothing is admissible.

> **Two reliability dimensions, measured separately:**
>
> - **Descriptive reliability** — does the source accurately characterise the state it claims? Data
>   completeness, revision rate, PIT integrity, stability, claim-vs-realised-state agreement.
>   **Most sources will pass this. It has never been measured.**
> - **Directional reliability** — does the source predict forward returns out-of-sample? Embargoed,
>   episode-counted, CI-bounded. **Currently nothing passes.**
>
> Descriptive reliability earns influence over **risk, asymmetry, conviction and magnitude**.
> Directional reliability earns influence over **expected direction**. Only the second is gated by the
> evidence that killed V1.

### M2 — The layers are independent contributors, not a hierarchy

Drawn as L1 → L2 → L3, Layer 3 reads as "a better Layer 2," and influence creeps upward. They should
be **three parallel contributors with different admissibility rules**, composed at a synthesis step:

```
   L1 POLICY            L2 EVIDENCE              L3 FORECAST
   exposure-driven      state-driven             direction-driven
   gate: none           gate: descriptive        gate: DIRECTIONAL
   (arithmetic on       reliability              reliability
    measured state)                              (currently: nothing passes)
        │                     │                       │
        └──────────┬──────────┴───────────┬───────────┘
                   ▼                      ▼
              SYNTHESIS            EVALUATION CONTRACT
         (action, magnitude,      (cross-cutting — attaches to
          urgency, conviction)     every layer, see Part 7)
```

### M3 — "No single source should dominate" needs an escape hatch

Usually right; occasionally wrong. A covenant breach, an accounting restatement, or a halted stock
*should* dominate. The rule becomes: **no source dominates by default; domination requires a declared,
versioned escalation rule** naming the condition and the override. Escalations are archived and
evaluated like any other claim.

### M4 — Simplify: three layers, not three plus a policy engine

Do not build a general policy engine. Layer 1 is a **versioned, human-authored policy document**
(target weights, caps, bands, tax rules, liquidity minima) plus arithmetic against measured state. It
should be a config artifact under version control, not a subsystem. This keeps Layer 1 auditable and
prevents it from growing into a second modelling surface.

**Would I replace the architecture? No. Adopt with M1–M4.**

---

## PART 3 — The Reliability Ledger, promoted to first-class

```python
@dataclass(frozen=True)
class ReliabilityRecord:
    source: str
    horizon: Horizon
    regime: Regime                  # conditioning is DELIBERATELY shallow — see below
    as_of: date

    # --- DESCRIPTIVE (gates risk/conviction influence)
    data_completeness: float        # non-null share on claimed cells
    revision_rate: float            # how often a past claim is restated
    pit_integrity: bool             # passes the poisoning test
    state_agreement: float          # claim vs independently-verified state
    stability: float                # claim persistence vs its own churn
    descriptive_score: float        # composite ∈ [0,1]

    # --- DIRECTIONAL (gates expected-direction influence)
    brier_skill_score: float        # vs constant-50%. NEGATIVE today for every source
    rank_ic: float
    rank_ic_ci: tuple[float, float]
    hit_rate_in_claimed_direction: float
    directional_score: float        # 0 unless the CI excludes zero

    # --- SAMPLE ADEQUACY (the gate V1 never had)
    episodes: int                   # distinct calendar episodes, not rows
    minimum_detectable_effect: float
    powered: bool                   # episodes ≥ floor AND MDE ≤ claimed effect

    tier: InfluenceTier             # SHADOW | CONTEXT | ADVISORY | DIRECTIONAL
    tier_since: date
    demotion_reason: str | None
```

### How influence is earned — four tiers, each with a declared gate

| Tier | Influence granted | Gate to enter |
|---|---|---|
| **SHADOW** | None. Computed, archived, never shown | Default for every new source |
| **CONTEXT** | Displayed to the PM; **cannot move the recommendation** | `descriptive_score ≥ 0.8`, PIT integrity passes, ≥ 20 episodes |
| **ADVISORY** | May modify **conviction, magnitude, urgency** — never flip the action | CONTEXT + descriptive stability over ≥ 2 regimes + `powered = True` |
| **DIRECTIONAL** | May **flip** the action | ADVISORY + `directional_score > 0` with a CI excluding zero on an embargoed holdout, sustained ≥ 4 quarters |

**Today every source sits at SHADOW or CONTEXT.** The architecture states this rather than hiding it.

### How influence is lost — automatic, not discretionary

1. **Rolling-window failure** — reliability recomputed each quarter on a trailing embargoed window;
   falling below the entry gate demotes one tier immediately.
2. **Staleness decay** — a source not evaluated for 2 quarters decays toward SHADOW. Influence must be
   *continuously* re-earned.
3. **Regime break** — on a declared regime transition, DIRECTIONAL sources drop to ADVISORY until
   re-established in the new regime. *(The CPE measured bear 0.81 vs bull 0.55 — reliability is
   regime-dependent and pretending otherwise is how era persistence got mistaken for skill.)*
4. **Structural change** — any feature-definition or model-version change resets the record. Reliability
   attaches to a **versioned** source, never to a name.

### Should reliability differ by horizon, regime, sector, cap, volatility?

| Dimension | Condition on it? | Why |
|---|---|---|
| **Horizon** | **YES — mandatory** | Measured: 0.5083 at 1w vs 0.4592 at 1y. A source reliable at 1Y may be noise at 1W |
| **Market regime** | **YES — with heavy shrinkage** | Measured regime dependence (bear 0.81 / bull 0.55), but few independent regime episodes exist. Shrink hard toward the pooled estimate |
| **Sector** | **NO — not until sample supports it** | |
| **Market cap** | **NO** | |
| **Volatility regime** | **NO** | |

**The reason for the three NOs is measured, not stylistic.** The CPE's sharpest finding was that
standalone accuracy **decreased monotonically as conditioning domains were added** (market-only 0.641 →
+sector 0.600 → +company 0.609 → market+sector+company 0.545). Conditioning reliability on many
dimensions re-creates the exact failure inside the ledger. **Condition on horizon; shrink on regime;
stop.** Additional dimensions are admitted only when a declared episode floor is met per cell.

---

## PART 4 — The expanded `PositionDecision`

Additions and changes to the V2 schema. Unlisted fields stand.

```python
@dataclass(frozen=True)
class PositionDecision:
    # ... V2 identity, provenance, action, magnitude, urgency ...

    # ---- ACTION STRENGTH (replaces the probability-like Trim Score)
    action_strength: float               # 0-100 ORDINAL. NOT a probability. Never mapped from Φ(z)
    action_strength_scale: str           # the versioned rubric it is read against
    strength_by_layer: LayerDecomposition # policy / evidence / forecast — sums EXACTLY to the total
    forecast_contribution: float         # points contributed by Layer 3. TODAY: 0.0
    forecast_contribution_pct: float     # its share. TODAY: 0.0%

    # ---- CONFIDENCE (V2 six-component profile, plus)
    confidence: ConfidenceProfile
    confidence_basis: BasisKind          # WHICH scale applies: policy-arithmetic vs evidence
    reliability_ceiling: float           # binding cap
    ceiling_binding_source: str          # which source capped it

    # ---- EVIDENCE ATTRIBUTION
    evidence_for: tuple[AttributedClaim, ...]      # each with tier, reliability, contribution
    evidence_against: tuple[AttributedClaim, ...]  # BOTH SIDES ALWAYS SHOWN
    evidence_balance: float                        # net, in action-strength points
    unresolved_conflicts: tuple[Conflict, ...]     # preserved, never averaged away
    context_only_claims: tuple[EvidenceClaim, ...] # CONTEXT tier — shown, never counted

    # ---- CATALYSTS (dated facts only, never estimated)
    catalysts: tuple[DatedCatalyst, ...]  # kind, date, source, days_until, confirmed
    catalyst_within_horizon: bool
    catalyst_note: str                    # "none confirmed" is a valid, honest value

    # ---- PORTFOLIO IMPACT (measured; zero estimation error)
    weight_now: Decimal
    weight_after_action: Decimal
    portfolio_hhi_delta: Decimal
    sector_exposure_delta: Decimal
    correlation_cluster_delta: Decimal | None
    tracking_error_delta: Decimal | None
    tax_consequence: TaxImpact | None
    liquidity_days_to_exit: Decimal | None

    # ---- HISTORICAL RELIABILITY (the audit trail V1 lacked)
    contributing_source_reliability: tuple[SourceReliability, ...]
    highest_tier_contributing: InfluenceTier
    decision_would_change_if_forecast_removed: bool

    # ---- WHAT CHANGED
    changed_since: date
    changes: tuple[AttributedChange, ...]  # each names the CAUSE, not just the delta
    change_driver: ChangeDriver            # POSITION_DRIFT | POLICY_CHANGE | NEW_EVIDENCE
                                           # | RELIABILITY_UPDATE | DATA_REVISION | NONE
    stability_note: str                    # flags churn without cause

    # ---- WHAT WOULD CHANGE IT
    boundary_conditions: tuple[BoundaryCondition, ...]
    nearest_boundary: BoundaryCondition | None   # the one most likely to bind first
    monitoring_triggers: tuple[Trigger, ...]     # what to watch, and at what level

    # ---- FALSIFIABILITY
    evaluation_contract: EvaluationContract
    abstained: bool                       # explicit "no view" — a scored outcome, not a gap
    abstention_reason: str | None
```

**`change_driver` matters more than it looks.** V1's cross-horizon notes reported score churn with no
cause. A change whose driver is `NONE` is **noise and must be suppressed** — the same rule that governs
horizon differences in Part 5.

---

## PART 5 — Multi-horizon reasoning: my V2 claim was too strong

I claimed horizon differences are "mostly noise." **Correct for V1's implementation, wrong as a general
principle**, and I withdraw the general form.

### Horizons legitimately differ because they optimise different objectives

| Source of difference | Example | Requires forecasting? |
|---|---|---|
| **Different objective** | 1W optimises execution and event risk; 1Y optimises thesis exposure | No |
| **Different admissible evidence** | Earnings in 3 days is decisive at 1W, irrelevant at 1Y | No |
| **Different binding constraint** | Liquidity binds short; tax and cap bind long | No |
| **Different reversibility cost** | A 1W trim is cheap to undo; a 1Y exit realises gains | No |
| **Term structure of risk** | Safe over a year, dangerous over a week (earnings), or the reverse (secular decline) | No |

**None of these require predictive skill.** V1's horizon differences were noise because they came from
*the same models on the same features with a different window parameter* — the one case where a
difference carries no information.

### The architectural rule that makes differences explainable

> **A cross-horizon difference is ADMISSIBLE if and only if it is attributable to a difference in
> (objective | admissible evidence set | binding constraint | reversibility cost). Otherwise it is
> suppressed and the recommendations are forced equal.**

Implemented as a hard invariant:

```python
@dataclass(frozen=True)
class HorizonDifference:
    from_horizon: Horizon
    to_horizon: Horizon
    cause: DifferenceCause    # OBJECTIVE | ADMISSIBLE_EVIDENCE | BINDING_CONSTRAINT
                              # | REVERSIBILITY | *no NOISE member exists*
    specifics: str            # "earnings 2026-08-04 inside 1W, outside 1Y"
    # If cause cannot be populated, the difference is NOT EMITTED and the
    # decisions are equalised to the longer horizon. Enforced by test.
```

The enum deliberately has **no `NOISE` member**. The system cannot express an unexplained difference —
it must either attribute it or suppress it. That converts "recommendations differ across horizons"
from a liability into a *feature*, because every difference carries its own justification.

---

## PART 6 — Six independent concepts

Yes — these must be **separate architectural concepts**, because they have **different falsification
times** and therefore cannot share a lifecycle, a store, or an evaluator.

| Concept | Claim about | Falsifiable | Evaluated against |
|---|---|---|---|
| **Evidence** | Present/past state | **Now** | Independently verified state |
| **Prediction** | Future outcome | At horizon end | Realised return |
| **Recommendation** | Which action to take | At horizon end, vs a counterfactual | Declared counterfactual set |
| **Confidence** | Reliability of one of the above | Over many instances | Calibration curve |
| **Explainability** | The derivation | **Immediately, mechanically** | Reconstruction from inputs — it is an *audit artifact*, not a belief |
| **Decision support** | The human interface | Only by observing behaviour | Did a decision change? |

**V1 merged all six into one number.** `TrimAssessment` fused a state claim, a return forecast, an
action, and a confidence into a single 0–100 score — which is why the platform could not tell which
part was wrong when the score failed. V2.1 gives each its own object, its own store, and its own
evaluator.

The practical consequence, and the answer to the PM's real question — *"given everything known, what is
the strongest defensible action?"* — is that the system can now answer it **without a prediction**:
strongest defensible action = the action supported by Layer 1 arithmetic and CONTEXT/ADVISORY evidence,
with the forecast contribution stated as 0.0 and the recommendation still fully justified.

---

## PART 7 — Preserving falsifiability

The central risk of a recommendation system is that it becomes unfalsifiable. Four mechanisms.

### 1. Layer-specific ex-post tests — the key design move

Each layer makes a **different kind of claim** and must be scored against a **different outcome**.
Demanding that policy predict returns is why V1 had nothing to test.

| Layer | Claim | Scored against | Passing looks like |
|---|---|---|---|
| **L1 Policy** | *"This exposure violates a stated risk rule"* | **Realised risk**: concentration, drawdown contribution, tracking error — **not return** | The action reduced the risk it claimed to. Verifiable even if the stock rose |
| **L2 Evidence** | *"The state is X"* | **Descriptive accuracy**: did the state verify, persist, and survive revision? | The claim was true when made |
| **L3 Forecast** | *"Returns will be positive"* | **Realised return**, embargoed, episode-counted | Brier skill > 0 and rank-IC CI excluding zero |

### 2. The counterfactual set — declared at creation, in the `evaluation_contract`

Every recommendation is scored against three counterfactuals:

1. **Do-nothing** — hold the position unchanged over the horizon
2. **Policy-only** — what Layer 1 alone would have done (isolates the marginal value of L2 + L3)
3. **Naive** — mechanical rebalance to target

Reported net of costs and taxes. The **policy-only counterfactual is the important one**: it directly
measures whether the evidence and forecast layers add anything, and it is the test V1 never had.

### 3. Abstention is a scored outcome

A system that says "no view" must not be free. Every abstention is archived and scored: abstaining when
the realised outcome was unremarkable is **correct**; abstaining when it was extreme and foreseeable
from CONTEXT-tier evidence is a **miss**. This makes honest silence measurable and prevents the system
from buying safety by declining to speak.

### 4. Decision-level FDR ledger

Count recommendations issued, recommendations later validated against their contract, and the implied
false-discovery rate — per source, per tier, per regime. This is the program-level accounting the
architecture review flagged as missing (R6) and it now has a natural home.

**Together these mean every output is falsifiable at a declared time by a declared test, and the
platform retains the property that is genuinely its best asset: it can prove itself wrong.**

---

## PART 8 — Version 2.1: the changes

| # | Change | Supersedes |
|---|---|---|
| **C1** | **Split reliability into DESCRIPTIVE and DIRECTIONAL.** Evidence earns risk/conviction influence on the first; direction on the second | V2's single reliability gate |
| **C2** | **Adopt the three-layer architecture** with layers as parallel contributors, not a hierarchy | V2's "policy spine / evidence enhancement" |
| **C3** | **Four-tier influence ladder** SHADOW → CONTEXT → ADVISORY → DIRECTIONAL, with automatic demotion | V2's binary earned/unearned weight |
| **C4** | **Reliability conditioned on horizon (mandatory) and regime (shrunk) ONLY.** No sector/cap/vol conditioning until an episode floor is met | New — derived from the CPE's monotone-degradation finding |
| **C5** | **Reinstate the score as an `action_strength` ORDINAL**, prominent, decomposable by layer, never a probability | V2's "score last, suppressed" |
| **C6** | **Reinstate catalysts as dated event risk in L1/L2** (never as an L3 predictor) | V2's near-total exclusion |
| **C7** | **Reinstate scenarios as conditional sensitivities** (measured betas), not narrative forecasts | V2's blanket exclusion |
| **C8** | **Reinstate analogues as descriptive context** at CONTEXT tier | V2's total exclusion |
| **C9** | **Horizon-difference invariant**: every difference carries a `DifferenceCause`; unattributable differences are suppressed and equalised. The enum has no `NOISE` member | V2's "differences are mostly noise" |
| **C10** | **Six concepts separated** — Evidence, Prediction, Recommendation, Confidence, Explainability, Decision Support get distinct objects, stores, and evaluators | V1's merged `TrimAssessment` |
| **C11** | **Layer-specific ex-post evaluation** — policy on risk, evidence on descriptive accuracy, forecast on return | V2's single evaluation contract |
| **C12** | **Abstention scored; decision-level FDR ledger** | New |
| **C13** | **Escalation rules** allow a single source to dominate when declared and versioned | V2's "no source dominates" |
| **C14** | **Layer 1 is a versioned config artifact**, not a subsystem | Simplification |

### Unchanged from V2

Correct-at-zero-signal remains the governing constraint. `signal_weight_applied`,
`defensible_without_forecast`, and `evaluation_contract` remain mandatory. No source reports its own
precision — `se ≡ |effect/z|` stays deleted. Redundancy is estimated, not declared. Conflict is
preserved, not averaged. Confidence is capped by demonstrated reliability. Build order still puts
measurement and policy first, archive second, reliability third, evidence last.

---

# Version 2.1

## "Would this architecture now be suitable for an institutional investment research platform used by professional portfolio managers?"

### The architecture: **yes.** The platform: **not yet** — and the gap is measurement, not design.

V2.1 clears the bars an institutional standard actually imposes: separation of evidence from forecast
from recommendation; influence earned through auditable, versioned, revocable reliability; both sides of
the evidence shown; every recommendation carrying its basis, its boundary conditions, and its
falsification test; risk claims scored on risk rather than return; and a system that can say *"no view"*
and be graded on it. Most institutional platforms do not separate description from prediction at all,
and almost none demote a signal automatically when it stops working.

**Four things still prevent the platform from meeting that standard, none of them architectural:**

1. **No source has demonstrated reliability of ANY kind — including descriptive.** The ledger is the
   spine of V2.1, and it is empty. Descriptive reliability has never been measured, and unlike
   directional reliability there is every reason to expect it to pass. Until it is measured, every
   source sits at SHADOW and the platform can only run its Layer 1.
2. **The data layer is destroyed and reproducibility is unproven.** No institutional platform ships
   without a restore drill. A permanent loss has already occurred.
3. **The value proposition is untested with a human.** V2.1 is built on the premise that a
   reliability-bounded explanation is what a PM wants. That premise has never been tested, and it is
   15 hours and $300 away.
4. **Layer 1 has no policy document.** The architecture assumes a versioned, human-authored statement
   of target weights, caps, bands, tax rules and liquidity minima. **It does not exist.** Without it
   Layer 1 has nothing to evaluate against, and Layer 1 is the only layer that works today.

**Item 4 is the binding one and it is not an engineering task.** The single highest-value hour available
is spent writing down the investment policy — because the moment it exists, the platform can issue
defensible Add/Hold/Trim/Exit recommendations across all five horizons, with stated conviction, honest
abstention where warranted, and `forecast_contribution = 0.0` printed on every one of them.

That system would be institutionally credible on the day it ships, and every subsequent layer would be
an improvement on something that already works — rather than, as in V1, a dependency of something that
never did.
