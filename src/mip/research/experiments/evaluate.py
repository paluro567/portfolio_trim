"""Generalized reconstruction + metrics (Stage 4).

Model-agnostic promotion of the CPE analysis. Reconstructs baseline / experiment-
alone / baseline+experiment (and declared ablation variants) via the EXISTING
production combination path (``mip.validation.systems.combine_rows`` →
``combine_model_evidence`` + ``assess_trim``) — never a re-implementation — and
scores them with the EXISTING ``mip.validation.metrics`` suite on the pre-declared
design/holdout split. Metric definitions are reused verbatim; nothing here
redefines a statistic.

The production baseline set is read from the registry (``Role.PRODUCTION``), so
the comparison always uses the current frozen benchmark, and the experiment id
comes from the spec — no hardcoded model names.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from mip.research.experiments.registry import EXPERIMENTS, Role
from mip.validation import metrics
from mip.validation.realized import realized_outcomes
from mip.validation.systems import combine_rows, load_predictions

HORIZONS = ("1w", "2w", "1m", "3m", "6m", "1y")


def production_ids() -> list[str]:
    return [s.experiment_id for s in EXPERIMENTS if s.role is Role.PRODUCTION]


def system_definitions(experiment_id: str, ablation_scopes: dict[str, str] | None = None) -> dict:
    """The model subsets to reconstruct. ``ablation_scopes`` maps a variant name
    to the experiment's captured ``scope`` tag (Stage 6); by default only the
    three primary systems are built."""
    base = production_ids()
    systems = {
        "baseline": base,
        "combined": [*base, experiment_id],
        "experiment_only": [experiment_id],
    }
    return systems


def build_systems(frame: pd.DataFrame, experiment_id: str) -> pd.DataFrame:
    """Reconstruct every primary system for each (symbol, as_of, horizon)."""
    defs = system_definitions(experiment_id)
    out: list[dict] = []
    for _, group in frame.groupby(["symbol", "as_of", "horizon"], sort=True):
        for name, models in defs.items():
            row = combine_rows(group, models)
            if row is not None:
                out.append({"system": name, **row})
    return pd.DataFrame(out)


def participation(frame: pd.DataFrame, experiment_id: str) -> dict:
    """Experiment participation / neutrality coverage — a first-class metric
    (the CPE was ~48% non-neutral)."""
    rows = frame[(frame["model"] == experiment_id) & frame["horizon"].notna()]
    res = {}
    for hz in HORIZONS:
        sub = rows[rows["horizon"] == hz]
        n = len(sub)
        neutral = int(sub["neutral"].sum()) if n else 0
        res[hz] = {
            "cells": n,
            "neutral": neutral,
            "participation_rate": (round((n - neutral) / n, 4) if n else None),
        }
    return res


def _split(frame: pd.DataFrame, holdout_start: date, holdout: bool) -> pd.DataFrame:
    d = pd.to_datetime(frame["as_of"]).dt.date
    return frame[d >= holdout_start] if holdout else frame[d < holdout_start]


def _per_system(prepared: pd.DataFrame) -> dict:
    return {
        hz: {
            sysn: metrics.accuracy_and_brier(
                prepared[(prepared["horizon"] == hz) & (prepared["system"] == sysn)]
            )
            for sysn in ("baseline", "combined", "experiment_only")
        }
        for hz in HORIZONS
    }


def _incremental(prepared: pd.DataFrame) -> dict:
    res = {}
    for hz in HORIZONS:
        co = metrics.cohort(prepared[prepared["system"] == "combined"], hz)
        ba = metrics.cohort(prepared[prepared["system"] == "baseline"], hz)
        res[hz] = metrics.block_bootstrap_delta(co, ba, metric="hit")
    return res


def _calibration(prepared: pd.DataFrame, system: str) -> dict:
    res = {}
    for hz in ("1w", "2w", "1m", "3m"):
        sub = prepared[(prepared["horizon"] == hz) & (prepared["system"] == system)]
        bins = metrics.calibration_bins(sub)
        occ = bins[bins["n"] > 0].dropna(subset=["mean_p", "realized_positive"])
        ece = (
            float(
                ((occ["mean_p"] - occ["realized_positive"]).abs() * occ["n"]).sum() / occ["n"].sum()
            )
            if len(occ)
            else None
        )
        res[hz] = {"ece": ece, "bins": bins.to_dict("records")}
    return res


def _confidence(prepared: pd.DataFrame, system: str) -> dict:
    return {
        hz: metrics.confidence_split(
            prepared[(prepared["horizon"] == hz) & (prepared["system"] == system)]
        )
        for hz in ("1w", "2w", "1m", "3m")
    }


def evaluate(
    factory,
    predictions_path: Path,
    experiment_id: str,
    holdout_start: date = date(2022, 1, 1),
) -> dict:
    """The full generalized analysis for one experiment. Reuses realized
    outcomes + the metrics suite verbatim."""
    frame = load_predictions(predictions_path)
    systems = build_systems(frame, experiment_id)
    symbols = sorted(systems["symbol"].unique())
    dates_by_symbol = {s: sorted(set(systems[systems["symbol"] == s]["as_of"])) for s in symbols}
    outcomes = realized_outcomes(factory, symbols, dates_by_symbol)
    prepared_all = metrics.prepare(systems, outcomes)

    result: dict = {
        "experiment_id": experiment_id,
        "participation": participation(frame, experiment_id),
        "splits": {},
    }
    for label, holdout in (("design", False), ("holdout", True)):
        prepared = _split(prepared_all, holdout_start, holdout)
        result["splits"][label] = {
            "n_rows": int(len(prepared)),
            "per_system": _per_system(prepared),
            "incremental_combined_minus_baseline": _incremental(prepared),
            "calibration_experiment": _calibration(prepared, "experiment_only"),
            "confidence_experiment": _confidence(prepared, "experiment_only"),
        }
    return result
