# DOMAIN MODEL

**Part 2 of the V4 brief.** Ownership column names the single service that may write the entity.
Persistence: `IMM` = immutable append-only · `VER` = versioned, new row per change · `MUT` = mutable ·
`DER` = derived, recomputable, cached.

---

## 1 · Entity catalogue

| Entity | Owner | Persist | Key |
|---|---|---|---|
| `Security` | Substrate | IMM | `security_id` (permanent, never ticker) |
| `SecurityIdentifier` | Substrate | IMM | `(security_id, valid_from)` |
| `Portfolio` | Portfolio Svc | VER | `portfolio_id` |
| `Position` | Portfolio Svc | DER | `(portfolio_id, security_id, as_of)` |
| `TaxLot` | Portfolio Svc | IMM | `lot_id` |
| `PolicyArtifact` | Policy Engine | **VER, never MUT** | `(policy_id, version)` |
| `PolicyConstraint` | Policy Engine | VER | `(policy_id, version, constraint_id)` |
| `Measurement` | Measurement Svc | DER | `(portfolio_id, security_id, as_of, metric)` |
| `CalculationResult` | Calc Engine | DER | `(calc_id, input_hash)` |
| `ConstraintEvaluation` | Policy Engine | DER | `(portfolio_id, security_id, as_of, constraint_id)` |
| `EvidenceSource` | Evidence Svc | VER | `(source_name, version)` |
| `EvidenceClaim` | Evidence Svc | IMM | `claim_id` |
| `ReliabilityRecord` | Reliability Ledger | IMM | `(source, version, horizon, regime, as_of)` |
| `Forecast` | Forecast Svc | IMM | `forecast_id` |
| `DecisionCandidate` | Decision Engine | transient | — |
| `EliminationEntry` | Decision Engine | IMM (in trace) | `(decision_id, action)` |
| `DecisionTrace` | Decision Engine | IMM | `decision_id` |
| `PositionDecision` | Decision Engine | **IMM** | `decision_id` |
| `EvaluationContract` | Decision Engine | IMM | `decision_id` |
| `ReportModel` | Report Engine | DER | `(decision_id, template_version)` |
| `RenderedReport` | Report Engine | IMM | `report_id` |
| `HistoricalSnapshot` | Snapshot Svc | **IMM + checksummed** | `snapshot_id` |
| `ResearchRun` | Research Archive | IMM | `run_id` |
| `EvaluationResult` | Evaluation Svc | IMM | `(decision_id, contract_id, evaluated_at)` |
| `GovernanceEvent` | Governance Svc | IMM | `event_id` |
| `Scenario` | Evidence Svc | DER | `(security_id, as_of, factor)` |

## 2 · Core entities in detail

### `PolicyArtifact` — the only home for preferences

```python
@dataclass(frozen=True)
class PolicyArtifact:
    policy_id: int
    version: str                      # semver; a change is a NEW ROW
    authored_by: str
    reviewed_by: str | None           # external review, per V3 blocker 4
    effective_from: date
    portfolio_value_source: str
    hard_cap_pct: Decimal
    core_target_pct: Decimal
    band_pp: Decimal
    sector_cap_pct: Decimal
    liquidity_limit_days: Decimal
    participation_rate: Decimal       # = 1.0. EXPLICIT because Amendment 002 D-01
                                      # arose from an undocumented convention
    gains_budget: Decimal
    gains_used: Decimal
    objective_order: tuple[str, ...]  # P1..P6 lexicographic priority
    tolerance_bands: Mapping[str, Decimal]   # the epsilon values
    tier_caps: Mapping[InfluenceTier, int]
    rubric: Mapping[str, int]
    content_hash: str
```

> `participation_rate` is a field **because** D-01 was caused by an unstated convention. Every
> liquidity calculation must name the rate it used.

### `PositionDecision` — the archived unit

Fields per ARCHITECTURE_V2.1 §4, plus `snapshot_id`, `policy_version`, `ledger_snapshot_id`,
`engine_version`, `code_sha`, `input_checksum`. **Immutable.** A correction is a new decision that
supersedes, never an edit.

