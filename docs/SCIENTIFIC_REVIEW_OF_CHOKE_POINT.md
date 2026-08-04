# Independent Scientific Review — Is the Proposed Choke Point the Root Constraint?

**Charge:** not to find another bottleneck, but to determine whether the proposed choke point is the
project's **root** constraint or merely the **deepest identified so far**. A platform redesign will be
decided on this answer.

**Verdict, stated first: it is NOT the root constraint.** It fails the necessity test and fails the
sufficiency test. The review identifies the root constraint below, and — importantly — **the
recommended experiment does not change.** Only the reason for running it, and what one does with the
other 75 hours, changes.

---

## PART 1 — The hypothesis, stated precisely

**Informal (as proposed):** *"The project's primary choke point is that the validation framework has no
mechanism to distinguish genuine null effects from underpowered studies."*

### Restated as a falsifiable scientific claim

> **H_A:** For the population of research questions this project has posed, the validation pipeline's
> minimum detectable effect (MDE) exceeds the magnitude of effects actually present in the data;
> consequently a material fraction of the project's negative results are **Type II errors** rather than
> true negatives, and the framework's lack of a sensitivity gate is the binding constraint on producing
> validated claims.

### Assumptions required for H_A to be true

**Explicit:**
1. The ten gates in `VALIDATION_GATES.md` contain no false-negative test. *(VERIFIED — grep for
   `power|detectable|false negative|sensitivity|positive control` returns zero matches.)*
2. G8 requires disclosure of small n, not achievement of adequate n. *(VERIFIED by quotation.)*
3. Underpowered and genuinely-null studies receive the same disposition. *(VERIFIED by the promotion
   discipline text.)*
4. Throughput of validated claims has been zero. *(VERIFIED — 5 phases, 0 promotions.)*

**Hidden — and this is where the hypothesis breaks:**
5. **Real effects existed in the data and the framework failed to detect them.** Without this, no Type II
   error has ever occurred, and "CI includes zero" was the *correct* output every time.
6. That "cannot determine" verdicts represent *failures of the instrument* rather than *accurate reports
   of a genuinely small or absent effect*.
7. That the throughput unit is "validated claims," and that a diagnostic improvement therefore counts as
   a throughput improvement.
8. That the project's decisive findings (the ones with CIs excluding zero) are not evidence that the
   instrument works.

**Untested:**
9. The pipeline's actual MDE — **never measured, only estimated, and the estimate was wrong twice.**
10. Whether effects of the size the project seeks (IC ≈ 0.03–0.05) exist in this information set at all.
11. Whether the model/combiner layer destroys signal that the features carry.

**Assumption 5 is doing all the work, and it has never been tested.** H_A as stated presupposes its own
conclusion.

---

## PART 2 — Necessity test

*If the framework HAD a working false-negative test, would each historical failure still have occurred?*

| # | Historical outcome | Still fails? | Why |
|---|---|---|---|
| 1 | **Analogue model rejected** | **YES** | Rejected for *leakage* (3m/6m/1y promise was 100% leakage) and for no ≤1m signal in **any** configuration (48–54% across all families/metrics/scalers/weightings). A Type I catch, correctly made. A sensitivity gate is irrelevant to it |
| 2 | **Ensemble loses to a constant 50%** | **YES** | Brier Δ +0.052 to +0.114, **every CI excluding zero**. A *decisive* result. Nothing about power changes it |
| 3 | **Calibration failure (+18–26 pp overclaim)** | **YES** | Measured with CIs excluding zero at all six horizons. Definitive |
| 4 | **Weighting degeneracy (Spearman −1.000)** | **YES** | An algebraic identity of `se ≡ \|effect/z\|`. Has nothing to do with statistical power |
| 5 | **1-year edge is an artifact** | **YES** | Established by *robustness*, not power: drop-3 symbols → IC −0.002; leave-one-year-out collapse. Correct conclusion reached **despite** underpowering |
| 6 | **CPE rejected** | **YES** | Forced-scope ablation showed accuracy **decreased** as conditioning was added; confidence inverted. Substantive failures |
| 7 | **Short-horizon coin-flip** | **YES** | Reproduced three times independently. Also the theoretically expected result |
| 8 | Confidence-inversion non-replication | **NO** | +0.0667 [−0.0628, +0.2029] — genuinely unresolvable. A sensitivity gate would have refused to run it |
| 9 | Paired baseline directional accuracy | **NO** | All CIs ±0.05, 2–5× the MEMD. Would have been refused |
| 10 | RS-retirement "cannot determine" | **NO** | CI [−0.005, +0.039]. Would have been refused |
| 11 | σ_true / Norgate uncertainty | **NO** | Both are downstream of not knowing instrument sensitivity |

