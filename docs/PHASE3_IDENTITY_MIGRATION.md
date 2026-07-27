# Phase 3 Design — Migration from Legacy `instrument_id` to Native `security_id`

**Status:** architecture migration design only — no production code, no model,
weight, or Trim Score changes. **Addresses:** R1/R4 of
[PHASE2_ARCHITECTURE_REVIEW.md](PHASE2_ARCHITECTURE_REVIEW.md) (the half-clean
pipeline). **Depends on:** Phase 1 (delivered) + Phase 2 clean price substrate
([PHASE2_DESIGN.md](PHASE2_DESIGN.md)).

> **The one question.** *How do we migrate from legacy `instrument_id`-based
> feature computation to a fully `security_id`-native research architecture while
> preserving research continuity, reproducibility, and scientific integrity?*
> Governing rule: **never compare survivor-biased signals against
> survivorship-clean outcomes.** Prefer the simplest migration that guarantees
> that. The result must not require another identity migration for a decade.

---

## Executive Recommendation

**Parallel-path, never in-place.** Do **not** re-key the legacy tables. Build a
`security_id`-native feature path that reads Phase 2's clean `security_price_daily`
and writes a new `security_id`-keyed feature store governed by the *same*
`feature_definitions` (same versioned definitions, new data lineage). Run it
**alongside** the legacy path, prove **two-track parity** (computation-equivalence
+ explained data-divergence) on the survivor overlap via the tested
`instrument_security_map` bridge, migrate feature families in **dependency waves**
(price-only first, fundamentals/earnings last), then flip production in a single
logged, reversible promotion and retire the legacy *computation* — while keeping
legacy *data* permanently as a reproducibility archive.

This is the simplest design that satisfies the governing rule, because it never
mutates an existing research artifact and makes every legacy↔native comparison an
explicit, versioned, auditable event.

Sequencing insight that shrinks the job: **macro and market-wide features are
already identity-neutral** (`macro_observations`, `feature_store_market_daily`
carry no `instrument_id`), so rate/macro families migrate the moment prices are
native — no bridge needed for them. The genuine work is concentrated in the
price-, fundamentals-, and earnings-keyed families.

---

## Stage 1 — Current Dependency Graph

Verified against `src/mip/domain/models.py`.

### Legacy-only (`instrument_id`-keyed)
- `symbol_history`, `daily_prices`, `corporate_actions`
- `company_fundamentals` (forward-only, survivor-biased), `earnings_observations`
  (append-only PIT-honest, but legacy identity + survivor universe)
- **`feature_store_daily`** ← the primary migration target
- `predictions` → `prediction_outcomes` (derived)
- Portfolio analytics: `transactions`, `lots`, `position_snapshots`

### Identity-neutral (no migration needed)
- `macro_series` / `macro_observations` (market-wide)
- `feature_store_market_daily` (market-wide regime/curve features)
- `trading_calendar`, `sectors`, `industries`, `ingestion_runs`,
  `feature_definitions`, `data_quality_issues`, `data_revisions`

### Already `security_id`-native
- Phase 1: `security_master`, `security_identifier_history`,
  `security_lifecycle_event`, `delisting_event`, `universe_definition`,
  `universe_membership`, `historical_classification`
- Phase 2 (designed): `security_price_daily`, `security_corporate_action`,
  `security_market_data_daily`, `delisting_return`, benchmarks,
  `research_snapshot` / `research_observation`

### Dependency graph (data → features → signals → outcomes)

