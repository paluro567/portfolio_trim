# V6 Research Program — Canonical Audit Record

**Issuing body:** Independent Research Integrity Board
**Effective date:** 2026-08-02
**Status:** CANONICAL. This document governs the permanent scientific record of the V6 program.
**Evidence base:** `V6_REPRODUCIBILITY_AUDIT.md` and its archived paired outputs (`V6_AUDIT_ARM1_CURVE_OLD.csv`, `V6_AUDIT_ARM1_CURVE_NEW.csv`, `V6_AUDIT_ARM15_PAIRED.csv`). **No computation was performed in producing this record.** Every figure below is transcribed from completed audit output.

---

## PART 1 — Final audit findings

Fifteen findings. Each carries exactly one classification.

### F-01 · Rank tie-handling defect — **Instrumentation defect**
`argsort(argsort(v))` assigns distinct ranks to tied values; correct Spearman requires average ranks. Present in `v6_arm1.py`, `v6_arm1b.py` and `a15_run.py`.
*Category:* it is a fault in the measuring apparatus, not in the data, the design, or the write-up.
*Numerical result changes:* yes, in a bounded set (F-04 – F-07).
*Scientific conclusion changes:* no.

### F-02 · Arm 1 primary statistics are provably invariant — **No action required**
The audit established the identity `avgrank = argsort_rank + 1` on tie-free input (max deviation `0.000e+00`). Spearman mean-centres both rank vectors, so the constant cancels and the implementations are bitwise identical wherever ties are absent. Arm 1's injected scores (`ρ·zy + √(1−ρ²)·ε`) and the outcome `spy_rel` are both tie-free at every horizon. `bias`, `mean_recovered_ic` and `sd_recovered_ic` changed in **0 of 84** cells.
*Category:* the defect provably cannot reach these quantities.
*Changes:* none, numerical or scientific.

### F-03 · Arm 1.5 reproduces bit-perfectly — **No action required**
max │published − re-run under original ranking│ = **0.000e+00** across `ic_combined`, `ic_consensus`, `loss`, `boot_lo`, `boot_hi`, `boot_sd` over 42 rows.
*Category:* confirms harness fidelity and substrate integrity; nothing to correct.
*Changes:* none.

### F-04 · Arm 1 · 1y MDE₉₀ knife edge — **Numerical correction**
Recovery at target IC 0.40 sat at exactly 180/200 = 0.900, on the ≥0.90 threshold. One seed's bootstrap lower bound crossed zero under the fix, giving 179/200 = 0.895. MDE₉₀ at 1y moves from **0.40** to **not achieved on the tested grid**.
*Category:* a published number changes; the underlying finding does not.
*Numerical:* yes. *Scientific:* no — it **reinforces** the published conclusion that 1y is severely underpowered.

### F-05 · Arm 1 · two further 1y recovery probabilities — **Numerical correction**
1y IC 0.12: 0.325 → 0.320. 1y IC 0.15: 0.340 → 0.335. Each is one seed in 200.
*Numerical:* yes. *Scientific:* no — neither sits at a decision threshold.

### F-06 · Arm 1.5 · 1y information-loss values — **Numerical correction**
Seven rows (all 1y, every ρ) shift by ≤ 3.535e-04, caused by the single 2-member tie group in `comb` at 1y (2 of 45 cells). `ic_consensus` changed in **0 of 42** rows.
*Numerical:* yes, in the 4th decimal. *Scientific:* no — **0 sign flips, 0 CI zero-exclusion flips**.

### F-07 · Bootstrap SE and CI shifts, both arms — **Numerical correction**
Arm 1 `mean_bootstrap_se`: all 84 cells, max 6.891e-05. Arm 1.5 `boot_lo` / `boot_hi` / `boot_sd`: all 42 cells, max 2.662e-03 / 4.074e-04 / 8.112e-04. Cause is resampling with replacement creating duplicate rows, not clipping.
*Numerical:* yes, immaterial. *Scientific:* no.

