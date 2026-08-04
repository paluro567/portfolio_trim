# V6 Arm 2 — Feature Selection (R4)

The frozen Part 2.1 rule was executed **verbatim and mechanically**. No outcome data was consulted at any step.

## 1. The rule as frozen

1. Restrict to **price-derived** features.
2. Select the highest **consumer count**, by static analysis of `src/mip/models/*.py`.
3. Ties → highest non-null coverage.
4. Ties → lexicographic name.

## 2. Execution trace

- Step 1 → 29 price-derived; 27 injectable (2 market-scope excluded structurally, §Audit 2).
- Step 2 → 19 have ≥1 consumer. **Maximum consumer count = 6, attained by exactly one feature.**
- Steps 3 and 4 **never fired** — there was no tie.

| Feature | Consumers | Consuming models |
|---|---|---|
| **`ret_21d`** | **6** | earnings, macro, momentum, relative, sector, valuation |
| `rel_ret_spy_63d` | 3 | earnings, momentum, relative |
| `ret_63d` | 3 | earnings, momentum, valuation |
| `dist_52w_high` | 2 | earnings, momentum |
| `vol_21d` | 2 | earnings, momentum |
| `rel_ret_sector_63d` | 2 | momentum, relative *(zero coverage)* |

## 3. Selected feature

**`ret_21d`** — 21-session total return on adjusted close.
`id=3`, scope instrument, `uses_adjusted_prices=true`, coverage **1.000000**, 37,876 non-null values, 10 instruments, 2010-02-03 → 2026-07-31.

Selection scale constant: **κ = 0.129007** (panel standard deviation of `ret_21d`).

## 4. Robustness of the selection

The static scan covers only `src/mip/models/*.py`, but models delegate to `src/mip/research/*.py`. Recounting transitively adds `historical_analogues` (which lists `ret_21d` in both `SECTOR_ETF_FEATURES` and `COMPANY_FEATURES`, `src/mip/research/analogues.py:78,82`) — but `historical_analogues` is in `SHADOW_MODELS` and is excluded from the scored ensemble, so it cannot enter the endpoint. Under either scan, **`ret_21d` still wins outright.** The selected feature is robust; the *sets built from it* are not.

## 5. B-01 — the rule measures the wrong quantity

The rule's consumer metric is *"the feature name appears in the model's source."* That is not value consumption. Inspecting all six counted consumers:

| Model | How it references `ret_21d` | Reads the **value**? |
|---|---|---|
| `momentum_exhaustion` | `ge("ret_21d", 0.7)`, `le("ret_21d", 0.2)`, … — percentile thresholds | **YES** |
| `valuation` | `_latest_feature_date()` → `series.index[-1]` | no — reads a **date** |
| `relative_strength` | `_latest_feature_date()` → `series.index[-1]` | no — reads a **date** |
| `earnings_behavior` | `_latest_feature_date()` → `series.index[-1]` | no — reads a **date** |
| `sector_rotation` | `_latest_feature_date()` → `series.index[-1]` | no — reads a **date** |
| `macro_regime` | `_latest_feature_date()` → `series.index[-1]` | no — reads a **date** |

Five of the six use `ret_21d` inside a **byte-identical copy-pasted helper**:

```python
def _latest_feature_date(self, symbol: str) -> date | None:
    definition = self._features.get_definition("ret_21d")
    if definition is None:
        return None
    series = self._features.get_instrument_series(definition.id, self._instrument_id(symbol))
    return series.index[-1].date() if not series.empty else None
```

`ret_21d` is the platform's **data-availability clock**. It scores 6 precisely because it is the conventional feature to ask "when was this instrument last updated" — an artifact of code duplication, not of model importance.

**The rule ranked boilerplate.** The true runtime value-consumer set among the 7 official models is `{momentum_exhaustion}` — n=1. This was confirmed empirically, not just by reading code: see `V6_ARM2_PROPAGATION_CHECKPOINT_VALIDATION.md`.

I did **not** change the rule. It was executed as frozen, and the defect is reported for the Preregistration Committee to rule on.