```
LEGACY WORLD (survivor-biased, instrument_id)      NATIVE WORLD (clean, security_id)
──────────────────────────────────────────        ─────────────────────────────────
yfinance ─► daily_prices ─┐                         Norgate ─► security_price_daily ─┐
corp_actions ─────────────┤                         Sharadar ─► security_market_data ┤
company_fundamentals ─────┤                         corp_action(sec_id) ─────────────┤
earnings_observations ────┤                                                          │
            ▼             │                                     ▼                    │
      feature_store_daily (instrument_id) ◄══ bridge ══►  research_feature_daily* (security_id)
            ▼             │        instrument_security_map        ▼                  │
      9 models (registry.required_data_sources → LEGACY)   (same feature_definitions)│
            ▼                                                     ▼                  │
      predictions (instrument_id) ─► prediction_outcomes   research_observation (security_id)
            ▼                                                  [survivorship-clean outcomes]
      Trim Score (production)                                  research_snapshot (immutable)

macro_observations / feature_store_market_daily  ── identity-neutral, shared by both ──
(* research_feature_daily = the new native feature store proposed by this design)
```

**The fault line** is the `bridge` row: today a study crosses it implicitly.
Phase 3 makes every crossing explicit, versioned, and eventually unnecessary
(both feature and outcome live natively).

---

## Stage 2 — Target Architecture

| Subsystem | Primary key | Source of truth | Versioning | PIT guarantee | Research role | Production role |
|---|---|---|---|---|---|---|
| Prices | `(security_id, price_date)` | `security_price_daily` (Norgate) | `data_version` | close known EOD | canonical | canonical (after flip) |
| Corporate actions | `(security_id, action_type, ex_date)` | `security_corporate_action` | `data_version` | ex-date PIT | canonical | canonical |
| Market data (cap/shares/$vol) | `(security_id, obs_date)` | `security_market_data_daily` (Sharadar) | `data_version` | as-of | canonical | canonical |
| Fundamentals | `(security_id, as_of)` | **new** PIT fundamentals (Sharadar SF1) | `data_version` | as-of report knowable | canonical | canonical |
| Earnings | `(security_id, earnings_date, observed_at)` | **re-keyed** earnings on security_id | append-only | known-when | canonical | canonical |
| **Feature store** | `(security_id, feature_date, feature_id)` | **`research_feature_daily`** (new) | `feature_definitions.version` + `data_version` | inputs ≤ feature_date | canonical | canonical (after flip) |
| Market/macro features | `(feature_date, feature_id)` | `feature_store_market_daily` (unchanged) | feature version | ≤ date | canonical | canonical |
| Signals / models | keyed via feature store | `registry.py` (`required_data_sources` retargeted) | `ExperimentSpec.version` | inherited | canonical | canonical |
| Predictions | `(security_id, …)` (re-keyed) | new `prediction` on security_id | immutable | as_of | evidence | canonical (after flip) |
| Outcomes | `(prediction_id)` | `research_observation` / re-keyed outcomes | derived | delist-aware | canonical | canonical |
| Universe | `(universe_definition_id, security_id, membership_date)` | Phase 1 | definition version | as-of | canonical | canonical |
| Portfolio | `security_id` (re-keyed, low priority) | transactions/lots | — | — | analytics | production |

**Become canonical:** the Phase 1 + Phase 2 `security_id` tables, plus the new
`research_feature_daily`, PIT fundamentals, and re-keyed earnings/predictions.

**Become compatibility layers (retained, read-only):** legacy `daily_prices`,
`corporate_actions`, `company_fundamentals`, `earnings_observations`,
`feature_store_daily`, legacy `predictions`/`prediction_outcomes`,
`symbol_history` — kept immutable to reproduce pre-migration studies, reachable
only through the `instrument_security_map` bridge.

**Stay as-is (identity-neutral):** macro tables, `feature_store_market_daily`,
calendar, `feature_definitions`, DQ ledger.

---

## Stage 3 — Migration Principles (non-negotiable)

1. **No research result silently changes.** Every result carries
   `(identity_world, feature_version, data_version, universe_version,
   snapshot_checksum)`. A number can only change when one of those changes.
2. **No feature redefinition without versioning.** Same computation on new data =
   new `data_version`; changed computation = new `feature_definitions.version`.
   Legacy values are never overwritten.
3. **Historical experiments remain reproducible forever.** Legacy feature/prediction
   *data* is immutable and never deleted, even after the legacy *computation* is
   retired.
4. **Legacy and native coexist during migration.** Two feature stores, dual
   compute, until parity + stability are proven.
