# AMENDMENT A-2026-006 — Recovered-SE Experiment Final Record

**Version:** 1.0 · **Effective date:** 2026-08-04 · **Type:** Scientific (withdrawal) + software correctness

## Background
The V6 program identified `se = abs(effect / z_raw)` in `src/mip/engine/evidence.py` as an implementation defect and, on the Oversight Committee's ranking, executed one controlled repair experiment: replace the uncertainty input, hold every other component fixed, and re-run the frozen paired baseline.

## Reason
The experiment completed. All 8 invariants passed; Arm A reproduced the archived canonical baseline to 2.842e-14. It established that the defect is real and mechanically removable, and that removing it does **not** improve forecasts. The research record contains a causal claim that must now be withdrawn.

## Correction

### 1. Original claim — WITHDRAWN
> "This defect produced inverted weighting behavior and **is implicated in the platform's measured ensemble failure**."
> — carried in the ensemble-failure root-cause record

### Replacement language
> "This defect produced inverted weighting behaviour: `spearman(|effect|, weight) = −0.7228`, with weights unbounded as `effect → 0`. The inversion is **confirmed**. The defect is **not** a cause of the measured forecasting failure: under the preregistered repair, holding all else fixed, the repaired ensemble did not beat the original at any horizon (0 PASS, 1 FAIL, 5 INCONCLUSIVE) and remained decisively worse than an uninformed constant-50% forecaster at all six horizons. The defect is a **software-correctness fault**, not a performance cause."

### 2. Findings ratified

| Statement | Status |
|---|---|
| The defect was real | **ESTABLISHED** |
| The defect was repaired mechanically | **ESTABLISHED** — max top share 0.878 → 0.628; effective models 3.91 → 4.13 |
| The repair did not improve predictive performance | **ESTABLISHED** — directionally worse at 5 of 6 horizons |
| The causal claim implicating the defect in ensemble failure | **WITHDRAWN** |
| The defect remains unacceptable as software | **ESTABLISHED** — removed from production, 17 regression tests |
| Complex weighting remains unsupported | **ESTABLISHED** — loses to constant-50% at 6/6 |

### 3. Claim NOT withdrawn — and independently confirmed
The prior finding that equal-weight's apparent advantage came from **shrinkage** stands. Holding the calibration scale fixed via `k_h` removes the shrinkage channel, and equal weighting then loses to both the original and repaired ensembles at all six horizons.

### 4. Scope limit — binding
No conclusion is expanded beyond this experiment. It does **not** establish that no predictive signal exists, that markets are unpredictable, or that any individual model lacks skill. Those were not tested.

## Affected documents
`docs/v6/V6_RECOVERED_SE_REPAIR_DECISION.md` · `V6_RECOVERED_SE_REPAIR_RESULTS.md` · `V6_SCIENTIFIC_OVERSIGHT_DETERMINATION.md` (Part 4 EVI rationale) · `V6_FINAL_SCIENTIFIC_DETERMINATION.md` · `src/mip/engine/evidence.py` (module docstring) · `~/.claude/.../memory/ensemble-failure-root-cause.md`

## Scientific impact
One causal claim withdrawn. No experimental result is altered. Arm 1, Arm 1.5, the reproducibility audit and the Arm 2 retirement are untouched. The platform's measured performance is unchanged by this amendment — the ensemble was, and remains, worse than a constant forecaster.

## Version history
- v1.0 · 2026-08-04 · initial issue. Original claim preserved verbatim above.

## Signatures

| Role | Name | Date | Signature |
|---|---|---|---|
| Closure and Repository Integrity Lead | — | — | *unsigned* |
| Independent Research Integrity Board | — | — | *unsigned* |

*No human sign-off evidence exists.*

## Hash field

| Artifact | SHA-256 |
|---|---|
| `V6_AMENDMENT_006_RECOVERED_SE.md` | recorded in `MANIFEST.sha256` |
| `src/mip/engine/evidence.py` (patched) | recorded in `MANIFEST.sha256` |
| `evidence.py.orig` (pre-patch) | recorded in `MANIFEST.sha256` |
