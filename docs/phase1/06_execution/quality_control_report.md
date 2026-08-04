# QUALITY-CONTROL REPORT

Line-by-line consistency review of the produced artifacts against `PHASE1_OPERATIONS_PACKAGE.md`.
**Ambiguities are listed, not silently resolved.**

---

## §1 — Requirements satisfied

| Ops § | Requirement | Artifact | ✓ |
|---|---|---|---|
| 1.1–1.9 | Hypotheses, dual gate, thresholds, anti-redesign rule | `analysis_report_template.md` §11–12 | ✓ |
| Part 2 preamble | Shared Meridian frame with all frozen values | `01_participant/00_frame_consent.md` | ✓ |
| Part 2 · A–G | Seven cases, baseline + report, frozen values | `case_A.md` … `case_G.md` | ✓ |
| Part 2 | Evaluator notes, expected constraints, classifications, bias risks **excluded** from participant files | verified — none appear | ✓ |
| Part 2 | Case F has no report; sham status not disclosed to participant | `case_F.md` | ✓ |
| Part 2 | Case G carries the score; arm status not disclosed | `case_G.md` | ✓ |
| §2.1 | Frozen 5×7 order; F and G never position 1 or 7 | `moderator_kit.md` §G | ✓ |
| §3.1–3.4 | Recruitment, screener, consent, scheduling | kit §§A–C, `00_frame_consent.md` | ✓ |
| §3.5 | Neutral introduction verbatim | kit §E.1 | ✓ |
| §3.6 | Pre-decision form | `forms.md` FORM 1 | ✓ |
| §3.7 | Post-decision form, **"Nothing changed" first**, reasoning required on every case | `forms.md` FORM 2 | ✓ |
| §3.8 | Final questionnaire | `forms.md` FORM 3 | ✓ |
| §3.9 | Debrief | kit §E.8 | ✓ |
| §4.1 | Usable by someone who has read no architecture document | kit header | ✓ |
| §4.2 | Timing guide, per-case budget, overrun rule | kit §F | ✓ |
| §4.3 | Commit / reveal / re-elicit / probe / sham scripts | kit §E.2–E.6 | ✓ |
| §4.4 | Prohibited language | kit §I | ✓ |
| §4.5 | Interruption rules | kit §F + §E.4 | ✓ |
| §4.6 | Clarification card incl. Case F response | kit §H | ✓ |
| §4.7 | Deviation form with minimum log list | kit §J | ✓ |
| §4.8–4.9 | Pre/post session checklists | kit §K–L | ✓ |
| §9.4 | Compensation log against the $500 participant cap | kit §M | ✓ |
| §5.1 | Evaluator criteria incl. ≥1 zero-exposure | evaluator kit §2 | ✓ |
| §5.2 | Neutral briefing, verbatim, nothing further disclosed | evaluator kit §4 | ✓ |
| §5.3 | Individual-record form, non-sequential IDs, guess field | evaluator kit §5 | ✓ |
| §5.4–5.6 | Q1 / Q2 / Q3 rubrics with anchors | evaluator kit §6–8 | ✓ |
| §5.7 | Five classifications, strict precedence, **analyst-computed** | `data_capture_spec.md` §7.3 | ✓ |
| §5.8–5.10 | Adjudication, unresolved, disagreement log | evaluator kit §11–13 | ✓ |
| §6.1–6.4 | Constraint-author instructions, COI, template, signing, freeze | `constraint_author_kit.md` | ✓ |
| §7.1 | Field dictionary — 10 tables | `data_capture_spec.md` | ✓ |
| §7.2 | Derived-flag rules incl. null-magnitude handling | `data_capture_spec.md` §7.2 | ✓ |
| §7.3 | All aggregate formulas; FAIL first; G excluded | `data_capture_spec.md` | ✓ |
| Part 8 | Fillable report, fixed limitations, mechanical decision | `analysis_report_template.md` | ✓ |
| §9.1–9.3 | Directory, permissions, role isolation | `directory_manifest.md` | ✓ |

## §2 — Ambiguities — STATUS AFTER AMENDMENT 001

**All six are now CLOSED.** Resolutions are recorded in `PHASE1_PROTOCOL_AMENDMENT_001.md` and are
binding. None changed a hypothesis, threshold, case, participant count, or budget.

| # | Issue | Class | Resolution | Amendment |
|---|---|---|---|---|
| **Q1** | Warm-up content unspecified | A | `01_participant/warmup.md` created — practice only, separate portfolio (Kestrel/DELTA), PRE form only, discarded | **A-001 · CLOSED** |
| **Q2** | "Coder-confirmed attribution" undefined | A | The **analyst** codes ATTRIB, **before** evaluator scores are opened, against the closed 14-token checklist; `attrib_quote` required for unprompted attribution; **unclear → FALSE** | **A-002 · CLOSED** |
| **Q3** | Two coders + κ vs single analyst | A | **κ REMOVED.** The governing frozen protocol never required it; 2-of-3 adjudication + `UNRESOLVED_RATE` + `BLINDING_ACCURACY` already discharge the function and are load-bearing | **A-003 · CLOSED** |
| **Q4** | Disconfirming-quote minimum ops-authored | D | Retained as an operational floor; sits outside every threshold | **A-005 · CLOSED** |
| **Q5** | Role hours vs line items | D | §9.4 line-item table governs and totals exactly 30; §9.3 per-role figures are indicative. Cap unchanged | **A-006 · CLOSED** |
| **Q6** | Terminal-wealth figures authored | A | **Replaced with a "not available" disclosure** on all 6 report-bearing cases. Zero invented empirical figures remain | **A-004 · CLOSED** |

