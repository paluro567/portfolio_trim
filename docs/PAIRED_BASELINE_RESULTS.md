# Paired Baseline Comparison — Results

Executed against [EXPERIMENT_PREREGISTRATION.md](EXPERIMENT_PREREGISTRATION.md), frozen before any
comparative result was viewed. Driver: scratchpad only; **no `src/` changes**. All systems
reconstructed through the production combiner via the shipped `mip.validation.systems.combine_rows`.

---

## 1. Part 1 — Research inventory, data audit, and BLOCKING FLAWS

### 1.1 STOP — two critical flaws found before execution

#### F1 — The production database has been destroyed (CRITICAL)

| Database | Tables | Size | State |
|---|---|---|---|
| `mip` | **1** (`alembic_version`, **no version row**) | 8.4 MB | **Data lost** |
| `mip_scratch` | **1** (`alembic_version`, no version row) | 8.3 MB | Data lost |
| `mip_test` | **0** | 47 MB | Empty |

Gone: `daily_prices`, `instruments`, `feature_store_daily`, `feature_store_market_daily`,
`company_fundamentals`, `earnings_observations`, `macro_observations`, `predictions`,
`prediction_outcomes`, the portfolio ledger, all 7 Phase 1 `security_master` tables, and all 13
Phase 2A native-outcome tables. The alembic version marker is also cleared, so the schema is not
merely dropped — the migration state is unrecoverable from the DB.

**Recoverable:** the schema (16 migrations in `alembic/versions`), prices/macro (re-ingestible from
yfinance/FRED), the 52-position portfolio (`data/peter_real_opening_balances_2026-07-16.csv`
survives).
**Not recoverable:** the single PIT fundamentals snapshot (2026-07-04) — `valuation` cannot be
un-inerted any faster than a fresh year of accumulation; the archived `predictions` history (the
immutable evidence archive and every `what_changed` baseline).

#### F2 — The shipped harness scores each system against its own target (CRITICAL)

`mip/validation/metrics.py::prepare()` computes
`realized_excess = actual − (expected_return − expected_excess)` — the **model's own implied
baseline** — and derives `hit` from it. Therefore `block_bootstrap_delta(metric="hit")` differences
two `hit` columns defined against **two different targets**. That is not a valid paired comparison,
and for `always_neutral` (no `expected_return` at all) it is undefined.

It is also the same mis-specification `ONEYEAR_DECOMPOSITION.md` §2 blamed for the withdrawn +0.17.

**Action taken:** all inference below uses **system-independent** targets — `spy_rel` (primary, T1)
and `actual` (T2). The shipped `hit`/`realized_excess` are excluded and reported once as a diagnostic
(§5.4).

### 1.2 What the experiments could still use

The only surviving panel with **both** per-model scores and realized outcomes:
`data/validation/analogue_v1/embargoed_revalidation/` — the embargo-hardened (leakage-free) capture.

| Property | Value |
|---|---|
| Per-model prediction rows | **62,100** |
| Unique securities | **7** (ADBE, AMD, AMZN, CRM, HNST, NOW, TSLA) |
| Scoring dates | **189** |
| Date range | **2019-01-02 → 2026-06-26** |
| Horizons | 1w, 2w, 1m, 3m, 6m, 1y |
| Avg securities per scoring date | **7.00** |
| Outcome cells complete | **7,290 / 7,584 (96.1%)** |
| Duplicate predictions / outcomes | **0 / 0** |
| Complete cases across all systems | **7,290 (no differential attrition)** |
| Valid cells after non-overlap cohort @1m | **419** |
| Valid cells after non-overlap cohort @1y | **45** |

**Production/research mismatch check:** the `baseline` system in the capture = the 7 official models
with `historical_analogues` excluded. Production today has
`SHADOW_MODELS = {historical_analogues, conditional_probability}`, so production's official ensemble
is **exactly** this 7-model set. **No mismatch.**

### 1.3 Missingness and activation by model

| Model | Rows | Missing vs grid | **Neutral share** |
|---|---|---|---|
| `valuation` | 7,938 | 0 | **1.000 — fully inert, ZERO directional calls** |
| `earnings_behavior` | 7,938 | 0 | **0.897** (10.3% activation) |
| `relative_strength` | 7,938 | 0 | 0.172 |
| `momentum_exhaustion` | 7,938 | 0 | 0.097 |
| `macro_regime` | 7,584 | 354 | 0.025 |
| `interest_rate_sensitivity` | 7,584 | 354 | 0.014 |
| `sector_rotation` | 7,602 | 336 | 0.013 |
| `historical_analogues` (shadow) | 7,578 | 360 | 0.060 |

