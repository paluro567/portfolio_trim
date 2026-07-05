# Market Intelligence Platform — Architecture (Version 2 — FROZEN)

**Status:** FROZEN as of 2026-07-04 after two review rounds.
Changes after this point require an explicit architecture amendment, not ad-hoc drift.
**Scope of this document:** the data platform and its reserved extension points.
No prediction models, no trim logic, no API are implemented in Phase 1.

---

## 1. System Pipeline

```
Market Data Providers (yfinance, FRED, ...)
        │  provider adapters — the ONLY code that imports provider SDKs
        ▼
Raw Data Archive (RawData/ — immutable, write-once CSVs)
        ▼
PostgreSQL (normalized system of record)
        ▼
Feature Engineering (registered, versioned, reusable features)
        ▼
Historical Research Engine          ◄── first-class layer (reserved)
  point-in-time data access · event studies · backtest harness
        ▼
Independent Intelligence Models     ◄── reserved
  Interest Rate · Macro · Sector · Catalyst · Event Studies ·
  Valuation · Technical · Volatility · Portfolio Risk
        ▼
Portfolio Decision Engine           ◄── reserved
        ▼
Trim Score Engine (multi-horizon: 1w, 2w, 1m, 3m, ...)  ◄── reserved
        ▼
Dashboard / API                     ◄── reserved
```

**The Historical Research Engine is the platform's point-in-time gatekeeper.**
Intelligence models never query raw tables directly for historical analysis;
they go through the research engine, which centralizes as-of joins,
macro publication lags, append-only earnings history, and trading-calendar
alignment. Point-in-time correctness is implemented once, not nine times.

## 2. Core Design Decisions (carried + hardened)

- **D1 — Provider adapters behind Protocol interfaces.** Nothing outside
  `providers/` imports `yfinance` or `fredapi`. Adapters return normalized
  DTOs with documented column contracts. New providers are new adapters;
  downstream layers are untouched.
- **D2 — Ingestion services own orchestration only.** Cursor → fetch (retry)
  → validate → archive → upsert → run record. All collaborators injected.
- **D3 — Concrete repositories** encapsulate all SQL. No generic repository.
- **D4 — Idempotency at the database.** Natural-key composite primary keys +
  `ON CONFLICT` upserts everywhere. Any ingestion may be re-run at any time.
- **D5 — Archive before load.** RawData CSVs are write-once and are the
  record of "what the provider said." Rejected rows get `.rejected.csv`
  sidecars.
- **D6 — Narrow feature store, split by scope** (v2): instrument features
  and market-wide features live in separate tables so both have real
  composite primary keys (fixes the NULL-uniqueness defect). Both are
  range-partitioned by year from day one.
- **D7 — Every run audited** in `ingestion_runs`; every fact row carries
  `ingestion_run_id` for lineage back to run and archive file.
- **D8 — Strong typing:** SQLAlchemy 2.x `Mapped[]` models, Pydantic
  Settings/DTOs, mypy-clean, Python 3.13.
- **D9 — Config via Pydantic Settings**, secrets via environment.
- **D10 — structlog** with `run_id`-bound context.
- **D11 (v2) — Keys, never tickers.** All relationships use `instrument_id`.
  Ticker strings appear only in `instruments.symbol` (current) and
  `symbol_history`. The sector→ETF mapping is an instrument FK.
- **D12 (v2) — Revisions are observable.** Incremental runs re-fetch an
  overlap window and diff before upserting; changes are recorded in
  `data_revisions` and stamped via `first_seen_at`/`last_updated_at`.
  An `adj_close` revision triggers a full-history refresh for that
  instrument (corporate-action tripwire).
- **D13 (v2) — Point-in-time discipline is schema-supported.** Macro series
  carry `publication_lag_days`; earnings are append-only observations;
  instruments are never deleted (`delisted_date`). The Historical Research
  Engine enforces these rules for all consumers.