### F-08 · Power-table seed metadata is wrong — **Provenance defect**
`V6_ARM1_POWER_TABLE.csv` carries `n_seeds` values of both 200 and 300. Every published recovery probability is an exact multiple of 1/200; **none** is a multiple of 1/300.
*Category:* the recorded conditions of the run misstate the actual conditions. Unrelated to tie handling.
*Numerical:* no result value changes — only the metadata column. *Scientific:* no.

### F-09 · Recovery curve splices two incompatible runs — **Provenance defect**
`V6_ARM1_RECOVERY_CURVES.csv` merges grid points ≤ 0.10 from `v6_arm1.py` (200 seeds, **400** bootstrap draws, seed stream `20260801 + hz·10⁶ + ρ·10⁴ + s`) with points ≥ 0.12 from `v6_arm1b.py` (200 seeds, **300** bootstrap draws, seed stream `77·10⁶ + tag·10⁵ + ρ·10³ + s`). The published file presents these as one curve.
*Category:* undisclosed heterogeneity in run conditions.
*Numerical:* yes, downstream — see F-10. *Scientific:* no.

### F-10 · MDE₈₀ at 3m and 1y are set by the 300-draw arm — **Numerical correction**
MDE₈₀ at 3m and 1y is determined by grid points ≥ 0.12, while `bootstrap_se` in the same published row comes from the 400-draw arm. Re-executed coherently at 400 draws throughout, MDE₈₀ = **0.20 at 3m** (published 0.25) and **0.30 at 1y** (published 0.40). The original and corrected rankings **agree** on these values, so the discrepancy is entirely provenance.
*Numerical:* yes — a full grid step at two horizons, the **largest** numerical effect the audit found. *Scientific:* no — the published values are conservative; the corrected MDEs are smaller, so the panel is marginally more sensitive than published, not less.

### F-11 · Scaling analysis used a third configuration — **Provenance defect**
`v6_arm1b.py` computed the n-scaling results with `seeds=150, boot=250`, a third parameter set not recorded in `V6_ARM1_SCALING.csv`.
*Numerical:* no value is contested. *Scientific:* no.

### F-12 · Readiness review mischaracterized the tie mechanism — **Documentation defect**
`V6_ARM2_REPRODUCIBILITY_REPORT.md` and `V6_ARM2_READINESS_DECISION.md` attribute the ties to the `Z_CLIP` boundary. The tie census shows the dominant tie value is **50.0, the neutral score** (1w 5, 2w 5, 1m 2, 3m 2, 6m 2, 1y 2 cells).
**The Board also corrects the audit report's own overstatement.** `V6_REPRODUCIBILITY_AUDIT.md` §1 states that *every* tie is at 50.0. The census shows a second 2-member tie group at 1y at score ≈ 0.00317, which is consistent with a `Z_CLIP` floor. The correct statement is: **the neutral score is the dominant tie mechanism; clipping is a minor secondary contributor observed once, at 1y.** The readiness review's hypothesis was not wrong, it was not dominant.
*Numerical:* no. *Scientific:* no.

### F-13 · Readiness review overstated its confidence — **Documentation defect**
The readiness review declared Arm 1 and Arm 1.5 "suspect until re-verified" on a theoretical argument, without measuring tie prevalence. Measurement showed exposure was near zero. Flagging was correct and cheap; the confidence level attached to it was not supported at the time it was written.
*Numerical:* no. *Scientific:* no.

### F-14 · Audit-run wall-clock times not instrumented — **Documentation defect**
The Arm 1.5 audit completed in under 30 s. The two Arm 1 audit passes were not wall-clock instrumented; only the substantive outputs were captured. Establishing exact runtimes would require re-execution, which this Board does not authorize.
*Numerical:* no. *Scientific:* no.

### F-15 · Archived substrate verified intact — **No action required**
`merged.csv` md5 `aa1c82bd1203b17b68a353656bef3ff4`, 51,025 rows; 7 prediction files, 63,535 lines; `v6_arm1.py` md5 `b620f05f95879edf408218910fc84ca6`; `a15_run.py` md5 `6608b6a33c154680641a313bbac3be5d`.
*Changes:* none.

