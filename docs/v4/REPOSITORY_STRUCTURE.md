# REPOSITORY STRUCTURE

**Part 7 of the V4 brief.** Three top-level source trees, separated by lifecycle: **production**,
**prototype**, **shared**.

---

## 1 · Layout

```
stock_scoring/
├── src/
│   ├── mip/                          ── PRODUCTION
│   │   ├── core/                     config, exceptions, decimal helpers, AsOf context
│   │   ├── substrate/                M1  identity, migrations, snapshots, backup
│   │   ├── marketdata/               M2
│   │   ├── fundamentals/             M3
│   │   ├── macro/                    M4
│   │   ├── portfolio/                M5  transactions, FIFO lots, snapshots
│   │   ├── measurement/              M6  L1 facts
│   │   ├── policy/                   M7  L2  <- ONLY module besides decision/ that may hold prefs
│   │   ├── calc/                     C1-C12, P1-P7 · NotComputable · CalculationResult
│   │   ├── decision/                 M11 L6 engine, stages, trace
│   │   ├── report/                   M12 L7 assembler + renderer (SEPARATED)
│   │   ├── archive/                  M13 L8
│   │   ├── evaluation/               M14 L9 contracts, counterfactuals, terminal wealth
│   │   ├── governance/               M15 L10
│   │   └── cli/                      M17
│   │
│   ├── mip_evidence/                 ── PRODUCTION, OPTIONAL PACKAGE
│   │   ├── sources/                  M8  one module per EvidenceSource
│   │   ├── catalysts/                PIT-verified dated events only
│   │   └── reliability/              M9  ledger; reader/writer types SPLIT
│   │
│   ├── mip_forecast/                 ── PRODUCTION, OPTIONAL, DORMANT
│   │   └── ...                       M10 no source has ever reached DIRECTIONAL tier
│   │
│   └── mip_proto/                    ── PROTOTYPE ONLY, NEVER IMPORTED BY mip/
│       ├── legacy.py                 legacy_action_strength()  <- Case G acceptance only
│       └── study_fixtures/           the 7 case fixtures
│
├── tools/
│   └── phase1/                       ── FROZEN, study-scope
│       ├── case_facts.py
│       └── verify_reports.py         81 checks — SEED of the production invariant suite
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── acceptance/                   ── THE SEVEN REPORTS AS CONTRACT
│   │   ├── test_semantic.py          asserts on ReportModel  (layout-independent)
│   │   ├── test_golden_render.py     byte-compare vs docs/phase1/01_participant/case_*.md
│   │   └── fixtures/case_{A..G}/
│   ├── invariants/
│   │   ├── test_determinism.py       same inputs -> byte-identical output
│   │   ├── test_pit_poisoning.py     corrupt post-as_of rows -> identical output   [RELEASE GATE]
│   │   ├── test_zero_signal.py       runs with mip_evidence + mip_forecast UNINSTALLED
│   │   ├── test_ast_boundaries.py    import guards, single-writer, no-preference-leak
│   │   ├── test_no_self_authorisation.py   engine cannot hold LedgerWriter
│   │   └── test_recomputability.py   every emitted figure derives from persisted inputs
│   └── conftest.py
│
├── alembic/versions/                 forward-only migrations
├── config/
│   ├── policy/                       PolicyArtifact versions — semver, never edited
│   ├── decision_config/              objective order, epsilon, tier caps, rubric
│   └── templates/                    report templates, versioned
├── docs/
│   ├── phase1/                       ── FROZEN CONTRACT. Read-only after freeze
│   └── v4/                           this architecture set
└── .github/workflows/ci.yml
```

## 2 · Classification of every tree

| Tree | Class | Rationale |
|---|---|---|
| `src/mip/` | **PRODUCTION** | Layers 0–2, 6–10. Survives indefinitely |
| `src/mip_evidence/` | **PRODUCTION, optional** | Must be uninstallable without breaking anything (P1) |
| `src/mip_forecast/` | **EXPERIMENTAL / dormant** | Built last, or never. No source has cleared DIRECTIONAL |
| `src/mip_proto/` | **PROTOTYPE ONLY** | Study fixtures + `legacy_action_strength`. AST test forbids `mip/` importing it |
| `tools/phase1/` | **FROZEN, study-scope** | Its 81 checks are ported into `tests/invariants/`, not deleted |
| `docs/phase1/` | **FROZEN CONTRACT** | Read-only. Any change requires an Amendment |
| `tests/acceptance/` | **PRODUCTION** | The contract, executable |

## 3 · CI pipeline

```yaml
jobs:
  lint:        ruff · black --check
  unit:        pytest tests/unit
  invariants:  pytest tests/invariants                       # includes PIT poisoning
  zero-signal: pip uninstall mip_evidence mip_forecast
               pytest tests/ -m "not requires_evidence"      # MUST PASS
  integration: pytest tests/integration                      # fresh DB, full migration chain
  acceptance:  pytest tests/acceptance                       # the seven reports
  contract:    python tools/phase1/verify_reports.py         # must exit 0
  determinism: run pipeline twice, diff byte-for-byte
```

**Every job is a merge blocker.** The `zero-signal` job is the one that keeps the architecture honest:
if a developer makes `mip/` depend on `mip_evidence/`, that job fails and the P1 principle is defended
mechanically rather than by review.

## 4 · Test taxonomy

| Layer | Scope | Count (target) | Speed |
|---|---|---|---|
| Unit | pure calculations, one function each | ~400 | ms |
| Invariants | determinism, PIT, boundaries, recomputability | ~40 | s |
| Integration | full migration chain + DB | ~150 | min |
| **Acceptance** | **the seven reports** | **14** (7 semantic + 7 golden) | s |
| Contract | `verify_reports.py` | 81 checks | s |

**The semantic/golden split is mandatory** (risk R3). A layout change touches seven golden files and
zero semantic assertions; a *logic* change fails semantics first, which is where the signal is.
