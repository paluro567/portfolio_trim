# V4 — Implementation Backlog

**Status:** READY TO EXECUTE · **Date:** 2026-08-04
**Authority:** frozen `docs/v4/` architecture set + the conforming spec (`ENGINEERING_SPECIFICATION.md`, `REPOSITORY_LAYOUT.md`, `MODULE_SPECIFICATIONS.md`, `IMPLEMENTATION_MILESTONES.md`, `TEST_PLAN.md`, `ADR-004`).

## Contents

| Document | Part |
|---|---|
| `TASK_BREAKDOWN.md` | 1 — work breakdown, 79 tasks |
| `CRITICAL_PATH.md` | 2 — dependency graph, parallel bands, longest chain |
| `SPRINT_PLAN.md` | 3 — 13 sprints |
| `RISK_REGISTER.md` | 4 — 15 implementation risks |
| `DEVELOPER_PLAYBOOK.md` | 5 — day-by-day |

## Totals

| Phase | Tasks | Days | Weeks | Gate |
|---|---|---|---|---|
| P0 Substrate | 14 | 25 | 5 | authorized |
| P1 Market data + portfolio | 12 | 25 | 5 | authorized |
| P2 Measurement + calc | 10 | 20 | 4 | authorized |
| P3 Policy | 7 | 15 | 3 | authorized |
| P4 Decision + Report | 21 | 30 | 6 | authorized |
| **Subtotal to frozen contract** | **64** | **115** | **23** | — |
| P5 Archive | 6 | 15 | 3 | **Phase 1 PASS** |
| P6 Evaluation | 6 | 20 | 4 | **Phase 1 PASS** |
| **Total** | **76** | **150** | **30** | — |

Evidence Layer (M8, M9) and Forecast Layer (M10) carry **no tasks in this backlog**. They are prohibited until Phase 1 PASS and, for evidence influence, a recorded ledger tier. Multi-distribution extraction carries no tasks; it fires on an ADR-004 trigger.

## Standing rules

1. **The backlog is closed.** Any task not listed requires an ADR before it is worked.
2. **No milestone reduces the passing-test count** (baseline 551) without an approved replacement recorded in the PR.
3. **Every phase ends with a rollback tag** that has been checked out and verified green.
4. **Frozen documents are read-only.** Conformance changes are recorded in `FROZEN_ARCHITECTURE_CONFORMANCE_MATRIX.md`.
5. **Deprecated modules keep a shim for one full phase**, then are removed.
6. Move and rename land in **separate commits** from behaviour changes.
7. Every CI job is a merge blocker: `lint`, `unit`, `invariants`, `zero-signal`, `min-deps`, `integration`, `acceptance`, `contract`, `determinism`.

## Entry condition

**P0-01 — commit the 74 dirty paths at HEAD `1b2aec9f` and tag `pre-P0`.** Until this lands, no task has a rollback point and no manifest can be hashed. This is the single blocking item.
