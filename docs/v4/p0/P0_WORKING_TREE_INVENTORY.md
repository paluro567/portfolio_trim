# P0-01 — Working Tree Inventory (Part 1)

**Branch:** `v6-closure` · **HEAD:** `b3bd82a0d003e5b009679e224a88c3f1d6d33c34` · **Remote:** `origin` exists (no push permitted)
**Paths:** 27 untracked · 0 modified · 0 deleted · 0 renamed

> **Baseline correction.** `IMPLEMENTATION_BACKLOG.md` states the entry condition as "commit the 74 dirty paths at HEAD `1b2aec9f`". That is stale. A prior session created branch `v6-closure` and landed six commits (`35c13cf`, `3e39675`, `8da8613`, `cb04738`, `d36fc6c`, `b3bd82a`); `1b2aec9f` is now `main` and an ancestor. The remaining P0-01 work is 27 untracked documentation files. `.gitignore` now excludes `data/reports/`, `data/validation/`, `RawData/`, `__pycache__/`, `*.pyc`.

## Classification key
A approved source change · B canonical architecture/engineering doc · C canonical scientific artifact · D approved test change · E generated, reproducibility-required · F temporary experimental · G obsolete duplicate · H unrelated · I secret/credential/DB/machine-local · J uncertain — human decision

## Inventory

| # | Path | Status | Class | Reason | Decision | Commit | Risk if committed | Risk if omitted |
|---|---|---|---|---|---|---|---|---|
| 1 | `docs/v6/V6_RED_TEAM_REVIEW.md` | `??` | **C** | Adversarial review of the V6 closure | **INCLUDE** | c1 | none | audit trail loses the challenge |
| 2 | `docs/v6/V6_SCIENTIFIC_ADJUDICATION.md` | `??` | **C** | Resolves closure vs red team; Brier decomposition | **INCLUDE** | c1 | none | canonical adjudication lost |
| 3 | `docs/v6/V6_EXTERNAL_PEER_REVIEW.md` | `??` | **C** | External referee report | **INCLUDE** | c1 | none | publication verdict lost |
| 4 | `docs/v6/V6_PEER_REVIEW_REBASELINE.md` | `??` | **C** | Post-review claim reclassification | **INCLUDE** | c2 | none | claim scopes unrecorded |
| 5 | `docs/v6/V6_AMENDMENT_007_PEER_REVIEW.md` | `??` | **C** | Formal amendment A-2026-007 | **INCLUDE** | c2 | none | corrections unapplied |
| 6 | `docs/v6/PRODUCT_EVIDENCE_BOUNDARY.md` | `??` | **C** | Frozen product evidence boundary | **INCLUDE** | c2 | none | **prohibited claims unenforced** |
| 7 | `docs/v6/FUTURE_PREDICTIVE_RESEARCH_GATE.md` | `??` | **C** | Gate conditions G1–G10 | **INCLUDE** | c2 | none | gate unrecorded |
| 8 | `docs/v6/REVISED_PROGRAM_SEQUENCE.md` | `??` | **C** | Execution order; anti-committee rule | **INCLUDE** | c2 | none | sequence unrecorded |
| 9 | `docs/v4/ADR-004-V4-PHYSICAL-PACKAGING.md` | `??` | **B** | Option B packaging decision | **INCLUDE** | c3 | none | **packaging rationale lost** |
| 10 | `docs/v4/ENGINEERING_SPECIFICATION.md` | `??` | **B** | Conforming spec | **INCLUDE** | c3 | none | blueprint lost |
| 11 | `docs/v4/REPOSITORY_LAYOUT.md` | `??` | **B** | Layout mapped to `src/mip/` | **INCLUDE** | c3 | none | layout lost |
| 12 | `docs/v4/MODULE_SPECIFICATIONS.md` | `??` | **B** | Module contracts, frozen domain names | **INCLUDE** | c3 | none | contracts lost |
| 13 | `docs/v4/IMPLEMENTATION_MILESTONES.md` | `??` | **B** | P0–P6 conforming | **INCLUDE** | c3 | none | phase plan lost |
| 14 | `docs/v4/TEST_PLAN.md` | `??` | **B** | Conforming test plan | **INCLUDE** | c3 | none | test strategy lost |
| 15 | `docs/v4/FROZEN_ARCHITECTURE_CONFORMANCE_MATRIX.md` | `??` | **B** | Records deviation V-1 | **INCLUDE** | c3 | none | **only record of V-1 lost** |
| 16–21 | `docs/v4/backlog/{IMPLEMENTATION_BACKLOG,TASK_BREAKDOWN,CRITICAL_PATH,SPRINT_PLAN,RISK_REGISTER,DEVELOPER_PLAYBOOK}.md` | `??` | **B** | Execution backlog, 64 tasks | **INCLUDE** | c4 | none | backlog lost |
| 22–27 | `docs/v4/_nonconforming_draft/*` (6 files) | `??` | **J** | **Superseded draft that contradicts the frozen architecture** on layout, pipeline order, domain names, optionality mechanism and milestone numbering. `README.md` marks it DO NOT IMPLEMENT. Reasonable engineers differ on whether a contradictory blueprint belongs in the canonical docs tree. | **EXCLUDE — human decision required** | — | a future reader implements from a contradictory blueprint | the audit trail of why the conforming spec exists is weakened (substance already recorded in the conformance matrix) |

## Summary

| Class | Count | Decision |
|---|---|---|
| B canonical architecture/engineering | 13 | INCLUDE |
| C canonical scientific artifact | 8 | INCLUDE |
| **J uncertain** | **6** | **EXCLUDE — not committable per Part 1** |
| A, D, E, F, G, H, I | 0 | — |

**No path is classified A (source), D (test), E (generated), F (temporary), G (obsolete), H (unrelated) or I (secret).** All 27 are documentation.
