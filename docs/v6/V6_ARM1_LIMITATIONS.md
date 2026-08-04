# V6 ARM 1 — LIMITATIONS

Stated so that no reader over-reads the result.

---

## 1 · What Arm 1 measured

**Only the validation layer**: `cohort()` → rank IC → block bootstrap → CI-excludes-zero.
Injection is applied **at the score level**, downstream of features, models, the combiner and the
score-to-probability mapping. **None of those was exercised.**

## 2 · Structural limitations

| # | Limitation | Consequence |
|---|---|---|
| **L1** | **7 symbols only** | The bootstrap blocks on symbols. With 7 groups the block structure is coarse. Behaviour at 100+ symbols is **unmeasured** |
| **L2** | **One era (2019–2026)** | Includes 2020 and 2022 but is a single sample path. Regime-conditional detection is untested |
| **L3** | **Survivor-only panel** | 7 surviving large-cap names, 6 of them tech/growth. Outcome dispersion is not representative |
| **L4** | **i.i.d. Gaussian injected signal** | Real signal is autocorrelated, fat-tailed and time-varying. A realistic signal may be **harder** to detect than the synthetic one |
| **L5** | **Single detection rule** | Only "95% CI excludes zero" on the rank IC. Directional accuracy and Brier were not used as detection statistics |
| **L6** | **Grid quantisation** | MDE is reported at grid points (0.10, 0.15, 0.25, 0.30, 0.40). True MDEs lie between grid values; reported figures are **upper bounds** |
| **L7** | **Extrapolation to n ≈ 12,600 is untested** | ~10× beyond the measured range **and** across a change in block structure. A hypothesis, not a finding |

## 3 · What the result does NOT license

- ❌ *"The pipeline can detect an IC of 0.03."* It cannot, on this data, at any horizon.
- ❌ *"G5 will pass."* Arm 1 does not evaluate G5. The gate needs the full surface and the Arm 2 − Arm 1 gap.
- ❌ *"The models are fine and only the data is small."* Arm 1 injected **downstream of the models** and says nothing about them.
- ❌ *"Past null results were true negatives."* At n = 1,264 the layer needs IC ≈ 0.10. Past studies ran at n = 47–1,264, so **an effect of realistic size (0.03–0.05) would have been missed** — every historical null on this panel is consistent with both "no effect" and "effect present but undetectable."

## 4 · What it does license

- ✅ The validation layer is **unbiased** (max |bias| 0.017).
- ✅ The bootstrap is **well-calibrated for n ≥ ~100** and matches `1/√n` to within 2.3%.
- ✅ **No pipeline defect** stands between the data and the answer *at the validation stage*.
- ✅ The **"blind instrument" hypothesis is ruled out at this scale** — the layer sees signal when signal is present.
- ✅ The analytic `2.486 × SE` formula is **optimistic by ~1.4×** and should not be used.

## 5 · A finding that reframes the project's history

At the 1m horizon (n = 421) the measured MDE(80%) is **0.15**. Every prior study on this panel that
reported "no effect" was operating with a detection floor **three to five times larger than the effect
sizes it was looking for.**

**Those nulls were never evidence of absence.** This is the first measurement in the project's history
that establishes that, and it is measured rather than argued.

## 6 · Reproducibility

Deterministic seeding verified across two `PYTHONHASHSEED` values (identical output).
Primary: 300 seeds × 400 draws. Extended: 200 × 300. Scaling: 150 × 250.
Driver: `scratchpad/v6_arm1.py`, `v6_arm1b.py` — **no `src/` changes, no migrations.**

## 7 · Two defects found in my own instrumentation

| # | Defect | Fix |
|---|---|---|
| 1 | Seeds derived from `hash()` — PYTHONHASHSEED-randomized, breaking reproducibility | Deterministic integer seed derivation; verified |
| 2 | `v6_arm1.py` lacked a `__main__` guard, so importing it re-ran the entire sweep | Second driver made self-contained |

Both were caught before results were recorded. Neither affects the reported numbers.
