# V6 Arm 2 Preregistration — Amendment B

**Issuing body:** V6 Arm 2 Preregistration Amendment Committee
**Version:** B, v1.0 · **Effective date:** 2026-08-02
**Amends:** `V6_ARM2_PREREGISTRATION.md` (original preserved verbatim; nothing edited in place)
**Status:** DRAFT — unsigned, unhashed. See §13.

---

## 1. Reason for amendment

The Arm 2 readiness review refused authorization on three blockers. All three trace to a single root defect: **the preregistration defined feature consumption syntactically** — as the appearance of a feature name in model source — when the scientific question requires a **causal** definition. That one error produced a treatment arm of boilerplate, a control arm of one, and a propagation checkpoint that could not fire.

This amendment replaces the syntactic definition with a two-stage causal one, rebuilds selection and control design on top of it, and repairs the A2 checkpoint so it measures propagation rather than emission. It does **not** change the scientific question, the injection family, the primary endpoint, or any decision threshold.

## 2. Blockers resolved

| Blocker | Resolved by |
|---|---|
| B-01 syntactic references treated as value consumption | §4 two-stage consumer definition |
| B-02 selection rule collapsed the control arm to n=1 | §5 selection rule with explicit floors on **both** arms |
| B-03 A2 failed at every ρ because of a threshold dead zone | §7 A2 redefined on pre-threshold decision variables |

## 3. Superseded language

### 3.1 Original (Part 2.1, feature selection) — SUPERSEDED

> (1) restrict to price-derived features; (2) highest consumer count by static analysis of `src/mip/models/*.py`; (3) ties → highest non-null coverage → lexicographic name.

**Replaced by §5.**

### 3.2 Original (Part 2.2, checkpoint A2) — SUPERSEDED

> A2: `ACTIVATION_SHIFT ≥ 0.02` OR `|SIGNAL_ALIGNMENT|` CI excludes zero.

**Replaced by §7.**

### 3.3 Original (consumer/non-consumer partition) — SUPERSEDED

> consumer set / non-consumer set written to Addendum A [as produced by static analysis]

**Replaced by §4 and §6.**

### 3.4 Retained unchanged

Injection family `f_i(ρ) = f_i + κ·ρ·Φ⁻¹(rank(y_i))`; ρ grid {0.00, 0.05, 0.10, 0.15, 0.20, 0.30}; PRIMARY ρ = 0.10; `TRANSMISSION = IC_M / IC_F`; PASS ≥ 0.75, FAIL ≤ 0.50, INCONCLUSIVE between; A1; saturation exclusion at 0.50; program rule (FAIL at ≥2 horizons with n ≥ 400); `SEED_BASE` = 20260801; ≥200 placebo seeds; stopping rules S1–S5.

---

## 4. Revised definition of a feature consumer

**Definition.** A model M is a **consumer** of feature F if and only if changing the **value** of F, holding every other input fixed, can change at least one of: model activation, model state, model effect, model score, or model metadata used in decision logic.

### 4.1 Explicitly non-qualifying

Reading only the feature timestamp; use as a data-availability clock; retrieving a definition without reading values; dead-code references; logging; metadata-only access; indirect references with no causal path to output. **The `_latest_feature_date()` helper — which reads `series.index[-1]` — is the canonical non-qualifying pattern and is excluded by name.**

### 4.2 Stage 1 — static dependency tracing

Build the reference graph over `src/mip/models/*.py` **and every module reachable from them** (`src/mip/research/*.py`, `src/mip/repositories/*.py`), including dynamically constructed names resolved by evaluating the model's own name templates at import time.

- **Stage-1 CANDIDATE:** at least one reference to F that is not on the §4.1 exclusion list.
- **Stage-1 EXCLUDED:** no references, or references exclusively on the exclusion list.

Stage 1 is **necessary but never sufficient.** It may only *remove* models from consideration; it may never confer consumer status.

### 4.3 Stage 2 — controlled perturbation (causal response test)

For every model surviving Stage 1, and every model not surviving it (to detect Stage-1 false negatives):

1. Compute baseline outputs over the **probe grid** (§4.4) with no perturbation.
2. For each `mult ∈ {2, 4, 8}` and each `sign ∈ {+1, −1}`, add `sign · mult · σ_F` to F at the cell's `as_of` only, leaving history and all other features untouched.
3. Re-evaluate all models and compare the **response vector** per (model, symbol, as_of, horizon):
   `(score, |active_regimes|, diagnostics.z_raw)`.

