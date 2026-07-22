"""Original-vs-hardened validation comparison (deliverable of the
harness-hardening phase).

Reads the CONTAMINATED original artifacts and the EMBARGOED rerun,
produces a side-by-side per-horizon table for every system, and
decomposes the change. Both artifact sets are preserved; nothing is
overwritten.

Run:  uv run python -m mip.validation.compare
"""

import json
from pathlib import Path

import pandas as pd

ORIGINAL = Path("data/validation/analogue_v1")
HARDENED = ORIGINAL / "embargoed_revalidation"
SYSTEMS = ("baseline", "analogue_only", "combined")
METRICS = (
    "direction_accuracy",
    "brier",
    "rank_correlation",
    "mae",
    "n",
    "mean_realized_excess",
)


def _load(directory: Path, period: str) -> pd.DataFrame:
    frame = pd.read_csv(directory / f"metrics_{period}.csv")
    return frame[(frame["sample"] == "cohort") & frame["system"].isin(SYSTEMS)]


def comparison_table(period: str) -> pd.DataFrame:
    original = _load(ORIGINAL, period)
    hardened = _load(HARDENED, period)
    merged = original.merge(hardened, on=["system", "horizon"], suffixes=("_original", "_hardened"))
    rows = []
    for _, row in merged.iterrows():
        entry = {"system": row["system"], "horizon": row["horizon"]}
        for metric in METRICS:
            original_value = row.get(f"{metric}_original")
            hardened_value = row.get(f"{metric}_hardened")
            entry[f"{metric}_original"] = original_value
            entry[f"{metric}_hardened"] = hardened_value
            if pd.notna(original_value) and pd.notna(hardened_value):
                entry[f"{metric}_delta"] = hardened_value - original_value
        rows.append(entry)
    return pd.DataFrame(rows)


def incremental_table(period: str, directory: Path) -> pd.DataFrame:
    """Combined-minus-baseline per horizon within one artifact set —
    the analogue's incremental contribution."""
    frame = _load(directory, period)
    combined = frame[frame["system"] == "combined"].set_index("horizon")
    baseline = frame[frame["system"] == "baseline"].set_index("horizon")
    rows = []
    for horizon in combined.index:
        if horizon not in baseline.index:
            continue
        rows.append(
            {
                "horizon": horizon,
                "n": combined.loc[horizon, "n"],
                "accuracy_delta": combined.loc[horizon, "direction_accuracy"]
                - baseline.loc[horizon, "direction_accuracy"],
                "brier_delta": combined.loc[horizon, "brier"] - baseline.loc[horizon, "brier"],
                "rank_delta": combined.loc[horizon, "rank_correlation"]
                - baseline.loc[horizon, "rank_correlation"],
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    outputs = {}
    for period in ("calibration", "holdout"):
        table = comparison_table(period)
        table.to_csv(HARDENED / f"comparison_{period}.csv", index=False)
        outputs[period] = table
        for name, directory in (("original", ORIGINAL), ("hardened", HARDENED)):
            incremental = incremental_table(period, directory)
            incremental.to_csv(HARDENED / f"incremental_{name}_{period}.csv", index=False)

    leakage = json.loads((HARDENED / "leakage_report.json").read_text())
    decomposition = {
        "leakage_report": leakage,
        "note": (
            "delta columns = hardened - original. For 1w/2w the original run "
            "had zero crossing-window exposure, so any delta there estimates "
            "run-to-run variation (the 'remaining unexplained change' bound); "
            "deltas beyond that band at 1m+ are attributable to the embargo."
        ),
    }
    (HARDENED / "comparison_summary.json").write_text(json.dumps(decomposition, indent=2))
    holdout = outputs["holdout"]
    analogue = holdout[holdout["system"] == "analogue_only"][
        ["horizon", "direction_accuracy_original", "direction_accuracy_hardened", "n_hardened"]
    ]
    print("analogue-only holdout accuracy, original vs hardened:")
    print(analogue.to_string(index=False))
    print(f"\nleakage violations in hardened run: {leakage['violations_total']}")
    print(f"artifacts written to {HARDENED}/")


if __name__ == "__main__":
    main()
