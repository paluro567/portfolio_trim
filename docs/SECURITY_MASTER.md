# Security Master & Universe Integrity (Phase 1)

Point-in-time, survivorship-clean identity for historical research. This is
**evaluation infrastructure**, not a predictive signal: it changes *which
securities and which point-in-time facts research is allowed to see*, and it
touches no production scoring, weights, or models.

> **Why this phase exists.** The prior research program concluded that the
> apparent Trim-Score edge could not be trusted because the evaluation universe
> was survivor-only and identity was keyed on the *current* ticker. Any backtest
> built on that foundation silently excludes failed companies and misattributes
> one company's history to whoever holds its ticker today. Phase 1 removes that
> confound at the source.

---

## 1. Identity model — the ticker is never identity

Every security has a permanent internal **`security_id`** (surrogate BIGINT).
It is minted once and never reused, reassigned, or derived from any market
identifier. Tickers, CUSIPs, ISINs, FIGIs and vendor ids are *attributes that
change over time*, recorded with validity intervals — not keys.

Two facts make the ticker unusable as identity, and both are represented:

- **Tickers change.** A company renames `OLD → NEW`; both map to the same
  `security_id` over their respective date ranges.
- **Tickers are reused.** After a company delists, a *different* company can
  later take its old ticker. `OLD` before 2020 and `OLD` after 2021 can be two
  distinct `security_id`s, disambiguated purely by the as-of date.

The natural key `(source, source_security_id)` anchors idempotency and
resolution: re-ingesting the same vendor record updates the same `security_id`
in place; a record with no permanent vendor id is **quarantined**, never merged
on ticker.

### Point-in-time rule

Every interval column follows `valid_from <= as_of < valid_to`, with
`valid_to IS NULL` meaning "still current". There is deliberately **no
`current_ticker()` accessor** — historical code must ask "what was this as of
date D", because that is the only question with a survivorship-safe answer.

---

## 2. Schema (7 tables)

Migration `fba564e9cd38` (`phase1 security master and universe integrity`),
purely additive on top of the existing schema; it also widens the
`ingestion_runs.run_type` CHECK to include `securities` and `universe` so the
existing audit spine carries Phase-1 build manifests.

| Table | Grain | Purpose |
|---|---|---|
| `security_master` | one row per `security_id` | permanent identity + current status (type, exchange, first/last trade, delisted flag) |
| `security_identifier_history` | `(security_id, identifier_type, valid_from)` | every ticker/CUSIP/ISIN/FIGI the security ever held, with `[valid_from, valid_to)` and exchange |
| `security_lifecycle_event` | `(security_id, event_type, effective_date)` | listed / renamed / exchange-changed / acquired / merged / bankrupt / spun-off, with successor/predecessor links |
| `delisting_event` | one row per delisted `security_id` | delisting date, code, reason, successor. `delisting_return` / `terminal_price` are **nullable, PENDING Phase 2** |
| `universe_definition` | `(name, version)` | versioned, immutable machine-readable eligibility policy |
| `universe_membership` | `(universe_definition_id, security_id, membership_date)` | reconstructed PIT membership per reconstitution date |
| `historical_classification` | `(security_id, scheme, valid_from)` | as-of GICS sector/industry (classifications drift, so they are dated) |

Every row carries `source`, `ingestion_run_id`, and `data_version` lineage.
Key integrity constraints: `security_master` UNIQUE `(source,
source_security_id)` and CHECK `delisting_date >= first_trade_date`;
`security_lifecycle_event` CHECK successor ≠ self; `universe_definition` UNIQUE
`(name, version)`.

Surrogate PKs are BIGINT and become `BIGSERIAL` automatically (verified against
the existing `ingestion_runs.id` sequence pattern).

---

## 3. Identity resolution (deterministic, never auto-merges on ticker)

`SecurityMasterIngestor.ingest(source)` resolves each source record in one pass:

1. **No `source_security_id`** → quarantine `missing_permanent_id`. Nothing
   without a stable vendor identity is allowed to mint or match a security.