`valuation`'s inertness is confirmed empirically at 100%: it contributes **nothing** to any cell.
The production "7-model" ensemble is operationally a **6-model** ensemble, and a **5.1-model**
ensemble once `earnings_behavior`'s 10% activation is weighted in.

### 1.4 Experiments invalidated by F1 (not run, not reported as null)

- **12-1 cross-sectional momentum baseline** (system C) — requires price history. **Substituted** by
  `momentum_exhaustion` alone (system F), declared in the preregistration. F is a weaker comparator
  than C: it was built inside this project, whereas C is a literature-standard external null.
- **Sector stability** — the sector map is gone.
- **Turnover-adjusted portfolio outcomes** — preregistered as *not evaluated*; the portfolio
  simulation is untrustworthy on this panel and its ledger is destroyed.
- **Broad-panel cross-sectional correlation** — see [POWER_FEASIBILITY_REPORT.md](POWER_FEASIBILITY_REPORT.md).

---

## 2. Level metrics — primary horizon 1m, target T1 (`spy_rel`), non-overlapping cohort

| System | n | Dir acc | Rank IC (pooled) | Rank IC (within-date) | Brier | Tercile spread | High-conv hit |
|---|---|---|---|---|---|---|---|
| **A — production 7-model** | 419 | 0.5131 | **−0.0209** | +0.0086 | **0.3022** | −0.0107 | 0.5333 |
| E — equal-weight | 419 | **0.5322** | +0.0054 | **+0.0440** | **0.2583** | −0.0026 | 0.5429 |
| B — always-neutral | — | *no call by construction* | *undefined* | *undefined* | **0.2500** | — | — |
| F — `momentum_exhaustion` only | 400 | 0.5175 | +0.0677 | +0.0689 | 0.3103 | +0.0176 | 0.5900 |
| D — `relative_strength` only | 360 | 0.5250 | +0.0368 | +0.0493 | 0.3055 | 0.5333 | — |
| D — `sector_rotation` only | 419 | 0.5155 | −0.0489 | +0.0077 | 0.3059 | −0.0091 | 0.4857 |
| D — `interest_rate_sensitivity` only | 417 | 0.5132 | +0.0564 | −0.0113 | 0.3116 | +0.0072 | 0.5143 |
| D — `macro_regime` only | 414 | 0.4758 | −0.0706 | −0.0213 | 0.3389 | −0.0010 | 0.5636 |
| D — `earnings_behavior` only | 50 | 0.4400 | −0.0745 | −0.3000 | 0.3370 | −0.0015 | 0.5385 |
| D — `valuation` only | **0** | *inert* | — | — | — | — | — |

**Designated "strongest single model" (D):** `momentum_exhaustion`, by pooled rank IC at 1m (+0.0677).
Note this designation is a post-hoc selection over 7 candidates and therefore biases D *upward* as a
comparator — conservative for A's claim, as preregistered.

### Production ensemble across all horizons (T1)

| Horizon | n | Dir acc | Rank IC (pooled) | Rank IC (within-date) | Brier | Tercile spread |
|---|---|---|---|---|---|---|
| 1w | 1259 | 0.5083 | +0.0143 | −0.0059 | 0.3144 | −0.0000 |
| 2w | 1259 | 0.5123 | +0.0114 | −0.0290 | 0.3068 | +0.0017 |
| **1m** | 419 | 0.5131 | −0.0209 | +0.0086 | 0.3022 | −0.0107 |
| 3m | 178 | **0.4663** | −0.0052 | +0.0053 | 0.3208 | −0.0591 |
| 6m | 92 | **0.4565** | **−0.1067** | +0.0082 | 0.3515 | −0.1930 |
| 1y | 45 | **0.4667** | **−0.1931** | −0.1184 | 0.3693 | **−0.5991** |

On the **embargo-hardened** grid against a **system-independent** target, the ensemble's directional
accuracy is **below coin-flip at 3m, 6m and 1y**, and pooled rank IC is **negative** at four of six
horizons. The 1y tercile spread is **−0.60** (top tercile underperformed bottom by 60 pp of
SPY-relative return) on n=45 — noise-dominated, but the *opposite sign* to the withdrawn headline.

---

## 3. Paired comparisons — primary metric (dir acc on T1), primary horizon 1m

Paired on identical `(symbol, as_of, horizon)` cells. Δ = **A − comparator**; positive favours the
production ensemble.

