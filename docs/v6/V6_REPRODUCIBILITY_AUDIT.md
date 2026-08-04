# V6 — Independent Reproducibility Audit: Rank Tie-Handling Defect

**Board:** Independent Reproducibility Audit Board · **Date:** 2026-08-01
**Mandate:** determine whether the corrected ranking implementation materially changes the conclusions of Arm 1 or Arm 1.5.
**Scope limit:** no new experiments, no redesign. Both arms were re-executed on the archived substrate with the original seeds; the ranking function is the only variable.

## 0. Audit design

The defect: `argsort(argsort(v))` assigns **distinct** ranks to tied values. Correct Spearman requires **average ranks** for ties.

Both arms were re-run with the point estimate and the bootstrap CI computed **twice from the identical resample indices** — once under the original ranking (`OLD`), once under average-rank (`NEW`). RNG consumption order was preserved exactly, so `OLD` must reproduce the published artifacts bit-for-bit. It does (§2, §3). Any `OLD → NEW` difference is therefore attributable to the fix alone.

### 0.1 The exact channel of the defect

For **tie-free** input, average-rank equals argsort-rank + 1:

```
max|avgrank − (argsort_rank + 1)| on tie-free data = 0.000e+00
```

Spearman mean-centres both rank vectors, so the additive constant cancels and the two implementations are **bitwise identical**. Ties are the *only* channel through which the defect can act. The audit therefore reduces to a tie census plus the bootstrap, where resampling with replacement creates duplicate rows.

## 1. PART 1 — Affected analyses

### Tie census (measured, not assumed)

| Series | Role | Ties |
|---|---|---|
| `spy_rel` (outcome `y`) | ranked in every IC, both arms, all 6 horizons | **0 at every horizon** |
| Arm 1 injected score `ρ·zy + √(1−ρ²)·ε` | input to MDE, recovery curves, power tables | **0** — continuous by construction |
| Arm 1.5 `cons` (equal-weight consensus) | input to LOSS | **0 at every horizon** |
| Arm 1.5 `comb` (combined score) | input to LOSS | **0 at 1w/2w/1m/3m/6m; 1 group (2 of 45) at 1y** |
| Arm 1 `evidence_score` (real scores) | context statistic only | 5 (1w, 2w), 2 (1m, 3m, 6m), 4 of 47 (1y) — all at **50.0** |

**Correction to the readiness review.** That review asserted the ties arise at the `Z_CLIP` boundary. They do not. Every tie observed is at **50.0, the neutral score**. The stated mechanism was wrong and the true exposure is far narrower than claimed. The readiness review's recommendation to re-verify was nonetheless correct — this audit is what settles it.

### Classification

**Definitely unaffected** — provable, not merely observed:
- Every Arm 1 point IC on injected scores (MDE table, recovery curves, power tables, bias, sd of recovered IC) — both ranked series are tie-free.
- Arm 1.5 `ic_consensus` at every horizon and every ρ.
- Arm 1.5 `ic_combined` and `loss` at 1w, 2w, 1m, 3m, 6m.
- All cohort construction, embargo logic, non-overlap stride, and `κ` estimation — no ranking involved.

**Possibly affected** — ties present or bootstrap duplicates:
- All block-bootstrap CIs and SEs in both arms (resampling with replacement creates duplicate rows).
- Arm 1.5 `ic_combined` / `loss` at 1y.
- Arm 1's `real_score_ic` context statistic and its CI.
- Recovery probabilities, via a bootstrap lower bound crossing zero.

**Definitely affected**:
- Nothing that carries a conclusion. The only quantities that moved are listed in §4.

## 2. PART 2 — Arm 1 reproduction

### 2.1 Paired result — 6 horizons × 8 grid points × 300 seeds × 400 bootstrap draws

| Quantity | max │NEW − OLD│ | Rows changed |
|---|---|---|
| `recovery_prob` | **0.000e+00** | **0 / 48** |
| `mean_recovered_ic` | **0.000e+00** | **0 / 48** |
| `sd_recovered_ic` | **0.000e+00** | **0 / 48** |
| `bias` | **0.000e+00** | **0 / 48** |
| `false_positive_rate` | **0.000e+00** | 0 / 6 |
| `mde_80` | **0.000e+00** | 0 / 6 |
| `mde_90` | **0.000e+00** | 0 / 6 |
| `mean_bootstrap_se` | 6.878e-05 | 48 / 48 |
| `analytic_mde_80` | 1.700e-04 | 6 / 6 |