**PASS (genuine consumer):** the response vector differs from baseline in **≥ 1 cell** at **≥ 1 horizon** for **≥ 1** (mult, sign) combination.
**FAIL (genuine non-consumer):** the response vector is **identical to baseline in every cell, every horizon, every (mult, sign) combination**.

The escalating multiplier exists solely to defeat dead-zone false negatives in **classification**. It is a detection probe and is **never** used as the experimental injection. Injection strength remains frozen at the §3.4 ρ grid.

### 4.4 Probe grid

Deterministic and predeclared: every 130th session from 2013-01-01 to 2025-06-30, crossed with the 6 operating companies having ≥252 sessions of prior history (ADBE, AMD, AMZN, CRM, NOW, TSLA). **150 cells.** HNST excluded (history begins 2021-05-04).

### 4.5 Exhaustiveness and mutual exclusivity

Stage 2 is a total function on the model set: every model is probed, and every model returns PASS or FAIL. Therefore CONSUMERS ∪ NON-CONSUMERS = the model set and CONSUMERS ∩ NON-CONSUMERS = ∅ **by construction**, not by inspection.

### 4.6 Liveness gate, applied before classification

A model is **LIVE** for a given panel if its score varies across the probe grid. A model whose output is constant is **DEAD**: it can be neither a consumer (no response is detectable) nor a control (no leakage is detectable). DEAD models are removed before classification and recorded by name.

---

## 5. Revised feature-selection rule

Uses only pre-outcome properties. No realized return, no transmission result, and no model outcome enters at any step.

### 5.1 Eligibility filter — all six must hold

| # | Requirement | Threshold |
|---|---|---|
| E1 | Genuine consuming models (§4, LIVE only) | **≥ 2** |
| E2 | Genuine non-consuming models (§4, LIVE only) | **≥ 2** |
| E3 | Activation frequency — probe cells in which ≥1 consumer responds | **≥ 20% of probe grid** |
| E4 | Non-null coverage over the injection panel | **≥ 0.95** |
| E5 | Independently verifiable definition — deterministic function of stored prices, `depends_on` chain fully resolvable, recomputable from the feature registry | must hold |
| E6 | No dependence on commercial/licensed data beyond the existing price feed | must hold |

### 5.2 Deterministic tie-breakers — declared before candidate inspection

Applied in strict order to features passing §5.1:

1. Highest count of genuine LIVE consumers.
2. Highest count of genuine LIVE non-consumers.
3. Highest activation frequency (E3).
4. Highest non-null coverage (E4).
5. Shortest `depends_on` chain (prefer directly price-derived).
6. Lexicographically smallest feature name.

### 5.3 Null result is a permitted and binding outcome

If no feature satisfies §5.1, the result is **NO ELIGIBLE FEATURE — ARM 2 BLOCKED**. The eligibility thresholds may not be lowered to produce a selection. Any future relaxation requires a separate, separately justified amendment naming the threshold changed and the reason.

---

## 6. Revised control design

### 6.1 Requirements

| Property | Requirement |
|---|---|
| Minimum control models | **2** genuine non-consumers |
| Minimum active control outputs | **2** LIVE controls (constant-output models never count) |
| Required output variability | control score SD > 0 across the probe grid |
| Allowable shared preprocessing | shared price ingestion, calendar, cohort construction, embargo — none of which is perturbed |
| Prohibited shared dependencies | a control may not consume the injected feature, nor any feature declaring it in `depends_on`, nor any feature derived from it |
| Contamination detection | any control whose response vector changes under injection at any ρ → **CONTROL CONTAMINATION — VOID** |
| Degenerate constant-output models | classified DEAD (§4.6), removed before classification, recorded by name, never counted as control or consumer |

### 6.2 Why a model-level control is required, not optional

The leakage hypothesis is: *injected information reaches models that do not read the feature, via a path the design did not intend.* Only a model-level control tests that. Feature placebo, symbol permutation and date permutation each test a different hypothesis — that the observed transmission exceeds chance — and are **complements, not substitutes**.

### 6.3 Predeclared fallback, and its limits

If §6.1 cannot be met, the Committee has considered whether an alternative control tests the same hypothesis:

