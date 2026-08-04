# Data-Provider Requirements

Derived from what the executed experiments actually needed and actually failed on — not from vendor
reputation. Sources: [PAIRED_BASELINE_RESULTS.md](PAIRED_BASELINE_RESULTS.md),
[POWER_FEASIBILITY_REPORT.md](POWER_FEASIBILITY_REPORT.md).

---

## 1. What the experiments proved about data needs

Three findings drive every requirement below:

1. **Breadth saturates at a few hundred names.** 500 → 5,000 names improves IC precision by 7.8%.
   Requirements for "broad coverage" are therefore **much weaker** than previously assumed.
2. **Independent years are the binding constraint** — the SE floor is `σ_true/√Y`, immune to breadth.
   **Depth, not breadth, is the scarce input.**
3. **Delisted coverage affects bias, not variance.** It does not appear in any SE calculation. It
   determines whether the estimate is *centred* correctly. This makes it a **correctness** requirement,
   not a **power** requirement — a distinction prior documents blurred.

---

## 2. Requirements

### MANDATORY — the study is invalid without these

| # | Capability | Which research failure it prevents | Which experiment depends on it | Free data? | Required now? |
|---|---|---|---|---|---|
| M1 | **Delisted securities** with full price history to termination | Upward-biased outcome measurement. The withdrawn +0.17 could not be tested for survivorship *at all* | Any absolute-signal study (E-decisive) | **No** — no free source carries the delisted population | Only when the decisive study runs |
| M2 | **Terminal outcomes / delisting returns** (numeric, with documented method: acquisition cash vs −100%) | Silent dropping of losers. Phase 2A already refuses to guess (`UNRESOLVED`, never assumed −100%) — so without this the pipeline *correctly* declines to produce results | E-decisive | **No** | With M1 |
| M3 | **≥ 20 years depth** | The binding power constraint (§1.2). At Y=15 the SE floor rises 15%; Y is the only lever that moves it | E-decisive; the power floor | Partially — free data has depth **for survivors only**, which is the bias, not the fix | With M1 |
| M4 | **Corporate actions** (splits, dividends, ex-dates) with raw prices retained | Unreproducible total-return construction; adjustment policy cannot be re-derived | Every return computation | Partially (yfinance: partial, jitter-prone — see `docs/PRICES.md`) | With M1 |
| M5 | **Point-in-time identity history** (permanent non-ticker id, ticker-change dates) | Ticker reuse bleeding one company's history into another; identity keyed on the *current* symbol was an original root cause | E-decisive | **No** | With M1 |
| M6 | **Reproducible historical snapshots** (stable vintage → identical checksum) | Irreproducible studies. Phase 2A's checksum machinery is built and requires a stable vendor vintage | All | N/A (a licence/format property) | With M1 |
| M7 | **~200–500 securities** | Insufficient cross-section. **Revised sharply downward** from the prior "~500 minimum, prefer 1500" on the §1.1 saturation finding | E-decisive | Yes for count, **no** for the delisted portion | With M1 |

### STRONGLY PREFERRED — materially better, not blocking

| # | Capability | Prevents | Free? | Now? |
|---|---|---|---|---|
| S1 | **Historical index membership** (add/drop dates) | A discretionary universe rule the project would have to defend. A vendor PIT constituent list is *better* than cap-filtered construction | No | With M1 |
| S2 | **Bulk export** | Irreproducible incremental pulls; also the cheapest path to a one-time 20-year corpus | N/A | With M1 |
| S3 | **Local retention after lapse** | Losing reproducibility of published studies when a subscription ends | N/A | With M1 |
| S4 | **Historical PIT sector classification** | Sector-relative targets and the (currently impossible) sector-stability analysis | No | With M1 |
| S5 | **API access** | Only convenience — a research corpus is built once, not streamed | N/A | Later |

### OPTIONAL — do not gate any current experiment

| # | Capability | Why optional |
|---|---|---|
| O1 | **PIT fundamentals history** | `valuation` is **100% neutral, 0 directional calls** on 7,938 cells. It contributes exactly nothing. Fixing it is a *new signal*, not a repair of the current one |
| O2 | **Earnings history (PIT)** | `earnings_behavior` fires 10.3% of the time and is anti-predictive when it does (standalone acc 0.44). Low priority |
| O3 | **PIT market cap / shares** | Needed only for `min_market_cap`; `min_price` and `min_dollar_volume` come from price × volume. Not required to answer the MVI question |
| O4 | **> 500 securities** | 7.8% SE gain from 10x the data (§1.1). Poor value |
| O5 | **macOS compatibility** | **Not a scientific requirement — an operating cost.** See §4 |
| O6 | **Residual / factor returns** | Already deferred to Important tier; benchmark- and sector-relative suffice |

