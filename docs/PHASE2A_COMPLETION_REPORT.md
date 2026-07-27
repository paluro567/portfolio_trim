# Phase 2A — Completion Report & Deliverables

Native survivorship-clean outcome foundation & migration guardrails. Companion to
[PHASE2A_NATIVE_OUTCOMES.md](PHASE2A_NATIVE_OUTCOMES.md). **Phase 2A establishes the
native outcome and provenance foundation. It does not migrate production feature
families (Phase 2B) and does not prove the Trim Score has predictive value.**

---

## 1. Repository Assessment (what existed / what was reused)

**Reused, not duplicated:**
- Phase 1 `security_master` + identity/lifecycle/**`delisting_event`** (whose
  nullable `delisting_return`/`terminal_price`/`cash_amount`/`successor_security_id`
  Phase 2A now complements) + universe tables — the canonical `security_id` spine.
- `IngestionRun` audit spine (`error_detail` JSONB manifest), `DataQualityIssue` +
  `IssueSeverity`/`IssueStatus` quarantine ledger, `RunStatus`.
- The Phase-1 adapter pattern (`SecuritySource` Protocol + frozen DTOs +
  `FixtureSource` + `blocked_source()`), mirrored exactly for outcomes.
- Conventions: `_text_enum` (TEXT+CHECK), `NAMING_CONVENTION`, `session_scope`,
  BigInteger→BIGSERIAL PKs, raw-SQL run_type CHECK swap, Typer CLI groups, and the
  definition-level `ExperimentSpec` registry (`research/experiments/registry.py`).

**Confirmed present & deliberately NOT changed:** legacy `daily_prices`,
`corporate_actions`, `company_fundamentals`, `earnings_observations`,
`feature_store_daily` (still `instrument_id`-keyed), `predictions`/
`prediction_outcomes`. No production scoring path was touched.

**Added:** 13 tables, new enums, the `mip/research_data/` package, the
`mip research-data` CLI, an integration suite, and this documentation.

## 2. Schema & Migration Summary

Migration `710af4aa92d0` (down_revision `fba564e9cd38`), purely additive; extends
the `ingestion_runs` run_type CHECK to add `bridge`, `research_prices`,
`research_outcomes`, `research_snapshot`, `experiment`. Tables added:

`instrument_security_map`, `security_price_daily`, `security_market_snapshot`,
`benchmark_return_daily`, `security_return_daily`, `terminal_outcome`,
`forward_return`, `research_dataset_snapshot`, `experiment_run`,
`experiment_run_metric`, `experiment_run_decision`, `feature_parity_record`,
`data_divergence_record`. Round-trip verified: upgrade → downgrade (to Phase 1 and
to base) → re-upgrade, all clean. The downgrade drops dependent tables first, then
removes orphaned Phase-2A `ingestion_runs` + their `data_quality_issues`, then
reverts the CHECK — so per-test teardown is safe. `test_migrations.py`
`REFERENCE_TABLES` updated with the 13 tables.

## 3. Native Outcome Architecture

See [PHASE2A_NATIVE_OUTCOMES.md §2–3](PHASE2A_NATIVE_OUTCOMES.md). Prices
(`security_price_daily`) → canonical daily returns (`security_return_daily`, with
`return_status`) → delist-aware forward outcomes (`forward_return`, with
`outcome_status`), benchmark-/sector-relative via `benchmark_return_daily`,
terminal valuation via `terminal_outcome`, materialized into an immutable checksummed
`research_dataset_snapshot`. All keyed on `security_id`; delisted names and terminal
outcomes are preserved, never dropped.

## 4. Identity Bridge Report

`instrument_security_map` is now first-class (PIT validity intervals, `mapping_method`,
`confidence`, `status`, full lineage). `BridgeIngestor` enforces: no overlapping
ACTIVE mappings per instrument; ambiguous (overlapping, different-security) mappings
quarantined with a DQ issue; ticker equality alone never establishes identity;
non-overlapping reuse across periods allowed; manual overrides explicit and
superseding. `BridgeRepository` provides as-of resolution both directions, coverage
validation, quarantine listing, and overlap-violation reporting. Tested for
as-of correctness and quarantine.

## 5. Provider Adapter Report

Vendor-independent `OutcomeSource` Protocol + frozen DTOs
(`SourcePriceBar`/`SourceMarketSnapshot`/`SourceBenchmarkBar`/`SourceTerminal`),
keyed by the vendor permanent id. `FixtureOutcomeSource` (deterministic,
delisting-inclusive) is the only concrete adapter; `blocked_outcome_source()` raises
loudly. **Approved posture recorded:** Norgate (primary) + Sharadar (PIT/cross-check),
CRSP optional audit. **BLOCKED:** no real vendor licensed; yfinance is never
substituted and called survivorship-clean. Provider-specific columns stay outside the
canonical model.

## 6. Experiment Provenance Report

`experiment_run` (+ metric + decision) records each execution bound to its exact
inputs and integrity stamps; `ExperimentProvenance.start_run` validates the stamp up
front (complete + native), so runs cannot be opened under-provenanced; runs
auto-number per experiment. Every research result traces to one immutable record.
Tested end to end (stamps, metric, decision, auto-increment).

## 7. Integrity Guardrail Report

`mip.research_data.guardrails` — typed exceptions, fail-loud. Blocks: legacy
feature ⋈ native outcome (`MixedIdentityWorldError`, the critical prohibition);
non-native-labeled-native; mixed snapshot checksums; mismatched universe versions;
unreconciled data versions; missing stamps; legacy ticker join without PIT
resolution; unexplained material divergence. See
[PHASE2A_NATIVE_OUTCOMES.md §8](PHASE2A_NATIVE_OUTCOMES.md). Tested (mixed-world,
checksum, universe-version, unexplained-divergence all raise).

## 8. Two-Track Parity Report

Track 1 (`ComputationParity` → `feature_parity_record`): identical inputs, legacy vs
native, exact/tolerance, unexplained mismatch fails. Track 2 (`DivergenceLedger` →
`data_divergence_record`): classify + explain each difference; `unknown`/`unexplained`
blocks promotion via `assert_no_unexplained_divergence`. A smaller post-clean edge is
expected, classified under `delisting_inclusion`/`universe_difference`, not a defect.

## 9. Test Report

`tests/integration/test_native_outcomes.py` — **25 scenarios, all passing** (fresh
DB, default and no-randomly order). Coverage maps 1:1 to the required list: native
`security_id` prices; ticker change across a window; ticker reuse non-contamination;
delisted loser retained; cash acquisition; stock-acquisition successor; bankruptcy
terminal; missing-terminal → unresolved (not deleted); split-adjusted; dividend-
adjusted; computation equivalence; divergence classified; unexplained divergence
blocks; legacy⋈native raises; checksum mismatch raises; universe-version mismatch
raises; experiment-run provenance; rebuilt-snapshot identical checksum; different
data_version distinct snapshot; delisted survive reconstruction; PIT-only market
rules; no silent removal; bridge as-of; ambiguous bridge quarantined; migration
additive/rollback-safe. `test_migrations.py` `REFERENCE_TABLES` updated (green).

**Unresolved gaps (by design, not defects):** all real-vendor acceptance is blocked
on licensing; residual/factor returns and native feature computation are Phase 2B;
full sector-relative returns need a sector-benchmark map.

_Note: an intermediate full-suite run showed a cascade of setup errors traced to a
`mip_test` database left dirty by a manually-interrupted run; on a freshly recreated
database the suite is green. Always run the integration suite against a clean
throwaway database._

## 10. Phase 2A Completion Report

**Complete:** native `security_id` prices/market/returns/forward-outcomes; delist &
terminal handling (never dropped, never zero-assumed); first-class PIT bridge with
quarantine; execution-level provenance; explicit integrity stamps; fail-loud
guardrails; two-track parity scaffolding; reproducible checksummed snapshots; CLI;
docs; tests.

**Blocked:** real survivorship-clean vendor ingestion (Norgate + Sharadar licensing).

**Acceptance criteria:** all mandatory criteria pass — native prices keyed by
`security_id`; delisted securities retained in outcome generation; terminal events
explicit; missing exit prices never silently delete; bridge PIT + tested; ambiguous
bridge quarantined; experiment runs persist full provenance; every result carries
integrity/version stamps; invalid legacy/native joins fail loudly; computation-
equivalence and divergence-classification infrastructure exist; unexplained
divergence blocks promotion; snapshot generation reproducible (same inputs → same
checksum); tests cover ticker change/reuse, delisting, bankruptcy, acquisitions,
splits, dividends, mixed-world rejection, and provenance; production scoring
unchanged; docs identify the blocked real-provider integration.

**May Phase 2B (native price-feature computation) begin?** **Yes.** The outcome
foundation, identity bridge, provenance, guardrails, and parity scaffolding are in
place, so Phase 2B can compute price-derived features natively and run computation
parity against the legacy path — provided (a) real prices are still gated on vendor
licensing and (b) Phase 2B honors the guardrails (native features only against native
outcomes). Phase 2A makes scientifically invalid combinations structurally
impossible; it does not itself validate any signal.
