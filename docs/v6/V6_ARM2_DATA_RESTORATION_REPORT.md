# V6 Arm 2 — Data Restoration Report (R1, R3)

**Date:** 2026-08-01 · **Class: B (approximate).** This is a **new study substrate**, never a reproduction of prior work.

## 1. Starting state

The live `mip` database held **1 table**. The prior research panel was lost.

## 2. Restoration sequence — all figures are command output

| Step | Command | Result | Wall clock |
|---|---|---|---|
| Schema | `uv run alembic upgrade head` | 1 → **86 tables**, 11 migrations, chain intact | — |
| Universe | `mip universe seed` | **78 instruments**, 11 sectors, 29 industries | — |
| Calendar | `mip calendar build --from 2010` | **4,419 sessions**, 2010-01-04 → 2027-07-30, 36 half-days | — |
| Prices | `mip ingest prices --symbols "…" --full-refresh` | **38,086 rows**, 0 updated, run 1 success | **9 s** |
| Macro | `mip ingest macro` | **25,910 obs**, 18 FRED series, run 3 success | **13 s** |
| Features | `mip features build --from 2010-01-01` | 69 defs, **855,418** instrument + **100,739** market values | **44 s** |

Total restoration wall clock: **66 seconds.** The pre-Stage-0 estimate was 4–6 hours; that estimate was wrong by roughly two orders of magnitude.

## 3. Price panel (verified by query)

| Symbol | Rows | From | To |
|---|---|---|---|
| ADBE | 4,169 | 2010-01-04 | 2026-07-31 |
| AMD | 4,168 | 2010-01-04 | 2026-07-31 |
| AMZN | 4,169 | 2010-01-04 | 2026-07-31 |
| CRM | 4,169 | 2010-01-04 | 2026-07-31 |
| HNST | 1,316 | 2021-05-04 | 2026-07-31 |
| IWM | 4,169 | 2010-01-04 | 2026-07-31 |
| NOW | 3,541 | 2012-06-29 | 2026-07-31 |
| QQQ | 4,169 | 2010-01-04 | 2026-07-31 |
| SPY | 4,169 | 2010-01-04 | 2026-07-31 |
| TSLA | 4,047 | 2010-06-29 | 2026-07-31 |

**Operating companies: 7** (ADBE, AMD, AMZN, CRM, HNST, NOW, TSLA). **Benchmark ETFs: 3** (SPY, QQQ, IWM). No sector ETFs exist in `universe.yaml`.

## 4. Class-B declaration (R3)

This panel is **not** the panel Arm 1 and Arm 1.5 ran on. It is a fresh reconstruction from the vendor's current adjusted-close series. Consequences, stated rather than papered over:

- Adjusted closes reflect **today's** corporate-action history, not the history as known at each `as_of`. Split/dividend restatements are silently folded in.
- The universe is survivorship-shaped: these 10 symbols were chosen previously and all still trade.
- Arm 1 / Arm 1.5 numbers are **not comparable** to anything computed here. Any cross-arm comparison must be flagged.

## 5. Feature coverage — what did NOT restore

**Live (27 instrument-scope price-derived + 27 of 28 market-scope).**

**Zero coverage — 19 features:**

| Group | Features | Cause |
|---|---|---|
| Fundamentals (10) | `pe_trailing`, `pe_forward`, `pe_*_chg_63d`, `price_to_sales`, `profit_margin`, `debt_to_equity`, `eps_growth_yoy`, `revenue_growth_yoy`, `log_market_cap` | No fundamental snapshots; **not PIT-restorable** |
| Earnings (4) | `days_since_earnings`, `days_until_earnings`, `earnings_recency`, `eps_surprise` | No earnings observations; **not PIT-restorable** |
| Sector-relative (4) | `rel_ret_sector_{5,21,63,126}d` | No sector ETFs in the universe |
| Market breadth (1) | `sector_breadth_ma50` | No sector ETFs |

### 5.1 Why fundamentals and earnings were NOT reconstructed (B-05)

`mip ingest fundamentals` snapshots "one dated row per instrument per day" **going forward**. It cannot produce a 2012 row containing 2012's then-known trailing EPS. Backfilling it would write **today's** restated figures onto historical dates — forward information, on the exact axis the price-poisoning test exists to protect.

Per the standing instruction — *do not silently substitute reconstructed data for lost point-in-time data* — **no substitution was made.** These features remain empty and the three models that depend on them are reported as degraded, not as working.

## 6. Model liveness on the restored panel (measured, 90 cells, horizon 1m)

| Model | Official | Output varies? | Note |
|---|---|---|---|
| `interest_rate_sensitivity` | yes | yes (sd 25.6) | restored by the macro ingest |
| `macro_regime` | yes | yes (sd 25.0) | |
| `momentum_exhaustion` | yes | yes (sd 28.0) | |
| `relative_strength` | yes | yes (sd 26.9) | |
| `valuation` | yes | **NO (sd 0.0000)** | fundamentals absent |
| `earnings_behavior` | yes | **NO (sd 0.0000)** | earnings absent |
| `sector_rotation` | yes | **NO (sd 0.0000)** | sector ETFs absent |

**Only 4 of 7 official models produce varying output.** A constant series has undefined rank IC, so `valuation`, `earnings_behavior` and `sector_rotation` cannot contribute to `TRANSMISSION = IC_M / IC_F` (B-04).

A per-symbol/per-date liveness call returned "non-neutral" for all nine models, which initially looked healthy. It was misleading: these three models return a **non-neutral constant**, not a neutral flag. Liveness had to be measured as output *dispersion*, not as the neutral flag.

## 7. Backup

Not taken. R1 requires a backup **immediately after** restoration; the restoration is not final while B-04/B-05 leave three models dark. Taking a backup now would enshrine a substrate that should not be used.