### Superseded — original wording retained for audit

*(The table below is the pre-amendment record. It is no longer actionable.)*

<details><summary>Original §2 (superseded)</summary>

| # | Ambiguity | Ops § | Impact | Decision required from |
|---|---|---|---|---|
| **Q1** | The warm-up case is required (§4.2) but no warm-up content is specified anywhere in the Ops Package. | §4.2 | Blocking — the moderator cannot run §E.1 without it | **Ops lead.** Options: reuse Case F's baseline as the warm-up (would contaminate the sham), or author an eighth throwaway baseline. **Cannot be resolved by the artifact lead without a design decision.** |
| **Q2** | `ATTRIB` may be satisfied by "reasoning_text names a report section unprompted (coder-confirmed)" (§7.2), but no coder role, procedure, or blinding status is defined for that determination. | §7.2 | Moderate — affects the Gate 1 numerator | **Ops lead.** Who confirms, and are they blind to phase? |
| **Q3** | §7.1 specifies "two coders … κ reported" for change scoring in the earlier package; the Ops Package §7.3 describes a single analyst. | §7.1 vs §7.3 | Low–moderate — κ may be uncomputable | **Ops lead.** If a single analyst codes, κ cannot be reported and §7 of the final report has no value to enter. |
| **Q4** | §10c of the report template asks for "notable disconfirming quotes"; the Ops Package requires them in the analysis plan but sets no minimum. Template imposes ≥2. | Part 8 | Low | Confirm ≥2 is acceptable or set to 0. |
| **Q5** | The Ops Package caps team time at 30 h but assigns 14 h to the ops lead/analyst; the tasks listed for that role total ~15 h once record preparation is included. | §9.3–9.4 | Low | Confirm the 1-hour overrun is absorbed or that the redaction hour is counted elsewhere. |
| **Q6** | Terminal-wealth figures (+8.2% vs +9.1%) were required by the report spec but no values are given in the Ops Package. Values used here are internally consistent and identical across all reports. | Part 2 | Low — but they are **authored, not specified** | **Ops lead must ratify these numbers before freeze**, or supply alternatives. |

</details>

**No ambiguity remains open. Q1 is closed by A-001.**

## §2b — Arithmetic defects (Amendment 002)

| ID | Case(s) | Defect | Class | Resolution |
|---|---|---|---|---|
| **D-01** | A | Full exit stated 16.2 days; computed **0.0162 days** (997.7×). Reachable only at an undocumented 0.1% participation rate | **C — material case-design change** | Liquidity removed as the EXIT-elimination reason; replaced with the Case-C wording *"the cap mandate does not require exit"*. Case A retains 4 material constraints |
| **D-02** | **A, C and G** | Total portfolio HHI stated below its mathematical floor in **all three** HHI-bearing reports (A 0.071<0.1029 · C 0.048<0.0652 · G 0.041<0.0468) | A — factual | Replaced with the position's own concentration contribution `w²`, exactly computable |
| **D-03** | B | Move-to-target stated 3.1% of ADV; computed **0.52%**. 3.1% is the position *weight* — wrong field transcribed | A — factual | Corrected to 0.5% |

**Scope note:** `PROTOTYPE_ENGINEERING_ASSESSMENT.md` flagged D-02 for Case A only. Independent
recomputation extended it to **Case G and then Case C** — every HHI figure in the study was impossible.

**Verification layer added:** `tools/phase1/{case_facts.py,verify_reports.py}` — 81 checks, exit 0.
**Negative control passed:** reintroducing D-01/D-02/D-03 produces 4 failures and exit 1.

## §3 — Artifacts requiring human signature, external authorship, or participant input

| Artifact | Requires | Status |
|---|---|---|
| `constraints_v1.0.md` | **External constraint author** — authorship + 2 signatures | **NOT STARTED — blocking §9.2 freeze** |
| Moderator identity | External person confirmed | **NOT STARTED — blocking recruitment (§9.5 cond. 1)** |
| Evaluator eligibility forms × 3 | 3 external professionals, ≥1 zero-exposure | **NOT STARTED** |
| Evaluator confidentiality statements × 3 | Signature | NOT STARTED |
| Participant consent × 5 | Signature | NOT STARTED |
| Eligibility confirmation × 5 | Moderator initials | NOT STARTED |
| Compensation log | Moderator initials × 5 | NOT STARTED |
| All response data | 5 real participants | NOT STARTED |
| Deviation forms × 5 | Moderator signature | NOT STARTED |
| Final report §0 hashes | Ops lead, before session 1 | NOT STARTED |
| Final report signatures | Analyst + moderator | NOT STARTED |
| Warm-up case content | — | **AUTHORED — `01_participant/warmup.md` (A-001)** |
| **Amendment 001 signatures** | Preparer + Ops lead | **NOT STARTED — blocking recruitment** |
| **Amendment 002 signatures** | Preparer + Ops lead | **NOT STARTED — blocking freeze** |

