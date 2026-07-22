# Validation Gates for Evidence Models

Every evidence model — new or revised — must pass ALL gates below on an
out-of-sample walk-forward evaluation before it may influence production
Trim Scores. These gates are enforceable requirements; a model that
cannot produce the required artifacts has not been validated.

Reference implementation: `mip/validation/` (walk-forward capture,
system reconstruction, metrics, leakage diagnostics) and
`mip/validation/eligibility.py` (the label-observability rule).

## G1 — Point-in-time feature correctness
Every feature value consumed at scoring date T must have been computable
from data available on T (publication lags respected). Enforced by the
Feature Store's availability gates; new feature families must extend the
existing PIT tests.

## G2 — Observable-label enforcement (per-horizon embargo)
Every historical outcome used at scoring date T and horizon H must
satisfy `position(t) + H <= position(T)` on the instrument's traded
calendar (end-on-T allowed: the platform scores after T's close, which
is a model input). Implemented once in
`mip.validation.eligibility.label_observable`; never duplicated.
`min_gap`-style near-duplicate suppression is not a substitute.

## G3 — Zero leakage diagnostics
The walk-forward run must emit observability diagnostics (used /
observable / embargoed / unavailable per horizon, per symbol, per
scoring date) and the aggregate report must show **violations_total ==
0**. The harness fails loudly (strict assertion) on any violation — no
silent discarding after execution begins.

## G4 — Price-poisoning invariance
Evaluating the model at historical as_of=T must be invariant to
arbitrary corruption of all post-T prices (see
`tests/integration/test_pit_alignment.py`). This is THE end-to-end
proof that `evaluate(as_of=T)` equals live inference on T.

## G5 — Deterministic reproduction
Identical frozen inputs must reproduce byte-identical machine-readable
outputs; candidate ordering, calendar lookups, and database queries must
have deterministic ordering; any randomness requires an explicit seed.

## G6 — Baseline comparison and incremental contribution
Report the candidate system against the current production baseline on
identical PIT data: directional accuracy, Brier, rank correlation, and
signed prediction-realized correlation, per horizon, on BOTH all scoring
dates and non-overlapping cohorts, with block-bootstrap uncertainty
(never independence-assuming intervals).

## G7 — Calibration analysis
Empirical confidence-to-accuracy mapping (calibration table). A model
whose confidence does not discriminate accuracy (see the analogue v1
finding) fails this gate regardless of headline accuracy.

## G8 — Sample-size and uncertainty disclosure
Every reported cell carries n (and effective sample size where serial
correlation applies). Cells below minimum sample sizes are reported as
statistically unresolved, never as evidence.

## G9 — Performance by symbol and period
Per-holding and calibration/holdout-period tables. Aggregate benefit
must not conceal per-symbol degradation; selection of any configuration
on the holdout period is prohibited.

## G10 — Era/regime-blocked analysis where appropriate
When a signal may be regime persistence in disguise (identical inputs
across symbols, slow-moving features), report era-blocked results and an
effective sample size that accounts for cross-symbol duplication.

## Promotion discipline
Promotion criteria must be declared BEFORE the evaluation runs (see the
analogue v1 validation's pre-declared criteria). Tuning on the final
test period invalidates the run. The default disposition for a model
that fails any gate is shadow mode or rejection — never partial credit.
