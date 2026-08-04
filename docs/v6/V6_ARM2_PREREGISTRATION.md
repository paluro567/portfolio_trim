# V6 ARM 2 — PREREGISTRATION

**Status:** FROZEN on signature. **Version 1.0.**
**Authority:** authorised in principle by the Independent Scientific Program Board
(`ARM2_PROGRAM_BOARD_REVIEW.md`), conditional on this document eliminating the four interpretation
ambiguities the Board identified.

> **Audit standard.** An external review board will audit every deviation. Every decision rule below is
> explicit, deterministic, and mechanically computable. No endpoint may be substituted, no threshold
> re-chosen, and no horizon or model selected after results are seen.

---

## PART 1 — Scientific question

### 1.1 Hypothesis

> **H1:** A cross-sectional information coefficient present in a model's *input feature* is transmitted
> to that model's *output evidence stream* with attenuation below the preregistered materiality bound.

### 1.2 Null hypothesis

> **H0:** The feature → model transformation attenuates a materially large fraction of the information
> present in its input — i.e. the models discard information demonstrably available to them.

### 1.3 What Arm 2 IS measuring

**The information transmission ratio across the feature → model segment**, for models that provably
consume the injected feature, with the propagation of that signal into the models' decision logic
independently verified.

### 1.4 What Arm 2 is NOT measuring — stated to prevent scope drift

| Not measured | Why |
|---|---|
| Whether real signal exists | The signal is injected and synthetic by construction |
| Whether the features are *good* | Feature quality is a separate question; Arm 2 injects into an existing feature |
| Combiner loss | Measured by Arm 1.5. Arm 2's endpoint stops at the model output |
| Validation-layer sensitivity | Measured by Arm 1 |
| Calibration correctness | **Already experimentally falsified.** Arm 2 measures whether calibration *changes* under injection, as a secondary only |
| Whether the weighting scheme is well-chosen | Out of scope in Arm 1.5 and remains out of scope here |
| Absolute achievable IC ceiling | Not computed. Transmission is measured relative to the injected input, not to an optimum |

---

## PART 2 — Experimental design

### 2.1 Injection location

**At the feature store, on exactly one named feature, before any model reads it.**

**Feature selection rule — deterministic, executed and recorded before any injection:**

1. Restrict to **price-derived** features (no macro, no fundamentals) so restoration class B revision
   exposure is minimised and the independent verification path is simplest.
2. Among those, select the feature with the **highest consumer count**, where a "consumer" is a model
   whose source references the feature name (determined by static analysis of `src/mip/models/*.py`).
3. Ties broken by **highest non-null coverage** on the restored panel; further ties by
   **lexicographic feature name**.

> **The selected feature name, its consumer set, and its non-consumer set MUST be written into
> `ARM2_ADDENDUM_A.md` and hashed BEFORE the first injection run.** The addendum is part of this
> preregistration.

### 2.2 Injected quantity

```
f_i(ρ)  =  f_i  +  κ · ρ · Φ⁻¹(rank(y_i))

  f_i  = original feature value for cell i
  κ    = standard deviation of f over the analysis panel, computed WITHIN horizon
  y_i  = realized spy_rel for cell i          ← READ-ONLY, NEVER MODIFIED
  ρ    ∈ {0.00, 0.05, 0.10, 0.15, 0.20, 0.30}   PRIMARY ρ = 0.10
```

### 2.3 Preserved quantities

| Preserved | Reason |
|---|---|
| **Realized outcomes (`spy_rel`)** | Read-only. Any write is a protocol violation |
| **All other features** | Only the selected feature is perturbed |
| **Model code** | Unmodified. Models run exactly as shipped |
| **Combiner, calibration, validation layer** | Unmodified — already measured by Arms 1.5 and 1 |
| **Cohort / embargo / block structure** | Identical to Arms 1 and 1.5 (`metrics.cohort`, block = 4) |

### 2.4 Randomisation

**Treatment injection is deterministic** given ρ — as in Arm 1.5 — so no seed enters the treatment arm.

**A placebo arm supplies the null distribution:**

```
f_i(placebo, s)  =  f_i  +  κ · ρ · Φ⁻¹(rank(y_π(s)(i)))
```
where `π(s)` is a **random permutation of y within date**, seeded by `s`. This preserves the injection's
marginal distribution while destroying the signal→outcome link. **≥200 placebo seeds at ρ = 0.10.**

### 2.5 Reproducibility

