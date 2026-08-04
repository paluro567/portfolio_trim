# Architecture V2 — Portfolio Decision Support, Signal-Optional

**Chief Quantitative Architect's design review and target architecture.**

Governing design constraint, derived from everything measured:

> ## The system must be CORRECT AT ZERO SIGNAL.
> With no predictive edge it must still produce defensible, useful, honest recommendations. With edge
> it produces better ones. It must never produce confident ones it has not earned.

The current architecture fails this test: at zero signal it produces confident garbage (+18–26 pp
overclaim, Brier worse than a constant 50% at all six horizons). Every design choice below follows
from making that impossible.

---

## PART 1 — Should the architecture change?

### Yes. "Predict future returns" is the wrong abstraction — for three specific, measured reasons.

**1. It makes the entire system's value conditional on a quantity never demonstrated.**
The output is a monotone function of a forecast. If IC ≈ 0 — and the shrinkage sweep found the
Brier-optimal displacement from neutral is **λ = 0 at every horizon, with no interior optimum** — then
the system's value is not merely zero, it is **negative**: it loses to a constant 50% forecast at all
six horizons, every CI excluding zero.

**2. It discards the information the platform demonstrably has.**
Position weight, cost basis, concentration (HHI 0.041 ≈ 24.5 effective positions), risk contribution,
realized correlation, drawdown — these are **measured, not forecast**. They carry no estimation error
about the future. And they are where portfolio decisions actually come from: *if a position is 28% of
the book, "trim" is correct regardless of what any model thinks about next month.* The current
architecture treats this as a small adjustment term (`A = clip(10·max(0, w/0.15−1) + 25·(rc−w), ±10)`)
bolted onto a forecast that carries the other 90 points.

**That is exactly backwards.**

**3. It makes horizons interchangeable when they are not.**
Today all six horizons are the same operation with a different parameter. That is why cross-horizon
differences are mostly noise — and why the shipped "cross-horizon notes" (abrupt ≥20 pt moves, side
reversals) report noise as insight. "Should I trim over one week" and "over one year" are **different
decisions with different dominant inputs**, not the same forecast at different scales.

### The correct abstraction

> **A recommendation is a decision under uncertainty about a POSITION, given a POLICY.**
> `decision = f(position state, policy, constraints) adjusted by g(evidence × demonstrated reliability)`

The first term is deterministic and always available. The second is currently near-zero-weight and must
*earn* its weight. This degrades gracefully; the current design does not.

### Where your proposed spec is a trap

I would not build four of the items as specified:

| Requested | Problem | V2 treatment |
|---|---|---|
| **Bull/Base/Bear scenarios** | If generated from models with no skill, these are **fabricated precision** — three confident narratives about an unforecastable variable | Replace with **empirical outcome distribution**: realized forward-return quantiles for comparable position/regime states. Distributional, not narrative. No story attached |
| **Upcoming catalysts** | The catalyst family was measured **inert** (7 cells in the CPE holdout). No PIT source exists for forward calendars; the platform documented this and correctly declined to scrape it | Restrict to **dated, PIT-verifiable events only** (earnings dates, index rebalances, lockups). Anything else is omitted, not estimated |
| **Historical analogues "when useful"** | Rejected in validation; long-horizon performance was **100% leakage** (1y 64.3% → 30.8% after embargo). "When useful" is an unfalsifiable gate | **Excluded from the decision path** until it passes VALIDATION_GATES. May appear as clearly-labelled context with zero weight |
| **Recommendation differs across horizons** | If the same features produce different numbers, the difference **is noise** | Differences must be **attributable to a different decision rule dominating**, not to a different forecast. If no rule differs, the recommendation must be identical across horizons — and saying so is a feature |

---

## PART 2 — The core domain object

### **`PositionDecision`** — one holding, one horizon, one recommended action.

Not `Prediction` (the abstraction we are leaving). Not `Evidence` (an input). Not `Recommendation`
(ambiguous about portfolio-awareness). The object must be about a **position**, because the same
security warrants different actions at 2% and 28% weight.

