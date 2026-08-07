# V4 — Repository Layout (conforming)

**Authority:** `REPOSITORY_STRUCTURE.md` (frozen). **Vehicle:** the existing single `mip` distribution per `ADR-004`.
Frozen names, module numbers (M1–M17) and layer numbers (L0–L10) are reproduced exactly.

## 1 · Target layout inside the existing repository

```
stock_scoring/
├── src/
│   ├── mip/                      ── PRODUCTION  (the shipped distribution)
│   │   ├── core/          L0     config, exceptions, Decimal helpers, AsOf context   [EXISTS]
│   │   ├── substrate/     M1 L0  identity, migrations, snapshots, backup             [NEW — from securities/, core/db]
│   │   ├── marketdata/    M2 L0  prices, actions, market snapshots                   [NEW — from ingestion/, providers/]
│   │   ├── fundamentals/  M3 L0                                                       [NEW — from ingestion/]
│   │   ├── macro/         M4 L0                                                       [NEW — from ingestion/]
│   │   ├── portfolio/     M5 L0  transactions, FIFO lots, snapshots                  [EXISTS — extend]
│   │   ├── measurement/   M6 L1  facts only                                           [NEW]
│   │   ├── calc/          —      C1–C12, P1–P7, NotComputable, CalculationResult     [NEW]
│   │   ├── policy/        M7 L2  PolicyArtifact, ConstraintEvaluation                [NEW]
│   │   ├── decision/      M11 L6 engine, stages, DecisionTrace                        [NEW]
│   │   ├── report/        M12 L7 assembler + renderer, SEPARATED                      [NEW — supersedes engine/report.py]
│   │   ├── archive/       M13 L8 immutable decision store                             [NEW]
│   │   ├── evaluation/    M14 L9 contracts, counterfactuals, terminal wealth          [EXISTS — extend]
│   │   ├── governance/    M15 L10                                                     [NEW]
│   │   └── cli/           M17    orchestrator + commands                              [EXISTS — extend]
│   │
│   ├── mip_evidence/             ── PRODUCTION, OPTIONAL   (root created now, shipped later)
│   │   ├── sources/       M8     one module per EvidenceSource        [from models/]
│   │   ├── catalysts/            PIT-verified dated events only        [from research/]
│   │   └── reliability/   M9     ledger; reader/writer types SPLIT     [NEW]
│   │
│   ├── mip_forecast/             ── OPTIONAL, DORMANT      M10          [empty root + Protocol impl stub]
│   │
│   └── mip_proto/                ── PROTOTYPE ONLY, NEVER IMPORTED BY mip/
│       ├── legacy.py             legacy_action_strength()  — Case G acceptance only
│       └── study_fixtures/       the seven case fixtures
│
├── tools/phase1/                 ── FROZEN, study-scope (81 checks → ported, not deleted)
├── tests/{unit,integration,acceptance,invariants}/
├── config/{policy,decision_config,templates}/
├── alembic/versions/
└── docs/{phase1,v4,v5,v6}/
```

## 2 · Retained-in-place packages not named by the frozen structure

The frozen structure names the **target**. These existing packages have no frozen counterpart and are classified here:

| Existing | Disposition | Reason |
|---|---|---|
| `features/` | **RETAIN in place** | Feature store (69 definitions) feeds `mip_evidence/sources`. Not on the policy-only path. |
| `models/` | **MOVE → `mip_evidence/sources/`** (P5+) | These are EvidenceSources under frozen naming. Gated. |
| `engine/evidence.py` | **WRAP behind `EvidenceProvider` Protocol**, then move | Patched (A-2026-006); must not be reachable from the policy-only path. |
| `engine/trim.py` | **DEPRECATE** | Produces directional recommendations — excluded by the product evidence boundary. |
| `engine/intelligence.py`, `engine/attribution.py`, `engine/report.py` | **DEPRECATE**, superseded by `report/` (M12) | Frozen structure separates assembler and renderer. |
| `research/`, `research_data/` | **ARCHIVE in place, FROZEN** | No production import. AST-enforced. |
| `validation/` | **RETAIN**, feeds `evaluation/` (M14) | PIT metrics, cohort, eligibility. |
| `repositories/` | **RETAIN, split by owner** | One repository module per owning module; single-writer invariant. |
| `reference/` | **MOVE → `substrate/` + `marketdata/`** | Calendar → marketdata; universe/sectors → substrate. |
| `securities/` | **MOVE → `substrate/` (M1)** | It *is* the identity spine. |
| `ingestion/`, `providers/` | **SPLIT → `marketdata/`, `fundamentals/`, `macro/`** | Frozen structure separates by domain. |
| `update/`, `api/`, `reporting/` | **RETAIN**, `reporting/` folds into `report/` renderer | — |
| `domain/` | **RETAIN**, extend with frozen entities | Canonical home for enums + entities. |

## 3 · Dependency rules (frozen, L0–L10)

```
L0  core, substrate(M1), marketdata(M2), fundamentals(M3), macro(M4), portfolio(M5)
L1  measurement(M6)                     ← facts only
L2  policy(M7)                          ← ONLY module besides decision/ that may hold preferences
L6  decision(M11)
L7  report(M12)
L8  archive(M13)
L9  evaluation(M14)
L10 governance(M15)
opt mip_evidence(M8,M9) · mip_forecast(M10)
```

**Prohibitions — each an executable test:**

| # | Rule | Test |
|---|---|---|
| D1 | `mip/` must not import `mip_evidence`, `mip_forecast`, `mip_proto` | `test_ast_boundaries.py`, `lint-imports` |
| D2 | No package outside `policy/` and `decision/` imports `mip.policy` | `test_ast_boundaries.py` (P4) |
| D3 | `measurement/` (L1) holds no preferences and imports no L2+ module | AST |
| D4 | `decision/` never holds a `ReliabilityLedgerWriter` | `test_no_self_authorisation.py` |
| D5 | `report/` writes nothing outside `ReportModel`/`RenderedReport` | AST |
| D6 | No production module imports `mip.research*` | AST |
| D7 | `mip_proto` importable only from `tests/acceptance/` | AST |
| D8 | `EvidenceClaim` has no field `se`, `z`, `score`, `weight`, `confidence` | schema test (P2) |

## 4 · Ownership (single-writer, frozen)

| Entity | Sole writer |
|---|---|
| `PolicyArtifact`, `PolicyConstraint`, `ConstraintEvaluation` | `policy/` (M7) |
| `Measurement`, `CalculationResult` | `measurement/` (M6) + `calc/` |
| `PositionDecision`, `DecisionTrace`, `EvaluationContract` | `decision/` (M11) |
| `ReportModel`, `RenderedReport` | `report/` (M12) |
| `ReliabilityRecord` | `mip_evidence/reliability/` (M9) writer type only |
| `EvidenceClaim`, `EvidenceSource` | `mip_evidence/sources/` (M8) |
| `Security`, `SecurityIdentifier`, `HistoricalSnapshot` | `substrate/` (M1) |
| `GovernanceEvent` | `governance/` (M15) |