| Item | Specification |
|---|---|
| Seed base | `20260801`; per-run seed `= SEED_BASE + horizon_id·10⁶ + round(ρ·100)·10⁴ + s` |
| Determinism check | Full pipeline run twice under two different `PYTHONHASHSEED` values must produce **byte-identical** outputs |
| Commit | Recorded at execution; working tree must be **clean** |
| Bootstrap | 1,000 draws, circular block = 4, per-symbol series, seed 20260801 |

### 2.6 Horizons, symbols, repetitions

| Parameter | Value |
|---|---|
| Horizons | **All six** — 1w, 2w, 1m, 3m, 6m, 1y. No horizon may be dropped or selected post hoc |
| Symbols | **The full restored panel.** The symbol set is recorded in Addendum A before injection |
| Treatment repetitions | 1 per (horizon, ρ) — deterministic |
| Placebo repetitions | **≥200 seeds** at ρ = 0.10, every horizon |
| Bootstrap draws | 1,000 per cell |

### 2.7 Stopping rules

| # | Rule | Action |
|---|---|---|
| **S1** | Placebo false-positive rate at ρ = 0.10 exceeds **0.10** | **HALT.** Harness invalid; no endpoint may be reported |
| **S2** | Model code hash differs from the hash recorded in Addendum A | **HALT.** The system under test changed |
| **S3** | Determinism check fails (two `PYTHONHASHSEED` runs differ) | **HALT.** Results are not reproducible |
| **S4** | Propagation checkpoint fails (Part 3) | **VOID** for that (horizon, ρ) — reported as VOID, **never as FAIL** |
| **S5** | Runtime exceeds the Addendum-A benchmark by >3× | **HALT and re-benchmark.** No partial sweep may be reported as complete |
| — | *No adaptive stopping on the primary endpoint.* The full ρ grid runs regardless of interim results | |

---

## PART 3 — Mandatory propagation checkpoint

**Purpose: eliminate the Board's four competing explanations for a negative result.**

### 3.1 Three measurement points

```
   INJECT
     │
     ▼
 ┌─────────────┐   A1   ┌──────────────┐   A2   ┌──────────────┐   A3
 │  feature f  │───────►│ model decision│───────►│ model output │───────►  combiner
 │             │        │ logic         │        │ (effect, z)  │
 └─────────────┘        └──────────────┘        └──────────────┘
   IC of the             activation-pattern        IC of the
   injected feature      shift                     output effect
```

| Point | Where | What is measured |
|---|---|---|
| **A1** | Feature store, post-injection, pre-model | `IC_F = Spearman(f(ρ), y)` on the analysis cohort |
| **A2** | Model output metadata | **Activation-pattern shift**: the change in the set of cells where the model is non-neutral and the number of active regimes, and whether that change correlates with `y` |
| **A3** | Model output evidence | `IC_M,m = Spearman(effect_m(ρ), y)` per consumer model |

**A2 is measured from the model's own emitted metadata (`neutral` flag, active-regime count) — the
models are NOT instrumented and NOT modified.**

### 3.2 A1 — injection landed

```
PASS   IC_F bootstrap CI lower bound > 0.05
FAIL   otherwise  →  VOID for that (horizon, ρ)
```
A failure here means the injection never established a measurable input signal. **This is a VOID, not
evidence about the models.**

### 3.3 A2 — signal reached the decision logic

```
ACTIVATION_SHIFT = | activation_rate(ρ) - activation_rate(0) |
SIGNAL_ALIGNMENT = Spearman( 1[non-neutral at ρ] - 1[non-neutral at 0] , rank(y) )

PASS   ACTIVATION_SHIFT >= 0.02  OR  |SIGNAL_ALIGNMENT| CI excludes zero
FAIL   ACTIVATION_SHIFT < 0.02  AND  SIGNAL_ALIGNMENT CI includes zero
       →  PROPAGATION FAILURE  →  VOID for that (horizon, ρ, model)
```

**Rationale:** the models activate on percentile-threshold crossings. If injected signal reaches the
decision logic, either the activation set must change, or the change must align with `y`. **If neither
occurs, the signal did not enter the model's decision path and no statement about model information
loss is licensed.**

### 3.4 A3 — transmission

Measured per consumer model and aggregated (Part 4).

### 3.5 Threshold saturation — measured, not assumed

```
SATURATION_RATE(ρ) = fraction of cells where the injected feature crosses ALL
                     percentile thresholds the model applies to it
```
Recorded at every ρ. **If SATURATION_RATE(0.10) > 0.50**, the model is threshold-saturated and its
result is reported **separately and excluded from the primary aggregate**, with the exclusion recorded
in advance by this rule rather than chosen afterwards.

