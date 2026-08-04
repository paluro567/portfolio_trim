# Phase 1 — Artifact Compliance Matrix

**Sole authoritative specification:** `docs/PHASE1_OPERATIONS_PACKAGE.md` (the "Ops Package").
This matrix records governance only. It does not reinterpret any requirement.

| # | Artifact | File | Governing §§ | Intended user | Freeze point | Restricted? |
|---|---|---|---|---|---|---|
| 0 | **Protocol Amendment 001** | `PHASE1_PROTOCOL_AMENDMENT_001.md` | Ops §§4.2, 7.2, 7.3; ARCH_V3 | Ops lead | **Before recruitment** | No |
| 0a | **Protocol Amendment 002** | `PHASE1_PROTOCOL_AMENDMENT_002.md` | Factual integrity; Ops Part 2 | Ops lead | **Before freeze** | No |
| 0c | **Verification layer** | `tools/phase1/{case_facts,verify_reports}.py` | Amendment 002 Part 7 | Ops lead | Before freeze | Analyst-only |
| 0b | **Warm-up practice sheet** | `01_participant/warmup.md` | §4.2 · A-001 | Participant via MOD | Before session 1 | **Practice status is moderator-only** |
| 1 | Shared portfolio frame | `01_participant/00_frame_consent.md` | Part 2 preamble | Participant | Before session 1 | No |
| 2 | Consent language | `01_participant/00_frame_consent.md` | §3.3 | Participant | Before recruitment | No |
| 3 | Case A packet (baseline + report) | `01_participant/case_A.md` | Part 2 · Case A | Participant | Before session 1 | **Report withheld until reveal** |
| 4 | Case B packet | `01_participant/case_B.md` | Part 2 · Case B | Participant | Before session 1 | **Report withheld until reveal** |
| 5 | Case C packet | `01_participant/case_C.md` | Part 2 · Case C | Participant | Before session 1 | **Report withheld until reveal** |
| 6 | Case D packet | `01_participant/case_D.md` | Part 2 · Case D | Participant | Before session 1 | **Report withheld until reveal** |
| 7 | Case E packet | `01_participant/case_E.md` | Part 2 · Case E | Participant | Before session 1 | **Report withheld until reveal** |
| 8 | Case F packet (baseline only — no report) | `01_participant/case_F.md` | Part 2 · Case F | Participant | Before session 1 | **Sham status restricted** |
| 9 | Case G packet | `01_participant/case_G.md` | Part 2 · Case G | Participant | Before session 1 | **Score-arm status restricted** |
| 10 | Pre-decision form | `01_participant/forms.md` | §3.6 | Participant | Before session 1 | No |
| 11 | Post-decision form | `01_participant/forms.md` | §3.7 | Participant | Before session 1 | No |
| 12 | Final questionnaire | `01_participant/forms.md` | §3.8 | Participant | Before session 1 | No |
| 13 | Recruitment message | `02_moderator/moderator_kit.md` §A | §3.1 | Recruiter | **Before recruitment** | No |
| 14 | Screener | `02_moderator/moderator_kit.md` §B | §3.2 | Recruiter | **Before recruitment** | No |
| 15 | Scheduling message | `02_moderator/moderator_kit.md` §C | §3.4 | Recruiter | **Before recruitment** | No |
| 16 | Eligibility confirmation sheet | `02_moderator/moderator_kit.md` §D | §3.2, §9.5 | Moderator | Before session 1 | Yes — participant PII |
| 17 | Moderator master script | `02_moderator/moderator_kit.md` §E | §3.5, §4.3 | Moderator | Before session 1 | **Yes — sham script** |
| 18 | Timing sheet | `02_moderator/moderator_kit.md` §F | §4.2 | Moderator | Before session 1 | No |
| 19 | Case-order assignment + randomisation | `02_moderator/moderator_kit.md` §G | §2.1 | Moderator | **Before session 1 (frozen)** | **Yes — reveals arms** |
| 20 | Clarification-response card | `02_moderator/moderator_kit.md` §H | §4.6 | Moderator | Before session 1 | Yes |
| 21 | Prohibited-language card | `02_moderator/moderator_kit.md` §I | §4.4 | Moderator | Before session 1 | Yes |
| 22 | Protocol-deviation form | `02_moderator/moderator_kit.md` §J | §4.7 | Moderator | Before session 1 | Yes |
| 23 | Pre-session checklist | `02_moderator/moderator_kit.md` §K | §4.8 | Moderator | Before session 1 | Yes |
| 24 | Post-session checklist | `02_moderator/moderator_kit.md` §L | §4.9 | Moderator | Before session 1 | Yes |
| 25 | Compensation log | `02_moderator/moderator_kit.md` §M | §9.4 | Moderator | Before session 1 | Yes — PII |
| 26 | Debrief script | `02_moderator/moderator_kit.md` §N | §3.9 | Moderator | Before session 1 | Yes |
| 27 | Constraint-author COI declaration | `03_constraint_author/constraint_author_kit.md` §1 | §6.2 | Constraint author | **Before session 1** | No |
| 28 | Constraint-author instructions | `03_constraint_author/constraint_author_kit.md` §2 | §6.1 | Constraint author | **Before session 1** | Partial — case baselines only |
| 29 | Blank constraint template | `03_constraint_author/constraint_author_kit.md` §3 | §6.4 | Constraint author | **Before session 1** | No |
| 30 | Per-case constraint templates (A,B,C,D,E,G) | `03_constraint_author/constraint_author_kit.md` §4 | §6.4 | Constraint author | **Before session 1** | No |
| 31 | Signing / versioning block | `03_constraint_author/constraint_author_kit.md` §5 | §6.3, §6.4 | Constraint author | **Before session 1** | No |
| 32 | Freeze + hashing checklist | `03_constraint_author/constraint_author_kit.md` §6 | §6.3, §9.2 | Ops lead | **Before session 1** | No |
| 33 | Evaluator invitation | `04_evaluator/evaluator_kit.md` §1 | §5.1 | Evaluator | Before evaluation | No |
| 34 | Evaluator eligibility form | `04_evaluator/evaluator_kit.md` §2 | §5.1, §3.2 | Evaluator | Before evaluation | No |
| 35 | Confidentiality + independence statement | `04_evaluator/evaluator_kit.md` §3 | §5.1 | Evaluator | Before evaluation | No |
| 36 | Neutral evaluator briefing | `04_evaluator/evaluator_kit.md` §4 | §5.2 | Evaluator | Before evaluation | **Blinded — verbatim only** |
| 37 | Randomised record scoring form | `04_evaluator/evaluator_kit.md` §5 | §5.3 | Evaluator | Before evaluation | **Blinded** |
| 38 | Q1 rubric | `04_evaluator/evaluator_kit.md` §6 | §5.4 | Evaluator | Before evaluation | Blinded |
| 39 | Q2 rubric | `04_evaluator/evaluator_kit.md` §7 | §5.5 | Evaluator | Before evaluation | Blinded |
| 40 | Q3 rubric | `04_evaluator/evaluator_kit.md` §8 | §5.6 | Evaluator | Before evaluation | Blinded |
| 41 | UNSUP flag instructions | `04_evaluator/evaluator_kit.md` §9 | §5.3, §5.7 | Evaluator | Before evaluation | Blinded |
| 42 | Pre/post guess field | `04_evaluator/evaluator_kit.md` §10 | §5.3 | Evaluator | Before evaluation | Blinded |
| 43 | Disagreement log | `04_evaluator/evaluator_kit.md` §11 | §5.10 | Analyst | Before evaluation | Analyst-only |
| 44 | Adjudication form | `04_evaluator/evaluator_kit.md` §12 | §5.8 | Analyst | Before evaluation | Analyst-only |
| 45 | Unresolved-record form | `04_evaluator/evaluator_kit.md` §13 | §5.9 | Analyst | Before evaluation | Analyst-only |
| 46 | Data-capture workbook spec | `05_analyst/data_capture_spec.md` | §7.1–7.3 | Analyst | **Before session 1** | Analyst-only |
| 47 | Final analysis + decision report | `05_analyst/analysis_report_template.md` | Part 8 | Analyst | **Before session 1** | Analyst-only |
| 48 | Execution directory manifest | `06_execution/directory_manifest.md` | §9.1–9.3 | Ops lead | Before recruitment | No |
| 49 | Quality-control report | `06_execution/quality_control_report.md` | Part 9 | Ops lead | Before recruitment | No |

## Freeze summary

**Must be frozen BEFORE recruitment begins** (§9.1): artifacts 13, 14, 15, 48, 49 — plus this matrix
**and artifacts 0 and 0a — `PHASE1_PROTOCOL_AMENDMENT_001.md` and
`PHASE1_PROTOCOL_AMENDMENT_002.md`, both signed and hashed, with
`tools/phase1/verify_reports.py` exiting 0.**

**Must be frozen BEFORE the first session** (§9.2): artifacts 0b, 1–12, 16–26, 27–32, 46, 47.
Artifacts 33–45 must exist and be frozen before evaluation begins; the Ops Package requires the
**constraint list (30–32) to be signed and hashed before Day 6 completes**, i.e. before any session.

**Restricted-distribution artifacts** (a leak invalidates blinding or the sham): 19, 17, 8, 9, 36–42,
43–45, 46, 47.
