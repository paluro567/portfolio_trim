# DATA-CAPTURE WORKBOOK SPECIFICATION — ANALYST ONLY

**One CSV per table.** Directory `07_responses/data/`. UTF-8, comma-delimited, header row required.
Field order as listed. **Derived fields are computed, never typed by hand.**

Governing sections: Ops Package §7.1, §7.2, §7.3.

---

## 1. `participants.csv` *(5 rows)*

| Field | Type | Allowed | Req | Source | Validation | Blinded | Derived |
|---|---|---|---|---|---|---|---|
| `participant_id` | str | P1–P5 | Y | §D sheet | unique; exactly 5 | No | No |
| `track` | enum | A, B | Y | screener | count(A) ≥ 3; count(B) ≤ 2 | No | No |
| `role` | str | free | Y | screener | non-empty | No | No |
| `years_experience` | int | ≥ 0 | Y | screener | A ≥ 3; B ≥ 5 | No | No |
| `portfolio_scale_band` | enum | `<250k`,`250k-1M`,`1M-10M`,`>10M` | Y | screener | B ≠ `<250k` | No | No |
| `n_positions_band` | enum | `<10`,`10-25`,`26-50`,`>50` | Y | screener | ≠ `<10` | No | No |
| `holding_period_band` | enum | `<1wk`,`1wk-3mo`,`3mo-1yr`,`>1yr` | Y | screener | ≠ `<1wk` | No | No |
| `has_written_process` | bool | TRUE/FALSE | Y | screener | must be TRUE | No | No |
| `recruited_date` | date | ISO-8601 | Y | log | ≤ `session_date` | No | No |
| `session_date` | date | ISO-8601 | Y | log | — | No | No |
| `sequence_id` | enum | P1–P5 | Y | §G table | = `participant_id` | No | No |

## 2. `cases.csv` *(7 rows — static, frozen)*

| Field | Type | Allowed | Req | Validation |
|---|---|---|---|---|
| `case_id` | enum | A–G | Y | exactly 7 |
| `case_type` | enum | CONFIRMATORY, SHAM, SCORE | Y | A–E = CONFIRMATORY; F = SHAM; G = SCORE |
| `archetype` | str | free | Y | non-empty |
| `in_gate1_denominator` | bool | — | Y | TRUE for A–E only |
| `in_gate2_denominator` | bool | — | Y | TRUE for A–E only |

```csv
case_id,case_type,archetype,in_gate1_denominator,in_gate2_denominator
A,CONFIRMATORY,above_hard_cap,TRUE,TRUE
B,CONFIRMATORY,below_target_event_risk,TRUE,TRUE
C,CONFIRMATORY,appreciated_winner_tax,TRUE,TRUE
D,CONFIRMATORY,loser_within_policy,TRUE,TRUE
E,CONFIRMATORY,conflicting_evidence_abstain,TRUE,TRUE
F,SHAM,sham_control,FALSE,FALSE
G,SCORE,exploratory_score_arm,FALSE,FALSE
```

## 3. `decisions.csv` *(70 rows = 5 participants × 7 cases × 2 phases)*

| Field | Type | Allowed | Req | Source | Validation | Blinded | Derived |
|---|---|---|---|---|---|---|---|
| `record_id` | str | `R-nnnn` | Y | generated | unique; **non-sequential, randomly assigned** | **Yes** | No |
| `participant_id` | enum | P1–P5 | Y | form | FK | **Yes to evaluators** | No |
| `case_id` | enum | A–G | Y | form | FK | No | No |
| `phase` | enum | PRE, POST | Y | form | 2 per (participant, case) | **Yes to evaluators** | No |
| `position_in_sequence` | int | 1–7 | Y | §G | matches §G row | **Yes** | No |
| `action` | enum | ADD, HOLD, TRIM, EXIT | Y | form | non-null | No | No |
| `magnitude_pct` | float | 0–100, nullable | N | form | null ⟺ "none" ticked | No | No |
| `confidence` | int | 1–5 | Y | form | non-null | No | No |
| `reasoning_text` | str | free | **Y** | form | **non-empty on EVERY row incl. PRE and unchanged POST** | No | No |
| `sections_ticked` | list | §3.7 Q4 values | N | form | POST only; empty on PRE | No | No |
| `nothing_changed_ticked` | bool | — | N | form | POST only | No | No |

> **`reasoning_text` empty on any row is a blocking data error.** Blind evaluation is impossible without
> it. Log as a protocol deviation and exclude that (participant, case) pair from Gate 2, retaining it in
> Gate 1 only if the change flags are determinable.

## 4. `change_flags.csv` *(35 rows — all derived)*

