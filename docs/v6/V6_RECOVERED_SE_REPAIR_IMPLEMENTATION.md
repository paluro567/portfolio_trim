# V6 — Recovered-SE Repair Implementation (Part 5)

**File:** `tools/v6/recovered_se_repair.py` — **research only.** `src/` is unmodified; production behaviour is unchanged and the defect remains in place in production pending a separate decision.

## Isolation
A single branch point, `recover_se(mode, effect, z_raw, n_eff)`, is the **only** line that differs between arms:

```
ORIGINAL : |effect / z_raw|              <- default; the defect
REPAIRED : 1 / sqrt(max(n_eff, 1.0))     <- frozen minimum repair, scaled by k_h
EQUAL    : 1                             <- repair control
```

`combine()` reproduces production `combine_decision_evidence` exactly — same correlation prior via `model_correlation`, same quadratic form, same `Z_CLIP = 4.0`, same `score_from_z`. Verified at **2.842e-14** against the archived canonical `baseline` (invariant I1).

| Requirement | Status |
|---|---|
| Original behaviour reproducible | ✔ `MODE_ORIGINAL` is the default and reproduces the archive to 2.8e-14 |
| Repaired behaviour disabled by default | ✔ requires explicit `MODE_REPAIRED` |
| Production not silently changed | ✔ no edit to `src/` |
| Model outputs byte-identical before weighting | ✔ `effect`, `z_raw` read once and passed unmodified to every mode |
| Outcomes unchanged | ✔ `realized_excess` read once from `merged.csv` |
| Cells unchanged | ✔ one cohort per horizon, shared by all arms |
| Only uncertainty and induced weights differ | ✔ invariant I8 |
| Weight calculations logged | ✔ per-arm shares → `V6_RECOVERED_SE_REPAIR_WEIGHT_DIAGNOSTICS.csv` |
| Deterministic | ✔ no RNG outside the bootstrap; bootstrap seeded at 20260801 with identical indices across arms |

## Tests — 11/11 pass
zero effect (ORIGINAL degenerates to `se=0`; REPAIRED stays finite) · near-zero `z` (REPAIRED unaffected) · missing `n_eff` (floored) · non-finite `n_eff` · weight ∝ `n_eff` · weight normalization sums to 1 · equal-input symmetry · bounded weight ratio · deterministic reproduction · ORIGINAL reproduces the `w = (z/effect)²` identity.