---

## 3. Provider evaluation template

Vendor-neutral. Score each cell from **the vendor's actual data**, not documentation. `N/A` is a
failing grade for a Mandatory row.

| # | Criterion | Test to run (evidence, not claims) | Pass threshold | Weight | Candidate A | Candidate B |
|---|---|---|---|---|---|---|
| M1 | Delisted securities present | `COUNT(DISTINCT id WHERE delist_date IS NOT NULL)` on the trial tier | ≥ 20% of all ids ever listed | **Gate** | | |
| M2 | Terminal value fill rate | `% of delisted ids with non-NULL terminal return` | **≥ 80%**, method documented | **Gate** | | |
| M3 | History depth | `MIN(price_date)` for a surviving and a delisted name | ≥ 20 yrs | **Gate** | | |
| M4 | Corporate actions | Reproduce one known split + one dividend from raw | Exact to tolerance | **Gate** | | |
| M5 | Identity history | Find one ticker-change and one ticker-reuse case; confirm dated intervals | Both resolvable without ticker collision | **Gate** | | |
| M6 | Vintage reproducibility | Pull the same window twice; compare checksums | Byte-identical | **Gate** | | |
| M7 | Breadth | `COUNT(DISTINCT id)` eligible at a past as-of date | ≥ 200 | **Gate** | | |
| S1 | PIT index membership | Retrieve constituents as of a past date | Add/drop dated | High | | |
| S2 | Bulk export | Export ≥ 1 yr × ≥ 100 names in one operation | Succeeds | High | | |
| S3 | Retention after lapse | Read the licence clause | Explicitly permitted | High | | |
| S4 | PIT sector | Find one reclassification with its date | Dated | Medium | | |
| — | **True annual cost** | Quote for the minimum bundle passing all Gates | — | Medium | | |
| — | **Total operating cost** | Cash + any VM/OS/licence + est. annual maintenance hours | — | Medium | | |
| — | Delivery friction | Time from zero to first 100 names ingested | ≤ 1 day | Medium | | |
| — | Adapter fit | Does it map onto the existing `OutcomeSource` Protocol without **structural** DTO change? | Field additions only | Medium | | |

**Decision rule:** any vendor failing one Gate is rejected regardless of the rest. Among survivors,
select on **total operating cost** (§4), not on cash price, reputation, or coverage beyond M7.

---

## 4. Is a maintained Windows VM scientifically justified?

**No. It is a vendor-specific operating cost, and it is currently premature at any price.**

Three separable points:

1. **Nothing in the requirements above is satisfiable only by one vendor.** M1–M7 are capability
   statements. A vendor requiring a Windows VM and one delivering over HTTPS score **identically** on
   every scientific row. The VM appears only in *total operating cost*.
2. **A research corpus is built once, not streamed.** M3 asks for 20 years of history; S2 asks for
   bulk export. Neither implies a maintained daily updater. If a Windows environment is needed at all,
   a **one-time** instance to produce a bulk export (≈ $5–20 of cloud time) satisfies the requirement.
   A *maintained* VM buys only ongoing updates, which no current experiment needs.
3. **It also degrades a real asset.** M6 requires reproducible snapshots. A hand-maintained VM sits
   outside the test suite and the migration chain — the one part of this platform that has consistently
   worked is its reproducibility discipline, and this is the only proposal that quietly weakens it.

**And the timing argument dominates all three:** per the power report, it is **not yet known whether
any dataset makes the absolute-signal question decisive.** Purchasing operating burden to acquire
data whose sufficiency is unmeasured is out of order regardless of vendor. Settle σ_true first (§5).

---

## 5. Are these requirements needed **now**?

**No. Not one Mandatory requirement is needed now**, and this is the report's main conclusion.

Every Mandatory row exists to serve the **decisive absolute-signal study**. That study cannot be
specified until σ_true is known, because σ_true determines whether the study is feasible at any
universe size (SE floor `σ_true/√Y`; at σ_true ≥ 0.15 the preregistered threshold is unreachable at
any breadth or price).

**σ_true needs breadth, not cleanliness** — survivorship distorts the *level* of the IC far more than
its *cross-date dispersion*. So it is measurable from a free ~500-name yfinance panel.

**Sequence:**

```
[free, ~1-2 days]  Estimate σ_true on a broad survivor panel
        │
        ├── σ_true ≥ 0.15 ──►  No affordable dataset reaches the threshold.
        │                      DO NOT PURCHASE. Requirements M1-M7 are moot.
        │
        └── σ_true ≤ 0.10 ──►  A ~200-500 name x 20y clean dataset IS decisive.
                               NOW run §3 against candidate vendors, select on
                               total operating cost, and purchase.
```

The requirements are correct and ready. They are simply not yet *due*.
