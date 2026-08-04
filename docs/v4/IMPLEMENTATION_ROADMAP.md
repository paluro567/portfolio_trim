# IMPLEMENTATION ROADMAP

**Parts 9 and 10 of the V4 brief.** Production engineering only. Strictly dependency-ordered.
Effort in engineer-weeks for one experienced engineer.

---

## 1 · The shape of the plan

> **Acceptance tests go green at the end of P4 — roughly week 18 of a ~40-week programme — with no
> Evidence Layer and no Forecast Layer built.**

Everything from P5 onward is additive to a system already proven against the frozen contract. That is
the direct consequence of every report stating `forecast_contribution 0.0` and `evidence contribution 0`.

## 2 · Phases

### P0 · Substrate — 5 weeks · risk MEDIUM

Identity spine (`security_id`, never ticker) · migrations with a `REFERENCE_TABLES` head assertion ·
`AsOf` context · content-addressed snapshot store · **automated offsite backup + a scheduled restore
drill**.
**Tests:** migration up/down · snapshot checksum stability · **restore drill** · PIT interface reflection.
**Done when:** a full DB can be destroyed and restored byte-identically from backup.
> Backup is P0, not an afterthought. The v1 platform permanently lost a PIT fundamentals snapshot and
> its prediction archive. That loss is unrecoverable and must not recur.

### P1 · Market data + portfolio — 5 weeks · risk MEDIUM-HIGH

Price/action/market-snapshot ingestion with revision handling and the completed-session guard ·
transaction ledger · FIFO lot engine (Decimal, replay-deterministic, oversell-rejecting) · position
snapshots with byte-identical rebuild.
**Tests:** price-poisoning · revision materiality · lot replay determinism · rebuild idempotence.
**Risk:** the v1 adjusted-close tripwire storm — mitigate with field-specific materiality tolerances and
the raw-shift guard already designed.
**Done when:** a full portfolio rebuild from the ledger is byte-identical twice running.

### P2 · Measurement (L1) + calculation engine — 4 weeks · risk LOW

C1–C12 · `CalculationResult` · **`NotComputable` as a first-class value** · unit tagging on every result.
**Tests:** one unit test per calculation with worked examples from the frozen packets · **C9 returns
`NotComputable` with partial book weights** · every result carries a unit.
**Done when:** `tools/phase1/verify_reports.py` passes using the production engine instead of its own
arithmetic.

### P3 · Policy Engine (L2) — 3 weeks · risk LOW-MEDIUM

Versioned `PolicyArtifact` (semver, never edited) with **explicit `participation_rate`** · P1–P7 ·
constraint evaluation.
**Tests:** policy versioning immutability · AST guard that only policy/ and decision/ import prefs ·
mandate detection across all seven fixtures.
**Risk:** the policy document itself is a *human* deliverable and remains the V3 blocker. Engineering
can ship the loader before the document exists.

### P4 · Decision Engine (L6) + Report Engine (L7) — 6 weeks · risk HIGH

Eleven-stage cascade · elimination trace as a **returned value** · abstention · boundary inversion (P6)
· `ReportModel`/`Renderer` split · templates N1–N7.
**Tests:** **THE SEVEN ACCEPTANCE TESTS** · all seven negative controls · determinism · zero-signal
(packages uninstalled).
**Risk drivers:** P6 boundary inversion is the hardest calculation in the system; the semantic/golden
split must be right from the first commit or retrofitting is painful.
> **✅ COMPLETION CRITERION: all fourteen acceptance assertions green, `verify_reports.py` exits 0, and
> the suite passes with `mip_evidence` and `mip_forecast` uninstalled.**
> **At this point the production system reproduces the frozen contract.**

### P5 · Decision Archive (L8) — 3 weeks · risk LOW

Immutable append-only store · `EvaluationContract` stamped at creation · `latest_before` · supersession.
**Tests:** immutability · contract non-nullable · future-archive invisibility (PIT).
**Done when:** `what_changed` populates from real archived history and terminal wealth still renders
"not available" on an empty archive.

### P6 · Evaluation Suite (L9) — 4 weeks · risk MEDIUM

Layer-specific scoring (policy→risk · evidence→descriptive · forecast→return) · three counterfactuals
incl. **policy-only** · **terminal-wealth disclosure, mandatory and non-optional** · abstention scoring
· decision-level FDR ledger.
**Tests:** counterfactual arithmetic · terminal wealth reported even when unfavourable · restatement-proof
re-evaluation.

### P7 · Reliability Ledger (L4) — 4 weeks · risk MEDIUM-HIGH

Descriptive **and** directional reliability, measured separately · four-tier ladder · automatic demotion
on decay/staleness/regime break · reader/writer type split · conditioned on horizon (mandatory) and
regime (shrunk) **only**.
**Tests:** **self-authorisation impossible** (AST + type) · demotion fires on staleness · no
sector/cap/vol conditioning.
**Risk:** this is the platform's central innovation and the easiest to get subtly wrong. Ship it empty
and keep it empty until P8 produces something to score.

### P8 · Evidence Layer (L3) — 6 weeks · risk MEDIUM

