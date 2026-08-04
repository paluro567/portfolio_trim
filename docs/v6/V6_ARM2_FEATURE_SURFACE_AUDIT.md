# V6 Arm 2 — Feature Surface Audit (Part 3)

Only the surface required for Arm 2 was recomputed. The platform was **not** rebuilt.

## 1. Registry

69 feature definitions: **41 instrument-scope**, **28 market-scope**. Store is year-partitioned (`feature_store_daily_y2009…y2028`, `feature_store_market_daily_y2009…y2028`).

## 2. Price-derived classification (frozen rule, step 1)

The registry has no `family` column. The authoritative, mechanical discriminator is **`uses_adjusted_prices IS NOT NULL`** — the calculator declares an adjustment policy exactly when it reads the price table. Fundamental, earnings and macro calculators leave it NULL.

- **29 price-derived** (25 adjusted, 4 raw-price: `atr14_pct`, `dist_52w_high`, `dist_52w_low`, `gap_1d`)
- 40 not price-derived

**2 of the 29 are market-scope** (`regime_bull`, `sector_breadth_ma50`). The frozen injection `f_i(ρ) = f_i + κ·ρ·Φ⁻¹(rank(y_i))` is indexed by instrument *i*; a market-scope feature has one value per date and no *i*. They are therefore **structurally outside the injection formula** — an exclusion forced by the frozen formula, not a discretionary choice.

**Injectable surface: 27 instrument-scope price-derived features.**

## 3. Coverage of the injectable surface

23 of 27 fully covered (coverage = 1.0000). Four at zero: `rel_ret_sector_{5,21,63,126}d` — no sector ETFs.

## 4. Forward-information check

`ret_21d` is `sessions_return(adj_close, 21)`, strictly backward-looking. Verified separately that **no registered feature declares `ret_21d` in `depends_on`**, so injecting it cannot leak into a derived feature. In particular `rel_ret_spy_21d` computes its own return from `adj_close` rather than reusing `ret_21d` (`src/mip/features/relative.py:36`); only `rel_ret_spy_accel_21d` has a dependency, and it is on `rel_ret_spy_21d`, not on `ret_21d`.

**Injection into `ret_21d` therefore has exactly one propagation path: direct value reads by models.** This is a clean experimental property and it is what made B-01 measurable.

## 5. Lookback

`ret_21d` needs 21 sessions + 5 buffer. Percentile-based consumption (`momentum_exhaustion`) needs ≥252 observations; the cell grid enforces ≥252 prior sessions per cell. **HNST is excluded** from the injectable panel — its history begins 2021-05-04, leaving too little pre-2012 lookback.

## 6. Determinism and versioning

All definitions are `version=1`. `computed_at` is stamped per row. Two consecutive `mip features build` runs over the same window produced identical row counts (855,418 / 100,739). Content hashing is deferred to R9, which is gated behind R2.

## 7. Audit artifact

Per-feature scope, coverage, non-null count, date range and consumer list: `/tmp/feature_surface_audit.csv` (to be relocated under `docs/v6/` once R2 is closed).
