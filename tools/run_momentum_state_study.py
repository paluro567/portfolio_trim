"""Execute the frozen momentum_state_v1 study. Research-only; writes artifacts."""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope
from mip.research import momentum_state as ms
from mip.research.experiments.prereg import PreRegistration

ART = Path("data/validation/momentum_state_v1")
prereg = PreRegistration.load(ART / "prereg.json")
prereg.verify_integrity()
print(f"prereg verified: {prereg.experiment_id} hash={prereg.content_hash[:16]}")

with session_scope(open_session_factory()) as s:
    syms = ms.eligible_symbols(s, date(2013, 1, 1), 2520)
    if ms.BENCHMARK not in syms:
        syms.append(ms.BENCHMARK)
    print(f"universe: {len(syms)} symbols")
    prices = ms.load_price_series(s, syms)
    regime = ms.load_market_regime(s)
    print(f"prices loaded: {len(prices)} symbols; regime days: {len(regime)}")

mom_window = int(sys.argv[1]) if len(sys.argv) > 1 else 21
obs = ms.build_observations(prices, regime, momentum_window=mom_window)
print(f"observations: {len(obs)}")

report: dict = {
    "experiment_id": prereg.experiment_id,
    "prereg_hash": prereg.content_hash,
    "generated_at": datetime.now(UTC).isoformat(),
    "momentum_window": mom_window,
    "universe_size": len(prices),
    "raw_observations": len(obs),
    "horizons": {},
}

for horizon in ("1w", "1m"):
    design, holdout = ms.split_observations(obs, horizon)
    viol = ms.leakage_violations(design, holdout, horizon)
    h: dict = {
        "n_design": len(design),
        "n_holdout": len(holdout),
        "leakage_violations": len(viol),
        "leakage_examples": viol[:5],
    }
    if viol:
        report["horizons"][horizon] = h
        continue

    # cells: momentum bucket x regime, on the HOLDOUT (reported evidence)
    base = ms.summarise(holdout, horizon, "UNCONDITIONAL")
    h["baseline_unconditional"] = base.to_dict()
    cells = []
    for b in range(len(ms.BUCKET_LABELS)):
        mom_cell = [o for o in holdout if o.bucket == b]
        if mom_cell:
            cells.append(
                ms.summarise(mom_cell, horizon, f"mom={ms.BUCKET_LABELS[b]}").to_dict()
                | {
                    "kind": "momentum_only",
                    "interpretation": ms.interpret(ms.summarise(mom_cell, horizon, "x"), base),
                }
            )
        for r in (0, 1, 2, 3):
            cell = [o for o in mom_cell if o.regime == r]
            if not cell:
                continue
            st = ms.summarise(cell, horizon, f"mom={ms.BUCKET_LABELS[b]} | {ms.REGIME_LABELS[r]}")
            cells.append(
                st.to_dict()
                | {"kind": "momentum_x_regime", "interpretation": ms.interpret(st, base)}
            )
    for r in (0, 1, 2, 3):
        cell = [o for o in holdout if o.regime == r]
        if cell:
            cells.append(
                ms.summarise(cell, horizon, ms.REGIME_LABELS[r]).to_dict() | {"kind": "regime_only"}
            )
    h["cells"] = cells

    # systems
    sysres = {}
    for name, key in ms.SYSTEMS.items():
        acc, flags, _ = ms.evaluate(design, holdout, horizon, key)
        sysres[name] = {"accuracy": acc, "n_scored": len(flags)}
    h["systems"] = sysres

    # PRIMARY: momentum+regime vs regime-only
    h["incremental_vs_regime_only"] = ms.paired_delta_bootstrap(
        design, holdout, horizon, ms.K_BOTH, ms.K_REG
    )
    h["incremental_vs_momentum_only"] = ms.paired_delta_bootstrap(
        design, holdout, horizon, ms.K_BOTH, ms.K_MOM
    )
    h["incremental_relstrength_vs_both"] = ms.paired_delta_bootstrap(
        design, holdout, horizon, ms.K_BOTH_REL, ms.K_BOTH
    )
    h["ece_momentum_plus_regime"] = ms.expected_calibration_error(
        design, holdout, horizon, ms.K_BOTH
    )
    h["confidence"] = ms.confidence_inversion(design, holdout, horizon, ms.K_BOTH)
    h["per_symbol"] = ms.per_symbol_delta(design, holdout, horizon, ms.K_BOTH, ms.K_REG)
    report["horizons"][horizon] = h

out = ART / (f"results_ret{mom_window}d.json")
out.write_text(json.dumps(report, indent=2, sort_keys=True, default=str))
print("wrote", out)
for hz, h in report["horizons"].items():
    print(
        f"\n=== {hz} ===  design={h['n_design']} holdout={h['n_holdout']} "
        f"leakage={h['leakage_violations']}"
    )
    if h.get("systems"):
        for k, v in h["systems"].items():
            print(f"   {k:32s} acc={v['accuracy']:.4f} n={v['n_scored']}")
        inc = h["incremental_vs_regime_only"]
        print(
            f"   INCREMENTAL vs regime-only: delta={inc['delta']:+.4f} "
            f"CI=[{inc['ci_low']:+.4f},{inc['ci_high']:+.4f}] n={inc['n']}"
        )
        print(
            f"   ECE={h['ece_momentum_plus_regime']:.4f}  "
            f"confidence_inverted={h['confidence']['inverted']}"
            f" (hi={h['confidence']['high_conf_acc']:.4f} "
            f"lo={h['confidence']['low_conf_acc']:.4f})"
        )
        ps = h["per_symbol"]
        print(
            f"   per-symbol: n={ps['n_symbols']} "
            f"median_delta={ps.get('median_delta', float('nan')):+.4f} "
            f"share_positive={ps.get('share_positive', float('nan')):.2%}"
        )
