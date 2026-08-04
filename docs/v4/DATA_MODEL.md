# DATA MODEL

**Part 4 of the V4 brief.** Every dataset states owner, cadence, retention, versioning and PIT
obligation. PIT column: **HARD** = a look-ahead here invalidates research · **SOFT** = as-of desirable ·
**N/A**.

---

## 1 · Dataset register

| # | Dataset | Owner | Update | Retention | Versioning | PIT |
|---|---|---|---|---|---|---|
| D01 | `security_master` | Substrate | on vendor change | permanent | append-only identity history | **HARD** |
| D02 | `security_price_daily` | Market Data | daily EOD | permanent | `data_version` + revision log | **HARD** |
| D03 | `corporate_action` | Market Data | on event | permanent | `data_version` | **HARD** |
| D04 | `security_market_snapshot` (shares, mcap, ADV) | Market Data | daily | permanent | `data_version` | **HARD** |
| D05 | `fundamentals_pit` | Fundamentals | vendor vintage | permanent | **vintage-keyed, never restated** | **HARD** |
| D06 | `macro_observation` | Macro | per release | permanent | publication-lagged | **HARD** |
| D07 | `benchmark_return_daily` | Market Data | daily | permanent | `data_version` | **HARD** |
| D08 | `portfolio_transaction` | Portfolio | on trade | permanent | append-only ledger | **HARD** |
| D09 | `tax_lot` / `lot_closure` | Portfolio | derived on replay | permanent | FIFO replay-deterministic | **HARD** |
| D10 | `position_snapshot` | Portfolio | daily | permanent | guarded upsert, byte-identical rebuild | **HARD** |
| D11 | `policy_artifact` | Policy | on authored change | permanent | **semver, new row, never edited** | SOFT |
| D12 | `catalyst_event` | Evidence | on announcement | permanent | announcement date ≤ as_of | **HARD** |
| D13 | `evidence_claim` | Evidence | per run | permanent | source_version | **HARD** |
| D14 | `reliability_record` | Reliability | quarterly + on demotion | permanent | append-only | **HARD** |
| D15 | `historical_snapshot` | Snapshot | per research run | permanent | **sha256 content-addressed** | **HARD** |
| D16 | `research_run` | Research Archive | per run | permanent | bound to snapshot + code_sha | **HARD** |
| D17 | `position_decision` + `decision_trace` | Decision | per pipeline run | **permanent, immutable** | supersession, never edit | **HARD** |
| D18 | `evaluation_contract` | Decision | with each decision | permanent | immutable | N/A |
| D19 | `evaluation_result` | Evaluation | at horizon maturity | permanent | restatement-proof upsert | **HARD** |
| D20 | `rendered_report` | Report | per publication | permanent | pinned `snapshot_id` | N/A |
| D21 | `governance_event` | Governance | on cap/policy/promotion change | permanent | immutable | N/A |
| D22 | `calculation_result` | Calc | per decision | 24 months then prune | `input_hash` | **HARD** |
| D23 | `data_quality_issue` | Substrate | on detection | permanent | quarantine ledger | SOFT |

## 2 · Point-in-time contract

**Rule.** Every repository method takes `as_of: date`. There is **no** current-value accessor in
D01–D07 or D12–D14. Enforced by an interface test that reflects over all repository protocols.

**Three PIT hazards, and their controls:**

| Hazard | Control |
|---|---|
| Restated fundamentals | D05 is **vintage-keyed**. A restatement creates a new vintage; the old one is never overwritten. Queries select the vintage available at `as_of` |
| Revised prices | D02 keeps a revision log. A revision creates a new `data_version`; snapshots pin the version they read |
| Forward-looking catalysts | D12 stores `announcement_date`. Admissible only when `announcement_date ≤ as_of`, regardless of `event_date` |

**Gate:** the price-poisoning test — corrupt every post-`as_of` row, assert byte-identical output — runs
on every release. It is the platform's single most valuable inherited test.

## 3 · Snapshot and reproducibility model

```
HistoricalSnapshot
  snapshot_id            uuid
  content_hash           sha256 over the sorted observation payload
  as_of_range            (start, end)
  universe_version       fk
  data_versions          {dataset: version}
  identity_world         'native' | 'legacy'
  created_at, created_by
```

Content-addressed: identical inputs produce one stored snapshot regardless of how many runs reference
it. Directly addresses the V2-review storage risk (R5) without a separate dedup layer.

**Report reproducibility (risk R2):** `rendered_report` pins `snapshot_id`. Regeneration re-reads the
pinned snapshot. A data revision never mutates an archived report — it produces a new decision that
supersedes.

## 4 · Retention and pruning

| Class | Retention | Rationale |
|---|---|---|
| Decisions, traces, contracts, results, governance | **Permanent, immutable** | The falsifiability record. Deleting it destroys the platform's core asset |
| Prices, actions, fundamentals, macro | Permanent | Reproducibility of every past study |
| Snapshots | Permanent, content-addressed | Cheap once deduplicated |
| `calculation_result` | 24 months | Recomputable from inputs; a cache, not a record |
| Rendered reports | Permanent | Immutable artifacts |
| Vendor raw payloads | Per licence | May be non-redistributable |

**Backup is a first-class requirement, not an operational nicety.** The v1 platform permanently lost a
PIT fundamentals snapshot and its prediction archive. Automated offsite backup plus a scheduled restore
drill is a release gate in P0.

## 5 · Physical notes

- PostgreSQL. Alembic migrations, forward-only, with a `REFERENCE_TABLES` head assertion.
- Every fact table carries `source`, `data_version`, `ingestion_run_id`.
- Numeric money and weights are `NUMERIC`, never float. Report arithmetic uses `Decimal` end to end.
- `daily_prices.ingestion_run_id` is overwritten on revision — inherited gotcha; "rows by run" queries
  conflate insert and revise. Documented, not relied upon.
