"""Stage D: validation metrics — pure functions over merged frames.

Every function takes a frame of merged system predictions and realized
outcomes with columns:

    symbol, as_of, horizon, system, evidence_score, confidence,
    expected_excess, expected_return, trim_score, band,
    actual, spy_rel, adverse, drawdown, fwd_vol

Realized excess is measured against the SAME yardstick the prediction
used: baseline = expected_return - expected_excess (the platform-wide
convention), so realized_excess = actual - baseline. The evidence score
is read as a pseudo-probability p = score/100 of positive realized
excess for Brier/log-loss — declared, not assumed calibrated (measuring
that is the point).

Overlap honesty: metrics are reported on all scoring dates AND on
non-overlapping cohorts (stride >= horizon), with circular block
bootstrap for the Combined-vs-Baseline differences. Conventional
independent-sample intervals are deliberately not produced.
"""

import math
import random

import numpy as np
import pandas as pd

GRID_SESSIONS = 10  # spacing of the main walk-forward grid
HORIZON_SESSIONS = {"1w": 5, "2w": 10, "1m": 21, "3m": 63, "6m": 126, "1y": 252}


def prepare(systems: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    frame = systems.merge(outcomes, on=["symbol", "as_of", "horizon"], how="inner")
    frame = frame[frame["complete"]].copy()
    baseline = frame["expected_return"].astype(float) - frame["expected_excess"].astype(float)
    frame["realized_excess"] = frame["actual"].astype(float) - baseline
    frame.loc[frame["expected_excess"].isna(), "realized_excess"] = np.nan
    frame["p_up"] = frame["evidence_score"].astype(float) / 100.0
    frame["hit"] = np.where(
        frame["realized_excess"].notna(),
        (frame["evidence_score"] > 50) == (frame["realized_excess"] > 0),
        np.nan,
    )
    return frame


def cohort(frame: pd.DataFrame, horizon: str) -> pd.DataFrame:
    """Non-overlapping scoring cohort: every k-th grid date per symbol so
    consecutive forward windows do not overlap."""
    stride = max(1, math.ceil(HORIZON_SESSIONS[horizon] / GRID_SESSIONS))
    subset = frame[frame["horizon"] == horizon]
    keep = []
    for _, group in subset.groupby(["symbol", "system"], sort=True):
        ordered = group.sort_values("as_of")
        keep.append(ordered.iloc[::stride])
    return pd.concat(keep, ignore_index=True) if keep else subset.iloc[0:0]


def accuracy_and_brier(frame: pd.DataFrame) -> dict:
    scored = frame[frame["realized_excess"].notna()]
    if scored.empty:
        return {"n": 0}
    y = (scored["realized_excess"] > 0).astype(float)
    p = scored["p_up"].clip(0.01, 0.99)
    hits = scored["hit"].astype(float)
    # Spearman via ranks + Pearson (scipy-free, tie-aware)
    spearman = scored["evidence_score"].rank().corr(scored["realized_excess"].rank())
    return {
        "n": int(len(scored)),
        "direction_accuracy": float(hits.mean()),
        "brier": float(((p - y) ** 2).mean()),
        "brier_reference": float(((0.5 - y) ** 2).mean()),  # uninformed forecaster
        "log_loss": float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()),
        "rank_correlation": None if pd.isna(spearman) else float(spearman),
        "mean_realized_excess": float(scored["realized_excess"].mean()),
    }


def decile_table(frame: pd.DataFrame, buckets: int = 10) -> pd.DataFrame:
    """Outcomes by evidence-score decile (pooled). Higher deciles should
    mean better outcomes if the score ranks the future at all."""
    scored = frame[frame["realized_excess"].notna()].copy()
    if len(scored) < buckets * 2:
        return pd.DataFrame()
    scored["decile"] = pd.qcut(scored["evidence_score"].rank(method="first"), buckets, labels=False)
    rows = []
    for decile, group in scored.groupby("decile", sort=True):
        rows.append(
            {
                "decile": int(decile) + 1,
                "n": len(group),
                "mean_score": float(group["evidence_score"].mean()),
                "mean_excess": float(group["realized_excess"].mean()),
                "median_excess": float(group["realized_excess"].median()),
                "p_positive": float((group["realized_excess"] > 0).mean()),
                "p_beat_spy": (
                    float((group["spy_rel"] > 0).mean()) if group["spy_rel"].notna().any() else None
                ),
                "median_adverse": float(group["adverse"].median()),
                "downside_p10": float(group["realized_excess"].quantile(0.10)),
                "mean_fwd_vol": float(group["fwd_vol"].mean()),
            }
        )
    return pd.DataFrame(rows)


def calibration_bins(frame: pd.DataFrame, edges=(0.2, 0.4, 0.6, 0.8)) -> pd.DataFrame:
    scored = frame[frame["realized_excess"].notna()].copy()
    bounds = [0.0, *edges, 1.0001]
    rows = []
    for low, high in zip(bounds, bounds[1:], strict=False):
        bucket = scored[(scored["p_up"] >= low) & (scored["p_up"] < high)]
        rows.append(
            {
                "bucket": f"{low:.1f}-{min(high, 1.0):.1f}",
                "n": len(bucket),
                "mean_p": float(bucket["p_up"].mean()) if len(bucket) else None,
                "realized_positive": (
                    float((bucket["realized_excess"] > 0).mean()) if len(bucket) else None
                ),
            }
        )
    return pd.DataFrame(rows)


