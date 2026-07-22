# Price Data: Canonical Semantics, Revision Policy, and the 2026-07-20 Tripwire Incident

## 1. Canonical field semantics

Every layer — provider request, normalization, storage, features, and
revision comparison — agrees on these definitions:

| Field | Semantics | Source column | Notes |
|---|---|---|---|
| `open`, `high`, `low`, `close` | **Raw as-traded prices in split-adjusted share units.** Yahoo restates raw OHLC into current share units after a split; it does **not** dividend-adjust them. | `Open/High/Low/Close` with `auto_adjust=False` | Historically byte-stable between fetches (measured 2026-07-20). A new split restates the whole history — handled by the split tripwire. |
| `adj_close` | **Total-return adjusted close**: raw close × cumulative split *and* dividend factor, back-adjusted so the latest bar equals its raw close. | `Adj Close` with `auto_adjust=False` | The factor product is **recomputed continuously by the provider with float jitter** (measured relative drift up to ~5.4e-7 across 2010-2026 history within 35 minutes). Comparisons must therefore use a materiality tolerance. |
| `volume` | Shares traded, as reported by the provider (split-adjusted units, integer). | `Volume` | Compared exactly; consolidated-volume corrections are genuine revisions. |
| dividends | Cash amount per share on the ex-date. | `Dividends` action column | Stored in `corporate_actions`; arrival back-shifts all earlier `adj_close`. |
| stock splits | Ratio effective on the ex-date. | `Stock Splits` action column | Stored in `corporate_actions`; arrival restates raw OHLC history → forces a full refresh. |

The provider request is pinned to `auto_adjust=False` so raw close and
adjusted close are **both** delivered and stored; features choose per
`feature_definitions.uses_adjusted_prices`. Raw prices are never
silently replaced by adjusted prices or vice versa.

**Only completed sessions are ingested.** The fetch window ends at the
last completed NYSE session (`resolve_market_date`: close + buffer, same
rule the orchestrator uses) — an in-progress intraday bar is a quote,
not a fact, and belongs to no ingestion.

## 2. Revision comparison tolerances

A re-fetched overlap row is compared field-by-field against the stored
row. A difference is a **revision** only if it is *material*:

| Field | Rule | Justification |
|---|---|---|
| `open/high/low/close/adj_close` | material iff `abs(new−old) > max(2e-6, 1e-5 × abs(old))` | Measured provider adjustment-factor noise: ≤ ~5.4e-7 relative. Smallest genuine adjustment signal: ~5.5e-5 relative (a $0.01 dividend on a ~$180 close). `1e-5` sits ≥18× above observed noise and ≥5× below the smallest genuine signal. The `2e-6` absolute floor (two storage quanta of `NUMERIC(18,6)`) protects sub-dollar prices where one quantum is itself float wobble. |
| `volume` | material iff integers differ | Provider history volumes are stable integers; changes are genuine. |
| any field `NULL↔value` | always material | Missing-data transitions are real information. |

Sub-material differences are ignored entirely: no revision row, no
update, no rewrite of the stored value (the stored value is equal to the
provider's within measurement noise).

## 3. The adj_close tripwire (full-history refresh policy)

A full-history refresh is triggered for a symbol **only** when the
overlap window proves a genuine historical re-adjustment:

1. **Pure re-adjustment signature** — a *material* `adj_close` change on
   a session **strictly before the newest fetched session**, while that
   row's raw `close` is unchanged. This is the fingerprint of a
   dividend back-adjustment or factor restatement: adjusted history
   moved, raw history did not.
2. **New split action** — a split not previously recorded arrives (raw
   OHLC history is restated by the provider in new share units).

Explicitly **not** escalated:

- The newest session's own values changing (a completing/corrected
  trailing bar) — recorded as an ordinary revision.
- A date where **both** raw close and adj_close changed — that is a
  spot data correction, recorded as a revision where it occurred.
- Sub-tolerance float noise — ignored entirely.

Every escalation logs the triggering field, stored value, incoming
value, absolute difference, relative difference, tolerance, affected
date, and the reason. The refresh pass reuses the same materiality
rules, so a refresh cannot itself manufacture noise revisions.

**Systematic raw-shift guard.** During the incremental pass, if a *raw
close* (not adj_close) shift is material on more than half of the
compared overlap sessions (`RAW_SHIFT_ALERT_FRACTION`, minimum
`RAW_SHIFT_MIN_ROWS` rows) with **no** split action to explain it, the
symbol fails loudly with a semantic error instead of recording the
shifts as revisions. This is the signature of `auto_adjust` flipping to
`True`, a raw-vs-adjusted column swap, or a provider schema change — a
configuration/semantics fault, not thousands of genuine revisions. The
guard is scoped to the incremental pass only: a deliberate full refresh
(manual, or triggered by a proven split/adjustment) legitimately
rewrites raw history and must reconcile it.

## 4. Archive identity and immutability