2. **Get-or-create** by `(source, source_security_id)` — the idempotency anchor.
3. **Permanent-identifier conflict.** If a CUSIP/ISIN/FIGI in the record is
   already held by a *different* `security_id` over an **overlapping** interval
   (`a_from <= b_to AND b_from <= a_to`, open ends → `9999-12-31`), the record is
   quarantined `ambiguous_identity`. We never guess which security is "right".
4. Otherwise upsert children (identifiers, lifecycle, delisting, classification)
   by natural key. Successor/predecessor references are resolved from the
   vendor's source ids to internal `security_id`s.

Quarantine uses the existing `data_quality_issues` ledger (severity `ERROR`),
so ambiguous identity is *surfaced and reviewable*, not dropped on the floor.
Delisted / inactive securities are always retained.

---

## 4. Universe policy (versioned & immutable)

`UniversePolicy` is a frozen dataclass serialized to
`universe_definition.eligibility_rules_json`. The shipped policy is
**`US_COMMON_EQUITY_V1`**:

- US common equity only (`SecurityType.COMMON`); ETFs, preferred, warrants,
  rights, units, and closed-end funds excluded by type; **ADRs excluded
  explicitly** (a policy choice, recorded, not an accident of missing data).
- Exchanges: NYSE, NASDAQ, NYSE American / AMEX.
- Minimum trading age: 252 trading days (~1 year) before eligibility.
- Monthly reconstitution cadence.
- **PENDING Phase 2** (recorded in `source_requirements_json.pending_phase2`,
  not silently applied): `min_price`, `min_market_cap`, `min_dollar_volume`.
  These need price/fundamental history that Phase 1 does not yet load, so they
  are declared but inert — a backtest cannot accidentally rely on them.

`register()` freezes a definition on first write; re-registering the same
`(name, version)` returns the frozen row unchanged, and any attempt to alter a
frozen policy raises — **rules change only by bumping the version**.

`build(policy, membership_dates)` evaluates each security's eligibility as of
each date using only `<= as_of` information (PIT ticker/exchange/type), writes
the included members, and records a manifest on a `universe` ingestion run:
input/included counts, `excluded_by_reason` tally, and a **deterministic sha256
checksum** over the sorted `(date, security_id)` set. Same frozen definition +
same data version ⇒ identical checksum.

---

## 5. Source-adapter contract (vendor-independent; real vendor BLOCKED)

`SecuritySource` is a `Protocol` (`name`, `data_version`, `securities()`,
`constituents()`) over frozen DTOs (`SourceSecurity`, `SourceIdentifier`,
`SourceLifecycleEvent`, `SourceDelisting`, `SourceClassification`,
`SourceConstituent`). Ingestion depends only on this contract, so a licensed
vendor is a drop-in adapter.

- `FixtureSource` — an in-memory adapter used by tests and by the CLI demo
  (`mip.securities.demo.demo_source`).
- `blocked_source()` — raises `ConfigurationError` with guidance. There is **no
  default real adapter**, by design: a free, survivor-only feed must never be
  wired in and passed off as survivorship-solved.

**Data limitation (must stay visible):** no survivorship-clean vendor is
licensed yet. Candidates evaluated: Norgate, Sharadar (Nasdaq Data Link), CRSP.
Until one is licensed and adapted, the security master contains only demo/test
data — real historical research is blocked on that procurement, *not* on this
code.

---

## 6. Data-quality framework

`check_security_master(session)` and `check_universe_membership(session,
definition_id)` return structured `Finding`s (read-only; they detect, they do
not mutate):

- `identifier_shared_over_overlap` — same identifier value held by two
  securities over overlapping intervals.
- `delisted_without_event`, `delisting_before_listing`,
  `classification_after_delisting`.
- `membership_after_delisting`, `membership_before_listing`.

These complement the ingest-time quarantine ledger: quarantine stops bad
identity from loading; the checks audit what did load.

---

## 7. Interfaces

### PIT repository (`SecurityRepository`)

All time-varying lookups require an `as_of` date: `resolve_ticker`,
`resolve_identifier`, `ticker_as_of`, `identifiers_as_of`, `lifecycle_as_of`,
`classification_as_of`, `delisted_between`, `members_as_of`, `is_eligible`.

### CLI (`mip securities …`)

