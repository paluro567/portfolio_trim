# V6 — Recovered-SE Defect Inventory (Part 1)

**Date:** 2026-08-02 · **Status:** pre-repair. No repair implemented or executed at time of writing.

## 1. Occurrences

Exhaustive search of `src/`, `tools/`, `tests/` for `se = |effect / z|` and algebraic equivalents.

| # | File | Line | Form | Caller | Downstream use |
|---|---|---|---|---|---|
| D1 | `src/mip/engine/evidence.py` | **331** | `abs(participating[m].expected_excess_return / participating[m].diagnostics.z_raw)` | `combine_decision_evidence()` | feeds D2 |
| D2 | `src/mip/engine/evidence.py` | **338** | `weights = [1.0 / s**2 for s in ses]` | same | precision weights → `weight_share`, combined effect, combined variance, combined z |
| D3 | `src/mip/engine/evidence.py` | 130 | `se: float  # recovered from effect / z_raw` | dataclass field | serialized into every archived per-model breakdown |
| D4 | `src/mip/engine/evidence.py` | 15 | docstring: "standard error recovered EXACTLY as se = effect / z_raw" | — | documents the defect as intended behaviour |
| D5 | `src/mip/engine/evidence.py` | 378 | `if reason.se <= 0:` | guard | only guard present; catches `se ≤ 0`, **not** `se → 0` |

**No occurrence exists in `tests/`, `tools/`, or any notebook.** The Arm 1.5 research harness reproduced the same expression (`se = (excess/z_raw).abs()`) deliberately, to replicate production; that harness was a scratch file and no longer exists on disk.

### Impact classification

| Question | Answer |
|---|---|
| Affects model weighting? | **Yes** — D1→D2 is the sole source of precision weights |
| Affects confidence? | **Yes, indirectly** — combined variance uses `se_i` in the correlated fixed-effect quadratic form; combined z scales with it |
| Affects calibration? | **Yes, indirectly** — `p_up = evidence_score/100 = Φ(z_combined)`, so any change to combined z moves the forecast probability |
| Affects archived historical outputs? | **Yes** — every row of the archived `baseline`, `combined`, `rho_*` and `shadow` systems was produced through D1/D2 |
| Active / legacy / dead? | **ACTIVE production code.** Not legacy, not dead. |

## 2. Reproduction of the inversion (canonical artifacts, 36,926 participating model-cell records, 6 models, 7,514 cells)

### 2.1 Relationship between |effect| and assigned weight

| Statistic | Value | Interpretation |
|---|---|---|
| `spearman(|effect|, weight)` | **−0.7228** | **Inversion confirmed.** A model reporting a larger effect is systematically assigned a *smaller* weight. |
| `spearman(se, |effect|)` | +0.7228 | the recovered "uncertainty" is largely a restatement of effect magnitude |
| `spearman(|z_raw|, weight)` | +0.1607 | weight responds only weakly to actual evidence strength |
| `spearman(n_eff, weight)` | **+0.8594** | the defective weight nonetheless tracks effective sample size closely in rank terms |

Algebraically `w = 1/se² = (z/effect)²`, so for fixed `z`, `w ∝ effect⁻²`. The measured −0.72 is that identity showing through the panel.

**Recorded before the repair is run:** the +0.8594 association with `n_eff` means the defective weighting already approximates sample-size weighting in rank order. This is a *mechanism* observation, not an outcome, and it lowers the prior expectation that repair will move performance materially.

### 2.2 Pathological weights

| Measure | Value |
|---|---|
| weight p50 / p90 / p99 / p99.9 / max | 1.672e3 / 4.155e4 / 1.386e5 / 1.981e5 / 2.496e5 |
| max / median ratio | 1.493e2 |
| weights > 100× median | 161 (0.436%) |
| weights > 10⁴× median | 0 |

### 2.3 Behaviour near zero

| Condition | n | median weight | vs panel median |
|---|---|---|---|
| `|effect| < 1e-4` | 253 | 2.000e4 | **12.0×** |
| `|effect| < 1e-3` | 2447 | 1.825e4 | **10.9×** |
| `|z_raw| < 0.05` | 1989 | 7.352e2 | 0.4× |
| `effect == 0` exactly | **0** | — | would be `+inf` |
| `z_raw == 0` | 0 (excluded upstream) | — | — |

The `effect → 0 ⇒ weight → ∞` pathology is **real and directional** (near-zero effects draw ~11–12× the panel median weight) but **did not materialize as infinity** in this panel: no exact-zero effect occurs, and the only guard (D5, `se ≤ 0`) was never triggered.

### 2.4 Clipping and flooring
`Z_CLIP = 4.0` is applied to the *combined* z after weighting, never to `se` or to the weights. There is **no weight cap, no weight floor, and no `se` floor** anywhere in the path.

### 2.5 Concentration under the defective weights

| Measure | Value |
|---|---|
| cells | 7,514 |
| mean / median HHI | 0.2601 / 0.2347 |
| effective # models (1/HHI) | mean 3.84, median 4.26 |
| mean top-model weight share | 0.3436 |
| cells with top share > 0.90 | 0.9% |
| cells with top share > 0.99 | 0.3% |

## 3. Determination

The defect is **reproduced, active, and production-affecting**. Its primary signature is the −0.72 effect-magnitude inversion. Its secondary signature — unbounded weights as `effect → 0` — is present in direction and magnitude but bounded in this panel. Concentration is moderate, not degenerate.