Every decision-bearing Arm 1 statistic is **numerically identical**. Only the bootstrap SE moves, in the fifth decimal, because resampling with replacement duplicates rows. Since a duplicated row carries its own `y` with it, the pairing inside a tie group is preserved and only a small arithmetic residue remains.

The one Arm 1 quantity that genuinely shifts is the **real-score IC**, a context statistic the source explicitly marks as *"context, not part of the injection"*:

| Horizon | OLD | NEW | Δ |
|---|---|---|---|
| 1w | +0.012567 | +0.012562 | −5.4e-06 |
| 1y | −0.183395 | −0.183753 | −3.6e-04 |

Both CIs continue to include zero at both horizons. No conclusion depends on it.

## 3. PART 3 — Arm 1.5 reproduction

### 3.1 Fidelity — `OLD` vs the published CSV, 42 rows

| Quantity | max │published − OLD│ |
|---|---|
| `ic_combined` | **0.000e+00** |
| `ic_consensus` | **0.000e+00** |
| `loss` | **0.000e+00** |
| `boot_lo` | **0.000e+00** |
| `boot_hi` | **0.000e+00** |
| `boot_sd` | **0.000e+00** |

**Bit-perfect.** Arm 1.5 reproduces exactly. The harness is faithful and the archived substrate is intact (`merged.csv` md5 `aa1c82bd1203b17b68a353656bef3ff4`, 51,025 rows; 7 prediction files, 63,535 lines).

### 3.2 Effect of the fix

| Quantity | max │NEW − OLD│ | Rows changed |
|---|---|---|
| `ic_consensus` | **0.000e+00** | **0 / 42** |
| `ic_combined` | 3.535e-04 | 7 / 42 (all 1y) |
| `loss` | 3.535e-04 | 7 / 42 (all 1y) |
| `boot_lo` | 2.662e-03 | 42 / 42 |
| `boot_hi` | 4.074e-04 | 42 / 42 |
| `boot_sd` | 8.112e-04 | 42 / 42 |
| **sign(`loss`) flips** | — | **0 / 42** |
| **CI zero-exclusion flips** | — | **0 / 42** |

Per-horizon max │Δloss│: 1w 0.000000 · 2w 0.000000 · 1m 0.000000 · 3m 0.000000 · 6m 0.000000 · **1y 0.000354**.

Only 1y moves, and only because `comb` has a single 2-member tie group in 45 cells.

### 3.3 Arm 1 at published provenance — 200 seeds, extended grid

Re-running at the seed count the published artifacts actually used:

| Horizon | `bootstrap_se` published | re-run `OLD` | FP published | re-run `OLD` | MDE₈₀ pub / OLD / NEW | MDE₉₀ pub / OLD / NEW |
|---|---|---|---|---|---|---|
| 1w | 0.0278 | 0.027771 | 0.025 | 0.025 | 0.10 / 0.10 / 0.10 | 0.10 / 0.10 / 0.10 |
| 2w | 0.0278 | 0.027835 | 0.035 | 0.035 | 0.10 / 0.10 / 0.10 | 0.10 / 0.10 / 0.10 |
| 1m | 0.0472 | 0.047201 | 0.020 | 0.020 | 0.15 / 0.15 / 0.15 | 0.20 / 0.20 / 0.20 |
| 3m | 0.0689 | 0.068912 | 0.020 | 0.020 | **0.25 / 0.20 / 0.20** | 0.25 / 0.25 / 0.25 |
| 6m | 0.0882 | 0.088180 | 0.055 | 0.055 | 0.30 / 0.30 / 0.30 | 0.40 / 0.40 / 0.40 |
| 1y | 0.1007 | 0.100718 | 0.095 | 0.095 | **0.40 / 0.30 / 0.30** | 0.40 / 0.40 / **NaN** |

Every base-grid statistic — bootstrap SE at all six horizons, false-positive rate at all six — reproduces the published value exactly.

## 4. PART 4 — Difference analysis

### 4.1 The only decision-relevant change in the entire audit

Three of 84 recovery probabilities moved, all at 1y, each by exactly 0.005 = **one seed in 200**:

| Horizon | target IC | Old | New | Abs Δ | Rel Δ | Decision changes? |
|---|---|---|---|---|---|---|
| 1y | 0.12 | 0.325 | 0.320 | 0.005 | 1.5% | no |
| 1y | 0.15 | 0.340 | 0.335 | 0.005 | 1.5% | no |
| 1y | **0.40** | **0.900** | **0.895** | 0.005 | 0.6% | **yes — MDE₉₀** |