## §4 — Must be hashed and frozen

**Before recruitment:** **`PHASE1_PROTOCOL_AMENDMENT_001.md` (signed + hashed)** ·
`00_COMPLIANCE_MATRIX.md` · `moderator_kit.md` §§A–C · `directory_manifest.md` · this report.

**Before session 1 — into `08_frozen/` with SHA-256 in `HASHES.txt`:**
`preregistration.md` · `PHASE1_PROTOCOL_AMENDMENT_001.md` · all **10** files in `01_participant/`
(including `warmup.md`) · `moderator_kit.md` (full) ·
`case_order_frozen.md` · **`constraints_v1.0.md`** · `evaluator_kit.md` · `data_capture_spec.md` ·
`analysis_report_template.md`

```bash
shasum -a 256 docs/phase1/08_frozen/* > docs/phase1/08_frozen/HASHES.txt
chmod -R a-w docs/phase1/08_frozen/
```

## §5 — Potential blinding leaks *(each with its control)*

| # | Leak vector | Control | Residual risk |
|---|---|---|---|
| **L1** | `LINKAGE_record_map.csv` reaching an evaluator | Stored outside the evaluator share; OPS-only; never attached to email | **Void Gate 2 if it occurs** |
| **L2** | Post-report reasoning quoting report-only figures | Mechanical redaction: numeric strings appearing only in the report → `[figure]` | Partial — measured by the guess field |
| **L3** | Sequential or case-clustered record IDs | IDs drawn from a shuffled pool | Low |
| **L4** | Pre/post records adjacent in a pack | Shuffle across participants and cases; no two related records adjacent | Low |
| **L5** | Constraint author seeing a report → platform wording in the constraint list | Author receives **page 1 only**, cases A,B,C,D,E,G | Low |
| **L6** | Evaluators comparing packs | Independence statement; separate packs; separate shuffles | Behavioural — unverifiable |
| **L7** | Moderator inferring the hypothesis and leaking tone | Moderator briefed on Part 4 only; scripts verbatim; prohibited-language card | Moderate — **the largest uncontrolled residual** |
| **L8** | Participant deducing Case F is a control | No comment on the missing page; clarification card response fixed | Low; logged if asked |
| **L9** | Case G's score revealing the arm to evaluators | Redact the score **and** its decomposition | Low |
| **L10** | Terminal-wealth heading appears only on report-bearing records | **CLOSED by A-004.** (1) The "not available" text is far less likely to be quoted than a return figure. (2) Redaction rule **R2** now maps any reference to *terminal wealth* / *following these recommendations* to `[reference to a report section]` | **Low, and measured** — any residual surfaces in `BLINDING_ACCURACY`, which caps the result at AMBIGUOUS above 65% |

## §6 — Conditions requiring cancellation before testing *(Ops §9.5)*

| # | Condition | Status | Action |
|---|---|---|---|
| 1 | No external moderator within 3 h of effort | **OPEN** | **Cancel.** No compliant fallback |
| 2 | Fewer than 3 Track A participants qualify | OPEN | **Cancel** |
| 3 | Constraint author unavailable or won't sign | **OPEN** | **Cancel.** Study is circular without it |
| 4 | Fewer than 3 evaluators, or none zero-exposure | **OPEN** | **Cancel.** Gate 2 unrunnable |
| 5 | Recruitment exceeds 6 h without 5 participants | not started | **Record FAIL** — not a cancellation |
| 6 | Reports cannot be static one-pagers within 5 h | **SATISFIED** — all seven produced as static text | — |
| **7** | Warm-up case content not authored (Q1) | **CLOSED — A-001** | `01_participant/warmup.md` authored |
| **8** | **Amendment 001 unsigned / unhashed** | **OPEN** | **Cannot begin recruitment.** The amendment governs four artifacts already in use |
| **9** | Case A liquidity arithmetic (D-01) | **CLOSED — Amendment 002** | Corrected; verifier clean |
| **10** | **Amendment 002 unsigned / unhashed** | **OPEN — NEW** | **Cannot freeze.** Governs a material case-design change |

**Warm-up removal note:** the warm-up is **not** subject to the Case G drop-trigger. It is required by
Ops §4.2 and costs 3 minutes of session time, not team hours.

**Case G drop-trigger:** if projected total exceeds 30 team-hours at the end of §9.1, remove Case G and
`case_G.md`. Sessions shorten to 82 minutes. Gate 1 and Gate 2 are unaffected (G is excluded from both).
Final questionnaire Q5–Q6 must then be struck, as they require the E-vs-G comparison.