| Alternative | Tests the same leakage hypothesis? | Disposition |
|---|---|---|
| Feature placebo (inject a feature no live model consumes) | **Partly** — detects a shared-substrate leak, but cannot detect leakage through a model that reads a *correlated* feature | Retained as a **secondary** control only |
| Symbol permutation | No — tests cross-sectional chance, not leakage | Not equivalent |
| Date permutation | No — tests temporal chance, not leakage | Not equivalent |
| Non-consumed feature injection | Same as feature placebo | Secondary only |
| Shadow feature column (write injected values to an unread column) | No — tests only that unread data stays unread; trivially true | Not equivalent |

**None is scientifically equivalent to a model-level control.** Accordingly, §6.1 is a **hard requirement**. If it cannot be met, Arm 2 is blocked; it does not proceed on a substitute.

---

## 7. Revised A2 propagation checkpoint

### 7.1 What A2 must establish

*Did the injected feature information causally reach the model's operative decision logic?* — **not** whether the model's output changed. The original A2 conflated the two, so a model with a threshold dead zone registered as "no propagation" when propagation had in fact occurred and been absorbed.

### 7.2 Exact observable

A **non-mutating instrumentation tap** on the model's own condition-evaluation path records, for every condition evaluated during a real scoring call:

`(model, symbol, as_of, horizon, feature, current_value, threshold_value, percentile_position, threshold_side)`

The tap is a passive observer inside the real model path. It does not recompute, reimplement, or approximate the model's logic, and it does not alter execution.

**Primary A2 observable — PERCENTILE-STATE MOVEMENT:**

`Δpctl = percentile_position(ρ) − percentile_position(0)`

the signed shift of the injected feature's position within the model's own lookback distribution, as computed by the model's own quantile machinery.

**Secondary A2 observables** (reported always, decisive only where stated in §9):
- `THRESHOLD_SIDE_CHANGE` — fraction of (cell, condition) pairs whose threshold side flips.
- `Δdistance_to_threshold` — change in |current_value − threshold_value|.
- `ACTIVATION_ELIGIBILITY_CHANGE` — change in `|active_regimes|`.

### 7.3 Unit of analysis

The **(cell, condition) pair**: one evaluated condition referencing the injected feature, for one (symbol, as_of), at one horizon. Bootstrap resampling is by **symbol block** (circular, block = 4), matching Arm 1 and Arm 1.5.

### 7.4 Null behaviour

At ρ = 0, `Δpctl ≡ 0` exactly for every pair, since the injection term is identically zero. The null is degenerate and exact — not estimated — which is why A2 can use a mean rather than a null-calibrated statistic.

### 7.5 Decision rule

Let `MEAN_ABS_PCTL_SHIFT = mean |Δpctl|` over all (cell, condition) pairs at the primary ρ.

| Outcome | Rule |
|---|---|
| **PASS** | CI lower bound of `MEAN_ABS_PCTL_SHIFT` **> 0.01** (1 percentile point) **AND** ≥ 1 consumer model instrumented at ≥ 1 condition |
| **FAIL** | CI upper bound **< 0.005** |
| **INCONCLUSIVE** | otherwise |

Required sample size: **≥ 400 (cell, condition) pairs per horizon**, matching the program rule's n ≥ 400.

### 7.6 A2 remains distinct from A3

| | A2 | A3 |
|---|---|---|
| Question | did information **arrive** at the decision logic? | did the model **emit** it? |
| Observable | percentile position within the model's lookback distribution | `ModelScore.score` |
| Location | inside the condition-evaluation path, pre-threshold | model output, post-combination |
| Can pass while the other fails | yes — arrival without emission is the *informative* case | yes — emission without arrival indicates contamination |

They are **not** collapsed. A2 passing and A3 near zero is a scientifically meaningful result (information arrived and was absorbed); under the original design that same state was indistinguishable from injection failure.

---

## 8. Threshold saturation and model suitability

### 8.1 Unsuitability criteria — evaluated BEFORE execution, from probe data only

A model is **UNSUITABLE for continuous feature-level injection** if, on the probe grid:

| # | Criterion | Threshold |
|---|---|---|
| U1 | Discontinuous consumption — feature enters only via threshold comparison, no continuous path | structural, from the tap |
| U2 | Activation sparsity — fraction of probe cells with any active condition on the feature | **< 0.10** |
| U3 | Insufficient crossings — threshold-side changes at max probe perturbation | **< 20 cells** |
| U4 | Saturation — `diagnostics.saturated` true in **> 50%** of probe cells |
| U5 | Neutrality — model neutral in **> 50%** of probe cells |
| U6 | Unstable internal state — response vector non-reproducible across two runs at fixed seed |