5. **Every legacy↔native join is explicit** through the tested, PIT-correct
   `instrument_security_map`. No implicit symbol joins, ever.
6. **No survivorship-clean outcome is evaluated against survivor-biased features.**
   Enforced by a hard guardrail that refuses `feature_store_daily ⋈
   research_observation`.
7. **Identity is resolved as-of.** A native feature row binds to `security_id` over
   the as-of interval; ticker reuse/rename never leaks across the bridge.
8. **Production flip is discrete, logged, and reversible** — a recorded promotion
   decision, never a gradual or silent cutover.
9. **Parity is proven, not assumed** — computation-equivalence AND explained
   data-divergence, before any family is trusted natively (Stage 6).
10. **Divergence is characterized, not suppressed.** Where native ≠ legacy, the
    difference must be *explained* (vendor/adjustment/survivorship) and bounded —
    an unexplained difference blocks promotion.

---

## Stage 4 — Migration Strategy (phased)

Runs **per feature-family wave** (Stage 5), not big-bang. Each phase below is a
gate for a wave.

### Phase A — Compatibility bridge
- **Objective:** elevate `instrument_security_map` to a first-class, PIT-correct,
  tested bridge (validity intervals, as-of resolution, DQ checks for many-to-one /
  temporal overlap / ticker reuse). Install the guardrail (principle 6).
- **Depends on:** Phase 1 identity (done).
- **Acceptance:** every legacy `instrument_id` with data resolves to exactly one
  `security_id` per as-of; ambiguities quarantined; guardrail blocks illegal joins
  in tests.
- **Rollback:** bridge is additive/read-only — drop the map, no data lost.
- **Research impact:** none yet (enables safe comparison). **Production:** none.

### Phase B — Native price substrate + dual computation (price-only wave)
- **Objective:** stand up `research_feature_daily` (security_id) and compute the
  price-only families from `security_price_daily`, in parallel with legacy.
- **Depends on:** Phase 2 `security_price_daily`; Phase A.
- **Acceptance:** native features produced for the ~500-name universe over full
  history incl. delisted names; same `feature_definitions` version as legacy.
- **Rollback:** stop the native job; legacy untouched.
- **Research:** additive (new native features available for shadow studies).
  **Production:** none (still on legacy).

### Phase C — Feature parity validation
- **Objective:** prove two-track parity per family (Stage 6).
- **Depends on:** Phase B.
- **Acceptance:** computation-equivalence exact on identical inputs; data-divergence
  on survivor overlap fully attributed and within thresholds.
- **Rollback:** family stays legacy-canonical if parity fails; fix and re-run.
- **Research:** unlocks trusting native features for that family. **Production:** none.

### Phase D — Shadow research (native)
- **Objective:** re-run representative studies natively and compare *conclusions*
  (not just values) to legacy; record native runs in the execution-level
  experiment-run store.
