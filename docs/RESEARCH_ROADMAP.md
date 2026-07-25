# Research Roadmap — What to Investigate Next

**Purpose:** decide which information families are most likely to add *incremental*
predictive information beyond the frozen seven-model ensemble. No implementation.

**The governing lesson (from CPE + analogue, both rejected):** re-expressing
information the ensemble already has adds nothing. The CPE's apparent edge was
market-era persistence already encoded by the regime models; it carried no
incremental value and its confidence was inverted. Therefore the only directions
worth pursuing are **genuinely orthogonal information families** — data the seven
models cannot see — and the **binding constraint is point-in-time data
acquisition**, not modeling (the framework generalizes evaluation, not
ingestion).

## What the ensemble already encodes (the overlap map)

| Model | Information |
|---|---|
| interest_rate_sensitivity, macro_regime | rates, curve, macro (FRED) |
| sector_rotation, relative_strength | sector/relative price behavior |
| momentum_exhaustion | own-price momentum / technical / volatility |
| earnings_behavior | earnings **timing** + realized surprise |
| valuation | fundamentals P/E, P/S — **currently inert** (≈1 PIT snapshot) |

So the ensemble is **price + macro/rates heavy, fundamentals-weak, and blind to
positioning, forward-looking expectations, and soft/text information.** Those
three buckets are where orthogonal signal lives.

## Ranking (5 dimensions, ★ = better)

| Direction | Info gain | Orthogonality | Data availability | PIT feasibility | Impl. effort | Verdict |
|---|---|---|---|---|---|---|
| **1. Insider transactions (SEC Form 4)** | ★★★★ | ★★★★★ | ★★★★★ (free, EDGAR) | ★★★★★ (filing date) | ★★★☆ | **Top EV** |
| **2. Short interest / crowding (FINRA)** | ★★★☆ | ★★★★ | ★★★★★ (free) | ★★★★ (publication date) | ★★★★ (cheap) | **High EV, cheap** |
| **3. Analyst estimate revisions** | ★★★★★ | ★★★★★ | ★★ (paid vintages) | ★★★ (needs true vintages) | ★★☆ (data is the wall) | **Highest ceiling, data-gated** |
| **4. Options-implied (IV / skew / term)** | ★★★★ | ★★★★ | ★★ (paid history) | ★★★★ (EOD quotes) | ★★ (heavy) | **High ceiling, data-hard** |
| **5. Fundamentals maturation + quality/accruals** | ★★★ | ★★ (overlaps valuation model) | ★★★★ | ★★★★ (snapshot as_of) | ★★★★ (passive) | **Unlock existing, time-gated** |
| **6. Firm-level credit (CDS / issuer spreads)** | ★★★ | ★★★ | ★★ | ★★★ | ★★ | Later |
| **7. Earnings-call / news text (NLP)** | ★★★★ | ★★★★ | ★★★ | ★★★ | ★ (heaviest) | Research-only, later |

*(Effort ★ scale: more ★ = less effort.)*

---

## The two orthogonal buckets, and why each beats the ensemble

### Bucket A — Positioning / flow (the ensemble is blind to *who is trading*)

**1. Insider transactions (SEC Form 4).** Corporate insiders' open-market buys/
sells. Orthogonal to price and macro; decades of evidence that insider **net
buying and cluster buys** predict forward returns. The ensemble has no window
into insider behavior at all.
- *Data:* SEC EDGAR Form 4 filings — **free**, structured XML.
- *PIT:* clean — use the **filing acceptance timestamp** (not the transaction
  date) as the availability date; handle Form 4/A amendments append-only. Same
  survivorship caveat as the whole platform (delisted names absent).
- *Features:* trailing net insider buying $, buyer breadth, cluster-buy flag,
  officer-vs-director weighting, buy/sell ratio over 3/6/12m.
- *Effort:* **Medium** — the EDGAR ingestion + Form 4 parser is the bulk; features
  and the model are the platform's standard pattern.

**2. Short interest / crowding (FINRA/exchange).** Short interest as % of float,
days-to-cover, and its *change*. Orthogonal-ish (partial overlap with momentum
via crowding); captures squeeze risk and bearish conviction the ensemble misses.
- *Data:* FINRA bi-monthly short-interest — **free**.
- *PIT:* use the **publication date** (settlement date + ~8 business-day lag), not
  the settlement date.
- *Features:* SI%float, days-to-cover, ΔSI, utilization proxy.
- *Effort:* **Low** — small dataset; the cheapest orthogonal family to test.

