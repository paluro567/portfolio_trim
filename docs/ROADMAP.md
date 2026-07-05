# Implementation Roadmap

Companion to ARCHITECTURE.md (v2, frozen 2026-07-04).
Phases are strictly sequential; each ends with a gate: **all listed tests
pass before the next phase begins.** Phases 0–7 constitute the data platform
(current scope). Phases 8+ are the reserved future layers, included so the
platform phases can be verified against what they must eventually support —
they are NOT part of current scope.

---

## Phase 0 — Scaffold & Core Infrastructure

**Goal:** A running skeleton: environment, config, logging, database
connectivity, migrations, test harness, lint/format gates.

**Why it exists:** Every later phase assumes these exist. Retro-fitting
config or migrations after tables exist is how projects accumulate permanent
scar tissue.

**Deliverables:**
- uv project (`pyproject.toml`), Python 3.13, ruff + black configured and agreeing on line length
- `core/config.py` (Pydantic Settings: DB URL, FRED key, RawData root, retry policy, history start date), `.env.example`
- `core/logging.py` (structlog, JSON + console renderers)
- `core/db.py` (engine/session factory), `core/retry.py`, `core/exceptions.py`
- Alembic wired to the SQLAlchemy metadata; empty baseline migration
- Typer CLI entry point with `mip --version` and `mip db upgrade`
- Folder skeleton including empty reserved packages (`research/`, `models/`, `engine/`, `api/`)
- pytest layout (`tests/unit`, `tests/integration` with throwaway-Postgres fixture)

**Dependencies:** none.

**Database changes:** none (baseline migration only).

**Packages/modules:** `mip.core.*`, `mip.cli.main`.

**Gate tests:**
- Settings load from env and `.env`; missing required setting fails loudly with a clear error
- Session fixture connects, commits, rolls back against throwaway Postgres
- `alembic upgrade head` and `downgrade base` both succeed on an empty DB
- Retry decorator: retries transient errors with backoff, gives up at max attempts, does not retry permanent errors
- `ruff check` and `black --check` clean; CI-style `pytest` green

---

## Phase 1 — Reference Data Layer

**Goal:** The identity spine: instruments, classification, symbol history,
trading calendar, seeded with the actual universe (holdings + SPY + sector
ETFs + index benchmarks).

**Why it exists:** Every fact table keys on `instrument_id`; every cursor and
alignment rule joins the trading calendar. Nothing can be ingested until
identities exist.

**Deliverables:**
- ORM models + migration for reference tables
- `reference/universe.py`: idempotent seed from a versioned YAML/CSV universe definition (symbols, types, industry/sector, sector→ETF instrument links)
- `reference/calendar.py`: trading-calendar builder (exchange calendar source), `mip calendar build --from 2010`
- `repositories/instruments.py`
- CLI: `mip universe seed`, `mip universe list`

**Dependencies:** Phase 0.

**Database changes:** `sectors`, `industries`, `instruments`,
`symbol_history`, `trading_calendar` (note: `sectors.etf_instrument_id` FK
is added after `instruments` exists — circular reference resolved in
migration ordering).

**Packages/modules:** `mip.domain.models` (partial), `mip.reference.*`,
`mip.repositories.instruments`.

**Gate tests:**
- Seed is idempotent: running twice produces identical row counts and ids
- CHECK constraint holds: instrument with both `industry_id` and `sector_id` is rejected; stock→industry→sector join resolves correctly
- Sector ETF mapping resolves to an instrument row, not a string
- Calendar: known holidays absent (e.g. 2026-07-03 observed), weekends absent, half-days flagged; contiguous coverage over the configured range
- Symbol history: changing a symbol writes a history row with correct `valid_from`/`valid_to`; old symbol still resolves for its period

---

## Phase 2 — Ingestion Framework + Price Ingestion

**Goal:** The full ingestion pattern implemented once, end to end, on the
hardest domain (prices): runs, archive, validation/quarantine, revision
detection, upserts, corporate actions.

**Why it exists:** Prices exercise every framework component (overlap
revisions, corporate-action tripwire, quality rules). Once this pattern is
proven, the remaining ingestion services are thin variations.

**Deliverables:**
- ORM + migrations: `ingestion_runs`, `daily_prices`, `corporate_actions`, `data_quality_issues`, `data_revisions`
- `providers/base.py` (Protocols + DTO column contracts), `providers/yfinance/prices.py`
- `ingestion/archive.py` (write-once writer; refuses overwrite; `.rejected.csv` sidecars)
- `ingestion/validation.py` (contract checks + quality rules: OHLC coherence, return-jump-without-corporate-action, stale prices, calendar gaps) with severity tiers
- `ingestion/revisions.py` (overlap diffing; adj_close tripwire → full-refresh scheduling)
- `ingestion/price_service.py`; `repositories/prices.py`, `ingestion_runs.py`
- CLI: `mip ingest prices [--symbols ... | --all] [--full-refresh]`, `mip runs list`, `mip quality list|accept`

