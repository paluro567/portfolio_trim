# Sharadar / Historical Provider Ingestion Plan

**Date:** 2026-08-23 · **Status:** PLAN + SCAFFOLDING. No credentials configured, no data fetched.
**Contract:** `mip.calibration.source.REQUIRED_DATASETS` (unchanged) · **Adapter:** `mip.providers.historical`
**Blocks:** the failing gate in `docs/HISTORICAL_CALIBRATION_READINESS.md`

---

## 0. Verification status

Facts below are marked **VERIFIED** (read from vendor documentation during this
work) or *requires external verification* (recorded as an expectation to be
checked against the data dictionary before any loader is written). Nothing
unverified has been written into code as though it were true — the mapping table
carries a `verified` flag per dataset and only `fundamentals_pit` is set.

**VERIFIED** from [sharadar.com/docs/fundamentals](https://sharadar.com/docs/fundamentals):

- SF1 dimensions are `ARQ`/`ARY`/`ART` ("as reported") and `MRQ`/`MRY`/`MRT`
  ("most recent reported"). AR is *"a point-in-time view with data time-indexed
  to the date the form 10 regulatory filing was submitted to the SEC"* and
  **excludes restatements**; MR *"includes restatements"*.
- Date fields: `datekey`, `reportperiod`, `calendardate`, `lastupdated`.
- TICKERS covers *"common stock securities (primary class) that are active or
  delisted from Nasdaq, NYSE or NYSEMKT"*.
- History to 1998; updates daily 17:30 and 23:30 ET; reporting lag < 1 day.

**VERIFIED** from [quantrocket.com/sharadar](https://www.quantrocket.com/sharadar/):
fundamentals since 1990, prices since 1998, S&P 500 constituents since 1957,
insiders since 2005, institutions since 2013, 8-K events since 1993.

**VERIFIED** from the fsharadar docs: DAILY carries `ev`, `evebit`, `evebitda`,
`marketcap`, `pb`, `pe`, `ps`; SEP is split-adjusted OHLCV; ACTIONS carries
splits and dividends.

---

## 1. Logical dataset → Sharadar mapping

The eight logical datasets are unchanged. Where the repository already has a
table for the concept, that table is reused — no parallel schema is proposed.

| Logical dataset | Repo table | Sharadar table | PK | Availability field | Verified |
|---|---|---|---|---|---|
| security_master | `security_master` | TICKERS | `permaticker` | — | field names: no |
| prices | `security_price_daily` | SEP | `ticker`,`date` | `date` | field names: no |
| fundamentals_pit | `company_fundamentals` | SF1 | `ticker`,`dimension`,`datekey` | **`datekey`** | **yes** |
| sector_history | `historical_classification` | TICKERS | `permaticker` | — | field names: no |
| earnings_history | `earnings_observations` | SF1 | `ticker`,`dimension`,`datekey` | `datekey` | field names: no |
| corporate_actions | `corporate_actions` | ACTIONS | `ticker`,`date`,`action` | `date` | field names: no |
| delistings | `delisting_event` | TICKERS (+ACTIONS) | `permaticker` | — | field names: no |
| universe_membership | `universe_membership` | TICKERS + DAILY | `permaticker`,`date` | `date` | field names: no |

### The four dates, kept apart

Collapsing these is exactly how the current `earnings_observations` table became
unusable. The contract keeps them as separate fields:

| Date | Meaning | Sharadar |
|---|---|---|
| **event date** | when the thing happened / the period it describes | `reportperiod` |
| **filing / report date** | when it was filed with the SEC | `datekey` |
| **first-known / availability** | when *we* could have known it | `datekey` for SF1; derived for others |
| **ingestion timestamp** | when *we* fetched it | our `ingestion_run_id`, never the vendor's |

A historical date on a row is not evidence that the row was knowable then. Only
the availability field is.

---

## 2. Identifier strategy

**`permaticker` is the anchor, never `ticker`.** Sharadar's permanent id maps to
`security_master.source_security_id`, with `source = 'sharadar'`; the platform's
own `security_id` remains the internal key. The Phase-1 ingestor already refuses
to merge on ticker.

| Event | Handling |
|---|---|
| Ticker change | New `security_identifier_history` row, `valid_from`/`valid_to` closed on the old one. `permaticker` unchanged. |
| **Ticker reuse** | Two `permaticker`s share a ticker across disjoint validity windows. The lookup index `(identifier_type, identifier_value)` plus date bounds keeps them apart. **This is the failure that silently merges two companies** and is a BLOCKING DQ check. |
| Merger / acquisition | `security_lifecycle_event` with `successor_security_id`; `delisting_event.successor_security_id` records the surviving entity. |
| Delisting | `security_master.delisted_flag` + `delisting_date`, plus a `delisting_event` row. |
| Share-class change | New `share_class` on the master; a separate `permaticker` if the vendor treats it as a separate security. |

Sharadar covers *primary class only* (VERIFIED), so multi-class issuers are
represented by one line. That is a coverage limitation, not an identity bug, and
must be disclosed in any study using it.

---

## 3. Survivorship

This is the reason the whole exercise exists. The current gate fails because
**0 of 585 instruments are delisted**.

How delisted securities enter:

1. `load_security_master()` returns **every** security TICKERS has ever covered,
   including `isdelisted` names — Sharadar explicitly covers delisted tickers
   (VERIFIED).
2. Each delisted name gets a `delisting_event` row with `delisting_date`.
3. `delisting_return` and `terminal_price` are **derived**, not assumed: the
   final SEP price plus any merger/liquidation consideration from ACTIONS.
4. **Where consideration is unknown the outcome is recorded UNRESOLVED, never
   assumed to be −100%.** The Phase-2A `terminal_outcome` table already has this
   three-way semantics (delisted → terminal value, unknown → UNRESOLVED, still
   listed → TRUNCATED).
5. `universe_membership` is built per date from what was listed *then*, so a
   security that later failed is still a member on the dates it traded.

**How the gate flips to PASS.** `readiness.assess_readiness` runs live and needs:
`instruments`-equivalent delisted count > 0 **and** `security_master` populated
for `survivorship_control`; `historical_classification` populated for
`pit_classification`; ≥250 distinct as-of dates for `pit_fundamentals`; ≥250
distinct observation dates for `pit_earnings`. Nothing about the gate needs
changing — it will pass when the data is right, and not before.

---

## 4. PIT fundamentals — the selection rule

**Use `ARQ`/`ARY`/`ART` only. Never `MRQ`/`MRY`/`MRT`.** MR dimensions are
updated when a company restates, so reading one at a historical as-of imports a
later restatement into the past.

The rule, implemented once in `validation.select_pit_fundamental`:

> Among **as-reported** facts whose `datekey` ≤ `as_of`, take the one with the
> **latest `datekey`**. Optionally restrict to a `reportperiod`.

Why not join on fiscal period: a single `(ticker, dimension, reportperiod)` can
appear several times as amended filings arrive. Selecting the latest row for a
period picks the newest amendment — including ones that had not yet been filed
at `as_of`. Selecting by `datekey` picks what a reader actually had.

`lastupdated` is a **vendor revision marker for incremental loads**, not an
availability date. It must never be used as the PIT filter: a row corrected in
2026 for a 2015 period still became public in 2015.

---

## 5. Earnings — and the gap that blocks four horizons

SF1 gives the reported figure and its filing date, which is a genuine
observation date, so *reported* earnings can be reconstructed PIT.

**Sharadar does not sell analyst estimates.** Nasdaq lists Zacks products
(ZEE / ZSEE / **ZEEH — "North American Consensus Earnings Estimate History"**)
as separate databases. *Requires external verification*, but the structural
conclusion is firm:

> **Beat/miss against contemporaneous consensus cannot be reconstructed from
> Sharadar alone.**

That matters because `earnings_delivery` — which votes at 1m, 3m, 6m and 1y —
is defined as the beat rate against consensus. Without PIT consensus:

- either a second vendor supplies estimate history with an observation date,
- or the `earnings_delivery` group is **excluded** from the reconstructed signal
  and the calibration is explicitly for a reduced signal, disclosed as such.

The one thing that must not happen is computing a historical "beat" against a
consensus figure pulled today. `SourceEarningsEvent.has_contemporaneous_consensus`
makes that a testable property rather than a matter of care.

---

## 6. Prices

| Representation | Use for |
|---|---|
| `closeunadj` (raw) | Audit, reconciliation, and sanity checks against the vendor |
| `close` (split-adjusted) | Nothing on its own — an intermediate |
| `closeadj` (split + dividend adjusted) | **Feature construction and forward returns** |
| `closeadj` + terminal value | **Portfolio-value simulation**, so a delisted holding resolves to cash rather than vanishing |

`closeadj` is **restated** as new corporate actions occur, so it is not itself
point-in-time. This is acceptable for return computation — a total-return series
is meant to reflect actions — but it means the price panel must be re-derived,
not appended, when actions arrive late. The existing `security_price_daily`
already carries `total_return_factor`, `split_factor` and `dividend_amount`
separately, which is what makes re-derivation auditable.

Missing sessions are validated against `exchange_calendars` (already a
dependency); a listed security with a gap is a WARNING, a delisted one ending
early is expected.

---

## 7. Sector history — likely degraded

TICKERS carries `sector`/`industry`/`sicsector`. **Believed to be current
classification only, with no history** — *requires external verification*.

If confirmed, then:

- `historical_classification` can only be populated with a single open-ended
  record per security, which is **non-PIT** and must be labelled so;
- the `pit_classification` gate check stays FAILED;
- **`sector_relative` must be dropped from the reconstructed signal**, or the
  calibration disclosed as using a non-PIT sector map.

Backfilling today's sector into the past without that label is prohibited.

---

## 8. Universe membership

There is no ready-made "all US common stock as of T" table; membership is
**constructed and versioned**:

```
security ∈ universe(T)  ⟺  firstpricedate ≤ T ≤ lastpricedate
                        ∧  category = common stock (primary class)
                        ∧  exchange ∈ {Nasdaq, NYSE, NYSEMKT}
                        ∧  DAILY.marketcap(T) ≥ min_market_cap
                        ∧  SEP.close(T)       ≥ min_price
                        ∧  dollar_volume(T)   ≥ min_dollar_volume
```

The thresholds are the `PENDING` fields already declared in
`mip.securities.universe_policy.US_COMMON_EQUITY_V1`. The definition is written
to `universe_definition` with a version and frozen; membership is reproducible
from the definition plus the data. SP500 is available separately (VERIFIED,
since 1957) if index membership is ever wanted.

**Today's holdings play no part in the historical universe.**

---

## 9. Staged ingestion

`RAW → NORMALIZED → PIT_CLEAN → CALIBRATION_READY`, specified in
`mip.providers.historical.staging`. The load-bearing boundary is
**NORMALIZED → PIT_CLEAN**: everything before it is mechanical translation, and
that step is the only place a restated value can be excluded.

| Stage | Output | Idempotency |
|---|---|---|
| RAW | Immutable archived vendor payloads under `RawData/` | Content-hashed; differing bytes for an archived window is an error, not an overwrite |
| NORMALIZED | Vendor-neutral DTOs; no vendor column names survive | Pure function of RAW |
| PIT_CLEAN | Phase-1/2A tables keyed on `security_id` | Guarded upsert on the natural key; `lastupdated` drives revision detection |
| CALIBRATION_READY | Checksummed `research_dataset_snapshot` | Content-addressed |

Unnormalisable records are **quarantined** into the existing
`data_quality_issues` ledger, never discarded.

---

## 10. Incremental loads

- **Backfill:** full history once, by year, per table.
- **Daily refresh:** `lastupdated > watermark` per table — the field exists for
  exactly this (VERIFIED).
- **Revised filings:** a new `datekey` is a new row, never an update. History of
  what was known when is preserved by construction.
- **Corrected vendor records:** same `datekey`, changed values → a
  `data_revisions` row plus a guarded update, mirroring the existing price
  revision machinery.
- **Newly delisted:** `isdelisted` flips → new `delisting_event`; the terminal
  outcome may lag and is UNRESOLVED until known.
- **Changed classification:** close the old `valid_to`, open a new record.

No full rebuild is required except when the price adjustment basis changes.

---

## 11. Data-quality gates

Fourteen checks in `mip.providers.historical.validation`, thirteen BLOCKING,
each declaring which readiness-gate check it feeds:

| Check | Feeds |
|---|---|
| duplicate_identity, ticker_reuse, missing_permanent_identifier | survivorship_control |
| **delisted_missing_terminal_outcome** | survivorship_control |
| universe_membership_gaps | survivorship_control |
| future_leakage, fundamentals_available_before_filing, **restated_dimension_used** | pit_fundamentals |
| earnings_observed_before_availability, earnings_consensus_not_contemporaneous | pit_earnings |
| sector_classification_leakage | pit_classification |
| price_gaps (WARNING) | price_history_depth |
| impossible_date_ordering, corporate_action_inconsistency | — |

---

## 12. Minimum viable ingestion, per horizon

From the readiness audit: **1w** is price-derived, **1m/3m** additionally need
`earnings_delivery`, **6m** adds `valuation_level`, **1y** adds
`company_quality`. Mapping that onto datasets:

| Horizon | Required datasets | Sharadar tables | Sufficient with Sharadar alone? |
|---|---|---|---|
| **1w** | security_master, prices, delistings, universe_membership | TICKERS, SEP, ACTIONS, DAILY | **YES** |
| **1m** | + earnings_delivery | + SF1 | **NO** — needs PIT consensus |
| **3m** | + earnings_delivery | + SF1 | **NO** — needs PIT consensus |
| **6m** | + valuation_level | + SF1 (ARQ), DAILY | **NO** — consensus; sector if `sector_relative` retained |
| **1y** | + company_quality | + SF1 (ARQ) | **NO** — consensus |

**The smallest purchase that unblocks a first real experiment is TICKERS + SEP +
ACTIONS + DAILY, and it buys exactly one horizon: 1w.** That is a genuine result
— it makes the survivorship-clean 1w calibration runnable, which today is
impossible — but it is one horizon out of five, and the 1w signal is the least
interesting of the five on prior evidence.

SF1 additionally unblocks `valuation_level` and `company_quality`, leaving only
`earnings_delivery` short. So **SF1 + a consensus-history vendor** is what a
full five-horizon calibration requires.

---

## 13. Subscription and access

*All pricing and packaging requires external verification — none of it is
provable from repository contents, and no purchase is recommended here.*

| Table | Need | Why |
|---|---|---|
| SHARADAR/TICKERS | **REQUIRED** | Identity, delisting flags, the survivorship fix |
| SHARADAR/SEP | **REQUIRED** | Prices incl. delisted names |
| SHARADAR/ACTIONS | **REQUIRED** | Splits/dividends; merger consideration for terminal returns |
| SHARADAR/SF1 | **REQUIRED for ≥1m** | PIT fundamentals via AR dimensions |
| SHARADAR/DAILY | Optional but effectively needed | Market cap / valuation for universe filters |
| SHARADAR/SP500 | Optional | Index membership |
| SHARADAR/EVENTS, SFP, SF2, SF3 | Optional | Not needed for this calibration |
| **Consensus estimate history (e.g. Zacks ZEEH)** | **REQUIRED for `earnings_delivery`** | Not a Sharadar product |

Known coverage limitations: US common stock, primary class, Nasdaq/NYSE/NYSEMKT
only (VERIFIED). No OTC, no non-primary share classes, no non-US.

---

## 14. Implementation phases

| Phase | Work | Gate |
|---|---|---|
| 1 | Verify the data dictionary; confirm every `verified=False` mapping; confirm sector history and delisting-return availability | **Do this before writing a loader** |
| 2 | Client + credentials + RAW archival | Key present |
| 3 | security_master + delistings | `survivorship_control` |
| 4 | prices + corporate actions | `price_history_depth` |
| 5 | universe membership | membership density |
| 6 | PIT fundamentals (AR only) | `pit_fundamentals` |
| 7 | sector history | `pit_classification` (may stay FAILED) |
| 8 | earnings history (+ consensus vendor if bought) | `pit_earnings` |
| 9 | Run DQ checks, then `assess_readiness` | gate PASS/FAIL |
| 10 | **Only on PASS**, run the pre-declared calibration experiment | — |

Phase 10 is not executed in this work, and the experiment's design is already
frozen in `docs/HISTORICAL_CALIBRATION_READINESS.md` §6 so it cannot be tuned
after seeing results.

---

## 15. Unresolved questions

1. **Does Sharadar provide any historical sector classification?** If not,
   `sector_relative` must be dropped from the reconstructed signal or the study
   labelled non-PIT on that axis. *Blocks phase 7.*
2. **Can a delisting return be derived reliably from TICKERS + ACTIONS?** If
   merger consideration is absent, a material share of delistings resolve to
   UNRESOLVED — which is honest but reduces effective sample.
3. **Is SEP keyed on `ticker` only?** If so every price row must be joined
   through TICKERS to `permaticker`, and ticker reuse becomes a live hazard
   rather than a theoretical one.
4. **Is there any PIT consensus source at acceptable cost?** This alone
   determines whether four of five horizons are ever calibratable.
5. **Does the AR dimension have gaps** for companies that never filed a 10-K/Q
   in a period (IPOs, foreign issuers)? Gaps become missing states, not zeros.

---

## 16. What this work did NOT change

Deterministic signal logic, calibration logic, report rendering, the OpenAI
research integration, integrated-horizon logic and production decision rules are
all untouched. The readiness gate still fails, the report still says historical
evidence is unavailable, and no data has been fetched.
