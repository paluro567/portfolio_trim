# P0-01 — Baseline Test Report (Part 5)

**Environment:** macOS darwin 25.5.0 · Python 3.13.14 (`uv`) · branch `v6-closure` · HEAD `b3bd82a0`
**Window (UTC):** 2026-08-06T01:01:03Z → 2026-08-06T01:01:10Z (+ follow-up verification)

## Results

| # | Check | Command | Exit | Summary |
|---|---|---|---|---|
| 1 | Full test suite | `uv run python -m pytest -q` | **0** | **551 passed, 252 skipped** — matches the frozen baseline exactly |
| 2 | Import check | `import mip, mip.cli.main, mip.engine.evidence` | **0** | OK |
| 3 | **Static check — ruff** | `uv run ruff check .` | **1** | **FAIL — 38 errors** |
| 4 | **Static check — black** | `uv run black --check src tests` | **1** | **FAIL — 2 files would be reformatted** |
| 5 | Manifest verification | 83 entries parsed from `MANIFEST.sha256` | **0** | **83 verified, 0 failed** |
| 6 | Recovered-SE defect absence | `grep "expected_excess_return / .*z_raw" src/` | **0** | **ABSENT**; 17 regression tests pass |
| 7 | Policy-only import check | — | n/a | Not applicable — `mip_evidence`/`mip_forecast` roots are created in **P0-04** |
| 8 | Repository status | `git status --porcelain -uall` | **0** | 27 untracked, 0 modified, 0 deleted |

> An earlier run in this session reported check 5 as "87 failures". That was a **parser defect in the verification loop**, not a manifest defect: `MANIFEST.sha256` carries a text header, and the loop treated header lines as hash entries. Re-run with correct parsing: **83/83 verified.**

## Failure detail

### Check 3 — ruff, 38 errors

| File | Count | Codes | Repository status |
|---|---|---|---|
| `tools/v6/recovered_se_repair.py` | **34** | E702×8, E501×7, N806×6, F401×4, E701×3, N803×2, E401×2, I001, B905 | **HASHED in `MANIFEST.sha256`** |
| `tools/phase1/case_facts.py` | 2 | N817, F401 | **FROZEN, study-scope** |
| `tools/phase1/verify_reports.py` | 1 | N817 | **FROZEN, study-scope** (the 81 contract checks) |
| `tests/unit/test_decision_evidence.py` | 1 | I001 | ordinary test file |

### Check 4 — black, 2 files

| File | Repository status |
|---|---|
| `tests/test_evidence_recovered_se.py` | **HASHED in `MANIFEST.sha256`** |
| `tests/unit/test_decision_evidence.py` | ordinary test file |

## Provenance of the failures — verified, not assumed

A read-only worktree was created at `main` (`1b2aec9`) and both checks re-run there:

```
ruff at main   exit=0    "All checks passed!"
black at main  exit=0
```

**Both checks were clean at `main`. The six V6-closure commits (`35c13cf`…`b3bd82a`) introduced all 38 ruff errors and both black violations.** This is newly-introduced debt on the current branch, not inherited repository debt.

## Gate decision: **STOP — DO NOT COMMIT**

Part 5 is unconditional: *"If any baseline test fails: STOP. Do not commit."* Two configured static checks fail.

Remediation is **not** mechanical, because three of the four affected files are protected:

- `tools/v6/recovered_se_repair.py` and `tests/test_evidence_recovered_se.py` are **hashed in `MANIFEST.sha256`**. Reformatting either invalidates its recorded hash and breaks the V6 reproducibility record, which currently verifies 83/83.
- `tools/phase1/case_facts.py` and `tools/phase1/verify_reports.py` are declared **FROZEN, study-scope** by the frozen `REPOSITORY_STRUCTURE.md`; `verify_reports.py` carries the 81 contract checks.

Only `tests/unit/test_decision_evidence.py` (1 ruff I001 + 1 black) is unprotected and safely fixable.

Running `ruff --fix` / `black` across the tree would silently mutate hashed canonical research artifacts and frozen study tooling. **That decision is not the P0-01 lead's to make.** No fix has been applied.
