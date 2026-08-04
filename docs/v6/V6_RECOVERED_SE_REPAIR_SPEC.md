# V6 — Recovered-SE Repair Specification (Part 3)

**Date:** 2026-08-02 · **Committed BEFORE any repaired performance was observed.**

## 1. Primary repair — SELECTED

> **`se_i = k_h / sqrt(n_eff_i)`**, hence `w_i = 1/se_i² = n_eff_i / k_h²`

`n_eff_i` is the model's overlap-adjusted effective sample size, already computed by each model at scoring time and **already stored in the archived per-model predictions**. Nothing new is computed, fitted, or purchased.

### 1.1 The scale constant `k_h`

`k_h` does **not** cancel. Substituting `se_i = k/√n_eff_i` into the correlated fixed-effect form:
- combined effect `e_c = Σ n_eff_i·e_i / Σ n_eff_i` — `k` cancels ✔
- combined variance `∝ k²`, therefore combined `z ∝ 1/k` — `k` **does not** cancel

Since `p_up = Φ(z_combined)`, `k` is a calibration-scale knob. Changing calibration is prohibited. Therefore:

> **`k_h` is fixed per horizon so that `median|z_combined|` under repair equals `median|z_combined|` under the original.**

This uses **no outcomes** — only the two systems' own combined z distributions. It holds the overall confidence scale exactly where the original put it, so the experiment isolates the **relative-weighting** change, which is the defect. Rank IC is invariant to `k` (Φ is monotone) and is reported as a scale-free cross-check.

### 1.2 Numerical safety (declared, not tuned)
- **Floor:** `n_eff_i ← max(n_eff_i, 1.0)`. Measured archive minimum is 1.030, so the floor is never expected to bind; it exists to make `w` finite by construction.
- **No cap required:** `w ∝ n_eff` is bounded by the archive maximum (320.1), giving a worst-case weight ratio of 320.1/1.0 = 320×, versus the defective path's unbounded `effect⁻²`.
- **Missing / non-finite `n_eff`:** the model is dropped from that cell and the drop is logged. Measured occurrences: 0.

### 1.3 Compliance with the mandated constraints

| Requirement | How satisfied |
|---|---|
| Not algebraically reconstructable from the same (effect, z) pair | `n_eff` is an independent quantity; it appears nowhere in `effect` or `z_raw` |
| No future outcomes from the evaluation period | `n_eff` counts historical analogue events strictly at/before `as_of` |
| Computable point-in-time | computed by each model at scoring time; already in the archive |
| Explicit provenance | `ScoreDiagnostics.max_n_eff` → serialized `n_eff` field in `predictions_*.jsonl` |
| Behaves sensibly near zero | `n_eff ≥ 1` by floor; `se` is finite and strictly positive for all records |
| No infinite or arbitrarily dominant weights | bounded ratio 320×; no dependence on `effect` |
| Not selected because it improves the result | selected and frozen in this document before any repaired metric was computed |
| No new commercial data | none |
| Changes only the defective uncertainty input | `effect`, correlation matrix, `Z_CLIP`, `score_from_z`, cells, outcomes all untouched |

## 2. Rejected alternatives

| Alternative | Rejected because |
|---|---|
| **Bootstrap SE inside the training window** | Not recoverable. Per-model bootstrap draws were never serialized, and re-running models is impossible — 3 of 7 emit constant output for want of fundamentals/sector data. Would also require recomputing history, violating "change only the uncertainty input". |
| **Stored `confidence` field** | `confidence = confidence_from_evidence(n_eff, agreement, prior)` is a bounded 0–1 *volume × consistency* score, not a standard error. Mapping it to an SE requires inventing a transform, and it is a monotone function of `n_eff` anyway — strictly worse provenance for the same information. |
| **Model-reported dispersion (σ, IQR/1.349)** | Not serialized in the archived predictions. Present only inside the analogue engine, which is a SHADOW model excluded from the official set. |
| **Re-derive SE by re-running the models** | Impossible on the surviving repository (3 dead models) and would alter more than the uncertainty input. |
| **Fixed equal uncertainty (`se_i = const`)** | Valid and defensible, but it discards the genuine point-in-time information in `n_eff`. **Retained as arm C, the repair control**, not as the primary repair. |
| **Any estimator fitted to evaluation-period outcomes** | Prohibited outright. |

## 3. What is explicitly NOT changed

Models · features · outcomes · symbol-date-horizon cells · horizons · universe · correlation prior (`BASELINE_CORRELATION`, `OVERLAP_CORRELATION`) · `Z_CLIP = 4.0` · `score_from_z = 100·Φ(z)` · `p_up = evidence_score/100` · clipping at `[0.01, 0.99]` · the Brier definition · cohort non-overlap stride · block-bootstrap structure.
