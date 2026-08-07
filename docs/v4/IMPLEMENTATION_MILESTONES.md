# V4 — Implementation Milestones (conforming)

**Frozen numbering P0–P6 is used verbatim.** No M0–M9 roadmap is substituted. Effort in engineer-weeks, one experienced engineer, from the frozen roadmap.

| Phase | Frozen scope | Weeks | Risk | Before Phase 1 PASS? |
|---|---|---|---|---|
| P0 | Substrate (M1) | 5 | MED | **AUTHORIZED** |
| P1 | Market data (M2) + portfolio (M5) | 5 | MED-HIGH | **AUTHORIZED** |
| P2 | Measurement (M6) + calc engine | 4 | LOW | **AUTHORIZED** |
| P3 | Policy Engine (M7, L2) | 3 | LOW-MED | **AUTHORIZED** |
| P4 | Decision (M11) + Report (M12) | 6 | HIGH | **AUTHORIZED** |
| P5 | Decision Archive (M13) | 3 | LOW | **GATED — Phase 1 PASS** |
| P6 | Evaluation Suite (M14) | 4 | MED | **GATED — Phase 1 PASS** |
| — | Evidence Layer (M8, M9) | — | — | **PROHIBITED** until Phase 1 PASS **and** a recorded ledger tier |
| — | Forecast Layer (M10) | — | — | **PROHIBITED** — dormant; no source has cleared DIRECTIONAL |
| — | Multi-distribution extraction | 1–2 | MED | **PROHIBITED** until an ADR-004 trigger |

**Rationale for the gate line:** P0–P4 reproduce the frozen contract with no Evidence and no Forecast layer — the frozen roadmap's own completion criterion. They are worth building under any Phase 1 outcome because they are the policy-only product. P5–P6 add archive and evaluation, which only pay off if the product is used.

---

### P0 · Substrate — 5 weeks · MEDIUM
**Start state:** 74 dirty paths at HEAD `1b2aec9f`; 551 tests green; 11 migrations.
**Changes:** commit the tree; **automated offsite backup + scheduled restore drill**; `securities/` → `substrate/` (M1); identity spine on `security_id`; `REFERENCE_TABLES` head assertion; `AsOf` context; content-addressed snapshot store. Create empty `src/mip_evidence/`, `src/mip_forecast/`, `src/mip_proto/` roots + `ADR-004` controls C-1…C-7.
**Tests:** migration up/down · snapshot checksum stability · **restore drill** · PIT interface reflection · `lint-imports` · `test_ast_boundaries.py`.
**Artifacts:** verified backup bundle; `MANIFEST.sha256`; CI with `lint`, `unit`, `invariants`, `zero-signal`.
**Done when:** a full DB can be destroyed and restored **byte-identically** from backup.
**Rollback:** git tag `pre-P0`; substrate is additive.
> Backup is P0, not an afterthought. A PIT fundamentals snapshot and a prediction archive were permanently lost once. That must not recur.

### P1 · Market data + portfolio — 5 weeks · MEDIUM-HIGH
**Start state:** P0 done.
**Changes:** `ingestion/`+`providers/` → `marketdata/` (M2), `fundamentals/` (M3), `macro/` (M4); `reference/calendar.py` → `marketdata/`; revision handling + completed-session guard; transaction ledger; FIFO lot engine (`Decimal`, replay-deterministic, oversell-rejecting); `PositionSnapshot` with byte-identical rebuild.
**Tests:** price-poisoning · revision materiality · lot replay determinism · rebuild idempotence.
**Risk:** the adjusted-close tripwire storm — field-specific materiality tolerances + raw-shift guard.
**Done when:** a full portfolio rebuild from the ledger is byte-identical twice running.
**Rollback:** tag `pre-P1`; old modules retained as deprecated shims for one phase.

### P2 · Measurement (L1) + calculation engine — 4 weeks · LOW
**Changes:** `calc/` with C1–C12, P1–P7, `CalculationResult`, **`NotComputable` as a first-class value**, unit tagging; `measurement/` (M6) facts-only, `MeasurementBasis` passed in.
**Tests:** one unit test per calculation with worked examples from the frozen packets · **C9 returns `NotComputable` with partial book weights** · every result carries a unit · D3 preference-leak AST test.
**Done when:** `tools/phase1/verify_reports.py` passes **using the production engine instead of its own arithmetic**.
**Rollback:** tag `pre-P2`; `calc/` additive.

### P3 · Policy Engine (L2) — 3 weeks · LOW-MEDIUM
**Changes:** versioned `PolicyArtifact` (semver, never edited) with **explicit `participation_rate`**; P1–P7; `ConstraintEvaluation`; `config/policy/` artifacts.
**Tests:** policy versioning immutability · AST guard D2 (only `policy/` and `decision/` import prefs) · mandate detection across all seven fixtures.
**Risk:** the policy *document* is a human deliverable and remains the V3 blocker. **Engineering ships the loader before the document exists.**
**Done when:** all seven fixtures load a policy and produce constraint evaluations.

### P4 · Decision (L6) + Report (L7) — 6 weeks · HIGH
**Changes:** S1–S9 cascade; elimination trace as a **returned value**; abstention; boundary inversion (P6); `ReportModel`/`Renderer` **split**; templates N1–N7; M17 orchestrator with the 13-stage manifest and `--resume`. Deprecate `engine/trim.py`, `engine/intelligence.py`, `engine/report.py`.
**Tests:** **the fourteen acceptance assertions** · all seven negative controls · determinism · **zero-signal with both optional roots deleted**.
**Risk:** boundary inversion is the hardest calculation in the system; the semantic/golden split must be right from the first commit.
> **✅ COMPLETION CRITERION: all fourteen acceptance assertions green, `verify_reports.py` exits 0, and the suite passes with `mip_evidence` and `mip_forecast` absent. At this point the production system reproduces the frozen contract.**
**Rollback:** tag `pre-P4`; deprecated engine modules retained until P5.

### P5 · Decision Archive (L8) — 3 weeks · LOW — **GATED on Phase 1 PASS**
Immutable append-only store; `EvaluationContract` stamped at creation; `latest_before`; supersession.
**Tests:** immutability · contract non-nullable · future-archive invisibility (PIT).
**Done when:** `what_changed` populates from real archived history and terminal wealth still renders "not available" on an empty archive.

### P6 · Evaluation Suite (L9) — 4 weeks · MEDIUM — **GATED on Phase 1 PASS**
Layer-specific scoring; three counterfactuals incl. **policy-only**; **mandatory terminal-wealth disclosure**; abstention scoring; decision-level FDR ledger.
**Tests:** counterfactual arithmetic · terminal wealth reported even when unfavourable · restatement-proof re-evaluation.

---

## Universal definition of done

1. `uv run pytest` green with **≥ 551 passed**; no skip added without an approved replacement.
2. All CI jobs green: `lint`, `unit`, `invariants`, `zero-signal`, `min-deps`, `integration`, `acceptance`, `contract`, `determinism`.
3. `git status --porcelain` empty; phase tagged.
4. New code covered by unit **and** at least one invariant, property, or acceptance test.
5. Frozen documents unchanged; `FROZEN_ARCHITECTURE_CONFORMANCE_MATRIX.md` updated in the same commit.
6. A named rollback tag exists and has been verified to check out and pass.
