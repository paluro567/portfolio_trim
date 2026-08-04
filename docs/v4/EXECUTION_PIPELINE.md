# EXECUTION PIPELINE

**Part 6 of the V4 brief.** One pipeline, twelve stages, resumable, with a stage manifest — the pattern
already proven by the v1 orchestrator.

---

## 1 · Stage sequence

```
 1  portfolio snapshot      M5   → PositionSnapshot            [pins as_of]
 2  policy loading          M7   → PolicyArtifact@version
 3  measurement generation  M6   → PositionState + Measurement[]
 4  constraint evaluation   M7   → ConstraintEvaluation[]
 5  evidence generation     M8?  → EvidenceClaim[]        SKIPPED IF ABSENT
 6  reliability read        M9   → ReliabilityRecord[] + ledger_snapshot_id
 7  forecast                M10? → Forecast?              SKIPPED IF ABSENT
 8  decision generation     M11  → PositionDecision + DecisionTrace   (×5 horizons)
 9  horizon reconciliation  M11  → HorizonTermStructure
10  report generation       M12  → ReportModel → RenderedReport
11  archive                 M13  → decision_id, contract stamped
12  verification            M16  → invariant suite; NON-ZERO EXIT BLOCKS PUBLICATION
13  publication             M17  → latest/ + dated tree
```

**Stages 5 and 7 are skippable by package absence, not by flag.** If `mip.evidence` is not installed,
stage 5 does not run and the pipeline completes normally. That is the zero-signal contract executed at
runtime.

**Stage 12 gates stage 13.** A verification failure blocks publication and leaves the previous published
artifacts untouched — the atomic-replace pattern already shipped in v1's `reporting/latest.py`.

## 2 · Primary sequence — one position, one horizon

```mermaid
sequenceDiagram
    autonumber
    participant O as M17 Orchestrator
    participant P as M5 Portfolio
    participant PE as M7 Policy
    participant ME as M6 Measurement
    participant EV as M8 Evidence (optional)
    participant RL as M9 Ledger (read-only)
    participant DE as M11 Decision
    participant RE as M12 Report
    participant AR as M13 Archive
    participant VA as M16 Validation

    O->>P: snapshot(portfolio_id, as_of)
    P-->>O: PositionSnapshot (pinned)
    O->>PE: load(policy_version)
    PE-->>O: PolicyArtifact
    O->>ME: position_state(security_id, as_of)
    ME-->>O: PositionState (facts only)
    O->>ME: book_weights(portfolio_id, as_of)
    ME-->>O: Mapping | NotComputable
    O->>PE: evaluate(state, policy)
    PE-->>O: ConstraintEvaluation (C1-C3, P1, P2)

    alt Evidence package installed
        O->>EV: claims(ctx)
        EV-->>O: EvidenceClaim[]  (no se, no z, no score)
        O->>RL: tier(source, horizon, regime) for each
        RL-->>O: InfluenceTier[] + ledger_snapshot_id
    else Evidence absent
        Note over O,RL: stage skipped; contribution = 0
    end

    O->>DE: decide(ctx, horizon)
    activate DE
    Note right of DE: S1 hard constraints<br/>S2 mandate<br/>S3 lexicographic<br/>S4 bounded modulation<br/>S5 forecast (dormant)<br/>S6 abstention<br/>S7-S9 score/confidence/boundaries
    DE-->>O: (PositionDecision, DecisionTrace)
    deactivate DE

    O->>AR: latest_before(...)
    AR-->>O: prior decision | None
    O->>DE: diff -> ChangeDriver
    O->>RE: assemble(decision, trace)
    RE-->>O: ReportModel
    O->>RE: render(model, template_version)
    RE-->>O: RenderedReport
    O->>AR: append(decision, trace, contract)
    AR-->>O: decision_id
    O->>VA: verify_invariants(decision, trace, model)
    alt invariants hold
        VA-->>O: OK
        O->>O: publish (atomic replace)
    else violation
        VA-->>O: FAIL
        O->>O: ABORT — previous publication untouched
    end
```

