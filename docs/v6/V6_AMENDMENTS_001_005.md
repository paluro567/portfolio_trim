# V6 Research Program — Formal Amendments 001–005

**Issuing body:** Independent Research Integrity Board · **Effective date:** 2026-08-02
**Governing record:** `V6_CANONICAL_AUDIT_RECORD.md`

**Preservation rule.** The original published record is preserved verbatim. No published value is overwritten. Each amendment states the original value, the corrected value, and the reason. Superseded values remain readable in the version history of each amendment and in the original artifacts, which are **not** to be edited in place — corrections are applied by appending an amendment block to each artifact's companion document and by publishing corrected values here.

---

# AMENDMENT A-2026-001
## Arm 1 — 1y MDE₉₀ correction

**Effective date:** 2026-08-02 · **Type:** Scientific record / numerical · **Conclusion changes:** No

### Background
Arm 1 measured the validation layer's minimum detectable effect by injecting a known cross-sectional IC into the score stream and recording the fraction of seeds whose block-bootstrap confidence interval excluded zero. MDE₉₀ is defined as the smallest target IC achieving recovery ≥ 0.90. The published value at the 1y horizon is 0.40.

### Reason
The reproducibility audit re-executed Arm 1 under corrected average-rank tie handling with identical seeds and identical bootstrap resample indices. At 1y, target IC 0.40, recovery under the original ranking was exactly **180/200 = 0.900** — precisely on the ≥0.90 threshold. Under corrected ranking one seed's bootstrap lower bound crossed zero, giving **179/200 = 0.895**. The MDE₉₀ criterion is then met at no point on the tested grid.

### Correction

| Quantity | Originally published | Corrected |
|---|---|---|
| Arm 1 · 1y · MDE₉₀ | 0.40 | **not achieved on the tested grid (0.00 – 0.40)** |
| Arm 1 · 1y · recovery at IC 0.40 | 0.900 | **0.895** |
| Arm 1 · 1y · recovery at IC 0.12 | 0.325 | **0.320** |
| Arm 1 · 1y · recovery at IC 0.15 | 0.340 | **0.335** |

All other horizons: recovery probabilities unchanged in 70 of 70 cells.

### Affected artifacts
`V6_ARM1_MDE_TABLE.csv` (row `1y`, column `mde_90`); `V6_ARM1_RECOVERY_CURVES.csv` (horizon `1y`, target_ic 0.12, 0.15, 0.40); `V6_ARM1_RESULTS.md` (MDE summary and power discussion).

### Scientific impact
**None adverse.** The published conclusion that long horizons are severely underpowered is **reinforced**. The record must additionally note that 1y MDE₉₀ was never robust: it rested on a single seed at an exact threshold. The corrected statement is that **1y power does not reliably reach 90% at any tested effect size.**

### Version history
- v1.0 · original publication · 1y MDE₉₀ = 0.40
- v1.1 · 2026-08-02 · superseded by this amendment. Original value preserved above.

---

# AMENDMENT A-2026-002
## Arm 1 — power-table seed metadata correction

**Effective date:** 2026-08-02 · **Type:** Administrative · **Conclusion changes:** No

### Background
`V6_ARM1_POWER_TABLE.csv` records the number of Monte Carlo seeds per grid cell in an `n_seeds` column.

### Reason
The column contains both 200 and 300. The audit established that **every** published recovery probability is an exact multiple of 1/200, and that **none** is a multiple of 1/300. The run used 200 seeds throughout; the rows labelled 300 are mislabelled.

### Correction

| Quantity | Originally published | Corrected |
|---|---|---|
| `n_seeds` (rows labelled 300) | 300 | **200** |
| `n_seeds` (rows labelled 200) | 200 | 200 (unchanged) |

No power value, recovery probability, or derived statistic changes.

### Affected artifacts
`V6_ARM1_POWER_TABLE.csv` (`n_seeds` column only).

### Scientific impact
**None.** This is a metadata correction. Its significance is that an incorrect seed count would have caused any future reproduction attempt to fail, and would have misstated the Monte Carlo resolution of every affected row.

### Version history
- v1.0 · original publication · mixed `n_seeds` ∈ {200, 300}
- v1.1 · 2026-08-02 · `n_seeds` = 200 throughout.

---

# AMENDMENT A-2026-003
## Arm 1 — recovery-curve provenance disclosure and MDE₈₀ correction

**Effective date:** 2026-08-02 · **Type:** Provenance / numerical · **Conclusion changes:** No

