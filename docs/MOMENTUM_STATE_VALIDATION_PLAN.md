# Momentum Continuation vs Overextension (momentum_state_v1) — Plan and Verdict

Companion to `docs/CPE_VALIDATION_PLAN.md`, following the same convention: the
plan and the verdict are versioned here; the generated artifacts
(`prereg.json`, `results_ret*.json`, `REPORT.md`) live under the gitignored
`data/validation/momentum_state_v1/`.

## Status

**CLOSED, HYPOTHESIS UNSUPPORTED — 2026-08-18; inference corrected 2026-08-19.**
Research-only. Never promoted, never wired into `mip/product/`.

The pre-registered promotion gates were not met, so the hypothesis is unsupported
and the experiment is closed. It is *not* classified as evidence of harm: the
original significance claim rested on an invalid confidence interval (see
*Verdict*). In the repository's `LifecycleStatus` vocabulary the nearest state
remains `REJECTED` — meaning "not promoted, do not use" — but the scientific
reading is **failure to demonstrate improvement**, not demonstrated degradation.
momentum_state_v1 has no registry entry (the registry requires an
`IntelligenceModel` subclass and this study is a bucket test, not a model).

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

> **INFERENCE CORRECTION, 2026-08-19.** The confidence intervals below were
> produced by a bootstrap whose resampling unit did not match the dependence
> structure of the data (see *Dependence defect* immediately after this table).
> **They are not valid dependence-adjusted intervals and must not be used to
> support any significance claim.** The point estimates are unaffected. No
> replacement interval is quoted, because none has been computed by a
> dependence-aware procedure. The experiment remains closed and is not being
> retuned or rerun.

| Horizon | regime-only | momentum+regime | Δ (point estimate) | originally-reported CI — **INVALID** | gate |
|---|---|---|---|---|---|
| 1w | 0.5114 | 0.4930 | −0.0182 | ~~[−0.0202, −0.0161]~~ | not met |
| **1m** | 0.4869 | 0.4834 | **−0.0034** | ~~[−0.0048, −0.0020]~~ | **not met** |

What remains valid: the **point estimates** (sample means, unbiased regardless of
dependence) — momentum+regime did not score above regime-only at either horizon,
and every system scored at or below 0.50. Per-symbol median delta −0.0045 with
44.7% of 441 symbols positive (descriptive; no interval attached). Confidence
inverted at 1w. PIT clean: **0 leakage violations** over 1,658,463 observations,
plus a price-poisoning invariance test — structural checks unaffected by the
dependence defect.

What is **no longer claimed**: that conditioning *significantly degrades*
forecasting. The observed difference is negative, but its uncertainty was never
validly quantified, so the experiment cannot distinguish a small true
degradation from no effect at all.

The pre-registered promotion gate required a CI lower bound above zero. That gate
is **not met** — it cannot be met, since no valid interval exists. The hypothesis
is therefore **unsupported and not promoted**. This is not evidence that the
hypothesis is true.

### Dependence defect in the original bootstrap

`paired_delta_bootstrap` sorted the paired cohort by date into a flat array of
symbol-date rows, then resampled circular blocks of **4 consecutive rows**. The
1m holdout held **492,031 rows across 1,158 trading dates — about 425 rows per
date**, so a 4-row block spanned roughly **0.94% of a single trading date**. It
therefore preserved:

- **cross-sectional same-date dependence:** no. ~425 same-date rows share one
  market/macro realisation; a 4-row block captures 4 of them.
- **overlapping-outcome serial dependence:** no. The 1m label spans 21 sessions,
  so observations up to 20 dates apart share outcome windows; blocks under one
  date span none of that.

Both dominant dependence structures were absent from the resampling, so the
interval reflects little more than binomial noise on a pseudo-replicated sample.
The defect is in the *inference*, not in the data, the labels, the PIT handling
or the point estimates.

Ablation E (`ret_63d`) is the only positive incremental (+0.0139; its interval
came from the same defective bootstrap and is likewise **invalid**) and is
explicitly **not** promoted: it is a robustness
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

This is the third experiment on the same premise to fail its promotion gates
(the first two, analogue v1 and CPE v1, are separate rejections on their own
evidence). `historical_analogues`
v1 (REJECTED) found the market domain to be era persistence, and found **no
incremental benefit from company similarity** — its variant ablation carried only
~24 observations per variant with no interval, so the earlier wording ("company
domain harmful") overstated what that evidence supports.
`conditional_probability` v1 (REJECTED) found standalone accuracy
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
