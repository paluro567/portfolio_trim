# V6 — MDE AND PIPELINE SENSITIVITY PLAN

**Objective:** measure what this pipeline can actually detect. **Pre-registered before the sweep runs.**

> The question every prior study begged: *is a null result a true negative, or a blind instrument?*
> V6 answers it by injecting a signal we control and finding where it disappears.

---

## 1 · The three arms

| Arm | Injection point | Measures |
|---|---|---|
| **Arm 1** | Synthetic IC added to the **score stream**, upstream of validation | MDE of the **validation layer alone** |
| **Arm 2** | Synthetic **feature** correlated with forward returns at known strength, run through a model + combiner | MDE of the **full downstream chain** |
| **Arm 3** | **12–1 momentum** implemented as a feature, run end-to-end | Does a **real, documented, literature-size** effect survive the whole pipeline? |

**Arm 2 − Arm 1 = signal destroyed by the model / probability / combiner layer.**
Never measured. Directly actionable: a large gap indicts the aggregation layer rather than the data.

## 2 · Sweep specification

| Axis | Values |
|---|---|
| **Injected IC** | 0.00 *(null control)* · 0.01 · 0.02 · 0.03 · 0.05 · 0.10 · 0.15 |
| **Breadth** | 7 · 31 · 100 · 500 names |
| **Years** | 4 · 8 · 15 · 20 |
| **Horizon** | 1w · 2w · 1m · 3m · 6m · 1y |
| **Seeds** | ≥ 200 per cell |

7 × 4 × 4 × 6 × 200 = **134,400 runs.** Batched; content-addressed snapshots prevent recomputation.

## 3 · Resampling — time-block, never row-independent

- **Annual block bootstrap** on overlapping-horizon metrics.
- **Per-horizon embargo** — the shipped `validation/eligibility.py` rule; `pos(t) + H ≤ pos(T)`.
- **Episode counting**, never row counting.
- Leakage report asserting **violations == 0** on every configuration.

## 4 · Detection criteria

A configuration **detects** an injected IC when the block-bootstrap CI on the recovered IC **excludes
zero** in **≥80%** of seeds. Reported at 80% and 90% power.
**MDE(config)** = the smallest injected IC meeting that criterion.

## 5 · False-positive and false-negative controls

| Control | Method | Required result |
|---|---|---|
| **False positive** | Inject **IC = 0.00**; count spurious detections | Detection rate ≈ α (≤0.07 at α=0.05). **Above 0.10 invalidates the sweep** |
| **False negative** | The MDE curve itself | Monotone in breadth and years. **Non-monotonicity indicates a harness defect, not a finding** |
| **Sanity** | Inject IC = 0.15 at 500 × 20 | Must detect in ≥99% of seeds. Failure means the harness is broken |
| **Arm-3 null** | Momentum on a shuffled-label universe | Must not detect |

## 6 · Required outputs

```
mde_surface.csv        arm, ic, breadth, years, horizon, detect_rate_80, detect_rate_90, se
information_loss.csv   horizon, mde_arm1, mde_arm2, loss = arm2 - arm1
arm3_result.json       12-1 momentum: IC, CI, detected(bool), per-horizon
false_positive.json    detection rate at IC = 0.00 per configuration
se_table.csv           achieved SE per configuration
leakage_report.json    violations == 0
```

## 7 · The gate — G5

> **PASS:** MDE ≤ **0.03** IC at an attainable configuration (**≤500 names × ≤20 years**) at 80% power.
> → Clean commercial data **could be decisive**. Condition 5A satisfied.
>
> **AMBIGUOUS:** MDE in **0.03–0.05**.
> → Purchase permitted **only** with the reduced claim declared in advance and recorded in the G6
> authorization.
>
> **FAIL:** MDE > **0.05** at **every** attainable configuration.
> → **No dataset can ever be decisive at this budget. G6 and G7 are permanently blocked. The prediction
> programme terminates and the product is formally redefined.**

**"Attainable" is bounded by what an affordable vendor supplies** — approximately 500 names and 20
years. A configuration requiring 3,000 names or 40 years is not attainable and does not count toward a
PASS.

## 8 · Interpretation matrix

| Arm 1 | Arm 2 | Arm 3 | Reading |
|---|---|---|---|
| MDE ≤0.03 | ≈ Arm 1 | detects | Instrument sound, chain sound. **Past nulls are true negatives** |
| MDE ≤0.03 | **≫ Arm 1** | fails | **The model/combiner layer destroys signal.** Repair the aggregation before buying any data |
| MDE >0.05 | — | fails | Instrument blind. Data may help **if** breadth/years lift the MDE below 0.03 |
| MDE >0.05 at every config | — | — | **G5 FAIL. Terminate the prediction programme** |

## 9 · Scope and cost

Existing free data · scratchpad drivers · no `src/` code · ~6 weeks · **$0** *(plus ≤$180 cloud compute
for the sweep, already inside the B0 line)*.

**Pre-registration is mandatory.** Thresholds in §7 are frozen before the first run. Discovering the
MDE and then choosing the threshold would be the exact circularity the methodology review rejected.
