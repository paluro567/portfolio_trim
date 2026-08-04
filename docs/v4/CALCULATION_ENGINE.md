# CALCULATION ENGINE

**Part 3 of the V4 brief.** Five layers. Every calculation declares inputs, output, unit, determinism,
cacheability and PIT status. **A calculation that cannot produce a value returns `NotComputable`,
never an approximation.**

---

## Layer 1 — Deterministic arithmetic

Pure functions of `PositionState` + `PolicyArtifact`. No estimation, no history.

| ID | Calculation | Inputs | Output | Unit | Det | Cache | PIT |
|---|---|---|---|---|---|---|---|
| **C1** | Cap excess | `weight_pct`, `hard_cap_pct` | `weight − cap` | pp | ✓ | ✓ | ✓ |
| **C2** | Band excess | `weight_pct`, `target_pct`, `band_pp` | `weight − (target + band)` | pp | ✓ | ✓ | ✓ |
| **C3** | Target deviation | `weight_pct`, `target_pct` | `target − weight` | pp | ✓ | ✓ | ✓ |
| **C4** | Action magnitude | excess pp, `portfolio_value` | `excess/100 × value` | USD | ✓ | ✓ | ✓ |
| **C5** | Position as % of ADV | `position_value`, `adv_20d` | `value/adv × 100` | pct | ✓ | ✓ | ✓ |
| **C6** | **Days to trade** | trade value, `adv_20d`, **`participation_rate`** | `value / (adv × rate)` | days | ✓ | ✓ | ✓ |
| **C7** | Gain/loss realised | magnitude$, `cost_basis`, `position_value` | `mag × (1 − basis/value)` | USD | ✓ | ✓ | ✓ |
| **C8** | Sector exposure after | `sector_pct`, excess pp | `sector − excess` | pct | ✓ | ✓ | ✓ |
| **C9** | **Portfolio HHI** | **all book weights** | `Σ wᵢ²` or **`NotComputable`** | ratio | ✓ | ✓ | ✓ |
| **C9s** | Own concentration | `weight_pct` | `w²` | ratio | ✓ | ✓ | ✓ |
| **C10** | Lot seasoning days | lot open dates, `as_of` | days to long-term | days | ✓ | ✓ | ✓ |
| **C11** | Gains budget remaining | `gains_budget`, `gains_used` | difference | USD | ✓ | ✓ | ✓ |
| **C12** | Weight vs position value | `weight_pct`, `portfolio_value` | implied value | USD | ✓ | ✓ | ✓ |

**C6 must name its rate.** `participation_rate` is a required `PolicyArtifact` field precisely because
Amendment 002 D-01 was caused by an undocumented convention. `CalculationResult.inputs` records the
rate used.

**C9 is the reference implementation of `NotComputable`.** When book weights are absent it returns
`NotComputable("requires all book weights; N of M available")`. The renderer emits an explicit absence
and falls back to C9s. **A plausible number is never produced.**

## Layer 2 — Policy calculations

| ID | Calculation | Inputs | Output | Det | Cache | PIT |
|---|---|---|---|---|---|---|
| **P1** | Hard-constraint feasibility | action set, C6, restricted list, wash-sale window | feasible actions | ✓ | ✓ | ✓ |
| **P2** | Mandate detection | C1, C2, C3, thresholds | `mandate: CAP\|BAND\|MIN\|None` | ✓ | ✓ | ✓ |
| **P3** | Mandated magnitude | mandate, C4 | pp + USD | ✓ | ✓ | ✓ |
| **P4** | Objective scoring | surviving actions, objective | per-objective score | ✓ | ✓ | ✓ |
| **P5** | Lexicographic survivor set | P4, `objective_order`, ε bands | reduced action set + elimination reasons | ✓ | ✓ | ✓ |
| **P6** | Boundary inversion | contribution, threshold | value at which the action flips | ✓ | ✗ | ✓ |
| **P7** | Tax-consequence eval | C7, C10, C11 | budget overshoot, staging option | ✓ | ✓ | ✓ |