### Result: **necessary for 4 of 11 — and NOT necessary for the seven most decisive.**

Every finding this project reached with a CI excluding zero was reached **without** any Type II
machinery. The framework produced definitive answers whenever definitive answers were available. It
returned "cannot determine" only where effects were small or absent.

**H_A therefore fails the necessity test.** A constraint that is absent from the majority of a system's
failures — and from all of its most decisive ones — is not that system's root constraint.

---

## PART 3 — Sufficiency test

*Would solving only this materially increase the probability of project success?*

### Verdict: **it would only improve diagnosis.**

Measuring the MDE produces **a number**. That number:

- ✅ makes five historical nulls interpretable
- ✅ makes future studies rejectable before they run
- ✅ prices any data purchase exactly
- ❌ creates no signal
- ❌ fixes no calibration
- ❌ produces **not one** validated claim

In Theory-of-Constraints terms this is fatal to the framing: I identified a constraint on
**interpretation**, not on **production**. Elevating it raises the *quality of the project's knowledge
about its own state*, not its output of validated claims.

There is a real counter-argument — in a research program, justified belief *is* the product, so a
measurement you cannot interpret has zero throughput. I accept it partially. But it only holds if the
interpretations would **change**. If the sweep returns "you could have detected IC = 0.03 easily," then
every past null was a true negative, nothing is reinterpreted, and the gain is confidence in
conclusions already reached.

**Sufficiency is therefore conditional on the experiment's outcome** — which is an argument for running
the experiment, not for having identified the root constraint.

---

## PART 4 — Causal graph and where the proposed choke point sits

```
 [1] INFORMATION SET              price + macro + earnings-timing, US liquid equities, 1w-1y
        │                          ← predictability here is bounded by market efficiency
        ▼                            *** NOTHING DOWNSTREAM CAN EXCEED THIS BOUND ***
 [2] HISTORICAL DATA              survivor-only; breadth saturates (10x names = 7.8%)
        │
        ▼
 [3] FEATURES                     68, PIT-clean, embargo-hardened
        │
        ▼
 [4] SIGNALS (9 models)           all rejected or inconclusive
        │
        ▼
 [5] PROBABILITIES                se ≡ |effect/z| → +19pt overclaim; weight = (z/effect)²
        │
        ▼
 [6] ENSEMBLE                     dampens (0.81x); loses to constant 50%, CIs excluding zero
        │
        ▼
 [7] VALIDATION   ← ★ PROPOSED CHOKE POINT SITS HERE ★
        │            ten gates, all Type I; no sensitivity gate; MDE never measured
        ▼
 [8] INVESTMENT DECISIONS         5 phases, 0 promotions, recommendations oscillating
        │
        ▼
 [9] PRODUCT / USER VALUE         untested — nothing has ever reached it
```

### Can anything upstream dominate it? **Yes — node [1].**

Node [7] is a constraint on *measuring* what nodes [1]–[6] produce. **Node [1] bounds what they can
produce at all.** If the information set contains no extractable cross-sectional predictability above
IC ≈ 0.03, then no amount of measurement capability at [7] yields a validated claim, because there is
nothing to validate.

**A constraint at [7] cannot be the root when an unresolved constraint sits at [1].** The proposed
choke point is the deepest constraint yet identified — which is exactly what this review was convened
to distinguish from a root cause.

---

## PART 5 — Competing hypotheses