## 3 · Decision Engine internal cascade

```mermaid
sequenceDiagram
    autonumber
    participant C as DecisionContext
    participant S1 as Stage 1 Hard constraints
    participant S2 as Stage 2 Mandate
    participant S3 as Stage 3 Lexicographic
    participant S4 as Stage 4 Evidence modulation
    participant S5 as Stage 5 Forecast (dormant)
    participant S6 as Stage 6 Abstention
    participant T as DecisionTrace

    C->>S1: {ADD,HOLD,TRIM,EXIT} x magnitudes
    S1->>T: record eliminations (rule, threshold, actual)
    alt feasible set empty
        S1-->>C: ESCALATE (archived outcome, never a silent HOLD)
    end
    S1->>S2: feasible actions
    alt mandate exists
        S2->>T: mandate_basis
        S2->>S4: action FIXED; only urgency/magnitude open
    else no mandate
        S2->>S3: feasible actions
        loop P1..P6 in policy order
            S3->>S3: score, keep within epsilon
            S3->>T: record eliminations
        end
        S3->>S4: survivor set
    end
    S4->>S4: cap contribution by tier (0 / +-10 / +-20)
    S4->>T: per-claim contribution
    S4->>S5: survivors
    alt DIRECTIONAL-tier forecast exists
        S5->>S5: expected-utility tie-break
    else none (always, to date)
        S5->>T: forecast_contribution = 0.0
    end
    S5->>S6: survivors
    alt >1 survivor and nothing discriminates and no mandate
        S6->>T: abstention_reason
        S6-->>C: HOLD, abstained = true
    else
        S6-->>C: action, magnitude, urgency
    end
```

## 4 · Evaluation loop (asynchronous, the only cycle)

```mermaid
sequenceDiagram
    autonumber
    participant SCH as Scheduler
    participant AR as M13 Archive
    participant MD as M2 Market Data
    participant EVAL as M14 Evaluation
    participant RL as M9 Ledger (writer)

    SCH->>AR: decisions whose contract matures today
    AR-->>SCH: decision[] + EvaluationContract[]
    loop each decision
        SCH->>MD: realised outcome over the contract window (as_of pinned)
        MD-->>SCH: prices, benchmark
        SCH->>EVAL: score per LAYER
        Note right of EVAL: policy -> realised RISK<br/>evidence -> DESCRIPTIVE accuracy<br/>forecast -> realised RETURN
        EVAL-->>SCH: EvaluationResult
        SCH->>EVAL: counterfactuals: do-nothing, POLICY-ONLY, naive
        SCH->>EVAL: terminal-wealth disclosure (mandatory, even if unfavourable)
    end
    SCH->>RL: update descriptive + directional reliability
    RL->>RL: apply tier ladder; AUTO-DEMOTE on decay/staleness/regime break
    Note over RL: writer type only; M11 never holds it
```

## 5 · Failure, resumability, idempotence

| Property | Mechanism |
|---|---|
| Resumable | Per-stage manifest; `--resume RUN_ID` skips stages recorded successful (v1 pattern) |
| Idempotent | Re-running with the same `(snapshot_id, policy_version, code_sha)` produces byte-identical output and a no-op archive append |
| Atomic publication | Temp file → fsync → `os.replace` in-directory; the previous artifact survives any failure |
| Advisory locking | Session-scoped lock prevents concurrent runs corrupting the archive |
| Partial failure | Per-position savepoint; one failed position rolls back alone and is reported in the manifest |

## 6 · Scheduling

| Job | Cadence | Notes |
|---|---|---|
| Ingest + measure | daily, post-close + buffer | never reads the in-progress bar (v1 tripwire lesson) |
| Decide + report | daily | 5 horizons per position |
| Evaluate matured | daily | sweeps ALL contracts — restatement-proof |
| Reliability recompute | quarterly | plus on-demand after a regime break |
| Research runs | ad hoc | separate batch path; never blocks the daily pipeline |