### Background
`V6_ARM1_RECOVERY_CURVES.csv` presents, for each horizon, a single recovery curve spanning target IC 0.00 to 0.40. `V6_ARM1_MDE_TABLE.csv` derives MDE₈₀ from that curve and reports `bootstrap_se` in the same row.

### Reason
The audit established that the published curve is a **splice of two runs with different configurations**, presented as one:

| Grid points | Script | Seeds | Bootstrap draws | Seed stream |
|---|---|---|---|---|
| 0.00 – 0.10 | `v6_arm1.py` | 200 | **400** | `20260801 + hz·10⁶ + ρ·10⁴ + s` |
| 0.12 – 0.40 | `v6_arm1b.py` | 200 | **300** | `77·10⁶ + tag·10⁵ + ρ·10³ + s` |

MDE₈₀ at 3m and at 1y is determined by grid points ≥ 0.12 — the 300-draw arm — while `bootstrap_se` in the **same published row** originates from the 400-draw arm. The published row therefore mixes two bootstrap resolutions.

Separately, the n-scaling analysis in `V6_ARM1_SCALING.csv` used a **third** configuration, `seeds=150, boot=250`, not recorded in the artifact.

Re-executed coherently at 400 draws throughout, with both the original and corrected rankings **in agreement**, MDE₈₀ is smaller at both affected horizons. This discrepancy is **provenance-caused and independent of tie handling**.

### Correction

| Quantity | Originally published | Corrected |
|---|---|---|
| Arm 1 · 3m · MDE₈₀ | 0.25 | **0.20** |
| Arm 1 · 1y · MDE₈₀ | 0.40 | **0.30** |
| Recovery curve provenance | undisclosed | **disclosed as above** |
| Scaling provenance | undisclosed | **`seeds=150, boot=250`** |

MDE₈₀ at 1w, 2w, 1m and 6m is unchanged. `bootstrap_se` and false-positive rate reproduce the published values at all six horizons.

### Affected artifacts
`V6_ARM1_RECOVERY_CURVES.csv` (provenance metadata; grid points ≥ 0.12); `V6_ARM1_MDE_TABLE.csv` (rows `3m`, `1y`, column `mde_80`); `V6_ARM1_RESULTS.md` (MDE summary; provenance section); `V6_ARM1_SCALING.csv` (provenance metadata).

### Scientific impact
**None adverse, and mildly favourable.** The corrected MDE₈₀ values are *smaller* than published, meaning the panel is marginally **more** sensitive at 3m and 1y than the record claimed. The published figures were conservative by one grid step. No conclusion depended on the difference.

The record must state going forward that a recovery curve assembled from heterogeneous runs is not a valid single power curve, and that MDE and its companion standard error must be computed under one configuration.

### Version history
- v1.0 · original publication · 3m MDE₈₀ = 0.25, 1y MDE₈₀ = 0.40, provenance undisclosed
- v1.1 · 2026-08-02 · corrected values and full provenance disclosure. Original values preserved above.

---

# AMENDMENT A-2026-004
## Arm 1.5 — 1y information-loss values

**Effective date:** 2026-08-02 · **Type:** Numerical · **Conclusion changes:** No

### Background
Arm 1.5 measured `LOSS = IC(consensus) − IC(combined)` under combiner-level injection across six horizons and seven ρ values, with block-bootstrap confidence intervals.

### Reason
Arm 1.5 reproduced **bit-perfectly** under the original ranking: max │published − re-run│ = 0.000e+00 across `ic_combined`, `ic_consensus`, `loss`, `boot_lo`, `boot_hi` and `boot_sd` over all 42 rows.

Under corrected average-rank handling, seven rows change — all at the 1y horizon, all ρ values. The cause is a single 2-member tie group in the combined score at 1y (2 of 45 cells). `ic_consensus` changed in **0 of 42** rows; horizons 1w, 2w, 1m, 3m and 6m changed in **0** rows.

### Correction

| ρ | Originally published `loss` | Corrected `loss` | Abs Δ | Rel Δ |
|---|---|---|---|---|
| 0.00 | +0.039921 | **+0.040125** | 2.04e-04 | 0.51% |
| 0.03 | +0.029249 | **+0.029449** | 2.00e-04 | 0.68% |
| 0.05 | +0.046640 | **+0.046839** | 1.99e-04 | 0.43% |
| 0.07 | +0.068248 | **+0.068445** | 1.97e-04 | 0.29% |
| **0.10 (primary)** | +0.033729 | **+0.033922** | 1.93e-04 | 0.57% |
| 0.15 | +0.053887 | **+0.054077** | 1.90e-04 | 0.35% |
| 0.20 | +0.085507 | **+0.085861** | 3.54e-04 | 0.41% |

