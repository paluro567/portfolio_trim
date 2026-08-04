# V6 Research Record — Canonical Index

**Generated:** 2026-08-04 · **Branch:** `v6-closure` · **Manifest:** `MANIFEST.sha256` (80 entries, all verified)
**Environment:** Python 3.13 (`uv`), Postgres 17 (`mip`, 86 tables at alembic head), lock: `uv.lock`, `pyproject.toml`
**Seeds:** `SEED_BASE = 20260801` (Arm 1 `v6_arm1.py`, Arm 1.5, recovered-SE repair). `v6_arm1b.py` used an independent base `77_000_000` — recorded because the extended grid cannot be reproduced from `SEED_BASE` alone.

## Governing documents
| Document | Role |
|---|---|
| `V6_FINAL_SCIENTIFIC_DETERMINATION.md` | **Closes V6.** All conclusions classified |
| `V6_CANONICAL_AUDIT_RECORD.md` | Reproducibility audit, canonical |
| `V6_SCIENTIFIC_OVERSIGHT_DETERMINATION.md` | Stopping-point determination |
| `V6_AMENDMENTS_001_005.md` · `V6_AMENDMENT_006_RECOVERED_SE.md` | Formal amendments |
| `V6_AMENDMENT_APPLICATION_REPORT.md` | What was applied, deferred, and why (**B-07**) |
| `V6_ENSEMBLE_RETIREMENT_REGISTER.md` · `V6_TO_PRODUCT_PROGRAM_HANDOFF.md` | Retirement and handoff |
| `V6_CLOSURE_VERIFICATION.md` · `V6_REPOSITORY_CLOSURE_REPORT.md` | Closure evidence |

## Experiments
| Arm | Documents | Reproduction command |
|---|---|---|
| Arm 1 | `V6_ARM1_RESULTS.md`, `_MDE_TABLE`, `_RECOVERY_CURVES`, `_POWER_TABLE`, `_SCALING`, `_LIMITATIONS`, `_SCIENTIFIC_REVIEW` | scratch harness `v6_arm1.py` / `v6_arm1b.py` — **not preserved**; see B-07 |
| Arm 1.5 | `V6_ARM15_RESULTS.md`, `_INFORMATION_LOSS`, `_BOOTSTRAP_RESULTS`, `_SECONDARY`, `_WEIGHTS`, `_DIAGNOSTICS`, `_REPRODUCIBILITY` | scratch harness `a15_run.py` — **not preserved** |
| Audit | `V6_REPRODUCIBILITY_AUDIT.md`, `V6_AUDIT_ARM1_CURVE_{OLD,NEW}.csv`, `V6_AUDIT_ARM15_PAIRED.csv` | — |
| Arm 2 | 12 readiness artifacts + `V6_ARM2_PREREGISTRATION.md` + `_AMENDMENT_B.md` | **RETIRED** — never executed |
| Recovered-SE repair | `V6_RECOVERED_SE_*` (5 md, 2 csv) | `uv run python tools/v6/recovered_se_repair.py` |

## Archived originals
`docs/v6/archive/original_pre_amendment/` — 12 pre-amendment artifacts + `evidence.py.orig`. Immutable.

## Research substrate (gitignored)
`data/validation/analogue_v1/embargoed_revalidation/` — `merged.csv` (51,025 rows) + 7 `predictions_*.jsonl` (63,535 lines). **Not under version control**; hashes in `MANIFEST.sha256` are the only binding record.

## Final scientific status
**CLOSED.** The directional ensemble is retired: every tested variant loses to a constant-50% forecaster. The recovered-SE defect was real, is repaired, and was **not** the cause. Whether real predictive signal exists in these features or models was **never tested and remains open**.
