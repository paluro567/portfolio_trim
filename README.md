# MIP — Market Intelligence Platform

Personal investment research engine. Generates per-holding and portfolio-level
decision-support reports from price, feature, fundamental and earnings data.

Every directional reading in this system is **EXPERIMENTAL**. No signal has
established predictive reliability. The reports are structured evidence, not
forecasts.

## Daily Portfolio Report Workflow

Run everything from the repository root:

```bash
cd /Users/peterluro/Desktop/stock_scoring
```

Your current holdings live in **`data/current_holdings.csv`**. That file is the
authoritative, mutable source of symbol, quantity and average cost — it is read
directly on every run. Edit it when you buy or sell. Nothing is stored in
Postgres for holdings.

Run these three commands in order on each trading day, after the close.

**1. Refresh prices and macro data** (~3 min)

```bash
uv run mip ingest prices --all && uv run mip ingest macro
```

**2. Build features for the symbols the report needs** (~20 s)

```bash
uv run mip features build --symbols AAPL,AMD,AMZN,AXP,BBAI,BE,CAKE,CELH,COIN,CORZ,CRM,CRWD,CVX,EL,ELF,FUBO,GEV,GOOG,HIMS,HNST,HOOD,INFQ,IWM,MA,MARA,META,MNDY,MSFT,NFLX,NKE,NOW,NVDA,ORCL,PANW,PATH,PINS,PLTR,PYPL,QQQ,RBRK,RZLV,SMCI,SNOW,SOFI,SPCX,SPY,T,TSLA,TTD,UNH,URNM,VOO,VTI,WYNN,XLB,XLC,XLE,XLF,XLI,XLK,XLP,XLRE,XLU,XLV,XLY,ZETA
```

**3. Generate the reports** (~15 s)

```bash
uv run mip product portfolio --as-of $(date +%F)
```

Reports land in **`data/product_reports/<DATE>/`**. Open
`data/product_reports/<DATE>/PORTFOLIO.md` first, then the individual
`<TICKER>/<TICKER>_<DATE>.md` files it points you to.

**Total runtime: about 3–4 minutes**, dominated by the price ingest.

### The symbol list in step 2 is maintained by hand

It is **current holdings + SPY/QQQ/IWM + the 11 sector ETFs**. There is no CLI
option that derives this set automatically — `mip features build` accepts only
`--symbols` (explicit list) or `--all` (every instrument, which is the slow path
described below).

Regenerate the list any time holdings change, and paste the output into step 2:

```bash
{ tail -n +2 data/current_holdings.csv | cut -d, -f1; printf 'SPY\nQQQ\nIWM\n'; /Applications/Postgres.app/Contents/Versions/17/bin/psql -U peterluro -h localhost -d mip -t -A -c "SELECT i.symbol FROM instruments i JOIN sectors s ON s.etf_instrument_id=i.id;"; } | tr -d ' \r' | grep . | sort -u | paste -sd, -
```

Or simply add the new ticker to the comma-separated list above.

### Adding a new ticker

1. Add the row to `data/current_holdings.csv`.
2. Confirm the symbol exists in `instruments` — `mip ingest prices --all`
   resolves from that table, **not** from `universe.yaml`, so a symbol present
   in `instruments` will be priced even if `universe.yaml` does not list it.
3. Add the ticker to the step-2 symbol list.
4. Run the three daily commands.

Until a new holding has prices, **market-value weight becomes unavailable for
the entire portfolio**, concentration goes `NOT_EVALUABLE`, and the ADD
suppression on oversized positions silently stops firing. One unpriced holding
degrades weights for all of them. Steps 1 and 2 fix this; check that the report
shows a real percentage rather than `unavailable`.

### Periodic — not daily

```bash
uv run mip ingest fundamentals   # weekly, or after a reporting season
uv run mip ingest earnings       # weekly, or when earnings dates shift
```

Fundamentals write one dated snapshot per instrument per day and feed the
valuation and company-quality readings, which vote only at 6m and 1y. Earnings
supply scheduled-event dates and the delivery record. Neither changes
meaningfully day to day; both are cheap enough to run weekly.

### Do not use `mip update` as the daily workflow

`uv run mip update --as-of <DATE>` runs twelve stages, and its features stage
calls `pipeline.build(None)` — scoping to **every active non-index instrument**
(currently 585), not just your holdings. Any instrument with no existing feature
history falls back to `history_start_date` (`2010-01-01`, `src/mip/core/config.py`),
so several hundred reference-universe securities each rebuild sixteen years of
history. That is tens of millions of rows and runs for hours.

The reference universe is used only for **fundamentals-based peer comparison**
(`src/mip/product/quality.py`, `src/mip/product/valuation.py` read
`company_fundamentals`). Those securities need **no** `feature_store_daily`
rows, so the work is wasted for reporting purposes.

`mip update` also generates the older `mip.engine.report` output — it never
writes `data/product_reports/`, so it does not replace step 3.

### Do not regenerate old report dates

`data/product_reports/<DATE>/` has **no overwrite guard**. Re-running
`mip product portfolio --as-of <PAST DATE>` silently replaces that cohort using
*today's* holdings, destroying the frozen evidence of what was actually
recommended then. Report directories are gitignored, so there is usually no way
back. Only ever generate for a date that has no directory yet.