def block_bootstrap_delta(
    combined: pd.DataFrame,
    baseline: pd.DataFrame,
    metric: str = "hit",
    block: int = 4,
    draws: int = 1000,
    seed: int = 7,
) -> dict:
    """Circular block bootstrap over per-symbol cohort series of the
    PAIRED difference (combined - baseline). Serial correlation is what
    the blocks are for; nothing here assumes independent daily samples."""
    merged = combined.merge(
        baseline,
        on=["symbol", "as_of", "horizon"],
        suffixes=("_combined", "_baseline"),
    )
    merged = merged[merged[f"{metric}_combined"].notna() & merged[f"{metric}_baseline"].notna()]
    if merged.empty:
        return {"n": 0}
    series_by_symbol = [
        group.sort_values("as_of")[[f"{metric}_combined", f"{metric}_baseline"]]
        .astype(float)
        .to_numpy()
        for _, group in merged.groupby("symbol", sort=True)
    ]
    point = float(
        merged[f"{metric}_combined"].astype(float).mean()
        - merged[f"{metric}_baseline"].astype(float).mean()
    )
    rng = random.Random(seed)
    deltas = []
    for _ in range(draws):
        combined_sum = baseline_sum = count = 0.0
        for series in series_by_symbol:
            n = len(series)
            if n == 0:
                continue
            take = 0
            while take < n:
                start = rng.randrange(n)
                for offset in range(min(block, n - take)):
                    row = series[(start + offset) % n]
                    combined_sum += row[0]
                    baseline_sum += row[1]
                take += block
                count += min(block, n)
        if count:
            deltas.append((combined_sum - baseline_sum) / count)
    deltas.sort()
    return {
        "n": int(len(merged)),
        "delta": point,
        "ci_low": deltas[int(0.025 * len(deltas))],
        "ci_high": deltas[int(0.975 * len(deltas))],
        "positive_share": sum(d > 0 for d in deltas) / len(deltas),
    }


def turnover(frame: pd.DataFrame) -> dict:
    """Score stability between consecutive scoring dates, per system."""
    rows = frame.sort_values("as_of")
    changes, band_changes, reversals = [], 0, 0
    pairs = 0
    for _, group in rows.groupby(["symbol", "horizon"], sort=True):
        trim = group["trim_score"].to_numpy(dtype=float)
        bands = group["band"].to_numpy()
        deltas = np.diff(trim)
        changes.extend(np.abs(deltas))
        band_changes += int((bands[1:] != bands[:-1]).sum())
        reversals += int(((deltas[:-1] > 10) & (deltas[1:] < -10)).sum()) + int(
            ((deltas[:-1] < -10) & (deltas[1:] > 10)).sum()
        )
        pairs += len(deltas)
    if not changes:
        return {"n": 0}
    changes_array = np.array(changes)
    return {
        "n": pairs,
        "mean_abs_change": float(changes_array.mean()),
        "p95_abs_change": float(np.percentile(changes_array, 95)),
        "band_turnover": band_changes / pairs if pairs else None,
        "reversal_rate": reversals / max(1, pairs - 1),
    }


def trim_band_outcomes(frame: pd.DataFrame) -> pd.DataFrame:
    """Realized outcomes by recommendation band + false/missed trim rates."""
    scored = frame[frame["realized_excess"].notna()]
    rows = []
    for band, group in scored.groupby("band", sort=True):
        rows.append(
            {
                "band": band,
                "n": len(group),
                "mean_excess": float(group["realized_excess"].mean()),
                "median_adverse": float(group["adverse"].median()),
                "p_positive": float((group["realized_excess"] > 0).mean()),
            }
        )
    return pd.DataFrame(rows)


def false_missed_trim(frame: pd.DataFrame) -> dict:
    scored = frame[frame["realized_excess"].notna()]
    if scored.empty:
        return {}
    trims = scored[scored["trim_score"] >= 75]
    keeps = scored[scored["trim_score"] < 40]
    bottom_quartile = scored["realized_excess"].quantile(0.25)
    missed_pool = scored[scored["realized_excess"] <= bottom_quartile]
    return {
        "false_trim_rate": (float((trims["realized_excess"] > 0).mean()) if len(trims) else None),
        "n_trim_signals": int(len(trims)),
        "missed_trim_rate": (
            float((missed_pool["trim_score"] < 60).mean()) if len(missed_pool) else None
        ),
        "n_bottom_quartile": int(len(missed_pool)),
        "keep_signal_excess": float(keeps["realized_excess"].mean()) if len(keeps) else None,
    }


def confidence_split(frame: pd.DataFrame) -> dict:
    scored = frame[frame["hit"].notna()]
    if scored.empty:
        return {}
    median = scored["confidence"].median()
    high = scored[scored["confidence"] >= median]
    low = scored[scored["confidence"] < median]
    return {
        "median_confidence": float(median),
        "high_confidence_accuracy": float(high["hit"].astype(float).mean()),
        "low_confidence_accuracy": float(low["hit"].astype(float).mean()),
    }