- **D14 (v2) — Portfolio truth is an append-only transaction ledger.**
  Lots, closures, and position snapshots are derived projections,
  rebuildable from the ledger at any time. Corrections are reversing
  entries, never UPDATEs.
- **D15 (v2) — Bad data is quarantined, never silently dropped.** The
  validation gate excludes `error`-severity rows from fact tables and
  ledgers them in `data_quality_issues` with a resolution workflow.

## 3. Folder Structure

```
stock_scoring/
├── pyproject.toml                # uv-managed; ruff + black config
├── .env.example
├── docs/
│   ├── ARCHITECTURE.md           # this document (frozen v2)
│   └── ROADMAP.md
├── RawData/                      # immutable CSV archive (gitignored)
│   ├── prices/  ├── macro/  ├── fundamentals/  └── earnings/
├── alembic/versions/             # migrations from day one
├── src/mip/
│   ├── core/                     # config, logging, db, retry, exceptions
│   ├── domain/                   # ORM models, enums
│   ├── providers/                # base protocols + yfinance/ + fred/
│   ├── repositories/             # one concrete repo per aggregate
│   ├── ingestion/                # archive, validation, quality, revisions,
│   │                             #   price/fred/fundamental/earnings services
│   ├── features/                 # calculators + pipeline
│   ├── portfolio/                # ledger, lot engine, snapshots, importers
│   ├── reference/                # universe seed, trading calendar builder
│   ├── research/                 # RESERVED — Historical Research Engine
│   ├── models/                   # RESERVED — intelligence models (one pkg each)
│   ├── engine/                   # RESERVED — decision engine, trim score
│   ├── api/                      # RESERVED — dashboard API
│   └── cli/                      # Typer app
└── tests/
    ├── unit/                     # fake providers, no network, no DB
    └── integration/              # against throwaway Postgres
```

Reserved packages exist as empty placeholders only; nothing in Phase 1 may
import from them.

## 4. Database Schema (v2 — frozen)

### 4.1 Reference & classification

```sql
CREATE TABLE sectors (
    id                 SERIAL PRIMARY KEY,
    name               TEXT NOT NULL UNIQUE,
    etf_instrument_id  INT REFERENCES instruments(id)   -- FK, not a ticker string
);

CREATE TABLE industries (
    id          SERIAL PRIMARY KEY,
    sector_id   INT NOT NULL REFERENCES sectors(id),
    name        TEXT NOT NULL,
    UNIQUE (sector_id, name)
);

CREATE TABLE instruments (
    id              SERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL UNIQUE,       -- CURRENT symbol only
    name            TEXT,
    instrument_type TEXT NOT NULL,              -- 'stock' | 'etf' | 'index'
    industry_id     INT REFERENCES industries(id),  -- stocks: industry only;
    sector_id       INT REFERENCES sectors(id),     -- sector derived via join
    currency        TEXT NOT NULL DEFAULT 'USD',
    exchange        TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    delisted_date   DATE,                       -- never DELETE instruments
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (NOT (industry_id IS NOT NULL AND sector_id IS NOT NULL))
    -- at most one direct classification; industry implies sector (3NF fix)
);

CREATE TABLE symbol_history (
    instrument_id INT NOT NULL REFERENCES instruments(id),
    symbol        TEXT NOT NULL,
    valid_from    DATE NOT NULL,
    valid_to      DATE,                          -- NULL = current
    PRIMARY KEY (instrument_id, valid_from)
);
CREATE INDEX ix_symbol_history_symbol ON symbol_history (symbol);

CREATE TABLE trading_calendar (
    exchange      TEXT NOT NULL DEFAULT 'NYSE',
    calendar_date DATE NOT NULL,
    is_half_day   BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (exchange, calendar_date)
);
```

### 4.2 Market data