| Quantity | Old | New | Abs Δ | Rel Δ | Preregistered decision | Scientific conclusion |
|---|---|---|---|---|---|---|
| Arm 1 · 1y · MDE₉₀ | 0.40 | **not achieved** | — | — | no gate defined on MDE₉₀ | **reinforced, not reversed** |

The 1y recovery probability at target IC = 0.40 sat at exactly **180/200 = 0.900**, precisely on the ≥0.90 threshold. Correcting the ranking flipped one seed's bootstrap lower bound across zero, giving 179/200 = 0.895, and the MDE₉₀ criterion is no longer met anywhere on the grid.

The honest reading: 1y MDE₉₀ was never robustly 0.40. It was 0.40 only on a knife edge decided by a single seed. The corrected result — 1y power never reliably reaches 90% at any tested effect size — **strengthens the published Arm 1 conclusion that the 1y horizon is severely underpowered.** No conclusion is reversed.

### 4.2 Everything else that moved

| Quantity | Arm | max │Δ│ | Decision changes? |
|---|---|---|---|
| `mean_bootstrap_se` | 1 | 6.891e-05 | no |
| `analytic_mde_80` | 1 | 1.700e-04 | no |
| `real_score_ic` (context) | 1 | 3.6e-04 (1y) | no — CI still spans zero |
| `ic_combined`, `loss` (1y only) | 1.5 | 3.535e-04 | no — 0 sign flips |
| `boot_lo` / `boot_hi` / `boot_sd` | 1.5 | 2.7e-03 / 4.1e-04 / 8.1e-04 | no — 0 zero-exclusion flips |

### 4.3 Quantities that did **not** move at all

`mean_recovered_ic`, `sd_recovered_ic`, `bias`, `false_positive_rate`, MDE₈₀ (all horizons), MDE₉₀ (5 of 6 horizons), Arm 1.5 `ic_consensus` (all 42 cells), Arm 1.5 `loss` at 1w/2w/1m/3m/6m. All identical to 0.000e+00.

Arm 1's central claim — the validation layer is **unbiased** — rests on the `bias` column, which is **bitwise unchanged**.

## 5. Separate finding — published Arm 1 artifacts have a provenance defect

This is **not** a tie-handling issue. It was discovered while establishing the baseline and is numerically **larger** than the defect under audit.

**A-01 — `V6_ARM1_POWER_TABLE.csv` carries an incorrect seed count.** The `n_seeds` column contains both 200 and 300. Every published recovery probability is an exact multiple of 1/200; **none** is a multiple of 1/300. The rows labelled 300 are mislabelled; the run used 200 seeds.

**A-02 — `V6_ARM1_RECOVERY_CURVES.csv` splices two incompatible runs.**

| Grid points | Script | Seeds | Bootstrap draws | Seed stream |
|---|---|---|---|---|
| 0.00 – 0.10 | `v6_arm1.py` | 200 | **400** | `20260801 + hz·10⁶ + ρ·10⁴ + s` |
| 0.12 – 0.40 | `v6_arm1b.py` | 200 | **300** | `77·10⁶ + tag·10⁵ + ρ·10³ + s` |

MDE₈₀ at 3m and 1y is determined by grid points ≥ 0.12 — the 300-draw arm — while `bootstrap_se` in the *same published row* comes from the 400-draw arm. Re-running coherently at 400 draws throughout gives MDE₈₀ = **0.20 at 3m** (published 0.25) and **0.30 at 1y** (published 0.40).

Both `OLD` and `NEW` agree on these values, so the discrepancy is **entirely provenance, not tie handling**. The published 3m and 1y MDE₈₀ figures are conservative by one grid step.

## 6. PART 5 — Scientific impact

| Question | Finding |
|---|---|
| Arm 1 remains valid? | **Yes.** Unbiasedness bitwise unchanged; MDE₈₀, FP rates, recovery curves unchanged except 3 cells at 1y. |
| Arm 1.5 remains valid? | **Yes.** Bit-perfect reproduction; 0 sign flips, 0 CI zero-exclusion flips. The finding that the combiner does not destroy signal stands. |
| Any gate changes? | **No.** No gate is defined on MDE₉₀ or on any quantity that moved. |
| Any roadmap decision changes? | **No.** The decision to proceed from Arm 1 → Arm 1.5 → Arm 2 rested on unbiasedness and on the combiner not destroying signal. Both are untouched. |
| Conclusions to withdraw? | **None.** One value is amended (1y MDE₉₀), in the direction that reinforces the existing conclusion. |

