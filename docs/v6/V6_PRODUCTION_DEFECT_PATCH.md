# V6 — Production Defect Patch (Part 4)

**Date:** 2026-08-04 · **Type:** code correctness only. **No forecasting claim attaches to this change.**

## 1. What was patched
`src/mip/engine/evidence.py` — the sole active occurrence:

```
- ses = [abs(participating[m].expected_excess_return / participating[m].diagnostics.z_raw)
-        for m in names]
+ ses = [model_standard_error(participating[m].effective_sample_size) for m in names]
```

Module docstring and the `ModelContribution.se` field comment were updated; the historical defect is documented in place so it cannot be reintroduced by someone reading only the code.

## 2. Replacement chosen: EQUAL UNCERTAINTY — and why not `k_h/√n_eff`

The preregistered estimator `se = k_h / √n_eff` was validated **in the research design only**, and it is **not valid for production**:

`k_h` is a per-horizon scale constant that the repair specification fixed by **matching the median combined |z| of the defective system**. Once the defective system is removed there is no production analogue for `k_h`, and fitting one is not authorized. Without a valid `k`, `1/√n_eff` is dimensionally inconsistent with effects measured in return units, and the resulting combined `z` would be meaningless.

**Equal uncertainty is the fallback the research record explicitly authorizes.** It requires no scale constant to produce weights: every participating model receives `EQUAL_SE`, so normalized weights are exactly `1/n` — bounded by construction and independent of the reported effect, which is precisely the property the defect violated.

## 3. Requirements met

| Requirement | How |
|---|---|
| No claim of improved forecasting | Stated in code and here; the experiment establishes the repair does **not** improve accuracy |
| No behaviour change beyond uncertainty and resulting weights | Only `ses` changed; effects, correlation prior, `Z_CLIP`, `score_from_z` untouched |
| Explicit handling of zero / missing / negative / non-finite `n_eff` | `model_standard_error()` validates `None`, non-castable, non-finite, and `< MIN_N_EFF` |
| Deterministic | Pure function, no state, no RNG |
| Bounded normalized weights | Exactly `1/n`; max/min weight ratio = 1.0 |
| Defective implementation retained only in archived fixtures | `docs/v6/archive/original_pre_amendment/evidence.py.orig`, and `tools/v6/recovered_se_repair.py` `MODE_ORIGINAL` (research only) |
| No active caller uses the defective formula | verified absent from `src/` by grep and by `test_defective_formula_absent_from_module_source` |

## 4. Tests — `tests/test_evidence_recovered_se.py`, 17 pass

zero effect (effect is no longer an input at all — the inversion is impossible by signature) · zero z · near-zero z · missing `n_eff` · non-finite `n_eff` (NaN, ±inf) · negative and zero `n_eff` · non-castable input · minimum valid `n_eff` · equal-`n_eff` symmetry · normalized weights sum to 1 · weight bounds (ratio = 1.0) · weight independent of effect magnitude · deterministic reproduction · defective formula absent from module source.

## 5. Downstream behaviour change — REPORTED, not concealed

Two existing tests encoded the defect and were corrected to the new contract:

- `test_expectations_are_precision_weighted` → **renamed** `test_expectations_are_equally_weighted`. It previously pinned a 16:1 weight split (10000 vs 625) that existed **only because of the defect**.
- `test_combination_matches_the_shared_framework_by_hand` — the by-hand expectation now passes `EQUAL_SE` for both models.

**A third test surfaced a material downstream consequence.** `tests/unit/test_intelligence.py::test_diff_against_previous` failed because the patch shifted combined scores enough that the engine **now emits the "Mixed Evidence" label** the fixture used as its "previous" value, leaving no diff to detect. The engine was **not** changed to accommodate the test; the fixture was made to derive a guaranteed-different label.

> **This is material for the product program: the patch changes emitted combined scores enough to flip at least one recommendation label.** That is a resulting consequence of corrected weights, permitted by the mandate, but it warrants product-side review before any release. It is reported here rather than absorbed silently.

**Full suite after patch: 551 passed, 252 skipped, 0 failed.**
