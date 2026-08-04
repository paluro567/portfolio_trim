# V6 Arm 2 — Addendum A

**Status: DRAFT — UNSIGNED, UNHASHED, NOT BINDING.**

Addendum A becomes binding only when (a) the readiness blockers are resolved or amended by the Preregistration Committee, (b) the repository is clean and committed (R2/R8), and (c) the R9 hash set is computed over that commit. None of the three holds. Per the standing instruction — *do not mark signatures complete without human evidence* — **no signature block is filled in.**

## A.1 Selected feature (R4)

| Field | Value |
|---|---|
| Name | `ret_21d` |
| Definition id | 3 |
| Version | 1 |
| Scope | instrument |
| `uses_adjusted_prices` | true |
| Description | 21-session total return on adjusted close |
| Coverage | 1.000000 (37,876 / 37,876) |
| Instruments | 10 |
| Date range | 2010-02-03 → 2026-07-31 |
| κ (panel SD) | **0.129007** |
| Selection path | Step 1 → 27 injectable; Step 2 → max consumer count 6, unique. Steps 3–4 never fired |

## A.2 Consumer / non-consumer sets (R4)

**As produced by the frozen rule — recorded because the rule requires it, and contested below.**

- CONSUMERS (6): `earnings_behavior`, `macro_regime`, `momentum_exhaustion`, `relative_strength`, `sector_rotation`, `valuation`
- NON-CONSUMERS (1): `interest_rate_sensitivity`
- Exhaustive (union = 7) and mutually exclusive (intersection = ∅): **proven**

**Measured contradiction (B-01).** 5 of the 6 recorded consumers are byte-identical under a ρ = 0.30 injection. They reference `ret_21d` only inside `_latest_feature_date()`, reading `series.index[-1]` — a date, never the value. The measured consumer set is `{momentum_exhaustion}`, n = 1.

These sets are recorded **as the rule produced them and as measurement contradicts them**. They are not reconciled here; reconciliation requires an amendment, which is the Committee's to make.

## A.3 Restored panel manifest (R3) — class B (approximate)

- Schema: 86 tables, 11 migrations
- Universe: 78 instruments, 11 sectors, 29 industries
- Calendar: 4,419 sessions, 2010-01-04 → 2027-07-30
- Prices: 38,086 rows, 10 symbols
- Macro: 25,910 observations, 18 FRED series
- Features: 69 definitions; 855,418 instrument + 100,739 market values
- Zero-coverage features: 19 (10 fundamental, 4 earnings, 4 sector-relative, 1 breadth)
- Injection panel: 771 cells, 6 symbols × 131 dates, 2012-01-03 → 2025-06-12, 26-session grid
- Excluded: HNST (history begins 2021-05-04, insufficient lookback)

## A.4 Frozen experimental constants (transcribed, unchanged)

- Injection: `f_i(ρ) = f_i + κ·ρ·Φ⁻¹(rank(y_i))`
- ρ grid: {0.00, 0.05, 0.10, 0.15, 0.20, 0.30}; PRIMARY ρ = 0.10
- Primary endpoint: `TRANSMISSION = IC_M / IC_F`
- A1: `IC_F` CI lower > 0.05
- A2: `ACTIVATION_SHIFT ≥ 0.02` OR `|SIGNAL_ALIGNMENT|` CI excludes zero
- Decision: VOID if A1/A2 fail; PASS if CI_lower > 0.75; FAIL if CI_upper < 0.50; else INCONCLUSIVE
- Saturation: TRANSMISSION > 0.50 excludes a model from the primary aggregate
- Program rule: FAIL at ≥2 horizons with n ≥ 400 → PROGRAM FAIL
- `SEED_BASE` = 20260801; ≥200 placebo seeds
- S5: runtime > 3× the Addendum-A benchmark → HALT

## A.5 Runtime benchmark (R5)

**0.615 s per cell**, all 7 models × 6 horizons, with the hook active.
Main sweep 47.4 min; placebo arm 26.3 h serial, ≈3.3 h at 8-way parallelism.

**Caveat binding on S5:** this benchmark was taken on a substrate where 3 of 7 models short-circuit on absent fundamentals. A restored substrate will be slower. S5's 3× threshold must be re-derived against the substrate actually used, or it will fire spuriously.

## A.6 Model source

Commit `1b2aec9f935a6f4792e00d0e7f684cc37ef05ebd`, branch `main`, **working tree dirty (56 paths)**. Source hashes are deliberately omitted — a hash over a dirty tree certifies nothing. To be filled when R2/R8 close.

## A.7 Defects recorded against this addendum

| ID | Severity | Summary |
|---|---|---|
| B-01 | CRITICAL | Consumer metric counts name mentions, not value reads; 5 of 6 consumers are boilerplate `_latest_feature_date()` |
| B-02 | CRITICAL | Max-consumer rule minimises the control arm; control n = 1 |
| B-03 | CRITICAL | A2 fails at every ρ (0.00415 @ 0.10; 0.00793 @ 0.30; threshold 0.02) → foreseeable VOID |
| B-04 | MAJOR | 3 of 7 models emit constant output; IC undefined |
| B-05 | MAJOR | Fundamentals/earnings not PIT-restorable; no substitution made |
| D-04 | MAJOR | Tie-unaware ranking; fixed here, **also present in Arm 1 and Arm 1.5** |

## A.8 Signatures

| Role | Name | Date | Signature |
|---|---|---|---|
| Readiness and Restoration Lead | — | — | *unsigned* |
| Preregistration Committee Chair | — | — | *unsigned* |
| Program Board | — | — | *unsigned* |

*No signature is recorded. No human evidence of sign-off exists.*
