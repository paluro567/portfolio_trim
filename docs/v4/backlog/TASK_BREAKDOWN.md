# V4 — Task Breakdown (Part 1)

Every task traces to the frozen `IMPLEMENTATION_MILESTONES.md` (P0–P6) and `MODULE_SPECIFICATIONS.md` (M1–M17). No new functionality.
Effort in **engineer-days**. DoD is additional to the universal DoD (suite ≥551 green, all CI jobs green, tree clean, tag exists).

## P0 · Substrate — M1, L0 — 25 d

| ID | Objective | Deps | Eff | Files | Tests | Definition of done |
|---|---|---|---|---|---|---|
| **P0-01** | Commit the working tree; tag `pre-P0` | — | 1 | 74 dirty paths | existing 551 | `git status --porcelain` empty; tag pushed |
| **P0-02** | Automated offsite backup of DB + `data/validation/` | P0-01 | 2 | `tools/ops/backup.sh`, CI cron | checksum verify | bundle produced, checksummed, stored offsite |
| **P0-03** | Scheduled restore drill | P0-02 | 2 | `tools/ops/restore.sh`, CI | `test_restore_drill` | DB destroyed and restored **byte-identically** |
| **P0-04** | Create `src/mip_evidence/`, `src/mip_forecast/`, `src/mip_proto/` roots | P0-01 | 1 | 3 new `__init__.py`, `pyproject.toml` extras | import smoke | roots exist; wheel still ships `src/mip` only |
| **P0-05** | import-linter contracts (ADR-004 C-2) | P0-04 | 1 | `.importlinter` | `lint-imports` | `mip` ↛ `mip_evidence`/`mip_forecast`/`mip_proto`/`mip.research*` |
| **P0-06** | `test_ast_boundaries.py` — D1–D8 | P0-04 | 3 | `tests/invariants/` | itself | all 8 guards assert; D6 passes on current tree |
| **P0-07** | `zero-signal` CI job (`rm -rf` both roots) | P0-04..06 | 1 | `.github/workflows/ci.yml` | job | job green with both roots deleted |
| **P0-08** | CI skeleton: `lint`, `unit`, `invariants`, `min-deps` | P0-01 | 2 | ci.yml, `pyproject` | — | all four jobs green, merge-blocking |
| **P0-09** | `securities/` → `substrate/` (M1); identity spine on `security_id` | P0-01 | 4 | `src/mip/substrate/`, callers | `test_identity_resolution` | no module resolves by ticker |
| **P0-10** | `REFERENCE_TABLES` migration-head assertion | P0-09 | 1 | `alembic/env.py` | `test_migration_head` | head mismatch raises `ConfigurationError` |
| **P0-11** | `AsOf` context object | P0-01 | 2 | `mip/core/asof.py` | `test_asof_threading` | no default `as_of` below `cli/` |
| **P0-12** | Content-addressed snapshot store (`HistoricalSnapshot`) | P0-09 | 4 | `mip/substrate/snapshots.py` | `test_snapshot_checksum` | checksum stable across processes |
| **P0-13** | Regenerate `MANIFEST.sha256`; verify every hash | P0-12 | 1 | `MANIFEST.sha256` | `test_manifest_verifies` | every listed hash matches |
| **P0-14** | Migration up/down on a fresh DB | P0-10 | 2 | `tests/integration/` | `test_migration_chain` | 11 migrations up and down; 86 tables |

## P1 · Market data + portfolio — M2–M5, L0 — 25 d

| ID | Objective | Deps | Eff | Files | Tests | Definition of done |
|---|---|---|---|---|---|---|
| **P1-01** | `ingestion/`+`providers/` → `marketdata/` (M2) | P0-09 | 4 | `mip/marketdata/` | `test_price_ingest` | old modules are deprecated shims |
| **P1-02** | `fundamentals/` (M3) split out | P1-01 | 2 | `mip/fundamentals/` | `test_fundamentals_pit` | PIT interface reflected |
| **P1-03** | `macro/` (M4) split out | P1-01 | 2 | `mip/macro/` | `test_macro_pit` | — |
| **P1-04** | `reference/calendar.py` → `marketdata/` | P1-01 | 1 | `mip/marketdata/calendar.py` | `test_sessions` | 4419 sessions reproduce |
| **P1-05** | Completed-session guard | P1-04 | 2 | `mip/marketdata/ingest.py` | `test_no_inprogress_bar` | in-progress bar never read |
| **P1-06** | Revision handling + field-specific materiality tolerances | P1-01 | 3 | `mip/marketdata/revisions.py` | `test_revision_materiality` | adjusted-close storm does not fire |
| **P1-07** | Raw-shift guard | P1-06 | 2 | same | `test_raw_shift_guard` | corporate action distinguished from a data error |
| **P1-08** | Transaction ledger | P0-09 | 3 | `mip/portfolio/ledger.py` | `test_ledger_append` | append-only, `Decimal` |
| **P1-09** | FIFO lot engine — `Decimal`, replay-deterministic, oversell-rejecting | P1-08 | 4 | `mip/portfolio/lots.py` | `test_lot_replay`, `test_oversell` | replay byte-identical twice |
| **P1-10** | `PositionSnapshot` byte-identical rebuild; pins `as_of` | P1-09 | 3 | `mip/portfolio/snapshots.py` | `test_rebuild_idempotence` | full rebuild identical twice running |
| **P1-11** | `test_pit_poisoning.py` — **release gate** | P1-05,P1-10 | 3 | `tests/invariants/` | itself | post-`as_of` corruption → identical output |
| **P1-12** | `integration` CI job (fresh DB, full chain) | P1-10 | 1 | ci.yml | — | job green |

