# V5 EXPERIMENT 001 — PREREGISTRATION

**Source under test: `momentum_exhaustion`**
**Frozen before any result is examined. Thresholds may not be altered after data is seen.**

> **This experiment does not test return prediction.** Any directional analysis is a protocol violation.

---

## 1 · Why this source was selected first

| Criterion | Assessment |
|---|---|
| Already implemented | ✅ 573 lines, 13 test files |
| Low reconstruction cost | ✅ **`daily_prices` only** — no macro, no fundamentals, no vendor data |
| Clear descriptive claim | ✅ an own-history percentile — a falsifiable numeric statement |
| Independently verifiable | ✅ **recomputable from raw prices, bypassing both the feature store and the model** |
| Useful to the final report | ✅ contributes to technical-state context |
| No dependence on return prediction | ✅ the claim is about present state only |
| No commercial data | ✅ free yfinance prices suffice |
| Activation | ✅ **90.3%** — ample episodes |

Selected over `interest_rate_sensitivity` (needs macro re-ingest first) and `sector_rotation` (needs the
sector map) purely on **shortest path to a first result**.

## 2 · Primary descriptive claim under test

> **For symbol S on date T, the model asserts that feature F sits at or above the p-th percentile of
> S's own stored history of F up to and including T.**

**H0 (null):** the model's percentile assertion does **not** agree with an independent recomputation
from raw prices, at a rate above chance.
**H1:** it agrees at a rate ≥ the CONTEXT threshold.

## 3 · Design

| Element | Specification |
|---|---|
| **Unit of observation** | one `(symbol, as_of, feature, threshold)` assertion |
| **Date range** | 2019-01-02 → the last complete session at run time |
| **Security coverage** | all universe symbols with ≥252 stored observations for the feature |
| **Sampling** | monthly `as_of` grid, matching the existing walk-forward cadence |
| **Minimum sample** | **≥20 distinct calendar episodes** (CONTEXT) · **≥40** (ADVISORY) |
| **Horizons** | percentile assertions are **horizon-independent**; the study is run once and the result applies to every horizon at which the source is admitted |
| **Regimes** | segmented by the existing declared classifier (SPY 200d, VIX≥20, FEDFUNDS vs −182d, CPI YoY accel) |

## 4 · Point-in-time requirements

1. The independent path may use **only** `daily_prices` rows with `price_date ≤ as_of`.
2. **Price-poisoning test is mandatory:** corrupt every row after `as_of`, recompute, require
   **byte-identical** output. **Failure is permanent disqualification, not a deduction.**
3. Percentile windows terminate at `as_of` inclusive.
4. No forward-fill across a gap.

## 5 · Independent verification method

**A separate script that shares no code with the model or the feature store.**

```
raw daily_prices (price_date <= as_of)
   -> compute the feature directly from prices
   -> compute the empirical percentile over the symbol's own history to as_of
   -> assert: is the value at/above the p-th percentile?     [INDEPENDENT ANSWER]

compare against the model's assertion for the same (symbol, as_of, feature, threshold)
```

**Forbidden in the verification path:** importing `mip.features.*`, importing `mip.models.momentum`,
reading `feature_store_daily`. Enforced by an AST check in the driver.

## 6 · Tolerance bounds

| Quantity | Tolerance | Rationale |
|---|---|---|
| Feature value | rel. 1e-6 | float reconstruction |
| Percentile rank | ±0.5 percentile points | tie-handling and plotting-position convention may differ legitimately |
| Boolean assertion | **exact** | the claim is binary; a disagreement is a disagreement |

**Agreement is scored on the boolean assertion.** Value and rank tolerances exist only to classify a
disagreement as *convention* rather than *error*, and both classes count against agreement.

## 7 · Missing-data and revision rules

| Situation | Rule |
|---|---|
| Fewer than 252 observations | assertion **not made** — excluded from the denominator, counted in coverage |
| Missing price on `as_of` | use the last session ≤ `as_of` (matches production) |
| Independent path cannot compute | **counts as a DISAGREEMENT**, never a silent skip |
| Price revised between runs | run twice on the same snapshot; a difference is a **reproducibility failure** |
| Model emits neutral | excluded from agreement, counted in activation |

## 8 · Frozen thresholds

### CONTEXT promotion (G3)
```
R7 state agreement       >= 0.80        <-- PRIMARY
R3 PIT poisoning         PASS (byte-identical)
R4 reproducibility       PASS (byte-identical across two runs)
R2 completeness          >= 0.95 on claimed cells
R1 coverage              >= 0.50 of eligible cells
episodes                 >= 20
independent path         documented and AST-verified
```

### ADVISORY promotion (G4)
```
all CONTEXT criteria, plus
episodes                 >= 40
regimes observed         >= 2 distinct
R7 agreement             >= 0.75 in EVERY observed regime (per-regime, NOT pooled)
R5 revision rate         <= 0.10
R6 stability             sign-flip rate below the random-walk null, CI excluding it
```

### Failure
```
R7 < 0.60                         -> FAIL: the source does not describe what it claims
R3 poisoning fails                -> PERMANENT DISQUALIFICATION
R4 not reproducible               -> disqualified until fixed; version reset
R5 > 0.25                         -> FAIL
episodes < 20                     -> insufficient; hold at SHADOW, recompute next quarter
```

### Automatic demotion
Quarterly, without discretion: any CONTEXT criterion fails → SHADOW · any ADVISORY criterion fails →
CONTEXT · not evaluated for 2 quarters → one tier down · regime transition → ADVISORY reverts to
CONTEXT until re-established · **any feature-definition or model-version change → full reset to
SHADOW.**

## 9 · Expected failure modes

| # | Mode | Detection |
|---|---|---|
| 1 | Percentile convention differs (Hazen vs linear) | rank within tolerance, boolean disagrees near the threshold — classifiable |
| 2 | Insufficient history for early dates | coverage below 0.50 |
| 3 | Feature-store staleness vs recomputation | systematic disagreement on recent dates |
| 4 | Look-ahead in the percentile window | **poisoning test fails → permanent disqualification** |
| 5 | Ties at the threshold boundary | concentrated disagreement at exactly p |
| 6 | Sector-FK-dependent conditions unavailable | reduced coverage, not disagreement |

## 10 · Prerequisites

1. Schema rebuilt (class A — verified).
2. Prices re-ingested (class B, ~4–6 h).
3. Feature store recomputed (class B, ~3–4 h).
4. **Backup taken immediately after** — the rebuild is itself an asset.
5. **Scratchpad drivers only. No `src/` changes, no migrations** — the V4 authorization boundary applies.

## 11 · Deliverables

`v5_exp001_agreement.csv` · `v5_exp001_poisoning.json` · `v5_exp001_reproducibility.json` ·
`v5_exp001_by_regime.csv` · `v5_exp001_coverage.json` · `V5_EXPERIMENT_001_RESULT.md`

## 12 · Declaration

```
Thresholds frozen before data examination   [ ]
Independent path shares no code with the model or feature store   [ ]
No directional analysis performed   [ ]
Prepared by ______________________   Date ____________
```

**STATUS: PREREGISTERED, NOT RUN.** Blocked on prerequisites 2–3 (data re-ingestion).
