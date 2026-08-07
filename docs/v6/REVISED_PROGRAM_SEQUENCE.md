# Revised Program Sequence

**Date:** 2026-08-04 · Purpose: end the committee cycle and resume execution.

Six committees have now reviewed V6. **No further review of V6 is authorized.** The record is closed by `V6_AMENDMENT_007_PEER_REVIEW.md`.

## Order of execution

| # | Action | Owner | Cost | Blocking? | Gate to proceed |
|---|---|---|---|---|---|
| **0** | **Back up `data/validation/`** — the archived panel is the single irreplaceable asset in the repository and exists in one copy | engineering | minutes | **YES — do first** | `tools/ops/backup.sh` completes with checksum |
| **1** | Commit the working tree and apply A-2026-007; hash and manifest | engineering | hours | YES | clean tree; `MANIFEST.sha256` verifies |
| **2** | Restore durable harnesses under `tools/v6/` — or formally withdraw Arm 1 and Arm 1.5 | engineering | 1–2 days | No | harness re-executes, or withdrawal recorded |
| **3** | **Phase 1 human study** — does an honest, non-predictive report change decisions? | human | weeks | **YES for product** | preregistered PASS ≥30% / KILL <15% |
| **4** | V5 descriptive-reliability research | research | weeks | No | gated on Phase 1 PASS |
| **5** | Resolve B-07 or withdraw the Arm 1 extended grid | research | days | No | opportunistic; may fold into #2 |
| **6** | Design a broad-universe discrimination study | research | weeks | No | **all of G1–G10 frozen first** |
| **7** | Commercial data purchase | budget | $$ | No | **only after #6 is frozen and signed** |

**Steps 0–1 are unconditional. Step 3 is the binding gate for everything downstream.** If Phase 1 returns KILL, steps 4, 6 and 7 are cancelled outright — there is no point resolving predictability for a product nobody uses.

## Anti-committee rule
No new committee, review board, panel, or adjudication may be convened on V6. Any further V6 question is answered by the amended record or is out of scope. The next artifact this program produces must be **executed work**, not another document.
