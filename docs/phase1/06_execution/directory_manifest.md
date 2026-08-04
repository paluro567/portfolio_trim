# EXECUTION DIRECTORY MANIFEST

**Principle: no person receives files beyond what their role requires.**
Roles: **OPS** (ops lead / analyst / architect) · **MOD** (external moderator) · **CA** (constraint
author) · **EVAL** (E1–E3) · **PART** (participants).

---

## Structure

```
docs/phase1/
│
├── 00_COMPLIANCE_MATRIX.md ................. OPS
├── PHASE1_PROTOCOL_AMENDMENT_001.md ........ OPS (signed + hashed before recruitment)
├── PHASE1_PROTOCOL_AMENDMENT_002.md ........ OPS (signed + hashed before freeze)
│
├── 01_participant/  ........................ PART (via MOD, one page at a time)
│   ├── 00_frame_consent.md
│   ├── warmup.md ........................... practice only; NOT a study case
│   ├── forms.md
│   ├── case_A.md   ├── case_B.md   ├── case_C.md
│   ├── case_D.md   ├── case_E.md   ├── case_F.md   └── case_G.md
│
├── 02_moderator/  .......................... MOD only
│   └── moderator_kit.md
│
├── 03_constraint_author/  .................. CA only
│   ├── constraint_author_kit.md
│   └── case_baselines_for_author/ .......... page 1 of cases A,B,C,D,E,G ONLY
│
├── 04_evaluator/
│   ├── evaluator_kit.md .................... §§1–10 to EVAL; §§11–13 OPS only
│   └── record_packs/
│       ├── E1_records.pdf  ├── E2_records.pdf  ├── E3_records.pdf
│       └── constraints_v1.0.md ............. read-only copy
│
├── 05_analyst/  ............................ OPS only
│   ├── data_capture_spec.md
│   └── analysis_report_template.md
│
├── 06_execution/  .......................... OPS
│   ├── directory_manifest.md
│   └── quality_control_report.md
│
├── 07_responses/  .......................... OPS only — CONTAINS LINKAGE
│   ├── forms_scanned/          <participant_id>/<case_id>_<PRE|POST>.pdf
│   ├── transcripts/            <participant_id>.txt
│   ├── deviations/             <participant_id>_deviations.pdf
│   ├── compensation_log.pdf
│   ├── data/                   the 10 CSVs from data_capture_spec.md
│   └── LINKAGE_record_map.csv  ** record_id → participant_id, case_id, phase **
│
├── 08_frozen/  ............................. READ-ONLY after Day 6
│   ├── preregistration.md
│   ├── PHASE1_PROTOCOL_AMENDMENT_001.md .... signed, hashed
│   ├── PHASE1_PROTOCOL_AMENDMENT_002.md .... signed, hashed
│   ├── constraints_v1.0.md ................. CA-authored, signed, hashed
│   ├── case_order_frozen.md ................ the §G table
│   └── HASHES.txt .......................... SHA-256 of every frozen artifact
│
└── 09_final/  .............................. OPS; circulated after the decision
    ├── PHASE1_FINAL_REPORT.md
    └── PHASE1_NEGATIVE_RESULT.md ........... produced ONLY on FAIL
```

**Outside `docs/phase1/`:**
```
tools/phase1/  ............................. OPS only
├── case_facts.py .......................... study case inputs, no narrative
└── verify_reports.py ...................... 81 checks; must exit 0 before freeze
```

## Access permissions

| Directory | OPS | MOD | CA | EVAL | PART | Note |
|---|---|---|---|---|---|---|
| `00_COMPLIANCE_MATRIX.md` | RW | — | — | — | — | |
| `01_participant/` | RW | **R** | — | — | **view only, one page at a time** | MOD controls reveal |
| `02_moderator/` | RW | **R** | — | — | — | **Contains sham script and arm assignment** |
| `03_constraint_author/` | RW | — | **RW** | — | — | CA sees case baselines only |
| `03_.../case_baselines_for_author/` | RW | — | **R** | — | — | **No reports. No Case F.** |
| `04_evaluator/` §§1–10 | RW | — | — | **R** | — | |
| `04_evaluator/` §§11–13 | RW | — | — | **NO** | — | Adjudication is analyst-only |
| `04_.../record_packs/` | RW | — | — | **R (own pack only)** | — | E1 must not see E2's pack |
| `05_analyst/` | RW | — | — | — | — | |
| `06_execution/` | RW | R | — | — | — | |
| `07_responses/` | **RW** | append only | — | — | — | **MOD may deposit, never read others'** |
| `07_.../LINKAGE_record_map.csv` | **RW — OPS ONLY** | — | — | **NEVER** | — | **Blinding-critical** |
| `08_frozen/` | **R after Day 6** | R | — | — | — | Write-protected post-freeze |
| `09_final/` | RW | R after decision | R after decision | R after decision | — | |

## Critical isolation rules

1. **`LINKAGE_record_map.csv` is the single blinding-critical file.** It is the only artifact mapping
   `record_id` → `participant_id` + `phase`. If an evaluator obtains it, **Gate 2 is void.** Store
   outside the evaluator share; never attach it to any evaluator email.
2. **`02_moderator/` must never reach an evaluator or participant** — it contains the arm assignment and
   the sham distractor script.
3. **The constraint author receives page 1 only** of cases A, B, C, D, E, G. **Never a report. Never
   Case F.** Seeing a report would let platform wording contaminate the constraint list and reintroduce
   circularity.
4. **Each evaluator receives only their own record pack**, in their own shuffle order.
5. **`08_frozen/` is chmod read-only after Day 6.** Any write is a protocol deviation.

```bash
chmod -R a-w docs/phase1/08_frozen/     # execute at end of Day 6
shasum -a 256 docs/phase1/08_frozen/* > docs/phase1/08_frozen/HASHES.txt
```

## File-naming conventions

| Artifact | Pattern | Example |
|---|---|---|
| Scanned form | `<participant_id>_<case_id>_<PRE\|POST>.pdf` | `P3_C_POST.pdf` |
| Redaction log | `redaction_log.csv` — `record_id,rule,original,replacement` | rules R1–R4, `data_capture_spec.md` |
| Warm-up form | `<participant_id>_WARMUP_DISCARD.pdf` — filed outside `data/` | `P3_WARMUP_DISCARD.pdf` |
| Transcript | `<participant_id>.txt` | `P3.txt` |
| Record ID | `R-nnnn`, **randomly assigned, non-sequential** | `R-0417` |
| Evaluator pack | `<evaluator_id>_records.pdf` | `E2_records.pdf` |
| Constraint list | `constraints_v1.0.md` — **no v1.1 exists** | |

**Record IDs must be drawn from a shuffled pool.** Sequential or case-clustered IDs leak condition and
would compromise blinding.
