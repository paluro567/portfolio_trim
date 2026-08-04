# SYSTEM ARCHITECTURE V4 — Production Platform

**Status:** design for a multi-year production implementation.
**Contract:** the seven Phase 1 participant packets are **immutable acceptance tests**. Nothing here
modifies the study.
**Inherits:** ARCHITECTURE_V3 (governing) · Amendments 001, 002 (binding) · `verify_reports.py`
(the seed invariant suite).

---

## 1 · The finding that shapes the whole architecture

> ### Every one of the seven frozen reports states `forecast_contribution 0.0` and `evidence contribution 0`.
> ### Therefore the acceptance tests can go green with **no Evidence Layer and no Forecast Layer built at all.**

The frozen contract encodes a system whose Reliability Ledger is **empty**. Reproducing it faithfully
requires only:

```
Measurement (L1)  +  Policy (L2)  +  Decision Engine  +  Report Engine
```

Three consequences, and they drive every decision below:

1. **The empty ledger is a first-class supported state, not a degraded one.** V4 must run correctly and
   indefinitely with zero admitted evidence sources.
2. **The build de-risks front-to-back.** Acceptance tests pass at roughly week 18 of a ~40-week
   programme; everything after that is *additive to a system already proven against the contract*.
3. **The Evidence and Forecast layers are optional subsystems.** Deleting them must leave a working
   platform. That is the V3 principle — *correct at zero signal* — expressed as a build order.

## 2 · Governing principles (inherited, non-negotiable)

| # | Principle | Enforcement in V4 |
|---|---|---|
| P1 | **Correct at zero signal** | `pytest -m zero_signal` runs the full suite with the Evidence and Forecast packages *uninstalled*. Must pass |
| P2 | **No source reports its own precision** | `EvidenceClaim` has no `se`, no `z`, no score field. Enforced by a schema test |
| P3 | **Influence is earned, revocable, default zero** | `ReliabilityLedgerReader` is the only type the Decision Engine can hold. Write access is a separate, unimported type |
| P4 | **Preferences live in exactly one place** | The Policy Artifact. An AST test forbids `mip.policy` imports outside the Policy Engine and Decision Engine |
| P5 | **Every output falsifiable at a declared time** | `EvaluationContract` is a non-nullable field on every archived decision |
| P6 | **PIT integrity** | Every read goes through an `AsOf` context; the price-poisoning test is a release gate |
| P7 | **No composite cardinal score** | `action_strength` exists **only** as a prototype acceptance fixture for Case G. Production emits action + magnitude in natural units |
| P8 | **Derived figures must be recomputable** | The `verify_reports.py` invariant is promoted to a production property test |

## 3 · Layer map

```
┌─────────────────────────────────────────────────────────────────────────┐
│ L0  SUBSTRATE        identity · PIT store · migrations · snapshots       │
│                      backup/restore · reproducibility                    │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐      ┌────────────────┐      ┌──────────────────┐
│ L1 MEASUREMENT│      │ L2 POLICY      │      │ L3 EVIDENCE      │  OPTIONAL
│ facts, zero   │      │ versioned      │      │ claims, no       │  (may be
│ estimation    │      │ human-authored │      │ self-precision   │  absent)
│ error         │      │ config artifact│      └────────┬─────────┘
└───────┬───────┘      └────────┬───────┘               │
        │                       │              ┌────────▼─────────┐
        │                       │              │ L4 RELIABILITY   │  gates L3
        │                       │              │ LEDGER (read-only│
        │                       │              │ to the engine)   │
        │                       │              └────────┬─────────┘
        │                       │                       │
        │                       │              ┌────────▼─────────┐
        │                       │              │ L5 FORECAST      │  DORMANT
        │                       │              │ (never admitted  │  (may be
        │                       │              │  to date)        │  absent)
        │                       │              └────────┬─────────┘
        ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ L6  DECISION ENGINE                                                      │
│     constraints → mandates → lexicographic → bounded modulation →        │
│     abstention → elimination trace         ZERO learned parameters       │
└───────────────────────────────┬─────────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ L7  REPORT ENGINE     semantic model → renderer (separation is mandatory)│
└───────────────────────────────┬─────────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ L8  DECISION ARCHIVE  immutable, contract-stamped ──┐                    │
└──────────────────────────────────────────────────┐  │                    │
                                                   ▼  │                    │
┌─────────────────────────────────────────────────────┴───────────────────┐
│ L9  EVALUATION SUITE  layer-specific tests · external benchmark ·         │
│     terminal-wealth disclosure ──────────────────────► feeds back to L4  │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ L10 GOVERNANCE  tier-cap changes · policy revisions · promotions as      │
│     immutable events requiring the same standard as earning influence    │
└─────────────────────────────────────────────────────────────────────────┘
```

