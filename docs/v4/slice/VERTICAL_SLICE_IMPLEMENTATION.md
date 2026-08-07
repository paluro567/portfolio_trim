# Vertical Slice — Implementation

## Holding selected: **AMZN**

| | |
|---|---|
| Rationale | Full price history (4,169 rows, 2010-01-04→2026-07-31), full feature coverage (23 features, 93,831 rows through 2026-07-31), real quantity and average cost in the user's own broker export, and the largest position in the portfolio. **Selected on data completeness, not on the recommendation it produces.** |
| Available | quantity 82, average cost $186.84 (broker export 2026-07-16); daily prices; 9 technical features; 2 market-regime features; own-history forward-return distributions |
| Unavailable | tax lots and acquisition dates; total portfolio market value (7 of 52 positions priced); fundamentals; earnings; valuation; catalysts; ADV; **listed options exposure** |
| Portfolio inputs used | `data/peter_real_opening_balances_2026-07-16.csv`, sha256 archived in every run bundle |

Nothing was invented. Quantity, average cost and position count come from the user's file; the file's own `notes` column records that acquisition dates are unavailable.

## Code added

| File | Lines | Purpose |
|---|---|---|
| `src/mip/product/contracts.py` | ~150 | Frozen value objects: `Status`, `Direction`, `Action`, `Confidence`, `Evidence`, `Constraint`, `HorizonVerdict`, `PositionState`. `Confidence.HIGH` is **deliberately absent from the enum** — prohibited by construction, not by a runtime check. |
| `src/mip/product/slice.py` | ~330 | `load_position`, `gather_evidence`, `evaluate_constraints`. Reads `daily_prices`, `feature_store_daily`, `feature_store_market_daily`. Strictly `feature_date <= as_of`. |
| `src/mip/product/decide.py` | ~130 | `directional_view`, `confidence_for`, `decide`. Directional attractiveness and portfolio action computed separately; deterministic constraints override. |
| `src/mip/product/render.py` | ~200 | Deterministic Markdown renderer, 23 sections. |
| `src/mip/cli/product.py` | ~90 | `mip product report`. Archives inputs, hashes outputs. |
| `tests/unit/test_product_slice.py` | ~230 | 25 tests. |

Modified: `src/mip/cli/main.py` (two lines registering the command group). **No migration. No new dependency. No change to any frozen or hashed artifact.**

## Pipeline as built

```
opening-balances CSV + daily_prices        -> PositionState
feature_store_daily                        -> price/technical evidence (9 items)
feature_store_market_daily                 -> market/regime evidence (2 items)
daily_prices own history, PIT              -> historical forward-return distributions (5 items)
fundamentals / earnings / valuation / catalysts -> 5 explicit UNAVAILABLE items
PositionState                              -> 4 deterministic constraints (all NOT_EVALUABLE)
evidence x horizon                         -> DirectionalView
constraints + missing-input rules          -> PortfolioAction + elimination trace
transparent caps                           -> Confidence
                                           -> Markdown report + JSON provenance bundle
```

## Design decisions worth recording

**Percentile-based directional readings.** A raw return tells you nothing without context, so each return/relative feature is placed in its own history: ≥70th percentile → POSITIVE, ≤30th → NEGATIVE, else NEUTRAL. Requires ≥252 observations or the percentile is reported unavailable. This is transparent and inspectable — no weights, no composite.

**Why every action is ABSTAIN.** Not a bug. All four deterministic constraints are `NOT_EVALUABLE` because no `PolicyArtifact` exists (module M7, phase P3, unbuilt), total portfolio market value is not computable, and tax lots are absent. Part 6's frozen rule is: *default to ABSTAIN if required portfolio information is unavailable*. HOLD would assert the position is within policy — there is no policy, so that assertion cannot be made honestly. The elimination trace states this per action, per horizon.

**Confidence is LOW everywhere, never MODERATE.** Three independent caps fire: a material portfolio input is missing, and every directional reading is EXPERIMENTAL. `HIGH` does not exist in the enum.

**Options exposure is flagged MATERIAL.** `data/unsupported_positions_2026-07-16.csv` records an AMZN call excluded from the schema. The report says so in the risk table rather than silently understating exposure.
