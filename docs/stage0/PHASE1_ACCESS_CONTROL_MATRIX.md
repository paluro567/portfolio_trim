# PHASE 1 ACCESS CONTROL MATRIX

Roles: **OPS** (ops lead / analyst) · **MOD** (external moderator) · **CA** (constraint author) ·
**EVAL** (E1–E3) · **PART** (participants).

---

## Matrix

| Path | OPS | MOD | CA | EVAL | PART | Blinding-critical |
|---|---|---|---|---|---|---|
| `docs/phase1/00_COMPLIANCE_MATRIX.md` | RW | — | — | — | — | |
| `PHASE1_PROTOCOL_AMENDMENT_001/002.md` | RW | R | — | — | — | |
| `01_participant/00_frame_consent.md` | RW | R | — | — | **view** | |
| `01_participant/warmup.md` | RW | R | — | — | **view (page only)** | moderator header restricted |
| `01_participant/forms.md` | RW | R | — | — | **view** | |
| `01_participant/case_A..E,G.md` **page 1** | RW | R | **R** | **R** (in records) | **view at commit** | |
| `01_participant/case_A..E,G.md` **page 2** | RW | R | ❌ **NEVER** | ❌ **NEVER** | **view at reveal only** | ⚠️ **YES** |
| `01_participant/case_F.md` | RW | R | ❌ **NEVER** | — | view | ⚠️ **sham status** |
| `02_moderator/moderator_kit.md` | RW | **R** | ❌ | ❌ | ❌ | ⚠️ **arm assignment + sham script** |
| `03_constraint_author/` | RW | — | **RW** | ❌ | — | |
| `04_evaluator/evaluator_kit.md` §§1–10 | RW | — | — | **R** | — | |
| `04_evaluator/evaluator_kit.md` §§11–13 | RW | — | — | ❌ **NEVER** | — | ⚠️ adjudication |
| `04_.../record_packs/E<n>_records.pdf` | RW | — | — | **R — own pack only** | — | ⚠️ |
| `05_analyst/` | RW | — | — | ❌ | — | |
| `06_execution/` | RW | R | — | — | — | |
| `07_responses/**` | RW | append | — | ❌ | — | |
| **`07_responses/LINKAGE_record_map.csv`** | **RW — OPS ONLY** | ❌ | ❌ | ❌ **NEVER** | ❌ | ⚠️ **VOIDS GATE 2 IF LEAKED** |
| `08_frozen/` | **R after freeze** | R | — | — | — | |
| `tools/phase1/` | RW | — | — | — | — | |

## Enforcement

Filesystem permissions are advisory on a single-operator machine. **The operative controls are
procedural:**

| # | Control | Mechanism |
|---|---|---|
| 1 | Page 2 never reaches CA or EVAL | CA pack contains page-1 extracts only; evaluator records reproduce the **baseline**, never the report |
| 2 | `LINKAGE_record_map.csv` never leaves OPS | Never attached to an evaluator communication. Stored outside the evaluator share |
| 3 | Evaluators receive only their own pack | Separate files, separate shuffles |
| 4 | Moderator kit never reaches EVAL or PART | Separate distribution |
| 5 | `08_frozen/` write-protected | `chmod -R a-w` after freeze; any write is a logged deviation |

```bash
chmod -R a-w docs/phase1/08_frozen/
shasum -a 256 docs/phase1/08_frozen/* > docs/phase1/08_frozen/HASHES.txt
```

## Current status

**Not yet applied.** `08_frozen/` is empty; freezing is gated on the signatures in
`PHASE1_SIGNATURE_CHECKLIST.md`. No participant, evaluator or constraint author exists, so **no
distribution has occurred and no leak is possible today.**
