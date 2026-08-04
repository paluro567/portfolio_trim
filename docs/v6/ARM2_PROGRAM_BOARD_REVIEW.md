# Independent Scientific Program Board — Is the Program Justified in Proceeding to Arm 2?

**Board review, 2026-08-01.** Evidence base: the original research program, Arm 1, Arm 1.5, and all
prior scientific reviews. No new experiment executed. Every classification below is tied to a completed
measurement.

---

## PART 1 — Pipeline decomposition: what has actually been measured

| # | Stage | Classification | Why this classification follows |
|---|---|---|---|
| **1** | **Feature generation** | **COMPLETELY UNMEASURED** | No experiment has injected at, or measured across, the feature layer. Arm 1 injected at the score; Arm 1.5 at the per-model effect. Both are downstream. No completed experiment touches feature computation |
| **2** | **Model fitting** (features → effect, z) | **COMPLETELY UNMEASURED for information transmission** · indirectly bounded on output | Arm 1.5 injected **at the model output**, bypassing the models entirely. No measurement of what the models do to information. *Indirect bound only:* on real data all 7 models produce near-zero IC (real-score IC −0.183 to +0.013 across horizons, Arm 1) — that bounds output **quality**, not transmission **loss** |
| **3** | **Calibration** (z → score → probability) | **EXPERIMENTALLY FALSIFIED** | Measured implied accuracy 0.694–0.722 vs realized 0.455–0.514 — an **+18 to +26 pp overclaim at all six horizons**. Brier worse than a constant 50% at all six, every CI excluding zero. Shrinkage sweep monotone with optimum λ = 0, no interior optimum. This is definitive, not suggestive |
| **4** | **Confidence estimation** | **EXPERIMENTALLY BOUNDED — inconclusive** | Top-vs-bottom quartile accuracy gap +0.0667, CI [−0.0628, +0.2029]; sign flips across horizons; Spearman(confidence, hit) ≈ 0 everywhere. The prior CPE inversion **did not replicate**. Bounded to a wide interval containing zero; neither validated nor falsified |
| **5** | **Combiner** (per-model evidence → combined score) | **EXPERIMENTALLY BOUNDED — not validated** | Arm 1.5: LOSS vs equal-weight consensus at ρ = 0.10 gives **0 FAIL, 2 PASS, 4 INCONCLUSIVE**; at 1w the CI lies entirely below zero (combiner *beat* consensus). LOSS does not scale with injected signal (slopes −0.031, −0.036, −0.071 at the three best-powered horizons). **Bounded relative to equal-weight — see Part 4 for why this is not validation** |
| **6** | **Validation layer** (cohort → IC → bootstrap → CI) | **EXPERIMENTALLY VALIDATED** | Arm 1: recovery monotone at all six horizons; estimator unbiased (max \|bias\| 0.017); **SE = 0.977/√n with max residual 0.0006** — within 2.3% of the theoretical bound; FP 2.0–3.5% against nominal 5% at 1w–3m. The only stage that meets a validation standard |

### Two stages carry qualifications the board requires be stated

**Stage 5 is bounded, not validated.** Arm 1.5's endpoint was `IC(equal-weight consensus) − IC(combined)`
— a **relative** comparison between two aggregations of the *same* injected inputs. It cannot detect a
loss that both paths incur identically.

**Stage 6's validation is scale-limited.** Arm 1 measured 3–7 symbols, n ≤ 1,264. The block bootstrap
blocks on symbols; behaviour at 100+ symbols is unmeasured. FP inflated to 9.5% at n = 47.

---

## PART 2 — Does Arm 2 have a unique purpose?

**Yes — it is the only completed-evidence-justified experiment that addresses stages 1 and 2, which are
the only two stages classified COMPLETELY UNMEASURED.**

### Alternatives considered

| Alternative | EVI vs Arm 2 | Disposition |
|---|---|---|
| **Arm 3 — 12-1 momentum end-to-end** | **Lower, on interpretability** | Tests a *real* documented effect through the whole pipeline. But if it fails, the result is confounded: 12-1 momentum famously underperformed in 2020–2021, inside the panel window. **A negative result cannot distinguish "pipeline lost it" from "the effect was absent in this era."** Arm 2's injected signal carries no such confound. **Arm 3 remains valuable and should follow Arm 2, not precede it** |
| **Absolute-loss measurement of the combiner** | **Higher per hour, but not a separate experiment** | Would close the Part 4 gap. **Folded into Arm 2 as a mandatory checkpoint** (Part 5), not run standalone — Arm 2 must measure per-model output IC anyway to interpret its own result |
| **Descriptive reliability (V5)** | **Not comparable** | Independent track, separately gated (G3/G4). Arm 1/1.5 changed nothing about its priority. Runs in parallel; does not compete |
| **Larger-panel replication of Arm 1** | Lower | Would test the scaling extrapolation, but the 31-symbol capture **has no outcomes** (prices destroyed). Blocked on the same restoration as Arm 2, and addresses a *bounded* stage rather than an *unmeasured* one |
| **Re-running Arm 1.5 at more horizons/ρ** | Lower | 4 of 6 horizons were INCONCLUSIVE **because n ≤ 419**, not because the grid was too coarse. More ρ values cannot fix a sample-size limit |
| **Calibration repair experiment** | Not an experiment | Stage 3 is already **falsified**. Repair is engineering, not measurement. No EVI |

