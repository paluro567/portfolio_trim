# ACCEPTANCE TEST PLAN

**Part 8 of the V4 brief.** The seven frozen participant packets are the contract. **A future
implementation passes only if it reproduces them.**

Source of truth: `docs/phase1/01_participant/case_{A..G}.md` — read-only, Amendment-controlled.

---

## 1 · Two-level assertion (mandatory)

| Level | Asserts on | Breaks when | Files touched by a layout change |
|---|---|---|---|
| **Semantic** | `ReportModel` — actions, magnitudes, units, traces, tiers, contributions | **logic** changes | 0 |
| **Golden render** | Byte comparison against the frozen packet | **layout** changes | 7 |

Semantic assertions are the real contract. Golden files stop unnoticed presentation drift. **Never
collapse the two** — a single byte-exact test would make every legitimate formatting change look like
a logic regression (risk R3).

## 2 · Per-case acceptance specification

Common inputs to every case: `PolicyArtifact` = Meridian (portfolio $12,000,000 · 24 positions · cap
15.0% · target 5.0% · band ±2.0pp · sector cap 30.0% · liquidity 2 days at **participation_rate 1.0** ·
gains budget $180,000, $120,000 used) · empty `ReliabilityLedger` (all sources CONTEXT) · empty
`DecisionArchive` for terminal wealth.

### CASE A — NOVA · above hard cap

| | |
|---|---|
| **Inputs** | weight 28.4% · value $3,410,000 · basis $830,000 · unrealised $2,580,000 LT · ADV $210,000,000 · sector 34.1% · corr 0.71/0.66 · prior weight 26.1% |
| **Calculations** | C1 = 13.4pp · C4 = $1,608,000 → "~$1,610,000" · C5 = 1.62% → "1.6%" · **C6 = 0.0162 days (participation 1.0)** · C8 34.1→30.6% · **C9 = NotComputable** · C9s 0.0807→0.0225 |
| **Recommendation** | `TRIM`, mandated, 13.4pp / ~$1,610,000, basis = concentration |
| **Trace** | EXIT eliminated — **cap mandate does not require exit** *(Amendment 002 D-01: NOT liquidity)* · HOLD, ADD eliminated — cap mandate |
| **Sections** | S01–S06, S10, S11, S13, S14, S15, S16, S17 |
| **Verification** | C6 must NOT trigger a liquidity elimination · C9 must return `NotComputable` · S16 = fixed "not available" · S17 = 0.0 |

### CASE B — HELIX · below target, event risk

| | |
|---|---|
| **Inputs** | weight 3.1% · value $372,000 · basis $410,000 · unrealised −$38,000 ST · ADV $44,000,000 · **confirmed earnings T+4** · prior 3.4% |
| **Calculations** | C3 = 1.9pp below · **C5c move-to-target = 0.5% of ADV** *(D-03)* · C6 move = 0.0052 days |
| **Recommendation** | `HOLD`, not mandated, no magnitude |
| **Trace** | ADD eliminated — within band, no mandate; dated event inside near horizons · TRIM, EXIT — no breach |
| **Sections** | S01, S02, S04–S07, S11, S13, S14, S15, S16, S17 |
| **Verification** | catalyst admissible only if `announcement_date ≤ as_of` · **no directional view attached to the event** |

### CASE C — ATLAS · appreciated winner, tax tension

| | |
|---|---|
| **Inputs** | weight 19.2% · value $2,300,000 · basis $520,000 · unrealised $1,780,000 (+342%) · 22% of lots ST at 9 months · ADV $95,000,000 · sector 26.8% · prior 17.9% |
| **Calculations** | C1 = 4.2pp · C4 = $504,000 · **C7 = $390,100 gain** · C10 = 3 months to LT · C11 = $60,000 remaining · C9s 0.0369→0.0225 |
| **Recommendation** | `TRIM`, mandated, 4.2pp / ~$504,000 |
| **Trace** | EXIT — cap mandate does not require exit · HOLD — cap mandate · **short-term lots eliminated from the sell set** |
| **Sections** | + S08 TAX DETAIL |
| **Verification** | C7 ÷ C11 overshoot ≈ 6.5× must be stated, not hidden · lot seasoning surfaced |

### CASE D — VERTEX · loser within policy · **designed no-action**

