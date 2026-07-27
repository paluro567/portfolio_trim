# Evaluation Foundation — Design to Make Trim-Score Research Trustworthy

Infrastructure design. No models, no tuning, no new signals. The goal is not better metrics — it is
**trustworthy** metrics: an evaluation system that can *separate* genuine stock selection from
systematic exposure, survivorship, era/symbol concentration, and noise.

## 1. Executive recommendation

**Build one thing next: a survivorship-clean, point-in-time, broad equity universe (~500 liquid names,
~15 years, delisted names included) and its price/outcome history — then re-run the *unchanged*
production score on it.**

Why it is the binding constraint: the prior study proved the 1-year "edge" was an artifact of 31
survivors × 4 independent years × 3 dominant symbols. The *statistical* apparatus to detect/reject a
real effect **already exists** in this platform (block bootstrap, effective-sample/overlap correction,
purged-embargo eligibility, pre-registration + kill criteria, the experiments registry/manifest,
within-date IC + decomposition — all built in prior phases and validated). What does **not** exist is a
universe with the *breadth and integrity* those tools require. Feeding a great framework a biased,
tiny universe is exactly how we produced a false positive.

**Explicitly do NOT build yet:** any new signal (PEAD, revisions, valuation, options, news), any weight
change, any model retirement. There is nothing to improve until we can measure whether it improved.

**What becomes possible afterward:** the single valid question — *does the current score show any
genuine cross-sectional selection value in a broad, unbiased universe?* — becomes answerable, and every
future candidate can finally be judged against a trustworthy baseline with adequate power.

## 2. Current evaluation audit