| ID | Hypothesis | Evidence for | Evidence against | P(true) | Effort to test | EV if confirmed |
|---|---|---|---|---|---|---|
| **A** | Validation framework is the root constraint | 10 gates verified all-Type-I; G8 discloses rather than requires; 3 of last 4 phases "cannot determine" | **Fails necessity (7 of 11)**; fails sufficiency; requires the untested hidden assumption that real effects were missed | **25%** | 50 h | Medium — reinterprets 5 nulls, prices future studies |
| **B** | Feature engineering cannot generate predictive information | Analogue RCA: no ≤1m signal in **any** configuration; CPE forced-scope ablation: accuracy *decreased* as conditioning was added | Collapses into C — the failure was not feature *selection* within the set, it was the set | 10% | 40 h | Low — points to the same place as C |
| **C** | **The prediction objective is statistically unrealistic for this information set and budget** | **Explains 11 of 11 observations** (see Part 6). Short-horizon efficiency reproduced 3× independently. Published cross-sectional IC for good single factors is 0.02–0.05 — the project set out to detect effects at the very edge of detectability with 31 names and 4 independent years. Breadth saturates. The 1y "edge" was concentration + era | Cannot be *proven* absent — absence of evidence. The 7-name panel is narrow | **65%** | 50 h (same experiment) | **Very high** — redefines the program or terminates it on evidence |
| **D** | Historical data is insufficient | Survivorship is real and untested | **Substantially refuted:** 5 of 11 failure mechanisms are data-invariant, incl. both causal ones; breadth saturates at 7.8% per 10× | 10% | ~60 h + $700 | Low |
| **E** | The product objective is incorrectly defined (value is explanatory, not predictive) | The reporting layer is elaborate, tested, and has **never been shown to a human** | Does not explain the ensemble, calibration, or weighting failures. It is a **response** to C, not a competitor | 30%* | 15 h + $300 | High — may reveal the actual product |
| **F** | The project has no stopping rule, so it cannot convert correct negatives into decisions | 5 phases of correct negatives followed by more building; recommendations oscillated across three reviews | Explains the *persistence* of failure, not its *origin*. A governance layer atop C | 40%* | ~0 h | Medium |

\* E and F are not mutually exclusive with C; they are compatible consequences of it.

---

## PART 6 — Which hypothesis explains the most, with the fewest assumptions?

| Observation | **H_A** (validation) | **H_C** (objective unrealistic) |
|---|---|---|
| Ensemble loses to constant 50% | ✗ (result was decisive) | ✓ nothing to combine |
| Calibration failure (+19 pts) | ✗ (decisive, CIs exclude zero) | ✓ models express confidence about an unpredictable target |
| Weighting degeneracy | ✗ (algebraic identity) | ✓ irrelevant because there is nothing to weight |
| Confidence non-replication | ✓ | ✓ no skill to be confident about |
| Analogue failure | ✗ (leakage + no signal in any config) | ✓ |
| CPE failure | ✗ (ablation showed conditioning *hurt*) | ✓ edge was era persistence |
| Short-horizon coin-flip | ✗ | ✓ the theoretically expected result |
| 1y artifact | ✗ (established by robustness) | ✓ |
| Repeated recommendation changes | partial | ✓ chasing a phantom produces oscillation |
| Norgate uncertainty | ✓ | ✓ cannot size a dataset for an effect that may not exist |
| σ_true uncertainty | ✓ | ✓ |
| **Total explained** | **4 of 11** | **11 of 11** |
| **Assumptions required** | 4 explicit + **4 hidden** + 3 untested | **1** |

### **H_C explains every observation with a single assumption. H_A explains four with eight.**

By any Bayesian or parsimony criterion, **H_C dominates**. The posterior strongly favours it.

### H_C, stated precisely enough to be falsifiable

> **H_C:** The cross-sectional forward-return predictability extractable from a price + macro +
> earnings-timing information set, at 1w–1y horizons on liquid US equities, is smaller than IC ≈ 0.03 —
> which is at or below the minimum detectable effect of **any configuration this project can afford**.
> The objective "statistically defensible decision support" is therefore unreachable **through
> prediction** at this budget.

Falsified by: any IC ≥ 0.03 that survives the existing gates.

---

## PART 7 — Falsifying the validation-framework hypothesis

### If H_A were NOT the true choke point, what would we expect to observe?

| Prediction if H_A is false | Actually observed? |
|---|---|
| Decisive results (CIs excluding zero) would appear whenever real effects were present | **YES** — Brier deltas, calibration overclaim, Spearman −1.000, the 1y artifact all resolved cleanly |
| "Cannot determine" would cluster on *small or absent* effects, not on large ones | **YES** — every inconclusive result concerns effects of ~0.01–0.02, right at the noise floor |
| Adding data/models/rigor would *not* increase validated-claim throughput | **YES** — 7→31 names, 7→9 models, embargo + PIT + pre-registration all added; throughput stayed at zero |
| Independent lines of evidence would converge on "no signal" for substantive, non-power reasons | **YES** — analogue (no signal in any config), CPE (conditioning *degrades*), shrinkage optimum λ = 0 with no interior optimum |
| The framework would successfully catch real errors when they occurred | **YES** — it caught its own leakage and withdrew its own headline result |

