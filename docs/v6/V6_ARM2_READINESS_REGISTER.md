# V6 Arm 2 — Readiness Register (R1–R12)

**Role:** V6 Arm 2 Readiness and Restoration Lead
**Date:** 2026-08-01
**Governing document:** `docs/v6/V6_ARM2_PREREGISTRATION.md` (frozen — not modified by this work)
**Authority exercised:** restoration, measurement, verification. **No** experimental design was changed.

## Status key

| Code | Meaning |
|---|---|
| CLOSED | Prerequisite satisfied, evidence recorded |
| CLOSED* | Satisfied mechanically, but the result invalidates a downstream assumption |
| BLOCKED | Cannot be satisfied without an amendment from the Preregistration Committee |
| NOT REACHED | Gated behind an upstream BLOCKED item |

## Register

| # | Prerequisite | Status | Evidence |
|---|---|---|---|
| R1 | Data restoration — prices, macro, feature store | **CLOSED** | 86 tables; 38,086 price rows; 25,910 macro obs; 955,157 feature values. `V6_ARM2_DATA_RESTORATION_REPORT.md` |
| R2 | Repository state — clean tree, commit recorded | **BLOCKED** | 56 uncommitted paths at HEAD `1b2aec9f`. Tree not clean; R8/R9 hashing cannot bind |
| R3 | Recovered artifacts documented, recorded class B | **CLOSED** | Panel manifest recorded; explicitly class B (approximate). `V6_ARM2_DATA_RESTORATION_REPORT.md` §4 |
| R4 | Feature selection executed; consumer/non-consumer sets written | **CLOSED\*** | Rule executed verbatim → `ret_21d`. Sets derived. **The rule's consumer metric is invalid** — see B-01. `V6_ARM2_FEATURE_SELECTION.md`, `V6_ARM2_CONSUMER_MAP.md` |
| R5 | Runtime benchmark — one full cell timed end to end | **CLOSED** | 0.615 s per (symbol, as_of) across all 7 models × 6 horizons. `V6_ARM2_RUNTIME_BENCHMARK.md` |
| R6 | Compute within budget; batching plan if not | **CLOSED** | Main sweep 47 min; placebo arm 26.3 h serial. Batching plan recorded |
| R7 | Determinism — two runs, different PYTHONHASHSEED, byte-identical | **NOT REACHED** | Gated behind R2 and B-01/B-03 |
| R8 | Version control — prereg + Addendum A committed and hashed | **BLOCKED** | Gated behind R2 |
| R9 | SHA-256 of document set, model source, feature snapshot, manifest | **NOT REACHED** | Gated behind R2/R8 |
| R10 | Random seeds — SEED_BASE = 20260801, ≥200 placebo seeds | **CLOSED** | SEED_BASE applied; ≥200 placebo seeds confirmed affordable under the batching plan |
| R11 | Placebo arm implemented — within-date permutation of y | **NOT REACHED** | Implementable, but pointless while A2 fails (B-03) |
| R12 | Outcome write-protection — `spy_rel` read-only | **CLOSED** | Injection hook writes only to the feature read path; outcomes recomputed from `daily_prices` and never written. `V6_ARM2_INJECTION_IMPLEMENTATION.md` §5 |

**Closed: 6. Blocked: 3. Not reached: 3.**

## Blocking defects raised by this work

| ID | Severity | Statement |
|---|---|---|
| **B-01** | **CRITICAL** | The frozen Part 2.1 consumer metric counts *occurrences of the feature name in model source*. For `ret_21d`, 5 of the 6 counted consumers never read the feature's **value** — they read `series.index[-1]` (a date) inside an identical copy-pasted helper `_latest_feature_date()`. The rule ranked a code-duplication artifact. |
| **B-02** | **CRITICAL** | The rule selects *maximum* consumer count, which by construction *minimises* the non-consumer control arm. The control arm for `ret_21d` is a single model (`interest_rate_sensitivity`). The preregistered pooling rule cannot operate on n=1. |
| **B-03** | **CRITICAL** | Measured propagation checkpoint **A2 fails at every ρ on the grid.** Max activation shift = 0.00793 at ρ=0.30; 0.00415 at the primary ρ=0.10; threshold is 0.02. Under the frozen decision rule (*VOID if A1/A2 fail*), Arm 2 run today returns **VOID**. |
| **B-04** | **MAJOR** | 3 of the 7 official models (`valuation`, `earnings_behavior`, `sector_rotation`) emit **constant** output on the restored panel (sd = 0.0000). IC is undefined for them; they cannot enter any IC-ratio endpoint. |
| **B-05** | **MAJOR** | Fundamentals and earnings history are **not point-in-time restorable**. The ingestion path snapshots current values forward; it cannot reconstruct history. Per the standing instruction, no substitution was made. |
| **D-04** | **MAJOR** | Defect in the analysis harness (mine): `argsort`-based ranking assigns *distinct* ranks to a constant array, yielding spurious non-zero IC. Fixed here. **The same tie-unaware ranking exists in `v6_arm1.py` and Arm 1.5's `a15_run.py`** and requires verification. |

## Decision

**READINESS: NOT GRANTED.** See `V6_ARM2_READINESS_DECISION.md`.


> **[AMENDED A-2026-005, 2026-08-04]** The tie-mechanism statement above is superseded. Measurement shows the **dominant** tie value is **50.0, the neutral score** (1w 5, 2w 5, 1m 2, 3m 2, 6m 2, 1y 2 cells). A second 2-member group at 1y sits at score ~0.00317, consistent with a `Z_CLIP` floor, so clipping is a **minor secondary contributor, not the mechanism**. Corrected statement: *the neutral score is the dominant tie mechanism; clipping contributes once, at 1y.*
