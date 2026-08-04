# Independent Scientific Review — Does Arm 1 Change the Optimal Roadmap?

**Board review, 2026-08-01.** Arm 1's measured results are accepted as established evidence.
No re-run, no redesign, no product discussion. Only conclusions that logically follow from Arm 1 are
updated.

---

## PART 1 — Reassessment of the program

### STRENGTHENED

| Conclusion | Why Arm 1 strengthens it |
|---|---|
| **The validation framework is a genuine asset** | Measured unbiased (max \|bias\| 0.017) and efficient to within **2.3% of the theoretical `1/√n` bound**. This is the strongest quantitative vindication the framework has received in the project's history |
| **The binding constraint is sample size, not machinery** | `SE = 0.977/√n`, residual 0.0006 across n = 141→1,264. Information loss is essentially entirely the sample, not the pipeline |
| **Prior studies were underpowered** | Previously argued from an analytic formula; now **measured**. At 1m (n = 421) the detection floor is IC 0.15 against effects of interest at 0.03–0.05 |
| **Block-bootstrap uncertainty is honest at adequate n** | FP rates 2.0–3.5% against a nominal 5% at 1w–3m — conservative, not permissive |

### WEAKENED

| Conclusion | Why |
|---|---|
| **"The ensemble contains no exploitable signal"** | Substantially weakened **as evidence of absence**. The measured MDE at every horizon exceeds the effect sizes sought by 3–13×. A real IC of 0.03–0.05 would have been invisible at every horizon tested |
| **"Four research phases returned negative results"** | Those phases returned *uninterpretable* results. Arm 1 shows the detection floor sat above the search target throughout |
| **H_C in its strongest form — "unreachable at any affordable budget"** | The measured scaling implies ~12,600 cells for MDE ≤ 0.03. A 500-name × 20-year panel exceeds that comfortably. **The "MDE too high to ever work" branch of H_C is weakened** |

### DISPROVEN

| Claim | Disproving evidence |
|---|---|
| **"The instrument may be blind"** | Recovery is monotone at all six horizons, reaching 90–91% at IC 0.10 (1w/2w) and 91.5–100% at IC 0.40. **The layer sees signal when signal is present.** Ruled out at this scale |
| **The analytic MDE formula `2.486 × SE`** | Understates the measured MDE at **every** horizon; ratio 1.28–1.60, mean **1.43**. Empirically MDE ≈ **3.44 × SE**. Every prior power calculation in this project using it was optimistic by ~40% |
| **The TOC diagnosis that the validation framework is *defective*** | Partially disproven. The framework lacked a *sensitivity measurement* — a real process gap, now closed — but the **machinery itself is sound and near-optimal**. The constraint is n, not the framework |

### NEWLY SUPPORTED

| Finding | Evidence |
|---|---|
| **The required dataset size is now a measured quantity** | `MDE ≈ 3.36/√n` ⇒ ~12,600 cells for MDE ≤ 0.03 *(extrapolation, labelled)* |
| **The bootstrap degrades at very small n** | FP 9.5% vs nominal 5% at n = 47 (1y). Long-horizon conclusions from this panel carry ~2× the nominal false-positive risk |
| **Detection is horizon-ordered by n alone** | MDE 0.10 / 0.10 / 0.15 / 0.25 / 0.30 / 0.40 tracks n = 1264 / 1264 / 421 / 180 / 94 / 47 exactly as `1/√n` predicts. **No horizon-specific pathology** |

### STILL UNKNOWN

1. Whether any real signal exists — Arm 1 injected synthetic signal and says nothing about this.
2. **Whether the model and combiner layers destroy signal** — Arm 1 injected *downstream* of them.
3. Whether `SE = 0.977/√n` holds at 100–500 symbols (block structure untested at breadth).
4. Whether a realistic (autocorrelated, fat-tailed) signal is as detectable as an i.i.d. Gaussian one.
5. Whether the calibration defects documented elsewhere affect anything measurable.

---

## PART 2 — Remaining uncertainties, ranked by EVI