| Command | Purpose |
|---|---|
| `mip securities ingest --fixture` | load the deterministic demo snapshot (real vendors blocked) |
| `mip securities list [--as-of D] [--active-only]` | securities with ticker as-of D; delisted shown by default |
| `mip securities show <id> [--as-of D]` | full PIT picture of one security |
| `mip securities resolve <ticker> --as-of D` | ticker → `security_id` as of D (reuse-safe) |
| `mip securities lifecycle <id> [--as-of D]` | PIT lifecycle events |
| `mip securities universe definitions` | list versioned definitions |
| `mip securities universe build --date D [--date D …]` | reconstruct membership + manifest |
| `mip securities universe members <def-id> --as-of D` | reconstruct membership as of D |
| `mip securities universe validate [--definition-id N]` | run DQ checks; non-zero exit on findings |

> The PIT universe commands are nested under `mip securities universe` because
> the top-level `mip universe` group already denotes the (separate) scoring
> universe. Same word, different concept — kept apart deliberately.

---

## 8. Test report

`tests/integration/test_security_master.py` (8 tests, all passing) proves the
acceptance scenarios against a real throwaway PostgreSQL over a 15-security
fixture covering: same-ticker, ticker change `OLD→NEW`, ticker reuse by a
different security, cash acquisition, stock acquisition (successor linked),
bankruptcy, exchange transfer, two share classes, spin-off (predecessor
linked), an ETF (universe-excluded), a CUSIP conflict (quarantined), and a
record with no permanent id (quarantined).

Verified end to end: 13 created / 2 quarantined; PIT ticker, exchange and
classification resolution; ticker reuse disambiguation; successor/predecessor
resolution; `delisted_between`; idempotent re-ingest (0 created / 13 updated,
no new rows); `data_version` lineage v1→v2 with identity preserved;
**survivorship** (a company that went bankrupt in 2018 is present in the 2016
reconstruction); membership never extends past delisting and never before
listing; **reproducibility** (identical checksum on rebuild); and clean DQ
checks. Unit suite: 528 passed, no regressions.

---

## 9. Acceptance criteria

**Verdict: Phase 1 engineering is COMPLETE.** All 14 acceptance criteria below
pass against a real PostgreSQL. Phase 2 *may begin* — but note that Phase 2 is
gated on a data-procurement decision (a licensed survivorship-clean vendor),
not on further work in this layer. Until that vendor is adapted, the master
holds only fixture/demo data and must not be presented as research-ready.

| Criterion | Status |
|---|---|
| Stable internal identity per security | ✅ `security_id`, never ticker |
| Ticker changes represented | ✅ identifier history intervals |
| Ticker reuse supported | ✅ as-of interval resolution |
| Delisted/inactive securities representable | ✅ retained + `delisting_event` |
| Lifecycle events point-in-time | ✅ `security_lifecycle_event` |
| Universe definitions versioned & immutable | ✅ frozen `(name, version)` |
| Membership reconstructable for a historical date | ✅ `members_as_of` |
| Membership never extends beyond delisting | ✅ enforced + DQ-checked |
| Historical lookups require as-of dates | ✅ no current-state accessor |
| Ambiguous matches quarantined | ✅ `ambiguous_identity` |
| Every record has source lineage + data_version | ✅ on all 7 tables |
| Reproducible builds | ✅ deterministic checksum |
| Tests cover failed/acquired/delisted/renamed | ✅ 8 integration tests |
| Docs state remaining data limitations | ✅ §5 (vendor BLOCKED) |

---

## 10. Phase 2 dependencies (what is deliberately NOT here)

Phase 1 builds *structure*. It does not yet load the data some structure
awaits:

- **Licensed survivorship-clean vendor** — the top blocker; everything real
  depends on it (§5).
- **Delisting returns & terminal prices** — columns exist, nullable; needed to
  measure the actual cost of failure without look-ahead.
- **Price / market-cap / liquidity history** — required to *activate* the
  `min_price` / `min_market_cap` / `min_dollar_volume` filters currently marked
  PENDING (§4).

Until a licensed vendor is adapted, this phase should be treated as a validated
skeleton: the identity, PIT, universe, reproducibility, and quarantine
machinery are proven on fixtures, and real research remains gated on data
procurement rather than on further engineering here.