| Field | Type | Derivation |
|---|---|---|
| `participant_id` | enum | key |
| `case_id` | enum | key |
| `magnitude_delta_abs_pp` | float | `abs(mag_POST − mag_PRE)`; null-handling per §7.2 below |
| `magnitude_delta_rel_pct` | float | `abs(mag_POST − mag_PRE) / max(mag_PRE, 0.1)` |
| `change_a` | bool | `action_POST != action_PRE` |
| `change_m` | bool | `magnitude_delta_abs_pp >= 2.0 OR magnitude_delta_rel_pct >= 0.25` |
| `attrib` | bool | see §7.2 and A-002 |
| `attrib_quote` | str | verbatim phrase justifying an unprompted attribution; **required whenever `attrib` is TRUE via unprompted naming**; empty if attribution came from a Q4 tick |
| `counted` | bool | `(change_a OR change_m) AND attrib` |

## 5. `evaluations.csv` *(3 rows per evaluated record)*

| Field | Type | Allowed | Req | Validation | Blinded |
|---|---|---|---|---|---|
| `record_id` | str | FK | Y | exists in `decisions` | Yes |
| `evaluator_id` | enum | E1, E2, E3 | Y | 3 rows per record | Yes |
| `q1` | int | 0, 1, 2 | Y | — | Yes |
| `q2_engaged` | list | constraint IDs | Y | IDs must exist for that case | Yes |
| `q3` | int | 0, 1, 2 | Y | — | Yes |
| `unsup` | bool | — | Y | — | Yes |
| `blinding_guess` | enum | BEFORE, AFTER, CANT_TELL | Y | — | Yes |
| `note` | str | free | N | — | Yes |

## 6. `adjudicated.csv` *(1 row per evaluated record — derived)*

| Field | Derivation |
|---|---|
| `q1_final` | value with ≥ 2 of 3 agreement, else `UNRESOLVED` |
| `q2_final` | set of constraint IDs ticked by ≥ 2 of 3 |
| `q3_final` | ≥ 2 of 3, else `UNRESOLVED` |
| `unsup_final` | ≥ 2 of 3, else `UNRESOLVED` |

## 7. `classifications.csv` *(25 rows — confirmatory only, derived)*

| Field | Derivation |
|---|---|
| `participant_id`, `case_id` | key |
| `classification` | UNCHANGED / DEGRADED / UNSUPPORTED / IMPROVED / DEFENSIBLE / UNRESOLVED — §7.3 precedence |

## 8. `blinding.csv` *(3 rows per evaluated record — derived)*

| Field | Derivation |
|---|---|
| `record_id`, `evaluator_id` | key |
| `guess` | from `evaluations` |
| `actual_phase` | from `decisions` — **joined only at analysis time** |
| `correct` | `guess != CANT_TELL AND guess == actual_phase` |

## 9. `deviations.csv`

`deviation_id` · `session_id` · `timestamp` · `case_id` · `description` · `cause` · `action_taken` ·
`data_affected` (bool)

## 10. `constraints.csv` *(frozen — from `constraints_v1.0.md`)*

`constraint_id` · `case_id` · `text` · `authored_by` · `frozen_hash`
**Read-only. Never edited after the hash is recorded.**

---

# EXACT CALCULATION RULES

## §7.2 — Derived flags

```python
CHANGE_A = (action_POST != action_PRE)

# magnitude: exactly one of PRE/POST null -> treated as a change
if (mag_PRE is None) != (mag_POST is None):
    CHANGE_M = True
elif mag_PRE is None and mag_POST is None:
    CHANGE_M = False
else:
    CHANGE_M = (abs(mag_POST - mag_PRE) >= 2.0
                or abs(mag_POST - mag_PRE) / max(mag_PRE, 0.1) >= 0.25)

ATTRIB = (any section ticked in sections_ticked other than "none of these")
         or (reasoning_text names a report section unprompted, ANALYST-confirmed
             per AMENDMENT 001 A-002, with attrib_quote recorded)

# A-002 binding rules:
#   who    : the ANALYST. No new role, no additional cost.
#   when   : after data entry, BEFORE evaluator scores are received or opened.
#   sees   : POST Q4 ticks, POST Q3 reasoning text, the report for that case.
#   NOT    : any evaluator score, classification, or aggregate result.
#   cats   : exactly the 14 POST-form Q4 tokens. No new category may be created.
#   multi  : all recorded; distinct_sections counts the union.
#   quote  : attrib_quote REQUIRED for unprompted attribution; no quote => invalid.
#   unclear: ATTRIB = FALSE  (conservative - makes Gate 1 harder, never easier).
#   separ. : the analyst NEVER scores Q1, Q2, Q3 or UNSUP.

COUNTED = (CHANGE_A or CHANGE_M) and ATTRIB
```

## §7.3 — Classification *(strict precedence, top to bottom; first match wins)*

```python
def classify(pre, post, change_a, change_m):
    changed = change_a or change_m
    if any_unresolved(pre, post):            return "UNRESOLVED"
    if not changed:                          return "UNCHANGED"
    if (post.q1 < pre.q1 or post.q3 < pre.q3
        or post.q2.issubset(pre.q2) and post.q2 != pre.q2):
                                             return "DEGRADED"
    if post.unsup:                           return "UNSUPPORTED"
    if (post.q2 > pre.q2                     # strict superset
        and post.q1 >= pre.q1
        and post.q3 >= pre.q3):              return "IMPROVED"
    return "DEFENSIBLE"
```

