# PHASE 1 — FINAL ANALYSIS AND DECISION REPORT *(fillable)* — ANALYST ONLY

> **The result in §11 is COMPUTED, not judged. The analyst has no discretion to override it.**
> If the analyst believes the computed result is wrong, that belief is recorded in §12 as a dissent
> and **the computed result still stands.**

---

## §0 — Identification and integrity

```
Preregistration identifier      ______________________________
Preregistration hash (SHA-256)  ______________________________
Preregistration frozen (UTC)    ______________________
Study completed (UTC)           ______________________

ARTIFACT VERSION HASHES
  PHASE1_OPERATIONS_PACKAGE.md  ______________________________
  PHASE1_PROTOCOL_AMENDMENT_001.md ___________________________
  00_COMPLIANCE_MATRIX.md       ______________________________
  01_participant/ (all files)   ______________________________
  02_moderator/moderator_kit.md ______________________________
  constraints_v1.0.md           ______________________________
  04_evaluator/evaluator_kit.md ______________________________
  05_analyst/data_capture_spec.md ____________________________
  05_analyst/analysis_report_template.md _____________________

  ▢ All hashes recorded BEFORE session 1     ▢ No artifact changed after freeze
  ▢ If any changed: deviation IDs ______________________
```

## §1 — Recruitment outcome

```
Approached ____   Screened ____   Qualified ____   Scheduled ____   Completed ____
Recruitment hours used ____ / 6          Recruitment failed?  ▢ Y  ▢ N
Withdrawals ____   Replacements ____
```

## §2 — Participant characteristics

```
     ID | Track | Role                | Yrs | Scale band | Positions | Hold period
     ---+-------+---------------------+-----+------------+-----------+------------
     P1 |       |                     |     |            |           |
     P2 |       |                     |     |            |           |
     P3 |       |                     |     |            |           |
     P4 |       |                     |     |            |           |
     P5 |       |                     |     |            |           |

Track A count ____  (required ≥3)      Track B count ____  (max 2)
Quota satisfied  ▢ Y  ▢ N   [if N: cancellation condition 2 — see §11]
```

## §3 — Protocol deviations

```
Total ____      Affecting data ____

ID | Session | Case | Description | Cause | Action taken | Data affected
---+---------+------+-------------+-------+--------------+--------------
```

## §4 — Case completion

```
Warm-up forms collected and discarded ____ / 5   [not in any dataset — A-001]
Cases delivered ____ / 35     Confirmatory (A–E) ____ / 25
Sham (F) ____ / 5             Score (G) ____ / 5
Records with empty reasoning_text ____   [each is a blocking data error — list IDs]
Pairs excluded from Gate 2 ____   IDs ______________________
```

## §5 — Behavioural results · **GATE 1**

```
n_conf (confirmatory classifications)  ____ / 25
COUNTED changes                        ____
raw_change_rate                        ____%

NET_CHANGE_RATE                        ____%     [PASS ≥30%  ·  FAIL <15%]
participants_with_change               ____ / 5  [PASS ≥3    ·  FAIL ≤1]
distinct_sections                      ____      [PASS ≥2]
ATTRIB via Q4 tick ____   via unprompted quote ____   (A-002; quotes recorded ▢)

Sections cited: ________________________________________________
```

## §6 — Sham comparison

```
Sham changes (Case F)   ____ / 5        sham_rate  ____%
raw_change_rate ____%  −  sham_rate ____%  =  NET_CHANGE_RATE ____%

Note: if sham_rate ≥ raw_change_rate, NET_CHANGE_RATE is ≤ 0 and FAIL is triggered.
```

## §7 — Blinded quality results · **GATE 2**

```
Attributed changes (D)  ____

  IMPROVED      ____        DEFENSIBLE   ____
  UNSUPPORTED   ____        DEGRADED     ____
  UNRESOLVED    ____                              (sums to D)

HARM_RATE = (UNSUPPORTED + DEGRADED) / D  =  ____%   [PASS ≤25%  ·  FAIL >40%]
n_improved                                   ____    [PASS ≥2]
improved_participants                        ____    [PASS ≥2]

Inter-evaluator disagreement log entries ____
Cohen's kappa: NOT COMPUTED — removed by AMENDMENT 001 A-003. Do not enter a value.
```

## §8 — Participant-level harm screen

```
     ID | DEGRADED count | UNSUPPORTED count
     ---+----------------+------------------
     P1 |                |
     P2 |                |
     P3 |                |
     P4 |                |
     P5 |                |

max_degraded_per_participant  ____        [FAIL if ≥2]
```

## §9 — Blinding integrity · Unresolved rate

```
Guesses made (≠ CANT_TELL)  ____      Correct  ____
BLINDING_ACCURACY           ____%     [PASS ≤65%]

UNRESOLVED_RATE             ____%     [PASS ≤30%]
```

