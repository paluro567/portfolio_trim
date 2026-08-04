# BACKUP POLICY

**Status: IMPLEMENTED AND DRILLED 2026-08-01.** Prior state: no backup, restore or checksum
infrastructure of any kind existed.

---

## 1 · Scope

| Class | Contents | Why |
|---|---|---|
| **Database** | `pg_dump -Fc` of `mip` | Schema + all rows |
| **Immutable research artifacts** | `data/validation/` (181 MB) | **The only irreplaceable research asset that survives** |
| **Generated reports** | `data/reports/` | Historical output |
| **Raw CSV** | portfolio opening balances, unsupported positions | Only surviving portfolio input |
| **Study contract** | `docs/phase1/` | Frozen acceptance criteria |
| **Code** | `src/ alembic/ tools/ docs/v4/ docs/program/` | Reconstruction path for the schema |

## 2 · Cadence and retention

| Trigger | Retention |
|---|---|
| **Before any destructive operation** (drop, migrate, bulk ingest) | permanent |
| **Weekly** while any research runs | 8 weekly |
| **Before and after each program gate** | permanent |
| Monthly | 12 monthly |

**Research artifacts and gate-boundary bundles are never pruned.**

## 3 · Integrity

Every bundle carries `CHECKSUMS.sha256` over all artifacts and a `MANIFEST.txt` recording UTC
timestamp, git commit, working-tree dirty count, and migration count. **A restore verifies checksums
before touching any database and aborts on mismatch.**

## 4 · Offsite — OPEN

**Not yet implemented.** Bundles are local only, which does not protect against device loss.

| Requirement | Status |
|---|---|
| Encrypted offsite copy | ☐ **OPEN** |
| ≥1 copy on separate physical media | ☐ **OPEN** |
| Automated, not manual | ☐ **OPEN** |
| Cost ceiling $120/yr | within the approved Stage 0 line |

**This is the one Stage 0 control that is designed but not delivered.** It is reported as open, not as
complete.

## 5 · Guards

1. `restore.sh` **refuses** to target the live `mip` database. Exercised in the drill.
2. Restores default to `mip_restore_drill`.
3. Checksum verification precedes any write.
4. The backup runs regardless of database state — an empty database is still captured, with a
   `DB_MISSING.txt` marker when absent.

## 6 · Verification requirement

> **A backup is not considered working until a restore drill has passed.**
> First drill: 2026-08-01 — **PASS**, 194 MB byte-identical, 0 missing, 0 differing.
> **Second drill required after data re-ingestion** to prove behaviour at realistic volume.