```sql
CREATE TABLE daily_prices (
    instrument_id    INT NOT NULL REFERENCES instruments(id),
    price_date       DATE NOT NULL,
    open             NUMERIC(18,6),
    high             NUMERIC(18,6),
    low              NUMERIC(18,6),
    close            NUMERIC(18,6) NOT NULL,
    adj_close        NUMERIC(18,6),
    volume           BIGINT,
    first_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ingestion_run_id BIGINT REFERENCES ingestion_runs(id),
    PRIMARY KEY (instrument_id, price_date)
);
CREATE INDEX ix_daily_prices_date ON daily_prices (price_date);

CREATE TABLE corporate_actions (
    id               BIGSERIAL PRIMARY KEY,
    instrument_id    INT NOT NULL REFERENCES instruments(id),
    action_type      TEXT NOT NULL,             -- 'split' | 'dividend'
    ex_date          DATE NOT NULL,
    split_ratio      NUMERIC(12,6),             -- splits
    cash_amount      NUMERIC(18,6),             -- dividends
    ingestion_run_id BIGINT REFERENCES ingestion_runs(id),
    UNIQUE (instrument_id, action_type, ex_date)
);
```

### 4.3 Macro (with publication-lag support)

```sql
CREATE TABLE macro_series (
    id                   SERIAL PRIMARY KEY,
    provider             TEXT NOT NULL DEFAULT 'FRED',
    provider_code        TEXT NOT NULL,          -- 'DGS10', 'FEDFUNDS', ...
    name                 TEXT NOT NULL,
    frequency            TEXT NOT NULL,          -- 'D' | 'W' | 'M' | 'Q'
    units                TEXT,
    seasonally_adjusted  BOOLEAN,
    publication_lag_days INT NOT NULL DEFAULT 0, -- obs_date + lag = first
                                                 -- date value was knowable
    UNIQUE (provider, provider_code)
);

CREATE TABLE macro_observations (
    series_id        INT NOT NULL REFERENCES macro_series(id),
    obs_date         DATE NOT NULL,              -- reference period date
    value            NUMERIC(18,6),
    first_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ingestion_run_id BIGINT REFERENCES ingestion_runs(id),
    PRIMARY KEY (series_id, obs_date)
);
CREATE INDEX ix_macro_obs_date ON macro_observations (obs_date);
```

All feature calculators and the Historical Research Engine must treat an
observation as available only from `obs_date + publication_lag_days`.
(Upgrade path: true release dates from FRED's releases API; revisions land in
`data_revisions`.)

### 4.4 Fundamentals & earnings

```sql
CREATE TABLE company_fundamentals (           -- dated snapshots, never mutated
    instrument_id      INT NOT NULL REFERENCES instruments(id),
    as_of_date         DATE NOT NULL,          -- date WE fetched it (PIT-honest)
    market_cap         NUMERIC(20,2),
    trailing_pe        NUMERIC(12,4),
    forward_pe         NUMERIC(12,4),
    price_to_book      NUMERIC(12,4),
    trailing_eps       NUMERIC(12,4),
    forward_eps        NUMERIC(12,4),
    dividend_yield     NUMERIC(8,6),
    beta               NUMERIC(8,4),
    shares_outstanding BIGINT,
    revenue_ttm        NUMERIC(20,2),
    profit_margin      NUMERIC(8,6),
    debt_to_equity     NUMERIC(12,4),
    ingestion_run_id   BIGINT REFERENCES ingestion_runs(id),
    PRIMARY KEY (instrument_id, as_of_date)
);

CREATE TABLE earnings_observations (          -- APPEND-ONLY; dates shift and
    id               BIGSERIAL PRIMARY KEY,   -- history must survive
    instrument_id    INT NOT NULL REFERENCES instruments(id),
    earnings_date    DATE NOT NULL,
    observed_at      TIMESTAMPTZ NOT NULL,
    time_of_day      TEXT,                    -- 'BMO' | 'AMC' | 'unknown'
    eps_estimate     NUMERIC(12,4),
    eps_actual       NUMERIC(12,4),
    is_confirmed     BOOLEAN NOT NULL DEFAULT FALSE,
    ingestion_run_id BIGINT REFERENCES ingestion_runs(id),
    UNIQUE (instrument_id, earnings_date, observed_at)
);
-- v_earnings_current (VIEW): latest observation per (instrument, earnings_date).
-- Catalyst/event-study models read the full history for "known as of" truth.
```

