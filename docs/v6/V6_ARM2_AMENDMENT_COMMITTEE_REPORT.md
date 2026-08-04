# V6 Arm 2 Preregistration Amendment Committee — Report

**Date:** 2026-08-02 · **Companion:** `V6_ARM2_PREREGISTRATION_AMENDMENT_B.md`

---

## PART 1 — Canonical record status: **NOT APPLIED**

Amendments A-2026-001 … 005 exist as documents but have **not** been applied to any artifact. Evidence:

| Amendment | Expected if applied | Actual artifact state | Applied? |
|---|---|---|---|
| A-2026-001 | `1y` `mde_90` = *not achieved* | `1y,47,0.1007,0.095,0.4,**0.4**,...` | **NO** |
| A-2026-002 | `n_seeds` = 200 throughout | column contains `200` **and** `300` | **NO** |
| A-2026-003 | `3m` `mde_80` = 0.20 | `3m,180,0.0689,0.02,**0.25**,0.25,...` | **NO** |
| A-2026-004 | 1y ρ=0.10 loss = 0.033922 | `1y,0.1,45,...,**0.03372859025032937**,...` | **NO** |
| A-2026-005 | clip-boundary language corrected | `Z_CLIP` claim still present in 2 documents | **NO** |

Versioned: **NO** · Signed: **NO** · Hashed: **NO** · In manifest: **NO** (no `MANIFEST*` or `*.sha256` exists). Only the amendment documents themselves reference the amendment IDs.

### Application and freeze checklist

| # | Step | Gate |
|---|---|---|
| C1 | Append amendment block to `V6_ARM1_RESULTS.md`, `V6_ARM15_RESULTS.md` — never edit published values in place | original preserved verbatim |
| C2 | Publish corrected CSVs as **new files** (`*_v1.1.csv`); retain originals unmodified | both versions readable |
| C3 | Add `AMENDED-BY: A-2026-00n` header to each affected artifact | every affected artifact carries a pointer |
| C4 | Correct `n_seeds` → 200 in `V6_ARM1_POWER_TABLE_v1.1.csv` | A-2026-002 |
| C5 | Add provenance block (script, seeds, bootstrap draws, seed stream) to recovery-curve and scaling artifacts | A-2026-003 |
| C6 | Correct clip-boundary language in the 4 documents named in A-2026-005 | A-2026-005 |
| C7 | Commit the working tree (56 uncommitted paths at HEAD `1b2aec9f`) | **required before C8** |
| C8 | SHA-256 every artifact; write `MANIFEST.sha256` | binds the record |
| C9 | Human signature on the amendment register | may not be auto-filled |

**This is a record-integrity prerequisite, not an Arm 2 scientific blocker.** C7 requires an explicit instruction to commit, which has not been given.

---

## PART 2 — The three blockers, restated

### B-01 — syntactic reference treated as value consumption

*Preregistered assumption:* the count of occurrences of a feature name in `src/mip/models/*.py` measures how many models consume that feature.
*Measured contradiction:* 5 of `ret_21d`'s 6 counted consumers reference it only inside a byte-identical copy-pasted helper `_latest_feature_date()`, which reads `series.index[-1]` — a **date**. Under a ρ=0.30 injection those 5 models were **byte-identical**.
*Why it cannot proceed:* the treatment arm was populated by code duplication. `ret_21d` won the selection because it is the platform's data-availability clock.
*Minimum property a valid amendment must restore:* consumption must be established **causally** — by changing the value and observing a response — never syntactically.

### B-02 — selection rule collapsed the control arm

*Preregistered assumption:* selecting the maximum-consumer-count feature strengthens the experiment.
*Measured contradiction:* over a fixed 7-model population, maximising the treatment arm **identically minimises** the control arm. `ret_21d` gave 6 / 1.
*Why it cannot proceed:* with one control there is no pooling, no between-model variance, and no way to separate one model's idiosyncrasy from systematic leakage.
*Minimum property:* the rule must impose an explicit floor on **both** arms, not maximise one.

### B-03 — A2 failed at every tested injection level

