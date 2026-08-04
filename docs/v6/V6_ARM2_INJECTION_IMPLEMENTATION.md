# V6 Arm 2 — Injection Implementation (Part 6)

## 1. Frozen specification

```
f_i(ρ) = f_i + κ · ρ · Φ⁻¹(rank(y_i))
ρ ∈ {0.00, 0.05, 0.10, 0.15, 0.20, 0.30},  PRIMARY ρ = 0.10
```
`i` indexes a cell = (symbol, as_of). κ = 0.129007 (panel SD of `ret_21d`).

## 2. Injection point

The hook wraps `FeatureRepository.get_instrument_series` — the single read path every model uses to obtain instrument feature values. Injection is applied **at read time**; the feature store on disk is never written.

```python
_orig = FeatureRepository.get_instrument_series
def hooked(self, feature_id, instrument_id):
    ser = _orig(self, feature_id, instrument_id)
    if feature_id != INJ["fid"] or ser.empty:
        return ser                      # untouched: every other feature
    d = INJ["delta"].get(instrument_id)
    if not d:
        return ser
    ser = ser.copy()                    # never mutate the cached series
    for dt, dv in d.items():
        ts = pd.Timestamp(dt)
        if ts in ser.index:
            ser.loc[ts] = ser.loc[ts] + dv
    return ser
FeatureRepository.get_instrument_series = hooked
```

Properties, each deliberate:

- **Feature-scoped.** Any `feature_id` other than `ret_21d` returns the original object.
- **Point-perturbation.** Only the value at the cell's `as_of` is shifted. Trailing history stays clean, so `momentum_exhaustion`'s percentile base is unperturbed and "current value vs. own history" keeps its intended meaning.
- **Non-destructive.** `ser.copy()` before mutation; the store is read-only throughout.
- **Single choke point.** Because no registered feature declares `ret_21d` in `depends_on`, this one hook captures the complete propagation surface.

## 3. Normal scores

`Φ⁻¹` uses Acklam's inverse-normal approximation (|err| < 1.15e-9), the same implementation used in Arm 1 and Arm 1.5. Ranks are computed over the pooled cell set, consistent with Arm 1.

## 4. Cell construction

- Grid: every 26th session (the 1y non-overlap stride, `ceil(252/10)`), 2012-01-03 → 2025-06-12.
- Symbols: 6 operating companies (HNST excluded — insufficient lookback).
- Requires ≥252 prior sessions and a complete forward window.
- **771 cells** across 131 dates. `f_raw` non-null: 771 / 771.

## 5. Outcome write-protection (R12)

`y` is recomputed inside the harness from `daily_prices` as forward excess return vs SPY. The harness:
- never writes to `daily_prices`, `feature_store_daily`, or any `spy_rel` column;
- opens sessions only for reads;
- confines all mutation to the in-memory `pd.Series` returned by the hook.

The frozen injection perturbs the **feature**; outcomes are never touched. R12 is satisfied by construction.

## 6. Defect found in the harness — D-04

The first measurement pass reported `IC_M = +0.2262` for three models whose output had sd = 0.0000. A constant series cannot have a defined rank IC.

Cause: ranks were computed as `argsort(argsort(x))`, which assigns **distinct** ranks 0…n−1 to a constant array instead of tied ranks. The "IC" was the correlation between *cell index* and rank(y) — a pure artifact, and identical across all three constant models, which is what exposed it.

Fixed to average-rank tie handling:

```python
def _avgrank(v):
    return pd.Series(v).rank(method="average").to_numpy(float)
```

After the fix those three models correctly report `IC_M = nan`.

**This defect is not confined to this harness.** The same `argsort(argsort(...))` ranking appears in `v6_arm1.py` (score-level injection) and Arm 1.5's `a15_run.py`. Model scores come from `score_from_z` with `Z_CLIP`, and clipping produces genuine ties at the boundary. Arm 1 and Arm 1.5 IC and LOSS estimates are therefore **suspect until re-verified**. This is logged for the Program Board; it is outside my authority to re-open those arms.