**Five predictions, five confirmations.** The observed history is exactly what one expects if the
validation framework is **working correctly** on a signal-free information set.

### The strongest argument that survives for H_A

**It is the constraint on LEARNING, not on SUCCEEDING.** The project cannot *establish* H_C without
measuring its own MDE — H_A's deficiency is precisely what prevents H_C from being confirmed or
refuted. So H_A is the **epistemic prerequisite** for resolving the root constraint, even though it is
not the root constraint.

That distinction is the correct resolution of this review, and it preserves the recommended action
while correcting the diagnosis.

---

## PART 8 — The decisive experiment

**Chosen: a STAGED POSITIVE CONTROL — inject a known signal at three points in the chain and find where
detection fails.**

It dominates every alternative because it is the **only** experiment that separates H_A from H_C, it
requires no new data, no vendor, no VM, and no variance-model assumption (the analytical route — σ_true
estimation — has already failed twice by producing wrong answers).

### Design

| Arm | Injection point | Measures |
|---|---|---|
| **1** | Synthetic IC added to the **score stream**, upstream of the validation path | MDE of the **validation layer alone** |
| **2** | Synthetic feature correlated with forward returns at known strength, run through a model + combiner | MDE of the **full downstream chain** |
| **3** | A documented real anomaly (12-1 momentum) implemented as a feature, run end-to-end | Whether a **real** effect of literature size survives the whole pipeline |

**Arm 2 MDE − Arm 1 MDE = signal destroyed by the model/probability/combiner layer.** That difference
has never been measured and is directly actionable.

- **Inputs:** existing captured panel; sweep injected IC ∈ {0.01, 0.02, 0.03, 0.05, 0.10, 0.15} ×
  breadth ∈ {7, 31, 100, 500} × years ∈ {4, 8, 15, 20} × 6 horizons; ≥ 200 seeds per cell.
- **Outputs:** detection rate at 80% and 90% power per configuration; the MDE surface; the Arm-2−Arm-1
  gap.

### Decision thresholds

| Result | Interpretation | Action |
|---|---|---|
| **Arm 1 MDE ≤ 0.03 on the current panel** | Validation layer is adequate. **H_A REJECTED.** Every past null is a true negative | Stop prediction research; pivot to H_E (product) |
| **Arm 1 MDE > 0.05** | Validation layer is blind. **H_A supported** | Fix the gate; re-run all five historical studies |
| **Arm 2 MDE ≫ Arm 1 MDE** | The model/combiner layer destroys signal — a **new** finding, and the first actionable defect with a real payoff | Repair the `se ≡ \|effect/z\|` recipe before anything else |
| **Arms 1 & 2 pass, Arm 3 fails** | The instrument works; the information set is empty. **H_C CONFIRMED** | Terminate prediction research on evidence |
| **No configuration detects IC = 0.03** | Unreachable at any affordable budget. **H_C CONFIRMED, strongest form** | Terminate; redefine the objective |

---

## PART 9 — The constraint hierarchy after the experiment

**If it succeeds** (instrument shown adequate, Arm 3 fails):
1. **The information set (H_C)** — is there predictability at all?
2. **Product definition (H_E)** — is the value explanatory rather than predictive? *(untested, 15 h)*
3. **Stopping rule (H_F)** — can the project convert correct negatives into decisions?

**If it fails** (instrument shown blind):
1. **Is the blindness fixable by data (breadth/years) or by method (the `se` recipe)?** — Arm 2 − Arm 1
   answers this directly
2. **The information set (H_C)** — reachable only after the instrument is repaired
3. **Product definition (H_E)**

**Both paths converge on H_C within two levels, and on H_E within three.** That convergence is itself
evidence that H_C is the root: whichever way the experiment resolves, the project arrives at the same
question.

---

## PART 10 — Formal scientific verdict

### 1. Is the proposed choke point truly the root constraint?

