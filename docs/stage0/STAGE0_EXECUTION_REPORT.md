# STAGE 0 EXECUTION REPORT

**Executed 2026-08-01.** Only verifiable results are reported. Every claim below traces to a command
that was run.

---

## 1 · Work completed

| # | Activity | Result |
|---|---|---|
| 1 | Repository audit — files, schemas, migrations, scripts, artifacts | 20 assets classified. **2 prior claims corrected** |
| 2 | Migration-chain integrity | **11 migrations, chain INTACT, rebuilds to 86 tables** on a disposable DB |
| 3 | **Backup control implemented** | `tools/ops/backup.sh` — none existed before |
| 4 | **Restore control implemented** | `tools/ops/restore.sh` — none existed before |
| 5 | **Backup executed** | 8 artifacts, 37 MB, checksummed |
| 6 | **Restore drill executed** | 7/7 checksums OK; **647 files, 194 MB, byte-identical** |
| 7 | Verifier executed with full record | **exit 0, 81 checks, 0 failures** |
| 8 | **Verifier portability defect found and fixed** | S0-D01: ran only on Python ≥3.10. Now verified on **3.9 and 3.11** |
| 9 | Negative control re-run after fix | defect → **exit 1**; restored → **exit 0** |
| 10 | Freeze manifest generated | **23 artifacts hashed (SHA-256)** |
| 11 | Evidence sources inventoried | 9 sources; independent verification paths mapped |
| 12 | V5 candidates selected | 5 selected, 4 excluded with reasons |
| 13 | V5 Experiment 001 preregistered | `momentum_exhaustion`; thresholds frozen |
| 14 | V6 readiness assessed | 4 ready · 4 minor · 2 major · 2 data-blocked |

**Effort: ~11 hours. Cash: $0.** Within the 40-hour / $120 pre-G1 ceiling.

## 2 · Defect found and fixed

**S0-D01 — verifier portability.** `case_facts.py` used `D | None` without
`from __future__ import annotations`; raised `TypeError` on Python 3.9. Fixed with one behaviour-neutral
import. **Caught before hashing** — which is what Stage 0 exists for.

## 3 · Corrections to prior documents

| Claim | Actual |
|---|---|
| "16 migrations" (V4 docs, memory) | **11 migrations** |
| Verifier runs anywhere | Required Python ≥3.10 until fixed |

## 4 · What Stage 0 did NOT do

No V4 production code · no migrations · no report generator · no new evidence sources · no Norgate
evaluation or purchase · no study modification · no data re-ingestion (planned, not executed) · no
signature obtained or simulated.

---

## Conclusions

### 1 · Phase 1 documentary freeze status
**PREPARED, NOT FROZEN.** All 23 artifacts hashed; verifier green with a valid negative control; freeze
manifest, signature checklist and access matrix produced. **Freezing requires human signatures — 0 of
19 obtained.**

### 2 · Human blockers still open
1. **External moderator — NOT CONFIRMED (binding blocker)**
2. External constraint author — not identified
3. Three evaluators, ≥1 zero-exposure — not identified
4. Five participants — not recruited
5. **19 signatures outstanding, 0 obtained**

### 3 · Research data restored
**NO.** Schema is *reconstructible* (verified). Research **data** is not restored — prices, macro and
features must be re-ingested (~12–15 h, class B). The prediction archive and the PIT fundamentals
vintage are **permanently irrecoverable**.

### 4 · Backup restore drill passed
**YES — qualified.** 7/7 checksums, 647 files, 194 MB byte-identical, live-DB guard exercised.
**Qualification: the database payload was empty (4 KB), so volume behaviour is unproven. A second drill
after re-ingestion is an open action.**

### 5 · First V5 evidence source selected
**`momentum_exhaustion`.** Price-only inputs · 90.3% activation · a falsifiable own-percentile claim ·
an independent path that bypasses both the feature store and the model code.

### 6 · V5 Experiment 001 ready to run
**NO.** Preregistered and frozen, but blocked on prerequisites: price re-ingestion (4–6 h) and feature
recomputation (3–4 h).

### 7 · V6 ready to begin
**PARTIALLY.** **Arm 1 can run today** on surviving captures — 7 symbols × 189 dates with per-model
values *and* outcomes — measuring the validation layer's MDE with no re-ingestion. **Arms 2 and 3 are
blocked on data.** **G5 is not evaluable** without the full surface and the Arm 2 − Arm 1 gap.

### 8 · Next human action
**Identify and confirm one external moderator.** Not the architect; reads only `moderator_kit.md`
Part 4; ~10 hours over three weeks. **3-hour effort limit — exceeding it is a cancellation, not a
delay.** Recruitment may not begin until this person exists.

### 9 · Next engineering action
**Re-ingest prices and macro, recompute the feature store, then back up immediately** (~12–15 h,
class B). This unblocks V5 Experiment 001, V6 Arms 2–3, and a volume-realistic second restore drill.
**Scratchpad and ingestion only — no `src/` changes, no migrations.**

### 10 · Next scientific action
**Run V6 Arm 1 on the surviving captures (~1 day).** It needs no data, answers a question never
answered — *what effect size can the validation layer detect?* — and is the cheapest partial progress
toward G5 available today.

### 11 · Norgate authorized today

# **NO**

### 12 · Exact blocker preventing Norgate authorization

**All four G6 conditions are unmet, and two are unmeasured:**

| Condition | Status |
|---|---|
| **C1** ≥1 source at ADVISORY | ❌ **The ledger is empty. V5 Experiment 001 is preregistered but not run** |
| **C2** G5 / MDE acceptable | ❌ **Never measured. V6 Arms 2–3 blocked on data; G5 not evaluable** |
| **C3** Survivorship is the *remaining* blocker | ❌ **Cannot be assessed until C1 and C2 exist.** Today the binding blocker is missing data and an empty ledger — **not survivorship** |
| **C4** Provider meets M1–M7 within ceilings | ❌ Not evaluated; premature |

> **The single exact blocker:** **no evidence source has ever been tested for descriptive reliability,
> and the pipeline's detection limit has never been measured.** Until both exist, survivorship-clean
> data cannot be shown to be the remaining obstacle — and buying it would be buying a better ruler for
> an object not yet confirmed to exist.
>
> **Earliest authorization: after V5 Experiment 001 reaches ADVISORY and V6 reports a passing MDE
> surface.** On the program timeline that is month 7–8. It may never occur: a **G5 FAIL blocks it
> permanently.**