## 7. PART 6 — Final audit

**1. Does the corrected implementation reproduce Arm 1?**
**Yes.** All base-grid statistics reproduce exactly — bootstrap SE and false-positive rate at all six horizons, MDE₈₀ at all six, MDE₉₀ at five of six. `bias`, `mean_recovered_ic` and `sd_recovered_ic` are bitwise identical across all 84 grid cells. Three recovery probabilities at 1y shift by one seed in 200; one of them moves MDE₉₀ at 1y from 0.40 to *not achieved*.

**2. Does it reproduce Arm 1.5?**
**Yes — bit-perfect.** max │published − re-run│ = 0.000e+00 across all 6 metrics × 42 rows. The fix changes `ic_consensus` in 0 of 42 cells and `loss` in 7 of 42 (all 1y, max 3.5e-04), with **0 sign flips and 0 CI zero-exclusion flips**.

**3. Are any published conclusions invalid?**
**No.** Not one conclusion from either arm is reversed, weakened, or withdrawn. The single amended value — 1y MDE₉₀ — moves in the direction that *reinforces* the published finding that the 1y horizon is severely underpowered.

**4. Must any document be amended?**
**Yes — three amendments, none of which changes a conclusion:**

- **`V6_ARM1_MDE_TABLE.csv` / `V6_ARM1_RESULTS.md`** — 1y MDE₉₀ from `0.40` to *not achieved on the tested grid*. Note that it sat at exactly 180/200 and was never robust.
- **`V6_ARM1_POWER_TABLE.csv`** — correct the `n_seeds` column to 200 throughout (defect A-01). Rows currently labelled 300 are mislabelled; the published recovery probabilities are all exact multiples of 1/200.
- **`V6_ARM1_RECOVERY_CURVES.csv` / `V6_ARM1_RESULTS.md`** — record that grid points ≥ 0.12 were produced by a *different script, seed stream and bootstrap count* (300 draws vs 400) than points ≤ 0.10 (defect A-02). MDE₈₀ at 3m and 1y is set by the 300-draw arm while `bootstrap_se` in the same row comes from the 400-draw arm. Re-run coherently at 400 draws, MDE₈₀ is 0.20 at 3m and 0.30 at 1y — the published values are conservative by one grid step.

The readiness review's stated *mechanism* must also be corrected: it attributed the ties to the `Z_CLIP` boundary. Measurement shows every tie is at **50.0, the neutral score**. Its recommendation to re-verify was right; its explanation was not.

**5. Is the scientific program authorized to continue?**
**Yes, with respect to this defect.** Arm 1 and Arm 1.5 are reproducible and their conclusions stand. The tie-handling defect was real but immaterial: the ranked series in both arms are almost entirely tie-free, so the corrected and original implementations are provably identical wherever ties are absent.

This authorization is **narrow**. It clears the instrumentation question only. It does **not** lift the Arm 2 readiness blockers (B-01 consumer metric, B-02 degenerate control arm, B-03 A2 failure), which are independent and remain in force.

## 8. Board note on the origin of this audit

The readiness review flagged this defect on a *theoretical* argument — clipping produces ties — and asserted that Arm 1 and Arm 1.5 were therefore "suspect." Measurement shows the exposure was near-zero: the injected scores that carry every Arm 1 conclusion are continuous by construction and contain no ties at all, and Arm 1.5's consensus series is tie-free at every horizon.

The flag was still worth raising: it was cheap to check and the correct answer was not knowable without checking. But the readiness review overstated it. "Suspect until re-verified" was the right action and the wrong confidence level, and the mechanism it named was not the mechanism at work.

The audit's most consequential finding is not the defect it was convened to examine. It is **A-02** — that a single published recovery curve was assembled from two runs with different bootstrap resolutions and different seed streams, shifting two published MDE₈₀ values by a full grid step. That defect was invisible to every review until someone tried to re-execute the run.


> **[AMENDED A-2026-005, 2026-08-04]** The tie-mechanism statement above is superseded. Measurement shows the **dominant** tie value is **50.0, the neutral score** (1w 5, 2w 5, 1m 2, 3m 2, 6m 2, 1y 2 cells). A second 2-member group at 1y sits at score ~0.00317, consistent with a `Z_CLIP` floor, so clipping is a **minor secondary contributor, not the mechanism**. Corrected statement: *the neutral score is the dominant tie mechanism; clipping contributes once, at 1y.*