```python
@dataclass(frozen=True)
class PositionDecision:
    # ---- identity & provenance
    security_id: int                  # permanent, never ticker
    portfolio_id: int
    as_of: date
    horizon: Horizon                  # 1W | 1M | 3M | 6M | 1Y
    engine_version: str
    policy_version: str               # WHICH policy produced this
    input_checksum: str               # reproducibility

    # ---- THE DECISION
    action: Action                    # ADD | HOLD | TRIM | EXIT
    magnitude: Decimal | None         # target weight change; None for HOLD
    urgency: Urgency                  # IMMEDIATE | SCHEDULED | OPPORTUNISTIC | NONE

    # ---- WHY  (the most important block)
    dominant_basis: BasisKind         # POLICY_BREACH | CONCENTRATION | RISK_BUDGET
                                      # | LIQUIDITY | TAX | EVIDENCE | NONE
    basis_decomposition: tuple[BasisContribution, ...]   # sums to the action, exactly
    signal_weight_applied: float      # 0.0-1.0 — how much the FORECAST actually moved this
    decision_without_evidence: Action # what the policy layer alone would say

    # ---- DEFENSIBILITY  (the field that makes V2 different)
    defensible_without_forecast: bool # would this survive deleting the predictive layer?
    defensibility_note: str
    reliability_ceiling: float        # confidence cannot exceed demonstrated reliability

    # ---- CONFIDENCE (six-component, never a single number — see Part 6)
    confidence: ConfidenceProfile

    # ---- COUNTERFACTUAL  (what a PM actually reads)
    boundary_conditions: tuple[BoundaryCondition, ...]  # "TRIM becomes HOLD if weight < 18.2%"
    what_changed: tuple[Change, ...]                    # vs the previous decision, with cause

    # ---- POSITION STATE  (measured, zero estimation error)
    weight: Decimal
    weight_vs_policy_target: Decimal
    risk_contribution: Decimal | None
    correlation_cluster: str | None
    unrealised_pnl_pct: Decimal | None
    tax_lot_summary: TaxLotSummary | None

    # ---- EVIDENCE (reliability-weighted; may be entirely empty and that is VALID)
    evidence: tuple[WeightedEvidence, ...]
    zero_weight_context: tuple[EvidenceClaim, ...]   # shown, never counted

    # ---- OUTCOME DISTRIBUTION (empirical, not narrative)
    outcome_quantiles: OutcomeDistribution | None    # p10/p25/p50/p75/p90 forward return
    distribution_source: str                         # which comparable set, n, PIT window

    # ---- HONESTY
    unknowns: tuple[Unknown, ...]                    # typed: NOT_MODELLED | NO_DATA | UNRESOLVED
    known_limitations: tuple[str, ...]

    # ---- EX-POST EVALUABILITY (declared at creation — see Part 9, Risk 3)
    evaluation_contract: EvaluationContract
```

**Three fields do the architectural work:**

- **`signal_weight_applied`** — makes the forecast's influence *visible and auditable*. Today it is
  ~90% and invisible. In V2 it starts at **0.0** and is raised only by demonstrated reliability.
- **`defensible_without_forecast`** — every recommendation declares whether it survives deleting the
  predictive layer. A system where most decisions are defensible is useful today; one where they are
  not is honest about resting on unvalidated forecasts.
- **`evaluation_contract`** — declared *at creation*, states how this decision will be scored later.
  Without it, a recommendation engine is unfalsifiable (Part 9, Risk 3).

---

## PART 3 — Information flow

Two tracks, asymmetric by design, joined by a reliability gate — plus the feedback loop the current
system lacks.