| Comparator | n | Δ dir acc | 95% CI (symbol-block) | 95% CI (year-block) | Share of draws > 0 | **Classification** |
|---|---|---|---|---|---|---|
| **E — equal-weight** | 419 | **−0.0191** | [−0.0421, **+0.0047**] | [−0.0455, +0.0045] | **0.05** | **Inconclusive** (leans against A) |
| F — momentum only | 400 | +0.0025 | [−0.0505, +0.0577] | [−0.0463, +0.0662] | 0.53 | Inconclusive |
| D — `macro_regime` | 414 | +0.0338 | [−0.0190, +0.0905] | [−0.0121, +0.0765] | 0.88 | Inconclusive |
| D — `interest_rate_sensitivity` | 417 | +0.0000 | [−0.0448, +0.0448] | [−0.0395, +0.0444] | 0.49 | Inconclusive |
| D — `relative_strength` | 360 | +0.0028 | [−0.0430, +0.0484] | [−0.0333, +0.0445] | 0.52 | Inconclusive |
| D — `sector_rotation` | 419 | −0.0024 | [−0.0467, +0.0397] | [−0.0506, +0.0450] | 0.44 | Inconclusive |
| D — `earnings_behavior` | 50 | +0.0600 | [−0.0536, +0.1607] | [−0.0690, +0.2059] | 0.80 | Inconclusive |
| B — always-neutral | — | *undefined* | — | — | — | *see §4* |

**Holm-Bonferroni** over the 4-member confirmatory family (B, D, E, F @1m): no comparison approaches
nominal significance on the primary metric, so the correction changes nothing.

**Every directional-accuracy comparison is INCONCLUSIVE** by the frozen criteria (CI includes 0 and
extends beyond ±0.02). Per the preregistration, this is **not** evidence of equality — every CI is
2–5x wider than the MEMD.

**The one directional signal:** against equal-weight, **95% of bootstrap draws are negative** and the
point estimate (−1.9 pp) sits at the MEMD boundary. The production correlated-fixed-effect weighting
*underperforms* a plain arithmetic mean of the same seven models. Not significant; not ignorable.

---

## 4. Paired comparisons — Brier score. **The decisive result.**

Δ = A − comparator. Brier is a **loss**, so **positive Δ means the production ensemble is WORSE.**

| Horizon | Δ vs **always-neutral** | 95% CI | Δ vs **equal-weight** | 95% CI |
|---|---|---|---|---|
| 1w | **+0.0642** | [+0.0493, +0.0778] | **+0.0542** | [+0.0443, +0.0632] |
| 2w | **+0.0565** | [+0.0424, +0.0694] | **+0.0484** | [+0.0388, +0.0567] |
| **1m** | **+0.0519** | [+0.0306, +0.0738] | **+0.0436** | [+0.0302, +0.0563] |
| 3m | **+0.0700** | [+0.0352, +0.0992] | **+0.0573** | [+0.0368, +0.0736] |
| 6m | **+0.0994** | [+0.0540, +0.1193] | **+0.0742** | [+0.0413, +0.0884] |
| 1y | **+0.1142** | [+0.0384, +0.1508] | **+0.0859** | [+0.0345, +0.1080] |

### **Twelve comparisons. One direction. Every confidence interval excludes zero.**

Survives Holm-Bonferroni trivially. **Classification: baseline clearly superior — the production
ensemble's probabilistic forecasts are worse than a constant 50%, and worse than an equal-weighted
average of its own components, at every horizon.**

**Mechanism (arithmetic, not inference).** Always-neutral emits `p_up = 0.5`, so its Brier is exactly
0.2500 on any binary outcome. The production ensemble's Brier @1m is 0.3022. Since directional
accuracy is ≈ 0.5131 — i.e. essentially no skill — every unit of confidence the combiner expresses by
pushing the score away from 50 is a **pure loss**. Equal-weight averaging shrinks scores toward 50
(Brier 0.2583) and is therefore better; always-neutral shrinks all the way and is best.

**This is systematic overconfidence, measured at the ensemble level, on a system-independent target,
with CIs excluding zero at all six horizons.** It independently confirms the analogue RCA's RC1
finding ("the `se` recipe overstates precision ~2x") and shows it is not confined to the analogue
model — it is a property of the production combination path.

**Preregistration gap, disclosed:** no MEMD was declared for Brier (only for dir-acc and rank IC).
The frozen equivalence bands therefore cannot be applied to these figures. They are reported as a
clear directional finding with CIs excluding zero — **not** retrofitted against a threshold invented
after the fact.

---

## 5. Robustness

### 5.1 Stability by calendar year (Δ dir acc @1m)

| Comparator | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|
| vs equal-weight | −0.056 | −0.062 | +0.017 | +0.018 | 0.000 | −0.065 | +0.018 | −0.036 |
| vs momentum only | −0.077 | −0.083 | +0.019 | **+0.200** | 0.000 | 0.000 | −0.018 | −0.037 |
| vs `macro_regime` | +0.019 | +0.042 | −0.071 | −0.036 | +0.073 | +0.065 | **+0.107** | **+0.107** |