### 8.2 Disposition — fixed in advance

A model meeting **U1 only** (thresholded but adequately active) is **RETAINED** in the primary experiment, and its A2 is evaluated on percentile-state movement per §7. This is the case the original design mishandled.

A model meeting **U2, U3, U4 or U5** is **EXCLUDED before execution** and recorded by name in Addendum A, with the criterion and measured value.

A model meeting **U6** is a **HALT** condition (stopping rule S1).

Excluded thresholded models may be studied under a separate, separately preregistered **threshold-response experiment** using a discrete injection family. That experiment is **not** authorized by this amendment.

### 8.3 Anti-gaming clause

All suitability determinations are made from probe data **before** the primary endpoint is computed, and are recorded in Addendum A before first injection. **No model's treatment may be changed after the primary endpoint is observed.** Violation voids the arm.

---

## 9. Primary endpoint disposition — RETAINED, with two gaps closed

`TRANSMISSION = IC_M / IC_F` is **retained**. Readiness evidence exposed two specification gaps that make the ratio ill-defined in states that actually occur; both are closed below. Neither changes a threshold.

### 9.1 Retained unchanged
PASS `CI_lower > 0.75` · FAIL `CI_upper < 0.50` · INCONCLUSIVE otherwise · saturation exclusion at 0.50 · program rule (FAIL at ≥2 horizons with n ≥ 400 → PROGRAM FAIL).

### 9.2 Denominator floor and behaviour near zero
`|IC_F| ≥ 0.05` is required, consistent with A1's existing `CI_lower(IC_F) > 0.05`. Below the floor the ratio is **not computed** and the arm returns **INJECTION FAILURE — VOID**. This prevents an unstable ratio being reported as a finding.

### 9.3 Sign handling — gap closed on measured evidence
Readiness measured `momentum_exhaustion`'s IC becoming **more negative** as ρ rose (−0.0045 → −0.0101 → −0.0248) while `IC_F` rose. TRANSMISSION is then **negative**, a state the three-way rule does not cover: a large-magnitude negative ratio would have been silently recorded as FAIL, when it in fact evidences **strong transmission with inverted sign** — the expected behaviour of a contrarian model ("exhaustion": high recent return ⇒ bearish).

**Correction:** thresholds are applied to **|TRANSMISSION|**; the sign is reported separately as `TRANSMISSION_SIGN`. A model with `|TRANSMISSION|` CI lower > 0.75 and negative sign is **VALID MODEL TRANSMISSION (sign-inverted)**, not FAIL. This is a repair to an undefined region, not a relaxation: no threshold value changes.

### 9.4 Pooling, weighting, intervals

| Element | Specification |
|---|---|
| Horizon pooling | **None** for the primary endpoint — reported per horizon. The program rule aggregates across horizons. |
| Consumer-model pooling | Inverse-variance weighted mean of per-model TRANSMISSION. **Requires ≥ 2 consumer models** — this is precisely what E1 protects. |
| Weighting | Inverse bootstrap variance of each model's TRANSMISSION |
| Confidence interval | Circular block bootstrap, 1000 draws, block = 4 — identical to Arm 1.5 |
| Bootstrap unit | **Per-symbol series block** (not the cell), matching Arm 1 and Arm 1.5 |
| Missing outputs | A model neutral or NaN in a cell → cell dropped **for that model only**. If > 50% of cells drop → model EXCLUDED under U5, recorded before the endpoint is computed. |

## 10. Revised interpretation matrix

Applied in strict order; the first matching row governs. `A3` is `|TRANSMISSION|`: high ≥ 0.75, moderate 0.50–0.75, near-zero ≤ 0.50.

| # | A1 | A2 | Control leakage | Saturation | A3 | **Verdict** |
|---|---|---|---|---|---|---|
| 1 | FAIL | any | any | any | any | **INJECTION FAILURE — VOID** |
| 2 | PASS | any | **present** | any | any | **CONTROL CONTAMINATION — VOID** |
| 3 | PASS | FAIL | absent | any | any | **PROPAGATION FAILURE — VOID** |
| 4 | PASS | INCONCLUSIVE | absent | any | any | **INCONCLUSIVE** |
| 5 | PASS | PASS | absent | **present** | any | **MODEL UNSUITABLE FOR THIS INJECTION DESIGN** |
| 6 | PASS | PASS | absent | absent | high | **VALID MODEL TRANSMISSION** |
| 7 | PASS | PASS | absent | absent | moderate | **INCONCLUSIVE** |
| 8 | PASS | PASS | absent | absent | near-zero | **VALID MODEL INFORMATION LOSS** |

