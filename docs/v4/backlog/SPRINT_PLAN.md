# V4 — Sprint Plan (Part 3)

Two-week sprints, one engineer. **Every sprint ends with a functioning repository**: suite ≥551 green, all configured CI jobs green, tree clean, phase-or-sprint tag placed.

| Sprint | Weeks | Phase | Objective | Tasks | Deliverables | Acceptance |
|---|---|---|---|---|---|---|
| **S1** | 1–2 | P0 | **Make the work safe to do.** Clean tree, verified backup, restore drill, boundary controls | P0-01…P0-08 | tag `pre-P0`; offsite backup; `.importlinter`; `test_ast_boundaries.py`; CI `lint`/`unit`/`invariants`/`min-deps`/`zero-signal` | **DB destroyed and restored byte-identically.** Both optional roots deletable, suite still green |
| **S2** | 3–5 | P0 | **Identity spine.** Substrate M1 | P0-09…P0-14 | `mip/substrate/`; `AsOf`; snapshot store; verified `MANIFEST.sha256` | No module resolves by ticker; migration up/down on a fresh DB; snapshot checksum stable. **Tag `P0-done`** |
| **S3** | 6–7 | P1 | **Market data.** M2/M3/M4 | P1-01…P1-07 | `marketdata/`, `fundamentals/`, `macro/`; revision + raw-shift guards | Completed-session guard holds; revision materiality does not fire on a real corporate action |
| **S4** | 8–10 | P1 | **Portfolio spine.** M5 | P1-08…P1-12 | ledger; FIFO lots; `PositionSnapshot` | **Full rebuild byte-identical twice running.** `test_pit_poisoning` green — **release gate**. **Tag `P1-done`** |
| **S5** | 11–12 | P2 | **Calculation engine.** C1–C12, P1–P7 | P2-01…P2-05 | `mip/calc/`; `NotComputable` as a value | Every calc has a worked-example unit test and a `unit`; **C9 returns `NotComputable` on partial book weights** |
| **S6** | 13–14 | P2 | **Measurement L1.** M6 | P2-06…P2-10 | `mip/measurement/`; `MeasurementBasis` | **`verify_reports.py` exits 0 on the production engine.** D3 preference-leak guard green. **Tag `P2-done`** |
| **S7** | 15–17 | P3 | **Policy Engine L2.** M7 | P3-01…P3-07 | `PolicyArtifact` (explicit `participation_rate`); `ConstraintEvaluation`; `config/policy/` | Policy versions immutable; mandate detection correct on all seven fixtures; D2 guard green. **Tag `P3-done`** |
| **S8** | 18–19 | P4 | **Cascade front half.** S1–S4 | P4-01…P4-05, P4-11 | `ports.py` Protocols; S1–S4; eliminations; `ESCALATE` | Eliminations record rule/threshold/actual; empty feasible set escalates, never a silent HOLD |
| **S9** | 20–21 | P4 | **Cascade back half + the hard calculation.** S5–S9, P6 inversion | P4-06…P4-10, P4-12 | S5 dormant; abstention; **boundary inversion**; `DecisionTrace` returned | `forecast_contribution == 0.0`; trace carries every stage and calculation; inversion correct on all seven fixtures |
| **S10** | 22–23 | P4 | **Report L7 + acceptance.** M12 | P4-13, P4-17, P4-14, P4-18 | `ReportModel` assembler; renderer + N1–N7; 7 semantic + 7 golden | **All fourteen acceptance assertions green** |
| **S11** | 24–25 | P4 | **Orchestrator + the zero-signal proof.** M17 | P4-15, P4-16, P4-19, P4-20, P4-21 | 13-stage manifest, `--resume`, advisory lock, atomic publication; legacy engine deprecated | ✅ **P4 COMPLETION: fourteen acceptance assertions green, `verify_reports.py` exits 0, and the suite passes with both optional roots deleted. The production system reproduces the frozen contract.** **Tag `P4-done` / `v4.0.0-rc`** |
| — | — | — | **PHASE 1 GATE** | — | — | **S12+ do not start without a Phase 1 PASS** |
| **S12** | 26–28 | P5 | Decision archive L8 | P5-01…P5-06 | immutable store; `EvaluationContract` | `what_changed` from real history; terminal wealth "not available" on empty archive |
| **S13** | 29–32 | P6 | Evaluation suite L9 | P6-01…P6-06 | layer scoring; counterfactuals; terminal wealth | Terminal wealth reported **even when unfavourable**; restatement-proof |

**Sprint order note:** S10 writes `test_semantic.py` (P4-17) *before* the renderer (P4-14) deliberately — mitigation for risk I-02.