**No alternative addresses an unmeasured stage. Arm 2 is unique in that respect.**

---

## PART 3 — Attacking Arm 2

The board attempted to prove Arm 2 unnecessary. **It failed to do so, but surfaced one objection
serious enough to change Arm 2's design requirements.**

### Objection 1 — the injected feature may not propagate *(SERIOUS)*

The models do not consume features linearly. `momentum_exhaustion` uses **own-percentile thresholds over
≥252 observations** and activates on discrete conditions. `sector_rotation` and `relative_strength` use
percentile deciles.

**Perturbing a feature to carry IC ρ does not guarantee the model's *output* carries ρ.** Threshold
logic can saturate, activation can change, and a model can go neutral. The injected signal may be
attenuated or destroyed **by the injection mechanism itself** rather than by the pipeline under test.

**This is the strongest objection and it is not hypothetical** — it follows directly from the documented
model designs.

### Objection 2 — dilution across models *(MODERATE)*

Injecting into one feature affects only the models consuming it. With ~4.9 active models per cell
(measured, Arm 1.5), the aggregate injection strength becomes an unmeasured function of feature
coverage. Effective ρ at the combined score is not the nominal ρ.

### Objection 3 — interpretation ambiguity *(SERIOUS, and it follows from 1 and 2)*

If Arm 2 measures large loss, three explanations are indistinguishable without further measurement:
**(a)** the feature→model transformation genuinely destroys information; **(b)** the injection failed to
propagate; **(c)** dilution reduced the effective signal. **A negative Arm 2 result would be
uninterpretable as specified.**

### Objection 4 — computational feasibility *(MODERATE)*

Arm 1.5 ran in 24 s because the combiner is arithmetic. Arm 2 must execute the **real models**, which
issue per-symbol database queries; documented full-universe passes take 5–7 minutes for 52 symbols.
A ρ × seed sweep over 7 symbols × 189 dates × 6 horizons is orders of magnitude more work.
**Unquantified, and the V6 readiness assessment already classified the sweep harness as major work.**

### Objection 5 — the models are deterministic *(MINOR)*

Given fixed features, model outputs are deterministic — as Arm 1.5's injection also was. Monte Carlo
variation requires a noise term in the injected feature. Resolvable in specification.

### Are these objections sufficient to delay Arm 2?

**No — but objections 1 and 3 are sufficient to require one addition before Arm 2 may begin.**

> **Mandatory propagation checkpoint.** Arm 2 must measure the IC present in the **per-model effect
> streams after the models run**, and compare it to the injected feature IC.
>
> This single measurement resolves objections 1, 2 and 3 — it separates *transmission* loss from
> *injection* failure — **and it simultaneously closes the Part 4 gap left by Arm 1.5**, because
> per-model output IC is exactly the missing reference point for absolute combiner loss.

**Delay is not warranted. A design precondition is.**

---

## PART 4 — Verifying the chain of inference

### The claimed chain

```
Validation layer  →  validated (Arm 1)
        ↓
Combiner          →  no distinguishable loss (Arm 1.5)
        ↓
∴ remaining uncertainty is Feature → Model
```

### The chain does not fully close. Here is exactly where.

**Arm 1.5's endpoint is relative, not absolute.** It measured
`IC(equal-weight consensus) − IC(combined)` — both computed from the **same** injected per-model
streams. A loss incurred *identically by both paths* is invisible to this metric.

**What the board can verify from completed outputs:** at ρ = 0.10 the per-model injected IC is
≈ ρ/√(1+ρ²) = **0.0995**. Measured:

| Horizon | IC consensus | IC combined | Both above per-model level? |
|---|---|---|---|
| 1w | +0.2626 | +0.2841 | **Yes** |
| 2w | +0.2524 | +0.2541 | **Yes** |
| 1m | +0.2222 | +0.2061 | **Yes** |
| 3m | +0.1661 | +0.1647 | **Yes** |
| 6m | +0.0670 | +0.0889 | No — consensus below |
| 1y | +0.1505 | +0.1167 | **Yes** |

**Aggregation amplifies per-model IC in both paths at five of six horizons.** That bounds the loss:
neither path is destroying signal *below the level supplied to it*.

**But the achievable ceiling was never measured.** Optimal aggregation of k correlated estimates of a
common signal has a theoretical maximum that Arm 1.5 did not compute. Both paths could sit equally far
below it.

### Corrected statement of the chain

