# EXISTING EVIDENCE SOURCE INVENTORY

Nine sources in `ALL_MODELS`. **No new source is created.** Facts from direct code inspection and
prior measured results.

---

## Summary

| Source | Lines | Test files | Status | Activation (measured) | V5 candidate |
|---|---|---|---|---|---|
| `momentum_exhaustion` | 573 | 13 | OFFICIAL | 90.3% | ✅ **YES — selected #1** |
| `relative_strength` | 580 | 14 | OFFICIAL | 82.8% | ✅ YES |
| `sector_rotation` | 512 | 31 | OFFICIAL | 98.7% | ✅ YES |
| `interest_rate_sensitivity` | 305 | 16 | OFFICIAL | 98.6% | ✅ YES |
| `macro_regime` | 657 | 22 | OFFICIAL | 97.5% | ✅ YES |
| `earnings_behavior` | 558 | 19 | OFFICIAL | **10.3%** | ⚠️ marginal — sparse |
| `valuation` | 580 | 21 | OFFICIAL | **0.0%** | ❌ **NO — nothing to verify** |
| `historical_analogues` | 196 | 9 | SHADOW | 94.0% | ❌ NO — rejected for leakage |
| `conditional_probability` | 196 | 12 | SHADOW | 48% | ❌ NO — rejected |

## Per-source detail

### `momentum_exhaustion` — **V5 candidate #1**
- **Claimed meaning:** where the stock's own momentum, trend, volatility and extension sit **relative to
  its own history**, expressed as own-percentile deciles.
- **Raw inputs:** `daily_prices` only. No macro, no fundamentals, no vendor data.
- **Transformation:** price → return/momentum/volatility features → percentile vs the stock's own
  stored history at/before `as_of` (≥252 obs required) → threshold conditions.
- **Descriptive claim:** *"feature X for this symbol is at/above its own p-th percentile as of date T."*
- **Directional claim:** continuation vs exhaustion — **out of scope for V5.**
- **Independent verification path:** ✅ **YES, strong.** Recompute the percentile directly from
  `daily_prices` in a separate script, bypassing the feature store entirely.
- **PIT status:** percentile formed at `as_of` from history to date. Documented limitation: early-history
  events are classified by the distribution known at `as_of`.
- **Known failures:** part of the redundant price cluster (realised z-corr **+0.513** with
  `relative_strength`). LOO removal −0.0119, CI includes 0.
- **Missing validation:** **no descriptive reliability has ever been measured.**

### `relative_strength` — candidate #2
Relative return percentiles vs sector ETF and market. Inputs: `daily_prices` + sector map.
**Independent path:** ✅ recompute relative returns from raw prices.
Known: most redundant model (0.37 with momentum on scores, +0.513 on z); E6 contrarian-mistimed −0.287;
retire-decision undecided across three attempts.

### `sector_rotation` — candidate #3
Sector-relative price behaviour. Inputs: `daily_prices` + sector classification.
**Independent path:** ✅ recompute from raw prices + the static sector map.
Known: **top-weighted in 55.9% of cells purely because it reports the smallest effects** (the
`se ≡ |effect/z|` artifact); LOO removal harmless.

### `interest_rate_sensitivity` — candidate #4
Rate/curve regime state from FRED. Inputs: `macro_observations` (publication-lagged).
**Independent path:** ✅ recompute from raw FRED series.
Known: **the only model whose LOO removal degrades accuracy with a CI excluding zero (−0.0381,
[−0.0678, −0.0070])** — flagged provisional, 1 of 7 tests without multiplicity correction.
**Requires macro re-ingestion first** (class B).

### `macro_regime` — candidate #5
Market-scope macro conditions over 18 FRED series, 16 y, publication-lagged.
**Independent path:** ✅ but more complex — 18 series, YoY/change transforms.
Known: **worst solo performer** (dir-acc 0.4758, Brier 0.3389); genuinely uncorrelated with the price
cluster (z-corr −0.003 to −0.130). Requires macro re-ingestion.

### `earnings_behavior` — marginal
Post-report window anchor, ≤14 days since earnings. **10.3% activation.**
**Independent path:** ✅ possible from `earnings_observations`, but sparse.
Known: anti-drift; standalone dir-acc 0.44; rank-corr worsens with horizon.
**Not selected:** activation too low for a ≥20-episode floor without a long window.

### `valuation` — **excluded**
**0.000 activation over 7,938 cells. LOO Δ exactly 0.0000 with a zero-width CI.**
Cause: one PIT fundamentals snapshot, now permanently lost.
**Cannot earn descriptive reliability: it emits no claim to verify.**

### `historical_analogues`, `conditional_probability` — **excluded**
SHADOW. Analogues: long-horizon performance was **100% leakage** (1y 64.3% → 30.8% after embargo).
CPE: edge was era persistence; confidence inverted; accuracy *decreased* as conditioning was added.
**Both are excluded from V5 candidacy — re-admitting a rejected source would require a separate
decision outside Stage 0's authority.**

## Independent verification path availability

| Source | Path | Bypasses feature store? | Bypasses model code? |
|---|---|---|---|
| momentum_exhaustion | raw `daily_prices` → percentile | ✅ | ✅ |
| relative_strength | raw prices + benchmark | ✅ | ✅ |
| sector_rotation | raw prices + sector map | ✅ | ✅ |
| interest_rate_sensitivity | raw FRED series | ✅ | ✅ |
| macro_regime | raw FRED × 18 | ✅ | ✅ |
| earnings_behavior | raw earnings observations | ✅ | ✅ |
| **valuation** | **none — no claim emitted** | — | — |

> **Every selected candidate has a verification path that bypasses both the feature store and the model
> code.** A source verifiable only through its own pipeline would be checking itself, which
> `V5_DESCRIPTIVE_RELIABILITY_PLAN.md` §1 forbids.