**Binding constraint:** row 8 is the **only** route to a negative finding, and it requires A1 PASS, A2 PASS, controls clean, and no saturation. No negative result may be labelled model information loss on any other path. Under the original design, rows 1, 3, 5 and 8 were indistinguishable — which is precisely how a foreseeable VOID could have been reported as an information-loss finding.

Sign-inverted transmission (§9.3) resolves to row 6 with `TRANSMISSION_SIGN = −1` recorded.

## 11. Readiness requirements under Amendment B

R1–R12 of the original preregistration remain in force. Amendment B adds:

| # | Requirement |
|---|---|
| R13 | Stage-1 static trace executed over models **and all reachable modules**; result recorded per candidate |
| R14 | Stage-2 causal-response probe executed on the full probe grid; PASS/FAIL recorded per (feature, model) |
| R15 | Liveness gate applied; DEAD models named before classification |
| R16 | Eligibility filter §5.1 applied mechanically; **NO ELIGIBLE FEATURE is a valid terminal outcome** |
| R17 | Condition-evaluation tap implemented and verified non-mutating (byte-identical outputs with tap on vs off) |
| R18 | Suitability criteria U1–U6 evaluated and recorded **before** first injection |

## 12. Implementation references

| Component | Location |
|---|---|
| Injection hook (feature read path) | `FeatureRepository.get_instrument_series` wrapper, `V6_ARM2_INJECTION_IMPLEMENTATION.md` §2 |
| Stage-2 probe harness | `/tmp/consumer_census.py`, `/tmp/deep_probe.py` — to be relocated under `tools/v6/` before signature |
| A2 tap | condition-evaluation path, `src/mip/research/conditions.py` (`ctx.value`, `ctx.quantile`) — **not yet implemented** |
| Diagnostics surface | `ScoreDiagnostics` (`src/mip/models/base.py:199`): `active_regimes`, `z_raw`, `z_clipped`, `saturated` |
| Liveness / DEAD determination | `V6_ARM2_DATA_RESTORATION_REPORT.md` §6 |

## 13. Scientific impact, limitations, signatures

### 13.1 Scientific impact
The scientific question is unchanged: *does information injected into a feature propagate to the models that consume it, and not to those that do not?* Amendment B changes only how "consume" is determined, how propagation is detected, and how undefined regions of the endpoint are resolved. **No threshold is relaxed. Injection strength is unchanged. No feature is selected on outcomes.**

### 13.2 Limitations
- The Stage-2 probe establishes causal dependence on a 150-cell grid. A dependency that fires in fewer than ~1/150 cells would be missed. Mitigated by the escalating ±2/±4/±8 SD multipliers, not eliminated.
- The A2 tap is specified but **not implemented**; R17 is open.
- All determinations are specific to the restored class-B panel (`V6_ARM2_DATA_RESTORATION_REPORT.md` §4). They do not transfer to a differently constituted universe.
- Three of seven official models are DEAD for reasons that are **not repairable** — fundamentals and earnings are not point-in-time restorable (B-05).

### 13.3 Version history
- v1.0 · 2026-08-02 · initial issue. Supersedes original Part 2.1, Part 2.2 A2, and the static consumer partition. Original preregistration preserved unedited.

### 13.4 Signatures

| Role | Name | Date | Signature |
|---|---|---|---|
| Preregistration Amendment Committee Chair | — | — | *unsigned* |
| Independent Research Integrity Board | — | — | *unsigned* |
| Program Board | — | — | *unsigned* |

*No signature recorded. No human evidence of sign-off exists.*

### 13.5 Hash field

| Artifact | SHA-256 |
|---|---|
| `V6_ARM2_PREREGISTRATION.md` | *pending — blocked on clean tree* |
| `V6_ARM2_PREREGISTRATION_AMENDMENT_B.md` | *pending* |
| Model source at execution commit | *pending* |
| Feature-store snapshot | *pending* |
| Restored-panel manifest | *pending* |

Hashes are deliberately omitted: the working tree is dirty (56 uncommitted paths at HEAD `1b2aec9f`), and a hash over an uncommitted tree binds nothing.