| Rank | Uncertainty | Why it matters now | Cost | P(changes direction) | EVI |
|---|---|---|---|---|---|
| **1** | **Model/combiner information loss** | Arm 1 cleared the validation layer. **The layer immediately upstream is where every measured defect in this project lives** — `se ≡ \|effect/z\|`, Spearman(\|effect\|, weight) = −1.000, the +18–26 pp overclaim. If it destroys signal, no dataset repairs it and the fix is free | **~1 day, $0 — executable today** | **~45%** | **HIGHEST** |
| **2** | Feature→model loss | The other half of the Arm 2 gap. Unmeasured | 1 wk + data restore | ~30% | High |
| **3** | Scaling validity at breadth | Determines whether the ~12,600-cell extrapolation holds. Gates the purchase decision | 1 wk + data restore | ~25% | High |
| **4** | True signal existence | The ultimate question — but unanswerable until 1–3 are resolved and clean data exists | months + $ | ~35% | High ceiling, gated |
| **5** | Descriptive reliability (V5) | Independent track; required for G4 | 8 wk, $0 | ~20% | Medium — unchanged by Arm 1 |
| **6** | Realistic vs synthetic signal detectability | Arm 1's injection is i.i.d. Gaussian; real signal may be harder | ~2 days | ~15% | Medium |
| **7** | Small-n bootstrap degradation | Measured (9.5% FP at n = 47). Consequence understood; affects interpretation of past 1y results only | 0 — already known | ~5% | Low |
| **8** | Survivorship bias magnitude | Unchanged by Arm 1. Still requires clean data by definition | $ + months | ~20% | Gated |
| **9** | Horizon dependence | **Resolved by Arm 1** — horizon ordering is fully explained by n | — | ~0% | **None remaining** |

**Arm 1 promoted #1 from "one of several concerns" to the single largest actionable uncertainty**, by
eliminating the layer beneath it.

---

## PART 3 — Should Arm 2 still be next?

# No. A narrower experiment now dominates it, and it is executable today.

### The argument

Arm 1 measured the pipeline **downstream of the score**. Arm 2 as specified measures everything from
the **feature** down. But the total loss decomposes:

```
Arm 2 loss  =  (feature → model loss)  +  (model → combiner → score loss)
```

**The second term is separately measurable on surviving artifacts, today, with no data restoration.**

The captures contain per-model `(effect, z_raw, score, confidence, neutral, n_eff)` for 7 models ×
7 symbols × 189 dates × 6 horizons — **62,100 rows, 44,052 non-neutral with both effect and z, and
every field `combine_rows` requires is present (verified).** The production combiner was previously
replicated on these exact artifacts to **2.84 × 10⁻¹⁴**.

So a **combiner-level injection** is possible: perturb the per-model effect streams to carry a known
IC, run them through the **real production combiner**, and measure how much of that IC survives into
the combined score.

### Why this dominates Arm 2 right now

| Criterion | Combiner injection | Arm 2 (feature-level) |
|---|---|---|
| Executable today | ✅ **Yes** | ❌ Blocked on ~12–15 h data restoration |
| Targets a layer with **known measured defects** | ✅ `se ≡ \|effect/z\|`, Spearman −1.000, +19 pt overclaim all live here | Partially |
| Decomposes Arm 2's future result in advance | ✅ Isolates one of the two terms | ❌ Returns only the sum |
| Cost | ~1 day, $0 | ~1 week + restoration |
| Actionable on a negative | ✅ **Repair is free and precedes any purchase** | Same, but later |

**If the combiner destroys signal, that is the highest-value finding available anywhere in the
programme** — it would mean the aggregation must be repaired *before* any data is bought, and the
repair costs nothing. **If it does not, Arm 2's eventual measurement cleanly isolates the
feature→model term.** Either outcome is strictly informative.

### Alternatives considered and rejected

| Alternative | Rejected because |
|---|---|
| **Arm 2 now** | Blocked on data restoration; returns a sum where a component is separately available |
| **Arm 3 (12-1 momentum)** | Blocked on data — needs ≥13 months of prices per symbol |
| **Empirical scaling at breadth** | Only 7 symbols have outcomes. The 31-symbol capture has **no outcomes** (prices destroyed). Blocked on the same restoration |
| **Larger panel replication** | Same blocker |
| **Descriptive reliability (V5)** | Genuinely valuable and independently gated (G3/G4), but **orthogonal** — Arm 1 changed nothing about its priority. Should run in parallel, not instead |
| **Restoration of lost research** | Necessary and already scheduled; it is a prerequisite, not an experiment |

**Recommended order: combiner injection (now) → data restoration → Arm 2 → Arm 3.**
V5 proceeds in parallel throughout, unchanged.

---

## PART 4 — Gate review

**Only changes with direct Arm 1 evidence are proposed.**

| Gate | Change | Justification |
|---|---|---|
| **G1** Phase 1 | **No change** | Arm 1 provides no evidence about product validation |
| **G2** V4 authorization | **No change** | No evidence bearing on it |
| **G3** CONTEXT | **No change** | Descriptive reliability untouched by Arm 1 |
| **G4** ADVISORY | **No change** | Same |
| **G5** MDE / sensitivity | **AMENDMENT — evidentiary, not threshold** | See below |
| **G6** Purchase | **No change to conditions.** Condition C3's *content* is affected | See below |
| **G7** DIRECTIONAL | **No change** | No evidence bearing on it |

