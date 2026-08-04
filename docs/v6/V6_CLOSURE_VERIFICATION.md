# V6 — Closure Verification (Part 8)

**Date:** 2026-08-04 · Bounded verification only. No experiment re-run.

| # | Check | Result |
|---|---|---|
| V1 | Canonical files exist | **PASS** — 51 documents/CSVs under `docs/v6/` |
| V2 | Hashes match | **PASS** — 80 / 80 verified via `shasum -a 256 -c` |
| V3 | Source imports | **PASS** — `mip.engine.evidence` imports; `EQUAL_SE=1.0`, `MIN_N_EFF=1.0` |
| V4 | Unit tests pass | **PASS** — 551 passed, 252 skipped, 0 failed |
| V5 | Defective formula absent from active code | **PASS** — `grep` over `src/` returns nothing; pinned by `test_defective_formula_absent_from_module_source` |
| V6 | Archived original behaviour reproducible through fixtures | **PASS** — `MODE_ORIGINAL` reproduces `w = (z/effect)² = 10000` for effect 0.02, z 2.0 |
| V7 | Amendment links resolve | **PASS** — all 4 governing amendment documents present |
| V8 | Retired Arm 2 code cannot execute accidentally | **PASS** — no injection hook exists in `src/`; the hook was only ever a runtime monkey-patch in a scratch harness that no longer exists |
| V9 | Withdrawn causal claim removed everywhere | **PASS** — 0 unqualified occurrences. It survives only inside `V6_AMENDMENT_006_RECOVERED_SE.md`, which quotes it in order to withdraw it, and in `V6_RECOVERED_SE_REPAIR_DECISION.md` under an explicit in-file withdrawal block |
| V10 | No document presents complex weighting as justified | **PASS** — `V6_ARM1_RESULTS.md` and `V6_ARM15_RESULTS.md` carry explicit A-2026-006 blocks stating it is not |

## Not verified, and why
- **Arm 1 extended-grid reproduction (B-07).** Establishing whether the published values or the audit re-run is correct requires re-running Arm 1's extended grid. Not authorized. Both readings are preserved side by side in `V6_ARM1_MDE_TABLE.csv`.
- **Runtime metadata for the Arm 1 audit passes.** Never instrumented; stated rather than invented.
