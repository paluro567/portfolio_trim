# V4 — Developer Playbook (Part 5)

**Granularity policy.** P0 and P1 are specified **day by day** — that is the work starting now, and the detail is actionable. P2–P4 are specified **week by week** with a stated daily rhythm. Day-level scheduling 15 weeks out is planning theatre: dependencies are fixed in `CRITICAL_PATH.md`, and the day a task starts is determined by when its predecessor lands, not by a calendar written today.

**Daily rhythm, every day, all phases:**
1. `uv run pytest -q` before the first edit — establish green.
2. Work one task. Move/rename in a separate commit from behaviour.
3. `uv run pytest -q` — count must be ≥ 551 passed.
4. `uv run ruff check . && uv run lint-imports` (from S1 onward).
5. Commit with the task ID in the subject. Push. CI must be green before the next task.

---

## P0 · Substrate — days 1–25

| Day | Objective | Coding | Tests | Expected repository state |
|---|---|---|---|---|
| 1 | **P0-01** clean tree | Review and stage 74 dirty paths in 5 logical commits (audit amendments · recovered-SE record · production patch + tests · V6 closure docs · V4 spec) | existing 551 | `git status` empty; tag `pre-P0`; **first rollback point exists** |
| 2 | **P0-02** backup | Extend `tools/ops/backup.sh`; offsite target; CI cron | checksum verify | backup bundle produced and checksummed |
| 3 | **P0-02** cont. | `data/validation/` included — the irreplaceable archive | manual restore | bundle verified offsite |
| 4 | **P0-03** drill | `tools/ops/restore.sh` refuses `mip` as target; scheduled job | `test_restore_drill` | drill runs on a scratch DB |
| 5 | **P0-03** cont. | — | full drill | **DB destroyed and restored byte-identically. P0 DoD met early.** |
| 6 | **P0-04** roots | Create `src/mip_evidence/`, `src/mip_forecast/`, `src/mip_proto/`; extras in `pyproject` | import smoke | 3 roots exist; wheel ships `src/mip` only |
| 7 | **P0-05** linter | `.importlinter` forbidden contracts | `lint-imports` | contracts green on the current tree |
| 8–9 | **P0-06** AST | `tests/invariants/test_ast_boundaries.py` — D1–D8 | itself | all 8 guards assert; D6 green |
| 10 | **P0-07** zero-signal | CI job: `rm -rf` both roots, `pytest -m "not requires_evidence"` | job | **job green — P1 principle now defended mechanically** |
| 11–12 | **P0-08** CI | `lint`, `unit`, `invariants`, `min-deps` jobs | — | four jobs merge-blocking |
| 13–16 | **P0-09** identity | `securities/` → `substrate/`; `security_id` everywhere; shims left behind | `test_identity_resolution` | no module resolves by ticker |
| 17 | **P0-10** head assert | `REFERENCE_TABLES` in `alembic/env.py` | `test_migration_head` | head mismatch raises |
| 18–19 | **P0-11** AsOf | `mip/core/asof.py`; thread through L0 | `test_asof_threading` | no default `as_of` below `cli/` |
| 20–23 | **P0-12** snapshots | Content-addressed `HistoricalSnapshot` | `test_snapshot_checksum` | checksum stable across processes |
| 24 | **P0-13** manifest | Regenerate + verify every hash | `test_manifest_verifies` | all hashes match |
| 25 | **P0-14** migrations | Fresh-DB up/down | `test_migration_chain` | 11 migrations, 86 tables. **Tag `P0-done`** |

## P1 · Market data + portfolio — days 26–50