### 3.6 Multi-model dilution — eliminated by design

The consumer / non-consumer split is **fixed in Addendum A before injection**.

- **Primary endpoint uses CONSUMER models only.** Dilution by non-consumers cannot enter it.
- **Non-consumer models are a NEGATIVE CONTROL** (Part 5, SE-1): their output IC must not change.

### 3.7 How propagation failure is distinguished from genuine information loss

| A1 | A2 | A3 | Conclusion |
|---|---|---|---|
| PASS | PASS | high IC | **Signal transmitted.** Models preserve information |
| PASS | PASS | **≈ 0** | **GENUINE MODEL INFORMATION LOSS.** Signal provably entered the decision logic and did not emerge |
| PASS | **FAIL** | any | **PROPAGATION FAILURE.** VOID. No statement about the models |
| **FAIL** | any | any | **INJECTION FAILURE.** VOID. No statement about anything |

**This table is the mechanism that eliminates the Board's ambiguity. It is applied before the primary
endpoint is computed.**

---

## PART 4 — Primary endpoint

### 4.1 Definition

> **TRANSMISSION(ρ) = IC_M(ρ) / IC_F(ρ)**
>
> `IC_F` = IC of the injected feature (checkpoint A1)
> `IC_M` = IC of the equal-weight consensus of **consumer-model** output effects (checkpoint A3)
>
> **Primary endpoint: TRANSMISSION at ρ = 0.10, per horizon, with a block-bootstrap CI.**

A ratio is used because it is scale-free: it does not require inventing an absolute IC constant, and it
is invariant to how much signal the injection happened to establish.

### 4.2 Validity precondition

The ratio is only computed where **A1 PASS** (`IC_F` CI lower bound > 0.05) and **A2 PASS**. Otherwise
the cell is **VOID**.

### 4.3 Estimator and null distribution

| Element | Specification |
|---|---|
| Estimator | Ratio of Spearman rank correlations on the non-overlapping cohort |
| Bootstrap | Circular block bootstrap, block = 4, per-symbol series, 1,000 draws, seed 20260801. **`IC_F` and `IC_M` are recomputed on the SAME resample index**, preserving their dependence |
| CI | 2.5th / 97.5th percentile of the bootstrap ratio distribution |
| Null distribution | The **placebo arm** (≥200 permuted seeds at ρ = 0.10). Under the null, `IC_F ≈ 0`, so the placebo primarily establishes the **false-positive rate for A1/A2**, not a ratio null |

### 4.4 Decision rule — mechanical, applied per horizon

```
VOID           if A1 FAIL or A2 FAIL
PASS           if CI_lower(TRANSMISSION) > 0.75
FAIL           if CI_upper(TRANSMISSION) < 0.50
INCONCLUSIVE   otherwise
```

**Threshold justification, declared in advance:** a percentile/threshold transform is expected to
attenuate somewhat; retaining ≥75% is consistent with a faithful transform. Discarding **more than
half** the information demonstrably present in the input is a first-order defect on any reading. The
0.50–0.75 band is declared inconclusive rather than assigned to either verdict.

### 4.5 Pooling — specified in advance

**Arm 1.5 surfaced a preregistration gap: one endpoint was named but six were produced, with no pooling
rule. That gap is closed here.**

> **No pooled verdict is computed.** The rule is applied at **all six horizons** and reported as a
> distribution. The **program-level conclusion** is defined mechanically as:
>
> - **PROGRAM FAIL** if FAIL at **≥2** horizons with n ≥ 400
> - **PROGRAM PASS** if PASS at **≥2** horizons with n ≥ 400 **and** FAIL at none
> - **PROGRAM INCONCLUSIVE** otherwise
>
> The `n ≥ 400` restriction is declared now, not chosen later: Arm 1 measured that horizons below that
> size have MDE ≥ 0.15 and, at n = 47, a false-positive rate of 9.5%.

---

## PART 5 — Secondary endpoints

**No secondary endpoint may override, modify, or substitute for the primary decision.** Each is
reported with its own limit and its relationship to the primary stated explicitly.

