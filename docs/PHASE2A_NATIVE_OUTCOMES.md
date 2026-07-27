# Phase 2A — Native Outcome Foundation & Migration Guardrails

**Status:** implemented (schema + services + CLI + tests). **Scope guard:** Phase
2A establishes the native outcome and provenance foundation. **It does NOT migrate
production feature families (that is Phase 2B) and does NOT prove the Trim Score
has predictive value.** Nothing here changes production scoring, model weights, or
the Trim Score. The real survivorship-clean vendor feed remains **BLOCKED** pending
licensing; only the deterministic fixture/demo source is available.

Predecessors: [PHASE2_DESIGN.md](PHASE2_DESIGN.md),
[PHASE2_ARCHITECTURE_REVIEW.md](PHASE2_ARCHITECTURE_REVIEW.md),
[PHASE3_IDENTITY_MIGRATION.md](PHASE3_IDENTITY_MIGRATION.md), and Phase 1
([SECURITY_MASTER.md](SECURITY_MASTER.md)).

---

## 1. What Phase 2A builds (and why)

The architecture review's top risk (R1) was that outcomes were being cleaned while
signals stayed survivor-biased and on the legacy `instrument_id`, joined across an
untrusted seam. Phase 2A lays the *outcome + provenance + guardrail* foundation so
that, when native feature computation begins (Phase 2B), a scientifically invalid
combination is **structurally impossible**:

- native, survivorship-clean prices/returns/forward-outcomes keyed on the permanent
  `security_id`;
- delisted/inactive securities and terminal outcomes preserved, never dropped;
- a first-class, point-in-time identity bridge with quarantine;
- execution-level experiment provenance (every result → one immutable run record);
- integrity/version stamps on every artifact;
- hard join guardrails that fail loudly on legacy⋈native mixes;
- two-track parity scaffolding (computation equivalence + data-divergence).

## 2. Canonical native outcome architecture

All tables key on `security_id`; every row carries `source` + `data_version` +
`ingestion_run_id` lineage. Natural keys include `source` + `data_version` so
multiple vendor snapshots coexist for cross-check without collision.

- **`security_price_daily`** — raw OHLC + `adjusted_close` + total-return/split
  factors + dividend amount. NEVER keyed by ticker or instrument_id.
- **`security_market_snapshot`** — PIT price, shares, market cap, dollar volume,
  exchange, security_type, sector. Activates the Phase-1 PENDING universe filters
  (price/market-cap/liquidity/investability) using only as-of values.
- **`benchmark_return_daily`** — `MARKET` / `SECTOR:<gics>` daily total returns for
  benchmark- and sector-relative outcomes (identity-neutral).
- **`security_return_daily`** — canonical daily total return with an explicit
  `return_status` (normal / corporate_action / delisting / terminal / missing /
  unresolved).
- **`terminal_outcome`** — the deterministic terminal valuation (see §3).
- **`forward_return`** — reproducible per `(security_id, as_of_date, horizon)`
  outcome: absolute / benchmark-relative / sector-relative (residual nullable,
  deferred), `outcome_status`, and the full integrity stamp set.
- **`research_dataset_snapshot`** — immutable, checksummed materialization with
  explicit `identity_world` / `feature_world` / `outcome_world`, manifest, counts.

## 3. Terminal-event handling (never fabricated, never zero-assumed)

`terminal_outcome` records the **rule used**, resulting investor value, source,
confidence, and DQ status. Deterministic rules:

| Event | Rule | Valuation |
|---|---|---|
| Cash acquisition | `cash_acquisition` | investor cash consideration / vendor terminal return |
| Stock acquisition / merger | `stock_acquisition` / `merger` | successor relationship + resulting value |
| Bankruptcy / liquidation | `bankruptcy` / `liquidation` | vendor delisting return / terminal proceeds |
| Stopped trading before exit | `stopped_trading` | vendor terminal return |
| Unknown | `unknown` | **unresolved** — recorded, never assumed −100% |

In `forward_return`, a delisting inside the window sets `delisting_in_window_flag`
and yields `delisted_in_window` / `terminated`; an unknown terminal yields
`unresolved` with a NULL return — **the observation is never deleted**. A
still-listed name at the data edge is `truncated`; a name with no entry price is
`no_entry_price`. Every `(security, as_of, horizon)` cell is written exactly once.

## 4. First-class identity bridge

`instrument_security_map` (PIT, `valid_from`/`valid_to`, `mapping_method`,
`confidence`, `status`, full lineage). Rules enforced by `BridgeIngestor` +
`BridgeRepository`:

- resolution uses **ACTIVE** rows only, **as of** a date;
- **no two active mappings for one instrument overlap** in time;
- ticker equality alone never establishes identity (`pit_ticker` is recorded for
  review, not trusted for resolution);
- an overlapping mapping to a **different** security is **quarantined** (a DQ issue
  is filed), never auto-merged;
- one instrument may map to different securities across **non-overlapping** periods
  (legitimate ticker reuse);
- manual overrides are explicit (`manual_override`) and supersede prior rows.

Queries: `resolve_instrument`, `resolve_security`, `validate_coverage`,
`list_quarantined`, `overlap_violations`.

