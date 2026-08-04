# SERVICE ARCHITECTURE

**Part 5 of the V4 brief.**

---

## 1 · Deployment stance: modular monolith

The brief lists thirteen candidate services. **Deploying thirteen network services for a platform whose
working set is ~50 positions × 5 horizons would be architecture theatre.** V4 defines thirteen
*modules* with hard boundaries inside **one process and one deployment**.

Boundaries are enforced by **AST import tests**, which the v1 platform already proved effective — the
same mechanism that keeps `mip.engine.trim` importing only `engine.evidence` and `core.exceptions`.
AST enforcement is strictly stronger than network separation for the invariants that matter here
(no self-authorisation, no preference leakage), and it costs no latency, no serialisation and no
distributed-failure surface.

**Extraction path:** any module may be lifted to a process boundary later, because each already
communicates through a Protocol with no shared mutable state. The two candidates if scale ever demands
it are Market Data ingestion and the walk-forward Research Runner — both batch, both isolatable.

## 2 · Module register

| # | Module | Owns (writes) | Depends on | Public API |
|---|---|---|---|---|
| **M1** | **Substrate** | `security_master`, identity history, migrations, snapshots, backups | — | `SecurityRepository`, `SnapshotStore` |
| **M2** | **Market Data** | prices, corporate actions, market snapshots, benchmarks | M1 | `PriceRepository(as_of)`, `ActionRepository(as_of)` |
| **M3** | **Fundamentals** | PIT vintages | M1 | `FundamentalsRepository(as_of, vintage)` |
| **M4** | **Macro** | macro observations | M1 | `MacroRepository(as_of)` |
| **M5** | **Portfolio** | transactions, lots, position snapshots | M1, M2 | `PortfolioService`, `TaxLotService` |
| **M6** | **Measurement (L1)** | measurements (derived) | M2, M5 | `MeasurementService.position_state(...)`, `.book_weights(...)` |
| **M7** | **Policy Engine (L2)** | policy artifacts, constraint evaluations | M6 | `PolicyEngine.load/evaluate` |
| **M8** | **Evidence (L3)** *(optional)* | evidence claims, catalysts, scenarios | M2–M4, M6 | `EvidenceSource` Protocol, `EvidenceService.claims(...)` |
| **M9** | **Reliability Ledger (L4)** | reliability records, tiers | M14 | **`ReliabilityLedgerReader`** (read) · `LedgerWriter` (separate type, M9-internal) |
| **M10** | **Forecast (L5)** *(optional, dormant)* | forecasts | M8, M9 | `ForecastService.forecast(...)` |
| **M11** | **Decision Engine (L6)** | decisions, traces | M6, M7, M8?, M9, M10? | `DecisionEngine.decide(...) -> (decision, trace)` |
| **M12** | **Report Engine (L7)** | report models, rendered reports | M11 | `ReportAssembler.assemble`, `Renderer.render` |
| **M13** | **Decision Archive (L8)** | archived decisions, contracts | M11 | `DecisionArchive.append/latest_before/get` |
| **M14** | **Evaluation (L9)** | evaluation results | M13, M2 | `EvaluationService.evaluate_matured(...)` |
| **M15** | **Governance (L10)** | governance events | M7, M9 | `GovernanceService.propose/approve` |
| **M16** | **Validation** | — (test-only) | all | `verify_invariants()`, acceptance runner |
| **M17** | **Administration** | run manifests, orchestration | all | CLI `mip update`, `mip report`, `mip evaluate` |

## 3 · Consolidations against the brief's candidate list

| Brief candidate | V4 treatment |
|---|---|
| Portfolio Service | **M5** as listed |
| Policy Engine | **M7** as listed |
| Evidence Engine | **M8** — optional package |
| Measurement Engine | **M6** as listed |
| Decision Engine | **M11** as listed |
| Report Engine | **M12** as listed |
| Research Archive | **merged into M13** — a research run is an archived decision set plus a snapshot ref. Two archives would drift |
| Historical Snapshot Service | **merged into M1** — snapshots are a substrate concern, not a peer service |
| Market Data Service | **M2** as listed |
| Recommendation Service | **merged into M11** — a recommendation is a decision plus actionability. A separate service would split the decision across a boundary |
| Narrative Service | **merged into M12** — templates only; a separate service implies generative narrative, which is prohibited |
| Validation Service | **M16**, test-scope only. It must never run in the decision path |
| Administration Service | **M17** as listed |

Four merges, each because the split would create a seam without an owner.

## 4 · State ownership

**Single-writer rule: exactly one module may write each table.** All others read through a Protocol.

Two ownership rules are load-bearing:

1. **M11 (Decision Engine) writes only `position_decision` and `decision_trace`.** It cannot write
   policy, cannot write the ledger, cannot write measurements.
2. **M9's read and write surfaces are different types.** M11 holds `ReliabilityLedgerReader`, which has
   no write methods. `LedgerWriter` lives in a module M11 does not import. Self-authorisation is a
   compile error, not a code-review question.

## 5 · Public API sketch

```python
# M6
def position_state(portfolio_id: int, security_id: int, as_of: date) -> PositionState
def book_weights(portfolio_id: int, as_of: date) -> Mapping[int, Decimal] | NotComputable

# M7
def load(version: str) -> PolicyArtifact
def evaluate(state: PositionState, policy: PolicyArtifact) -> ConstraintEvaluation

# M11
def decide(ctx: DecisionContext, horizon: Horizon) -> tuple[PositionDecision, DecisionTrace]
def decide_all_horizons(ctx: DecisionContext) -> HorizonTermStructure

# M12
def assemble(d: PositionDecision, t: DecisionTrace) -> ReportModel
def render(model: ReportModel, template_version: str) -> str

# M13
def append(d: PositionDecision, t: DecisionTrace, c: EvaluationContract) -> UUID
def latest_before(portfolio_id, security_id, horizon, as_of) -> PositionDecision | None

# M14
def evaluate_matured(as_of: date) -> list[EvaluationResult]     # feeds M9
```

## 6 · Failure and degradation

| Failure | Behaviour |
|---|---|
| M8 (Evidence) unavailable or **not installed** | Decisions proceed with zero evidence contribution. **Reports remain complete.** This is the P1 zero-signal test |
| M10 (Forecast) unavailable or not installed | `forecast_contribution = 0.0`. Already the state on every frozen report |
| M9 (Ledger) unavailable | **Hard fail.** Without tier information, evidence cannot be bounded. Better to stop than to admit unbounded influence |
| M2 stale | Decision proceeds against the last complete session; staleness is stated in the report |
| M13 empty | `what_changed` omitted; terminal wealth renders "not available" (A-004) |

**The asymmetry is deliberate.** Missing evidence degrades gracefully; a missing *governor* of evidence
does not degrade at all.