| ID | Endpoint | Purpose | Decision limit | Relationship to primary |
|---|---|---|---|---|
| **SE-1** | **Non-consumer negative control**: change in output IC for models that do not read the injected feature | Confirms the injection is feature-specific and dilution is controlled | \|ΔIC\| CI must include zero. **If it excludes zero, the injection leaked** and the primary is reported with a leak caveat | **Diagnostic.** Cannot change the primary verdict; a leak downgrades confidence, not the verdict |
| **SE-2** | Per-model transmission ratio, each consumer separately | Locates loss to a specific model | None. Descriptive | Decomposes the primary; never replaces it |
| **SE-3** | Saturation rate per model per ρ | Detects threshold saturation | > 0.50 at ρ = 0.10 ⇒ that model is excluded from the primary aggregate **by the Part 3.5 rule** | Exclusion rule is preregistered, not post hoc |
| **SE-4** | Activation rate and neutral rate per model per ρ | Structural stability of model outputs | Descriptive; feeds the Part 6 matrix | Diagnostic only |
| **SE-5** | **Calibration shift**: mean \|score − 50\| of the combined score at ρ vs ρ = 0 | Does injected signal change calibration behaviour? | Descriptive. **Calibration is already experimentally falsified**; this measures *change*, not correctness | **Never** affects the primary verdict |
| **SE-6** | Combined-score IC (post-combiner) | End-to-end context; comparability with Arm 1.5 | Descriptive | Reported for continuity; the primary stops at the model output |
| **SE-7** | Dose–response monotonicity of `TRANSMISSION` across the ρ grid | A non-monotone response indicates a harness defect | Non-monotone at a well-powered horizon ⇒ flagged as a harness concern in the report | Diagnostic |
| **SE-8** | Runtime and cell counts per configuration | Feasibility record | Stopping rule S5 | Operational |

---

## PART 6 — Interpretation matrix

**Every outcome maps to exactly one interpretation.** Dimensions:
**P** propagation (A1∧A2) · **L** information loss (primary) · **C** calibration shift (SE-5) ·
**S** model output structure (SE-4 activation stability).

### 6.1 Propagation failed — collapses regardless of other dimensions

| P | L | C | S | Scientific conclusion | Engineering conclusion | Next experiment | Program implication |
|---|---|---|---|---|---|---|---|
| **FAIL** | any | any | any | **VOID.** No statement about feature→model information loss is licensed | The injection mechanism, not the pipeline, is the object needing repair | Re-specify injection (different feature or larger κ) and re-run Arm 2. **This is not a new arm** | Feature→Model remains **COMPLETELY UNMEASURED**. No gate advances |

### 6.2 Propagation succeeded — the eight live cells

| # | L | C | S | Scientific conclusion | Engineering conclusion | Next experiment | Program implication |
|---|---|---|---|---|---|---|---|
| 1 | **low** | unchanged | preserved | **Models transmit information faithfully.** Cleanest possible result | No repair indicated in feature→model | **Arm 3** (real documented effect, end to end) | All downstream segments measured and cleared. **Feature generation becomes the last unmeasured stage** |
| 2 | **low** | changed | preserved | Models transmit; calibration responds to signal | Calibration repair is now measurable, and is a separate known defect | Arm 3 | As #1, plus calibration repair becomes empirically checkable |
| 3 | **low** | unchanged | **degraded** | Models transmit **despite** activation instability | Activation logic is unstable but not lossy | Arm 3; instrument activation stability | As #1, with a recorded structural caveat |
| 4 | **low** | changed | **degraded** | Transmission preserved; both calibration and structure move | Two separate defects, neither lossy | Arm 3 | As #1, two caveats recorded |
| 5 | **high** | unchanged | preserved | **MODELS DESTROY INFORMATION** demonstrably present in their inputs, without structural change | The loss is in the model's *transformation*, not its activation logic | **Diagnostic decomposition of the model transform** — not Arm 3 | **Decisive.** No dataset repairs this. The purchase track cannot proceed on a signal-destroying pipeline |
| 6 | **high** | changed | preserved | Models destroy information; calibration also responds | As #5 | As #5 | As #5 |
| 7 | **high** | unchanged | **degraded** | Models destroy information **and** activation is unstable | Loss plausibly located in threshold/activation logic — SE-3 saturation identifies which models | As #5, prioritising the saturating models | As #5 |
| 8 | **high** | changed | **degraded** | Models destroy information with both calibration and structural instability | Multiple concurrent defects | As #5 | As #5 |

### 6.3 Inconclusive primary

| P | L | Interpretation |
|---|---|---|
| PASS | **INCONCLUSIVE at every horizon with n ≥ 400** | The experiment ran validly and did not resolve. **Report as inconclusive.** Do not substitute a secondary endpoint. Do not re-run with altered thresholds. Feature→Model remains unmeasured |

---

## PART 7 — Implementation readiness

**No implementation may begin until every box is ticked and Addendum A is hashed.**