- **Depends on:** Phase C; the `experiment_run` store (review correction #3).
- **Acceptance:** native and legacy conclusions agree where data is comparable;
  where they differ, the difference is explained by survivorship/vendor (the
  expected direction — e.g. edge shrinks when losers are included).
- **Rollback:** none needed (shadow only).
- **Research:** native becomes the *preferred* research substrate for migrated
  families. **Production:** none.

### Phase E — Native promotion (per family)
- **Objective:** production Trim Score reads native features for migrated families;
  retarget `registry.required_data_sources` from legacy to native.
- **Depends on:** Phase D + production-stability window.
- **Acceptance:** logged promotion decision; live scores reproducible from native
  lineage; a stability window with no unexplained drift.
- **Rollback:** flip `required_data_sources` back to legacy (both stores live).
- **Research:** native is canonical. **Production:** now on clean identity/data.

### Phase F — Legacy retirement (per family, then global)
- **Objective:** retire legacy *computation* and survivor ingestion for migrated
  families; retain legacy *data* as archive.
- **Depends on:** all families through Phase E + research/production stability.
- **Acceptance:** Stage 7 evidence satisfied.
- **Rollback:** legacy data retained, so re-enabling a legacy path is possible
  during a defined grace period.
- **Research/Production:** fully native; legacy read-only archive only.

---

## Stage 5 — Feature Migration (per family)

| Family | Current dep | Native dep | Complexity | Scientific risk | Validation | Wave |
|---|---|---|---|---|---|---|
| **Momentum exhaustion** | prices | `security_price_daily` | Low | Low | comp-equiv + divergence | **1 (immediate)** |
| **Relative strength** | prices | `security_price_daily` + benchmarks | Low | Low | same + benchmark parity | **1** |
| **Sector rotation** | prices | prices + `historical_classification` (PIT sector) + sector benchmarks | Low-Med | Med (PIT sector correctness) | + sector-map parity | **1** |
| **Macro regime** | prices + macro | prices + macro (**identity-neutral**) | Low | Low | comp-equiv (macro unchanged) | **1** |
| **Interest-rate sensitivity** | prices + macro | prices + macro (**identity-neutral**) | Low | Low | comp-equiv | **1** |
| **Confidence** (meta) | model agreement | inherits migrated inputs | Low | Med (composition of migrated) | end-to-end after its inputs | **follows wave 1** |
| **Valuation** | prices + fundamentals | prices + **new PIT fundamentals (SF1)** | **High** | **High** (legacy fundamentals survivor/forward-only) | needs infra first | **2 (blocked on PIT fundamentals)** |
| **Earnings behavior** | prices + earnings | prices + **re-keyed PIT earnings** | Med-High | Med-High | needs earnings re-source | **2** |
| **Historical analogues** *(REJECTED/shadow)* | full stack | full stack | High | Low priority (rejected) | only if revived | **3 (last / optional)** |
| **Conditional probability** *(REJECTED/shadow)* | full stack | full stack | High | Low priority (rejected) | only if revived | **3 (last / optional)** |

**Can move immediately onto `security_price_daily`:** momentum, relative
strength, sector rotation, macro regime, interest-rate sensitivity (wave 1).
Confidence follows automatically once its inputs are native.

**Require additional infrastructure first:** valuation (PIT fundamentals from
Sharadar SF1 — not the legacy survivor-biased `company_fundamentals`) and
earnings behavior (PIT earnings re-keyed to `security_id`). The two rejected
shadow models migrate last, or never unless revived.

---

## Stage 6 — Validation Strategy (two-track parity)

Feature equivalence cannot be exact across worlds because the underlying prices
differ (survivor yfinance vs clean Norgate). Honest validation is therefore two
separate tests:

1. **Computation equivalence (proves the code is right).** Feed the *identical*
   price/input vector through both the legacy and native code paths; values must
   match to numerical tolerance. Any mismatch is a migration bug.
2. **Data-divergence characterization (proves differences are explained).** On the
   *survivor overlap* (securities present in both worlds), measure native−legacy
   feature differences and attribute each to a cause: dividend/split adjustment
   methodology, vendor price differences, or survivorship. Differences must be
   bounded and directionally sensible; **unexplained divergence blocks promotion.**

Plus the standard gates:
- **Prediction equivalence:** on the survivor overlap, native-fed scores track
  legacy within the divergence envelope.
- **Research reproducibility:** re-running a study on the same
  `(feature_version, data_version, snapshot_checksum)` reproduces it exactly.
- **Historical replay:** replay a past date's universe+features natively; matches
  the recorded snapshot.
- **Walk-forward consistency:** native walk-forward produces the same *structure*
  of results; edge changes only in the expected (survivorship) direction.
- **Statistical drift:** monitor native-vs-legacy feature distributions; a drift
  gate flags unexplained shifts.
- **Performance & data lineage:** native jobs meet runtime budgets; every native
  value traces to `ingestion_run_id` + `data_version` + source.
- **Acceptance thresholds / rollback criteria:** per-family numeric tolerances
  (comp-equiv exact; divergence within a pre-registered band). Breach ⇒ family
  stays legacy-canonical and the flip rolls back.

**Scientific-continuity guarantee:** because every result is stamped with its
identity world and versions, and the guardrail forbids mixed joins, it is
*impossible* to silently compare survivor-biased features with clean outcomes —
the exact failure this migration exists to prevent.

---

## Stage 7 — Legacy Retirement Plan

**Retire (remove) once all waves clear Phase E + stability windows:**
- Legacy feature **computation jobs** and survivor-biased (yfinance) ingestion
  *for research purposes*.
- Dual-write/dual-compute scaffolding.
- `registry.required_data_sources` pointers to legacy stores.

**Retain permanently (compatibility layer, read-only):**
- Legacy **data**: `feature_store_daily`, `daily_prices`, `corporate_actions`,
  `company_fundamentals`, `earnings_observations`, `symbol_history` — the only way
  to reproduce pre-migration studies.
- Legacy `predictions` / `prediction_outcomes` — immutable evidence.
- `instrument_security_map` — required to interpret archived legacy data forever.

**Required evidence to retire:** every production feature family through Phase E;
two-track parity passed; a defined production-stability window with no unexplained
drift; a research-stability window in which native reproduces or explains all
active studies; the execution-level experiment-run store populated with native
runs.

---

## Stage 8 — Migration Risk Register

| # | Risk | Severity | Likelihood | Scientific impact | Eng. impact | Mitigation |
|---|---|---|---|---|---|---|
| M1 | Bridge mis-maps (many-to-one / ticker reuse) → features attached to wrong `security_id` | **High** | Med | High | Med | Phase A tested PIT bridge + DQ checks; block on ambiguity (quarantine) |
| M2 | Silent conclusion change mistaken for a bug (or vice versa) from vendor/survivorship divergence | **High** | High | High | Low | Two-track parity (Stage 6); pre-registered divergence bands; stamp every result |
| M3 | Reproducibility lost if legacy data deleted | **High** | Low | High | Low | Never delete legacy data; retain as read-only archive (Stage 7) |
| M4 | Researchers run mixed legacy/native studies during coexistence | **High** | Med | High | Low | Hard guardrail (principle 6); mandatory `identity_world` stamp; CLI refuses mixed joins |
| M5 | Valuation/earnings families blocked on PIT fundamentals/earnings infra, stalling migration | Med | High | Med | Med | Wave the migration; ship price families first; don't gate them on fundamentals |
| M6 | Dual-compute cost/complexity during coexistence | Med | Med | Low | Med | Time-box the dual window per family; automate parity; retire promptly |
| M7 | Undetected feature drift post-flip | Med | Med | Med | Low | Statistical drift gate; stability window before retirement |
| M8 | Portfolio analytics still on `instrument_id` after research migrates | Low | High | Low | Med | Migrate portfolio last (production analytics, not research integrity) |
| M9 | Registry `required_data_sources` retarget applied unevenly across families | Med | Med | Med | Low | Make source-world a per-family field; conformance test asserts no family mixes worlds |

All High-risk items (M1–M4) are mitigated by Phase A + the two-track parity gate +
the guardrail + the no-delete archive rule — none requires new modeling or Trim
Score changes.

---

## Deliverable summary

- **Executive recommendation:** parallel-path (never in-place), same versioned
  feature definitions on clean data, two-track parity, dependency-wave family
  migration, logged reversible flip, permanent legacy-data archive.
- **Dependency graph / target architecture / roadmap / validation / retirement /
  risks:** Stages 1–8 above.
- **Scientific-continuity guarantee:** identity-world + version stamping plus the
  mixed-join guardrail make it structurally impossible to compare survivor-biased
  features against clean outcomes.

**Final constraint honored:** this modernizes identity only in service of research
consistency; it changes no model, weight, or Trim Score logic; it prefers the
simplest design that guarantees the integrity rule; and by retaining legacy data
as a permanent archive while making `security_id` canonical, it is built to
outlast a decade of research without a second identity migration.