Raw archive artifacts are write-once. Identity:
`{category}/{name}/{start}_{end}_run{run_id}[-{label}][.rejected].csv`.
The incremental pass uses no label; the within-run full-refresh pass
uses `-full`, so the two passes can never collide. Writing **identical
bytes** to an existing path is a logged no-op (idempotent); writing
**different** bytes to an existing path remains a hard
`PermanentError` — immutability is never relaxed.

## 5. Transaction boundary

- The prices stage runs in **one database transaction** (stage-scoped
  `session_scope`: commit on success, rollback on stage failure).
- Inside the stage, **each symbol runs in a SAVEPOINT**
  (`begin_nested`): a symbol that fails mid-flight has *all* its
  database mutations (price rows, revisions, quality issues, action
  rows) rolled back; the run continues, the run record marks the
  symbol failed, and run status becomes `partial`.
- Archive CSVs are filesystem writes and therefore non-transactional:
  a rolled-back symbol/stage can leave archive files referencing a
  run_id with no surviving DB mutations. This is safe litter —
  immutability holds, and a stage retry opens a new run_id so paths
  never collide across attempts.
- Retries: stage-level retry rolls back the whole stage first (no
  duplicate revisions/rows); within a run, the refresh pass re-fetches
  rows the incremental pass just wrote, finds them identical, and
  records nothing twice.

## 6. Incident root cause — 2026-07-20 "tripwire storm"

**Symptom.** `uv run mip update` (run 44/prices run 45, 14:38 EDT,
market open): 74 of 78 symbols fired `prices.adj_close_tripwire`,
115,818 rows "updated" (115,745 of 116,105 revisions were adj_close),
prices stage took 1,482 s, and SNOW + XLY failed with
`archive is immutable — refusing to overwrite ..._run45.rejected.csv`.
Friday's run 41 (09:44 EDT, 14 minutes after the open) had already
shown the same storm (35,566 updates).

**Root causes (all demonstrated, none guessed):**

1. **Partial intraday bars were ingested as facts.** The fetch window
   ended at wall-clock `today()` even though the platform's own
   `resolve_market_date` knew the session was incomplete. Friday's
   09:44 run stored 14-minutes-after-open bars; Monday's run compared
   them against Friday's completed bars → a guaranteed `close` +
   `adj_close` "revision" on that date for every symbol → the tripwire
   read it as a corporate-action re-adjustment. Evidence: AMD's *only*
   adj_close revision in run 45 was Friday's bar, off by $31.76
   (6.8% — its actual intraday move after 09:44); 77 close revisions ≈
   one per symbol, all on Friday.
2. **Zero-tolerance comparison at the 1e-6 storage quantum.** Once the
   tripwire forced a full-history diff, Yahoo's continuously
   recomputed adjustment factors differed in the low-order bits across
   ~16 years. Measured live: stored values written at 14:38 differed
   from a 15:12 fetch by 1e-5…1.5e-4 absolute (3e-8…5.4e-7 relative)
   on historical dates — pure float jitter, while raw OHLC was
   byte-identical. Result: thousands of sub-noise adj_close
   "revisions" per symbol per run (AAPL 3,133; MSFT 3,199; SPY 3,171),
   and each run's rewrite guaranteed the next run would find fresh
   jitter — a self-perpetuating storm.
3. **Within-run archive collision.** SNOW's and XLY's *live partial
   bars* were OHLC-incoherent (SNOW open 267.12 < low 267.29 —
   snapshot skew impossible in a completed bar) → rejected by
   validation in the incremental pass **and again** in the tripwire's
   full-refresh pass. Both passes archived rejected rows for the same
   single date with the same run_id → identical path
   `2026-07-20_2026-07-20_run45.rejected.csv` → immutable-archive
   refusal → symbol marked failed.
4. **No per-symbol transaction isolation.** The failed symbols' partial
   mutations from the incremental pass (e.g. SNOW's Friday revision)
   remained in the stage session and were committed.

**Fixes.** (1) Fetch end = last completed session; the provider request
itself excludes in-progress bars. (2) Field-specific materiality
tolerances (§2). (3) Escalation requires the pure re-adjustment
signature or a new split (§3). (4) Pass-labeled archive identity plus
identical-content dedupe (§4). (5) Per-symbol savepoints (§5). (6) One
`prices.symbol_done` per symbol with separate incremental/refresh
breakdowns; the refresh pass logs `prices.full_refresh_done`.

## 7. Known limitations

- A genuine provider correction on a date **outside** the overlap
  window that never touches adj_close is not detected (pre-existing
  D12 design: only re-adjustments justify deep refreshes).
- Stored `adj_close` may sit up to `max(2e-6, 1e-5×price)` from the
  provider's latest float recomputation — inside measurement noise by
  construction, and it prevents unbounded rewrite churn.
- Archive litter: files from rolled-back attempts persist (documented
  above); they are inert and never overwritten.
- `resolve_market_date` falls back to wall-clock `today` only when the
  trading calendar is empty (bootstrap before `mip calendar build`).
