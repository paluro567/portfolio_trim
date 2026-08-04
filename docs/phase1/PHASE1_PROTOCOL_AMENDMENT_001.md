# PHASE 1 — PROTOCOL AMENDMENT 001

**Version:** 1.0 · **Status:** awaiting signature and hash · **Effective:** on signature, before recruitment
**Authority:** `PHASE1_OPERATIONS_PACKAGE.md` (frozen) remains the governing protocol. This amendment
resolves ambiguities and internally-authored assumptions **within** it. It creates no new requirement.

> **CONFIRMED UNCHANGED BY THIS AMENDMENT:**
> primary hypothesis · secondary hypotheses H2/H3/H4 · dual-gate structure · **all PASS, AMBIGUOUS and
> FAIL thresholds** · the seven cases · participant count (5) · evaluator count (3) · the 30-hour /
> $650 cap · the anti-redesign rule · case order · sham design · classification precedence.

---

## PART 1 — Classification of every open issue

| ID | Issue | Class | Reason |
|---|---|---|---|
| **Q1** | Warm-up case content unspecified | **A — resolvable now** | §4.2 mandates a warm-up; only the content was missing. Producing it fulfils the protocol rather than extending it |
| **Q2** | "Coder-confirmed attribution" undefined | **A** | A procedural gap. Resolvable by naming the role, timing and rules without new cost |
| **Q3** | Two coders + Cohen's κ vs single analyst | **A** | A superseded-document conflict, resolvable by applying the precedence the Ops Package already asserts |
| **Q4** | "Disconfirming quotes" minimum (≥2) is ops-authored | **D — non-blocking** | Sits in §10b qualitative, outside every threshold. Cannot affect the decision |
| **Q5** | Role hours (§9.3) do not reconcile to line items (§9.4) | **D — non-blocking** | Both total within the 30-hour cap. No threshold depends on the split |
| **Q6 / TW** | Terminal-wealth figures +8.2% / +9.1% were authored, not specified | **A** | Resolvable, **and required** — invented empirical results must not be presented as observed facts |
| **L10** | Terminal-wealth heading appears only in report-bearing records | **A** | Resolvable by the Q6 fix plus a mechanical redaction extension |
| **L1–L5, L8, L9** | Blinding leak vectors | **D** | Controls already specified and implemented |
| **L6** | Evaluators comparing packs | **D** | Behavioural; controlled as far as documents allow (independence statement, separate shuffles) |
| **L7** | Moderator inferring the hypothesis | **D** | Largest uncontrolled residual; controlled by verbatim scripts and Part-4-only briefing. **Not further reducible in documents** |
| **C1** | No external moderator | **B — human dependency** | Cannot be resolved in documents |
| **C2** | <3 Track A participants | **B** | Cannot be resolved in documents |
| **C3** | Constraint author unconfirmed | **B** | Cannot be resolved in documents |
| **C4** | <3 evaluators / none zero-exposure | **B** | Cannot be resolved in documents |
| **C7** | Warm-up not authored | **A → RESOLVED** | Closed by this amendment |

**No issue was classified C (prohibited design change). No resolution below alters a hypothesis or threshold.**

---

## PART 2 — A-001 · Warm-up requirement

| | |
|---|---|
| **Source conflict** | Ops §4.2 allocates 5 minutes to a "warm-up case (discarded)". No warm-up content exists anywhere in the Ops Package or artifact set |
| **Resolution** | Create `01_participant/warmup.md` — a **practice exercise**, not a study case. Separate fictional portfolio (Kestrel, $4.0M, 18 positions) and security (DELTA, regional utilities). No report, no sham, no score. **PRE form only; no POST form.** Marked `WARM-UP — DISCARD` and excluded from every dataset. Target 3 minutes, hard stop 4:00 |
| **Rationale** | The protocol requires it; only the content was absent. It teaches the response format and nothing else. Using a different portfolio prevents anchoring on Meridian's limits. Omitting the POST form prevents any early signal that a second question follows — a blinding gain over reusing a study case |
| **Prohibited alternatives rejected** | An eighth study case (would alter participant burden and the case set) · reusing Case F (would contaminate the sham) |
| **Affected files** | **NEW** `01_participant/warmup.md` · `02_moderator/moderator_kit.md` §E.1, §F, §K · `directory_manifest.md` · `00_COMPLIANCE_MATRIX.md` · `quality_control_report.md` §2 Q1, §6 cond. 7 |
| **Preregistration change** | **No.** Warm-up data is not collected, not analysed, and enters no threshold |

