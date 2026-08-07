# Vertical Slice — Capability Gap Analysis

Inspected the repository as it exists, not the planning documents.

| Capability | Status | Location | Tests | Reusable now | Deterministic | Evidence status |
|---|---|---|---|---|---|---|
| Holdings input | **WORKING** | `data/peter_real_opening_balances_2026-07-16.csv` (52 real positions, qty + avg cost) | — | **yes** | yes | fact |
| Price history | **WORKING** | `daily_prices` — 38,086 rows, 10 symbols, 2010-01-04→2026-07-31 | `tests/unit/test_*ingest*` | **yes** | yes | fact |
| Feature store | **WORKING** | `feature_store_daily` 855,418 rows / 23 live features; `feature_store_market_daily` | existing | **yes** | yes | DESCRIPTIVE |
| Trading calendar | **WORKING** | `trading_calendar`, 4,419 sessions | existing | yes | yes | fact |
| Cost basis | **PARTIAL** | avg cost only in broker export | — | yes | yes | fact |
| Tax lots | **MISSING** | `lots` table exists, **0 rows**; export has no acquisition dates | `test_portfolio_lots.py` | no | — | UNAVAILABLE |
| Portfolio weights | **PARTIAL** | cost-basis weight computable for all 52; market-value weight needs prices for all 52 (only 7 have them) | — | partial | yes | DESCRIPTIVE / UNAVAILABLE |
| Concentration | **PARTIAL** | `portfolio/analytics.py` exists but needs a populated portfolio | `test_portfolio_analytics.py` | no | yes | NOT_EVALUABLE |
| Liquidity | **MISSING** | no ADV wired | — | no | — | UNAVAILABLE |
| Correlations | **PARTIAL** | `portfolio/analytics.py` | yes | no (needs populated portfolio) | yes | — |
| Market regime | **WORKING** | `regime_bull`, `vix_pctile_252d` in `feature_store_market_daily` | existing | **yes** | yes | DESCRIPTIVE |
| Company fundamentals | **MISSING** | no PIT fundamentals; 3 of 7 models emit constant output | — | no | — | UNAVAILABLE |
| Earnings | **MISSING** | `earnings_events` table absent from this database | — | no | — | UNAVAILABLE |
| Valuation | **MISSING** | depends on fundamentals | — | no | — | UNAVAILABLE |
| Catalysts | **MISSING** | no PIT-verified catalyst source wired | — | no | — | UNAVAILABLE |
| Technical indicators | **WORKING** | 9 features used: `ret_21/63/126/252d`, `vol_21d`, `dist_52w_high`, `price_to_ma50/200`, `rel_ret_spy_63d` | existing | **yes** | yes | DESCRIPTIVE |
| Historical outcomes | **WORKING** | computed from `daily_prices` own history, strictly PIT | new | **yes** | yes | DESCRIPTIVE |
| Analogue matching | **BROKEN for product use** | `research/analogues.py` — SHADOW model, excluded from the decision path; Arm 2 could not validate its consumer structure | existing | **no** | yes | UNAVAILABLE |
| Evidence generation | **PARTIAL** | `engine/evidence.py` patched (A-2026-006) but emits the retired directional ensemble | 17 regression tests | **no** — excluded by the product evidence boundary | yes | excluded |
| Recommendation generation | **BROKEN for product use** | `engine/trim.py` emits directional labels + 0–100 scores — prohibited | existing | **no** | yes | excluded |
| Report generation | **PARTIAL** | `engine/report.py` renders trim assessments — prohibited content | existing | **no** | yes | excluded |
| CLI | **WORKING** | 20 command groups; Typer; `cli/_deps.py` session factory | existing | **yes** | yes | — |
| Export / archival | **PARTIAL** | `data/reports/` pattern exists | — | pattern reused | yes | — |

## What this forced

The existing recommendation and report path (`trim` → `report`) is unusable: it emits 0–100 predictive scores and directional labels that the frozen product evidence boundary prohibits. The slice therefore **reuses the data layer aggressively** (prices, features, calendar, CLI, session factory) and **adds a thin new decision+render layer** rather than rebuilding anything.

Net new code: 4 modules, ~700 lines. Zero migrations. Zero new models. Zero new dependencies.