### Classification summary

| Category | Findings |
|---|---|
| Instrumentation defect | F-01 |
| Provenance defect | F-08, F-09, F-11 |
| Documentation defect | F-12, F-13, F-14 |
| Numerical correction | F-04, F-05, F-06, F-07, F-10 |
| Scientific correction | **none** |
| No action required | F-02, F-03, F-15 |

**No finding in the entire audit is a scientific correction.**

---

## PART 2 — Canonical research record: documents requiring amendment

Five amendments. Every other V6 document stands unaltered.

| Amendment | Document(s) | Sections | Figures | Tables | Provenance metadata | Conclusions change? | Type |
|---|---|---|---|---|---|---|---|
| **A-2026-001** | `V6_ARM1_MDE_TABLE.csv`, `V6_ARM1_RESULTS.md` | MDE summary; power discussion | none | MDE table, row `1y`, column `mde_90` | none | **No** — reinforced | Scientific record / numerical |
| **A-2026-002** | `V6_ARM1_POWER_TABLE.csv` | — | none | `n_seeds` column | seed count 300 → 200 | **No** | Administrative |
| **A-2026-003** | `V6_ARM1_RECOVERY_CURVES.csv`, `V6_ARM1_MDE_TABLE.csv`, `V6_ARM1_RESULTS.md`, `V6_ARM1_SCALING.csv` | provenance note; MDE summary | none | recovery curves (grid ≥0.12); MDE table rows `3m`, `1y`, column `mde_80` | bootstrap draws, seed streams, script identity | **No** | Provenance / numerical |
| **A-2026-004** | `V6_ARM15_INFORMATION_LOSS.csv`, `V6_ARM15_RESULTS.md` | information-loss table | none | 7 rows, horizon `1y`, all ρ | none | **No** | Numerical |
| **A-2026-005** | `V6_ARM2_REPRODUCIBILITY_REPORT.md`, `V6_ARM2_READINESS_DECISION.md`, `V6_ARM2_READINESS_REGISTER.md`, `V6_REPRODUCIBILITY_AUDIT.md` | defect D-04 statement; conclusion 13; §1 tie census note | none | none | none | **No** | Documentation |

**Documents explicitly NOT amended:** `V6_ARM1_LIMITATIONS.md`, `V6_ARM1_SCIENTIFIC_REVIEW.md`, `V6_ARM15_DIAGNOSTICS.md`, `V6_ARM15_REPRODUCIBILITY.md`, `V6_ARM15_BOOTSTRAP_RESULTS.csv`, `V6_ARM15_SECONDARY.csv`, `V6_ARM15_WEIGHTS.csv`, `ARM2_PROGRAM_BOARD_REVIEW.md`, `V6_ARM2_PREREGISTRATION.md`, and all remaining Arm 2 readiness artifacts. No audit finding reaches them.

---

## PART 4 — Canonical results

### 4.1 Arm 1 — MDE table (definitive)

| Horizon | n | bootstrap_se (published) | bootstrap_se (canonical) | FP rate | MDE₈₀ published | MDE₈₀ **canonical** | MDE₉₀ published | MDE₉₀ **canonical** |
|---|---|---|---|---|---|---|---|---|
| 1w | 1264 | 0.0278 | 0.027771 | 0.025 | 0.10 | 0.10 | 0.10 | 0.10 |
| 2w | 1264 | 0.0278 | 0.027835 | 0.035 | 0.10 | 0.10 | 0.10 | 0.10 |
| 1m | 421 | 0.0472 | 0.047201 | 0.020 | 0.15 | 0.15 | 0.20 | 0.20 |
| 3m | 180 | 0.0689 | 0.068912 | 0.020 | 0.25 | **0.20** | 0.25 | 0.25 |
| 6m | 94 | 0.0882 | 0.088180 | 0.055 | 0.30 | 0.30 | 0.40 | 0.40 |
| 1y | 47 | 0.1007 | 0.100718 | 0.095 | 0.40 | **0.30** | 0.40 | **not achieved** |