### `DecisionTrace` — returned, not logged

```python
@dataclass(frozen=True)
class DecisionTrace:
    decision_id: UUID
    stages: tuple[StageRecord, ...]        # every stage, inputs, survivors
    eliminations: tuple[EliminationEntry, ...]
    mandate_basis: str | None
    abstention_reason: str | None
    policy_version: str
    ledger_snapshot_id: str
    calculations: tuple[CalculationResult, ...]   # every derived figure + its inputs
```

`calculations` is what makes S05 (boundary conditions) invertible and what lets the acceptance suite
assert on arithmetic rather than on prose.

### `CalculationResult` — the anti-D-02 entity

```python
@dataclass(frozen=True)
class CalculationResult:
    calc_id: str                       # "C1_cap_excess", "C9_portfolio_hhi"
    inputs: Mapping[str, Decimal]
    value: Decimal | NotComputable     # <-- a VALUE, not an exception
    unit: str                          # "pp" | "USD" | "days" | "ratio" | "pct"
    deterministic: bool
    as_of: date
    input_hash: str
```

**`NotComputable` is a first-class value carrying a reason.** When the book weights are absent, `C9`
returns `NotComputable("requires all book weights")` and the renderer emits an explicit absence.
A plausible-looking number can never be produced for an uncomputable quantity — the structural fix for
the D-02 class of defect.

### `EvidenceClaim` — note what is absent

```python
@dataclass(frozen=True)
class EvidenceClaim:
    claim_id: UUID
    source: str; source_version: int
    security_id: int; as_of: date; horizon: Horizon
    claim: str                         # human-readable, falsifiable
    direction: Direction               # SUPPORTS_ADD | SUPPORTS_TRIM | NEUTRAL
    effect: Decimal                    # observed historical effect
    dispersion: Decimal                # OBSERVED, never effect/z
    n_effective: Decimal
    episodes: int
    provenance: Provenance
    # ABSENT BY DESIGN: se, z, score, confidence, weight.
```

### `ReliabilityRecord` — dual reliability

`descriptive_score` gates risk/conviction influence; `directional_score` gates expected direction.
Plus `episodes`, `minimum_detectable_effect`, `powered`, `tier`, `tier_since`, `demotion_reason`.
Conditioned on **horizon (mandatory) and regime (shrunk) only** — never sector/cap/vol, per the CPE
monotone-degradation finding.

## 3 · Relationships

```
Security 1──N SecurityIdentifier
Security 1──N Position ──N TaxLot
Portfolio 1──N Position
PolicyArtifact 1──N PolicyConstraint
PositionState + PolicyArtifact ──> ConstraintEvaluation ──> DecisionCandidate[]
EvidenceSource 1──N EvidenceClaim ──gated by──> ReliabilityRecord
DecisionCandidate[] + EvidenceClaim[] + Forecast? ──> PositionDecision 1──1 DecisionTrace
PositionDecision 1──1 EvaluationContract 1──N EvaluationResult ──updates──> ReliabilityRecord
PositionDecision 1──1 ReportModel 1──N RenderedReport
HistoricalSnapshot 1──N ResearchRun
GovernanceEvent ──authorises──> PolicyArtifact(version) | ReliabilityRecord(tier)
```

## 4 · Ownership invariants — AST-enforced

| Invariant | Test |
|---|---|
| Only Policy Engine writes `PolicyArtifact` | import guard |
| Only Reliability Ledger writes `ReliabilityRecord` | import guard + `ReliabilityLedgerReader` type |
| Decision Engine writes no entity except `PositionDecision`/`DecisionTrace` | import guard |
| Report Engine writes nothing outside `ReportModel`/`RenderedReport` | import guard |
| No package outside Policy Engine + Decision Engine imports `mip.policy` | AST test (P4) |
| `EvidenceClaim` has no field named `se`, `z`, `score`, `weight`, `confidence` | schema test (P2) |