| # | Prerequisite | Requirement | Status |
|---|---|---|---|
| **R1** | **Data restoration** | Prices, macro, feature store rebuilt; backup taken immediately after | ☐ **BLOCKED** |
| **R2** | **Repository state** | Working tree clean; commit recorded; **model code hashed into Addendum A** | ☐ |
| **R3** | **Recovered artifacts** | Restored panel documented: symbols, dates, coverage. **Recorded as class B (approximate) — a new study, never a reproduction of prior work** | ☐ |
| **R4** | **Feature selection executed** | Part 2.1 rule run; feature name, consumer set, non-consumer set written to Addendum A | ☐ |
| **R5** | **Runtime benchmark** | One full (horizon × ρ) cell timed end to end; total sweep cost projected and recorded. **The Board flagged this as entirely unquantified** | ☐ |
| **R6** | **Compute requirements** | Projected cost within budget; batching plan recorded if the naive sweep is infeasible | ☐ |
| **R7** | **Determinism** | Two full runs under different `PYTHONHASHSEED` produce byte-identical output | ☐ |
| **R8** | **Version control** | This preregistration and Addendum A committed and hashed **before** the first injection | ☐ |
| **R9** | **Hashing** | SHA-256 of: this document, Addendum A, model source, feature-store snapshot, restored-panel manifest | ☐ |
| **R10** | **Random seeds** | `SEED_BASE = 20260801`; derivation formula in 2.5; ≥200 placebo seeds | ☐ |
| **R11** | **Placebo arm implemented** | Within-date permutation of `y`; verified to preserve marginal distributions | ☐ |
| **R12** | **Outcome write-protection** | `spy_rel` verified read-only by test; any write fails the run | ☐ |

### Addendum A — required contents, frozen before first injection

```
ARM2_ADDENDUM_A.md
  selected_feature            : ______________________
  selection_rule_output       : consumer count ___, coverage ___, tie-breaks applied ___
  CONSUMER models             : [ ______________________ ]
  NON-CONSUMER models         : [ ______________________ ]   <- SE-1 negative control
  restored panel: symbols ___ dates ___ range ___ to ___
  model source SHA-256        : ______________________
  feature-store snapshot hash : ______________________
  runtime benchmark           : ___ s per (horizon x rho) cell;  projected sweep ___ h
  Prepared by ______  Date ______   SHA-256 of this addendum ______
```

---

## PART 8 — Freeze declaration

```
V6 ARM 2 PREREGISTRATION · VERSION 1.0

PRIMARY ENDPOINT   TRANSMISSION = IC_M / IC_F  at rho = 0.10, per horizon
DECISION RULE      VOID if A1 or A2 fails
                   PASS  if CI_lower > 0.75
                   FAIL  if CI_upper < 0.50
                   else INCONCLUSIVE
PROGRAM RULE       FAIL at >=2 horizons with n>=400  -> PROGRAM FAIL
                   PASS at >=2 horizons with n>=400 and no FAIL -> PROGRAM PASS
                   otherwise -> PROGRAM INCONCLUSIVE

The following may NOT change after signature:
  - the hypothesis and null hypothesis
  - the injection formula and rho grid
  - the propagation checkpoint and its thresholds (0.05 / 0.02)
  - the primary endpoint, its estimator, and its 0.75 / 0.50 limits
  - the pooling rule and the n>=400 restriction
  - the stopping rules S1-S5
  - the interpretation matrix

Deviations must be logged as deviations and reported. They may not be
described as revisions.

Prepared by ______________________   Date ______________
Approved   ______________________   Date ______________

SHA-256 (this document)  ______________________________________________
SHA-256 (Addendum A)     ______________________________________________
Recorded in program register  ☐
```

### Ambiguity-elimination audit

| Board ambiguity | Eliminated by | Mechanism |
|---|---|---|
| **1 · Feature→Model information loss** | Primary endpoint | The quantity being measured |
| **2 · Injection propagation failure** | **A1 + A2 checkpoints** | Failure yields **VOID**, never FAIL. No statement about models is licensed without verified propagation |
| **3 · Model threshold saturation** | **SE-3 + Part 3.5** | Saturation measured; >0.50 excludes that model from the primary **by preregistered rule** |
| **4 · Multi-model dilution** | **Consumer/non-consumer split fixed in Addendum A** | Primary uses consumers only; non-consumers are a negative control (SE-1) |

**All four ambiguities identified by the Program Board are eliminated by preregistered mechanism rather
than by post-hoc argument.**