### G5 — proposed amendment (definitional, not a threshold change)

**Threshold unchanged: MDE ≤ 0.03 at an attainable configuration.** Arm 1 provides no evidence about
what effect size is economically meaningful, so the 0.03 stands.

**Two evidentiary amendments follow directly from Arm 1:**

1. **The analytic `2.486 × SE` estimator is prohibited for G5 determination.** Arm 1 measured it
   optimistic by 1.28–1.60× at every horizon. **MDE must be established by measured recovery
   probability, never by formula.** This is direct Arm 1 evidence.
2. **The Arm 2 − Arm 1 gap requirement is already in G5 and is retained**, with the ordering clarified:
   the combiner slice may be measured first and reported separately.

**Ordering within G5 changes; the gate sequence G1→G7 does not.**

### G6 — effect on the Norgate justification

**Stronger — in one specific, measured respect.**

Arm 1 **removes "the instrument might be blind" as a reason to withhold the purchase.** The layer is
unbiased, efficient to within 2.3% of theory, and the measured scaling implies the required n is
comfortably inside a 500-name × 20-year panel.

**But condition C3 — "survivorship is the *remaining* blocker" — is now demonstrably NOT satisfied**,
and Arm 1 is why: the layer immediately upstream of the score has never been tested, and it carries
three separately measured defects. **A cheaper blocker plausibly remains.** C3 cannot be signed until
the combiner question is answered.

**Net: the case for eventual purchase is stronger; the case for purchasing now is unchanged and
remains negative.**

---

## PART 5 — Preregistration

Arm 2 is **not** the highest-value next experiment (Part 3), so the preregistration below covers the
experiment that is. **Arm 2's preregistration follows after data restoration, unchanged in design.**

# ARM 1.5 — COMBINER-LEVEL INJECTION · PREREGISTRATION

**Frozen before implementation. No threshold may be altered after results are seen.**

### Hypothesis

> **H1:** A known cross-sectional IC injected into the per-model effect streams survives passage
> through the production combiner into the combined score with information loss below the
> preregistered tolerance.

### Null hypothesis

> **H0:** The combiner destroys a material fraction of injected signal — measured recovery of the
> combined score is materially below the recovery of the injected per-model streams.

### Injected signal

```
For each model m and cell i:
    effect_m,i(ρ)  =  effect_m,i  +  κ_m · ρ · Φ⁻¹(rank(y_i))
    z_raw_m,i(ρ)   =  effect_m,i(ρ) / se_m,i        [se held at its ORIGINAL recovered value]
```

- `κ_m` scales the injection to each model's own effect dispersion, so no model is privileged.
- **`se` is held fixed at its original value.** Recomputing it would re-derive `se ≡ |effect/z|` and
  circularly erase the defect under test.
- ρ ∈ {0.00, 0.03, 0.05, 0.07, 0.10, 0.15, 0.20}. **Realized outcomes are never modified.**
- Seeds deterministic, ≥200 per cell. Reproducibility verified across two `PYTHONHASHSEED` values.

### Injection location

**At the per-model evidence stream**, upstream of `combine_model_evidence` and downstream of the
models. This isolates the aggregation layer exactly.

### Information-loss measurement — the primary endpoint

```
LOSS(ρ)  =  IC_recovered(per-model consensus)  −  IC_recovered(combined score)
```
where the per-model consensus is the equal-weight mean of injected model scores — the natural
reference for "what the combiner had available."

**Primary endpoint: `LOSS` at ρ = 0.10, with a block-bootstrap CI.**

### Secondary endpoints

1. MDE(80%) of the combined score, per horizon — comparable to Arm 1's score-level MDE.
2. Recovery probability curves, combined vs consensus.
3. Weight concentration (HHI of `weight_share`) under injection — does injection shift weights?
4. Whether the **inverse-effect-size weighting** (Spearman(|effect|, weight) = −1.000) systematically
   down-weights the injected models.
5. False-positive rate at ρ = 0.00.

### Success criteria

> **PASS (combiner is not the bottleneck):** `LOSS` CI upper bound < **0.02 IC** at ρ = 0.10,
> **and** combined-score MDE ≤ 1.25 × Arm 1's score-level MDE at the matched horizon.

### Failure criteria

> **FAIL (combiner destroys signal):** `LOSS` CI lower bound > **0.02 IC** at ρ = 0.10,
> **or** combined-score MDE > 2 × Arm 1's score-level MDE at the matched horizon.

### Stopping rules

- Stop and report if the false-positive rate at ρ = 0.00 exceeds **0.10** — the harness is invalid.
- Stop if combiner replication drifts from the previously established 2.84 × 10⁻¹⁴ — the reference
  implementation has changed.
- No adaptive stopping on the primary endpoint. The full ρ grid runs regardless of interim results.