Bootstrap bounds shift across all 42 rows by at most 2.662e-03 (`boot_lo`), 4.074e-04 (`boot_hi`), 8.112e-04 (`boot_sd`).

### Affected artifacts
`V6_ARM15_INFORMATION_LOSS.csv` (horizon `1y`, all ρ; bootstrap columns all rows); `V6_ARM15_RESULTS.md` (information-loss table).

### Scientific impact
**None.** Across all 42 cells there are **0 sign flips** and **0 confidence-interval zero-exclusion flips**. Every inferential statement in Arm 1.5 — including the primary finding that the combiner does not destroy signal — is unaffected. The corrections lie in the fourth decimal of a quantity whose confidence interval spans zero at 1y both before and after.

### Version history
- v1.0 · original publication · 1y loss values as tabulated above
- v1.1 · 2026-08-02 · corrected 1y values and bootstrap bounds. Original values preserved above.

---

# AMENDMENT A-2026-005
## Readiness review and audit report — tie-mechanism and confidence corrections

**Effective date:** 2026-08-02 · **Type:** Documentation · **Conclusion changes:** No

### Background
The Arm 2 readiness review identified the rank tie-handling defect (logged there as D-04) and recommended re-verification of Arm 1 and Arm 1.5. The subsequent reproducibility audit discharged that recommendation.

### Reason
Three statements in the record are not supported by the measured tie census and require correction.

**(a) Mechanism.** The readiness review attributed the ties to the `Z_CLIP` boundary. The census shows the dominant tie value is **50.0, the neutral score**: 5 cells at 1w, 5 at 2w, 2 at 1m, 2 at 3m, 2 at 6m, 2 at 1y.

**(b) The audit report's own overstatement.** `V6_REPRODUCIBILITY_AUDIT.md` §1 states that *every* observed tie is at 50.0. This is incorrect. The 1y census shows a **second 2-member tie group at score ≈ 0.00317**, consistent with a `Z_CLIP` floor. The readiness review's hypothesis was therefore not wrong — it was **not dominant**. This Board corrects its own prior correction.

**(c) Confidence.** The readiness review declared Arm 1 and Arm 1.5 "suspect until re-verified" on a theoretical argument, without measuring tie prevalence. Measurement showed the exposure was near zero: the injected scores carrying every Arm 1 conclusion are continuous by construction and contain no ties at all, and Arm 1.5's consensus series is tie-free at every horizon.

### Correction

| Statement | Original | Corrected |
|---|---|---|
| Tie mechanism | "`Z_CLIP` produces genuine ties at the boundary" | **"The neutral score 50.0 is the dominant tie mechanism; clipping is a minor secondary contributor, observed once, at 1y."** |
| Audit report §1 | "every tie observed is at 50.0" | **"the dominant tie value is 50.0; one 2-member group at 1y sits at ≈0.00317, consistent with a clip floor"** |
| Status of Arm 1 / Arm 1.5 | "suspect until re-verified" | **"re-verified; reproducible; conclusions stand"** — the "suspect" characterization is **withdrawn** as an overstatement of the evidence available when written |

### Affected artifacts
`V6_ARM2_REPRODUCIBILITY_REPORT.md` (cross-arm defect D-04 section); `V6_ARM2_READINESS_DECISION.md` (numbered conclusion 13); `V6_ARM2_READINESS_REGISTER.md` (defect D-04 row); `V6_REPRODUCIBILITY_AUDIT.md` (§1 tie census, §8 Board note).

### Scientific impact
**None.** No numerical result and no conclusion depends on these statements. The correction is recorded because the readiness review's stated mechanism would mislead any future investigator into looking for ties at the clip boundary, where they are largely absent, rather than at the neutral score, where they concentrate.

The Board affirms that raising the flag was correct: the check was cheap and the answer was not knowable without measuring. Only the confidence attached to it was unsupported.

### Version history
- v1.0 · readiness review as published · clip-boundary mechanism; "suspect" status
- v1.1 · audit report as published · "every tie at 50.0"
- v1.2 · 2026-08-02 · both superseded by this amendment. Original statements preserved above.

---

## Amendment register

| ID | Type | Documents | Conclusions change |
|---|---|---|---|
| A-2026-001 | Scientific record / numerical | 3 | No — reinforced |
| A-2026-002 | Administrative | 1 | No |
| A-2026-003 | Provenance / numerical | 4 | No |
| A-2026-004 | Numerical | 2 | No |
| A-2026-005 | Documentation | 4 | No |

**Total scientific corrections: 0. Total conclusions withdrawn: 0.**
