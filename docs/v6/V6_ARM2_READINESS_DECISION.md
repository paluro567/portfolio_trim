# V6 Arm 2 — Readiness Decision

**Decision: READINESS NOT GRANTED. Arm 2 must not be executed on this substrate under the current preregistration.**

The decision is mechanical: the preregistration states **VOID if A1/A2 fail**, and A2 was measured to fail at every ρ on the frozen grid, including 3× the primary. Executing the sweep would purchase a VOID that is already known.

## What was closed

R1, R3, R5, R6, R10, R12 — six of twelve. The database was rebuilt from 1 to 86 tables and the full price, macro and feature surface restored in **66 seconds** against a 4–6 hour estimate. Compute, the prerequisite most expected to bind, does not: the sweep costs ≈4 h under an 8-way batching plan.

## Why readiness fails

**B-03 is decisive and sufficient.** A2 requires activation shift ≥ 0.02. Measured: **0.00415** at primary ρ = 0.10 and **0.00793** at ρ = 0.30. Five of six designated consumers were **byte-identical** under injection.

**B-01 explains it.** The frozen consumer metric counts occurrences of the feature name in model source. Five of `ret_21d`'s six "consumers" reference it only inside an identical copy-pasted helper that reads `series.index[-1]` — a **date**. `ret_21d` is the platform's data-availability clock, and it won the selection because that boilerplate is duplicated across five models. The rule ranked code duplication.

**B-02 is structural.** The rule maximises consumer count, which over a fixed 7-model population identically *minimises* the control arm. The rule that picks the feature is the rule that guarantees the weakest control. Control n = 1.

Measurement inverts the design: **1 treated model, 3 usable controls** — the opposite of the many-treated/few-control structure Arm 2 assumes.

## What I did not do

I did not redesign the experiment, alter the selection rule, thresholds, checkpoints or pooling rule, run the sweep, substitute reconstructed data for lost point-in-time data, sign anything, or commit the repository.

---

# Conclusion — 14 points

1. **Readiness is NOT granted.** Six of twelve prerequisites closed; three blocked; three not reached.

2. **Restoration succeeded and was cheap.** 86 tables, 38,086 price rows, 25,910 macro observations, 955,157 feature values — **66 seconds** total against a 4–6 hour estimate.

3. **The restored panel is class B (approximate).** A new study substrate, never a reproduction. Adjusted closes carry today's corporate-action history; the 10-symbol universe is survivorship-shaped. Arm 1 / Arm 1.5 results are not comparable to anything computed on it.

4. **Fundamentals and earnings are not PIT-restorable.** The ingestion path snapshots current values forward. Backfilling would write today's restated figures onto historical dates. **No substitution was made**; 19 features remain at zero coverage.

5. **The frozen selection rule was executed verbatim and selected `ret_21d`** — 6 consumers, unique maximum; the coverage and lexicographic tie-breaks never fired. The selection is robust to scan scope.

6. **The rule measures the wrong quantity (B-01).** It counts name mentions, not value reads. Five of six consumers reference `ret_21d` only inside `_latest_feature_date()`, reading a **date**. The feature won because it is the platform's data-availability clock, duplicated across five models.

7. **The partition IS provably exhaustive and mutually exclusive** — union 7, intersection ∅. The named stop condition is **satisfied**; it is not what blocks this experiment.

8. **The control arm is degenerate (B-02).** Maximising consumers identically minimises controls. Control n = 1 (`interest_rate_sensitivity`, verified clean including its dynamically built feature names). The preregistered pooling rule cannot operate.

9. **A1 passes.** IC_F rises monotonically with ρ: +0.2267 → +0.3043 → +0.4715. The injection hook does what the specification says.

10. **A2 fails at every ρ (B-03).** Best consuming model: 0.00415 at primary ρ (4.8× below the 0.02 threshold), 0.00793 at ρ = 0.30 (2.5× below). Cause: `momentum_exhaustion` consumes `ret_21d` through **percentile thresholds** — a step function with a dead zone that absorbs continuous perturbation. Only 8 of 90 cells cross at primary ρ.

11. **A3 is unusable.** Three of seven models emit **constant** output (sd = 0.0000) — IC undefined (B-04). The one responsive model's IC moves *more negative* as ρ rises while IC_F rises: transmission enters with **inverted sign**, a case the PASS/FAIL/INCONCLUSIVE rule does not contemplate and would silently record as FAIL.

12. **Compute is not the constraint.** 0.615 s per cell; main sweep 47 min; placebo arm 26.3 h serial, ≈3.3 h at 8-way parallelism. Affordable. The blockers are scientific, and no one should argue readiness from cost.

13. **I found a defect in my own analysis code and it reaches earlier arms (D-04).** `argsort(argsort(...))` assigns distinct ranks to constant arrays, producing spurious IC — it reported `IC_M = +0.2262` for three models whose output never varied. Fixed to average-rank tie handling. **The same ranking is in `v6_arm1.py` and Arm 1.5's `a15_run.py`**, where `Z_CLIP` produces genuine ties; those results are order-sensitive and should be re-verified. Every number in these eleven documents is post-fix.

14. **The minimum to unblock, for the Preregistration Committee — not for me.** Replace the static consumer metric with a **measured** one (inject at ρ = 0.30 and classify by whether output changes); re-select on a rule that guarantees a control arm of usable size rather than minimising it; probe threshold-consuming models with a perturbation matched to their quantised transmission path; and restore or formally abandon the three dark models. **Do not raise ρ to force A2 to pass** — that changes the question from "does signal transmit" to "how much signal does it take to cross a threshold."

---

**Addendum A is drafted, unsigned and unhashed.** R2 and R8 remain blocked on a dirty working tree (56 uncommitted paths at HEAD `1b2aec9f`), and no commit was made because none was requested.


> **[AMENDED A-2026-005, 2026-08-04]** The tie-mechanism statement above is superseded. Measurement shows the **dominant** tie value is **50.0, the neutral score** (1w 5, 2w 5, 1m 2, 3m 2, 6m 2, 1y 2 cells). A second 2-member group at 1y sits at score ~0.00317, consistent with a `Z_CLIP` floor, so clipping is a **minor secondary contributor, not the mechanism**. Corrected statement: *the neutral score is the dominant tie mechanism; clipping contributes once, at 1y.*