**Dependencies:** Phase 1 (instruments, calendar).

**Database changes:** the five tables above; `feature` tables NOT yet.

**Packages/modules:** `mip.providers.base`, `mip.providers.yfinance.prices`,
`mip.ingestion.{archive,validation,revisions,price_service}`,
`mip.repositories.{prices,ingestion_runs}`.

**Gate tests (fake provider for all unit tests; one live smoke test allowed):**
- Idempotency: same fixture ingested twice → identical DB state, second run reports 0 inserts
- Incremental cursor: only missing dates requested; overlap window included
- Revision: fixture where an overlap `adj_close` differs → `data_revisions` row written, `last_updated_at` bumped, full refresh scheduled
- Quarantine: row with `high < low` → excluded from `daily_prices`, present in `data_quality_issues` (severity error) and `.rejected.csv`; warning-tier row loads and is flagged
- Quality rule: +45% day with a matching split in `corporate_actions` passes; without one → flagged
- Archive: writer refuses to overwrite an existing file; archive path recorded on run
- Partial failure: one symbol raising permanently → run `status=partial`, other symbols loaded, error detail recorded
- Run accounting: insert/update counts match actual row changes

---

## Phase 3 — Macro Ingestion (FRED)

**Goal:** Macro series and observations flowing with publication-lag
metadata and revision logging.

**Why it exists:** Treasury yields, Fed Funds, CPI, GDP, employment feed the
Interest Rate and Macro models and several features. Publication lag captured
here is what makes future backtests honest.

**Deliverables:**
- ORM + migration: `macro_series`, `macro_observations`
- Versioned series catalog (config): provider codes, frequency, `publication_lag_days` per series (e.g. DGS10 = 1, CPIAUCSL ≈ 42, GDP ≈ 30/60/90 pattern → conservative constant per series)
- `providers/fred/macro.py`; `ingestion/fred_service.py`; `repositories/macro.py`
- CLI: `mip ingest macro [--series ... | --all]`

**Dependencies:** Phase 2 (framework: runs, quality, revisions, archive).

**Database changes:** `macro_series`, `macro_observations`.

**Packages/modules:** `mip.providers.fred.macro`,
`mip.ingestion.fred_service`, `mip.repositories.macro`.

**Gate tests:**
- Idempotent re-ingestion of a fixture series
- Header/detail integrity: unknown series code fails loudly; adding a catalog entry requires no migration
- Frequency conformity: monthly fixture with two obs in one month → quality issue
- Revision: changed historical CPI value in fixture → `data_revisions` row, value updated
- Lag metadata: every seeded series has explicit `publication_lag_days`; catalog test fails if a series omits it
- FRED missing-value marker ('.') stored as NULL, not zero

---

## Phase 4 — Fundamentals & Earnings Ingestion

**Goal:** Dated fundamental snapshots and append-only earnings observations.

**Why it exists:** Valuation model inputs (fundamentals history starts the
day this ships — every day of delay is lost history) and Catalyst model
inputs (point-in-time earnings dates).

**Deliverables:**
- ORM + migrations: `company_fundamentals`, `earnings_observations` + `v_earnings_current` view
- `providers/yfinance/{fundamentals,earnings}.py`
- `ingestion/{fundamental_service,earnings_service}.py`; repositories
- Cross-field consistency checks (market_cap ≈ close × shares within tolerance; non-negatives; period-over-period jump flags)
- CLI: `mip ingest fundamentals`, `mip ingest earnings`

**Dependencies:** Phase 2 (framework); Phase 3 not required.

**Database changes:** `company_fundamentals`, `earnings_observations`, view.

**Packages/modules:** `mip.providers.yfinance.{fundamentals,earnings}`,
`mip.ingestion.{fundamental_service,earnings_service}`, repositories.

**Gate tests:**
- Snapshot semantics: two fetches on different dates → two rows; same-day re-fetch upserts, never duplicates
- Append-only earnings: shifted date in fixture → new observation row, prior row untouched; `v_earnings_current` returns the latest per (instrument, date)
- Consistency rule: market_cap inconsistent with price × shares → quality issue (unit-error tripwire)
- Missing fundamentals fields tolerated as NULL without quarantining the snapshot

---

## Phase 5 — Feature Store & Feature Pipeline

**Goal:** Registered, versioned features computed incrementally into the two
partitioned feature tables; single consumption API.

**Why it exists:** The hand-off surface between the data platform and every
future model. This phase completes the original Phase 1 mission.