Bootstrap SE and false-positive rate reproduce the published values at all six horizons. Changed cells in bold: two from provenance (F-10), one from tie handling (F-04).

### 4.2 Arm 1 — recovery table, 1y tail (the only horizon with any change)

| target IC | Published / original ranking | **Canonical** | Δ |
|---|---|---|---|
| 0.12 | 0.325 | **0.320** | −0.005 |
| 0.15 | 0.340 | **0.335** | −0.005 |
| 0.20 | 0.530 | 0.530 | 0 |
| 0.25 | 0.590 | 0.590 | 0 |
| 0.30 | 0.800 | 0.800 | 0 |
| 0.40 | 0.900 | **0.895** | −0.005 |

All other horizons: **0 of 70 cells changed**. `mean_recovered_ic`, `sd_recovered_ic`, `bias`: **0 of 84 changed**.

### 4.3 Arm 1.5 — information loss, 1y (the only horizon with any change)

| ρ | Published | **Canonical** | Abs Δ | Rel Δ | Sign | CI excludes 0 |
|---|---|---|---|---|---|---|
| 0.00 | +0.039921 | **+0.040125** | 2.04e-04 | 0.51% | unchanged | unchanged |
| 0.03 | +0.029249 | **+0.029449** | 2.00e-04 | 0.68% | unchanged | unchanged |
| 0.05 | +0.046640 | **+0.046839** | 1.99e-04 | 0.43% | unchanged | unchanged |
| 0.07 | +0.068248 | **+0.068445** | 1.97e-04 | 0.29% | unchanged | unchanged |
| **0.10 (primary)** | +0.033729 | **+0.033922** | 1.93e-04 | 0.57% | unchanged | unchanged |
| 0.15 | +0.053887 | **+0.054077** | 1.90e-04 | 0.35% | unchanged | unchanged |
| 0.20 | +0.085507 | **+0.085861** | 3.54e-04 | 0.41% | unchanged | unchanged |

1w, 2w, 1m, 3m, 6m: max │Δloss│ = **0.000000**. `ic_consensus`: unchanged in all 42 rows.

### 4.4 Bootstrap summaries

| Arm | Quantity | Cells changed | max │Δ│ | Decision impact |
|---|---|---|---|---|
| 1 | `mean_bootstrap_se` | 84 / 84 | 6.891e-05 | none |
| 1 | `analytic_mde_80` | 6 / 6 | 1.700e-04 | none |
| 1.5 | `boot_lo` | 42 / 42 | 2.662e-03 | none — 0 zero-exclusion flips |
| 1.5 | `boot_hi` | 42 / 42 | 4.074e-04 | none |
| 1.5 | `boot_sd` | 42 / 42 | 8.112e-04 | none |

### 4.5 Power tables

Arm 1 false-positive rates are canonical as published and unchanged by the fix: 1w 0.025 · 2w 0.035 · 1m 0.020 · 3m 0.020 · 6m 0.055 · 1y 0.095. `V6_ARM1_POWER_TABLE.csv` requires the `n_seeds` metadata correction only (A-2026-002); no power value changes.

### 4.6 Provenance metadata (canonical)

| Artifact | Script | Seeds | Bootstrap draws | Seed stream |
|---|---|---|---|---|
| Recovery curves, grid 0.00–0.10 | `v6_arm1.py` | 200 | 400 | `20260801 + hz·10⁶ + ρ·10⁴ + s` |
| Recovery curves, grid 0.12–0.40 | `v6_arm1b.py` | 200 | **300** | `77·10⁶ + tag·10⁵ + ρ·10³ + s` |
| n-scaling | `v6_arm1b.py` | **150** | **250** | `77·10⁶ + (200+tag)·10⁵ + ρ·10³ + s` |
| Arm 1.5 all cells | `a15_run.py` | — | 1000 | `SEED = 20260801`, block = 4 |
| Audit re-runs (both arms) | audit harness | 200 / 300 | 400 (Arm 1), 1000 (Arm 1.5) | as above, paired OLD/NEW on identical indices |