`EvidenceSource` Protocol · **first source only** · catalyst store (PIT-verified dated events) ·
conflict preservation (E4) · claim rendering, both sides.
**Tests:** `EvidenceClaim` has no `se`/`z`/`score` field · new source enters at SHADOW automatically ·
**conflicting claims are never averaged** · uninstalling the package leaves everything green.
**Constraint:** one source at a time. Each earns its tier or stays at SHADOW.

### P9 · Governance (L10) — 2 weeks · risk LOW

Immutable governance events for tier-cap changes, policy revisions, promotions — same evidentiary
standard to raise a cap as to earn influence.
**Rationale:** without it, the tier caps are a YAML file anyone can edit, which is how V2.1 becomes V1.

### P10 · Forecast Layer (L5) — DEFERRED INDEFINITELY · risk N/A

**Not scheduled.** No source has ever reached DIRECTIONAL tier. Build only if P7's ledger promotes one.

### Totals

| | Weeks | Cumulative |
|---|---|---|
| P0–P4 — **contract reproduced** | **23** | **23** |
| P5–P7 — archive, evaluation, ledger | 11 | 34 |
| P8–P9 — evidence, governance | 8 | 42 |
| P10 — forecast | deferred | — |

## 3 · Dependency graph

```
P0 Substrate
 ├─> P1 Market data + Portfolio
 │    └─> P2 Measurement + Calc
 │         ├─> P3 Policy
 │         │    └─> P4 Decision + Report  ✅ ACCEPTANCE GREEN
 │         │         └─> P5 Archive
 │         │              ├─> P6 Evaluation
 │         │              │    └─> P7 Reliability Ledger
 │         │              │         ├─> P8 Evidence
 │         │              │         └─> P10 Forecast (deferred)
 │         │              └─> P9 Governance
```

**P4 has no dependency on P7 or P8.** That is the whole point.

## 4 · Part 10 — component classification

| Component | Class | Why |
|---|---|---|
| Substrate: identity, migrations, snapshots, backup | **PRODUCTION** | Foundation; nothing works without it |
| Market data, corporate actions, revision handling | **PRODUCTION** | Required by L1 |
| Portfolio ledger, FIFO lots, position snapshots | **PRODUCTION** | Layer 1's inputs |
| Measurement (L1) | **PRODUCTION** | The only layer that works at zero signal |
| Calculation engine C1–C12, P1–P7 | **PRODUCTION** | Deterministic core |
| `NotComputable` | **PRODUCTION** | Structural fix for the D-02 defect class |
| Policy Engine + `PolicyArtifact` | **PRODUCTION** | The sole home for preferences |
| Decision Engine (11 stages, trace, abstention) | **PRODUCTION** | The central deliverable |
| Report Engine (assembler + renderer, split) | **PRODUCTION** | The contract's output |
| Decision Archive + `EvaluationContract` | **PRODUCTION** | Falsifiability record |
| Evaluation Suite + terminal-wealth disclosure | **PRODUCTION** | Prevents self-grading |
| Reliability Ledger | **PRODUCTION** | The platform's central innovation |
| Governance | **PRODUCTION** | Stops the architecture being edited into V1 |
| Evidence Layer | **PRODUCTION, optional** | Must remain uninstallable |
| `EvidenceSource` implementations | **EXPERIMENTAL** | Each starts at SHADOW; most will stay there |
| Forecast Layer | **DEFERRED** | No source has cleared DIRECTIONAL. May never be built |
| `legacy_action_strength()` | **PROTOTYPE-ONLY** | Case G acceptance only. AST-forbidden in `mip/` |
| Study fixtures (7 cases) | **PROTOTYPE-ONLY** | Fictional composites, deliberately disposable |
| `tools/phase1/verify_reports.py` | **PROTOTYPE → PRODUCTION in spirit** | Its 81 checks are ported into `tests/invariants/`; the file itself stays frozen |
| Trim score / composite 0–100 output | **LEGACY — deleted** | Removed by ARCHITECTURE_V3. Never reinstated |
| `se ≡ \|effect/z\|` weighting | **LEGACY — deleted** | Spearman −1.000. Never reinstated |
| `confidence = volume × agreement` | **LEGACY — deleted** | Both terms measured to carry no information |
| Declared correlation priors | **LEGACY — deleted** | Wrong in both directions |
| `valuation`, `historical_analogues`, CPE | **LEGACY** | Removed from the decision path; data retained |

## 5 · Risk register

| # | Risk | Phase | Sev | Mitigation |
|---|---|---|---|---|
| 1 | P6 boundary inversion harder than scoped | P4 | High | Prototype it first; it is the only genuinely novel algorithm |
| 2 | Acceptance brittleness from byte-matching | P4 | High | Semantic/golden split mandatory from commit one |
| 3 | Price-revision tripwire storm recurs | P1 | High | Field-specific materiality + raw-shift guard, both already designed in v1 |
| 4 | Evidence creep raises tier caps informally | P8 | High | P9 Governance precedes broad evidence work |
| 5 | Ledger conditioned on too many dimensions | P7 | Medium | Horizon mandatory, regime shrunk, nothing else — the CPE lesson |
| 6 | Policy document never written | P3 | **High, non-engineering** | Loader ships without it; the artifact remains a human blocker |
| 7 | Walk-forward compute at 22× | P6 | Medium | Content-addressed snapshots; batch path separate from the daily pipeline |
| 8 | Backup not exercised | P0 | High | Restore drill is a P0 completion criterion, not a runbook line |
