# V4 — Implementation Risk Register (Part 4)

Implementation risks only. Scientific risks are out of scope and are closed in the V6 record.
P = probability · I = impact on schedule or correctness.

| # | Risk | P | I | Mitigation | Contingency |
|---|---|---|---|---|---|
| **I-01** | **P4-09 boundary inversion** proves harder than 5 d — the hardest calculation in the system | **HIGH** | **HIGH** | Spike it in P2 alongside the calc engine, before the cascade needs it; worked examples from all seven frozen packets as the first test | Ship P4 with boundary inversion behind an explicit `NotComputable("boundary inversion unavailable")`; reports render the absence honestly; close in a P4.1 |
| **I-02** | **Semantic/golden split retrofitted rather than built in** (frozen risk R3) | MED | **HIGH** | Write `test_semantic.py` (P4-17) **before** the renderer (P4-14); assembler and renderer land in separate commits | Freeze the renderer, rebuild the model layer behind it; ~1 week |
| **I-03** | **Adjusted-close revision storm** recurs during P1-06 | MED | **HIGH** | Field-specific materiality tolerances + raw-shift guard designed before ingestion is switched on | Pin to a snapshot; process revisions offline until tolerances are calibrated |
| **I-04** | **Module moves break the 551-test baseline** | **HIGH** | MED | Deprecated shims retained one full phase; move and rename in separate commits; suite run per commit | Revert the move commit; shim stays; re-attempt next phase |
| **I-05** | `mip/` acquires an import of `mip_evidence/` because both roots are on the dev path | MED | **HIGH** | ADR-004 C-1/C-2/C-3: `zero-signal` job deletes the roots; import-linter; AST test — all merge-blocking | Any escape reaching `main` fires ADR-004 trigger **T5** and forces the distribution split immediately |
| **I-06** | Migration chain breaks on a fresh DB | MED | **HIGH** | `REFERENCE_TABLES` head assertion (P0-10); `integration` job on every PR | Forward-only fix migration; never edit a released migration |
| **I-07** | **Backup/restore is deferred under schedule pressure** | MED | **CRITICAL** | P0-02/03 are the second and third tasks in the programme; DoD of P0 is a byte-identical restore | Halt P1 until the drill passes. A PIT snapshot and a prediction archive were lost once; there is no recovery |
| **I-08** | `Decimal` discipline erodes; a `float` reaches a calculation | MED | **HIGH** | `test_float_boundary` in the invariant suite from P2-01; ruff rule | Fix at the boundary; add a regression test per escape |
| **I-09** | Determinism breaks via `set` iteration, `hash()`, or wall clock | MED | MED | AST scan in `test_determinism.py`; two-subprocess `PYTHONHASHSEED` diff in CI | Bisect on the determinism job; it runs per-PR so the blast radius is one commit |
| **I-10** | Seven golden files churn on every cosmetic template edit | **HIGH** | LOW | Semantic tests carry the logic assertions; golden churn is expected and cheap | `--regen-golden` with mandatory PR diff review |
| **I-11** | The policy **document** (a human deliverable) never arrives, blocking P3 | MED | MED | Frozen roadmap already anticipates this: **engineering ships the loader before the document exists**; fixtures supply test artifacts | P3 completes against fixture policies; production artifact lands later |
| **I-12** | Single-engineer bus factor across a 23-week serial chain | MED | **HIGH** | Every task has explicit files, tests and DoD; per-phase rollback tags; playbook is executable by a second engineer | Parallel bands A–I in `CRITICAL_PATH.md` absorb a second engineer without redesign |
| **I-13** | Scope creep from "while we're in here" refactors | **HIGH** | MED | Backlog is closed: any task not in `TASK_BREAKDOWN.md` requires an ADR | Reject at review; log to a deferred list |
| **I-14** | `verify_reports.py` (81 checks) fails when moved onto the production engine (P2-10) | MED | MED | It is the P2 DoD, so it is discovered inside P2, not later | The 81 checks are authoritative; the production engine is wrong and is fixed |
| **I-15** | Phase 1 returns KILL after P0–P4 is built | MED | MED | P0–P4 is the policy-only product and is worth building under any outcome | P5/P6 cancelled as already specified; no sunk cost in evidence or forecast |