---

## PART 3 — A-002 · Attribution coding

| | |
|---|---|
| **Source conflict** | Ops §7.2 allows `ATTRIB` to be satisfied when "reasoning_text names a report section unprompted (coder-confirmed)", but defines no coder, timing, permitted information, or unclear-case rule |
| **Resolution** | See the operating rules below |
| **Rationale** | `ATTRIB` is a **Gate 1** field. Blinding in this study protects **Gate 2** (quality), which is scored solely by the three blinded evaluators. Attribution is a mechanical match of the participant's own words against a **closed 14-item checklist**, so it needs neither blinding nor a second rater. **No new paid role is introduced** |
| **Affected files** | `05_analyst/data_capture_spec.md` §7.2 · `analysis_report_template.md` §5 · `evaluator_kit.md` (no change — attribution is outside the evaluator role) |
| **Preregistration change** | **No.** The `ATTRIB` definition is unchanged; only its operating procedure is specified |

### A-002 operating rules — binding

| # | Rule |
|---|---|
| 1 | **Who:** the **analyst**. No new role, no additional cost |
| 2 | **When:** after data entry, and **before evaluator scores are received or opened.** Attribution can therefore never be influenced by a quality outcome |
| 3 | **May see:** the POST form Q4 ticks · the POST form Q3 reasoning text · the report for that case (needed to verify a named section exists) |
| 4 | **May NOT see:** any evaluator score, any classification, any aggregate result |
| 5 | **Categories:** exactly the 14 tokens on the POST form Q4 checklist. No new category may be created |
| 6 | **Recording:** the checklist token(s), in `sections_ticked` |
| 7 | **Multiple sections:** all are recorded; `distinct_sections` counts the union across the study |
| 8 | **Unprompted naming:** the analyst must **record the verbatim quoted phrase** justifying the attribution in a new field `attrib_quote`. An attribution with no quote is invalid |
| 9 | **Unclear:** `ATTRIB = FALSE`. This is deliberately conservative — it makes Gate 1 **harder** to pass, never easier |
| 10 | **Separation:** the analyst **never** scores Q1, Q2, Q3 or `UNSUP`. Those come only from E1–E3 |

---

## PART 4 — A-003 · Coder count and Cohen's κ

| | |
|---|---|
| **Source conflict** | The superseded `PHASE1_STUDY_PACKAGE.md` required "two coders … κ reported". `PHASE1_OPERATIONS_PACKAGE.md` — which explicitly supersedes it — specifies a single analyst plus three blinded evaluators with 2-of-3 adjudication, and **never mentions κ** |
| **Resolution** | **OPTION C — κ is removed.** The governing frozen protocol does not require it |
| **Rationale** | Three reasons. (1) **Precedence:** the Ops Package states it supersedes the study package; the earlier requirement has no force. (2) **Function already discharged:** 2-of-3 majority adjudication provides the inter-rater safeguard κ was meant to provide, and does so *load-bearingly* — it **sets the code**, whereas κ would merely be reported. The `UNRESOLVED` rate is the direct measure of disagreement and already **caps the result at AMBIGUOUS above 30%**. (3) **No invention:** computing κ across three raters on a mixed ordinal/set/binary instrument would require choosing a variant (Fleiss, weighted, per-dimension) that the protocol never specified. Selecting one now would be inventing a measure to fill a field |
| **Options rejected** | **A** — the evaluators do provide independent coding, but of *quality*, not of `ATTRIB`; conflating them would breach the separation in A-002. **B** — designating evaluators as attribution coders would unblind them to the report's existence. **D** — leaving it unresolved would leave an unfillable field in the final report |
| **Affected files** | `05_analyst/analysis_report_template.md` §7 · `05_analyst/data_capture_spec.md` · `quality_control_report.md` §2 Q3 |
| **Preregistration change** | **No.** κ appears in no threshold, in no PASS/FAIL condition, and in no hypothesis |

