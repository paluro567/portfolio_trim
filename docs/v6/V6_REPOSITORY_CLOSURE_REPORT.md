# V6 — Repository Closure Report (Part 6)

**Date:** 2026-08-04 · **Branch:** `v6-closure` (created from `main` @ `1b2aec9f`) · **Working tree: CLEAN (0 uncommitted paths)**

Work was committed to a branch, not to `main`. Merging is left to the repository owner.

## Commit inventory

| # | Commit | Contents | Classification |
|---|---|---|---|
| 1 | `35c13cf` | Amended CSVs (A-002/003/004), tie-mechanism wording (A-005), immutable archive, audit record, amendment docs | Canonical research artifact |
| 2 | `3e39675` | Recovered-SE experiment record (5 md + 2 csv), A-2026-006, final determination, `tools/v6/` | Canonical research artifact |
| 3 | `8da8613` | `src/mip/engine/evidence.py` patch, 17 new tests, 3 corrected tests | **Approved source correction** |
| 4 | `cb04738` | Retirement register, handoff, and the prior research document set (`docs/*.md`, `docs/phase1`, `docs/program`, `docs/stage0`, `docs/v4`) | Canonical research artifact |
| 5 | `d36fc6c` | `MANIFEST.sha256`, closure verification, record index, `tools/ops`, `tools/phase1` | Backup / manifest infrastructure |

## Path classification and decisions

| Path group | Classification | Decision | Reason |
|---|---|---|---|
| `docs/v6/**` (51 files) | Canonical research artifact | **INCLUDE** | Governing record |
| `docs/v6/archive/original_pre_amendment/**` | Canonical — immutable originals | **INCLUDE** | Preserves superseded values; hashed |
| `docs/{phase1,program,stage0,v4}/`, `docs/*.md` | Canonical research artifact | **INCLUDE** | Previously untracked research record |
| `src/mip/engine/evidence.py` | Approved source correction | **INCLUDE** | The patch |
| `tests/test_evidence_recovered_se.py` | Approved source correction | **INCLUDE** | 17 regression tests |
| `tests/unit/test_decision_evidence.py`, `tests/unit/test_intelligence.py` | Approved source correction | **INCLUDE** | Corrected tests that pinned the defect |
| `tools/v6/`, `tools/ops/`, `tools/phase1/` | Reproduction + infrastructure | **INCLUDE** | Required to reproduce published research |
| `MANIFEST.sha256` | Manifest infrastructure | **INCLUDE** | Binds the record |
| `**/__pycache__/`, `*.pyc` (14 paths, some previously tracked) | Generated output | **EXCLUDE — untracked and gitignored** | Build artifacts; were erroneously tracked before |
| `RawData/macro/**`, `RawData/prices/**` (30 paths) | Generated output | **EXCLUDE — gitignored** | Regenerable ingestion cache (`mip ingest` reproduces it in seconds) |
| `data/validation/**` | Canonical substrate | **EXCLUDE — pre-existing `.gitignore`** | **Hashed in `MANIFEST.sha256`** — the only binding record. Flagged: this substrate is irreplaceable and is not under version control. |

Nothing was committed blindly; nothing was deleted.

## Repository hygiene note
`__pycache__` and `*.pyc` files were previously **tracked**. They are now removed from the index and added to `.gitignore`. This is incidental to V6 closure and is recorded rather than presented as part of the scientific work.

## Open item
The research substrate `data/validation/analogue_v1/embargoed_revalidation/` is excluded by a pre-existing `.gitignore` rule. It is class-B irreplaceable data with no version control. Its hashes are recorded, but **hashes detect loss; they do not prevent it.** Backing it up is a repository-owner decision outside this task's authority.