### 4.5 Operations, quality, revisions

```sql
CREATE TABLE ingestion_runs (
    id             BIGSERIAL PRIMARY KEY,
    run_type       TEXT NOT NULL,     -- prices|macro|fundamentals|earnings|features|snapshots
    provider       TEXT NOT NULL,
    scope          TEXT,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at   TIMESTAMPTZ,
    status         TEXT NOT NULL DEFAULT 'running',  -- running|success|partial|failed
    rows_inserted  INT NOT NULL DEFAULT 0,
    rows_updated   INT NOT NULL DEFAULT 0,
    archive_path   TEXT,
    error_detail   JSONB
);
CREATE INDEX ix_runs_type_started ON ingestion_runs (run_type, started_at DESC);

CREATE TABLE data_quality_issues (
    id               BIGSERIAL PRIMARY KEY,
    ingestion_run_id BIGINT NOT NULL REFERENCES ingestion_runs(id),
    entity_type      TEXT NOT NULL,     -- 'price' | 'macro_obs' | 'fundamental' | ...
    entity_key       TEXT NOT NULL,     -- e.g. 'AAPL/2026-07-02'
    rule             TEXT NOT NULL,     -- e.g. 'return_gt_40pct_no_corp_action'
    severity         TEXT NOT NULL,     -- 'error' (quarantined) | 'warning' | 'info'
    observed_value   TEXT,
    details          JSONB,
    status           TEXT NOT NULL DEFAULT 'open',  -- open|accepted|resolved
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_dqi_status ON data_quality_issues (status, created_at DESC);

CREATE TABLE data_revisions (                 -- provider changed history under us
    id               BIGSERIAL PRIMARY KEY,
    table_name       TEXT NOT NULL,           -- 'daily_prices' | 'macro_observations'
    entity_key       TEXT NOT NULL,           -- 'AAPL/2026-06-15' | 'DGS10/2026-06-01'
    field            TEXT NOT NULL,
    old_value        TEXT,
    new_value        TEXT,
    detected_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ingestion_run_id BIGINT REFERENCES ingestion_runs(id)
);
CREATE INDEX ix_revisions_entity ON data_revisions (table_name, entity_key);
```

### 4.6 Feature store (split by scope; partitioned)

```sql
CREATE TABLE feature_definitions (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,      -- 'ret_21d', 'vol_63d', 'dist_52w_high',
                                    -- 'rel_ret_spy_63d', 'curve_slope_10y2y', ...
    version     INT NOT NULL DEFAULT 1,
    scope       TEXT NOT NULL,      -- 'instrument' | 'market'
    description TEXT NOT NULL,      -- human-readable: future explanation text
    params      JSONB,              -- {'window': 21, 'benchmark': 'SPY'}
    uses_adjusted_prices BOOLEAN,   -- documents adjusted-vs-raw per feature
    UNIQUE (name, version)
);

CREATE TABLE feature_store_daily (            -- instrument-scoped features
    instrument_id INT  NOT NULL REFERENCES instruments(id),
    feature_date  DATE NOT NULL,
    feature_id    INT  NOT NULL REFERENCES feature_definitions(id),
    value         NUMERIC(20,8),
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, feature_date, feature_id)
) PARTITION BY RANGE (feature_date);          -- yearly partitions

CREATE TABLE feature_store_market_daily (     -- market-wide features
    feature_date  DATE NOT NULL,              -- (curve slope, yield changes...)
    feature_id    INT  NOT NULL REFERENCES feature_definitions(id),
    value         NUMERIC(20,8),
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (feature_date, feature_id)
) PARTITION BY RANGE (feature_date);
```