| | |
|---|---|
| **Inputs** | weight 2.8% · value $336,000 · basis $600,000 · unrealised −$264,000 LT · ADV $18,000,000 · no events · prior 2.9% |
| **Calculations** | C3 = 0.2pp below (inside band) · C5 full exit = 1.87% → "1.9%" · **no limit breached** |
| **Recommendation** | `HOLD`, **abstained = true** |
| **Trace** | TRIM, EXIT, ADD all eliminated — no breach, no mandate |
| **Sections** | + S09 TAX NOTE, **S12 ABSTENTION** |
| **Verification** | **abstention must fire** · loss-harvest availability stated as a fact, never as a recommendation · no directional language anywhere |

### CASE E — ORION · conflicting evidence · **abstention probe**

| | |
|---|---|
| **Inputs** | weight 8.1% · value $972,000 · basis $700,000 · unrealised $272,000 LT · ADV $61,000,000 · sector 19.4% · prior 8.3% · **4 CONTEXT claims, 2 for reduction, 2 for retention** |
| **Calculations** | C3 = 0.1pp above (inside band) · all limits inside |
| **Recommendation** | `HOLD`, **abstained = true** |
| **Trace** | all actions feasible, none mandated, nothing discriminates |
| **Sections** | **S13 rendered as `EVIDENCE — SHOWN UNRECONCILED`** + S12 ABSTENTION |
| **Verification** | **conflicting claims MUST NOT be averaged into a net score** · E4 must detect the conflict · abstention statement present · every claim contributes 0 |

### CASE F — PINNACLE · sham · **no report**

| | |
|---|---|
| **Inputs** | weight 6.2% · value $744,000 · ADV $27,000,000 · no events |
| **Expected** | **No report is generated.** Baseline only |
| **Verification** | the pipeline must support a *no-report* outcome without error. This is the acceptance test for stage-13 suppression |

### CASE G — CASCADE · band breach · **score arm, production-dead**

| | |
|---|---|
| **Inputs** | weight 11.2% · value $1,340,000 · basis $820,000 · unrealised $524,000 LT · ADV $38,000,000 · sector 14.6% · prior 10.6% |
| **Calculations** | C2 band ceiling 7.0%, excess 4.2pp · C4 = $504,000 → "~$503,000" · C7 = $195,600 → "$196,000" · C9s 0.0125→0.0049 |
| **Recommendation** | `TRIM`, 4.2pp to the band ceiling. **Cap NOT breached** |
| **Sections** | + `ACTION STRENGTH 68/100` with decomposition |
| **Verification** | **`action_strength` may be produced ONLY by `mip_proto.legacy.legacy_action_strength`.** An AST test asserts `mip/` never imports it. This acceptance test asserts a feature that must never ship |

## 3 · Global verification criteria

Every case must satisfy all of:

| # | Criterion |
|---|---|
| V1 | `forecast_contribution == 0.0` on every report-bearing case |
| V2 | Every evidence claim is CONTEXT tier and contributes exactly 0 |
| V3 | S16 terminal wealth is the fixed "not available" text — **no invented empirical figure** (A-004) |
| V4 | Every derived figure is reproducible from `CalculationResult.inputs` |
| V5 | No emitted figure lacks a unit |
| V6 | No total portfolio HHI unless all book weights are persisted (A-002/D-02) |
| V7 | The elimination trace is a returned value, not a log artifact |
| V8 | Determinism: identical `(snapshot_id, policy_version, ledger_snapshot_id, code_sha)` → byte-identical output |
| V9 | The whole suite passes with `mip_evidence` and `mip_forecast` **uninstalled** |
| V10 | `tools/phase1/verify_reports.py` exits 0 against the generated artifacts |

**V9 is the deepest criterion.** It proves the production system reproduces the frozen contract using
only Layers 1, 2, 6 and 7 — which is what makes the roadmap front-loadable.

## 4 · Negative controls

A passing suite proves nothing unless it can fail. Mirroring the Amendment 002 negative control:

| # | Injected defect | Must fail |
|---|---|---|
| N1 | Case A liquidity restored to 16.2 days | C6 assertion |
| N2 | Total HHI emitted with partial book weights | V6 + `NotComputable` assertion |
| N3 | Case B move-to-target set to 3.1% | C5c assertion |
| N4 | An evidence claim given a non-zero contribution at CONTEXT tier | V2 + tier-cap assertion |
| N5 | Terminal wealth given a numeric value | V3 assertion |
| N6 | `mip/decision` importing `LedgerWriter` | AST boundary test |
| N7 | Case E claims averaged into one score | E4 conflict-preservation assertion |

**CI runs the negative controls on a schedule against a mutated build.** A suite that has never failed
has never been shown to work.
