# Phase 2 Design — Survivorship-Clean Historical Research Dataset

**Status:** design only (no production code). **Predecessors:**
[EVALUATION_FOUNDATION_DESIGN.md](EVALUATION_FOUNDATION_DESIGN.md) (strategy),
[SECURITY_MASTER.md](SECURITY_MASTER.md) (Phase 1, delivered). **Scope rule:**
Phase 2 does not touch the production Trim Score, model weights, or any signal.
It builds *trustworthy historical outcomes* so future research conclusions are
scientifically defensible.

**Pre-implementation review:** [PHASE2_ARCHITECTURE_REVIEW.md](PHASE2_ARCHITECTURE_REVIEW.md)
returned *Approved With Minor Corrections*. Before the first Phase 2 commit, fold
in its corrections 1–3: (1) scope the first study to signals recomputable from
the clean `security_price_daily`/return series (defer feature-store re-keying to
a named Phase 3) + a guardrail against joining legacy `feature_store_daily` to
`research_observation`; (2) make `instrument_security_map` a first-class,
PIT-correct, tested bridge (not "reconciliation only"); (3) seed an
execution-level `experiment_run` results store now. These are additive (~2–4
days), not a redesign.

**Decisions locked (owner-approved 2026-07-26):** (1) provider posture =
**Norgate + Sharadar** two-source cross-validated primary (not Norgate-only, not
CRSP-gated); (2) **residual/factor returns deferred** to the Important tier — the
MVI ships benchmark-relative + sector-relative returns only, with a nullable
`forward_return_residual` column present from day one so residualization can be
added later without a schema change.

> **The one question Phase 2 exists to answer.**
> *What is the smallest survivorship-clean historical dataset that lets us
> reliably determine whether a predictive signal has genuine out-of-sample
> stock-selection value?*
> Everything below is subordinated to that question. If a choice adds coverage
> but not decision power for it, the choice is deferred.

---

## 0. Where the gap actually is (grounded in the current schema)

Production already has `daily_prices`, `corporate_actions`, and a
`predictions → prediction_outcomes` archive. That machinery is **not**
survivorship-clean, and it is the source of the problem:

- `daily_prices` and `corporate_actions` are keyed on the **legacy
  `instruments.id`**, whose `symbol` is UNIQUE and "CURRENT symbol only". That
  identity model is exactly what Phase 1 replaced.
- The price history is **survivor-only** (yfinance drops delisted names).
- `prediction_outcomes.actual_return` is derived from `entry_price`/`exit_price`
  in `daily_prices`. **If a security delists between entry and exit there is no
  exit price** — the outcome is NULL or absent, so the losers that delist are
  the exact observations that vanish. The measurement of edge is biased upward
  at the point of measurement.

Phase 1 fixed *identity*. Phase 2 must fix *outcomes*, and it must do so on the
Phase 1 `security_id`, not on `instruments.id`. The legacy tables stay for the
live production pipeline; the **research dataset is rebuilt clean and keyed on
`security_id`**, with an explicit bridge to the legacy id for reconciliation.

---

## Stage 1 — Phase 2 Objectives (Required / Important / Future)

### Required — validation is impossible without these
1. **Survivorship-clean daily prices incl. delisted names**, keyed on
   `security_id`, spanning the full life of every security in the research
   universe (listing → delisting), raw + total-return-adjusted.
2. **Delisting returns.** The terminal return realized at/through delisting
   (fills the deliberately-nullable `delisting_event.delisting_return` /
   `terminal_price` from Phase 1). Without this, forward returns that cross a
   delisting are undefined and get silently dropped — the primary bias.
3. **Point-in-time market cap, shares outstanding, and dollar volume /
   liquidity**, so the Phase 1 universe's PENDING `min_price` / `min_market_cap`
   / `min_dollar_volume` filters can be applied *as of* each reconstitution date
   without look-ahead.
4. **Benchmark returns** (broad-market total return) and **sector benchmark
   returns**, to convert raw forward returns into **benchmark-relative** and
   **sector-relative** returns — the unit in which "selection value" is defined.
