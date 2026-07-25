"""Stage 4 — generalized reconstruction: system-building mechanics (DB-free).

Full CPE metric parity against the archived results is an explicit reproduction
command; here we prove the reconstruction reads the registry benchmark, builds
the three primary systems via the production combiner, and computes
participation correctly.
"""

from datetime import date

import pandas as pd

from mip.research.experiments.evaluate import (
    build_systems,
    participation,
    production_ids,
    system_definitions,
)

D = date(2023, 6, 1)


def _row(model: str, horizon: str, score: float, neutral: bool) -> dict:
    return {
        "symbol": "NVDA",
        "as_of": D,
        "horizon": horizon,
        "model": model,
        "score": score,
        "confidence": 0.0 if neutral else 0.5,
        "neutral": neutral,
        "excess": None if neutral else (score - 50) / 1000.0,
        "expected": None if neutral else 0.02,
        "z_raw": None if neutral else (score - 50) / 20.0,
        "n_eff": 0.0 if neutral else 30.0,
    }


def test_system_definitions_read_registry_benchmark() -> None:
    defs = system_definitions("conditional_probability")
    assert defs["baseline"] == production_ids()
    assert defs["combined"] == [*production_ids(), "conditional_probability"]
    assert defs["experiment_only"] == ["conditional_probability"]
    assert "conditional_probability" not in defs["baseline"]  # experiment never in baseline


def test_build_systems_reconstructs_three_systems() -> None:
    rows = [_row(m, "1m", 60.0, neutral=False) for m in production_ids()]
    rows.append(_row("conditional_probability", "1m", 40.0, neutral=False))
    frame = pd.DataFrame(rows)
    systems = build_systems(frame, "conditional_probability")
    assert set(systems["system"]) == {"baseline", "combined", "experiment_only"}
    baseline = systems[systems["system"] == "baseline"].iloc[0]
    combined = systems[systems["system"] == "combined"].iloc[0]
    cpe_only = systems[systems["system"] == "experiment_only"].iloc[0]
    assert baseline["participating"] == len(production_ids())
    assert combined["participating"] == len(production_ids()) + 1
    assert cpe_only["participating"] == 1


def test_experiment_neutral_excluded_from_combined_participation() -> None:
    rows = [_row(m, "1m", 60.0, neutral=False) for m in production_ids()]
    rows.append(_row("conditional_probability", "1m", 50.0, neutral=True))
    frame = pd.DataFrame(rows)
    systems = build_systems(frame, "conditional_probability")
    combined = systems[systems["system"] == "combined"].iloc[0]
    baseline = systems[systems["system"] == "baseline"].iloc[0]
    # a neutral experiment adds nothing -> combined participation == baseline
    assert combined["participating"] == baseline["participating"]


def test_participation_rate() -> None:
    rows = [
        _row("conditional_probability", "1m", 60.0, neutral=False),
        _row("conditional_probability", "1m", 50.0, neutral=True),
        _row("conditional_probability", "1m", 55.0, neutral=False),
    ]
    frame = pd.DataFrame(rows)
    part = participation(frame, "conditional_probability")
    assert part["1m"]["cells"] == 3
    assert part["1m"]["neutral"] == 1
    assert part["1m"]["participation_rate"] == round(2 / 3, 4)