### Bucket B — Forward-looking expectations (the ensemble sees only *realized* fundamentals)

**3. Analyst estimate revisions.** Revision *breadth* and *momentum* (up/down
revisions to forward EPS/revenue). The single strongest orthogonal candidate —
post-revision drift is one of the most robust documented anomalies, and it is
entirely absent from the ensemble (which sees realized earnings *after* the fact,
never the changing forward expectation).
- *Data:* the hard part — needs a source with **true historical vintages** (what
  the estimate was *on each past date*): I/B/E/S, Zacks, Refinitiv, Visible Alpha
  (paid). **yfinance current consensus is useless for backtesting** (look-ahead).
- *PIT:* the entire difficulty — using current consensus is a look-ahead bug;
  only vintaged estimates with revision dates are valid.
- *Effort:* modeling is easy; **data acquisition is the wall** — start procurement
  evaluation now, as it is the long pole.

**4. Options-implied information.** Implied-vol level vs realized, **skew**
(put-call IV asymmetry), term structure, and put/call flow. Forward-looking,
risk-neutral, orthogonal; skew and the variance risk premium have return-
predictive evidence. The ensemble has only *realized* volatility.
- *Data:* historical EOD options chains (paid: ORATS, OptionMetrics, or scraped
  with care). Costly/heavy.
- *PIT:* clean if EOD quotes are timestamped; needs care on IV computation
  (dividends, rates, American exercise).
- *Effort:* **High** — data + an options-analytics layer.

### Adjacent — unlock what already exists

**5. Fundamentals maturation + quality/accruals.** The valuation model is *already
built* but inert because only ~1 PIT fundamentals snapshot exists (yfinance can't
backfill vintages). This needs no new model — just **time** (daily snapshots are
already accumulating) plus a small **accruals / earnings-quality** feature set
(Sloan accruals, cash-flow-vs-earnings) once ≥1 year of snapshots exists. Moderate
orthogonality (overlaps the valuation model's intent), but near-zero marginal
effort and already in motion — a passive win to let run.

---

## Recommended investigation order

0. **Build the orthogonality pre-screen FIRST (process, ~days).** Before building
   any model, use the new shadow framework to cheaply measure a *crude* signal's
   incremental information: capture a rough feature as a shadow experiment, run
   the block-bootstrap combined−baseline test on a small sample, and **kill
   candidates that overlap before full implementation.** This is the direct
   antidote to the CPE failure mode and makes the rest of the roadmap cheap.
1. **Short interest (Rank 2)** — cheapest orthogonal family; fastest to a
   pre-screen read; builds the "positioning" muscle.
2. **Insider transactions (Rank 1)** — best expected value; builds the EDGAR
   ingestion capability reused by any future filing-based family.
3. **(Parallel, passive) Fundamentals maturation (Rank 5)** — let snapshots
   accumulate; add accruals features when data supports it. Zero opportunity cost.
4. **(Parallel, procurement) Scope analyst-revision and options data (Ranks 3/4)**
   — the highest ceilings but data-gated; begin source evaluation now because
   acquisition is the long pole, and gate the build on a vintage-clean feed.
5. **Later:** firm-level credit (Rank 6), earnings-call/news NLP (Rank 7) — high
   orthogonality but heaviest effort and (for NLP) a deliberate step beyond the
   platform's current no-LLM-prediction ethos.

## Cross-cutting caveats (apply to every direction)

- **The bar is incremental, not standalone.** A signal must beat the *combined*
  seven-model system on the holdout with a block-bootstrap CI excluding zero —
  not merely beat coin-flip alone (the CPE cleared the latter and still failed).
- **Survivorship + small cross-section (~78 names)** cap statistical power and
  bias positioning signals upward; per-name families (insider, short interest)
  will be sparse — plan for low effective sample and honest neutrals.
- **PIT is the make-or-break.** Every family lives or dies on a vintage-clean
  availability date; a current-value shortcut is a look-ahead bug (the reason
  yfinance estimates can't be used for revisions).
- **Each family = new ingestion + PIT features + a shadow model**, then the
  framework's validation is automatic. Data engineering, not modeling, is the
  cost — budget accordingly.

## Explicitly not recommended

Intraday / microstructure / order-flow (not PIT-feasible at daily frequency,
out of scope); further pure-technical or factor-beta variants (overlap momentum/
relative-strength); seasonality/calendar effects (data-mining risk); generic
web-news scraping or LLM-generated market predictions (ethos + effort, low
verifiable orthogonality).
