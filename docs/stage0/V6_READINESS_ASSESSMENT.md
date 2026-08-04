# V6 READINESS ASSESSMENT

**V6 is NOT executed.** This records only what the repository can currently support.
**No production refactoring was performed.**

---

## Capability assessment

| # | Capability | Status | Evidence | Work required |
|---|---|---|---|---|
| 1 | **Score-level signal injection (Arm 1)** | 🟡 **Minor work** | `validation/systems.py::combine_rows` reconstructs any model subset from captured `(effect, z_raw)`; injection = perturbing that frame before combination | ~1 day driver |
| 2 | **Feature-level injection (Arm 2)** | 🔴 **Major work** | Requires a synthetic feature correlated with forward returns, registered and flowing through model → combiner. Feature pipeline exists (`features/pipeline.py`) but **no injection hook** | ~1 week driver + **blocked on data** |
| 3 | **12–1 momentum end to end (Arm 3)** | 🔴 **Blocked by missing data** | Needs ≥13 months of prices per symbol. **`daily_prices` is empty** | Data re-ingestion first |
| 4 | **Time-block resampling** | 🟢 **READY** | `metrics.block_bootstrap_delta` — circular block bootstrap over per-symbol cohort series, block=4, paired differences. Year-block variant written in session scratch | none |
| 5 | **Per-horizon embargo** | 🟢 **READY** | `validation/eligibility.py` — central rule `pos(t)+H ≤ pos(T)`; `walkforward.py` asserts `violations == 0` and emits `leakage_report.json` | none |
| 6 | **False-positive controls** | 🟡 **Minor work** | Injecting IC = 0.00 is a parameter of the Arm-1/Arm-2 driver | included above |
| 7 | **False-negative controls** | 🟡 **Minor work** | The MDE curve itself; monotonicity check is analysis code | ~0.5 day |
| 8 | **MDE sweep harness** | 🔴 **Major work** | 134,400 runs (7 IC × 4 breadth × 4 years × 6 horizons × 200 seeds). No batching or parallelism exists; current full-universe passes take 5–7 min for 52 symbols | ~1 week + compute |
| 9 | **Arm 2 − Arm 1 loss analysis** | 🟡 **Minor work** | Pure arithmetic once arms 1 and 2 produce MDE surfaces | ~0.5 day |
| 10 | **Cohort / non-overlap** | 🟢 **READY** | `metrics.cohort` — stride `ceil(H/10)` per symbol | none |
| 11 | **Realized outcomes** | 🔴 **Blocked by missing data** | `validation/realized.py` reads `daily_prices` — empty | Data re-ingestion |
| 12 | **Captured walk-forward for Arm 1** | 🟢 **READY (artifacts survive)** | `analogue_v1/embargoed_revalidation` — 7 symbols × 189 dates, per-model captures **plus outcomes**; `conditional_v1` — 31 symbols × 175 dates, per-model captures **without** outcomes | none for Arm 1 |

## Summary

| Status | Count | Items |
|---|---|---|
| 🟢 **Ready** | 4 | time-block resampling · embargo · cohort · surviving captures |
| 🟡 **Minor work** | 4 | Arm 1 injection · FP controls · FN controls · loss analysis |
| 🔴 **Major work** | 2 | Arm 2 injection · MDE sweep harness |
| 🔴 **Blocked by missing data** | 2 | Arm 3 (12–1 momentum) · realized outcomes |
| 🔴 **Blocked by lost artifacts** | 0 | — |

## Critical finding

> **Arm 1 can run today on surviving artifacts.**
>
> The `analogue_v1/embargoed_revalidation` capture retains per-model `(effect, z_raw)` **and** realized
> outcomes for 7 symbols × 189 dates. That is sufficient to inject synthetic IC at the score level and
> measure the **validation layer's** MDE — **without re-ingesting a single price.**
>
> Arms 2 and 3 require the data layer. **Arm 1 does not.**

This matters because Arm 1 alone answers a question that has never been answered: *what effect size can
the validation layer detect at all?* A partial V6 is available at low cost while data re-ingestion
proceeds.

**It does not satisfy G5.** The gate requires the full surface, and the Arm 2 − Arm 1 gap — the
diagnostic that would indict the model/combiner layer — needs both arms.

## Sequencing implication

```
now                    -> Arm 1 on surviving captures (~1 day)      [partial signal]
after data re-ingest    -> Arm 2 + Arm 3 + full sweep (~2 weeks)     [G5 evaluable]
```

## Explicitly NOT done

No production refactoring. No `src/` changes. No injection hooks added to `features/pipeline.py`. The
V4 authorization boundary holds: **the moment a domain object acquires a repository, it is prohibited.**
