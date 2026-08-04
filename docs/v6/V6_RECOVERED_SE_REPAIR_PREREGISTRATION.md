# V6 — Recovered-SE Repair Preregistration (Part 4)

**Date:** 2026-08-02 · **Frozen BEFORE execution.** Seed `SEED_BASE = 20260801`.

## 1. Hypothesis (Part 2)

**H1 (alternative):** The recovered-SE implementation `se = |effect/z|` materially degrades the ensemble relative to the frozen replacement `se = k/√n_eff`, holding every other component fixed.

**H0 (null):** Replacing the recovered-SE rule produces no material change in the ensemble's paired performance.

### What this experiment measures
Whether one known implementation defect, in the uncertainty input to precision weighting, degraded measured ensemble performance relative to the frozen baselines — with all other components held byte-identical.

### What it does NOT measure
- Whether real predictive signal exists in the models, features, or platform.
- Whether the platform is investable, or whether any model has skill.
- Whether `n_eff` weighting is optimal — only that it is defensible and defect-free.
- Anything about Arm 2, propagation, or feature consumption.

A repaired ensemble that still loses to a constant forecaster is a *coherent and expected* outcome of this design and does **not** falsify the repair.

## 2. Arms

| Arm | Definition |
|---|---|
| **A** | Original defective production ensemble — `se = |effect/z_raw|`, recomputed from archived per-model predictions |
| **B** | Repaired ensemble — `se = k_h/√n_eff` per the frozen spec |
| **C** | Equal-weight ensemble — `se_i = const` (repair control) |
| **D** | Best frozen simple baseline from the prior paired-baseline study |
| **E** | Neutral constant baseline — `p ≡ 0.5` |

**D ≡ E.** The prior paired-baseline study's frozen simple baseline is the uninformed constant-50% forecaster, implemented in `metrics.accuracy_and_brier` as `brier_reference`. D and E are therefore the same comparator and are reported once, as **D/E**. This is recorded rather than substituted: no alternative simple baseline is introduced.

## 3. Held identical across all arms
Symbol-date-horizon cells · models · per-model `effect` and `z_raw` · outcomes (`realized_excess`) · date blocks · missing-data rules · calibration treatment (`p = clip(score/100, 0.01, 0.99)`) · evaluation metrics · **bootstrap resample indices**.

## 4. Primary endpoint

> **ΔBrier = Brier(A) − Brier(B)**, paired, per horizon. Positive ⇒ repair improves.

`Brier = mean((p − y)²)`, `y = 1[realized_excess > 0]`, `p = clip(evidence_score/100, 0.01, 0.99)` — the exact definition at `src/mip/validation/metrics.py:72`, unchanged.

**Cells:** `metrics.cohort()` non-overlapping cohort per horizon (stride `ceil(H_sessions/10)`), restricted to `realized_excess.notna()` — the frozen prior protocol.

## 5. Secondary endpoints (may never override the primary)
B vs C · B vs D/E · A vs C · rank IC (`rank_correlation`) · direction accuracy · log loss · ECE · weight concentration · effective number of models.

## 6. Inference

| Element | Specification |
|---|---|
| Bootstrap unit | **per-symbol circular block**, block = 4 |
| Draws | 1000, identical indices across all arms (paired) |
| Seed | 20260801 |
| Confidence interval | percentile, 95% (2.5 / 97.5) |
| Minimum sample | **n ≥ 100** cohort cells per horizon; below that the horizon is reported but classified INCONCLUSIVE |
| Pooling | **none across horizons** for the primary; each horizon decided independently |
| Multiplicity | 6 horizons → program rule §7 handles it; no per-horizon alpha adjustment, since the program rule requires agreement across ≥3 horizons |

## 7. Program-level decision rule — frozen in advance

Defined now to prevent the six-horizon ambiguity encountered in Arm 1.5.

Per horizon, on ΔBrier:
- **PASS** — CI lower bound > 0
- **FAIL** — CI upper bound < 0
- **INCONCLUSIVE** — CI spans 0, or n < 100

Program-level, over the 6 horizons:
- **PROGRAM PASS** — PASS at ≥ 3 horizons and FAIL at 0
- **PROGRAM FAIL** — FAIL at ≥ 3 horizons and PASS at 0
- **PROGRAM NULL** — INCONCLUSIVE at ≥ 4 horizons *(the defect is real but not material to performance)*
- **PROGRAM MIXED** — any other combination; reported as INCONCLUSIVE with the pattern stated

## 8. Pre-execution invariants (Part 6) — all must hold or STOP
1. Arm A reproduces the archived canonical `baseline` evidence_score to < 1e-9.
2. A and B use identical per-model `effect` values (byte-identical).
3. Identical cell sets across arms.
4. Identical outcomes.
5. No data added or removed.
6. No calibration parameter refitted using evaluation outcomes.
7. No result-dependent choices; the repair was frozen in the spec document before execution.
8. The only causal difference is the uncertainty input and the weights it induces.