The split gives both tables real composite PKs (the v1 design's nullable
`instrument_id` under a UNIQUE constraint could not enforce uniqueness for
market rows). Consumption goes through a single repository API that pivots
narrow→wide per request; heavier consumers (future training jobs) get
Parquet exports behind the same seam.

### 4.7 Portfolio (append-only ledger + derived projections)

```sql
CREATE TABLE portfolios (
    id                SERIAL PRIMARY KEY,
    name              TEXT NOT NULL UNIQUE,
    base_currency     TEXT NOT NULL DEFAULT 'USD',
    cost_basis_method TEXT NOT NULL DEFAULT 'FIFO',  -- 'FIFO' | 'specific_id'
    description       TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE transactions (                   -- SOURCE OF TRUTH. Append-only.
    id            BIGSERIAL PRIMARY KEY,      -- Corrections = reversing entries.
    portfolio_id  INT NOT NULL REFERENCES portfolios(id),
    instrument_id INT REFERENCES instruments(id),   -- NULL for cash movements
    txn_type      TEXT NOT NULL,  -- buy|sell|dividend|split|deposit|withdrawal|fee
    trade_date    DATE NOT NULL,
    quantity      NUMERIC(20,8),
    price         NUMERIC(18,6),
    fees          NUMERIC(18,6) NOT NULL DEFAULT 0,
    total_amount  NUMERIC(20,6) NOT NULL,     -- signed cash impact
    external_id   TEXT,                       -- broker id → idempotent imports
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (portfolio_id, external_id)
);
CREATE INDEX ix_txn_portfolio_date ON transactions (portfolio_id, trade_date);

CREATE TABLE lots (                           -- derived; rebuildable from ledger
    id                   BIGSERIAL PRIMARY KEY,
    portfolio_id         INT NOT NULL REFERENCES portfolios(id),
    instrument_id        INT NOT NULL REFERENCES instruments(id),
    open_transaction_id  BIGINT NOT NULL REFERENCES transactions(id),
    open_date            DATE NOT NULL,
    quantity_opened      NUMERIC(20,8) NOT NULL,
    quantity_remaining   NUMERIC(20,8) NOT NULL,
    cost_basis_per_share NUMERIC(18,6) NOT NULL,
    is_closed            BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX ix_lots_portfolio_instr ON lots (portfolio_id, instrument_id)
    WHERE NOT is_closed;

CREATE TABLE lot_closures (                   -- realized gains, per lot slice
    id                    BIGSERIAL PRIMARY KEY,
    lot_id                BIGINT NOT NULL REFERENCES lots(id),
    close_transaction_id  BIGINT NOT NULL REFERENCES transactions(id),
    close_date            DATE NOT NULL,
    quantity_closed       NUMERIC(20,8) NOT NULL,
    proceeds              NUMERIC(20,6) NOT NULL,
    cost_basis            NUMERIC(20,6) NOT NULL,
    realized_gain         NUMERIC(20,6) NOT NULL,
    holding_period_days   INT NOT NULL,
    term                  TEXT NOT NULL       -- 'short' | 'long'
);

CREATE TABLE position_snapshots (             -- derived daily; unrealized gains
    portfolio_id    INT NOT NULL REFERENCES portfolios(id),
    instrument_id   INT NOT NULL REFERENCES instruments(id),
    snapshot_date   DATE NOT NULL,
    quantity        NUMERIC(20,8) NOT NULL,
    cost_basis      NUMERIC(20,6) NOT NULL,
    market_value    NUMERIC(20,6),
    unrealized_gain NUMERIC(20,6),
    weight          NUMERIC(10,8),            -- share of portfolio market value
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (portfolio_id, instrument_id, snapshot_date)
);
```

The transaction ledger doubles as point-in-time universe membership: "what
did I hold on date X" is answerable with no survivorship bias — the input the
Portfolio Risk model and backtests will rely on.

