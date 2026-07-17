"""Evaluation analytics: calibration, model, horizon, and trim-bucket
measurement over archived predictions and their realized outcomes.

All functions are pure over plain row dicts (the contract below), so
every number is reproducible from the archive by hand. Predictions
without combinable evidence (expected excess None) are archived facts
but are excluded from error and direction statistics — missing evidence
is never scored as a right or wrong forecast.

Row contract (produced by `evaluated_row`):
    symbol, horizon, as_of, trim_score, confidence,
    expected_excess_return, recommendation_label, data_quality_label,
    model_contributions (list of dicts), actual_return,
    actual_excess_return, prediction_error, absolute_error,
    direction_correct (bool | None)
"""

import math
from typing import Any

from mip.engine.trim import HORIZON_SESSIONS

HORIZON_ORDER = tuple(HORIZON_SESSIONS)
CONFIDENCE_EDGES = (0.2, 0.4, 0.6, 0.8)
TRIM_EDGES = (20.0, 40.0, 60.0, 80.0)


def evaluated_row(prediction, outcome, symbol: str) -> dict[str, Any]:
    """ORM pair -> the plain analytics row (values verbatim)."""
    return {
        "symbol": symbol,
        "horizon": prediction.horizon,
        "as_of": prediction.as_of,
        "trim_score": prediction.trim_score,
        "confidence": prediction.confidence,
        "expected_excess_return": prediction.expected_excess_return,
        "recommendation_label": prediction.recommendation_label,
        "data_quality_label": prediction.data_quality_label,
        "model_contributions": prediction.model_contributions or [],
        "actual_return": outcome.actual_return,
        "actual_excess_return": outcome.actual_excess_return,
        "prediction_error": outcome.prediction_error,
        "absolute_error": outcome.absolute_error,
        "direction_correct": outcome.direction_correct,
    }


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _share(flags: list[bool]) -> float | None:
    return sum(flags) / len(flags) if flags else None


def _sign(value: float) -> int:
    return (value > 0) - (value < 0)


def _ranks(values: list[float]) -> list[float]:
    """1-based ranks with ties sharing their average rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman rank correlation = Pearson correlation of the ranks."""
    rx, ry = _ranks(xs), _ranks(ys)
    n = len(rx)
    mean_x, mean_y = sum(rx) / n, sum(ry) / n
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(rx, ry, strict=True))
    var_x = sum((x - mean_x) ** 2 for x in rx)
    var_y = sum((y - mean_y) ** 2 for y in ry)
    if var_x == 0 or var_y == 0:
        return None
    return covariance / math.sqrt(var_x * var_y)


# -- calibration -------------------------------------------------------------------


def calibration_table(rows: list[dict], edges: tuple[float, ...] = CONFIDENCE_EDGES) -> list[dict]:
    """Empirical confidence -> directional accuracy mapping. Confidence is
    evidence volume x agreement (not a stated win probability); this table
    MEASURES what accuracy each confidence level actually delivered."""
    bounds = [0.0, *edges, 1.0000001]
    table = []
    for low, high in zip(bounds, bounds[1:], strict=False):
        scored = [
            r for r in rows if r["direction_correct"] is not None and low <= r["confidence"] < high
        ]
        table.append(
            {
                "bucket": f"{low:.2f}-{min(high, 1.0):.2f}",
                "n": len(scored),
                "mean_confidence": _mean([r["confidence"] for r in scored]),
                "direction_accuracy": _share([r["direction_correct"] for r in scored]),
                "mean_absolute_error": _mean(
                    [r["absolute_error"] for r in scored if r["absolute_error"] is not None]
                ),
            }
        )
    return table


# -- per-model analytics -----------------------------------------------------------


def model_analytics(rows: list[dict]) -> list[dict]:
    """Measurement only: each model's archived per-prediction effect vs the
    realized excess. Information gain is versus the naive zero-excess
    baseline forecast: naive_mae - model_mae (positive = the model's
    numbers reduced forecast error)."""
    per_model: dict[str, dict[str, list]] = {}
    for row in rows:
        actual = row["actual_excess_return"]
        combined = row["expected_excess_return"]
        for c in row["model_contributions"]:
            bucket = per_model.setdefault(
                c["model"],
                {
                    "weight": [],
                    "abs_contribution": [],
                    "agree": [],
                    "hit": [],
                    "err": [],
                    "naive": [],
                    "effect": [],
                },
            )
            effect = c["effect"]
            bucket["weight"].append(c["weight_share"])
            bucket["abs_contribution"].append(abs(c["signed_contribution"]))
            bucket["effect"].append(effect)
            if combined not in (None, 0.0) and effect != 0.0:
                bucket["agree"].append(_sign(effect) == _sign(combined))
            if actual is not None and effect != 0.0:
                bucket["hit"].append(_sign(effect) == _sign(actual))
                bucket["err"].append(abs(actual - effect))
                bucket["naive"].append(abs(actual))
    table = []
    for model in sorted(per_model):
        b = per_model[model]
        accuracy = _share(b["hit"])
        mae = _mean(b["err"])
        naive = _mean(b["naive"])
        agreement = _share(b["agree"])
        table.append(
            {
                "model": model,
                "n": len(b["effect"]),
                "avg_weight_share": _mean(b["weight"]),
                "avg_abs_contribution": _mean(b["abs_contribution"]),
                "avg_effect": _mean(b["effect"]),
                "agreement_rate": agreement,
                "contradiction_rate": (1.0 - agreement if agreement is not None else None),
                "directional_accuracy": accuracy,
                "directional_edge": (accuracy - 0.5 if accuracy is not None else None),
                "mae": mae,
                "naive_mae": naive,
                "information_gain": (naive - mae if None not in (naive, mae) else None),
            }
        )
    return table


