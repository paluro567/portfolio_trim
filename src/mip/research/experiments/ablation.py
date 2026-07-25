"""Generalized ablation protocol (Stage 6).

An ablation study compares variants of an experiment (component on/off, forced
scope, feature-family removed, confidence/weighting component removed, …). The
CORE here is deliberately concept-free: it groups captured experiment evidence
by a ``variant`` tag supplied IN THE DATA, then reconstructs and scores each
variant with the SAME production combiner, realized outcomes, metrics, and split
as the primary experiment. It knows nothing about "market"/"sector"/"company"/
"catalyst" — those are the CPE adapter's vocabulary, carried on the tag.

An experiment declares its ablation dimensions in ``ExperimentSpec.ablation_
dimensions``; an experiment-specific adapter produces the tagged evidence (e.g.
the CPE forced-scope evaluator). This module consumes that tagged evidence.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from mip.research.experiments.evaluate import build_systems, production_ids
from mip.validation import metrics
from mip.validation.realized import realized_outcomes

VARIANT_COLUMN = "scope"  # default tag column (the CPE tags its forced scopes here)


def variant_names(ablation_frame: pd.DataFrame, variant_col: str = VARIANT_COLUMN) -> list[str]:
    return sorted(v for v in ablation_frame[variant_col].dropna().unique())


def _variant_frame(
    baseline_frame: pd.DataFrame,
    ablation_frame: pd.DataFrame,
    experiment_id: str,
    variant: str,
    variant_col: str,
) -> pd.DataFrame:
    """Experiment rows for one variant + the production baseline rows on the
    same (symbol, as_of, horizon) cells — the input to the shared combiner."""
    exp = ablation_frame[ablation_frame[variant_col] == variant].copy()
    exp = exp[exp["model"] == experiment_id]
    keys = set(zip(exp["symbol"], exp["as_of"].astype(str), exp["horizon"], strict=True))
    base = baseline_frame[baseline_frame["model"].isin(production_ids())].copy()
    base = base[base.apply(lambda r: (r["symbol"], str(r["as_of"]), r["horizon"]) in keys, axis=1)]
    return pd.concat([base, exp], ignore_index=True)


def variant_metrics(
    factory,
    baseline_frame: pd.DataFrame,
    ablation_frame: pd.DataFrame,
    experiment_id: str,
    variant: str,
    holdout_start: date = date(2022, 1, 1),
    horizon: str = "1m",
    variant_col: str = VARIANT_COLUMN,
) -> dict:
    frame = _variant_frame(baseline_frame, ablation_frame, experiment_id, variant, variant_col)
    systems = build_systems(frame, experiment_id)
    if systems.empty:
        return {"variant": variant, "n": 0}
    symbols = sorted(systems["symbol"].unique())
    dates_by_symbol = {s: sorted(set(systems[systems["symbol"] == s]["as_of"])) for s in symbols}
    outcomes = realized_outcomes(factory, symbols, dates_by_symbol)
    prepared = metrics.prepare(systems, outcomes)
    d = pd.to_datetime(prepared["as_of"]).dt.date
    hold = prepared[(d >= holdout_start) & (prepared["horizon"] == horizon)]
    exp = metrics.accuracy_and_brier(hold[hold["system"] == "experiment_only"])
    comb = metrics.accuracy_and_brier(hold[hold["system"] == "combined"])
    base = metrics.accuracy_and_brier(hold[hold["system"] == "baseline"])
    return {
        "variant": variant,
        "n": exp.get("n", 0),
        "experiment_accuracy": exp.get("direction_accuracy"),
        "experiment_brier": exp.get("brier"),
        "combined_accuracy": comb.get("direction_accuracy"),
        "baseline_accuracy": base.get("direction_accuracy"),
        "incremental": (
            (comb.get("direction_accuracy") or 0) - (base.get("direction_accuracy") or 0)
        ),
    }


def analyze_ablation(
    factory,
    baseline_frame: pd.DataFrame,
    ablation_frame: pd.DataFrame,
    experiment_id: str,
    holdout_start: date = date(2022, 1, 1),
    horizon: str = "1m",
    variant_col: str = VARIANT_COLUMN,
) -> dict:
    """Per-variant standalone + incremental metrics, deterministically ordered
    by variant name. Concept-free: variants come from the data tag."""
    return {
        "experiment_id": experiment_id,
        "horizon": horizon,
        "variants": [
            variant_metrics(
                factory,
                baseline_frame,
                ablation_frame,
                experiment_id,
                v,
                holdout_start,
                horizon,
                variant_col,
            )
            for v in variant_names(ablation_frame, variant_col)
        ],
    }
