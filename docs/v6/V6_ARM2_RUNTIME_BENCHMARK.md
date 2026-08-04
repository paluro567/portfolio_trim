# V6 Arm 2 — Runtime Benchmark (R5, R6)

Hardware: darwin 25.5.0, Postgres.app 17, Python 3.13 (`uv` venv), single process, no parallelism.

## 1. Per-model cost — 147 evaluations (7 models × 7 symbols × 3 dates)

| Model | Total | Per (symbol, as_of) |
|---|---|---|
| `macro_regime` | 5.49 s | 0.2612 s |
| `interest_rate_sensitivity` | 3.97 s | 0.1890 s |
| `momentum_exhaustion` | 3.15 s | 0.1500 s |
| `relative_strength` | 2.03 s | 0.0967 s |
| `earnings_behavior` | 0.83 s | 0.0395 s |
| `sector_rotation` | 0.22 s | 0.0106 s |
| `valuation` | 0.12 s | 0.0058 s |
| **All 7** | **15.81 s** | **0.753 s** |

One `evaluate()` returns all **6 horizons**, so a "cell" is (symbol, as_of), not (symbol, as_of, horizon).

## 2. Full cell under the injection harness (R5 — one full cell, end to end)

Measured in situ, three passes of 90 cells:

| ρ | Wall clock | Per cell |
|---|---|---|
| 0.00 | 55.7 s | 0.618 s |
| 0.10 | 55.0 s | 0.611 s |
| 0.30 | 55.4 s | 0.616 s |

**Benchmark: 0.615 s per cell**, all 7 models × 6 horizons, including the hook. Cost is flat in ρ, as expected — injection adds an O(1) addition per read.

The harness is *faster* than the raw 0.753 s because the three fundamentals-starved models short-circuit on missing data. On a fully restored substrate this benchmark would rise; it is a **floor, not a ceiling**, and S5's 3× halt threshold should be set against a restored-substrate benchmark, not this one.

## 3. Sweep projection

Panel: **771 cells** (6 symbols × 131 dates).

| Component | Arithmetic | Cost |
|---|---|---|
| One ρ pass | 771 × 0.615 s | **7.9 min** |
| Main sweep, 6 ρ values | 6 × 7.9 min | **47.4 min** |
| Placebo arm, 200 seeds @ primary ρ | 200 × 7.9 min | **26.3 h** |
| **Total, serial** | | **≈ 27.1 h** |

The placebo arm is **97%** of the total. It cannot be avoided by reuse: the placebo permutes `y` within date, the injection is a function of `rank(y)`, so every seed changes the injected features and forces a full re-evaluation.

## 4. R6 verdict and batching plan

27.1 h serial exceeds a single working session but is **not** infeasible. The workload is embarrassingly parallel across symbols and seeds:

1. Shard the placebo arm by seed across **8 worker processes** → **≈ 3.3 h** wall clock.
2. Run the main sweep serially (47 min) — small enough not to warrant sharding.
3. Each worker gets its own DB session and its own `INJ` state; the hook is per-process, so no cross-talk.
4. Checkpoint per (seed, ρ) to disk so a halt under S5 loses at most one shard.

**Projected wall clock under the plan: ≈ 4 h. Within budget. R6 CLOSED.**

## 5. Cost is not the binding constraint

Compute was the prerequisite most expected to block Arm 2. It does not. At ~4 h parallel the experiment is affordable.

What blocks it is that the money would buy a **foreseeable VOID** (B-03). The benchmark's real contribution is establishing that the blockers are scientific, not economic — the sweep is cheap enough that no one should be tempted to argue readiness from cost.
