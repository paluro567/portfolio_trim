# Momentum Continuation vs Overextension (momentum_state_v1) — Plan and Verdict

Companion to `docs/CPE_VALIDATION_PLAN.md`, following the same convention: the
plan and the verdict are versioned here; the generated artifacts
(`prereg.json`, `results_ret*.json`, `REPORT.md`) live under the gitignored
`data/validation/momentum_state_v1/`.

## Status

**REJECTED — 2026-08-18.** Research-only. Never promoted, never wired into
`mip/product/`.

## Pre-registration

Frozen `2026-08-18T15:22:49Z` via `mip.research.experiments.prereg.PreRegistration`.
**Content hash `0544388a1412ae0be8a40d125b216b1f9ba010a33d57d2fecd9e3d0ce7ab632a`**,
verified by the runner before each execution. Nothing was changed after results
were seen.

- **Hypothesis.** Extreme positive momentum may either continue or mean-revert.
  Conditioning on simple pre-existing market state improves the ability to
  distinguish continuation from overextension relative to unconditional and
  momentum-only baselines.
- **Null.** Momentum bucket conditioned on market regime adds no forward
  excess-return information beyond regime-only; incremental CI includes 0 at 1m.
- **Primary metric.** Directional accuracy of sign(forward 21-session excess
  return vs SPY). **Primary horizon 1m**; 1w secondary. 3m/6m/1y out of scope.
- **State.** PIT expanding percentile of `ret_21d` in the symbol's own history
  (≥252 prior obs), bucketed 0-20/20-40/40-60/60-80/80-90/90-95/95-99/99-100,
  crossed with `regime_bull` × `regime_high_vol`. Both regime features are
  pre-existing and versioned (SPY>200MA; VIX>25) — no threshold was invented.
- **Split.** design ≤ 2021-12-31 (outcome window closed before boundary),
  holdout ≥ 2022-01-01; straddling observations dropped as the embargo.
- **Universe.** 443 instruments, first price ≤ 2013-01-01 and ≥ 2520 sessions.
- **Bootstrap.** Circular block, block=4, draws=1000, seed=7, paired cells.

## Verdict

| Horizon | regime-only | momentum+regime | Δ | 95% CI | gate |
|---|---|---|---|---|---|
| 1w | 0.5114 | 0.4930 | −0.0182 | [−0.0202, −0.0161] | fail |
| **1m** | 0.4869 | 0.4834 | **−0.0034** | **[−0.0048, −0.0020]** | **FAIL** |

The incremental CI lies entirely **below** zero: conditioning momentum on market
regime measurably *degrades* forward excess-return direction. Per-symbol median
delta −0.0045 with only 44.7% of 441 symbols positive. Confidence inverted at 1w.
PIT clean: **0 leakage violations** over 1,658,463 observations, plus a
price-poisoning invariance test.

Ablation E (`ret_63d`) is the only positive incremental (+0.0139, CI
[+0.0124, +0.0154]) and is explicitly **not** promoted: it is a robustness
ablation rather than the primary, its accuracy is 0.5007, and its confidence is
severely inverted (0.5005 high vs 0.6342 low), an independent pre-registered
disqualifier. Acting on it would be the specification search the freeze prevents.

## Known defect in this experiment

The ≥30-independent-episode floor is **unsatisfiable on a pooled panel**:
`calendar_episodes` was designed for a sparse analogue match set, and with 443
symbols trading daily the whole holdout collapses to ≤16 episodes, so 0/32 cells
qualified at either horizon. All bucket-level CONTINUATION/OVEREXTENSION labels
are therefore INCONCLUSIVE and carry no evidential weight. The primary test is
unaffected — it uses a date-ordered block bootstrap and never counts episodes. A
successor must count episodes per symbol and pool, or drop episode counting in
favour of a date-clustered bootstrap.

## Relationship to prior work

This is the third independent negative on the same premise. `historical_analogues`
v1 (REJECTED) found the company domain harmful and the market domain to be era
persistence. `conditional_probability` v1 (REJECTED) found standalone accuracy
falling monotonically as conditioning domains were added (0.641 market-only →
0.545 market+sector+company). This study reproduces that direction with a
deliberately low-dimensional, fully interpretable specification on the deepest
PIT-safe data available.

## Implementation provenance and the two performance rewrites

Recorded because an earlier version of this commit message described the
rewrites as output-preserving. **That description was wrong**, and the accurate
account is:

- **Expanding percentile.** The first draft used an ordered insert with
  ``bisect_right``, which counts values **<= x**. It was replaced by a Fenwick
  tree counting values **strictly < x** (O(n^2) -> O(n log n); the naive form
  does not finish on a 443-symbol universe). **The two disagree on exact ties** —
  0.59% of real ``ret_21d`` values overall (10,709 of 1,821,786), but heavily
  concentrated in symbols with long flat-price stretches (FLUT 54%, SW 45%,
  FERG 40%, AMCR 34%).
- **Bootstrap.** ``random.Random(seed)`` was replaced by
  ``numpy.random.default_rng(seed)`` and the block loop vectorised. Same
  procedure and same parameters (circular block, block=4, draws=1000, seed=7),
  but a different RNG stream, so the draws are **not** bit-identical either.

**Neither abandoned draft produced an authoritative result.** Both of their runs
were killed before writing output (exit 144). Every artifact under
``data/validation/momentum_state_v1/`` was generated by the final implementation
in this commit, which is also what the docstrings describe and what the tests
assert. Code, tests, docstrings and artifacts are mutually consistent.

**The verdict is therefore the verdict of the pre-registered study as actually
executed** — the hypothesis, gates, thresholds, sample, PIT rules and acceptance
criteria are untouched, and nothing was re-interpreted. What was corrected is a
claim about the optimisation, not a result.

Strictly-below tie semantics are now pinned by three tests in
``tests/unit/test_momentum_state.py`` so the ambiguity cannot recur.

## Reuse

`src/mip/research/momentum_state.py` (study), `tools/run_momentum_state_study.py`
(runner), `tests/unit/test_momentum_state.py` (PIT and design guarantees). Built
on `mip.research.outcomes` and the embargo semantics of
`mip.validation.eligibility`. No new schema, no new validation framework.