*Preregistered assumption:* `ACTIVATION_SHIFT ≥ 0.02` detects propagation into consuming models.
*Measured contradiction:* max shift **0.00415** at primary ρ=0.10 and **0.00793** at ρ=0.30 — 4.8× and 2.5× below threshold. Only `momentum_exhaustion` moved at all (8/90 and 13/90 cells).
*Why it cannot proceed:* the frozen rule returns **VOID** when A2 fails, so the sweep buys a known outcome.
*Minimum property:* A2 must detect **causal arrival at the decision logic**, which for a threshold consumer occurs continuously even when the output does not change. Measuring arrival by output change conflates A2 with A3.

**None of these findings is softened. All three are confirmed.**

---

## PART 10 — Pre-amendment feasibility check

### Commands executed

| # | Command | Result |
|---|---|---|
| 1 | artifact grep of 5 amendment targets | all 5 **unapplied** (Part 1) |
| 2 | inspect `ScoreDiagnostics` (`src/mip/models/base.py:199`) | exposes `active_regimes`, `z_raw`, `z_clipped`, `saturated` → viable A2 observables |
| 3 | `consumer_census.py` — 23 candidate features × ±2σ × 20 cells (671 s) | 4 LIVE / 3 DEAD models; **max 1 genuine live consumer** |
| 4 | `deep_probe.py` — 4 candidates × {±2, ±4, ±8}σ × 150 cells (2424 s) | **max 1 genuine live consumer** confirmed |

### Model liveness (measured)

**LIVE (4):** `interest_rate_sensitivity`, `macro_regime`, `momentum_exhaustion`, `relative_strength`
**DEAD (3, constant output):** `earnings_behavior`, `sector_rotation`, `valuation` — fundamentals, earnings and sector-ETF features absent and **not PIT-restorable**

### Stage-2 causal-response census — 23 candidates, ±2σ, 20 cells

| Genuine live consumers | Features |
|---|---|
| **1** (14) | `atr14_pct`, `dist_52w_high`, `ma50_ma200_spread_chg_21d`, `price_to_ma200`, `price_to_ma50`, `ret_126d`, `ret_21d`, `ret_63d`, `vol_21d`, `vol_ratio_21_63` → `momentum_exhaustion`; `rel_ret_spy_5d/21d/63d/126d`, `rel_ret_spy_accel_21d` → `relative_strength` |
| **0** (9) | `dist_52w_low`, `gap_1d`, `log_ret_1d`, `ma50_ma200_spread`, `ret_1d`, `ret_252d`, `ret_5d`, `vol_63d` |
| **≥ 2** | **none** |

### Deep probe — defeating dead-zone false negatives (150 cells, up to ±8σ)

| Feature | Genuine live consumers | Responding cells |
|---|---|---|
| `ret_63d` | 1 — `momentum_exhaustion` | 148 / 150 (98.7%) |
| `dist_52w_high` | 1 — `momentum_exhaustion` | 140 / 150 (93.3%) |
| `rel_ret_spy_63d` | 1 — `relative_strength` | 148 / 150 (98.7%) |
| `vol_21d` | 1 — `momentum_exhaustion` | 17 / 150 (11.3%) |

`rel_ret_spy_63d` was the **only** candidate whose static references include both live non-macro models. At ±8σ across 150 cells, `momentum_exhaustion` did **not** respond. Its static reference is not a value dependency.

### Structural cause — why 1 is the ceiling

- 3 of 7 models are DEAD and can be neither consumer nor control.
- Of the 4 LIVE models, `macro_regime` and `interest_rate_sensitivity` consume **only market-scope macro features** and never read instrument-scope price features.
- The remaining two have **disjoint** dependency sets: `momentum_exhaustion` reads absolute price / momentum / volatility features; `relative_strength` reads `rel_ret_spy_*`.

**Therefore the maximum genuine live consumer count for any instrument-scope price-derived feature is exactly 1. E1 (≥ 2) is not merely unmet — it is structurally unreachable on this substrate.**

### Feasibility determinations

