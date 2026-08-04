# V6 ARM 1.5 — REPRODUCIBILITY RECORD

---

## Execution environment

| Field | Value |
|---|---|
| Commit | `1b2aec9f935a6f4792e00d0e7f684cc37ef05ebd` |
| Interpreter | project venv via `uv run python` (Python 3.11) |
| Working directory | `/Users/peterluro/Desktop/stock_scoring` |
| Date (UTC) | 2026-08-01 |
| Runtime — primary | **24.2 s** |
| Runtime — secondaries | ~5 min |

## Commands executed

```bash
uv run python /tmp/a15_prereq.py     # Part 1 prerequisite verification
uv run python /tmp/a15_run.py        # Parts 2-4: injection, LOSS, primary decision
uv run python /tmp/a15_sec.py        # Part 5: secondary endpoints (after primary finalised)
```

## Random seeds

| Component | Seed | Note |
|---|---|---|
| Block bootstrap | **20260801** | `np.random.default_rng(20260801)`, fixed for every horizon and ρ |
| Injection | **none required** | The preregistered injection formula contains **no noise term** — it is deterministic given ρ. Only the bootstrap consumes randomness |

> **Interpretation recorded, not a redesign.** The preregistration states "seeds deterministic, ≥200 per
> cell." Because the injection as written is deterministic, there is exactly **one** realisation per ρ;
> the ≥200 requirement is therefore satisfied by the bootstrap, run at **1,000 draws** — five times the
> preregistered minimum. This is a faithful reading of a specification written before the deterministic
> property was apparent.

## Parameters as executed

```
RHO_GRID   = [0.00, 0.03, 0.05, 0.07, 0.10, 0.15, 0.20]   (as preregistered)
PRIMARY    = 0.10                                          (as preregistered)
N_BOOT     = 1000
BLOCK      = 4                                             (matches shipped block_bootstrap_delta)
kappa_m    = std(effect_m) computed WITHIN each horizon
cohort     = mip.validation.metrics.cohort  (identical to Arm 1)
target     = spy_rel  (system-independent; never modified)
```

**κ_m scope note:** the preregistration writes `κ_m` indexed by model. Effect scales differ by an order
of magnitude across horizons, so κ was computed within each horizon — the only implementation under
which the preregistered intent ("so no model is privileged") holds when analysis is per-horizon.
Recorded as an implementation decision, made before results were examined.

## Input artifacts

| Artifact | Detail |
|---|---|
| `predictions_*.jsonl` × 7 | 54,522 rows for the 7 official models |
| `merged.csv` | sha256 `d3db3fa9dbb7a57d54db3762ee47781b…`; `baseline` system supplies the cell structure |
| Outcome column | `spy_rel` — **read-only throughout** |

## Verification performed

| Check | Result |
|---|---|
| Combiner replication vs `combine_rows` | **max err 1.42e-14** over 250 cells (reference 2.84e-14) |
| `score = 100·Φ(clip(z_raw))` | **max err 0.000e+00** over 36,926 rows |
| Harness validity — FP at ρ = 0.00 | **0/6 horizons**, FP = 0.000 (limit 0.10) |
| Weight invariance under injection | HHI identical to 4 dp — confirms `se` was held fixed as specified |
| Outcomes unmodified | `spy_rel` never assigned; verified by inspection |

## Generated artifacts

```
docs/v6/V6_ARM15_RESULTS.md
docs/v6/V6_ARM15_INFORMATION_LOSS.csv        42 rows (6 horizons x 7 rho)
docs/v6/V6_ARM15_BOOTSTRAP_RESULTS.csv       42 rows + per-row verdict
docs/v6/V6_ARM15_SECONDARY.csv               42 rows, detection + HHI
docs/v6/V6_ARM15_WEIGHTS.csv                 per-model weights at rho 0.00 / 0.10
docs/v6/V6_ARM15_DIAGNOSTICS.md
docs/v6/V6_ARM15_REPRODUCIBILITY.md
```

## Deviations from preregistration

**None affecting any endpoint, hypothesis, or criterion.** Two recorded interpretations, both made
before results were examined:

1. **Seeds** — injection is deterministic, so seed applies to the bootstrap (see above).
2. **κ_m computed within horizon** — required for the preregistered intent to hold (see above).

## Preregistration gap surfaced during execution

The preregistration names **one** primary endpoint but the experiment yields **six** (one per horizon),
and **no pooling rule was specified.** The rule was applied mechanically at every horizon and reported
as a distribution. **No pooled verdict is claimed; no horizon was selected after seeing results.**
Recorded as a gap in the preregistration, not resolved post hoc.

## Scope limitation, restated

Because `se` was held fixed as preregistered, **weights could not move.** Arm 1.5 therefore tested
whether the aggregation destroys signal **given** the existing weights. It did **not** test whether
those weights are well-chosen. The separately measured `Spearman(median|effect|, weight) = −1.000`
inversion is untouched by this experiment.
