# V4 — Module Specifications (conforming)

**Authority:** frozen `DOMAIN_MODEL.md` + `REPOSITORY_STRUCTURE.md`. Frozen names are used verbatim; no synonyms are introduced.

## PART 5 — Domain model conformance

Canonical home: `src/mip/domain/`. All entities `@dataclass(frozen=True, slots=True)`.
Serialization: `to_dict()` — key-sorted, `Decimal` → string, `date` → ISO-8601, no `float` anywhere.
Versioning: `IMM` never edited (correction = new row that supersedes) · `VER` = new row per change (semver) · `DER` = recomputable, cached, safe to drop.

| Frozen entity | Existing equivalent | Required adaptation | Canonical owner | Persist |
|---|---|---|---|---|
| `Security`, `SecurityIdentifier` | `securities/` | move to `substrate/`; key on `security_id`, **never ticker** | Substrate M1 | IMM |
| `Portfolio`, `Position`, `TaxLot` | `portfolio/{snapshots,lots}.py` | `Decimal` audit; FIFO replay determinism; oversell rejection | Portfolio Svc M5 | VER/DER/IMM |
| `PositionSnapshot` | `portfolio/snapshots.py` | add `snapshot_id`, checksum, `as_of` pinning | Portfolio Svc M5 | IMM |
| **`PolicyArtifact`** | **none — new** | semver, never edited; **explicit `participation_rate`**; `objective_order`, `tolerance_bands`, `tier_caps`, `rubric`, `content_hash` | Policy Engine M7 | **VER, never MUT** |
| `PolicyConstraint` | none | per-version rows | Policy Engine M7 | VER |
| **`PositionState`** | partially `portfolio/analytics.py` | facts only, zero preferences | Measurement M6 | DER |
| **`Measurement`** | none | `(portfolio_id, security_id, as_of, metric)` | Measurement M6 | DER |
| **`CalculationResult`** | none | `value: Decimal \| NotComputable`; `unit`; `input_hash`; `deterministic` | Calc Engine | DER |
| `NotComputable` | none | **first-class value carrying a reason** — never an exception | Calc Engine | — |
| **`ConstraintEvaluation`** | none | one row per `(…, constraint_id)`; C1–C3, P1, P2 | Policy Engine M7 | DER |
| `EvidenceSource` | `models/*.py` | move to `mip_evidence/sources/`; versioned | Evidence Svc M8 | VER |
| **`EvidenceClaim`** | `NormalizedEvidence` (`models/base.py`) | **strip `se`, `z`, `score`, `weight`, `confidence`**; add `dispersion` (OBSERVED, never `effect/z`), `n_effective`, `episodes`, `provenance` | Evidence Svc M8 | IMM |
| **`ReliabilityRecord`** | none | `descriptive_score` + `directional_score`; `episodes`, `minimum_detectable_effect`, `powered`, `tier`, `tier_since`, `demotion_reason`; conditioned on **horizon (mandatory) + regime (shrunk) only** | Reliability Ledger M9 | IMM |
| `Forecast` | none | dormant | Forecast Svc M10 | IMM |
| `DecisionCandidate`, `EliminationEntry` | none | transient / in-trace | Decision Engine M11 | — / IMM |
| **`DecisionTrace`** | none | **returned, not logged**; `stages`, `eliminations`, `mandate_basis`, `abstention_reason`, `policy_version`, `ledger_snapshot_id`, `calculations` | Decision Engine M11 | IMM |
| **`PositionDecision`** | `engine/trim.py` output (deprecated) | ARCHITECTURE_V2.1 §4 fields + `snapshot_id`, `policy_version`, `ledger_snapshot_id`, `engine_version`, `code_sha`, `input_checksum` | Decision Engine M11 | **IMM** |
| `EvaluationContract` | none | stamped at decision creation, non-nullable | Decision Engine M11 | IMM |
| **`ReportModel`** / **`RenderedReport`** | `engine/report.py` (fused) | **split assembler from renderer** | Report Engine M12 | DER / IMM |
| `HistoricalSnapshot` | `tools/ops/backup.sh` | content-addressed + checksummed | Snapshot Svc M1 | IMM + checksummed |
| `EvaluationResult` | `validation/` | layer-specific scoring | Evaluation Svc M14 | IMM |
| `GovernanceEvent` | none | authorises `PolicyArtifact(version)` and `ReliabilityRecord(tier)` | Governance M15 | IMM |
| `ResearchRun`, `Scenario` | `research_data/` | archive in place | Research Archive / Evidence Svc | IMM / DER |