```
 TRACK A — POSITION & POLICY  (deterministic · always available · zero estimation error)
 ═══════════════════════════════════════════════════════════════════════════════════════
   Broker ledger ──► Lots (FIFO) ──► Position state ──► Weight, cost basis, tax lots
   Price history ──► Realised risk ──► Vol, drawdown, correlation, risk contribution
   Policy doc    ──► Targets ──────► Target weight, caps, sector limits, rebalance bands
                                              │
                                              ▼
                                    POLICY EVALUATION
                                    → breaches, deviations, constraint violations
                                    → a COMPLETE, DEFENSIBLE decision on its own
                                              │
 TRACK B — EVIDENCE  (probabilistic · optional · weight EARNED, default ZERO)              │
 ═══════════════════════════════════════════════════════════════════════════════════      │
   Raw data ──► Features (PIT) ──► Evidence Claims ──► RELIABILITY GATE ──────────────┐   │
                                   (each: effect, dispersion,          │              │   │
                                    provenance, NO self-reported se)   │              │   │
                                                                       ▼              ▼   ▼
                                                        ┌──────────────────────────────────────┐
                                                        │  weight_i = f(REALISED out-of-sample │
                                                        │  reliability of source i at horizon h)│
                                                        │  Never self-reported precision.       │
                                                        │  DEFAULT = 0. Weight is EARNED.       │
                                                        └───────────────────┬──────────────────┘
                                                                            ▼
                                                            ┌───────────────────────────┐
                                                            │   DECISION SYNTHESIS      │
                                                            │  policy action, adjusted  │
                                                            │  by evidence × reliability│
                                                            └─────────────┬─────────────┘
                                                                          ▼
                                                              PositionDecision (per horizon)
                                                                          ▼
                                                              Portfolio Decision Report
                                                                          ▼
                                                              Immutable Decision Archive
                                                                          │
   ╔══════════════════════════════════════════════════════════════════════▼══════════════╗
   ║  RELIABILITY LEDGER  ← THE LOOP THE CURRENT SYSTEM LACKS                             ║
   ║  Realised outcomes are scored against the declared evaluation_contract, per source,   ║
   ║  per horizon, per regime → updates the weights above.                                 ║
   ║  The system LEARNS HOW MUCH TO TRUST ITSELF FROM ITS OWN TRACK RECORD.                ║
   ╚═══════════════════════════════════════════════════════════════════════════════════════╝
```

**The critical property:** delete Track B entirely and the system still works — it becomes a rigorous
policy-and-risk rebalancing engine. Today, delete the forecast and nothing remains.

**The critical addition:** the platform already has an immutable prediction archive. It has **never
been wired back into weighting**. Confidence is currently computed from evidence *volume* — which was
measured to carry no information. In V2, weight and confidence come from **realized calibration**.

---

## PART 4 — Horizon design

### Shared substrate, independent decision rules. Not independent models.

Independent models would multiply an already-fatal multiple-comparisons problem across six horizons
with no power to distinguish them. Shared *models* with only a horizon parameter — the current
design — is what makes cross-horizon differences noise.

**The resolution: one evidence substrate, six genuinely different decision rules, with different
dominant inputs.**

| Horizon | Dominant inputs | Evidence weight ceiling | Honest default |
|---|---|---|---|
| **1W** | Liquidity, execution cost, tax-lot timing, hard policy breach | **0.00** — measured coin-flip (0.5083), reproduced 3× | **HOLD** unless a policy breach or liquidity event exists |
| **1M** | Policy bands, rebalance schedule, concentration | **0.00** — 0.5136, CI ±0.05 | HOLD unless a band is breached |
| **3M** | Concentration drift, sector/regime exposure, earnings cycle | ≤ 0.10 — *and 0.4622 is below coin-flip today* | Policy-driven |
| **6M** | Risk budget, correlation-cluster exposure, thesis checkpoints | ≤ 0.10 (0.4549 today) | Policy-driven |
| **1Y** | Valuation, thesis integrity, structural concentration, tax | ≤ 0.20 **if earned** (0.4592 today) | Policy-driven |

**Every ceiling is currently 0.00 in practice**, because no source has demonstrated out-of-sample
reliability. The ceilings are the *maximum a source could ever earn*, not what it gets.

### How evidence should evolve across horizons

Not by re-running the same model with a bigger window. By **different evidence classes becoming
admissible**:

- Short horizons admit only *observable state* (liquidity, spread, lot age, announced events).
- Medium horizons admit *regime and cycle* evidence.
- Long horizons admit *valuation and structural* evidence.

An evidence class that cannot demonstrate reliability at a horizon is **inadmissible at that horizon** —
not down-weighted, inadmissible.

### Representing conflicting recommendations

A **decision term structure**, with the conflict *named and attributed*:

```
NVDA   1W  HOLD    ── no policy breach; liquidity fine
       1M  HOLD    ── within rebalance band (28.4% vs 30% action threshold)
       3M  TRIM    ── concentration: crosses the 25% review band
       6M  TRIM    ── concentration + correlation cluster (0.71 w/ AMD, SMCI)
       1Y  EXIT-P  ── partial: 28.4% vs 15% policy cap

CONFLICT: 1W HOLD vs 1Y EXIT-PARTIAL
CAUSE:    different RULES dominate — not a change in forecast.
          Short horizons see no breach; the 1Y policy cap is breached by 13.4pp.
RESOLUTION: act on the longest horizon whose rule is breached, at the urgency of
          the shortest. → Begin scheduled partial exit; no immediate action required.
```

**A conflict is only reportable if the *rules* differ.** If the same rule produces different answers at
different horizons, that is noise and must be suppressed — the opposite of today's behaviour.

---

## PART 5 — The evidence engine

### Every subsystem contributes a *claim*, not a score.

```python
@dataclass(frozen=True)
class EvidenceClaim:
    source: str
    horizon: Horizon
    claim: str                        # human-readable, falsifiable
    direction: Direction              # SUPPORTS_ADD | SUPPORTS_TRIM | NEUTRAL
    effect: float                     # observed historical effect
    dispersion: float                 # observed dispersion — MEASURED, never effect/z
    n_effective: float
    episodes: int                     # distinct calendar episodes (anti-double-count)
    provenance: Provenance            # PIT window, feature versions, code sha
    admissible_at_horizon: bool
    # NOTE: NO self-reported standard error. NO z. NO 0-100 score.
```

### Four rules, each derived from a measured failure

**Rule 1 — No source reports its own precision.**
`se ≡ |effect / z_raw|` produced `weight = (z/effect)²`, giving **Spearman(|effect|, weight) = exactly
−1.000**: the model expressing itself in the smallest numbers won the vote. Sources report **effect and
observed dispersion**; the engine computes precision from *realized* out-of-sample performance.

**Rule 2 — Weight is earned, default zero.**
The platform already invented shadow-mode discipline for new models. V2 generalises it: **every**
source starts at zero weight and earns it by passing VALIDATION_GATES *including a sensitivity gate*.
Today's default is "included unless demoted" — backwards.

**Rule 3 — Redundancy is estimated, never declared.**
Declared priors were measured wrong in **both** directions: `momentum ↔ relative` declared 0.50 /
realized +0.513 (correct), but `rates ↔ macro` declared 0.50 / realized **−0.003** (badly
over-declared). V2 estimates the correlation matrix from realized claim history, with declared priors
only as a prior with an explicit shrinkage weight that decays as data accrues.

**Rule 4 — Conflict is preserved, not collapsed.**
The current engine collapses everything to one score. Since cross-model agreement was measured to carry
**no** predictive information, collapsing destroys the one honest thing disagreement conveys: *the
sources do not agree, so the decision should not be forecast-driven.*

### Conflict resolution

```
1. Are the conflicting sources ADMISSIBLE at this horizon?   → drop inadmissible
2. Do any have DEMONSTRATED reliability > 0?                 → if none: evidence weight = 0,
                                                                decision is policy-only, and
                                                                the report SAYS SO
3. Are they REDUNDANT (estimated corr > 0.4)?                → treat as one source
4. Genuine conflict among reliable, independent sources?     → do NOT average.
                                                                Widen the outcome distribution,
                                                                lower recommendation confidence,
                                                                REPORT BOTH CLAIMS
```

Averaging conflicting evidence into a point estimate is how the current system converts disagreement
into false precision.

---

## PART 6 — Confidence

### One number is the defect. Six components, never multiplied into one score.

```python
@dataclass(frozen=True)
class ConfidenceProfile:
    data_quality: float          # completeness, staleness, source integrity   [MEASURABLE NOW]
    evidence_quality: float      # PIT integrity, n_eff, episodes, leakage-free [MEASURABLE NOW]
    agreement: float             # cross-source consistency  ← REPORTED, NEVER MULTIPLIED IN
    model_confidence: float      # self-reported  ← DISPLAY SUPPRESSED until recalibrated
    historical_reliability: float# realised OOS calibration, this source × horizon × regime
    recommendation_confidence: float   # the composite the PM sees
    ceiling_binding: str         # WHICH component capped it
```

### The three rules that prevent the measured failure from recurring