**Deliverables:**
- ORM + migrations: `feature_definitions`, `feature_store_daily`, `feature_store_market_daily` (yearly partitions + partition-creation helper)
- `features/base.py` (FeatureCalculator interface; declared lookback; declared adjusted-vs-raw)
- Calculators: rolling returns (5/21/63/126/252d), rolling volatility (21/63d), moving averages (50/200d) and spread, 52-week high/low distance (raw close), relative return vs SPY and vs sector ETF, Treasury yield changes (1d/5d/21d), yield-curve slope (10y−2y)
- `features/pipeline.py`: incremental orchestration on the trading calendar with lookback buffer; publication-lag-aware availability shifting for macro-derived features
- `repositories/features.py` with `get_matrix(features, instruments, date_range)` pivot API
- CLI: `mip features build [--from DATE]`, `mip features list`

**Dependencies:** Phases 2 + 3 (prices and macro in DB); Phase 4 not required.

**Database changes:** the three feature tables + partitions.

**Packages/modules:** `mip.features.*`, `mip.repositories.features`.

**Gate tests:**
- Golden values: each calculator vs hand-computed fixtures (known series → known ret_21d, vol_63d, MA cross, 52w distance, curve slope)
- Idempotency: rebuild over the same range → identical values, no duplicates (both tables' PKs enforced — including market table)
- Lag correctness: macro-derived feature for obs_date D is first available at D + `publication_lag_days` (the look-ahead regression test)
- Calendar alignment: features exist only on trading days; instruments with short history produce NULL-free partial ranges (absent rows, not zeros)
- Relative return uses sector-ETF FK resolution; instrument without a sector ETF skips the feature cleanly
- Version bump: changing a window param requires a new `feature_definitions` version; writing under an existing version with different params fails
- `get_matrix` returns correctly pivoted frame; missing features are absent columns, not silent zeros

---

## Phase 6 — Portfolio Ledger & Projections

**Goal:** Append-only transaction ledger with derived lots, closures
(realized gains), and daily position snapshots (unrealized gains).

**Why it exists:** The platform's purpose is evaluating YOUR holdings; the
Portfolio Risk model and Trim Score need positions, and lot-level cost basis
is what makes future trim recommendations tax-aware.

**Deliverables:**
- ORM + migrations: `portfolios`, `transactions`, `lots`, `lot_closures`, `position_snapshots`
- `portfolio/ledger.py` (append-only enforcement; reversing entries), `portfolio/lot_engine.py` (FIFO + specific-id), `portfolio/snapshots.py` (daily builder joining `daily_prices`), `portfolio/importers.py` (broker CSV with `external_id` idempotency)
- Full rebuild command: derive lots/closures/snapshots from ledger from scratch
- CLI: `mip portfolio create|import|snapshot|rebuild|positions`

**Dependencies:** Phase 2 (prices for valuation); Phases 3–5 not required.

**Database changes:** the five portfolio tables.

**Packages/modules:** `mip.portfolio.*`, portfolio repositories.

**Gate tests:**
- Ledger append-only: UPDATE/DELETE on transactions rejected at the application layer; correction flows as reversing entry
- Import idempotency: same broker CSV twice → no duplicate transactions (external_id constraint)
- FIFO golden case: scripted buy/buy/sell sequence → hand-computed lot closures, realized gains, short/long term classification
- Partial lot close: sell spanning two lots splits proceeds/basis correctly; `quantity_remaining` consistent
- Rebuild determinism: wipe projections, rebuild from ledger → byte-identical lots/closures/snapshots
- Snapshot valuation: quantity × adj-price on date, weights sum to 1 (± rounding) per portfolio-date; instrument missing a price that day → flagged, not silently zero
- Point-in-time holdings: "positions as of date X" matches hand-derived state mid-fixture

---

## Phase 7 — Platform Hardening & End-to-End Operation

**Goal:** The data platform runs as a daily operation: one command updates
everything, quality and revisions are reviewable, the whole pipeline is
verified end to end. **This phase closes the current scope.**

**Why it exists:** Individually tested parts are not an operated platform.
This is the acceptance gate for "data platform complete" and the freeze
point before any research/model work.

**Deliverables:**
- `mip update` — orchestrated daily run: prices → macro → fundamentals → earnings → features → snapshots, with per-stage status and a summary table
- `mip status` — freshness report per domain (last successful run, latest data date vs calendar, open quality issues count)
- Backfill runbook + `--full-refresh` paths exercised; cron setup documented
- Documentation pass: README, provider-onboarding guide (how to add a provider without touching downstream), feature-onboarding guide

**Dependencies:** Phases 0–6 complete.

**Database changes:** none (or trivial ops indexes discovered under load).

**Packages/modules:** `mip.cli` orchestration; no new domain packages.

**Gate tests:**
- End-to-end integration: empty DB → migrate → seed → full historical ingest (fixture providers) → features → portfolio import → snapshots; assert row counts, spot-check values, zero unexplained quality errors
- `mip update` twice in a row: second run is a near-no-op (idempotency at system level)
- Failure injection: provider down mid-update → affected stage `partial`/`failed`, later stages proceed where dependencies allow, `mip status` reflects it accurately
- Freshness: `mip status` correctly flags a domain that missed its last trading day
- Live smoke test against real yfinance + FRED for a 3-symbol, 3-series micro-universe

---

# Reserved Future Phases (NOT current scope)

Included so the platform above can be validated against what it must
support. Sequencing may be reordered when scope opens; each still obeys the
per-phase test gate.

## Phase 8 — Historical Research Engine

**Goal:** The point-in-time gatekeeper layer: as-of data access API, event
study framework, backtest harness.
**Why:** Centralizes PIT rules (publication lags, append-only earnings,
calendar alignment) so nine models don't reimplement them; every model
consumes history exclusively through it.
**Deliverables:** `research/` package — as-of query API over features/macro/
earnings/fundamentals; event-study primitives (event windows, abnormal
returns vs benchmark); walk-forward backtest harness with explicit
information-availability rules.
**Dependencies:** Phases 5–7.
**DB changes:** possibly an `events` generalization table; research-run
audit table.
**Modules:** `mip.research.*`.
**Gate tests:** PIT regression suite — no query can return a macro value
before `obs_date + lag` or an earnings date not yet observed as of the query
date; event-study golden cases; backtest reproducibility (same inputs →
identical results).

## Phase 9 — Intelligence Models (one sub-phase per model)

**Goal:** Independent model packages: Interest Rate Sensitivity, Macro,
Sector Rotation, Catalyst, Historical Event Studies, Valuation, Technical,
Volatility, Portfolio Risk — in whatever order research priorities dictate.
**Why:** The platform's analytical payload; independence is the architectural
requirement (a new model must never require redesign).
**Deliverables per model:** a package under `models/` consuming ONLY the
feature store + research engine; scores written to the reserved
`model_definitions` / `model_runs` / `model_scores` /
`model_score_components` shape with `horizon` first-class.
**Dependencies:** Phase 8 (and Phase 6 for Portfolio Risk).
**DB changes:** the four model-output tables (first model phase); nothing
per additional model.
**Gate tests per model:** golden scoring cases; explainability contract —
every score decomposes into named feature contributions that sum to the
score under the model's combination rule; determinism (re-run → identical
scores); no imports from `providers/` or raw-table access (architecture
conformance test).