# -- per-horizon analytics ---------------------------------------------------------


def _sharpe(rows: list[dict]) -> float | None:
    """Direction-aligned realized excess, mean/std (unannualized): the
    realized excess sign-flipped where the evidence favored reduction."""
    aligned = [
        row["actual_excess_return"] * (1.0 if row["expected_excess_return"] > 0 else -1.0)
        for row in rows
        if row["actual_excess_return"] is not None
        and row["expected_excess_return"] not in (None, 0.0)
    ]
    if len(aligned) < 2:
        return None
    mean = sum(aligned) / len(aligned)
    variance = sum((x - mean) ** 2 for x in aligned) / (len(aligned) - 1)
    return mean / math.sqrt(variance) if variance > 0 else None


def horizon_analytics(rows: list[dict]) -> list[dict]:
    table = []
    for horizon in HORIZON_ORDER:
        subset = [r for r in rows if r["horizon"] == horizon]
        errors = [r["prediction_error"] for r in subset if r["prediction_error"] is not None]
        accuracy = _share(
            [r["direction_correct"] for r in subset if r["direction_correct"] is not None]
        )
        confidence = _mean([r["confidence"] for r in subset])
        labels: dict[str, int] = {}
        for r in subset:
            labels[r["recommendation_label"]] = labels.get(r["recommendation_label"], 0) + 1
        table.append(
            {
                "horizon": horizon,
                "n": len(subset),
                "rmse": math.sqrt(sum(e**2 for e in errors) / len(errors)) if errors else None,
                "mae": _mean([abs(e) for e in errors]),
                "direction_accuracy": accuracy,
                "avg_actual_excess": _mean(
                    [
                        r["actual_excess_return"]
                        for r in subset
                        if r["actual_excess_return"] is not None
                    ]
                ),
                "sharpe": _sharpe(subset),
                "recommendation_frequency": dict(sorted(labels.items())),
                "avg_confidence": confidence,
                "calibration_gap": (
                    confidence - accuracy if None not in (confidence, accuracy) else None
                ),
            }
        )
    return table


# -- trim-score buckets --------------------------------------------------------------


def trim_analytics(rows: list[dict], edges: tuple[float, ...] = TRIM_EDGES) -> dict:
    """Is the trim score meaningful? Bucket realized excess by trim score,
    check monotonicity (higher trim -> lower future excess), bucket hit
    rates on the directional buckets, and the Spearman rank correlation
    (meaningful scores correlate negatively with realized excess)."""
    scored = [r for r in rows if r["actual_excess_return"] is not None]
    bounds = [0.0, *edges, 100.0000001]
    neutral_low, neutral_high = edges[len(edges) // 2 - 1], edges[len(edges) // 2]
    buckets = []
    for low, high in zip(bounds, bounds[1:], strict=False):
        subset = [r for r in scored if low <= r["trim_score"] < high]
        excess = [r["actual_excess_return"] for r in subset]
        if high <= neutral_low + 1e-9:  # maintain side: positive excess is a hit
            hit = _share([e > 0 for e in excess])
        elif low >= neutral_high - 1e-9:  # trim side: negative excess is a hit
            hit = _share([e < 0 for e in excess])
        else:
            hit = None  # the neutral band makes no directional claim
        buckets.append(
            {
                "bucket": f"{low:.0f}-{min(high, 100.0):.0f}",
                "n": len(subset),
                "avg_trim_score": _mean([r["trim_score"] for r in subset]),
                "avg_actual_excess": _mean(excess),
                "hit_rate": hit,
            }
        )
    populated = [b["avg_actual_excess"] for b in buckets if b["n"] > 0]
    inversions = sum(1 for a, b in zip(populated, populated[1:], strict=False) if b > a)
    spearman = None
    if len(scored) >= 3:
        spearman = _spearman(
            [r["trim_score"] for r in scored],
            [r["actual_excess_return"] for r in scored],
        )
    return {
        "buckets": buckets,
        "n": len(scored),
        "monotonic": inversions == 0 and len(populated) >= 2,
        "inversions": inversions,
        "rank_correlation": spearman,  # meaningful trim scores are NEGATIVE here
    }