**Rule A — `recommendation_confidence ≤ historical_reliability`.**
A hard ceiling. A source that has never demonstrated out-of-sample skill **cannot** produce a
high-confidence recommendation, however clean its data or numerous its samples. This structurally
prevents the +18–26 pp overclaim: today confidence derives from evidence *volume*, and volume was
measured to be uncorrelated with accuracy.

**Rule B — `agreement` is reported, never multiplied in.**
Today `confidence = volume × agreement`. Agreement carries no predictive information, and the price
cluster (realized corr +0.513) manufactures agreement mechanically. Multiplying it in converts
redundancy into confidence.

**Rule C — Policy-driven decisions get their own scale.**
"Trim: your position is 28.4% against a 15% cap" is **near-certain** — it is arithmetic on measured
state. "Trim: our models expect underperformance" is currently **near-zero**. These must never share a
confidence scale. `dominant_basis` selects which scale applies.

**Consequence, stated plainly:** on today's evidence nearly every recommendation this platform issues
would be labelled *high confidence, policy-driven* or *low confidence, evidence-driven*. That is the
correct output and it is far more useful than a uniform 0.70.

---

## PART 7 — The ideal single-stock report

Ordered by **decidability**, not by interest. A PM reads top-down and can stop at any point.

| # | Section | Why here | Notes |
|---|---|---|---|
| **1** | **The decision and its basis** — one line | The only thing 80% of readings need | *"TRIM (1Y) — concentration: 28.4% vs 15% cap. Forecast contributed 0.0."* Names `dominant_basis` and `signal_weight_applied` **in the headline** |
| **2** | **What would change it** — boundary conditions | The single most actionable block on the page | *"Becomes HOLD below 18.2% weight, or if the correlation cluster falls under 0.55."* PMs act on thresholds, not scores |
| **3** | **Position state** | Facts, zero estimation error | Weight, target, cost basis, lots, risk contribution, correlation cluster |
| **4** | **Policy deviations** | The deterministic triggers | Every breach, with its rule and threshold |
| **5** | **What changed since last review** | Cheap, high-signal, causally attributed | Diff vs the archived prior decision, with the cause named |
| **6** | **Risks — including not-modelled** | Honest exposure | Typed `unknowns`: NOT_MODELLED, NO_DATA, UNRESOLVED. The derivatives gap belongs here |
| **7** | **Evidence, reliability-labelled** | Support, not the decision | Each claim with its realized reliability. **Zero-weight sources visually separated** |
| **8** | **Empirical outcome distribution** | Replaces bull/base/bear | p10/p25/p50/p75/p90 of realized forward returns for comparable states, with n and window. **No narrative** |
| **9** | **Catalysts** | Only PIT-verifiable | Dated events only. **Omitted entirely if none qualify** — never estimated |
| **10** | **Cross-horizon term structure** | Context | Conflicts shown only where *rules* differ |
| **11** | Historical analogues | Currently **excluded** | Re-admitted only on passing the gates |
| **12** | The numeric score | **Least important — deliberately last** | Today it leads. In V2 it is a summary of the above, suppressed when `signal_weight_applied ≈ 0` |

**The inversion is the point:** the score goes from first to last, and the *basis* and *boundary
conditions* move to the top.

---

## PART 8 — Mapping the current project

