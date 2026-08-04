# V6 — Recovered-SE Repair Decision (Parts 9, 11)

**Date:** 2026-08-02 · Based solely on the completed paired experiment.

## Part 9 — Decision matrix, applied mechanically

| # | Condition | Applies? | Evidence |
|---|---|---|---|
| 1 | Defect remains mechanically present → REPAIR FAILED | **No** | weight formula contains no effect term; max top-share 0.878 → 0.628; `spearman(n_eff, w)` +0.48 → +0.68 |
| 2 | Defect removed, repaired materially beats original → PERFORMANCE-RELEVANT | **No** | 0 horizons PASS |
| 3 | Defect removed, repaired ties original → **DEFECT WAS REAL BUT NOT MATERIAL TO PERFORMANCE** | **YES — governing** | 5 of 6 horizons INCONCLUSIVE; PROGRAM NULL |
| 4 | Defect removed, repaired loses → original accidentally beneficial; defect still must not return | **YES at 1w only** | ΔAB = −0.006196, CI [−0.010948, −0.000546] |
| 5 | Repaired fails to beat equal weight or the simple baseline → **COMPLEX WEIGHTING REMAINS UNJUSTIFIED** | **YES** | beats equal weight at 6/6, but **loses to constant-50% at 6/6**, significantly at 5/6 |
| 6 | Underpowered → INCONCLUSIVE, do not claim repair effectiveness | **Partly** | 5 of 6 horizons INCONCLUSIVE on the primary |

**Governing program decision: rows 3 + 5.** The defect was real and is now mechanically eliminated, but it was **not material to performance**, and no weighting scheme tested — defective, repaired, or equal — is justified against an uninformed constant forecaster.

Row 4 is recorded and binding in one direction: the defect's marginal apparent benefit at 1w does not license its retention. It must not return.

## Part 11 — Final decision

1. **Defect reproduced: YES** — `spearman(|effect|, weight) = −0.7228`; near-zero effects draw 11–12× median weight.
2. **Valid replacement available: YES** — `se = k_h/√n_eff`, point-in-time, independently stored, bounded.
3. **Original canonical result reproduced: YES** — max │Δscore│ = 2.842e-14.
4. **Experimental invariants passed: YES** — 8/8.
5. **Defect mechanically eliminated: YES** — no effect term in the weight; max top-share 0.878 → 0.628; effective models 3.91 → 4.13.
6. **Repaired ensemble beats original: NO** — 0 PASS, 1 FAIL, 5 INCONCLUSIVE; directionally worse at 5 of 6 horizons.
7. **Repaired ensemble beats equal weight: YES** — positive at 6/6 horizons, significant at 1w and 2w.
8. **Repaired ensemble beats the frozen simple baseline: NO** — loses to constant-50% at 6/6, significant at 5/6, by ≈0.05–0.08 Brier.
9. **Complex weighting remains scientifically justified: NO.**
10. **Any prior conclusion withdrawn: YES — one, narrowly.** The claim that the recovered-SE defect *is implicated in the platform's measured ensemble failure* is withdrawn **as a causal claim about performance**. The defect is confirmed real and confirmed to produce inverted weighting; repairing it does not recover performance. The related prior finding that equal-weight's advantage came from **shrinkage** is not withdrawn — this experiment independently **confirms** it: once the calibration scale is held fixed, equal weighting loses at all six horizons.
11. **Scientific program should continue: NO.**

   The Oversight Committee predeclared that the program should stop after this test if it failed. It has run. The single highest-EVI action available at zero cost is now exhausted: the one diagnosed defect standing between the platform and a verdict is repaired, and the verdict is unchanged. Every ensemble variant loses to a coin flip by ≈0.05–0.08 Brier at nearly every horizon, rank ICs straddle zero, and directional accuracy sits at ~0.50. There is no remaining diagnosed defect whose repair could plausibly alter this.

   *Scope, stated honestly:* this panel is class-B restored, 10 symbols, 3,252 cohort cells, with 3 of 7 models emitting constant output. The finding is nonetheless a replication — the prior paired-baseline study reached the same conclusion on a fuller substrate — and the margin is large and significant, not marginal.

12. **Single highest-value next action**

   > **Stop ensemble development and close the scientific record.** Apply amendments A-2026-001 … 005 to their target artifacts, commit the working tree (56 uncommitted paths at HEAD `1b2aec9f`), SHA-256 every artifact, and write `MANIFEST.sha256`.

   The record currently contains five documented-but-unapplied corrections, no hashes, and no manifest. That is the one remaining task whose value does not depend on the platform having skill — and it is the prerequisite for any future work, by anyone, on any substrate.

   The production defect at `src/mip/engine/evidence.py:331` should be repaired **as a code-correctness matter**, not as a performance intervention. This experiment establishes it will not improve forecasts.


> **[AMENDED A-2026-006, 2026-08-04]** Any statement that the recovered-SE defect is *implicated in the platform's measured ensemble failure* is **WITHDRAWN as a causal claim about performance**. The inversion is confirmed (`spearman(|effect|, weight) = -0.7228`); the completed repair experiment established the defect is **not** a cause of the forecasting failure. See `V6_AMENDMENT_006_RECOVERED_SE.md`.