**No.** It is the deepest constraint identified so far — which is precisely the distinction this review
was convened to make. It sits at node [7] of the causal graph while an unresolved constraint sits at
node [1], and a constraint on measurement cannot be root when a constraint on the measurand is open.

### 2. Is it necessary?

**No.** Seven of eleven historical failures — including all of the most decisive — would have occurred
unchanged. Every result the project reached with a CI excluding zero was reached without any Type II
machinery.

### 3. Is it sufficient?

**No.** Solving it **only improves diagnosis.** It creates no signal, fixes no calibration, and produces
no validated claim. Its sufficiency is conditional on its own outcome.

### 4. If not, what is the true root constraint?

> **The prediction objective is statistically unrealistic for this information set at this budget.**
> Extractable cross-sectional predictability from price + macro at 1w–1y horizons appears to be smaller
> than IC ≈ 0.03, at or below the MDE of any affordable configuration. It explains **11 of 11**
> observations with **one** assumption, against the validation hypothesis's 4 of 11 with eight.

### 5. Highest-EVI experiment?

The **staged positive control** (Part 8). It is the only experiment that separates H_A from H_C, it
needs no data purchase, and it is robust to which hypothesis is correct.

### 6. What should the next 100 hours accomplish?

| Hours | Work |
|---|---|
| 20 | Restore the platform to runnable; automate backups; verify the rebuild reproduces archived captures byte-for-byte |
| 40 | Build and run the three-arm staged positive control |
| 15 | Re-interpret all five historical results against the measured MDE surface |
| 15 | **Test H_E in parallel** — show the existing reports to three people and record what they did differently. It is the leading hypothesis in *both* branches of Part 9, it needs no instrument, and it is the only untested value hypothesis in the project |
| 5 | Codify a sensitivity gate (G11) so underpowered and null stop sharing a disposition |
| 5 | Contingency |

*(This restores the human-evaluation hours the TOC memo cut. That cut followed from a diagnosis this
review has now rejected: under H_C, product definition is the next constraint on both branches, so
testing it early is correct rather than a local optimum.)*

### 7. Should any money be spent before the experiment?

**No — with one exception: ~$120 for automated offsite backup.** The project has already permanently
lost a PIT fundamentals snapshot and its prediction archive. Everything else — Norgate, Parallels,
Windows, any vendor — waits. **$0 to data.**

### 8. If this were my own project, what would I do next?

Restore the database and turn on backups. Then write the injection harness and find the effect size at
which the platform stops seeing a signal I put there myself. While that runs, show three people the
institutional reports and write down what they actually did differently. Then read the number and the
notes together, and decide whether this is a prediction project or an explanation project.

I would not buy data. I would not install Parallels. I would not write another model.

---

## Confidence statement

> **Confidence that the proposed choke point (the validation framework) is the project's root
> constraint: 25%.**
>
> **Confidence that H_C — the prediction objective is unrealistic at this budget — is the root
> constraint: 65%.**

### Why this is below 90%, and exactly what evidence is missing

**One measurement is missing: the pipeline's minimum detectable effect.** Until it exists:

1. **H_C cannot be confirmed** — "no signal found" is not the same as "no signal exists," and that is
   precisely the ambiguity H_A names. H_C's 65% rests on convergent circumstantial evidence
   (independent failures for substantive non-power reasons, λ = 0 with no interior optimum, three
   independent reproductions of short-horizon efficiency), **not** on a direct test.
2. **H_A cannot be fully rejected** — its 25% is not zero, because if Arm 1 returns an MDE above 0.05 it
   becomes the operative blocker on learning, even while remaining downstream of H_C.
3. **The Arm-2 − Arm-1 gap has never been measured.** If the model/combiner layer is destroying signal
   the features carry, a **new** hypothesis enters at meaningful probability and both current numbers
   move.

**No amount of further reasoning closes this gap.** Three consecutive analyses — including two of my own
— have attempted to settle it analytically, and two produced arithmetically wrong answers. The
remaining uncertainty is not a reasoning deficit; it is a **missing measurement**, and it is 40 hours
and $0 away.

**Recommendation to the board: do not authorise a platform redesign on the current evidence.** Authorise
the 100 hours in §6. The measurement they produce is what a redesign decision requires, and it is the
same experiment under either hypothesis — which is the strongest practical argument for running it
before spending anything else.
