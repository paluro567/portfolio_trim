"""Stage 6 — generalized ablation: concept-free per-variant reconstruction.

The core groups by a data-supplied variant tag; it must not know domain names.
Full CPE forced-scope parity is a reproduction command.
"""

from datetime import date

import pandas as pd

from mip.research.experiments.ablation import _variant_frame, variant_names
from mip.research.experiments.evaluate import production_ids

D = date(2023, 6, 1)


def _row(model, scope=None):
    r = {
        "symbol": "NVDA",
        "as_of": D,
        "horizon": "1m",
        "model": model,
        "score": 60.0,
        "confidence": 0.5,
        "neutral": False,
        "excess": 0.01,
        "expected": 0.02,
        "z_raw": 0.5,
        "n_eff": 30.0,
    }
    if scope is not None:
        r["scope"] = scope
    return r


def test_variant_names_sorted_from_data() -> None:
    frame = pd.DataFrame(
        [
            _row("conditional_probability", "market"),
            _row("conditional_probability", "market_company"),
        ]
    )
    assert variant_names(frame) == ["market", "market_company"]


def test_variant_frame_isolates_one_variant_plus_baseline() -> None:
    baseline = pd.DataFrame([_row(m) for m in production_ids()])
    ablation = pd.DataFrame(
        [
            _row("conditional_probability", "market"),
            _row("conditional_probability", "market_company"),
        ]
    )
    frame = _variant_frame(baseline, ablation, "conditional_probability", "market", "scope")
    exp_rows = frame[frame["model"] == "conditional_probability"]
    assert len(exp_rows) == 1
    assert exp_rows.iloc[0]["scope"] == "market"  # only the market variant's row
    # all seven production models joined on the matching cell
    assert set(frame[frame["model"] != "conditional_probability"]["model"]) == set(production_ids())


def test_variant_frame_respects_cell_keys() -> None:
    # baseline row on a DIFFERENT cell must not be joined
    baseline = pd.DataFrame([_row(production_ids()[0])])
    baseline.loc[0, "as_of"] = date(2020, 1, 1)  # different as_of
    ablation = pd.DataFrame([_row("conditional_probability", "market")])
    frame = _variant_frame(baseline, ablation, "conditional_probability", "market", "scope")
    # no baseline row shares the (NVDA, 2023-06-01, 1m) key -> only the exp row
    assert (frame["model"] == "conditional_probability").all()
