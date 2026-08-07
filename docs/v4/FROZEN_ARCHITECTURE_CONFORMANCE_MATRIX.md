# Frozen Architecture — Conformance Matrix

**Purpose:** every frozen requirement, where it lands in the existing repository, and how conformance is proven.
Updated in the same commit as any change to `src/`.

## 1 · Pipeline stages (frozen order, unchanged)

| Stage | Frozen | Module | Physical location | Conformance test |
|---|---|---|---|---|
| 1 | portfolio snapshot | M5 | `mip/portfolio/` | `test_rebuild_idempotence` |
| 2 | **policy loading** | M7 | `mip/policy/` | `test_policy_before_measurement` |
| 3 | measurement generation | M6 | `mip/measurement/` | `test_measurement_no_preferences` (D3) |
| 4 | constraint evaluation | M7 | `mip/policy/` | `test_constraint_eval_fixtures` |
| 5 | evidence generation | M8? | `mip_evidence/sources/` | `test_zero_signal` (skipped when absent) |
| 6 | reliability read | M9 | `mip_evidence/reliability/` | `test_no_self_authorisation` |
| 7 | forecast | M10? | `mip_forecast/` | `test_zero_signal` |
| 8 | decision generation | M11 | `mip/decision/` | 14 acceptance assertions |
| 9 | horizon reconciliation | M11 | `mip/decision/` | `test_horizon_term_structure` |
| 10 | report generation | M12 | `mip/report/` | 7 semantic + 7 golden |
| 11 | archive | M13 | `mip/archive/` | `test_archive_immutable` |
| 12 | verification | M16 | `tests/invariants/` | non-zero exit blocks publication |
| 13 | publication | M17 | `mip/cli/` | `test_atomic_replace` |

**Stage 2 precedes stage 3.** `measurement/` receives a `MeasurementBasis` extracted from `PolicyArtifact` by the orchestrator; it never imports `policy/`.

## 2 · Frozen principles

| # | Principle | Enforcement | Status |
|---|---|---|---|
| P1 | Correct at zero signal — optional layers skippable **by absence** | `zero-signal` CI job deletes both roots (ADR-004 C-1) | approximation recorded |
| P2 | `EvidenceClaim` carries no `se`/`z`/`score`/`weight`/`confidence` | schema test | direct |
| P4 | Only `policy/` and `decision/` import preferences | AST test D2 | direct |
| — | `NotComputable` is a value, not an exception | `test_notcomputable_is_value` | direct |
| — | Escalation, never a silent HOLD | `test_escalate_on_empty_feasible_set` | direct |
| — | Single writer per entity | AST import guards | direct |
| — | Assembler/renderer separated | semantic vs golden split | direct |
| — | Determinism, PIT | `test_determinism`, `test_pit_poisoning` (release gate) | direct |

## 3 · Deviations from the frozen structure — complete list

| # | Frozen | Actual (this phase) | Reason | Reverts when |
|---|---|---|---|---|
| **V-1** | `mip_evidence`, `mip_forecast` are separately installable distributions; `zero-signal` runs `pip uninstall` | One distribution; roots exist under `src/`; `zero-signal` runs `rm -rf` | ADR-004 — migration disproportionate before Phase 1 | any ADR-004 trigger T1–T6 |

**V-1 is the only deviation.** Every other frozen element — pipeline order, module numbers M1–M17, layer numbers L0–L10, phase numbers P0–P6, domain object names, subsystem responsibilities, dependency rules, evidence boundaries, scientific restrictions — is reproduced exactly.

## 4 · Scientific restrictions carried forward (frozen, unchanged)

| Restriction | Source | Enforcement |
|---|---|---|
| No calibrated probabilities in reports | `PRODUCT_EVIDENCE_BOUNDARY.md` | renderer deny-list |
| No directional recommendations on the V4 path | same | `engine/trim.py` deprecated |
| No synthetic confidence | same | `EvidenceClaim` schema test (P2) |
| Evidence at SHADOW/CONTEXT only | same | tier caps 0 / ±10 / ±20; ledger refuses promotion |
| `se = abs(effect/z_raw)` must never return | A-2026-006 | `test_evidence_recovered_se.py` (17 tests) |
| `dispersion` is OBSERVED, never `effect/z` | frozen `DOMAIN_MODEL.md` | schema + review |
| Reliability conditioned on horizon + regime only | frozen | ledger schema |