## 5. Provider adapter contracts

Vendor-independent frozen DTOs + `OutcomeSource` Protocol
(`prices`/`market_snapshots`/`benchmarks`/`terminals`), all keyed by the vendor's
permanent `source_security_id` (resolved to `security_id` via the Phase-1 natural
key). Provider-specific columns stay **outside** the canonical model.

- **Approved posture:** Norgate (primary survivorship-clean prices + delisting) +
  Sharadar (PIT market cap / cross-check); CRSP optional audit.
- **`FixtureOutcomeSource`** — deterministic, delisting-inclusive; tests + demo.
- **`blocked_outcome_source()`** — raises loudly; **yfinance/stooq are never
  substituted and called survivorship-clean**.

## 6. Experiment-run provenance

`experiment_run` (+ `experiment_run_metric`, `experiment_run_decision`) records that
a registered experiment RAN, bound to its exact inputs: `identity_world`,
signal/feature/outcome/universe/data versions, `snapshot_id` + `snapshot_checksum`,
`code_sha`, pre-registration & kill criteria → metrics + decision. Runs auto-number
per experiment. `ExperimentProvenance.start_run` validates the integrity stamp up
front, so a run cannot be opened under-provenanced. Every research result traces to
one immutable execution record.

## 7. Research integrity stamps

Persisted explicitly (never inferred from a table name): `identity_world`
(`legacy_instrument` | `native_security`), `feature_version`, `data_version`,
`universe_version`, `snapshot_checksum`, `code_sha`, `calculation_version`. Carried
on `forward_return`, `research_dataset_snapshot`, and `experiment_run`.

## 8. Hard join guardrails (fail loudly)

`mip.research_data.guardrails` — typed exceptions, never warnings:

| Prohibited combination | Guard | Exception |
|---|---|---|
| legacy feature ⋈ native outcome | `assert_worlds_joinable` | `MixedIdentityWorldError` |
| non-native outcome labeled native | `assert_native_outcomes` | `MixedIdentityWorldError` |
| mixed snapshot checksums in one run | `assert_single_snapshot` | `SnapshotChecksumMismatchError` |
| mismatched universe versions | `assert_universe_versions_match` | `UniverseVersionMismatchError` |
| mismatched data versions, no policy | `assert_data_versions_reconciled` | `DataVersionMismatchError` |
| missing integrity stamps | `IntegrityStamp.require_complete` | `MissingIntegrityStampError` |
| legacy ticker join w/o PIT resolution | `assert_no_legacy_ticker_join` | `LegacyTickerJoinError` |
| unexplained material divergence | `assert_no_unexplained_divergence` | `UnexplainedDivergenceError` |

The critical prohibition — legacy `feature_store_daily` + native `forward_return` /
research observation — is unconditional and covered by a test.

## 9. Two-track parity

- **Track 1 — computation equivalence** (`ComputationParity`, `feature_parity_record`):
  identical inputs through legacy and native code paths; exact or within a frozen
  tolerance; any unexplained mismatch fails (`passed=False`).
- **Track 2 — data-divergence characterization** (`DivergenceLedger`,
  `data_divergence_record`): each legacy-vs-native difference is attributed to a
  class (price-adjustment / dividend / split / delisting-inclusion / ticker-history
  / vendor-restatement / missing-legacy / universe-difference / CA-correction /
  unknown) and explained. An `unknown` class or `unexplained` review status is
  material-divergence-until-explained and **blocks promotion**.

A smaller apparent edge after survivorship-clean reconstruction is *expected*, not a
defect — it is characterized under `delisting_inclusion` / `universe_difference`.

## 10. Snapshot reproducibility

`ForwardOutcomeBuilder.build_snapshot` computes every outcome in memory, derives a
deterministic SHA-256 over the ordered `(security_id, as_of, horizon, status,
absolute_return)` tuples, persists rows stamped with that checksum, and freezes the
snapshot. `rebuild_checksum` recomputes from persisted rows; `mip research-data
snapshots verify` confirms the match. Same inputs ⇒ same checksum; a changed vendor
`data_version`/value ⇒ a distinct snapshot identity and checksum.

## 11. CLI

`mip research-data`: `data ingest|status`, `outcomes build|validate`,
`snapshots build|show|verify`, `parity computation|divergence`,
`experiments list|show`, `integrity`. `data ingest` without `--fixture` invokes the
blocked source and exits.

## 12. Known data limitations & Phase 2B dependencies

- **BLOCKED:** no licensed survivorship-clean vendor yet (Norgate + Sharadar). All
  real-data acceptance is gated behind procurement; the fixture proves the machinery.
- **Deferred to Phase 2B+:** residual/factor returns (`residual_return` nullable,
  present from day one); native feature computation and the `feature_world` becoming
  `native_security`; full sector-relative returns require a sector-benchmark map;
  cross-vendor auto-reconciliation beyond a sampled audit; re-keying production
  `predictions` onto `security_id`.
- Phase 2A does not claim the predictive system is validated.

---

### Deliverable pointers

Repository assessment, schema/migration summary, and the eight other required
reports are in [PHASE2A_COMPLETION_REPORT.md](PHASE2A_COMPLETION_REPORT.md).
