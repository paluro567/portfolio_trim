# RESEARCH DATA RECOVERY PLAN

**Reconstructed data is never treated as identical to the original.** Every row states expected
fidelity and the specific way a reconstruction differs.

---

## A · Exact reconstruction possible

| Asset | Source | Method | Fidelity | Time |
|---|---|---|---|---|
| **Database schema** | 11 migrations in-repo | `alembic upgrade head` | **EXACT** — verified: 86 tables | 5 min |
| **Trading calendar** | migration seed data | replay | **EXACT** | included |
| **Reference data** (sectors, instrument defs) | `universe.yaml` + reference migration | replay | **EXACT** | 30 min |
| **Portfolio ledger** | `peter_real_opening_balances_2026-07-16.csv` | `mip portfolio import` | **EXACT** — the CSV is the original input | 1 h |
| **FIFO lots / position snapshots** | derived from the ledger | replay-deterministic engine | **EXACT** — the engine is replay-deterministic by construction | 30 min |

## B · Approximate reconstruction only

| Asset | Source | Method | **How it differs from the original** | Time |
|---|---|---|---|---|
| **Daily prices** | yfinance | re-ingest 16 y × ~78 symbols | **Vendor has since revised.** `adj_close` is continuously recomputed; split/dividend factors drift. A re-ingest today produces *today's view of history*, not the view held on the original ingest date. **Materially different for adjusted series, near-identical for raw OHLC** | 4–6 h |
| **Corporate actions** | yfinance | re-ingest | Same revision exposure; back-filled corrections may now be present that were not before | included |
| **Macro observations** | FRED | re-ingest 18 series, 16 y | **FRED revises.** The platform stores publication-lagged values, but a re-ingest captures *current vintages*, not the vintages as published. **PIT integrity is weakened unless ALFRED vintages are used** | 2 h |
| **Feature store** | recomputed from prices + macro | `mip update --from-stage features` | Inherits every upstream revision. **Feature values will not match the originals exactly** | 3–4 h |
| **Benchmark series** | yfinance | re-ingest | Same revision exposure | included |

> **The distinguishing property of class B: the reconstruction is scientifically usable but is NOT the
> same dataset.** Any study re-run on reconstructed data must be reported as a *new* study, never as a
> reproduction of the original.

## C · Permanently irrecoverable

| Asset | Why | Consequence |
|---|---|---|
| **PIT fundamentals snapshot (2026-07-04)** | A single vendor vintage captured once. yfinance cannot supply historical vintages, and no archive was taken | `valuation` remains inert. Fundamental evidence requires a **new** vendor with true vintages. **Roughly one year of daily snapshots would be needed to rebuild an equivalent from scratch** |
| **Prediction archive** (`predictions`, `prediction_outcomes`) | Immutable append-only store, destroyed with the DB. No export exists | **The reliability feedback loop has no history to learn from.** `what_changed` has no baseline. Terminal-wealth disclosure stays "not available" (A-004) until a new archive accumulates |
| **Original ingestion-run lineage** | `ingestion_runs`, `data_quality_issues` rows | Provenance of the original data is unrecoverable. Any re-ingest carries new run ids that cannot be reconciled to the old ones |
| **Original feature-store values** | Derived from the pre-revision price/macro state | The exact numbers behind the 2026 studies cannot be regenerated |
| **`mip_test` / `mip_scratch` contents** | Dropped | No research value; noted for completeness |

## D · Not needed for V5 or V6

| Asset | Why not needed |
|---|---|
| Prediction archive | V5 tests **descriptive** reliability — does a source describe state correctly. It does not consult past predictions |
| PIT fundamentals | `valuation` is **not a V5 candidate** (100% neutral, nothing to verify) |
| Original run lineage | V5/V6 are new studies with new lineage |
| Original feature values | V5 recomputes features; V6 injects synthetic signal |
| Terminal-wealth history | Not an input to either |

**Consequence: V5 and V6 can proceed on reconstructed (class B) data without scientific compromise**,
because neither claims continuity with the destroyed studies.

## Scientific-equivalence statement

| Question | Answer |
|---|---|
| Can the 2026 studies be reproduced? | **No.** Class B revision exposure makes exact reproduction impossible |
| Can equivalent *new* studies be run? | **Yes** — with the caveat that they are new studies |
| Is V5 compromised by reconstruction? | **No** — it tests description against an independent path, both computed from the same reconstructed inputs |
| Is V6 compromised? | **No** — it injects a signal we control; the MDE is a property of the pipeline, not of the vintage |
| Is a future V7 compromised? | **Yes, if run on reconstructed free data.** V7 requires survivorship-clean vendor data by definition |

## Recommended recovery sequence

| # | Step | Class | Time | Blocking for |
|---|---|---|---|---|
| 1 | Rebuild schema | A | 5 min | everything |
| 2 | Reference data + universe | A | 30 min | prices |
| 3 | Re-ingest prices (~78 symbols, 16 y) | B | 4–6 h | features, V5, V6 |
| 4 | Re-ingest macro (18 FRED series) | B | 2 h | rates/macro sources |
| 5 | Recompute feature store | B | 3–4 h | **V5 Experiment 001** |
| 6 | Import portfolio ledger | A | 1 h | measurement layer |
| 7 | **Backup immediately after** | — | 15 min | protects the rebuild |

**Total ≈ 12–15 hours**, inside the 40-hour pre-G1 ceiling with the ~11 hours already spent on audit,
tooling and drill.