### 4.7 Seed metadata

`SEED_BASE = 20260801` governs `v6_arm1.py` and `a15_run.py`. `v6_arm1b.py` does **not** derive from `SEED_BASE`; it uses an independent `77_000_000` base. This is recorded here because it was previously undocumented, and it is the reason the extended grid cannot be reproduced from `SEED_BASE` alone.

### 4.8 Runtime metadata

Arm 1.5 audit re-run: **under 30 s** wall clock. Arm 1 audit re-runs: multi-minute, **not instrumented** (F-14). Establishing precise figures would require re-execution and is not authorized.

---

## PART 5 — Scientific impact

| Prior conclusion | Classification | Why |
|---|---|---|
| **Arm 1: the validation layer is unbiased** | **Unchanged** | Rests on the `bias` column, bitwise identical in 0/84 changed cells. |
| **Arm 1: the validation layer is efficient (empirical/analytic MDE ratio ≈ 1.3–1.6)** | **Unchanged** | Driven by `bootstrap_se`, which reproduces published values at all six horizons. |
| **Arm 1: false-positive control is at nominal level** | **Unchanged** | FP rates changed in 0/6 horizons. |
| **Arm 1: long horizons are severely underpowered** | **Numerically corrected — conclusion strengthened** | 1y MDE₉₀ falls from 0.40 to *not achieved*. The horizon is less powered than published, not more. |
| **Arm 1: MDE₈₀ at 3m = 0.25, at 1y = 0.40** | **Numerically corrected** | Coherent 400-draw execution gives 0.20 and 0.30. Provenance-caused (F-09/F-10), not tie-caused. Direction is favourable: the panel is marginally more sensitive than published. |
| **Arm 1.5: the combiner does not destroy signal** | **Unchanged** | 0 sign flips, 0 CI zero-exclusion flips across 42 cells; five of six horizons bitwise identical. |
| **Arm 1.5: equal-weight consensus vs combined comparison** | **Unchanged** | `ic_consensus` changed in 0/42 rows. |
| **Arm 1.5: primary endpoint LOSS(0.10)** | **Numerically corrected at 1y only** | 1y +0.033729 → +0.033922; CI continues to span zero. Other five horizons unchanged. |
| **Readiness review: Arm 1/1.5 are "suspect"** | **Administratively corrected** | Withdrawn as an overstatement (F-13). The defect was real, its effect was immaterial. |
| **Readiness review: ties arise at the `Z_CLIP` boundary** | **Administratively corrected** | Dominant mechanism is the neutral score 50.0; clipping is a minor secondary contributor (F-12). |
| **Any conclusion withdrawn** | **None** | No finding is a scientific correction. |

---

## PART 6 — Program status

Every statement below is supported only by completed audit evidence.

| Question | Determination | Evidence |
|---|---|---|
| **Any gate changes?** | **No.** | No V6 gate is defined on MDE₉₀, on bootstrap SE, or on any quantity that moved. Gate-bearing quantities — `bias`, FP rate, MDE₈₀ at 1w/2w/1m/6m, Arm 1.5 sign and CI exclusion — are all unchanged. |
| **Any roadmap decision changes?** | **No.** | The Arm 1 → Arm 1.5 → Arm 2 progression rested on (a) the validation layer being unbiased and (b) the combiner not destroying signal. Both are established unchanged. |
| **Any funding decision changes?** | **No.** | No funding decision in the V6 record is conditioned on a corrected quantity. The audit consumed no new capital and required no new data. |
| **Any Arm 2 prerequisite changes?** | **No.** | Arm 2 readiness is blocked by B-01 (consumer metric counts name mentions, not value reads), B-02 (control arm n=1), and B-03 (checkpoint A2 fails at every ρ: 0.00415 at primary, 0.00793 at 3× primary, threshold 0.02). None of these depends on rank tie handling. All three **remain in force.** |
| **Any scientific recommendation changes?** | **One, narrowly.** | The readiness review's recommendation to re-verify Arm 1 and Arm 1.5 is **discharged** by this audit. Its characterization of those arms as "suspect" is withdrawn. All other recommendations stand. |