## P2 · Measurement + calc engine — M6, L1 — 20 d

| ID | Objective | Deps | Eff | Files | Tests | Definition of done |
|---|---|---|---|---|---|---|
| **P2-01** | `CalculationResult` + **`NotComputable` as a value** | P1-10 | 2 | `mip/calc/result.py` | `test_notcomputable_is_value` | never raised for missing inputs |
| **P2-02** | Calculations C1–C6 | P2-01 | 4 | `mip/calc/c1_c6.py` | 6 unit tests, worked examples | each carries a `unit` |
| **P2-03** | Calculations C7–C12 | P2-01 | 4 | `mip/calc/c7_c12.py` | 6 unit tests | **C9 returns `NotComputable` on partial book weights** |
| **P2-04** | Calculations P1–P7 | P2-01 | 4 | `mip/calc/p1_p7.py` | 7 unit tests | — |
| **P2-05** | `input_hash` + `deterministic` flag on every result | P2-02..04 | 1 | `mip/calc/result.py` | `test_input_hash` | identical inputs → identical hash |
| **P2-06** | `measurement/` (M6) `PositionState`, facts only | P2-02..04 | 4 | `mip/measurement/` | `test_position_state` | zero preferences |
| **P2-07** | `book_weights` → `Mapping | NotComputable` | P2-06 | 1 | same | `test_book_weights_partial` | partial weights → `NotComputable` |
| **P2-08** | `MeasurementBasis` value object (from `PolicyArtifact`) | P2-06 | 1 | `mip/measurement/basis.py` | `test_basis_passed_in` | `measurement/` never imports `policy/` |
| **P2-09** | D3 preference-leak AST test | P2-06 | 1 | `tests/invariants/` | itself | L1 holds no thresholds |
| **P2-10** | `verify_reports.py` passes on the **production** engine | P2-02..07 | 3 | `tools/phase1/` | contract job | exits 0 using production arithmetic |

## P3 · Policy Engine — M7, L2 — 15 d

| ID | Objective | Deps | Eff | Files | Tests | Definition of done |
|---|---|---|---|---|---|---|
| **P3-01** | `PolicyArtifact` entity incl. **explicit `participation_rate`** + `content_hash` | P2-06 | 3 | `mip/domain/policy.py` | `test_policy_artifact` | all frozen fields present |
| **P3-02** | `config/policy/` artifact format + loader | P3-01 | 2 | `mip/policy/loader.py`, `config/policy/` | `test_policy_load` | unknown version → `ConfigurationError` |
| **P3-03** | Semver immutability — a change is a new row | P3-02 | 2 | `mip/policy/versioning.py` | `test_policy_immutable` | editing an existing version raises |
| **P3-04** | `PolicyConstraint` per version | P3-02 | 2 | `mip/policy/constraints.py` | `test_constraints_versioned` | — |
| **P3-05** | `ConstraintEvaluation` — C1–C3, P1, P2 | P3-04, P2-06 | 3 | `mip/policy/evaluate.py` | `test_constraint_eval` | absent input → explicit non-evaluable, never a silent PASS |
| **P3-06** | Mandate detection | P3-05 | 2 | `mip/policy/mandate.py` | across all 7 fixtures | correct on A–G |
| **P3-07** | D2 AST guard — only `policy/`+`decision/` import prefs | P3-01 | 1 | `tests/invariants/` | itself | guard green |

## P4 · Decision + Report — M11, M12, L6/L7 — 30 d

