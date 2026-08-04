# V5 — DESCRIPTIVE RELIABILITY PLAN

**Objective:** determine whether any evidence source accurately and reproducibly characterises the state
it claims to measure.

> ### V5 DOES NOT TEST RETURN PREDICTION. Any directional analysis in V5 is a protocol violation.

**A source may not reach ADVISORY merely because its values are available.** Availability is not
reliability.

---

## 1 · Eligible source types

| Eligible | Requirement |
|---|---|
| ✅ Makes a **checkable state claim** | An independent verification path exists |
| ✅ Deterministic from PIT inputs | Same inputs → byte-identical claim |
| ✅ Produces ≥20 calendar episodes | Below this, descriptive statistics are unestimable |
| ❌ **Ineligible: unverifiable claims** | If no independent path can confirm the claim, the source **cannot earn descriptive reliability at all** and remains SHADOW permanently |

**The independent verification path is the crux.** A claim such as *"P/E sits at the 94th percentile of
its 10-year range"* is verified by recomputing the percentile through a **different code path and a
different data path**. A source that can only be checked against itself is not checkable.

## 2 · The seven measured dimensions

| # | Dimension | Definition | Method |
|---|---|---|---|
| **R1** | **Coverage** | fraction of (security, date) cells for which a claim is produced | count ÷ eligible cells |
| **R2** | **Completeness** | non-null rate on claimed cells | count |
| **R3** | **PIT integrity** | uses only data available at `as_of` | **price-poisoning test — corrupt every post-`as_of` row, require byte-identical output** |
| **R4** | **Reproducibility** | same inputs → same claim | recompute twice, byte-compare |
| **R5** | **Revision behaviour** | how often a past claim is restated | restatements ÷ claims over a trailing window |
| **R6** | **Stability** | claim persistence vs its own churn | sign-flip rate between consecutive episodes, versus a random-walk null |
| **R7** | **State agreement** | **does the claim match an independent measurement of the state?** | agreement rate against the independent path |

**R7 is the substance.** R1–R6 test hygiene; R7 tests truth.

## 3 · Failure conditions

| Condition | Consequence |
|---|---|
| R3 PIT poisoning fails | **Immediate permanent disqualification.** Look-ahead is not a scoring deduction |
| R4 not reproducible | Immediate disqualification until fixed; version reset |
| No independent verification path | Ineligible; SHADOW permanently |
| R7 < 0.60 | Fail — the source does not describe what it claims |
| R5 > 0.25 | Fail — a claim that restates a quarter of the time is not a measurement |
| Episodes < 20 | Insufficient sample; hold at SHADOW, recompute next quarter |

## 4 · Promotion criteria

### SHADOW → CONTEXT *(G3)*

**All required:**
```
R3 PIT poisoning        PASS (byte-identical)
R4 reproducibility      PASS (byte-identical)
R7 state agreement      ≥ 0.80
R2 completeness         ≥ 0.95 on claimed cells
R1 coverage             ≥ 0.50 of eligible cells
episodes                ≥ 20
independent path        EXISTS and is documented
```
**Grants:** displayed in reports. **Contributes exactly 0.**

### CONTEXT → ADVISORY *(G4)*

**All of CONTEXT, plus:**
```
episodes                ≥ 40
regimes observed        ≥ 2 distinct
R7 stability            ≥ 0.75 in EVERY observed regime (not pooled)
R5 revision rate        ≤ 0.10
R6 stability            sign-flip rate < the random-walk null, CI excluding it
```
**Grants:** may modulate conviction, magnitude, urgency. **May never flip an action.**
Satisfies frozen-decision condition **5B**.

> **Per-regime, not pooled.** A source reliable only in one regime is a regime artifact — the exact
> failure the CPE exhibited.

## 5 · Automatic demotion

Evaluated **quarterly, without discretion**:

| Trigger | Action |
|---|---|
| Any CONTEXT criterion fails on a trailing window | → SHADOW |
| Any ADVISORY criterion fails | → CONTEXT |
| Not evaluated for 2 quarters | **staleness decay** → one tier down |
| Regime transition declared | ADVISORY → CONTEXT until re-established in the new regime |
| Feature-definition or source-version change | **full reset to SHADOW.** Reliability attaches to a *versioned* source, never a name |
| R3 PIT poisoning fails at any time | **permanent disqualification** |

## 6 · Conditioning — deliberately shallow

| Dimension | Condition on it? | Why |
|---|---|---|
| **Horizon** | **Yes, mandatory** | Reliability at 1y says nothing about 1w |
| **Regime** | **Yes, with heavy shrinkage** | Few independent regime episodes exist |
| Sector · market cap · volatility | **NO** | The CPE measured accuracy *decreasing monotonically* as conditioning domains were added (0.641 → 0.600 → 0.609 → 0.545). Deeper conditioning re-creates that failure **inside the ledger**, where it is invisible |

## 7 · Scope and cost

Existing free data · scratchpad drivers · **no `src/` code, no migrations** · 3–5 candidate sources from
the existing registry — **no new sources** · ~8 weeks · **$0**.

**Exit:** the ledger is no longer empty, or it is demonstrated that nothing can enter it. Either is a
result. If nothing clears CONTEXT in two quarters, escalate to quarterly governance.
