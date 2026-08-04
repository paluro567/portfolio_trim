# PHASE 1 — PROTOCOL AMENDMENT 002
## Factual Integrity Corrections

**Version:** 1.0 · **Status:** awaiting signature and hash · **Effective:** on signature, before freeze
**Authority:** `PHASE1_OPERATIONS_PACKAGE.md` remains the governing protocol. This amendment corrects
false arithmetic in participant-facing artifacts. It adds no case, removes no case, and changes no
criterion.

> **CONFIRMED UNCHANGED:** primary and secondary hypotheses · dual-gate structure · **all PASS,
> AMBIGUOUS and FAIL thresholds** · seven cases · participant count (5) · evaluator count (3) ·
> 30-hour / $650 cap · anti-redesign rule · case order · sham design · classification precedence ·
> report format and section order.

> **ONE CORRECTION IS NOT CLERICAL.** D-01 materially changes Case A's decision logic. It is classified
> **C** and labelled as such throughout, in accordance with the instruction not to describe a material
> change as clerical.

---

## PART 1 — Independent recomputation

### D-01 · Case A — full-exit days of ADV

| Input | Value | Source |
|---|---|---|
| Position market value | $3,410,000 | `case_A.md` page 1 |
| 20-day ADV | $210,000,000 | `case_A.md` page 1 |
| Liquidity limit | 2 days of 20-day ADV | Meridian policy |
| Participation convention | **100% of ADV** — the policy states *"no action sized above 2 days of 20-day average dollar volume"* | policy text |

```
days_to_exit = position_value ÷ adv_20d
             = $3,410,000 ÷ $210,000,000
             = 0.0162 days
```

**Stated: 16.2 days. Computed: 0.0162 days. Ratio 997.7×.**

Tested against every convention that could rescue the figure:

