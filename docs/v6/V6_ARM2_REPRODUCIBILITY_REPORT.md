# V6 Arm 2 — Reproducibility Report (R7, R8, R9, R10)

## R7 — Determinism: NOT REACHED

R7 requires two full runs under different `PYTHONHASHSEED` producing byte-identical output. **Not executed**, for a stated reason: R7 certifies the reproducibility of *the preregistered experiment*, and that experiment is blocked (B-01/B-02/B-03). Certifying the determinism of a run that must not happen would be a false readiness signal.

Determinism groundwork that **is** in place:

- Seeds derive from `SEED_BASE = 20260801` by integer arithmetic, never from `hash()`. The Arm 1 `hash()` defect (PYTHONHASHSEED-randomised) is not reproduced here.
- Ranking uses `mergesort` (stable) and, post-D-04, average-rank tie handling — order-independent for tied values.
- Cell construction is a deterministic function of the trading calendar and the price panel.
- Feature build is reproducible: two consecutive builds produced identical row counts (855,418 / 100,739).

Residual risk that must be closed before R7 can pass: **dict iteration order in `INJ["delta"]`**. It is populated in cell order and consumed by lookup, so it should not affect results — but "should not" is exactly what R7 exists to test. It must be tested, not asserted.

## R8 — Version control: BLOCKED

R8 requires the preregistration and Addendum A committed and hashed **before first injection**.

```
HEAD    1b2aec9f935a6f4792e00d0e7f684cc37ef05ebd
branch  main
status  56 uncommitted paths
```

Uncommitted content includes the entire `docs/` output of this programme (V2/V2.1/V3 architecture, CIO review, constraint analysis, Phase 1 package, all V6 artifacts) and every restored price CSV under `RawData/prices/`.

**The tree is not clean and no commit was made.** Committing is an outward-facing act on the user's repository that was not requested, and R8's purpose — binding a preregistration to an immutable commit *before* results exist — is not served by a commit made after the blocking analysis is already written. R8 stays BLOCKED pending an explicit instruction to commit.

## R9 — Hashing: NOT REACHED

R9 hashes the preregistration, Addendum A, model source, feature-store snapshot and restored-panel manifest. All five inputs exist, but hashing an uncommitted tree binds nothing — any of the 56 dirty paths can change without trace. **R9 is gated behind R2/R8** and was not performed, rather than performed in a form that would look like evidence without being evidence.

## R10 — Random seeds: CLOSED

- `SEED_BASE = 20260801`, applied.
- Derivation per §2.5 of the preregistration: integer arithmetic over (horizon index, ρ index, seed index). No `hash()`.
- **≥200 placebo seeds confirmed affordable** — 200 seeds cost 26.3 h serial, ≈3.3 h under the 8-way batching plan (`V6_ARM2_RUNTIME_BENCHMARK.md` §4).

## R11 — Placebo arm: NOT REACHED

Implementable — within-date permutation of `y`, marginals preserved by construction since permutation is measure-preserving. Not built: a placebo arm calibrates the null for an endpoint that cannot be computed while A2 fails.

## Cross-arm reproducibility defect — D-04

`v6_arm1.py` and `a15_run.py` both rank via `argsort(argsort(...))` with no tie handling. Model scores come from `score_from_z` under `Z_CLIP`; clipping produces exact ties at the boundary, and tied values receive **distinct, index-order-dependent ranks**.

Two consequences:
1. IC and LOSS estimates in Arm 1 and Arm 1.5 carry an unquantified bias wherever scores tie.
2. Those statistics are **sensitive to row order** — a reproducibility failure independent of any seed.

This surfaced here only because three models produced perfectly constant output, making the artifact impossible to miss. Re-verification of Arm 1 and Arm 1.5 under tie-aware ranking is recommended to the Program Board. It is outside my authority to re-open those arms.


> **[AMENDED A-2026-005, 2026-08-04]** The tie-mechanism statement above is superseded. Measurement shows the **dominant** tie value is **50.0, the neutral score** (1w 5, 2w 5, 1m 2, 3m 2, 6m 2, 1y 2 cells). A second 2-member group at 1y sits at score ~0.00317, consistent with a `Z_CLIP` floor, so clipping is a **minor secondary contributor, not the mechanism**. Corrected statement: *the neutral score is the dominant tie mechanism; clipping contributes once, at 1y.*