| Component | Current state | Bias risk | Severity | Required correction |
|---|---|---|---|---|
| Universe selection | `universe.yaml` = today's holdings + ETFs (~78) | Selection/survivorship | **Critical** | PIT rule-based universe |
| Point-in-time membership | none — current set projected back | Survivorship + look-ahead | **Critical** | PIT membership table |
| Delisted / bankrupt / acquired | **absent** (never ingested) | Survivorship | **Critical** | ingest delisted names + delisting returns |
| Delisting returns | not handled (yfinance drops delisted) | Downward-truncation of losers | **Critical** | source that carries delisting return |
| Symbol/identifier history | `symbol_history` table exists (unused at scale) | Identity drift | Med | populate from PIT source |
| Sector classification | static (today's sector for all history) | Style mislabeled as selection | High | PIT classification |
| Corporate actions | splits/dividends captured | mostly OK | Low | validate on broad universe |
| Prices | yfinance total-return adj_close + raw | survivor-only | High | broad survivorship-clean source |
| Fundamentals / earnings | dated snapshots, PIT-honest but **sparse** (~1 snapshot) | valuation inert | Med (not blocking now) | accrue forward / paid vintages later |
| Features | PIT by construction | OK | Low | recompute on new universe |
| Macro | FRED with publication lags | OK | Low | — |
| Scoring vs forward window | monthly, **overlapping 1y windows** | pseudo-replication | High | horizon-specific non-overlap / block-aware CI (framework exists) |
| Observation count vs independent N | 43 dates read as if independent (≈4 real) | over-confidence | **Critical** | effective-N everywhere (framework exists) |
| Research/validation/holdout split | design/holdout split exists; no locked holdout ledger | multiple-testing/contamination | Med | holdout access policy + hypothesis ledger |

**One-line summary:** the *statistics* are sound; the *universe and its survivorship integrity* are not.

## 3. Recommended universe design — tiered (Option D)

| Tier | Purpose | Construction | ~Breadth | Survivorship | Recommendation |
|---|---|---|---|---|---|
| **Validation** | promotion decisions | PIT liquid large/mid-cap (rule-based) | **~500** | clean (incl. delisted) | **BUILD FIRST** |
| Discovery | hypothesis generation | broad PIT US common shares | ~2,000+ | clean | Later |
| Portfolio-relevance | relevance weighting | current + recent holdings | ~80 | n/a | keep |
| Reporting | the actual product | current holdings | ~50 | n/a | unchanged (production) |

Chosen for the first study: the **Validation tier — ~500 survivorship-clean liquid names over ~15
years.** Not the biggest possible universe — the *smallest that meets integrity + power* (§5). Broad
microcap discovery is deferred (noise, data cost) until the validation tier proves the concept.

## 4. Data coverage plan

| Data domain | Current | Required | PIT? | Source options | Cost | Blocking? |
|---|---|---|---|---|---|---|
| Historical security master | partial (instruments) | full incl. delisted | needs PIT | Norgate / Sharadar / CRSP | $–$$$ | **Yes** |
| PIT identifier/ticker history | table exists, unfilled | full | yes | same | — | **Yes** |
| Delisted securities + **delisting returns** | **none** | full | yes | Norgate / Sharadar / CRSP | $–$$$ | **Yes (the core gap)** |
| PIT index/universe membership | none | validation-tier rules | yes | Norgate (PIT constituents) / rule-based | $ | **Yes** |
| Historical market cap (for liquidity/size) | none | full | yes | Sharadar / CRSP | $ | High |
| PIT sector/industry | static | PIT | yes | Sharadar / GICS history | $ | High (Should) |
| Corporate actions | splits/divs | validate broad | yes | source-provided | — | Low |
| Adjusted + unadjusted prices | yes (survivors) | broad + delisted | yes | Norgate / Sharadar | $ | **Yes** |
| Volume/liquidity | yes (survivors) | broad | yes | same | — | Med |
| Benchmark + sector-benchmark returns | SPY + sector ETFs | keep | yes | have | — | No |
| Risk-free rate | FRED | keep | yes | have | — | No |
| Factor-exposure inputs (size/mom/value) | partial (price-derived) | for residualization | yes | derivable + fundamentals | $ | Later |
| PIT fundamentals/earnings | sparse | multi-year | yes | Sharadar (PIT) | $ | Later |

**Source honesty (per the standard — evaluate whether it *solves* survivorship, not convenience):**
- **Already-available / free (yfinance, stooq):** do **NOT** solve survivorship — they carry survivors
  only and drop delisted names. Unusable for the core gap.
- **Paid-but-realistic:** **Norgate Data** (retail-affordable US equities, survivorship-free, delisted +
  delisting handling, PIT index constituents) and **Sharadar / Nasdaq Data Link** (survivorship-free
  prices + PIT fundamentals, affordable) — either **solves the blocking gap.**
- **Paid-and-expensive / gold standard:** **CRSP** (survivorship-free, delisting returns, the academic
  reference) — best integrity, higher cost / WRDS access.
- **Unavailable/impractical:** assembling survivorship-clean history from free scraping — do not attempt;
  it reintroduces the exact bias we are removing.

**Blocking gap = a survivorship-clean price+delisting+membership feed. It requires a (modest) paid
source. Free data cannot close it — that is the honest conclusion.**

## 5. Statistical power plan

Cross-sectional IC sampling error ≈ `1/√(N−3)` per date; over `T_eff` *independent* periods,
`SE(mean IC) ≈ 1/√((N−3)·T_eff)`. Overlapping monthly 1-year windows collapse to `T_eff ≈ #years`.
Detectable IC (95%) ≈ `1.96·SE`.

| Universe | History | Freq | Effective N (names × indep. years) | ~SE(mean IC) | ~Detectable IC | Reliability |
|---:|---:|---:|---:|---:|---:|---|
| 50 | 5y | monthly | ~250 | 0.065 | ~0.13 | **≈ today — useless** |
| 200 | 10y | monthly | ~2,000 | 0.022 | ~0.044 | borderline |
| **500** | **15y** | monthly | ~7,500 | 0.012 | **~0.023** | **adequate** |
| 1,000 | 20y | monthly | ~20,000 | 0.007 | ~0.014 | excellent |

- **Target effect size:** realistic equity cross-sectional IC is **~0.02–0.05**. To *reject or detect*
  it with a CI excluding zero we need `SE ≤ ~0.015–0.02` → **~300–500 names × ~12–15 years.**
- **Caveats (make the table optimistic):** stocks co-move (cross-sectional correlation reduces effective
  N below name count) and cluster by sector — so the *practical* target is the upper end (**~500 × 15y**),
  and the final number should come from a **block-and-cross-correlation-aware simulation**, not this
  closed form. Directional-accuracy detection is even weaker (a 2–3pp edge needs tens of thousands of
  independent obs) — reinforcing that **IC, not accuracy, is the primary metric.**

## 6. Validation architecture (horizon-specific)

| Horizon | Scoring freq | Overlap handling | Embargo/purge | Primary metric | Min effective N |
|---|---|---|---|---|---|
| 1w | weekly/monthly | low | 1w embargo, purge overlap | within-date IC (residual) | high (many dates) |
| 1m | monthly | moderate | 1m embargo + purge | within-date IC | adequate |
| 3m | monthly (report) / **quarterly non-overlap (primary)** | block-aware | 3m purge | within-date IC | quarterly blocks |
| 6m | semiannual non-overlap | block-aware | 6m purge | within-date IC | few blocks |
| 1y | **annual non-overlap (primary)** + monthly (diagnostic, block-CI) | **year-block bootstrap** | 1y purge | within-date IC on residual returns | #years |

- **Walk-forward:** expanding-window, **purged and embargoed** (López de Prado) so no training/scoring
  cell shares its forward window with a test cell.
- **Uncertainty:** always block-aware (by scoring date/year) + two-way (date × symbol) resampling; never
  naive independent-sample CIs. *(All implemented already in `mip/validation` + the experiments harness.)*
- **Holdout policy (§7):** research / validation / **locked holdout** are date-partitioned; the locked
  holdout is accessed rarely, logged, and never iterated on.

## 7. Research / validation / holdout separation & multiple-testing control

- **Research** (earliest ~60% of history): hypothesis generation, exploration — no promotion claims.
- **Validation** (next ~25%): pre-registered shadow experiments, candidate comparison, promotion
  decisions. *(The experiments registry + frozen pre-registration + kill criteria already enforce this.)*
- **Locked holdout** (final ~15%, most recent): final confirmation only; **access-logged**, budget of
  N lifetime touches, never used to iterate. Turning it into a training set is prevented by (a) a
  logged access ledger and (b) a rule that a failed holdout test *retires the hypothesis family*, not
  the holdout.
- **Multiple-testing:** a **hypothesis ledger** records every signal/horizon/universe/sector/parameter
  test; promotion applies **FDR (Benjamini-Hochberg)** across the family, a **permutation/reality-check**
  benchmark, a **minimum effect-size floor**, and a **research-budget** count carried on each candidate
  ("N related hypotheses tested before this one"). Deflate metrics for the number of trials.

## 8. Conceptual research data model (what exists vs new)

Reproducibility requirement: any historical experiment is rerunnable and yields identical results from
the same **data version**.

**Already present (reuse):** `instruments`, `symbol_history`, `corporate_actions`, `daily_prices`
(adj+raw), `feature_store*`, `company_fundamentals`, `earnings_observations`, the prediction archive,
and the experiments **registry / reproducibility manifest / pre-registration**.

**New entities required:**

| Entity | Purpose | Natural key | Key fields | PIT requirement | Data-quality check |
|---|---|---|---|---|---|
| security_master | one row per real security incl. dead | permanent id | first/last date, status, share class | identity stable across ticker changes | no two live tickers share id-date |
| universe_membership | PIT tier membership | (id, date, tier) | in/out, eligibility reason | selection uses only ≤date info | no future-dated entries |
| delisting_event | end-of-life + **delisting return** | (id, delist_date) | reason, final/delisting return | return known at event | every dead id has one |
| pit_classification | PIT sector/industry | (id, valid_from) | GICS, valid_to | as-known-then | contiguous, no gaps |
| exposure_snapshot | PIT beta/size/factor loadings | (id, date, factor) | value, lookback | estimated pre-date | betas within bounds |
| hypothesis | registered research question | hypothesis_id | statement, family, budget-before | frozen pre-results | linked pre-registration |
| experiment_run | one execution | run_id | data_version, seed, universe tier | manifest-pinned | reproducible digest |
| metric_result | computed metric + block-CI | (run_id, metric, horizon) | value, ci, effective_n, method | — | effective_n ≤ raw_n |
| holdout_access_log | locked-holdout touches | (hypothesis_id, ts) | outcome | append-only | budget not exceeded |
| promotion_decision | recorded go/no-go | decision_id | verdict, evidence, reviewer | immutable | one per candidate |

*(`data_version` on `experiment_run` is the reproducibility spine — it pins the universe snapshot,
price/delisting vintage, feature versions, and code commit.)*

## 9. Minimum viable foundation

**Must have** (without it, conclusions stay unreliable):
1. Survivorship-clean **security master + delisting events + delisting returns** for the ~500-name
   validation tier. *(complexity: high — the paid-data lift)*
2. **PIT universe-membership** for that tier (rule-based, ≤-date only). *(medium)*
3. **Broad price + forward-outcome history** incl. delisted names, survivorship-aware returns. *(medium)*
4. Re-run the **unchanged** production models over that universe + **block-aware within-date IC**
   evaluation. *(low — the models are price-driven and the eval framework exists)*

**Should have:** PIT sector classification (allocation-vs-selection); exposure snapshots (beta/size for
residual targets); the hypothesis ledger + holdout access log.

**Later:** broad microcap discovery tier; PIT fundamentals vintages; a real multi-factor model; PEAD/
revisions/positioning research.

## 10. Phased build roadmap

- **Phase 0 — Freeze conclusions.** Record: production Trim Score has *no demonstrated stock-selection
  edge*; all model revisions blocked. *(done — this and the prior study docs.)*
- **Phase 1 — Security master & universe integrity.** PIT membership, identifier history, delistings,
  corporate-action validation for the validation tier. *Deliverable:* survivorship-clean universe table.
  *Acceptance:* zero future-dated membership; every dead id has a delisting event+return; spot-checks vs
  known delistings pass. *Unlocks:* an unbiased cross-section. *Fails if:* delisted coverage is partial.
- **Phase 2 — Broad price & outcome history.** Survivorship-aware returns + forward outcomes incl.
  delisting returns. *Acceptance:* losers are present and correctly truncated; no silent deletion of
  cells with missing future prices (they are handled, not dropped as survivors). *Unlocks:* honest
  forward returns.
- **Phase 3 — Power & sampling framework.** Wire horizon-specific non-overlap + purge/embargo +
  block/two-way resampling + effective-N + MDE reporting. *(Mostly reuse `mip/validation` + harness.)*
  *Acceptance:* effective-N and block-CI reported on every metric; simulation-based power matches §5.
- **Phase 4 — Re-run the production score on the rebuilt foundation.** The decisive test. *Acceptance:*
  within-date residual IC with block-CI, dominant-symbol/period exclusions, and leave-one-year-out, on
  ~500 clean names × 15y. *Unlocks:* the answer to "does the current score have any genuine edge?"
- **Phase 5 — Resume candidate research.** Only after Phase 4 yields a trustworthy baseline **and** the
  resumption gate passes.

## 11. Research-resumption gate (go / no-go)

Model research stays blocked until **every mandatory** box is checked:

- [ ] PIT universe exists (selection uses only ≤-date information).
- [ ] Delisted/bankrupt/acquired securities represented, with delisting returns.
- [ ] Corporate actions validated on the broad universe.
- [ ] No future information enters universe selection (audited).
- [ ] Effective sample size meets threshold (detectable IC ≤ ~0.03; ≥ ~300 names × ≥ ~10 independent
      periods).
- [ ] Multiple market regimes represented (≥ 2–3 bull/bear/rate cycles).
- [ ] No single symbol drives the aggregate (dominant-symbol exclusion stable).
- [ ] No single year drives the aggregate (leave-one-year-out stable).
- [ ] Walk-forward procedure frozen (purged/embargoed, horizon-specific).
- [ ] Primary metric frozen (within-date residual IC) with block-aware CIs.
- [ ] Holdout access policy frozen (logged, budgeted, non-iterative).

**Until all mandatory conditions pass, no new predictive signal, weight change, or model retirement is
permitted.** The platform's next advantage is not a factor — it is the ability to reject false
discoveries and measure small genuine effects honestly.