| Question | Answer | Evidence |
|---|---|---|
| At least one eligible feature exists? | **NO** | E1 fails for all 23 candidates |
| Valid consumer set exists? | **NO** | max 1; ≥2 required |
| Valid control design exists? | **YES** | 3 live controls available whenever there is 1 consumer; E2 satisfiable |
| A2 measurable inside the real model path? | **Measurable in principle, NOT implemented** | `momentum_exhaustion` responds in 148/150 cells for `ret_63d`, so percentile-state movement would fire; the tap (R17) is unwritten |
| Adequate samples exist? | **YES** | 771-cell injection panel; probe activation 93–99% for three candidates |
| Runtime within the frozen ceiling? | **YES** | 0.63 s/cell measured, consistent with the frozen 0.615 s/cell benchmark |

**Verdict under §5.3: NO ELIGIBLE FEATURE — ARM 2 BLOCKED.**

The Committee records explicitly that it **did not** lower E1 to 1 to produce a selection. With a single consumer, TRANSMISSION has no between-model variance and no pooling — the mirror image of B-02, and the defect this amendment exists to remove.

---

## PART 12 — Addendum A disposition: **WITHDRAWN**

The existing unsigned Addendum A records the `ret_21d` partition (6 consumers / 1 non-consumer) that measurement has falsified: 5 of the 6 are not consumers. It **may not be signed**.

- **Withdrawn**, not revised — its central content is the invalid partition.
- **No replacement is drafted.** Amendment B §5.3 yields NO ELIGIBLE FEATURE, so there is no feature, no consumer set, and no control set to record. Drafting a replacement would require inventing content the evidence does not support.
- The withdrawn document is **retained in the archive** marked `WITHDRAWN 2026-08-02 — supersedes nothing; contains a partition falsified by Stage-2 causal-response testing.`

---

## PART 13 — Final authorization decision

1. **Canonical audit amendments applied and frozen: NO** — all five unapplied; no versioning, signatures, hashes, or manifest.
2. **B-01 resolved: YES** — Amendment B §4 replaces syntactic matching with a two-stage causal definition, validated by measurement.
3. **B-02 resolved: YES** — §5.1 imposes explicit floors on both arms (E1 ≥ 2 consumers, E2 ≥ 2 controls); §6 makes a model-level control a hard requirement.
4. **B-03 resolved: YES** — §7 redefines A2 on percentile-state movement inside the real model path, separating arrival from emission.
5. **Eligible feature exists: NO** — E1 fails for all 23 candidates at up to ±8σ across 150 cells.
6. **Genuine consumer set verified: NO** — the verification method executed correctly and returned a maximum of 1 genuine live consumer; no feature yields a valid (≥2) set.
7. **Valid control design verified: YES** — 3 live genuine non-consumers available; E2 satisfiable.
8. **A1 implementation valid: YES** — IC_F rose monotonically +0.2267 → +0.3043 → +0.4715 with ρ.
9. **Revised A2 implementation valid: NO** — specified in §7, but the condition-evaluation tap is unimplemented (R17 open).
10. **A3 implementation valid: YES** — `ModelScore.score` via the existing injection hook.
11. **Primary endpoint retained: YES** — `TRANSMISSION = IC_M / IC_F`, thresholds unchanged; denominator floor and sign handling specified for previously undefined regions.
12. **Original Addendum A disposition: WITHDRAWN** — contains the falsified `ret_21d` partition; no replacement drafted, as no eligible feature exists.
13. **Amendment B ready for signature and hashing: NO** — requires a clean tree (C7) and R17.
14. **Arm 2 readiness requirements passed: 6 / 12** — CLOSED: R1, R3, R5, R6, R10, R12. BLOCKED: R2, R4, R8. NOT REACHED: R7, R9, R11.
15. **Arm 2 authorized to execute: NO.**
16. **Exact remaining blocker — B-06:**

> **No feature on the restored substrate has ≥ 2 genuine live consuming models, and none can.** Only 4 of 7 official models are LIVE; 2 of those consume exclusively market-scope macro features; the remaining 2 have disjoint instrument-feature dependencies. The maximum achievable genuine consumer count is **1**. Arm 2 as designed measures transmission *across* consuming models, which requires at least two. The binding constraint is the **model population**, not the feature, the injection, the checkpoint, or the endpoint — all of which Amendment B repairs.

**Arm 2 is not executed.**