| ID | Objective | Deps | Eff | Files | Tests | Definition of done |
|---|---|---|---|---|---|---|
| **P4-01** | `ports.py` Protocols: `EvidenceProvider`, `ForecastProvider`, `ReliabilityLedgerReader` | P3-05 | 2 | `mip/decision/ports.py` | `test_ports_protocol_only` | no concrete optional-layer import in `mip/` |
| **P4-02** | S1 hard constraints + `EliminationEntry` | P4-01 | 3 | `mip/decision/stages/s1.py` | `test_s1_eliminations` | rule, threshold, actual recorded |
| **P4-03** | S2 mandate | P4-02 | 2 | `s2.py` | `test_s2_mandate` | action fixed; urgency/magnitude open |
| **P4-04** | S3 lexicographic P1..P6 with epsilon bands | P4-03 | 4 | `s3.py` | `test_s3_lexicographic` | eliminations recorded per objective |
| **P4-05** | S4 bounded evidence modulation, tier caps 0/±10/±20 | P4-04, P4-01 | 3 | `s4.py` | `test_s4_tier_caps` | contribution ≤ cap; 0 when absent |
| **P4-06** | S5 forecast, dormant | P4-05 | 1 | `s5.py` | `test_s5_dormant` | `forecast_contribution == 0.0` |
| **P4-07** | S6 abstention | P4-06 | 2 | `s6.py` | `test_s6_abstain` | HOLD + `abstained=true` + reason |
| **P4-08** | S7–S9 score, confidence, boundaries | P4-07 | 3 | `s7_s9.py` | unit | — |
| **P4-09** | **P6 boundary inversion** — hardest calculation | P4-08 | 5 | `mip/calc/boundary.py` | property + worked examples | inverts on all 7 fixtures |
| **P4-10** | `DecisionTrace` as a **returned value**, not logged | P4-02..08 | 2 | `mip/decision/trace.py` | `test_trace_returned` | every stage, input, survivor present |
| **P4-11** | `ESCALATE` on empty feasible set | P4-02 | 1 | `s1.py` | `test_escalate` | archived; **never a silent HOLD** |
| **P4-12** | `HorizonTermStructure` reconciliation (×5 horizons) | P4-10 | 2 | `mip/decision/horizons.py` | `test_term_structure` | — |
| **P4-13** | `ReportModel` assembler | P4-10 | 3 | `mip/report/model.py` | 7 semantic tests | assembler holds no rendering |
| **P4-14** | Renderer + templates N1–N7 | P4-13 | 4 | `mip/report/render.py`, `config/templates/` | 7 golden tests | byte-compare vs `docs/phase1/01_participant/case_*.md` |
| **P4-15** | M17 orchestrator: 13-stage manifest, `--resume`, advisory lock, per-position savepoint | P4-14 | 4 | `mip/cli/orchestrate.py` | `test_resume`, `test_lock` | stages 5/7 skip on absence |
| **P4-16** | Atomic publication (temp → fsync → `os.replace`); stage 12 gates 13 | P4-15 | 2 | `mip/cli/publish.py` | `test_atomic_replace` | verification failure leaves prior artifacts untouched |
| **P4-17** | 7 semantic acceptance tests | P4-13 | 3 | `tests/acceptance/test_semantic.py` | itself | assert on `ReportModel`, layout-independent |
| **P4-18** | 7 golden render tests | P4-14 | 2 | `tests/acceptance/test_golden_render.py` | itself | byte-identical |
| **P4-19** | Deprecate `engine/trim.py`, `engine/intelligence.py`, `engine/report.py` | P4-14 | 2 | `mip/engine/` | `test_trim_quarantined` | not importable from the V4 path |
| **P4-20** | `test_zero_signal.py` — full pipeline, both optional roots deleted | P4-15 | 2 | `tests/invariants/` | itself | complete `RenderedReport`; evidence 0; forecast 0.0 |
| **P4-21** | `determinism` + `acceptance` + `contract` CI jobs | P4-18 | 1 | ci.yml | — | all merge-blocking and green |

## P5 · Decision Archive — M13, L8 — 15 d — **GATED on Phase 1 PASS**
`P5-01` immutable append-only store · `P5-02` `EvaluationContract` stamped at creation, non-nullable · `P5-03` `latest_before` · `P5-04` supersession · `P5-05` future-archive PIT invisibility · `P5-06` `what_changed` from real history; terminal wealth renders "not available" on an empty archive.

## P6 · Evaluation Suite — M14, L9 — 20 d — **GATED on Phase 1 PASS**
`P6-01` layer-specific scoring (policy→risk, evidence→descriptive, forecast→return) · `P6-02` three counterfactuals incl. **policy-only** · `P6-03` **mandatory terminal-wealth disclosure** · `P6-04` abstention scoring · `P6-05` decision-level FDR ledger · `P6-06` restatement-proof re-evaluation.