| Participation rate | Days to exit | Documented in frozen materials? |
|---|---|---|
| **100% of ADV** *(the policy's own convention)* | **0.0162** | **Yes** |
| 20% | 0.0812 | No |
| 10% | 0.1624 | No |
| 1% | 1.6238 | No |
| 0.1% | **16.2381** ← matches | **No — and absurd** |

**16.2 days is reachable only at a 0.1% participation rate, which appears nowhere in the frozen
materials.** Adopting it would be inventing an unstated convention to preserve a desired conclusion.

**VERDICT:** a full exit is **0.0162 days — 123× inside the 2-day limit.** The $1,610,000 trim is
0.0077 days. **Liquidity is not a binding constraint anywhere in Case A.**

*(Both page-1 facts are mutually consistent: $210M ADV → 1.62% of ADV, stated as 1.6%. Only the page-2
report claim is the outlier.)*

### D-02 · Portfolio HHI — Cases A, **C and G** *(ALL THREE HHI-bearing reports)*

Since `HHI = Σ wᵢ²`, HHI can never be less than any single position's `wᵢ²`.

| | Case A | Case C | Case G |
|---|---|---|---|
| Weight | 28.4% | 19.2% | 11.2% |
| Own contribution `w²` | **0.0807** | 0.0369 | 0.0125 |
| Stated total HHI | **0.071** | **0.048** | **0.041** |
| `stated ≥ own`? | **NO — impossible on its own** | Yes | Yes |
| Minimum possible total *(other 23 equal)* | **0.1029** | **0.0652** | **0.0468** |
| Maximum possible total *(others at the 15% cap)* | 0.1714 | 0.1476 | 0.1261 |
| Valid range | [0.1029, 0.1714] | [0.0652, 0.1476] | [0.0468, 0.1261] |
| **Verdict** | **IMPOSSIBLE** | **IMPOSSIBLE** | **IMPOSSIBLE** |

> **EXTENSION OF SCOPE — TWICE.** `PROTOTYPE_ENGINEERING_ASSESSMENT.md` flagged D-02 for Case A only.
> Independent recomputation shows **Case G (0.041 < 0.0468 floor)** and **Case C (0.048 < 0.0652 floor)**
> are also impossible. **Every one of the three HHI-bearing reports states a mathematically impossible
> value.** D-02 is extended to all three.
>
> The pattern is diagnostic: the HHI figures were authored to *look* like a plausible diversification
> improvement rather than computed, which is precisely the failure mode a verification layer exists to
> catch.

**Only 1 of 24 weights is specified in either case. Total portfolio HHI is not computable from the
available facts, and the remaining 23 weights will not be fabricated to retain the field.**

### D-03 · Case B — move-to-target as % of ADV

```
deviation   = target − weight = 5.0% − 3.1%      = 1.9 pp
trade_value = 1.9% × $12,000,000                 = $228,000
pct_of_adv  = $228,000 ÷ $44,000,000             = 0.518%   → 0.5%
days        = 0.0052 days   (inside the 2-day limit either way)
```

**Stated: 3.1%. Computed: 0.5%.** The stated figure is numerically identical to the **position weight
(3.1%)** — a transcription of the wrong field. *(Position as % of ADV would be 0.845%, also not 3.1%.)*

---

## PART 2 — D-01 resolution

| Option | Assessment |
|---|---|
| **1 · Correct the figure; remove liquidity as the EXIT-elimination reason** | **SELECTED** |
| 2 · Change the ADV so the trace stays true | **Rejected.** Requires ADV ≈ $210k, which also falsifies page 1's "1.6% of ADV" (becomes 1,624%). Two participant-facing baseline changes, and it converts Case A from a concentration archetype into an illiquidity archetype — a larger design change than Option 1 |
| 3 · Apply a documented participation constraint | **Rejected — impossible.** No participation rate exists in the frozen materials; only 0.1% reproduces 16.2 days. Selecting it would fabricate a fact to preserve a conclusion |
| 4 · Classify EXIT as feasible but undesirable | **Subsumed by Option 1.** The selected replacement text does exactly this |

### Selected resolution

Replace the liquidity justification with the **wording already used in Case C** for the identical
situation — *"the cap mandate does not require exit."* This introduces no new fact, requires no baseline
change, and is internally consistent with the frozen case set.

### Impact assessment — stated plainly

| Dimension | Changed? | Detail |
|---|---|---|
| Participant-facing information | **YES** | One line of the Case A elimination trace |
| Set of material constraints | **YES** | Liquidity is removed from Case A. Ops Package Part 2 listed *"staging/liquidity of a $1.61M reduction"* as expected — that expectation is **superseded**. Under the frozen facts the trim is 0.0077 days and liquidity is simply not live |
| Remaining material constraints | **4 — above the 3 minimum** | cap breach (13.4pp) · realised-gains budget (a $1.61M trim realises ≈ $1,218,000 of gain against $60,000 remaining) · sector cap (34.1% vs 30.0%) · correlation cluster (0.71 / 0.66) |
| Plausible defensible decisions | **NO** | Trim-to-cap, staged trim, partial trim, trim-below-cap, and reasoned rejection of the cap all remain available |
| Unsupported-decision examples | **NO** | Deference and unstated-basis changes are unaffected |
| Degraded-decision examples | **YES** | Ops Part 2 Case A's example *"post recommends full exit while the liquidity constraint is on the page"* is **void** and is superseded by: *"post recommends full exit while the cap mandate requires only a trim to 15.0%."* |
| Q2 scoring | **INDIRECTLY** | The constraint author has **not yet authored**, so no rework occurs. Liquidity will simply not appear on Case A's list |
| Evaluator instructions | **NO** | Rubrics are case-agnostic |
| Intended purpose of Case A | **PRESERVED** | Still "position materially above a hard concentration cap" |
| Preregistration | **NO** | |
| Study thresholds | **NO** | |

### Classification: **C — a material case-design change requiring this amendment.**

Not clerical. It alters a participant-facing decision justification and removes one expected material
constraint. It is nonetheless the **smallest** correction that preserves Case A's purpose without
presenting false arithmetic.

**Timing note:** because the constraint author is unconfirmed and has authored nothing, this correction
lands **before** any dependent work exists. Later would be materially more expensive.

---

## PART 3 — D-02 resolution

| Option | Assessment |
|---|---|
| A · Recompute from a newly specified 24-position portfolio | **Rejected.** Requires fabricating 23 weights — explicitly prohibited |
| **B · Replace with a metric computable from existing facts** | **SELECTED** |
| C · Label unavailable | Rejected as larger: removes information and may read to a participant as a system defect, contaminating the very perception the study measures |
| D · Remove the field | Rejected as larger: deletes a line from a frozen report section |

### Selected resolution

Replace total portfolio HHI with **this position's own contribution to portfolio concentration
(weight²)** — exactly computable from page-1 facts, and participant-verifiable.

| Case | Before → after | Derivation |
|---|---|---|
| **A** | **0.0807 → 0.0225** | `0.284²` → `0.150²` (trim to the 15.0% cap) |
| **C** | **0.0369 → 0.0225** | `0.192²` → `0.150²` (trim to the 15.0% cap) |
| **G** | **0.0125 → 0.0049** | `0.112²` → `0.070²` (trim to the 7.0% band ceiling) |

This is a substitution **within** the existing PORTFOLIO IMPACT section. No section is added or removed.

### Materiality

| Reaches | Materiality |
|---|---|
| Constraint author | **NO** — the author receives **page 1 only**; HHI appears only on page 2. It cannot appear on any Q2 list |
| Evaluators | **NO** — evaluator records reproduce the **case baseline**, not the report. HHI never reaches an evaluator |
| Any PASS / AMBIGUOUS / FAIL condition | **NO** |
| Participant decisions | **Weakly** — sits under "portfolio impact", a Q4 checklist token. A participant could attribute a change to a section containing a false figure |

**Classification: A — factual correction with no methodological effect.** It touches no scored element;
it is corrected because the study must not present false arithmetic.

---

## PART 4 — D-03 resolution

**Simple arithmetic correction: `3.1%` → `0.5%`.**

| Changed? | |
|---|---|
| Action | **NO** — HOLD, driven by band status |
| Magnitude | **NO** — none |
| Constraints | **NO** — Case B's elimination trace makes no liquidity claim; 0.5% and 3.1% are both far inside the 2-day limit |
| Evaluator classification | **NO** — but note the figure **is on page 1**, so it *is* seen by the constraint author and reproduced in evaluator records. A visible false figure must be corrected |
| Test purpose | **NO** — still "below target with near-term event risk" |
| Study thresholds | **NO** |

**Classification: A — factual correction with no methodological effect.**

---

## PART 5 — Affected artifacts

| Artifact | Change | Occurrences |
|---|---|---|
| `01_participant/case_A.md` | D-01 elimination trace · D-02 portfolio impact | 2 |
| `01_participant/case_B.md` | D-03 baseline ADV line | 1 |
| `01_participant/case_C.md` | D-02 portfolio impact | 1 |
| `01_participant/case_G.md` | D-02 portfolio impact | 1 |
| `PHASE1_OPERATIONS_PACKAGE.md` Part 2 Case A | **SUPERSEDED, not edited** — the expected-constraint reference to *"staging/liquidity of a $1.61M reduction"* and the degraded example *"full exit while the liquidity constraint is on the page"* are void. This amendment governs | 2 |
| `06_execution/quality_control_report.md` | Record D-01…D-03 closure; extend D-02 to Case G | — |
| `00_COMPLIANCE_MATRIX.md` | Add Amendment 002 row | 1 |
| `06_execution/directory_manifest.md` | Add Amendment 002 + `tools/phase1/` | 2 |
| **`tools/phase1/`** | **NEW** — `case_facts.py`, `verify_reports.py` | — |
| Constraint-author kit | **No text change.** Author sees page 1 only; Case B's page-1 correction reaches them through the corrected packet | — |
| Evaluator kit | **No text change.** Rubrics are case-agnostic; baselines reach evaluators through the corrected packets | — |
| Redaction rules R1–R4 | **No change.** Corrected figures redact identically | — |
| Data-capture spec · analysis template | **No change.** No threshold, field, or formula references these values | — |

---

## PART 6 — Exact replacement text

### D-01 · `case_A.md` — WHY NOT THE ALTERNATIVES

**FROM**
```
  EXIT   eliminated — liquidity: a full exit is 16.2 days of average
         dollar volume, above the 2-day limit
```
**TO**
```
  EXIT   eliminated — the cap mandate does not require exit; trimming to
         the 15.0% cap satisfies it
```

### D-02 · `case_A.md` — PORTFOLIO IMPACT

**FROM** `  Portfolio HHI     0.071  →  0.048`
**TO** `  This position's contribution to portfolio` / `  concentration (weight squared)   0.0807  →  0.0225`

### D-02 · `case_C.md` — PORTFOLIO IMPACT

**FROM** `  Portfolio HHI     0.048  →  0.039`
**TO** `  This position's contribution to portfolio` / `  concentration (weight squared)   0.0369  →  0.0225`

### D-02 · `case_G.md` — PORTFOLIO IMPACT

**FROM** `  Portfolio HHI     0.041  →  0.036`
**TO** `  This position's contribution to portfolio` / `  concentration (weight squared)   0.0125  →  0.0049`

### D-03 · `case_B.md` — baseline table

**FROM** `| A move to target as % of ADV | 3.1% |`
**TO** `| A move to target as % of ADV | 0.5% |`

---

## Confirmations

| | |
|---|---|
| **Case logic materially changed** | **YES — D-01 only.** Explicitly stated, not labelled clerical |
| **Preregistration changed** | **NO** |
| **Hypotheses changed** | **NO** |
| **Thresholds changed** | **NO** |
| Cases added or removed | NO |
| Participant or evaluator count changed | NO |
| Budget changed | NO |
| Report format or section order changed | NO |

## Signature and hash block

```
AMENDMENT 002 · VERSION 1.0 · FACTUAL INTEGRITY

D-01  Case A full-exit liquidity     CLASS C — material case-design change
D-02  Portfolio HHI, Cases A, C AND G  CLASS A — factual correction
D-03  Case B move-to-target % of ADV CLASS A — factual correction

Case logic materially changed   ▢ YES (D-01)   [must be acknowledged, not waived]
Preregistration changed         ▢ NO
Hypotheses changed              ▢ NO
Thresholds changed              ▢ NO
Case set changed                ▢ NO
Budget changed                  ▢ NO

Prepared by ______________________   Date ______________
Approved by (Ops lead) ______________________   Date ______________

File name    PHASE1_PROTOCOL_AMENDMENT_002.md
SHA-256      ____________________________________________________
Recorded in preregistration  ▢       Placed in 08_frozen/  ▢
Verifier run clean (tools/phase1/verify_reports.py exit 0)  ▢
```

```bash
shasum -a 256 docs/phase1/PHASE1_PROTOCOL_AMENDMENT_002.md
```

**Amendment 002 must be signed and hashed, and the verifier must exit 0, before freeze.**