| Subsystem | Verdict | Rationale |
|---|---|---|
| **Historical Research Engine (PIT, embargo, poison tests)** | **KEEP** | The best asset in the project. It caught its own leakage. Untouched |
| **Security master / identity (Phase 1)** | **KEEP** | Correct, tested, 8/8 acceptance |
| **Feature Store** | **KEEP** | Works; PIT-clean |
| **Portfolio Analytics** | **KEEP — and PROMOTE to the core** | Weights, HHI, risk contribution, correlation. It becomes Track A, the spine |
| **Immutable prediction archive** | **KEEP — and WIRE IT UP** | Exists; never fed back. Becomes the Reliability Ledger |
| **Explainability / attribution** | **KEEP** | Exact accounting invariant, typed unknowns. This is the product |
| **Data engineering / migrations** | **KEEP (restore first)** | Schema survives; DB destroyed |
| **Validation Framework** | **MODIFY** | Add a **sensitivity gate**: no study runs without a declared, demonstrated MDE. Underpowered and null must stop sharing a disposition |
| **Report Generation** | **MODIFY** | Reorder per Part 7. Basis first, score last |
| **Evidence models (rates, macro, momentum, sector, relative)** | **MODIFY** | Retained as *claim producers*; **strip self-reported precision** (`se`, `z`, 0–100 score) |
| **Backtesting / walk-forward** | **MODIFY** | Add staged positive controls and an MDE surface |
| **Ensemble combiner** | **REPLACE** | `se ≡ \|effect/z\|` → `weight = (z/effect)²` → Spearman −1.000. The measured architectural defect |
| **Confidence engine** | **REPLACE** | `volume × agreement`. Both terms measured to carry no information. Replace with the six-component profile |
| **Trim Score formula** | **REPLACE** | `E = 50 + c·(50−s)` makes forecast the trunk and portfolio a ±10 twig. Invert |
| **Cross-horizon notes** | **REPLACE** | Reports noise as insight. Replace with the rule-difference term structure |
| **`valuation` model** | **REMOVE** (from the registry) | 0.000 activation over 7,938 rows; LOO Δ exactly 0.0000 with zero-width CI. Provably dead weight. Re-admit when PIT fundamentals exist |
| **`historical_analogues`** | **REMOVE from the decision path** | Long-horizon promise was 100% leakage. Context only |
| **Conditional Probability Engine** | **REMOVE from the decision path** | Edge was era persistence; confidence inverted |
| **Declared correlation priors** | **REMOVE** | Measured wrong in both directions. Estimate instead |
| **User-facing numeric probability** | **REMOVE until recalibrated** | Claims ~70% accuracy, delivers ~51% |

---

## PART 9 — The five largest scientific risks

| # | Risk | Threat | Why |
|---|---|---|---|
| **1** | **The pivot does not escape the prediction problem.** Horizon-differentiated Add/Hold/Trim/Exit **is** a directional forecast in new packaging. If evidence weight creeps above zero without earning it, V2 is V1 with better vocabulary | **SEVERE** | The single greatest risk. Mitigation: `signal_weight_applied` is an explicit, audited, archived field, and the reliability ceiling is a hard constraint, not a convention |
| **2** | **Unfalsifiability.** A recommendation engine is far harder to score than a predictor — there is no ground truth for *"should I have trimmed."* The pivot risks trading a **rigorous failure for an unfalsifiable success**, which is strictly worse | **SEVERE** | Mitigation: `evaluation_contract` declared **at creation**. Every decision states its ex-post test — the realized return of the recommended action vs the hold counterfactual, over the stated horizon, net of costs. Measurable, pre-registered, archived |
| **3** | **The policy layer is trivially derivable.** If most value is "you're at 28%, cap is 15%, trim," a spreadsheet does it. The platform must add something beyond rebalancing arithmetic or it has no reason to exist | **HIGH** | Mitigation: the differentiator must be the **evidence-labelled, reliability-bounded, counterfactual explanation** — and that hypothesis has **never been tested with a human.** Test it before building |
| **4** | **Fabricated precision in scenarios and catalysts.** Bull/base/bear and forward catalysts have no validated source. Highest risk of manufacturing authority the evidence does not support | **HIGH** | Mitigation: empirical quantiles with n and window disclosed; catalysts restricted to dated PIT events; omission preferred to estimation |
| **5** | **Reliability-loop overfitting.** Learning weights from one's own track record on a small sample re-creates the power problem *inside* the weighting layer, and does so invisibly | **MEDIUM-HIGH** | Mitigation: weights update only on out-of-sample, embargoed, episode-counted evidence, with a hard floor of zero and a declared minimum episode count before any weight exceeds zero |

**Risk 2 is the one I would watch hardest.** The current platform's greatest achievement is that it
*proved itself wrong five times*. A recommendation architecture can quietly destroy that property.
`evaluation_contract` exists to prevent it and should be non-negotiable.

---

## PART 10 — Version 2 architecture

### Core domain model

`PositionDecision` (Part 2) — one holding × one horizon × one action, carrying its basis, its
defensibility, its six-component confidence, its boundary conditions, and its ex-post evaluation
contract.

