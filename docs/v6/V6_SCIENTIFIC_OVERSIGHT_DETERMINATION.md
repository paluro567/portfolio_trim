# V6 Program — Independent Scientific Oversight Determination

**Date:** 2026-08-02 · **Scope:** whether the V6 program has reached a genuine scientific stopping point
**Evidence base:** completed experiments (Arm 1, Arm 1.5, paired baseline), the reproducibility audit, amendments A-2026-001…005, the Arm 2 readiness review, and Amendment B. No new computation was performed.

---

## PART 1 — Is Arm 2 blocked by science, or by the surviving repository?

Four candidate explanations were put to the evidence. Three are rejected; two hold jointly.

### (a) "The scientific hypothesis cannot currently be tested" — **REJECTED**
The hypothesis — *does injected feature information propagate to consuming models and not to non-consumers?* — is well-posed and testable. Amendment B demonstrates a valid instrument exists: A1 fires (IC_F rose monotonically +0.2267 → +0.3043 → +0.4715 with ρ), and the Stage-2 causal probe detects real dependencies cleanly (`ret_63d` → `momentum_exhaustion` in 148/150 cells). Nothing about the *question* is untestable. The instrument works; there is nothing to point it at.

### (b) "The surviving repository no longer contains sufficient independent models" — **CONFIRMED. This is the operative cause.**
Measured: 3 of 7 official models emit constant output (`earnings_behavior`, `sector_rotation`, `valuation`). Of the 4 LIVE models, `macro_regime` and `interest_rate_sensitivity` consume **only market-scope macro features** and never read an instrument-scope price feature. The remaining two have **disjoint** dependency sets. Across 23 candidate features at ±2σ, and 4 candidates at up to ±8σ over 150 cells, the maximum genuine consumer count is **exactly 1**.

### (c) "The original research environment has become irrecoverable" — **REJECTED**
Recovery succeeded, and quickly. The database rebuilt to 86 tables; 38,086 price rows ingested in 9 seconds; the feature surface (855,418 rows, 69 definitions) rebuilt in 44 seconds; the Arm 1/1.5 substrate survived byte-intact (`merged.csv` md5 `aa1c82bd…`, 51,025 rows) and Arm 1.5 reproduced **bit-perfectly** (0.000e+00 across 6 metrics × 42 rows). What did not return is PIT fundamentals and earnings — which were never locally reproducible and are a **vendor** gap, not a recovery failure.

### (d) "The design asks for evidence the repository was never capable of producing" — **CONFIRMED, and this is the sharper finding**
The preregistration selected its feature by **counting name occurrences in source**. That count never measured whether any model could respond to a value change. Measurement later showed 5 of `ret_21d`'s 6 counted consumers were byte-identical under a ρ=0.30 injection — they referenced the feature only through a copy-pasted `_latest_feature_date()` helper reading a **date**.

The consequence is not merely that the surviving repository fails the requirement. It is that **the preregistration's feasibility was never established on any repository, surviving or original.** The syntactic count manufactured an appearance of feasibility that no measurement supported. Had the original environment been fully intact, no completed evidence shows the requirement would have been met either — because the requirement was never checked.

### Determination
Arm 2 is blocked by **(b) the model population** and **(d) an unverified design premise**, not by science and not by irrecoverable data. The blocker is structural and was latent from the moment the preregistration was frozen.

---

## PART 2 — Has the program reached an information limit?

### Answerable now, from the surviving repository

| # | Question | Blocked by | Status |
|---|---|---|---|
| Q1 | Does repairing `se ≡ \|effect/z\|` close the production-vs-equal-weight gap? | nothing | **Open, free, decision-changing** |
| Q2 | What is σ_true, the cross-sectional IC dispersion? | nothing | Open, free |
| Q3 | Do `rel_ret_sector_*` features have ≥2 genuine live consumers? | sector-ETF prices absent from `universe.yaml` (config, not vendor) | **Open, free, untested** |
| Q4 | Why do 3 of 7 models emit constant output? | nothing | **Answered** — absent fundamentals/earnings/sector inputs |
| Q5 | Is the validation layer unbiased and efficient? | nothing | **Answered** — Arm 1: yes |
| Q6 | Does the evidence combiner destroy signal? | nothing | **Answered** — Arm 1.5: no |
| Q7 | Does the ensemble beat a naive constant-50% predictor? | nothing | **Answered — NO, at all 6 horizons on Brier** |

### Require restoring historical research or new data

| # | Question | Blocked by |
|---|---|---|
| Q8 | Does feature information propagate to ≥2 consuming models? | **insufficient model diversity** — contingent on Q3 |
| Q9 | Do fundamentals-driven models (`earnings_behavior`, `valuation`) contribute skill? | **missing PIT data** — vendor blocked |
| Q10 | Would a broader universe change the power picture? | missing data (free feed extensible); prior finding: breadth **saturates** |

### Permanently unanswerable from this repository

| # | Question | Why |
|---|---|---|
| Q11 | What were the exact original (pre-loss) production scores? | **irrecoverable artifacts** — the restored panel is class B (approximate), never a reproduction |
| Q12 | Would the original 7-live-model configuration have satisfied Arm 2's consumer requirement? | irrecoverable — the configuration no longer exists and was never measured causally while it did |

### Determination
The program has **not** reached an information limit. **Arm 2** has. Three open questions (Q1, Q2, Q3) are answerable at **zero data cost**, and Q1 is decision-changing in both directions.

---

## PART 3 — Should Arm 2 exist at all?

### Conclusion: **PERMANENTLY RETIRE ARM 2 AS PREREGISTERED**

Three independent grounds, each from completed evidence:

**1. It is not executable, and the obstacle is structural.** Maximum genuine consumer count is 1; the design requires ≥2. Not a threshold that can be tuned — a property of the model population.

