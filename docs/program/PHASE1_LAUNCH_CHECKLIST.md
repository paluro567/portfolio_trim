# PHASE 1 LAUNCH CHECKLIST

Uses the frozen artifacts. **No replacement study materials are generated.**
Ordered by dependency. `[H]` = requires a human who does not yet exist.

---

## Stage 0 — Documentary freeze *(no humans required)*

```
▢  0.1  Sign PHASE1_PROTOCOL_AMENDMENT_001.md      (preparer + Ops lead)
▢  0.2  Hash it:  shasum -a 256 docs/phase1/PHASE1_PROTOCOL_AMENDMENT_001.md
▢  0.3  Sign PHASE1_PROTOCOL_AMENDMENT_002.md      (preparer + Ops lead)
        └─ Acknowledge the D-01 material-change box. IT MAY NOT BE WAIVED.
▢  0.4  Hash it
▢  0.5  Run  python3 tools/phase1/verify_reports.py   → MUST EXIT 0
        └─ last known state: 81 checks, 0 failures, exit 0
▢  0.6  Record both hashes in the preregistration
▢  0.7  Write preregistration.md; timestamp; hash
▢  0.8  Copy frozen artifacts into docs/phase1/08_frozen/
▢  0.9  shasum -a 256 docs/phase1/08_frozen/* > 08_frozen/HASHES.txt
▢  0.10 Apply access controls per directory_manifest.md
        └─ LINKAGE_record_map.csv: OPS ONLY. A leak voids Gate 2.
```

## Stage 1 — Human confirmation `[H]` — **THE BINDING BLOCKER**

```
▢  1.1  [H] CONFIRM EXTERNAL MODERATOR
        ├─ Not the architect. No compliant fallback exists.
        ├─ Has read nothing beyond moderator_kit.md Part 4.
        ├─ 3-hour effort limit  →  exceeded = CANCEL (condition 1)
        └─ ** RECRUITMENT MAY NOT BEGIN UNTIL THIS IS DONE **
▢  1.2  [H] Confirm constraint author  (condition 3 = CANCEL if unavailable)
▢  1.3  [H] Confirm 3 evaluators, ≥1 with zero project exposure (condition 4)
▢  1.4  [H] Countersign COI and confidentiality declarations
```

## Stage 2 — Constraint authorship `[H]` — **freeze gate**

```
▢  2.1  Send page 1 ONLY of cases A,B,C,D,E,G  (never a report, never Case F)
▢  2.2  [H] Author 3–6 material constraints per case
▢  2.3  [H] Sign §1 COI and §5 declaration
▢  2.4  Save VERBATIM as constraints_v1.0.md — no editing of the author's wording
▢  2.5  Hash; record; chmod read-only
        ** NO SESSION MAY OCCUR BEFORE 2.5 IS COMPLETE **
```

## Stage 3 — Recruitment `[H]`

```
▢  3.1  Send recruitment message (kit §A)
▢  3.2  Screen (kit §B) — Track A ≥3, Track B ≤2
▢  3.3  Confirm eligibility (kit §D); assign P1–P5 in scheduling order
▢  3.4  6-hour cap. Exceeded without 5 qualified → RECORD FAIL, not cancel
▢  3.5  [H] Obtain consent signatures
▢  3.6  Schedule 5 × 90-minute sessions
```

## Stage 4 — Sessions `[H]`

```
▢  4.1  Brief moderator on Part 4 ONLY (1 h)
▢  4.2  Assemble packs in the frozen §G order; page 2 separated
▢  4.3  Run warm-up (warmup.md) → mark WARM-UP — DISCARD
▢  4.4  Sessions P1→P5, one per day
        ├─ PRE form witnessed and initialled BEFORE any reveal
        ├─ POST Q3 reasoning REQUIRED on every case incl. unchanged
        └─ Case F: 3:00 timed distractor, no comment on the missing page
▢  4.5  Complete post-session checklists; pay incentives
```

## Stage 5 — Blinded evaluation `[H]`

```
▢  5.1  Assemble 70 records; assign non-sequential shuffled IDs
▢  5.2  Apply redaction R1–R4; log every substitution
▢  5.3  Shuffle across participants and cases; no related records adjacent
▢  5.4  Distribute own-pack-only to E1/E2/E3 + constraints + rubrics
        └─ LINKAGE_record_map.csv NEVER leaves OPS
▢  5.5  [H] Independent scoring (~2 h each)
▢  5.6  Adjudicate 2-of-3; UNRESOLVED not forced
▢  5.7  Compute blinding guess accuracy
```

## Stage 6 — Mechanical decision

```
▢  6.1  Compute every §7.3 metric
▢  6.2  Evaluate FAIL conditions FIRST — they override PASS
▢  6.3  Complete analysis_report_template.md §§1–11
▢  6.4  Write the ≤40-word summary — no form of "improve", no banned term
▢  6.5  Sign (analyst + moderator)
▢  6.6  Execute §12 without discretion
```

---

## Current status

| Stage | Status |
|---|---|
| 0 Documentary freeze | **READY — 0/10 executed.** Nothing blocks it |
| 1 Human confirmation | **BLOCKED — 0/4** |
| 2 Constraint authorship | Blocked on 1.2 |
| 3–6 | Blocked upstream |

## The binding blocker and the next human action

> ### BLOCKER: no external moderator exists.
> ### NEXT HUMAN ACTION: identify and confirm one person who is not the architect, will read only `moderator_kit.md` Part 4, and can commit ~10 hours across three weeks.
>
> Ops §9.5 condition 1 provides no fallback. **Recruitment may not begin until this person is confirmed.**
> Effort limit: 3 hours. Exceeding it is a cancellation, not a delay.