## §10 — Value beyond cap-breach

```
COUNTED changes attributable ONLY to Case A       ____ / ____
COUNTED changes on cases B–E                      ____ / 20
distinct sections excluding "policy status"       ____
Would the result survive removing Case A?         ▢ Y  ▢ N

[If N and RESULT would otherwise be PASS: this is an AMBIGUOUS branch — see §12]
```

## §10b — Qualitative observations

```
Abstention (Case E):    ACCEPT ____  TOLERATE ____  REJECT ____
Comprehension:          CORRECT ____  PARTIAL ____  INCORRECT ____
Score-arm preference (E vs G):  no-score ____  score ____  indifferent ____
Unprompted adoption asks ____
WTP offered (recorded, NOT scored, NOT part of any threshold): ______________
Three most-cited "not worth reading" items: ______________________________
Notable disconfirming quotes (required — at least two): __________________
```

## §10c — LIMITATIONS · **FIXED TEXT — DO NOT EDIT**

> n=5; participant is the unit of independence. Hypothetical decisions, not executed trades. Disguised
> composite cases. Single session; no longitudinal use. Volunteer selection. No confidence intervals are
> reported and none are supportable. Gate 2 is a harm screen plus existence proof; it cannot and does
> not estimate a rate of beneficial change.

---

## §11 — DECISION · **MECHANICAL**

### Step 1 — FAIL conditions *(evaluated first; any one triggers FAIL)*

```
▢ NET_CHANGE_RATE < 0.15                     value ____
▢ participants_with_change ≤ 1               value ____
▢ recruitment_failed = TRUE                  value ____
▢ HARM_RATE > 0.40                           value ____
▢ max_degraded_per_participant ≥ 2           value ____

ANY TICKED?  ▢ YES → RESULT = FAIL (stop; ignore Step 2)   ▢ NO → continue
```

### Step 2 — PASS conditions *(all six required)*

```
▢ NET_CHANGE_RATE ≥ 0.30                     value ____
▢ participants_with_change ≥ 3               value ____
▢ distinct_sections ≥ 2                      value ____
▢ HARM_RATE ≤ 0.25                           value ____
▢ n_improved ≥ 2 AND improved_participants ≥ 2   values ____ / ____
▢ UNRESOLVED_RATE ≤ 0.30 AND BLINDING_ACCURACY ≤ 0.65   values ____ / ____

ALL SIX TICKED?  ▢ YES → RESULT = PASS    ▢ NO → RESULT = AMBIGUOUS
```

### Result

```
              ▢ PASS        ▢ AMBIGUOUS        ▢ FAIL

PASS conditions met ____ / 6      FAIL conditions triggered ____
```

## §12 — REQUIRED NEXT ACTION · **no discretion**

```
▢ PASS
    → Proceed to Phase 2 (policy artifact + Layer 1). No architecture change.

▢ AMBIGUOUS  — select the applicable branch:
    ▢ diffuse across participants
        → One follow-up. ONE pre-declared report-content change: ________________
          No architecture change. Same thresholds. Same cap.
    ▢ concentrated in ≤2 participants
        → One follow-up with DIFFERENT PARTICIPANTS ONLY. No content change permitted.
    ▢ change driven only by the cap breach (§10 = N)
        → One follow-up with cases A and G REMOVED.
    ▢ UNRESOLVED_RATE >30% or BLINDING_ACCURACY >65%
        → Quality gate uninformative. One follow-up; evaluation procedure only.
    In every branch: exactly ONE follow-up. It may not produce another.
    If the follow-up does not reach PASS → FAIL, with no further options.

▢ FAIL
    → Stop. Development halts. 90-day pause.
    → A FAIL may NOT be answered by rewriting the report and re-testing.
    → Resumption requires a NEW product hypothesis and a sponsor other than the architect.
    → The negative result is written up and published internally in full.

ANALYST DISSENT (optional, does not change the result): ____________________
```

## §13 — CLOSING SUMMARY SENTENCE · frozen rules

**Rules — all binding:**
1. **Maximum 40 words.**
2. **May not contain the word "improve" or any variant** (improves, improvement, improved).
3. Must state the observed result, not an interpretation of it.
4. Must not use: *validates · proves · demonstrates value · confirms · shows promise · encouraging ·
   promising · successful.*
5. Must be written **after** §11 is computed, and must be consistent with it.

**Reference form for a PASS result:**
> *"The report changed committed decisions at a rate above reconsideration; blinded external evaluators
> did not find those changes predominantly unsupported or degraded, and judged at least two of them to
> increase constraint engagement."*

```
SUMMARY (≤40 words) ______________________________________________________
__________________________________________________________________________

Word count ____    ▢ contains no form of "improve"    ▢ no banned term used
```

---

```
Signed (analyst)   ______________________   Date ______________
Signed (moderator) ______________________   Date ______________
```