**Replacement reporting (already required by the frozen protocol):** disagreement-log entry count ·
`UNRESOLVED_RATE` (PASS ≤ 30%) · `BLINDING_ACCURACY` (PASS ≤ 65%).

---

## PART 5 — A-004 · Terminal-wealth disclosure

| | |
|---|---|
| **Source conflict** | ARCHITECTURE_V3 mandates a terminal-wealth disclosure on every report. The Ops Package requires the section but specifies **no values**. Values of +8.2% and +9.1% were authored during artifact production |
| **Resolution** | **OPTION B — a clearly labelled "not available in this pilot" statement**, identical on all six report-bearing cases |
| **Rationale** | Option A presents **invented empirical results as observed facts** — prohibited outright, and a direct violation of the architectural principle the disclosure exists to serve. Option C is impossible: the cases carry no decision history from which to calculate. Option D would omit an architecturally mandated section and change what participants evaluate. **Option B is the only choice that is both permitted and faithful: the section is present, and it honestly discloses its own absence** — which is precisely what the disclosure is for |
| **Affected files** | `01_participant/case_A.md`, `case_B.md`, `case_C.md`, `case_D.md`, `case_E.md`, `case_G.md` · `05_analyst/data_capture_spec.md` (redaction rule) · `quality_control_report.md` §2 Q6, §5 L10 |
| **Preregistration change** | **No.** No threshold references terminal wealth |

### Replacement text — identical on all six reports

```
TERMINAL-WEALTH DISCLOSURE
  Not available. This platform has no recorded decision history, so the
  realised outcome of following its recommendations versus taking no
  action cannot be reported. This section will carry that comparison
  once a decision archive exists.
```

**Applied: 6 of 6 report-bearing cases patched. Zero invented empirical figures remain in any
participant-facing artifact.**

### L10 — terminal-wealth heading as a condition leak

| | |
|---|---|
| **Residual** | The section heading appears only on report-bearing records. A POST reasoning text referring to it would identify the record as POST |
| **Resolution** | Two measures. (1) **Option B substantially reduces the risk on its own** — a participant is far less likely to reference "not available" than a concrete return figure. (2) **Redaction rule extended**: any reference to *terminal wealth*, *following these recommendations*, or the disclosure by name is redacted to `[reference to a report section]` — a mechanical extension of the existing numeric-redaction rule, applied by the redactor before packs are distributed |
| **Residual after fix** | **Low, and measured.** Any remaining leak surfaces in `BLINDING_ACCURACY`, which caps the result at AMBIGUOUS above 65%. Not silently absorbed |

---

## PART 6 — A-005 and A-006 · Non-blocking reconciliations

**A-005 — disconfirming quotes (Q4).** The ≥2 minimum in `analysis_report_template.md` §10b is an
**ops-lead reporting floor**, not a protocol requirement. It sits in the qualitative section, outside
every threshold, and cannot affect the computed decision. **Retained as an operational floor.** No
preregistration change.

**A-006 — hour reconciliation (Q5).** Ops §9.4's **line-item table governs** and totals exactly 30 team
hours. §9.3's per-role hours are indicative and do not sum identically because the 1-hour moderator
briefing appears in the "role recruitment + briefing" line while being moderator time. **The 30-hour cap
is unchanged and unaffected.** No preregistration change.

---

## Signature and hash block

```
AMENDMENT 001 · VERSION 1.0

Issues resolved: A-001 (warm-up) · A-002 (attribution coding) · A-003 (kappa removed)
                 A-004 (terminal wealth + L10) · A-005 · A-006

Hypotheses changed          ▢ NO   [must be NO]
Thresholds changed          ▢ NO   [must be NO]
Preregistration changed     ▢ NO   [must be NO]
Case set changed            ▢ NO   [must be NO]
Budget changed              ▢ NO   [must be NO]

Prepared by ______________________   Date ______________

Approved by (Ops lead) ______________________   Date ______________

File name    PHASE1_PROTOCOL_AMENDMENT_001.md
SHA-256      ____________________________________________________
Recorded in preregistration  ▢       Placed in 08_frozen/  ▢
```

```bash
shasum -a 256 docs/phase1/PHASE1_PROTOCOL_AMENDMENT_001.md
```

**This amendment must be signed and hashed before recruitment begins.**
