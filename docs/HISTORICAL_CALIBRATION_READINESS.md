# Historical Calibration — Readiness Audit and Ingestion Contract

**Date:** 2026-08-23 · **Verdict: GATE FAILED. Calibration is BLOCKED.**
**Gate implementation:** `src/mip/calibration/readiness.py` (live queries, re-run every report)

---

## 1. What the gate is for

Historical calibration answers one question: *for a current deterministic
security-view state, what did forward returns actually look like historically?*

That question is only answerable if three things hold at once. This audit found
that **none of them do**, and the gate is implemented in code so the answer is
re-derived from the database on every run rather than trusted from this
document.

## 2. Result — 5 of 6 checks FAIL

| Check | Result | Observed |
|---|---|---|
| `survivorship_control` | **FAIL** | 585 instruments, **0 delisted**; `security_master` = 0, `delisting_event` = 0 |
| `pit_fundamentals` | **FAIL** | **3** distinct `as_of_date` values, all 2026-08-07 → 2026-08-16 |
| `pit_earnings` | **FAIL** | 13,231 observations spanning 2001-10-26 → 2027-02-18, from **3** `observed_at` dates |
| `pit_classification` | **FAIL** | `historical_classification` = 0 |
| `signal_reconstructability` | **FAIL** | Reconstructable at `1w` only; blocked at `1m`, `3m`, `6m`, `1y` |
| `price_history_depth` | PASS | 537 instruments with ≥5y; 2010-01-04 → 2026-08-14 |

### 2.1 Survivorship

Zero of 585 instruments are delisted. Every name in the universe is present
*because it survived*. A forward-return study over this population measures
selection, not signal — the losers were removed before the question was asked.
All 14 survivorship-clean tables are empty.

### 2.2 Point-in-time reconstruction

**Fundamentals** are a snapshot, not a vintage series: three as-of dates, all
within a nine-day window last month. There is no way to know what a P/E looked
like in 2018 from this data.

**Earnings are worse, and the shape of the problem is easy to miss.** The table
holds 25 years of earnings events — which looks like history. But `observed_at`
takes only three values, all in August 2026. The entire back history was
witnessed in three ingests. Using a 2015 earnings surprise at a 2015 as-of would
be reading a 2026 observation into the past. The dates are accurate; the
*observability* is not.

### 2.3 Signal reconstructability — the subtle blocker

Even granting clean data, the signal itself must be reconstructable. The
deterministic security view is a majority vote across phenomenon groups, and
different groups vote at different horizons:

| Horizon | Reconstructable groups | Blocked groups |
|---|---|---|
| 1w | absolute_momentum, trend_position, sector_relative, market_regime, volatility, own_history | — |
| 1m | + market_relative | earnings_delivery |
| 3m | + market_relative | earnings_delivery |
| 6m | (as 1w) | earnings_delivery, valuation_level |
| 1y | (as 1w, no sector_relative) | earnings_delivery, valuation_level, company_quality |

Only **1w** is composed entirely of price-derived groups. At every other horizon
the view depends on fundamentals or earnings that have no usable history, so
there is no historical state to condition on — the thing calibration would
measure cannot be recreated.

And 1w would still be survivor-only, so it fails on §2.1 anyway.

## 3. Decision

Per the standing instruction not to backtest today's survivors:

- **No calibration study was run.** Not even a survivor-only one labelled
  INCONCLUSIVE — running it would produce a number that would eventually be
  quoted.
- Every horizon reports `ValidationStatus.UNAVAILABLE` with the gate's reason.
- The report states plainly that historical evidence is unavailable and why.
- `blocked_source()` raises rather than falling back to the legacy tables.

## 4. What is missing, in priority order

1. **Delisting data with terminal returns** — the single most important gap.
   Without it, a position that delists simply vanishes from the sample and every
   forward-return statistic is biased upward.
2. **PIT universe membership** — who was in the universe *then*, not who is now.
3. **PIT fundamentals vintages** — as-reported figures with the date they became
   knowable, not restatements.
4. **Earnings with true observation dates** — the estimate and actual as they
   stood when published.
5. **PIT sector/industry classification** — classification as of the historical
   date.
6. **Prices keyed on a permanent `security_id`**, covering delisted names.

Price history depth is adequate and is not a blocker.

## 5. Ingestion contract (provider-neutral)

Declared in `src/mip/calibration/source.py` as `REQUIRED_DATASETS`, and
deliberately vendor-neutral: the protocol names datasets and fields, never a
provider. Where the repository already has a table for the concept, the contract
**reuses that table** rather than proposing a new schema.

| Logical dataset | Existing table | Status | Required fields |
|---|---|---|---|
| `security_master` | `security_master` | EMPTY | security_id, source, source_security_id, first_seen, last_seen |
| `prices` | `security_price_daily` | EMPTY | security_id, price_date, OHLC, volume |
| `fundamentals_pit` | `company_fundamentals` | SNAPSHOT-ONLY | security_id, as_of_date, period_end, publication_date, metrics |
| `sector_history` | `historical_classification` | EMPTY | security_id, valid_from, valid_to, scheme, sector, industry |
| `earnings_history` | `earnings_observations` | CONTAMINATED | security_id, earnings_date, **observed_at**, eps_estimate, eps_actual |
| `corporate_actions` | `corporate_actions` | POPULATED (survivor-only, ticker-keyed) | security_id, ex_date, action_type, ratio, amount |
| `delistings` | `delisting_event` | EMPTY — **critical** | security_id, delisting_date, reason, **delisting_return**, terminal_price |
| `universe_membership` | `universe_membership` | EMPTY | universe_id, security_id, valid_from, valid_to |

Any provider satisfying `HistoricalDataSource` can fill these. No vendor name
appears in the application.

## 6. The experiment, when data permits

Pre-declared now so it cannot be tuned after seeing results:

- **Condition on** the existing deterministic security view — `POSITIVE`,
  `CONFLICTED`, `NEGATIVE`, `NEUTRAL` — at 1w/1m/3m/6m/1y. No new model.
- **Question:** do these states correspond to meaningfully different forward
  return distributions?
- **Split:** chronological train / validation / test. No random split, no
  threshold tuning.
- **Baselines:** unconditional stock distribution, SPY, sector benchmark, and
  the momentum and mean-reversion baselines already in the repository.
- **Statistics:** dependence-aware. Same-date cross-sectional correlation and
  overlapping forward windows both inflate naive n; the resampling unit must be
  dates, per gate G11 in `docs/VALIDATION_GATES.md`.
- **Promotion** requires PIT-clean data, survivorship control, historical
  reconstructability, adequate sample, out-of-sample directional stability, and
  a result not confined to one regime. Otherwise the status stays INCONCLUSIVE
  or REJECTED.

## 7. Signal freeze

Calibration conditions on a signal, so the signal is frozen and hashed:
`mip.calibration.signal_definition.current_signal_definition()` derives the
signature from the live product constants. Change a threshold and the signature
changes, which invalidates any artifact computed against the old one — a
calibration is only ever served for the exact definition it was computed for.

## 8. What is explicitly NOT allowed

- Using today's web or today's model to reconstruct historical research,
  sentiment, or narrative. Historical qualitative data would require a genuinely
  timestamped archival corpus with a hard as-of cutoff, which does not exist
  here.
- Any LLM-derived field in the historical channel. Enforced by an AST test:
  `mip.calibration` may not import `mip.research_assistant` or `openai`.
- Backtesting on the surviving universe and labelling the result
  INCONCLUSIVE. A number once produced gets quoted.