## Phase 10 — Portfolio Decision Engine & Trim Score Engine

**Goal:** Combine model scores per holding into multi-horizon Trim Scores
(1w, 2w, 1m, 3m, ...) with full explanation chains.
**Why:** The platform's end product: "consider trimming X, because …".
**Deliverables:** `engine/` — score combination policies, horizon handling,
lot-aware context (tax terms from `lot_closures`/`lots`), explanation
assembly from `model_score_components` and `feature_definitions.description`.
**Dependencies:** Phase 9 (≥2 models live), Phase 6.
**DB changes:** trim-score output tables (designed then, following the
model-output pattern).
**Gate tests:** combination golden cases; every Trim Score traceable to
model scores → feature contributions → feature versions → ingestion runs
(full lineage walk executes); horizon isolation (a 1w score never consumes
features flagged longer-horizon-only).

## Phase 11 — Dashboard / API

**Goal:** Read-only API and dashboard surfacing scores, explanations,
positions, data freshness, and quality status.
**Why:** Consumption layer; deliberately last — every view reads tables that
already exist and are already tested.
**Deliverables:** `api/` (FastAPI or similar — decided then), read-only
endpoints, no business logic in the API layer.
**Dependencies:** Phases 7 + 10 (subsets can ship after Phase 7 for data
monitoring).
**DB changes:** none (read-only).
**Gate tests:** contract tests per endpoint; API-layer-has-no-writes
conformance test.

---

## Sequencing summary

```
0 Scaffold ─ 1 Reference ─ 2 Prices ─┬─ 3 Macro ──┬─ 5 Features ─┐
                                     ├─ 4 Fund/Earn ─────────────┼─ 7 Hardening ─ FREEZE
                                     └─ 6 Portfolio ─────────────┘
future:  8 Research Engine ─ 9 Models (×9) ─ 10 Decision/Trim ─ 11 Dashboard
```

Phases 3, 4, and 6 depend only on Phase 2's framework and may be built in
any order (or interleaved). Phase 5 needs 2 + 3. Phase 7 closes the data
platform — the current, frozen scope.