### Interpretation rules — fixed in advance

| Result | Interpretation | Consequence |
|---|---|---|
| **PASS** | The combiner is not the bottleneck | Arm 2's eventual gap is attributable to feature→model. G6 condition C3 becomes assessable |
| **FAIL** | **The combiner destroys signal** | **Repair the aggregation before any data purchase.** C3 cannot be satisfied. This is the highest-value negative available |
| LOSS CI straddles 0.02 | Inconclusive at this n | Report as inconclusive. **Do not reinterpret as PASS** |
| Secondary 4 confirms injected models are down-weighted | Mechanism identified | The `se ≡ \|effect/z\|` defect has a measured consequence, elevating its repair priority |

**Anti-reinterpretation clause:** the primary endpoint is `LOSS` at ρ = 0.10 with its CI. No secondary
endpoint may be substituted for it. An inconclusive primary is reported as inconclusive.

---

## PART 6 — Funding review

### Has Arm 1 materially increased confidence in the project?

**Yes — in the apparatus, not in the hypothesis.**

Arm 1 established that the measurement instrument is unbiased and near-theoretically-efficient. That is
a real and uncommon result; most research programmes never measure their own detection limit at all.
**It increases confidence that a future positive result would be trustworthy.**

It increased confidence in the *existence of signal* by **zero** — it injected synthetic signal and was
designed to say nothing about real signal. Any read of Arm 1 as encouraging about the hypothesis is a
misread.

### Should the program continue exactly as planned?

**Almost. One reordering, no structural change.** Gates, thresholds and the V5 track are unchanged.
The single change is inserting the combiner-injection slice ahead of Arm 2, on grounds of executability
and target value.

### Should the ordering of experiments change?

**Yes — one insertion.** Combiner injection now → restoration → Arm 2 → Arm 3. V5 unchanged and
parallel.

### Has the justification for eventually purchasing survivorship-free data become stronger, weaker, or unchanged?

**Stronger for eventual purchase. Unchanged for purchase now.**

- **Stronger:** the "blind instrument" objection is removed by measurement, and the required n is now
  known to be attainable.
- **Unchanged for now:** G6 condition C3 requires survivorship to be the *remaining* blocker. Arm 1
  **identified a cheaper untested blocker upstream**. C3 is further from satisfaction today than it
  appeared yesterday — not because the data case weakened, but because a cheaper alternative
  explanation was surfaced and is now testable for $0.

---

## PART 7 — Final verdict

### 1 · The single largest scientific uncertainty

> **Whether the model and combiner layers destroy signal before it reaches the validation layer.**
>
> Arm 1 cleared everything downstream of the score. The layer immediately upstream carries three
> separately measured defects — `se ≡ |effect/z|`, a perfect inverse-effect-size weighting inversion
> (Spearman −1.000), and an 18–26 pp overclaim. **It has never been tested for information loss.**

### 2 · The single highest-value next experiment

> **Combiner-level injection (Arm 1.5)** — inject a known IC into the per-model effect streams, pass it
> through the real production combiner, and measure how much survives.
>
> **~1 day, $0, executable today on verified surviving artifacts.**

### 3 · Why it is superior to every alternative

1. **It is the only high-value experiment executable today.** Arm 2, Arm 3, breadth-scaling and larger
   panels are all blocked on ~12–15 h of data restoration.
2. **It targets the layer with the highest prior probability of defect** — the only layer in the system
   with three independently measured pathologies.
3. **It decomposes Arm 2 in advance.** Arm 2 returns a sum; this returns one of its two terms, making
   Arm 2's eventual result interpretable rather than ambiguous.
4. **A negative result is free to act on and changes the purchase decision.** If the combiner destroys
   signal, the repair costs nothing and must precede any data spend — and G6 condition C3 cannot be
   signed until this is known either way.
5. **Feasibility is verified, not assumed:** 62,100 per-model rows, 44,052 non-neutral with both effect
   and z, every required field present, and the combiner previously replicated on these exact artifacts
   to 2.84 × 10⁻¹⁴.

### 4 · The result that would most change the project's direction

> **A measured combiner LOSS with a CI lower bound above 0.02 IC.**
>
> That would establish that signal is destroyed between the models and the score — meaning **no dataset,
> at any price, repairs the platform until the aggregation is fixed.** It would halt the purchase track
> immediately, redirect engineering to a free repair, and retroactively explain every null result in
> the project's history through a mechanism entirely inside the repository.
>
> The symmetric result — LOSS CI upper bound below 0.02 — would clear the aggregation layer, leave the
> feature→model term as the last untested link, and make G6 condition C3 assessable for the first time.
>
> **Both outcomes are decisive. Neither requires a dollar.**
