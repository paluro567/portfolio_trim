# V6 — Ensemble Retirement Register (Part 5)

**Date:** 2026-08-04 · Nothing required to reproduce published research is deleted.

| Artifact | Class | Disposition |
|---|---|---|
| `V6_ARM1_*` (results, CSVs, limitations, scientific review) | **Retained for historical reproducibility** | Canonical; hashed in `MANIFEST.sha256` |
| `V6_ARM15_*` (results, CSVs, diagnostics, reproducibility) | **Retained for historical reproducibility** | Canonical; hashed |
| `V6_REPRODUCIBILITY_AUDIT.md`, `V6_AUDIT_ARM1_CURVE_*.csv`, `V6_AUDIT_ARM15_PAIRED.csv` | **Retained for historical reproducibility** | Canonical; hashed |
| `V6_CANONICAL_AUDIT_RECORD.md`, `V6_AMENDMENTS_001_005.md`, `V6_AMENDMENT_006_RECOVERED_SE.md` | **Retained — governing** | Canonical |
| `archive/original_pre_amendment/**` | **Retained — immutable originals** | Never modified; hashed |
| **Alternative weighting experiments** | **Retired** | None exist beyond the single preregistered repair; no further weighting experiment is authorized |
| **Weighting optimization** | **Retired** | Complex weighting is unsupported (B6); optimization would presuppose what was refuted |
| **Ensemble calibration** | **Retired** | Emitted probabilities are worse than an uninformed constant (B7); recalibration is not authorized |
| **Ensemble confidence** | **Deprecated** | `combined_confidence` retains no demonstrated directional validity (B8); must not be presented as predictive confidence |
| `V6_ARM2_*` (12 readiness artifacts, preregistration, Amendment B) | **Retained as a frozen baseline** | Arm 2 permanently retired; documents preserved as the methodological record |
| `V6_ARM2_ADDENDUM_A.md` | **Retired — WITHDRAWN** | Contains the `ret_21d` partition falsified by Stage-2 causal testing. Marked withdrawn; may not be signed. No replacement. |
| `V6_ARM2_PREREGISTRATION_AMENDMENT_B.md` methodology | **Retained as reusable methodology** | The causal consumer definition, control requirements, A2 checkpoint and interpretation matrix are sound and outlive Arm 2 |
| **Future ensemble roadmap items** | **Retired** | Further ensemble development is not authorized |
| `tools/v6/recovered_se_repair.py` (research-only switch, `MODE_ORIGINAL`) | **Retained for historical reproducibility** | Research-only. Not importable by production — lives under `tools/`, not `src/`, and no `src/` module references it |
| `docs/v6/archive/original_pre_amendment/evidence.py.orig` | **Retained as archived fixture** | The only surviving copy of the defective formula, inert |
| `/tmp` audit harnesses (`consumer_census.py`, `deep_probe.py`, `run_repair.py`, `defect_repro.py`, `tie_census.py`, `sel2.py`) | **Deleted — generated and non-canonical** | Ephemeral; superseded by `tools/v6/recovered_se_repair.py` and by the published CSVs. Their outputs are preserved. |

## Import isolation
- The defective formula exists **only** in `docs/v6/archive/original_pre_amendment/evidence.py.orig` (a `.orig` file, not importable) and in `tools/v6/recovered_se_repair.py` under an explicit `MODE_ORIGINAL` branch.
- `tools/` is not a package on the production import path; no module under `src/` imports from it.
- Verified: `grep -rn "expected_excess_return / .*z_raw" src/` returns **nothing**.
- Pinned by `test_defective_formula_absent_from_module_source`.

## Arm 2 execution isolation
No Arm 2 executor exists in `src/`. The injection hook was never merged into production — it was applied at runtime by monkey-patching `FeatureRepository.get_instrument_series` inside a scratch harness that no longer exists. **There is no code path by which Arm 2 can execute accidentally.**
