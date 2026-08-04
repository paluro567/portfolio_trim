# V6 Arm 2 — Propagation Checkpoint Validation (Part 7)

**Scope: mechanism validation on a reduced slice. This is NOT the preregistered sweep. TRANSMISSION is not computed or reported.**

Slice: 90 cells, horizon 1m, ρ ∈ {0.00, 0.10, 0.30}. All figures use the tie-aware ranking (post-D-04 fix).

## A1 — feature-level injection lands

Frozen gate: `IC_F` CI lower > 0.05.

| ρ | IC_F(`ret_21d`) |
|---|---|
| 0.00 | +0.2267 |
| 0.10 (primary) | **+0.3043** |
| 0.30 | +0.4715 |

IC_F rises monotonically with ρ, and the increments track the injection: the hook does what the specification says. **A1 PASSES.** The feature carries the injected signal.

## A2 — activation-pattern shift in consuming models

Frozen gate: `ACTIVATION_SHIFT ≥ 0.02` **OR** `|SIGNAL_ALIGNMENT|` CI excludes zero.
Operationalised as mean |score(ρ) − score(0)| / 100 over the slice.

| Model | Frozen class | shift @ ρ=0.10 | cells changed | shift @ ρ=0.30 | cells changed |
|---|---|---|---|---|---|
| `momentum_exhaustion` | CONSUMER | **0.00415** | 8 / 90 | **0.00793** | 13 / 90 |
| `earnings_behavior` | CONSUMER | 0.00000 | 0 / 90 | 0.00000 | 0 / 90 |
| `macro_regime` | CONSUMER | 0.00000 | 0 / 90 | 0.00000 | 0 / 90 |
| `relative_strength` | CONSUMER | 0.00000 | 0 / 90 | 0.00000 | 0 / 90 |
| `sector_rotation` | CONSUMER | 0.00000 | 0 / 90 | 0.00000 | 0 / 90 |
| `valuation` | CONSUMER | 0.00000 | 0 / 90 | 0.00000 | 0 / 90 |
| `interest_rate_sensitivity` | NON-CONSUMER | 0.00000 | 0 / 90 | 0.00000 | 0 / 90 |

**A2 FAILS.**

- The best consuming model reaches **0.00415** at the primary ρ — **4.8× below** the 0.02 threshold.
- At ρ = 0.30, three times the primary and the largest value on the frozen grid, it reaches **0.00793** — still **2.5× below** threshold.
- The other five "consumers" are **byte-identical** under injection. Not attenuated: unchanged.

The `|SIGNAL_ALIGNMENT|` alternative cannot rescue A2. Five consumers have a strictly zero difference vector, so alignment is undefined for them; only `momentum_exhaustion` could be tested, and A2 would then rest on a single model — which is the B-02 problem again.

## Why the one true consumer barely moves

`momentum_exhaustion` consumes `ret_21d` through **percentile threshold crossings** — `ge("ret_21d", 0.7)`, `le("ret_21d", 0.2)`, `ge("ret_21d", 0.6)`, `le("ret_21d", 0.1)`, `ge("ret_21d", 0.8)`, `le("ret_21d", 0.4)`.

This is a **step function with a dead zone**. A perturbation changes the score only if it pushes the value across a threshold; otherwise it is absorbed entirely. At ρ = 0.10, only **8 of 90 cells** cross. The transmission path is not lossy — it is *quantised*, and a continuous injection is close to the worst possible probe for it.

## A3 — model-output IC

| Model | IC_M @ ρ=0.00 | @ ρ=0.10 | @ ρ=0.30 | sd(score) |
|---|---|---|---|---|
| `momentum_exhaustion` | −0.0045 | −0.0101 | −0.0248 | 28.05 |
| `relative_strength` | −0.1288 | −0.1288 | −0.1288 | 26.91 |
| `macro_regime` | +0.1132 | +0.1132 | +0.1132 | 25.01 |
| `interest_rate_sensitivity` | +0.0941 | +0.0941 | +0.0941 | 25.59 |
| `valuation` | **nan** | nan | nan | **0.0000** |
| `earnings_behavior` | **nan** | nan | nan | **0.0000** |
| `sector_rotation` | **nan** | nan | nan | **0.0000** |

Two independent failures:

1. **Three models have undefined IC** (constant output — B-04). `TRANSMISSION = IC_M / IC_F` is undefined for them at every ρ.
2. **The one responsive model moves the wrong way.** `momentum_exhaustion`'s IC becomes *more negative* as ρ increases (−0.0045 → −0.0101 → −0.0248) while IC_F rises. On this slice, injected signal enters that model with **inverted sign** — consistent with its thresholds being contrarian ("exhaustion": high recent return ⇒ bearish). TRANSMISSION would be negative, a case the frozen decision rule (PASS >0.75 / FAIL <0.50 / else INCONCLUSIVE) does not contemplate: a large-magnitude negative ratio would be silently recorded as FAIL.

## Verdict

**A1 PASSES. A2 FAILS. A3 is undefined for 3 of 7 models and sign-inverted for the only responsive one.**

The frozen decision rule states: **VOID if A1/A2 fail.**

Executing Arm 2 as preregistered on this substrate returns **VOID** — with high confidence, since A2 fails by 2.5× even at three times the primary ρ. Spending the sweep to obtain a foreseeable VOID is not justified. This is B-03.
