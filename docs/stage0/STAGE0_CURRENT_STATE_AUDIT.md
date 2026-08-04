# STAGE 0 — CURRENT STATE AUDIT

**Method:** direct inspection of files, schemas, migrations, scripts, tests and stored artifacts on
2026-08-01. **No prior summary was relied upon.** Two prior claims were found to be wrong and are
corrected below.

---

## 1 · Asset register

| # | Expected asset | Classification | Evidence |
|---|---|---|---|
| 1 | **Research database `mip`** | **PERMANENTLY LOST** | 8.2 MB; **1 table** (`alembic_version`) with **0 rows**. All 86 schema tables absent |
| 2 | `mip_scratch` | **PERMANENTLY LOST** | 8.2 MB; 1 table, 0 rows |
| 3 | `mip_test` | **MISSING** | 47 MB allocated, **0 tables** — dropped, disk not reclaimed |
| 4 | **Migration chain** | **PRESENT AND VERIFIED** | **11 migrations**, single head `710af4aa92d0`, single root `5f5857c012a0`, chain walk = 11/11 **INTACT**. Rebuilt on a disposable DB → **86 tables** |
| 5 | Raw price/macro data | **RECONSTRUCTIBLE (approximate)** | Not in DB; re-ingestible from yfinance/FRED. **Not vintage-identical** — see recovery plan |
| 6 | **Validation artifacts** | **PRESENT AND VERIFIED** | 181 MB, 80 artifact files. `analogue_v1` 103 MB · `conditional_v1` 78 MB. Byte-verified in the restore drill |
| 7 | **Generated reports archive** | **PRESENT AND VERIFIED** | 4.7 MB, 4 dated trees + institutional examples |
| 8 | Immutable research snapshots | **MISSING** | Phase 2A `research_dataset_snapshot` table existed in schema; **no rows survive**. No snapshot files on disk |
| 9 | **Prediction archive** | **PERMANENTLY LOST** | `predictions` / `prediction_outcomes` tables gone with the DB. No export exists |
| 10 | Experiment manifests | **PRESENT (partial)** | `data/validation/conditional_v1/manifest.json` present. Definition-level registry in `research/experiments/registry.py`. **No execution-level run store** |
| 11 | **Backup scripts** | **MISSING → NOW PRESENT** | **None existed.** `tools/ops/backup.sh` created and executed this session |
| 12 | **Restore scripts** | **MISSING → NOW PRESENT** | **None existed.** `tools/ops/restore.sh` created and drilled |
| 13 | **Checksum infrastructure** | **MISSING → PARTIAL** | No repo-wide checksum tooling existed. Backup bundles now carry `CHECKSUMS.sha256`. Phase 1 manifest generated |
| 14 | **Evidence sources** | **PRESENT AND VERIFIED** | 9 in `ALL_MODELS`; 7 official, 2 shadow (`historical_analogues`, `conditional_probability`) |
| 15 | Portfolio CSVs | **PRESENT AND VERIFIED** | `peter_real_opening_balances_2026-07-16.csv` + unsupported positions |
| 16 | **PIT controls** | **PRESENT BUT UNVERIFIED** | `validation/eligibility.py` (embargo), `tests/integration/test_pit_alignment.py`, `tests/unit/test_feature_pit.py`. **Cannot execute — the poisoning test requires DB data that no longer exists** |
| 17 | Test suite | **PRESENT BUT UNVERIFIED** | 782 test functions. Unit tests runnable; **integration suite cannot pass without data** |
| 18 | Phase 1 study artifacts | **PRESENT AND VERIFIED** | 21 documents + 2 tools; all 23 hashed |
| 19 | PIT fundamentals snapshot (2026-07-04) | **PERMANENTLY IRRECOVERABLE** | Single vintage; yfinance cannot supply historical vintages |
| 20 | Offsite backup copy | **MISSING** | Local bundle only. See BACKUP_POLICY.md §4 |

## 2 · Corrections to prior documents

| Claim | Where | Actual | Status |
|---|---|---|---|
| "the 16 migrations in `alembic/versions`" | V4 repository/roadmap docs, program memory | **11 migrations** | **CORRECTED** |
| `verify_reports.py` runs anywhere | implied by the frozen-tool status | Required Python ≥3.10 (`D \| None` without `__future__`) | **DEFECT FOUND AND FIXED** — see §3 |

## 3 · Defect found during Stage 0

**S0-D01 — verifier portability.** `tools/phase1/case_facts.py` used PEP 604 annotations without
`from __future__ import annotations`, so it raised `TypeError` on Python 3.9. The tool had only ever
been executed under the 3.11 venv.

- **Severity:** would have blocked verification on any machine with an older interpreter, including a
  restored environment.
- **Fix:** one behaviour-neutral import added. Verified on **Python 3.9 → exit 0** and **3.11 → exit 0**.
- **Negative control re-run after the fix:** defect injected → **exit 1**, 1 failure detected;
  restored → **exit 0**.
- **Caught before hashing**, which is the purpose of Stage 0.

## 4 · What is verifiably intact

1. **The schema is fully reconstructible** — 11/11 chain, rebuilds to 86 tables.
2. **All research artifacts survive** — 194 MB byte-verified through a real backup/restore cycle.
3. **All evidence-source code survives** — 9 models, 782 test functions.
4. **All Phase 1 study artifacts survive** and are hash-pinned.

## 5 · What is verifiably gone

1. **Every row of research data.**
2. **The prediction archive** — the immutable decision history the reliability loop was to feed on.
3. **The single PIT fundamentals vintage** — permanently, with no substitute.
4. **Any ability to run the PIT poisoning test** until data is re-ingested.