**P6 is the hardest calculation in the system.** It inverts the decision function per contribution to
produce S05. It is not cacheable because it depends on the whole surviving action set.

## Layer 3 — Evidence aggregation *(optional package)*

| ID | Calculation | Inputs | Output | Det | Cache | PIT |
|---|---|---|---|---|---|---|
| **E1** | Admissibility filter | claim, horizon, tier | admissible? | ✓ | ✓ | ✓ |
| **E2** | Tier cap application | claim, tier, `tier_caps` | bounded contribution | ✓ | ✓ | ✓ |
| **E3** | Redundancy estimation | realised claim history | correlation matrix | ✓ | ✓ | ✓ |
| **E4** | Conflict detection | admissible claims | conflict set — **never averaged** | ✓ | ✓ | ✓ |
| **E5** | Contribution accumulation | E2, E3 | signed contribution | ✓ | ✓ | ✓ |

**Absent by design:** any inverse-variance weighting, any `se` recovery, any z-to-score mapping.
`se ≡ |effect/z|` is deleted permanently.

## Layer 4 — Decision reasoning

| ID | Calculation | Inputs | Output | Det | Cache | PIT |
|---|---|---|---|---|---|---|
| **D1** | Stage cascade | P1, P2, P5, E5, forecast? | action, magnitude, urgency | ✓ | ✗ | ✓ |
| **D2** | Abstention determination | survivor set, discriminating evidence, mandate | abstain? + reason | ✓ | ✗ | ✓ |
| **D3** | Elimination trace assembly | every stage's removals | `EliminationEntry[]` | ✓ | ✗ | ✓ |
| **D4** | Confidence profile | ledger, `dominant_basis` | 6 components + ceiling | ✓ | ✗ | ✓ |
| **D5** | Change diff | prior archived decision, current | `changes[]` + `ChangeDriver` | ✓ | ✗ | ✓ |
| **D6** | Horizon reconciliation | 5 horizon decisions | term structure + `DifferenceCause` | ✓ | ✗ | ✓ |

**D4 hard rule:** `recommendation_confidence ≤ historical_reliability`.
**D6 hard rule:** an unattributable cross-horizon difference is suppressed and equalised to the longer
horizon. `DifferenceCause` has no `NOISE` member.

## Layer 5 — Narrative generation

**Templates only. No free text generation, no language model, anywhere in the decision path.**

| ID | Generator | Inputs | Output | Det |
|---|---|---|---|---|
| **N1** | Basis line | `dominant_basis`, C1/C2/C3 | one line | ✓ |
| **N2** | Boundary statements | P6 | ordered statements | ✓ |
| **N3** | Elimination lines | D3 | one line per rejected action | ✓ |
| **N4** | Abstention statement | D2 | **fixed text** | ✓ |
| **N5** | Confidence statement | D4 | basis-typed statement | ✓ |
| **N6** | What-changed prose | D5 | attributed diff | ✓ |
| **N7** | Terminal-wealth line | archive history | realised vs do-nothing **or the fixed "not available" text** | ✓ |

Every generator is a pure function from structured input to string. **Byte-identical output for
identical input is a test.**

## Determinism and caching summary

| Layer | Deterministic | Cacheable | Cache key |
|---|---|---|---|
| L1 | All | All | `(calc_id, input_hash)` |
| L2 | All | All except P6 | `(calc_id, input_hash, policy_version)` |
| L3 | All | All | `+ source_version, ledger_snapshot_id` |
| L4 | All | **None** — depends on the whole context | — |
| L5 | All | All | `(generator, model_hash, template_version)` |

**The entire engine is deterministic.** `(snapshot_id, policy_version, ledger_snapshot_id, code_sha)`
→ byte-identical decision, trace and report. This is asserted in CI on every commit and is what makes
the seven frozen reports usable as acceptance tests at all.