## 5. Why each table exists (delta from v1)

Unchanged rationale: `sectors`, `industries`, `instruments`, `daily_prices`,
`macro_series`/`macro_observations` (header/detail), `company_fundamentals`
(dated snapshots), `ingestion_runs` (audit spine), `feature_definitions`
(features as governed, versioned entities).

New/changed in v2:

- **`symbol_history`** — tickers change and get reused; the id↔symbol map is
  temporal, not static.
- **`trading_calendar`** — one canonical set of trading days; cursors,
  gap detection, and feature alignment join against it instead of
  reimplementing calendar arithmetic.
- **`corporate_actions`** — root-cause data for adjusted-price drift;
  captured from day one because "as seen at the time" cannot be backfilled.
- **`earnings_observations`** (replaces mutable `earnings_calendar`) —
  announced dates move; append-only observations preserve "what was known
  when" for the Catalyst model, with a view for the current calendar.
- **`data_quality_issues`** — quarantine ledger with a resolution workflow;
  bad data is excluded and visible, never silently dropped.
- **`data_revisions`** — providers rewrite history (adj_close after
  dividends, macro revisions); this makes it observable and triggers
  corrective refreshes.
- **`feature_store_market_daily`** — market-wide features get a real PK and
  a clean home (v1 defect fix).
- **Portfolio tables** — ledger as truth, projections as cache (D14);
  `lot_closures` *is* realized gains at the lot level;
  `position_snapshots` *is* unrealized gains per position per day.

## 6. Ingestion Flow (unchanged shape, hardened steps)

`mip ingest prices --symbols AAPL,MSFT`:

1. Open `ingestion_runs` row; bind `run_id` into structlog.
2. Cursor per instrument from `daily_prices`, minus an **overlap window**
   (last ~10 trading days) for revision detection.
3. Fetch via provider adapter with retry/backoff; permanently failing
   symbols are recorded and skipped (`status=partial`).
4. Normalize to the internal contract; strip timezones to dates.
5. Validate (contract + quality rules). `error` rows → quarantine
   (`data_quality_issues` + `.rejected.csv` sidecar); `warning` rows → load
   and flag.
6. Archive validated frame to `RawData/prices/...` (write-once).
7. Diff overlap rows against stored values → differences logged to
   `data_revisions`, `last_updated_at` bumped; `adj_close` diffs schedule a
   full-history refresh (corporate-action tripwire).
8. Bulk upsert `ON CONFLICT DO UPDATE`; corporate actions upserted alongside.
9. Close run with counts and status.

FRED / fundamentals / earnings services share the identical shape; earnings
inserts are append-only rather than upserts. The feature pipeline
(`mip features build`) reads only from PostgreSQL, respects
`publication_lag_days` and the trading calendar, and upserts into the two
feature tables under a `run_type='features'` run. The snapshot builder
(`mip portfolio snapshot`) replays the ledger and joins prices.

## 7. Known Limitations (accepted for Phase 1)

1. yfinance fragility — contained by D1 + D5.
2. Fundamentals are not point-in-time before our first snapshot; backtests
   may use them only from `as_of_date` forward.
3. Macro values are latest-revision (lag handled; vintage/ALFRED is a future
   provider slot).
4. Single-currency (USD) logic despite schema support for `currency`.
5. No scheduler — CLI on cron until orchestration is earned.

Explicitly deferred (named trigger conditions, not forgotten): wide
materialized feature views (trigger: interactive dashboard latency), Parquet
training exports (trigger: model training workloads), events generalization
(trigger: Catalyst model build), ALFRED vintages (trigger: Historical Event
Studies model), TimescaleDB/partitioning beyond feature tables (trigger:
universe ×10 or intraday data), corporate-action-based self-computed
adjustments (trigger: first observed Yahoo adjustment error).

---

*Frozen 2026-07-04. Implementation proceeds per docs/ROADMAP.md.*