5. **Materialized, versioned, reproducible forward-return observations**: one
   immutable research snapshot per (universe definition version, data version),
   from which every `(security_id, as_of, horizon)` forward return is
   reconstructible byte-for-byte.

### Important — materially better research, not blocking
- **Residual (risk-adjusted) returns** — market/sector-beta-neutralized returns
  (single- or few-factor). Sharpens IC but is not required to *detect* selection
  value; the first study runs on benchmark-/sector-relative returns.
- **Historical GICS sector reclassifications** beyond what Phase 1 already
  stores (Phase 1 has `historical_classification`; Phase 2 populates it from a
  PIT source instead of today's static map).
- **Historical index membership** (S&P 500/1500) as an *alternative* PIT
  universe and as a survivorship cross-check.
- **Unadjusted + adjusted prices both retained**, so any future corporate-action
  policy change is reproducible from raw.

### Future — must NOT delay Phase 2
- Intraday / minute bars, options, short interest, borrow.
- Multi-factor (Fama-French/Barra-style) residualization.
- International / non-US securities.
- Analyst revisions, positioning, alternative data (these are *new signals*,
  explicitly out of scope, and are what a future CPE promotion would need).

---

## Stage 2 — Required Historical Data (per-domain spec)

Depth target: **~20 years** (≈2005→present). Rationale from Phase 1's
decomposition finding: the failure was an effective sample of ~4 independent
annual blocks. Annual-block validation needs ≥15 non-overlapping years to have
any power; 20 gives margin and covers ≥2 full regime cycles (2008, 2020, 2022).

Minimum acceptable quality is stated as a **rejection threshold**, not an ideal.

| Domain | Purpose (why required) | PIT requirement | Depth | Depends on | Min acceptable quality (else reject) |
|---|---|---|---|---|---|
| Daily prices (raw) | base series; corporate-action reproducibility | close known EOD of its date | 20y, full life incl. delisted | Phase 1 `security_id` | full life of every delisted name; no forward-fill across delisting |
| Total-return adj close | forward-return computation | adjustment factors as-of | 20y | prices + corp actions | dividends + splits reinvested; documented methodology |
| Corporate actions | adjust raw→total-return; validate | ex-date known on ex-date | 20y | prices | splits & dividends complete for included names; ex-dates correct |
| Delisting events | mark end-of-life; stop membership | known at delisting | 20y | Phase 1 `delisting_event` | **every** delisted `security_id` has one |
| **Delisting returns** | truncate losers correctly | value realized at delist | 20y | delisting events | numeric return (or documented −100%/acquisition value); **no NULLs for delisted names in universe** |
| Historical market cap | universe eligibility; size neutralization | cap as-of, no restatement | 20y | shares × price | monthly granularity min; PIT (not today's shares projected back) |
| Shares outstanding | market cap; float sanity | as-of the date | 20y | — | split-consistent; no look-ahead restatement |
| Dollar volume / liquidity | eligibility; tradability screen | as-of | 20y | prices × volume | daily volume present for included names |
| Benchmark returns | benchmark-relative return | close EOD | 20y | — | total-return index (e.g. SPY/VTI TR or CRSP mkt) |
| Sector benchmark returns | sector-relative return | close EOD | 20y | sector map | one total-return series per GICS sector |
| Historical sector classification | sector-relative grouping; neutralization | classification as-of | 20y | Phase 1 `historical_classification` | PIT sector; reclassifications dated, not today's map |
| Historical index membership | alt universe + survivorship cross-check | membership as-of | 20y | Phase 1 `universe_membership` | add/drop dates; *Important*, not Required |
| Trading calendar | align dates; count sessions | static/PIT | 20y | existing `trading_calendar` | NYSE/Nasdaq holidays + half-days (already present) |
| Exchange history | eligibility; venue changes | as-of | 20y | Phase 1 `security_identifier_history` | already in Phase 1 (exchange on each ticker interval) |
| PIT eligibility variables | freeze the universe reproducibly | all as-of | 20y | above rows | every filter input available ≤ as_of |

---

## Stage 3 — Data Source Evaluation

Evaluated against **research trustworthiness**, not price. The disqualifying
axes are *survivorship handling* and *delisting returns*: a source that fails
either cannot support the objective at any price.

| Provider | Coverage (US eq.) | Survivorship | Delisting **returns** | Corp actions | Hist. identifiers | Hist. mkt cap | PIT integrity | API / bulk | Licensing | ~Cost/yr | Integration | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Norgate Data** | Full US, incl. delisted | **Free of survivorship** | **Yes** | Yes | Yes (ticker changes) | via shares (partial) | PIT index constituents | Bulk (desktop DB) + API | Retail, per-seat | **$$ (~$1–1.5k)** | Medium (bulk export → adapter) | **Primary** |
| **Sharadar (SEP/SF1/TICKERS via Nasdaq Data Link)** | Full US, incl. delisted | **Free of survivorship** | Yes (SEP delisting) | Yes | TICKERS table | **Yes (SF1 marketcap PIT)** | Strong, dated | **REST + bulk export** | Subscription | **$$ (~$1–3k)** | **Easy (clean API/bulk)** | **Primary-alt / supplementary for mkt cap & fundamentals** |
| **CRSP** | Full US, gold standard | **Free of survivorship** | **Yes (canonical delisting returns)** | Yes | PERMNO/PERMCO | Yes | Reference-grade | Bulk (academic) | Institutional/academic | **$$$$** | Hard (access + format) | **Aspirational audit benchmark** if access exists |
| FactSet / Refinitiv | Full + global | Clean (enterprise) | Yes | Yes | Yes | Yes | Strong | Enterprise API | Enterprise contract | **$$$$$** | Hard/heavy | Overkill; reject on cost/complexity |
| Polygon.io | Full US | Partial (delisted tickers exist) | **No true delisting return** | Splits/divs | Some | No PIT cap | Weak PIT | Great API | Subscription | $$ | Easy | Reject: no delisting returns / PIT cap |
| Tiingo | Broad US | Survivor-leaning | No | Divs/splits | Limited | No | Weak | Good API | Cheap | $ | Easy | Reject for depth/survivorship |
| Financial Modeling Prep | Broad | Survivor-leaning | No | Partial | Limited | Restated (look-ahead risk) | Weak | Good API | Cheap | $ | Easy | Reject: restatement/look-ahead |
| Alpha Vantage | Broad | Survivor-only | No | Partial | No | No | None | Rate-limited | Free/cheap | $ | Easy | Reject outright |
| Internal (yfinance/stooq, current `daily_prices`) | Survivors only | **Fails** | **No** | Partial | current-symbol only | forward-only | Fails | in-repo | — | — | Reject as research source (keep for live prod) |

### Recommendation — layered, two-source primary

- **Primary price + delisting + PIT index membership: Norgate Data.**
  Retail-affordable, genuinely survivorship-free, carries delisting handling and
  PIT index constituents, and supports bulk export for reproducible snapshots.
  It is the smallest spend that clears both disqualifying axes.
- **Supplementary PIT market-cap / shares / fundamentals + independent
  cross-check: Sharadar (SEP + SF1 + TICKERS) via Nasdaq Data Link.** Sharadar's
  SF1 gives point-in-time market cap and shares without restatement — the
  cleanest affordable source for Stage 2 rows 6–8 — and its independent price
  series lets us *validate* Norgate rather than trust one vendor blindly.
- **Audit benchmark (only if institutional access already exists): CRSP.** Use
  its canonical delisting returns to spot-audit a sample; do not gate Phase 2 on
  procuring it.

Two affordable, survivorship-free sources that **cross-validate each other** buy
more research integrity than one gold-standard source we can't independently
check. Neither is chosen for being cheap; each is the best affordable source on
its required axis, and the overlap is the point.

> **Procurement is the true critical-path blocker** — same posture as Phase 1's
> `blocked_source()`. No engineering below should be represented as
> research-ready until at least the Norgate license is in hand and adapted.

---

## Stage 4 — Canonical Outcome Model

All research tables key on Phase 1 **`security_id`**. New tables (proposed
names; final in the migration doc), each carrying `source` + `data_version` +
`ingestion_run_id` lineage like the Phase 1 tables:

```
security_master (Phase 1)  ──1:N──┐
   security_id (PK)               │
                                  ▼
   security_price_daily        (security_id, price_date) → open/high/low/close_raw,
                                  close_adj, total_return_factor, volume, currency
   security_corporate_action   (security_id, action_type, ex_date) → split_ratio,
                                  cash_amount   [survivorship-clean, on security_id]
   security_market_data_daily  (security_id, obs_date) → shares_outstanding,
                                  market_cap, dollar_volume   [PIT, no restatement]

delisting_event (Phase 1) ──1:1── delisting_return   (security_id) →
                                  delisting_return, terminal_price, method
                                  [fills Phase 1's nullable columns]

benchmark_series (benchmark_id, kind, name)   kind ∈ {market, sector, size}
   └─1:N─ benchmark_return (benchmark_id, price_date) → total_return
   sector_benchmark_map links GICS sector → benchmark_id (dated)

research_snapshot (snapshot_id) → universe_definition_id (Phase 1),
   data_version, source_manifest(JSONB), row_count, checksum, frozen_at
   └─1:N─ research_observation
          (snapshot_id, security_id, as_of, horizon) →
             forward_return_total,            -- survivorship-clean, delist-aware
             forward_return_benchmark_rel,    -- vs market benchmark
             forward_return_sector_rel,       -- vs sector benchmark
             forward_return_residual,         -- Important tier; nullable in MVI
             exit_kind ∈ {price, delisting, still_listed_truncated},
             eligible_flag, market_cap_at_as_of, dollar_volume_at_as_of
```

**Bridge to legacy identity (reconciliation only):** a thin
`instrument_security_map (instrument_id → security_id, valid_from, valid_to)`
lets us (a) reconcile the new clean prices against legacy `daily_prices` on
survivors, and (b) eventually re-key `predictions`/`prediction_outcomes` onto
`security_id`. Research never reads through the legacy `instruments.symbol`.

**Connection to Phase 1.** `research_observation` is the join of Phase 1
identity/universe with Phase 2 outcomes: membership comes from
`universe_membership` (as-of), eligibility inputs from
`security_market_data_daily`, the forward return from `security_price_daily` +
`delisting_return`, and the relative returns from `benchmark_return`. Every
column has an as-of ≤ the observation date — no look-ahead by construction.

---

## Stage 5 — Research Dataset Construction

Deterministic pipeline, each step reproducible from the one before:

1. **PIT universe construction.** For each monthly reconstitution date, take
   Phase 1 `universe_membership` for the chosen `universe_definition` version,
   then apply the previously-PENDING filters using `security_market_data_daily`
   **as of that date only** (`min_price`, `min_market_cap`, `min_dollar_volume`).
2. **Historical inclusion rules.** A security is included for `as_of` iff listed,
   eligible type/exchange (Phase 1), past `min_trading_age`, and passes the
   as-of size/price/liquidity screen. Inclusion is frozen into the snapshot.
3. **Delisting treatment.** If a security delists within a forward horizon, the
   forward return is computed to the **delisting return**, and `exit_kind =
   delisting`. It is **never dropped**. Membership never extends past the
   delisting date (already enforced + DQ-checked in Phase 1).
4. **Corporate-action adjustment.** Total-return factor built from
   `security_corporate_action` (splits + dividends reinvested); raw close always
   retained so adjustments are reproducible and auditable.
5. **Forward-return generation.** For each `(security_id, as_of, horizon)`:
   `forward_return_total` = adjusted exit / adjusted entry − 1, where exit is the
   priced close at `as_of + horizon` **or** the delisting return if delisting
   occurs first. Truncation of a still-listed name at the data edge is marked
   `still_listed_truncated`, not silently dropped.
6. **Benchmark-relative & sector-relative returns.** Subtract the market
   benchmark's and the as-of GICS sector benchmark's total return over the same
   window. These are the primary selection-value units.
7. **Residual returns (Important tier).** Market/sector-beta-neutralized return
   over the window; nullable and skipped in the MVI.
8. **Research snapshots + versioning + reproducibility.** Materialize the whole
   observation set into an immutable `research_snapshot` stamped with the
   universe definition version, `data_version`, a source manifest (provider +
   vendor data vintage), and a **deterministic checksum** over sorted
   `(security_id, as_of, horizon, forward_return_total)`. Re-running the same
   inputs reproduces the same checksum — the same guarantee Phase 1's universe
   builder already provides, extended to outcomes.

---

## Stage 6 — Validation of the Completed Dataset

Each check is a gate; a failure blocks the snapshot from being marked research-ready.

- **Coverage:** every included `security_id` has continuous prices over its
  membership span (no unexplained gaps beyond the trading calendar).
- **Survivorship:** the count of distinct securities ever included **rises** as
  history deepens, and delisted names are present (a survivor-only feed shows the
  opposite). Cross-check included-name counts vs Norgate's PIT index constituents.
- **Corporate-action:** reconstruct adjusted close from raw + actions and match
  the vendor's adjusted series within tolerance on a sample.
- **Delisting:** **zero** delisted-in-universe securities with a NULL delisting
  return; delisting dates equal Phase 1 `delisting_event`.
- **Missing-data:** every observation is `price`, `delisting`, or explicitly
  `still_listed_truncated` — none silently absent. Report a truncation census.
- **Point-in-time:** no field used at `as_of` has a source timestamp > `as_of`
  (assert against vendor as-of dates); market cap is not today's shares × old price.
- **Historical identifier:** forward returns follow the `security_id` across
  ticker changes (a rename does not break the series) and never bleed across a
  ticker *reuse* boundary (Phase 1 resolution).
- **Universe reconstruction:** rebuilding a past month reproduces the snapshot's
  membership exactly (checksum match).
- **Forward-return sanity:** independent recomputation from stored prices matches
  materialized returns; distribution has no impossible values (e.g. < −100%).
- **Cross-vendor:** Norgate vs Sharadar returns agree within tolerance on the
  survivor overlap; disagreements quarantined to the Phase 1 DQ ledger.
- **Reproducibility:** two clean builds from the same vendor vintage yield
  identical checksums.

---

## Stage 7 — Minimum Viable Implementation

**MVI question it must unlock:** *does signal X have out-of-sample stock-selection
value?* — answerable via annual-block IC / rank-correlation of the signal against
**survivorship-clean, delisting-aware, benchmark-relative forward returns** on
the ~500-name Validation tier over ~20 years.

### Build immediately (MVI)
1. Norgate license + `SecuritySource`-style **price/corp-action/delisting adapter**
   keyed on `security_id` (reuses the Phase 1 adapter contract & blocked-source
   discipline).
2. `security_price_daily`, `security_corporate_action`, `delisting_return`,
   `benchmark_series`/`benchmark_return`, `sector_benchmark_map`.
3. Sharadar adapter for `security_market_data_daily` (PIT market cap / shares /
   dollar volume) — needed to activate the Phase 1 PENDING universe filters.
4. Forward-return + benchmark-relative + sector-relative generation into
   `research_snapshot` / `research_observation`, with checksum.
5. Stage 6 validation gates (all Required ones) + a `mip research dataset
   build|validate|show` CLI mirroring Phase 1's ergonomics.

### Explicitly wait
- Residual/factor returns, historical index-membership tier, cross-vendor
  auto-reconciliation beyond a sampled audit, re-keying production
  `predictions` onto `security_id` (do it once, after MVI proves the pipeline).

### Dependencies
Norgate license → price/delisting adapter → Sharadar mkt-cap → universe filter
activation → forward returns → snapshot → validation. Phase 1 is a hard
prerequisite (identity + membership) and is already done.

### Acceptance criteria (Phase 2 complete when ALL hold)
1. ~500-name Validation tier, ~20y, survivorship-clean, every delisted name
   present with a non-NULL delisting return.
2. Forward returns exist for every `(included security_id, as_of, horizon)` with
   `exit_kind` set; **no observation silently dropped** for a missing future price.
3. PIT: no look-ahead in any eligibility or return input (validated).
4. Benchmark-relative and sector-relative returns present for every observation.
5. Universe filters (`min_price`/`min_market_cap`/`min_dollar_volume`) applied
   from PIT market data; Phase 1 PENDING markers cleared.
6. Every observation reproducible: same vendor vintage + definition version ⇒
   identical snapshot checksum.
7. All Stage 6 Required validation gates pass; cross-vendor sample audit within
   tolerance.
8. Docs state residual/factor returns as Important-tier deferred, and any
   remaining vendor limitations.

### Testing
Integration tests over a **fixture vendor** (as in Phase 1) covering: a delisted
loser truncated to its delisting return; a renamed security whose forward return
spans the ticker change; a ticker-reuse boundary that must not bleed; a name
failing the as-of liquidity screen; a corporate-action adjustment reproduced
from raw; and a reproducibility (checksum) test. Real-vendor tests gated behind
the license, like Phase 1.

### Estimated effort
Adapters + schema/migration: ~1 week. Snapshot/forward-return engine +
validation: ~1–1.5 weeks. CLI + docs + tests: ~0.5 week. **≈3 engineering weeks
after the Norgate + Sharadar licenses land.** Licensing/procurement lead time is
the dominant real-world cost, not code.

### Risks
- **Procurement delay / license terms** forbidding redistribution of raw vendor
  data — mitigate by storing derived returns + checksums, not redistributing raw.
- **Vendor disagreement** on adjusted prices — mitigate with the cross-vendor
  audit and quarantine.
- **Delisting-return semantics** vary by vendor (acquisition cash vs −100%) —
  standardize a documented `method` on `delisting_return`.
- **PIT market-cap gaps** pre-Sharadar-coverage — accept a documented earliest
  eligible date rather than back-filling with restated shares (which would
  reintroduce look-ahead).

---

## Deliverable summaries

**Executive recommendation.** Build the smallest survivorship-clean outcome
layer — Norgate prices/corp-actions/delisting-returns + Sharadar PIT market cap,
keyed on the Phase 1 `security_id`, materialized into immutable, checksummed
research snapshots of benchmark- and sector-relative forward returns for a
~500-name, ~20-year Validation tier. This, and only this, makes an OOS
stock-selection test trustworthy; residual/factor returns and breadth are
deferred.

**Recommended provider.** Primary **Norgate Data**; supplementary **Sharadar
(Nasdaq Data Link)** for PIT market cap and as an independent cross-check;
**CRSP** as an optional audit benchmark if institutional access already exists.
Chosen on survivorship + delisting-return integrity, not cost.

**Canonical outcome architecture.** Stage 4 — outcome tables on `security_id`,
joined to Phase 1 identity/universe, with a legacy `instrument_id` bridge for
reconciliation only.

**Data coverage matrix.** Stage 2 (required rows) + Stage 3 (source & blocking
status). Blocking status for every Required row today: **BLOCKED on vendor
license**; engineering-ready behind the adapter contract.

**Build plan.** Stage 7 — immediate MVI vs explicitly-deferred, ordered by
dependency.

**Acceptance criteria.** Stage 7 list — survivorship, delisting returns, PIT
correctness, relative returns, filter activation, reproducibility, validation
gates, documented limitations.

**Final constraint honored:** every choice above optimizes reproducibility,
point-in-time correctness, and survivorship integrity over speed or
convenience. Phase 2's purpose is not a better Trim Score — it is making every
future research conclusion trustworthy.