**The only cycle in the system is L8 → L9 → L4.** Everything else is a DAG. That cycle is the
reliability feedback loop and it is deliberately the sole exception.

## 4 · Cross-cutting concerns

| Concern | Mechanism |
|---|---|
| **Point-in-time** | Every repository method takes `as_of: date`. There is no "current" accessor anywhere in L0–L3. Enforced by an interface test |
| **Determinism** | `(policy_version, snapshot_checksum, code_sha)` → byte-identical decision. Verified in CI on every commit |
| **Reproducibility** | Reports pin a `snapshot_id`. Regenerating an archived report re-reads the pinned snapshot, never live data |
| **Auditability** | Every decision carries its `DecisionTrace` including the `ledger_snapshot_id` actually read |
| **Configuration** | Policy, tier caps, ε bands, rubric points are versioned artifacts in `08_frozen/`-style storage. Never fitted, never edited in place |
| **Secrets** | Vendor credentials only; no user PII in the research path |
| **Observability** | Structured events per pipeline stage; the stage manifest pattern already proven in the v1 orchestrator |

## 5 · Part 11 — Critical design review

| # | Risk | Severity | Mitigation in this design |
|---|---|---|---|
| **R1** | **Half-clean seam** — clean outcomes joined to dirty-identity signals. The V2 review's top risk | **High** | `assert_worlds_joinable` promoted to a runtime guard on every research read; identity world stamped on every snapshot; L1 and L3 share one identity spine (`security_id`) |
| **R2** | **Report determinism vs data revision** — prices get revised, so a regenerated report differs from the archived one | **High** | Reports pin `snapshot_id`. Regeneration reads the pinned snapshot. A revision creates a *new* snapshot; it never mutates an old one. Archived reports are immutable artifacts, not views |
| **R3** | **Acceptance-test brittleness** — byte-exact matching on 7 reports breaks on any formatting change | **High** | **Mandatory semantic/rendering split.** Acceptance asserts on the `ReportModel` (semantic), plus one golden-file render test per case. A layout change touches 7 golden files and zero semantic assertions |
| **R4** | **Trace coupling** — the elimination trace is emitted *during* computation; naive design makes the engine untestable | **Medium-high** | `DecisionTrace` is a first-class return value, not a logging side effect. `decide()` returns `(PositionDecision, DecisionTrace)`. No global logger participates |
| **R5** | **Ledger self-authorisation** | **High** | `ReliabilityLedgerReader` is a distinct type with no write methods; the writer type is in a package the engine does not import. Compile-time, not convention |
| **R6** | **Evidence creep** — tier caps raised under pressure, reproducing V1 | **High** | L10 Governance: a cap change is an immutable event requiring the same evidentiary standard as earning influence. `signal_weight_applied` is printed on every report |
| **R7** | **Walk-forward compute** — 500 names × 20y ≈ 120k cells, ~22× today | Medium | Batch/parallel harness designed in P8; snapshots content-addressed to avoid recomputation. **Not on the critical path to acceptance** |
| **R8** | **Maintainability of five layers** | Medium | Modular monolith, not microservices (§ SERVICE_ARCHITECTURE §1). One process, one deployment, service *boundaries* enforced by AST tests rather than by network calls |
| **R9** | **PIT leakage via catalyst data** | Medium | Only dated, source-attributed, PIT-verifiable events are admissible. No forward calendars from non-PIT sources. Inherited from V2.1 |
| **R10** | **Total-HHI class of defect recurring** — figures that look plausible but are uncomputable | Medium | Amendment 002's rule promoted to architecture: **a derived figure may be emitted only if the calculation engine can produce it from persisted inputs.** `NotComputable` is a value the report renders as an explicit absence, never a plausible number |

**R10 is the direct architectural descendant of the D-02 defect** — three impossible HHI values shipped
because a human authored what a calculator should have produced. V4 makes that class of error
structurally impossible.

## 6 · Document set

| Document | Covers |
|---|---|
| **SYSTEM_ARCHITECTURE_V4.md** *(this)* | Principles · layer map · cross-cutting · critical design review |
| `SOFTWARE_DESIGN.md` | Report decomposition · dependency graph · module interfaces |
| `DOMAIN_MODEL.md` | Entities · fields · relationships · ownership · persistence |
| `DATA_MODEL.md` | Datasets · PIT · retention · versioning · physical schema |
| `CALCULATION_ENGINE.md` | The five calculation layers |
| `SERVICE_ARCHITECTURE.md` | Services · APIs · state ownership |
| `EXECUTION_PIPELINE.md` | Runtime pipeline · sequence diagrams |
| `REPOSITORY_STRUCTURE.md` | Packages · tests · CI · prototype/production separation |
| `ACCEPTANCE_TEST_PLAN.md` | The seven reports as executable acceptance criteria |
| `IMPLEMENTATION_ROADMAP.md` | Dependency-ordered phases · effort · risk · component classification |