Supporting: `Policy` (versioned, declared, human-authored) · `PositionState` (measured) ·
`EvidenceClaim` (no self-reported precision) · `ReliabilityRecord` (realized OOS calibration per
source × horizon × regime) · `DecisionArchive` (immutable, append-only).

### Subsystems and dependencies

```
 L0  SUBSTRATE       identity · PIT data · migrations · backups · reproducibility
                     └─ everything depends on this; currently DESTROYED, restore first
 L1  MEASUREMENT     position state · realised risk · correlation · tax lots
                     └─ deterministic, zero estimation error, ALWAYS AVAILABLE
 L2  POLICY          versioned targets, caps, bands, constraints (human-authored)
                     └─ depends on L1 only.  ► CAN PRODUCE A COMPLETE DECISION ALONE ◄
 L3  EVIDENCE        features → claims (effect + dispersion + provenance)
                     └─ depends on L0. Produces NO scores and NO precision
 L4  RELIABILITY     realised OOS calibration per source × horizon × regime
                     └─ depends on L3 + DecisionArchive.  GATES all L3 influence
 L5  SYNTHESIS       policy action, adjusted by evidence × reliability
                     └─ depends on L1, L2, L3, L4
 L6  EXPLANATION     basis decomposition · boundary conditions · typed unknowns
                     └─ depends on L5
 L7  REPORT          decision-ordered, score-last
 L8  ARCHIVE         immutable decisions + evaluation contracts ──► feeds back into L4
```

**The dependency that defines V2: L2 → decision, without L3.** The policy layer alone produces a
complete, defensible recommendation. Evidence is an *enhancement*, gated by L4, defaulting to zero.

### Scientific rationale

The system's output must not be a monotone function of a quantity that has never been demonstrated.
Measured: the ensemble loses to a constant 50% at all six horizons (CIs excluding zero); the
Brier-optimal displacement from neutral is λ = 0 with no interior optimum; confidence overclaims by
18–26 pp; the weighting ranks by inverse effect size (Spearman −1.000). Every one of those is a
consequence of building the decision *on top of* a forecast. V2 builds it on top of **measured position
state**, with the forecast as a gated, auditable, currently-zero-weight adjustment.

### Engineering rationale

Most of the platform survives — the PIT research engine, security master, feature store, portfolio
analytics, attribution, immutable archive. What is replaced is the **combination and confidence layer**
(~4 modules), which is exactly where the measured defects live. Portfolio analytics is *promoted from
adjustment to spine*, which is a re-wiring rather than a rewrite. The archive gains a feedback edge it
was always shaped for. This is an **inversion of the dependency graph, not a rebuild.**

---

## "If I were starting this project today, this is the architecture I would build."

I would build a **position-and-policy decision engine with a reliability-gated evidence layer**, and I
would build it in this order:

1. **Measurement and policy first.** Position state, realised risk, and a versioned written policy.
   This alone produces defensible Add/Hold/Trim/Exit recommendations at every horizon on day one, with
   near-certain confidence, and it can never be wrong about the future because it makes no claim about
   it.
2. **The decision archive and evaluation contract second** — before any evidence layer exists — so that
   every recommendation is falsifiable from the very first one. This is the property that took the
   current project five research phases to develop and it should be present at commit one.
3. **The reliability ledger third**, empty, with every future source defaulting to zero weight.
4. **Evidence last**, one source at a time, each earning weight only by demonstrated out-of-sample
   calibration against the contract.

That ordering inverts the current project's history, which built evidence first, decisions second,
and evaluation last — and therefore spent ~580 hours before discovering that its central quantity
could not be trusted.

**And I would ship step 1 before writing a single model.** A platform that says *"trim NVDA: it is 28%
of your book against a 15% cap, here is the tax consequence, here is what would change our mind, and we
have no reliable view on next month's return"* is more institutionally credible than anything this
project has produced — and it is buildable in weeks, from parts that already exist and already work.

---

**One caveat I will not soften:** Risk 3 says the policy layer may be trivially derivable, and the
differentiator — reliability-bounded explanation — has never been tested with a human. **That test is
15 hours and $300 and it should precede this redesign, not follow it.** Building V2 before knowing
whether anyone values the explanation would repeat the exact error this architecture is designed to
prevent: investing heavily in a capability whose value was assumed rather than measured.
