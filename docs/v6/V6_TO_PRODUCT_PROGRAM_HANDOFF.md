# V6 → Product Program Handoff

**Date:** 2026-08-04 · No new product features are designed here.

## What V6 contributes

**Retain:**

| Contribution | Why it survives |
|---|---|
| **Scientific evaluation framework** | Arm 1 established the measurement layer is unbiased and efficient. Cohort non-overlap, per-horizon embargo, circular block bootstrap, and the paired-comparison protocol are validated and reusable. |
| **Immutable archives** | `archive/original_pre_amendment/`, hashed manifest, amendment discipline that preserves superseded values in-file. |
| **Reliability discipline** | Preregistration, frozen endpoints, invariant gates before performance evaluation, and the rule that a negative result requires passing upstream checkpoints first. |
| **Causal-dependency methodology** | Amendment B's two-stage consumer definition (static trace + controlled perturbation) generalizes far beyond Arm 2. |
| **Abstention** | Neutral output when evidence is absent remains correct and is now better supported: the constant-50% forecaster outperformed every ensemble variant tested. |
| **Policy-based recommendations** | Decisions driven by declared policy rather than predicted direction. |
| **Descriptive evidence with earned influence** | The reliability-tier discipline (SHADOW → CONTEXT → ADVISORY → DIRECTIONAL) with influence earned by demonstrated reliability. |
| **Explicit reporting of absent directional reliability** | The platform must state plainly where directional reliability has not been established. After V6 that is **everywhere** in the directional ensemble. |

**Exclude from the product decision path:**

| Excluded | Reason |
|---|---|
| The predictive ensemble as a directional signal | Loses to a constant-50% forecaster at all six horizons |
| Predictive confidence | `combined_confidence` has no demonstrated directional validity |
| Composite probability claims | `p_up = evidence_score/100` is worse than uninformed |
| Retired Arm 2 work | Permanently retired |
| Any implication that predictive edge was established | **None was.** V6 tested plumbing, not skill. |

## Three distinct tracks — do not conflate

1. **Phase 1 product validation** — sham-controlled decision-change study, 23 hashed artifacts, Amendments 001/002 awaiting signature. **Unaffected by V6.** It tests whether the reports change decisions, not whether they predict returns.
2. **V5 descriptive-reliability research** — descriptive evidence with earned influence. **Unaffected by V6**, and now the only research track with a live scientific question.
3. **Retired directional ensemble research** — V6. **Closed.**

## What resumes next
**Phase 1 product validation.** It is already approved, already specified, does not depend on predictive skill, and is blocked only on human signature of Amendments 001 and 002.

## One item requiring product-side attention
The correctness patch changes emitted combined scores enough to **flip at least one recommendation label** (surfaced by `test_diff_against_previous`). This is a legitimate consequence of removing inverted weights, but it must be reviewed before any release that includes it.