| Day | Objective | Coding | Tests | Expected state |
|---|---|---|---|---|
| 26–29 | **P1-01** M2 | `ingestion/`+`providers/` → `marketdata/`; shims | `test_price_ingest` | 38,086-row ingest reproduces |
| 30–31 | **P1-02** M3 | `fundamentals/` split | `test_fundamentals_pit` | PIT interface reflected |
| 32–33 | **P1-03** M4 | `macro/` split | `test_macro_pit` | — |
| 34 | **P1-04** calendar | `reference/calendar.py` → `marketdata/` | `test_sessions` | 4419 sessions reproduce |
| 35–36 | **P1-05** guard | Completed-session guard | `test_no_inprogress_bar` | in-progress bar never read |
| 37–39 | **P1-06** revisions | Field-specific materiality tolerances | `test_revision_materiality` | no storm on real actions |
| 40–41 | **P1-07** raw shift | Raw-shift guard | `test_raw_shift_guard` | action vs data error distinguished |
| 42–44 | **P1-08** ledger | Append-only transaction ledger, `Decimal` | `test_ledger_append` | — |
| 45–48 | **P1-09** FIFO | Lot engine; oversell rejection; replay determinism | `test_lot_replay`, `test_oversell` | replay byte-identical twice |
| 49 | **P1-10** snapshot | `PositionSnapshot`; pins `as_of` | `test_rebuild_idempotence` | **full rebuild byte-identical twice running** |
| 50 | **P1-11/12** gate | PIT poisoning; `integration` job | `test_pit_poisoning` | **RELEASE GATE green. Tag `P1-done`** |

## P2 · Measurement + calc — weeks 11–14

| Week | Objective | Daily pattern | Exit state |
|---|---|---|---|
| 11 | **P2-01** + **P2-02** | Day 1 `CalculationResult`/`NotComputable`; days 2–5 C1–C6, one calc per half-day with its worked example first | `NotComputable` never raised |
| 12 | **P2-03** + **P2-04** | C7–C12 then P1–P7, same rhythm; **C9 partial-weights test written first** | every result carries a `unit` |
| 13 | **P2-05** + **P2-06** | `input_hash`; then `PositionState`, facts only | D3 guard green |
| 14 | **P2-07…P2-10** | `book_weights`, `MeasurementBasis`, AST test, then port `verify_reports.py` | **`verify_reports.py` exits 0 on the production engine. Tag `P2-done`** |

> Reserve the last two days of week 12 for the **P4-09 boundary-inversion spike** (risk I-01). It is not scheduled work in P2; it is a de-risking read-ahead so P4 does not discover the difficulty at week 20.

## P3 · Policy Engine — weeks 15–17

| Week | Objective | Daily pattern | Exit state |
|---|---|---|---|
| 15 | **P3-01/02** | `PolicyArtifact` with explicit `participation_rate`; loader; `config/policy/` | artifact loads with `content_hash` |
| 16 | **P3-03/04** | Semver immutability; `PolicyConstraint` | editing a released version raises |
| 17 | **P3-05…P3-07** | `ConstraintEvaluation` C1–C3/P1/P2; mandate detection across A–G; D2 guard | **mandate correct on all seven fixtures. Tag `P3-done`** |

## P4 · Decision + Report — weeks 18–25

| Week | Objective | Daily pattern | Exit state |
|---|---|---|---|
| 18 | **P4-01/02** + **P4-11** | Protocols first; then S1 with eliminations; ESCALATE | never a silent HOLD |
| 19 | **P4-03/04/05** | S2 mandate; S3 lexicographic P1..P6; S4 tier caps 0/±10/±20 | contribution 0 when evidence absent |
| 20 | **P4-06/07/08** | S5 dormant; S6 abstention; S7–S9 | `forecast_contribution == 0.0` |
| 21 | **P4-09** + **P4-10/12** | Boundary inversion (spiked in week 12); trace as returned value; term structure | inversion correct on all seven fixtures |
| 22 | **P4-13** + **P4-17** | Assembler **then semantic tests — in this order** (risk I-02) | 7 semantic assertions green |
| 23 | **P4-14** + **P4-18** | Renderer + templates N1–N7; golden byte-compare | **fourteen acceptance assertions green** |
| 24 | **P4-15/16** | Orchestrator, 13-stage manifest, `--resume`, advisory lock, atomic publication | stages 5/7 skip on absence |
| 25 | **P4-19/20/21** | Deprecate legacy engine; zero-signal full pipeline; remaining CI jobs | ✅ **acceptance green, `verify_reports.py` exit 0, suite passes with both optional roots deleted. Tag `P4-done` / `v4.0.0-rc`** |

## Phase 1 gate

**Do not begin P5.** S12 and S13 require a Phase 1 PASS. On KILL, both are cancelled and V4 ships as the policy-only product — which is what P0–P4 already delivers.