> The remaining uncertainty is isolated to **{Feature → Model} ∪ {common-mode aggregation loss}.**
>
> The second term is **bounded** — both paths amplify rather than attenuate, and the combined score
> clears Arm 1's detection floor at 1w, 2w and 1m — but it is **not measured**.

**The break is small and quantified, not fatal.** It is closed by the same propagation checkpoint
Part 3 already requires, which is why the board does not treat it as a separate work item.

---

## PART 5 — Arm 2 readiness review

| Domain | Status | Blocker |
|---|---|---|
| **Prerequisites — data** | ❌ **BLOCKED** | `daily_prices`, `macro_observations`, `feature_store_daily` all empty. Models cannot execute. **~12–15 h restoration (class B)** |
| **Prerequisites — schema** | ✅ Ready | 11-migration chain verified INTACT; rebuilds to 86 tables |
| **Repository state** | ⚠️ Partial | Models, feature pipeline and validation harness present and tested (782 test functions). **No feature-injection hook exists** — V6 readiness classified this "major work" |
| **Data dependencies** | ❌ Blocked | Reconstructed prices/macro are **class B (approximate)** — vendor-revised, not vintage-identical. Acceptable for Arm 2 (injected signal is controlled) but must be recorded as a new study, not a reproduction |
| **Statistical assumptions** | ⚠️ Needs specification | Injection must include a noise term for Monte Carlo (objection 5). Effective ρ at the combined score is unknown a priori (objection 2) — **the propagation checkpoint measures it rather than assuming it** |
| **Computational assumptions** | ❌ **UNQUANTIFIED** | Models issue per-symbol DB queries; documented 5–7 min per 52-symbol pass. Sweep cost never estimated. **Must be benchmarked before the full sweep is authorised** |
| **Stopping criteria** | ❌ Not written | Arm 2 has **no preregistration**. Arm 1.5's was written in the review that authorised it; Arm 2's does not exist |
| **Reproducibility** | ⚠️ Achievable | Arm 1 and 1.5 both established deterministic-seed patterns and cross-`PYTHONHASHSEED` verification. Precedent exists; must be applied |

### Remaining blockers, ranked

1. **Research data restoration** — hard prerequisite, ~12–15 h *(already authorised under the V4 boundary as disaster recovery)*
2. **Arm 2 preregistration** — does not exist; must be frozen before implementation
3. **Propagation checkpoint** — must be specified in that preregistration *(Part 3)*
4. **Feature-injection hook** — major implementation work, not yet scoped
5. **Compute benchmark** — must precede full-sweep authorisation

---

## PART 6 — Scientific decision

### 1 · Has the scientific uncertainty now been isolated to the Feature → Model pipeline?

**No — not fully. It is isolated to {Feature → Model} ∪ {common-mode aggregation loss}.**

Arm 1 validated the validation layer. Arm 1.5 bounded the combiner **relative to equal-weight
consensus** but did not measure **absolute** aggregation loss, because both compared paths consume the
same injected inputs. Completed outputs bound the residual — aggregation amplifies per-model IC at five
of six horizons — but do not eliminate it.

**Feature→Model is the dominant remaining uncertainty and the only stage still classified COMPLETELY
UNMEASURED. It is not the sole one.**

### 2 · Is Arm 2 now the highest Expected Value experiment?

**Yes — conditional on the propagation checkpoint.** It is the only experiment addressing an unmeasured
stage. **Without the checkpoint its EVI is materially lower**, because a negative result would be
uninterpretable across three competing explanations (Part 3, objection 3).

### 3 · Is there any experiment with higher Expected Value?

**No standalone experiment.** The one measurement with higher value per hour — absolute combiner loss
via per-model output IC — **is a component of Arm 2, not a competitor to it**, and Arm 2 must perform it
regardless to interpret its own result. Arm 3 is confounded by era and should follow. V5 runs in
parallel on an independent gate.

### 4 · Is the evidence now sufficient to justify restoring the research environment?

**Yes.** Three independent justifications from completed work: Arm 2 cannot run without it; Arm 3 and
any breadth replication are blocked on the same dependency; and **restoration was already authorised
under the V4 authorization boundary as disaster recovery for a realised permanent loss, independent of
any experiment.** The board's finding adds scientific justification to an authorisation that already
existed on other grounds.

### 5 · What single Arm 2 result would most change the future direction?

> **A large measured feature→model loss *with the propagation checkpoint confirming the injected signal
> reached the model inputs intact.***

The conjunction is what makes it decisive. It would establish that **the models themselves destroy
information that was demonstrably present in their inputs** — a failure no dataset of any size or
cleanliness repairs, sitting entirely inside the repository, and rendering every historical null
attributable to a mechanism upstream of everything measured so far.

The symmetric result — signal propagates *and* survives the models — would leave **feature generation
itself** as the last unmeasured stage, and would mean every downstream segment of the pipeline has been
measured and cleared.

**Both outcomes are decisive. Neither is obtainable without restoration, and neither is interpretable
without the checkpoint.**