## Aggregate metrics

```python
# ---- GATE 1 : influence ------------------------------------------------
n_conf          = count(classifications)                       # expect 25
counted_conf    = count(COUNTED == True, case_type == CONFIRMATORY)
raw_change_rate = counted_conf / n_conf
sham_changes    = count((CHANGE_A or CHANGE_M), case_id == "F")   # max 5
sham_rate       = sham_changes / 5
NET_CHANGE_RATE = raw_change_rate - sham_rate                  # <- GATE 1 PRIMARY

participants_with_change = count(distinct participant_id
                                 where any COUNTED == True and case_id in A..E)
distinct_sections = count(distinct entries across sections_ticked
                          for COUNTED rows, excluding "none of these")

# ---- GATE 2 : quality --------------------------------------------------
D               = counted_conf                                 # denominator
n_improved      = count(classification == "IMPROVED")
n_defensible    = count(classification == "DEFENSIBLE")
n_unsupported   = count(classification == "UNSUPPORTED")
n_degraded      = count(classification == "DEGRADED")
n_unresolved    = count(classification == "UNRESOLVED")

HARM_RATE       = (n_unsupported + n_degraded) / D              # <- GATE 2 PRIMARY
UNRESOLVED_RATE = n_unresolved / D
improved_participants        = count(distinct participant_id where IMPROVED)
max_degraded_per_participant = max over participants of count(DEGRADED)

# ---- BLINDING INTEGRITY -----------------------------------------------
guesses_made      = count(blinding_guess != "CANT_TELL")
BLINDING_ACCURACY = count(correct == True) / guesses_made

# ---- VALUE BEYOND CAP BREACH ------------------------------------------
counted_excl_A       = count(COUNTED == True, case_id in B..E)
sections_excl_policy = count(distinct sections for COUNTED rows,
                             excluding "policy status" and "none of these")
survives_removing_A  = (counted_excl_A / 20) - sham_rate >= 0.30
```

## DECISION — FAIL evaluated first, and it overrides PASS

```python
FAIL = (NET_CHANGE_RATE < 0.15
        or participants_with_change <= 1
        or recruitment_failed
        or HARM_RATE > 0.40
        or max_degraded_per_participant >= 2)

PASS = (NET_CHANGE_RATE >= 0.30
        and participants_with_change >= 3
        and distinct_sections >= 2
        and HARM_RATE <= 0.25
        and n_improved >= 2
        and improved_participants >= 2
        and UNRESOLVED_RATE <= 0.30
        and BLINDING_ACCURACY <= 0.65)

if FAIL:      RESULT = "FAIL"          # precedence: FAIL wins even if PASS is also True
elif PASS:    RESULT = "PASS"
else:         RESULT = "AMBIGUOUS"
```

## Exclusions — enforced by assertion

```python
assert all(row.case_id != "G" for row in gate1_numerator + gate1_denominator)
assert all(row.case_id != "G" for row in gate2_numerator + gate2_denominator)
assert all(row.case_id != "F" for row in gate2_numerator + gate2_denominator)
assert n_conf == 25 or logged_deviation_explains(n_conf)
```

**Case G is excluded from every confirmatory numerator and denominator. Case F contributes only to
`sham_rate`.**

---

# REDACTION RULE — applied by the redactor before evaluator packs are distributed

Mechanical. Applied to `reasoning_text` only. **Never edit reasoning structure or wording beyond these
substitutions.**

| # | Target | Replace with |
|---|---|---|
| R1 | Any numeric string that appears **only** in the report for that case, not in its baseline | `[figure]` |
| R2 | **(A-004 / L10)** Any reference to *terminal wealth*, *following these recommendations*, or the disclosure by name | `[reference to a report section]` |
| R3 | Any reference to the Case G **score** or its decomposition | `[figure]` |
| R4 | Characterisations appearing only in a report (e.g. "top decile") | `[characterisation]` |

Every substitution is logged: `record_id · rule · original · replacement`. The redactor is **not** an
evaluator.

---

# COHEN'S KAPPA — REMOVED

Per **AMENDMENT 001 A-003**, κ is **not computed and not reported**. The governing frozen protocol
(`PHASE1_OPERATIONS_PACKAGE.md`) specifies three blinded evaluators with 2-of-3 adjudication and never
requires κ. The superseded `PHASE1_STUDY_PACKAGE.md` requirement has no force.

Inter-rater disagreement is reported by the three measures the frozen protocol **does** require, all of
which are load-bearing rather than merely descriptive:

- **disagreement-log entry count**
- **`UNRESOLVED_RATE`** — caps the result at AMBIGUOUS above 30%
- **`BLINDING_ACCURACY`** — caps the result at AMBIGUOUS above 65%
