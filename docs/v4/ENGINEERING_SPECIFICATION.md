# V4 — Engineering Specification (conforming)

**Authority:** the frozen `docs/v4/` set. **Vehicle:** the existing `mip` distribution per `ADR-004`.
Nothing in the frozen architecture is changed here. This document says only *how it lands in this repository*.

## 1 · Interpretation

1. The frozen documents define **logical architecture**.
2. `src/mip/` defines the **physical implementation vehicle**.
3. Separate distributions are deferred until an `ADR-004` trigger fires.
4. Evidence and forecast must remain unable to affect the policy-only path when absent.
5. No scientific or product boundary is weakened by shared packaging.

## 2 · PART 3 — The frozen pipeline, unchanged

The frozen order is authoritative. **Policy loading (stage 2) precedes measurement generation (stage 3).**

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

### 2.1 Why policy loads before measurement, and how the code conforms

`PolicyArtifact` is loaded first because it **pins the version** stamped into every downstream artifact
and supplies `portfolio_value_source` and `participation_rate` — inputs that measurement needs to name
the basis of every figure it emits. Measurement does not *evaluate* policy; it *reads declared bases from*
it. `ConstraintEvaluation` (stage 4) is where policy is applied.

**Conforming rule:** `measurement.generate(...)` accepts a `MeasurementBasis` value object extracted from
`PolicyArtifact` by the orchestrator at stage 2. `measurement/` never imports `policy/` — D3 holds. The
dependency is on *data passed in*, not on the module.

### 2.2 Current modules violating the frozen dependency direction

| Module | Violation | Remediation | Phase |
|---|---|---|---|
| `engine/evidence.py` | Evidence sits on the decision path; would make stage 5 non-skippable | Wrap behind `EvidenceProvider` Protocol; move to `mip_evidence/sources/` | P5 |
| `engine/trim.py` | L7 concern importing L6 and emitting directional labels | Deprecate; excluded from V4 path | P4 |
| `engine/intelligence.py` | Assembler and renderer fused | Split into `report/model.py` + `report/render.py` | P4 |
| `engine/report.py` | Same | Superseded by `report/` (M12) | P4 |
| `models/*` | Preference-bearing thresholds outside `policy/` (D2) | Move to `mip_evidence/sources/`; thresholds become `PolicyArtifact` fields | P5 |
| `cli/decision.py` | Calls the engine directly, bypassing the stage manifest | Route through the M17 orchestrator | P4 |
| `reference/calendar.py` | Imported by both L0 and L1 consumers | Move to `marketdata/` (M2) | P1 |

No current module places measurement before policy — the ordering conflict was in the quarantined draft only.

## 3 · PART 4 — Optionality without a physical split

Required property (frozen P1): **absence, not a flag.** Approximated with the strongest controls available
in one distribution. A boolean feature flag is explicitly insufficient and is not used.

| # | Mechanism | Detail |
|---|---|---|
| 1 | **Isolated package roots** | `src/mip_evidence/`, `src/mip_forecast/` created now, exactly as the frozen structure names them |
| 2 | **Wheel ships `src/mip` only** | `[tool.hatch.build.targets.wheel] packages = ["src/mip"]` — unchanged. Optional roots are dev-tree only until extraction. |
| 3 | **Optional dependency groups** | `[project.optional-dependencies] evidence = [...]`, `forecast = [...]`. Never in `[project].dependencies`. |
| 4 | **Protocol interfaces** | `mip/decision/ports.py` declares `EvidenceProvider`, `ForecastProvider`, `ReliabilityLedgerReader`. `mip/` imports **only** these Protocols. |
| 5 | **Discovery by entry point** | Optional layers register via `importlib.metadata` entry points `mip.evidence` / `mip.forecast`. No entry point ⇒ stage skipped. No import of a concrete class anywhere in `mip/`. |
| 6 | **import-linter** | `forbidden` contracts: `mip` ↛ `mip_evidence`, `mip_forecast`, `mip_proto`, `mip.research*`. |
| 7 | **AST boundary test** | `tests/invariants/test_ast_boundaries.py` |
| 8 | **`zero-signal` CI job** | `rm -rf src/mip_evidence src/mip_forecast` then `pytest -m "not requires_evidence"`. **Absence is physical.** |
| 9 | **Policy-only execution test** | `test_zero_signal.py` runs the full 13-stage pipeline with both roots deleted and asserts a complete `RenderedReport`, `forecast_contribution == 0.0`, evidence contribution `0` |
| 10 | **Minimum-dependency CI job** | installs `[project].dependencies` only — no extras — and runs unit + invariants + acceptance |

**Contract:** the policy-only product must import, execute, test and render **with `mip_evidence` and
`mip_forecast` not present on disk**. Verified by job 8, which deletes them.

## 4 · Determinism, PIT, error model

- **Determinism:** identical `(snapshot_id, policy_version, code_sha)` ⇒ byte-identical output and a no-op
  archive append. No `hash()`, no bare-`set` iteration, no wall clock below `cli/`. `Decimal` throughout;
  never constructed from `float`.
- **PIT:** no read of any row with `effective_date > as_of`. Release gate: `test_pit_poisoning.py`.
- **`NotComputable` is a value, not an exception** (`CalculationResult.value: Decimal | NotComputable`).
  An uncomputable quantity renders as an explicit absence and **never** as a plausible number. This is the
  structural fix for the D-02 defect class.
- **Escalation, never silent HOLD:** an empty feasible set after stage S1 returns `ESCALATE` and is archived.
- **Stage 12 gates stage 13:** verification failure blocks publication; previous artifacts untouched
  (atomic temp → fsync → `os.replace`).

## 5 · PART 9 — Deferred physical extraction plan

Not executed now. Executed on any `ADR-004` trigger T1–T6.

**Stable interfaces required first:** `EvidenceProvider`, `ForecastProvider`, `ReliabilityLedgerReader`
Protocols frozen and versioned; `EvidenceClaim` and `ReliabilityRecord` serialization contracts stable
across two releases; entry-point discovery in production use.

**Boundaries and direction:** `mip_evidence` → depends on `mip` (core, domain). `mip_forecast` → depends
on `mip` and may read `mip_evidence` contracts. **`mip` depends on neither, ever.** `mip_proto` depends on
nothing and is imported only by `tests/acceptance/`.

**Steps:** (1) add `src/mip_evidence/pyproject.toml`, `src/mip_forecast/pyproject.toml`; (2) convert the
repo to a uv workspace; (3) move extras into each distribution's own dependencies; (4) replace the
`rm -rf` in the zero-signal job with the frozen `pip uninstall mip_evidence mip_forecast`; (5) independent
version numbers.

**Effort:** 1–2 engineer-weeks *if* the Protocols and entry points are already in production use; several
times that if extraction is attempted before them. This is the whole reason the seams are built now.

**Tests that must pass before and after, unchanged:** the full unit suite; all eight invariants;
the fourteen acceptance assertions; `tools/phase1/verify_reports.py` exit 0; the determinism diff. The
zero-signal job must pass in *both* forms — `rm -rf` before, `pip uninstall` after — during one overlap release.