**2. Its feasibility premise was never verified.** The design was frozen on a syntactic count that measurement falsified. A preregistration whose central selection rule does not measure what it claims cannot be repaired by re-running it; the frozen artifact is unsound at its root.

**3. Its decision value is now low regardless of outcome.** Arm 2 exists to localize where signal is lost. Arm 1 established the validation layer is unbiased and efficient. Arm 1.5 established the combiner does not destroy signal. Arm 2 would have closed that chain. But the chain's *purpose* was to explain why the platform underperforms — and that question already has a specific, code-level answer: equal-weight beat production on **shrinkage alone** (96–104% of the gap), caused by `se ≡ |effect/z|` overconfidence plus Jensen. Arm 2 does not test that mechanism. Whether it passed or failed, the diagnosed defect would remain untested and the established finding — the ensemble loses to a constant 50% predictor at every horizon — would remain unchanged.

### What survives
The **propagation question** remains scientifically legitimate. It may be re-proposed only as a new, separately preregistered experiment whose feasibility is **demonstrated by Stage-2 causal measurement before freezing** — the discipline whose absence caused this failure. Amendment B's consumer definition, control requirements, A2 checkpoint and interpretation matrix are sound and should be **retained as reusable methodology**, independent of Arm 2's retirement.

Arm 2 does not proceed as preregistered, is not redesigned into executability, and is not kept alive pending restoration.

---

## PART 4 — Lowest-cost path to new information, ranked by EVI

| Rank | Action | Cost | Could it change a decision? | EVI |
|---|---|---|---|---|
| **1** | **Repair `se ≡ \|effect/z\|` and re-run the paired baseline** | $0, low hours | **Yes, in both directions.** Success → the only established performance failure has a fixable cause and the platform's premise survives. Failure → decisive grounds to terminate. | **Highest** |
| 2 | Ingest sector ETFs; re-run Stage-2 on `rel_ret_sector_*` | $0, ~1 hour | Yes — the **only** free action that could revive a dead model (`sector_rotation`) and populate the 4 features never tested | High |
| 3 | Measure σ_true on the restored panel | $0 | No by itself; corrects every future power calculation (prior power arithmetic was wrong twice) | Moderate |
| 4 | Restore PIT fundamentals (vendor) | $$$, previously rejected twice | Only if #1 succeeds; otherwise buys data for models whose value is unestablished | Low now |
| 5 | Execute another injection experiment | — | Blocked; no eligible feature exists | None |
| 6 | Terminate the program | — | Premature while #1 is untried at $0 | Negative now |

### Why #1 outranks #2
Action #2 is cheaper in judgment but instrumental: it unblocks an experiment this Committee has just retired. Action #1 attacks the **single diagnosed cause of the only established failure**, costs nothing, and is decision-changing whichever way it resolves. That is the definition of maximum expected value of information.

**Note on #2:** `rel_ret_sector_5d/21d/63d/126d` were excluded from the 23-candidate census because they hold **zero non-null values** — sector ETFs are absent from `universe.yaml`, which lists only SPY, QQQ and IWM. They are the only untested candidates in the repository, and the gap is configuration, not vendor. Whether they yield ≥2 genuine consumers is **unknown and untested** — this Committee does not assert that they would.

---

## PART 5 — Final decision

**1. Has the current repository reached its scientific information limit?**
**No — for the program. Yes — for Arm 2.** Three questions remain answerable at zero data cost (Q1, Q2, Q3), and Q1 is decision-changing in both directions.

**2. Is Arm 2 still scientifically executable?**
**No.** Maximum genuine consumer count is 1 against a requirement of 2, confirmed at up to ±8σ across 150 cells. The constraint is the model population, not the feature, injection, checkpoint, or endpoint.

**3. Exact prerequisite before Arm 2 could ever become executable**

> **At least two LIVE models that, by Stage-2 causal-response test, genuinely consume one common feature satisfying E3–E6 — together with at least two LIVE genuine non-consumers of that same feature.** Four live models with overlapping-but-not-identical dependency structure, established by measurement before any design is frozen.
>
> On this repository there is exactly one free route: ingest sector ETFs, revive `sector_rotation`, and demonstrate that a `rel_ret_sector_*` feature has ≥2 genuine live consumers. **If that test fails, the prerequisite requires PIT fundamentals** to revive `earnings_behavior` and `valuation` — a vendor purchase rejected twice on prior evidence.

**4. Single highest-value activity for the entire project**
**Repair the `se ≡ |effect/z|` recovered-standard-error defect and re-run the paired baseline against equal-weight and constant-50%.** It is free, it targets the only established performance failure, its cause is already diagnosed to a specific line of code, and both possible outcomes change what the program should do next.

**5. Has the program reached a natural stopping point pending restoration?**
**Arm 2 has reached a permanent stopping point — retirement, not suspension: restoration is neither necessary nor sufficient to justify it. The program has not.** Stopping now would forgo a zero-cost test of the one defect already identified as the cause of the platform's only measured failure. The program should stop **after** that test, if it fails.

---

### Committee note

The V6 program's instrumentation is now better understood than its subject. Arm 1 proved the ruler is unbiased. Arm 1.5 proved the combiner is faithful. The audit proved both are reproducible. Amendment B built a rigorous definition of feature consumption — and the first honest application of it found nothing to measure.

Four increasingly careful examinations of the measuring apparatus have not tested the claim the platform exists to make. The established finding on that claim remains what the paired baseline reported: **the ensemble loses to a constant 50% predictor at all six horizons.** One diagnosed, unrepaired, zero-cost defect stands between that finding and a verdict. It should be repaired and the comparison re-run before anything else is built, bought, or preregistered.