**Immutability rule:** every `IMM` entity is append-only. A correction creates a new row that supersedes; no edit, ever.
**Schema test (P2):** `EvidenceClaim` must have no field named `se`, `z`, `score`, `weight`, `confidence`.

## PART 4 — Module contracts

### `mip.substrate` (M1, L0)
`security_id(identifier, as_of) -> int` · `snapshot(scope, as_of) -> HistoricalSnapshot` · `restore(snapshot_id)`
Errors: `ConfigurationError` on migration-head mismatch (`REFERENCE_TABLES` assertion). Deterministic: checksum-stable.

### `mip.marketdata` (M2, L0)
`prices(security_id, window, as_of)` · `actions(...)` · `market_snapshot(as_of)` · `sessions(...)`
Errors: `DataUnavailable`. **Never reads the in-progress bar.** Revision handling with field-specific materiality tolerances and the raw-shift guard.

### `mip.portfolio` (M5, L0)
`snapshot(portfolio_id, as_of) -> PositionSnapshot` (**pins `as_of`**) · `lots(...)` FIFO, `Decimal`, replay-deterministic, oversell-rejecting.
Deterministic: byte-identical rebuild from the transaction ledger, twice running.

### `mip.calc`
`compute(calc_id, inputs, as_of) -> CalculationResult` for C1–C12 and P1–P7.
**Returns `NotComputable(reason)` as a value; never raises for missing inputs.** Every result carries a `unit`.
Example: C9 (portfolio HHI) returns `NotComputable("requires all book weights")` on partial weights.

### `mip.measurement` (M6, L1)
`position_state(security_id, as_of, basis: MeasurementBasis) -> PositionState` · `book_weights(portfolio_id, as_of) -> Mapping | NotComputable`
**Facts only. Zero preferences. Imports no L2+ module** (D3). `MeasurementBasis` is passed in by the orchestrator, extracted from `PolicyArtifact` at stage 2.

### `mip.policy` (M7, L2)
`load(policy_version) -> PolicyArtifact` · `evaluate(state, policy) -> tuple[ConstraintEvaluation, ...]`
The **only** module besides `decision/` that may hold preferences (D2). `PolicyArtifact` is never edited — a change is a new version.
Errors: `ConfigurationError` on unknown version or `content_hash` mismatch.

### `mip.decision` (M11, L6)
`decide(ctx, horizon) -> tuple[PositionDecision, DecisionTrace]`
Cascade S1–S9: S1 hard constraints → S2 mandate → S3 lexicographic P1..P6 → S4 bounded evidence modulation (tier caps 0 / ±10 / ±20) → S5 forecast (dormant) → S6 abstention → S7–S9 score/confidence/boundaries.
**Empty feasible set after S1 ⇒ `ESCALATE`, archived — never a silent HOLD.**
**Never holds a `ReliabilityLedgerWriter`** (D4). Depends on `EvidenceProvider`/`ForecastProvider` Protocols only.

### `mip.report` (M12, L7)
`assemble(decision, trace) -> ReportModel` · `render(model, template_version) -> RenderedReport` — **separated** (frozen risk R3).
Errors: `IntegrityError` if any claim exceeds its tier cap, or if a deny-listed token reaches rendered text.

### `mip.archive` (M13, L8)
`append(decision, trace, contract) -> decision_id` · `latest_before(...) -> PositionDecision | None`
Immutable; future decisions invisible at `as_of` (PIT).

### `mip.evaluation` (M14, L9)
Layer-specific scoring: policy → realised **risk**, evidence → **descriptive** accuracy, forecast → realised **return**.
Three counterfactuals incl. **policy-only**. **Terminal-wealth disclosure is mandatory, even when unfavourable.**

### `mip.governance` (M15, L10)
`record(event) -> event_id`. Authorises `PolicyArtifact(version)` and `ReliabilityRecord(tier)` changes.

### `mip_evidence.reliability` (M9)
`ReliabilityLedgerReader.tier(source, horizon, regime) -> InfluenceTier` · `ReliabilityLedgerWriter.update(...)`
**Reader and writer are distinct types.** Auto-demotes on decay, staleness, regime break.

### `mip.cli` (M17)
Orchestrator: 13 stages, per-stage manifest, `--resume RUN_ID`, advisory session lock, per-position savepoint.
The only layer permitted to read the clock, `sys.argv`, or write outside the archive.