---

## PART 7 — Final certification

**1. Does the corrected implementation reproduce Arm 1?**
**Yes.** Bootstrap SE and false-positive rate reproduce the published values at all six horizons; MDE₈₀ reproduces at four of six and MDE₉₀ at five of six; `bias`, `mean_recovered_ic` and `sd_recovered_ic` are bitwise identical across all 84 grid cells. Three recovery probabilities at 1y move by one seed in 200. The two MDE₈₀ non-reproductions (3m, 1y) are **provenance-caused, not tie-caused** — the original and corrected rankings agree on them.

**2. Does the corrected implementation reproduce Arm 1.5?**
**Yes — bit-perfect.** max │published − re-run│ = **0.000e+00** across six metrics and 42 rows. The correction alters seven 1y values in the fourth decimal, with **0 sign flips and 0 confidence-interval zero-exclusion flips**.

**3. Are any published scientific conclusions invalid?**
**No.** Not one conclusion from Arm 1 or Arm 1.5 is reversed, weakened, or withdrawn. The single conclusion-adjacent change — 1y MDE₉₀ — moves in the direction that **reinforces** the published finding. The audit produced **zero scientific corrections**.

**4. Which documents require amendment?**
Five amendments across seven documents:
- **A-2026-001** — `V6_ARM1_MDE_TABLE.csv`, `V6_ARM1_RESULTS.md` (1y MDE₉₀)
- **A-2026-002** — `V6_ARM1_POWER_TABLE.csv` (seed metadata)
- **A-2026-003** — `V6_ARM1_RECOVERY_CURVES.csv`, `V6_ARM1_MDE_TABLE.csv`, `V6_ARM1_RESULTS.md`, `V6_ARM1_SCALING.csv` (provenance splice; MDE₈₀ at 3m and 1y)
- **A-2026-004** — `V6_ARM15_INFORMATION_LOSS.csv`, `V6_ARM15_RESULTS.md` (1y values)
- **A-2026-005** — `V6_ARM2_REPRODUCIBILITY_REPORT.md`, `V6_ARM2_READINESS_DECISION.md`, `V6_ARM2_READINESS_REGISTER.md`, `V6_REPRODUCIBILITY_AUDIT.md` (tie-mechanism and confidence statements)

**5. Is the V6 scientific record now internally consistent?**
**Conditionally — upon execution of the five amendments.** As of this writing the record contains three live inconsistencies: a mislabelled seed count (F-08), an undisclosed run splice (F-09), and a mischaracterized tie mechanism carried in four documents (F-12). None affects a conclusion. Once A-2026-001 through A-2026-005 are applied, the record is internally consistent.

**6. Is the scientific program authorized to proceed to the next preregistered stage?**
**Not yet — and not for any reason arising from this audit.**

The instrumentation question is **closed**: Arm 1 and Arm 1.5 are reproducible and their conclusions stand. That clearance is granted without reservation.

But the next preregistered stage is Arm 2, and Arm 2 readiness was refused on three independent grounds (B-01, B-02, B-03) that this audit does not touch. Checkpoint A2 fails by 2.5× even at three times the primary ρ, and the frozen decision rule returns **VOID** when A2 fails. Authorization to proceed to Arm 2 requires an amendment from the Preregistration Committee resolving the consumer-metric and control-arm defects. **That authority does not rest with this Board.**

---

## Board note

The defect this audit was convened to examine proved immaterial. The defect it found incidentally — that a single published recovery curve was assembled from two runs with different bootstrap resolutions and different seed streams, displacing two MDE₈₀ values by a full grid step (F-09, F-10) — is larger in magnitude and was invisible to every prior review.

Both were found the same way: by attempting to re-execute a published result and insisting the attempt reproduce it exactly. The Board records that as the operative lesson. A result that cannot be re-executed from its recorded provenance is not yet a result.