- **vs equal-weight:** negative in 5 of 8 years. The deficit is not one bad year.
- **vs momentum only:** the entire comparison is **one year** — 2022 (+0.200, n=50). Remove 2022 and
  A loses to momentum-only on balance. This is the same single-era concentration pattern that
  invalidated the 1y headline.
- **vs `macro_regime`:** A's advantage *grows* in the last two years (+0.107, +0.107) — the only
  pattern in the data that favours the ensemble, and it is unconfirmed at n≈56/yr.

### 5.2 Stability by market regime (SPY direction over the forward window)

| Comparator | SPY up | SPY down |
|---|---|---|
| vs equal-weight | −0.014 (n=278) | −0.028 (n=141) |
| vs momentum only | −0.049 (n=265) | **+0.104** (n=135) |
| vs `macro_regime` | +0.065 (n=276) | −0.029 (n=138) |

A beats momentum-only **only in down markets** and loses in up markets — consistent with the
documented contrarian-mistiming of the price cluster, and it means the F comparison is a regime bet,
not a skill difference.

### 5.3 Sensitivity

| Test | Result |
|---|---|
| Winsorize T1 at 1%/99% | **Identical to 4 dp for every comparison.** Not outlier-driven |
| Complete-cases across all systems | 7,290 — **identical** to per-pair joins. No differential attrition |
| Year-block vs symbol-block bootstrap | Agree throughout (see §3) |
| Missing-data treatment | No sensitivity: attrition is common across systems by construction |

### 5.4 F2 diagnostic — how much did the mis-specified target matter *here*?

| Metric (system A, 1m, pooled) | Value |
|---|---|
| Rank IC vs **model's own baseline** (shipped `realized_excess`) | +0.0126 |
| Rank IC vs **`spy_rel`** (system-independent) | +0.0238 |
| Dir acc vs model's own baseline | 0.5136 |

**Honest note:** on this panel the mis-specification's numerical effect is **small** (both ICs are
within noise of zero), unlike the 1y case in `ONEYEAR_DECOMPOSITION` (+0.17 vs +0.01–0.09). F2 remains
a genuine design defect that *invalidates cross-system pairing in principle*, and it had to be
corrected to run system B at all — but it is not the explanation for the results above.

---

## 6. Model-ablation summary

| Ablation | Finding |
|---|---|
| **Best single model vs ensemble** | Indistinguishable. `momentum_exhaustion` alone: Δ = +0.0025 [−0.0505, +0.0577]. The ensemble adds nothing measurable over its own best component |
| **Equal-weight vs production weighting** | **Production weighting is worse.** Dir acc Δ = −0.0191 (95% of draws negative); Brier Δ = +0.0436 [+0.0302, +0.0563] — CI excludes zero at every horizon. The correlated-fixed-effect combiner is a net negative versus an arithmetic mean of the same inputs |
| **Ensemble minus each model** | Not separately run — the single-model results above bound it, and F1 prevents recomputation on a wider panel. Declared as not evaluated |
| **`valuation` contribution** | Exactly **zero** (100% neutral, 0 calls). It is dead weight in the registry |
| **`earnings_behavior` contribution** | 10.3% activation; standalone dir acc 0.44, rank IC −0.075. Anti-predictive when it fires, on n=50 |

---

## 7. Classification against the frozen criteria

| Comparison | Metric | Classification |
|---|---|---|
| A vs B (always-neutral) | Brier (designated) | **Baseline clearly superior** (directional; no Brier MEMD preregistered) |
| A vs E (equal-weight) | Brier | **Baseline clearly superior** — CI excludes 0 at all 6 horizons |
| A vs E (equal-weight) | Dir acc | **Inconclusive**, leaning against A (95% of draws negative) |
| A vs F (momentum only) | Dir acc | **Inconclusive** — and what signal exists is one year (2022) and one regime |
| A vs D (each single model) | Dir acc | **Inconclusive** in all 7 cases |
| A vs D (`macro_regime`) | Brier | A **better**, Δ = −0.0354 [−0.0626, −0.0074] — the ensemble's one CI-excluding-zero *win* |

**Did the ensemble beat simple alternatives? No.** It is statistically indistinguishable from its own
best single component and from an equal-weighted average on directional accuracy, and it is
**decisively worse than both a constant 50% forecast and an equal-weighted average on Brier**.

**Is any system shown to have positive skill? Not established.** A paired design compares systems; it
cannot show either exceeds zero. Directional accuracies cluster at 0.51–0.53 with the ensemble
*below* 0.50 at three of six horizons.
