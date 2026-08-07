# V4 — Test Plan (conforming)

**Authority:** frozen `REPOSITORY_STRUCTURE.md` §3–§4 and `ACCEPTANCE_TEST_PLAN.md`.
**Baseline that may not regress:** 551 passed / 252 skipped. **No milestone may reduce the passing count without an explicitly approved test replacement recorded in the PR.**

## 1 · Taxonomy (frozen targets)

| Layer | Scope | Target | Speed |
|---|---|---|---|
| Unit | one pure function each | ~400 | ms |
| Invariants | determinism, PIT, boundaries, recomputability | ~40 | s |
| Integration | full migration chain + DB | ~150 | min |
| **Acceptance** | **the seven reports** | **14** (7 semantic + 7 golden) | s |
| Contract | `tools/phase1/verify_reports.py` | 81 checks | s |

**The semantic/golden split is mandatory** (frozen risk R3): a layout change touches seven golden files and zero semantic assertions; a logic change fails semantics first.

## 2 · Invariant suite — `tests/invariants/`

| Test | Assertion |
|---|---|
| `test_determinism.py` | same inputs → byte-identical output; two subprocesses, `PYTHONHASHSEED` 0 and 1 |
| `test_pit_poisoning.py` | corrupt every post-`as_of` row → identical output · **RELEASE GATE** |
| **`test_zero_signal.py`** | full 13-stage pipeline with `src/mip_evidence/` and `src/mip_forecast/` **deleted from disk**; complete `RenderedReport`; `forecast_contribution == 0.0`; evidence contribution `0` |
| `test_ast_boundaries.py` | D1–D8 import guards, single-writer, no-preference-leak |
| `test_no_self_authorisation.py` | `decision/` cannot hold `ReliabilityLedgerWriter` |
| `test_recomputability.py` | every emitted figure derives from persisted inputs |
| `test_evidence_claim_schema.py` | `EvidenceClaim` has no field `se`, `z`, `score`, `weight`, `confidence` (P2) |
| `test_notcomputable_is_value.py` | C9 with partial book weights returns `NotComputable`, does not raise, and renders as explicit absence |

## 3 · Boundary enforcement (Part 7)

| Test | Proves |
|---|---|
| `test_import_boundaries` (`lint-imports`) | `mip` ↛ `mip_evidence`, `mip_forecast`, `mip_proto`, `mip.research*` |
| `test_no_dependency_cycles` | import graph over `src/mip/` is a DAG; L(n) never imports L(>n) |
| **policy-only installation** | CI job installs `[project].dependencies` only — no extras — and imports `mip.cli.main` |
| **policy-only execution** | `test_zero_signal.py` above |
| **evidence-absent** | `rm -rf src/mip_evidence` → `pytest -m "not requires_evidence"` green |
| **forecast-absent** | `rm -rf src/mip_forecast` → same |
| deterministic pipeline | run twice, diff byte-for-byte |
| frozen domain serialization | every entity round-trips; no `float`; `Decimal`→str; keys sorted |
| golden Phase 1 reports | byte-compare vs `docs/phase1/01_participant/case_*.md` |
| **regression preservation** | `pytest` count ≥ 551 passed at every milestone |
| migration compatibility | full chain up/down on a fresh DB; `REFERENCE_TABLES` head assertion |

## 4 · Unit tests by module

`substrate` identity resolution, snapshot checksum, restore drill · `marketdata` completed-session guard, revision materiality, raw-shift guard · `portfolio` FIFO replay, oversell rejection, `Decimal` exactness · `calc` one test per C1–C12 and P1–P7 with worked examples from the frozen packets · `measurement` facts-only, no preference leak · `policy` version immutability, `content_hash`, mandate detection across all seven fixtures · `decision` each cascade stage, elimination recording, ESCALATE on empty feasible set, abstention · `report` assembler/renderer separation, tier caps, deny-list · `archive` immutability, PIT invisibility · `evaluation` counterfactual arithmetic, mandatory terminal wealth · `engine.evidence` the 17 existing recovered-SE regression tests, retained verbatim.

## 5 · Property tests

| Property | Statement |
|---|---|
| lot additivity | `position.quantity == Σ lot.quantity` exactly under `Decimal` |
| policy totality | ∀ state incl. all-unavailable: one `ConstraintEvaluation` per constraint, no exception |
| calc totality | ∀ inputs: `CalculationResult` returned, `NotComputable` where inputs are absent |
| tier ceiling | ∀ claim: contribution ≤ tier cap (0 / ±10 / ±20) |
| decision totality | ∀ context: `(PositionDecision, DecisionTrace)` or `ESCALATE`; never a silent HOLD |
| trace invertibility | every figure in `ReportModel` traces to a `CalculationResult` in `DecisionTrace.calculations` |
| serialization round-trip | `from_dict(to_dict(x)) == x` for every frozen entity |

## 6 · CI jobs — every one a merge blocker (frozen §3)

```yaml
lint:        ruff · black --check · lint-imports
unit:        pytest tests/unit
invariants:  pytest tests/invariants                      # includes PIT poisoning
zero-signal: rm -rf src/mip_evidence src/mip_forecast     # ADR-004 C-1: absence, not a flag
             pytest tests/ -m "not requires_evidence"     # MUST PASS
min-deps:    install [project].dependencies only; pytest tests/unit tests/invariants
integration: pytest tests/integration                     # fresh DB, full migration chain
acceptance:  pytest tests/acceptance                      # the seven reports
contract:    python tools/phase1/verify_reports.py        # must exit 0
determinism: run pipeline twice, diff byte-for-byte
```

`zero-signal` is the job that keeps the architecture honest: if `mip/` acquires a dependency on `mip_evidence/`, it fails and P1 is defended mechanically rather than by review.
