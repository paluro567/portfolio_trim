# Prototype Engineering Assessment — Minimum Software for the Seven Reports

**Scope:** the minimum software required to generate the seven participant-facing V3 reports.
**Sources:** `ARCHITECTURE_V3_BLUEPRINT.md` · `PHASE1_OPERATIONS_PACKAGE.md` ·
`PHASE1_PROTOCOL_AMENDMENT_001.md` · the frozen artifacts in `docs/phase1/`.
**No study material is modified by this document.**

---

## FINDING 0 — Three arithmetic defects in the frozen reports *(report only; not fixed here)*

Running the calculation layer against the frozen case facts surfaced three internal inconsistencies.
**These are defect reports requiring an Ops-lead decision, not engineering changes.**

| ID | Case | Field | Stated | Computed from case facts | Severity |
|---|---|---|---|---|---|
| **D-01** | **A** | "full exit is **16.2 days** of average dollar volume" | 16.2 days | **0.016 days** ($3.41M ÷ $210M ADV) — off by ~1000× | **BLOCKING** |
| **D-02** | A | Portfolio HHI "0.071 → 0.048" | 0.071 | **Impossible.** A 28.4% position alone contributes 0.0807, so total HHI ≥ 0.081 | Moderate |
| **D-03** | B | "A move to target as % of ADV: 3.1%" | 3.1% | **0.52%** ($228k move ÷ $44M ADV) | Minor |

### Why D-01 blocks

Case A's elimination trace reads *"EXIT eliminated — liquidity: a full exit is 16.2 days of ADV, above
the 2-day limit."* But the same packet's baseline states the position is **1.6% of ADV**. A participant
who reads both sees a direct contradiction, and liquidity is precisely the kind of constraint the
external author is likely to list for Case A — so a participant *engaging* the constraint correctly
(Q2 credit) could be reasoning from a figure the packet contradicts.

Both baseline lines are mutually consistent ($210M ADV → 1.6% of ADV). **Only the report's 16.2-day
claim conflicts.** The two candidate corrections are not equivalent:

- **Change the baseline ADV to ~$210k** → 16.2 days holds, but "position as % of ADV: 1.6%" becomes
  1,624% and must also change.
- **Change the report claim to ~0.02 days** → the liquidity limit no longer eliminates EXIT, which
  **changes the elimination trace substantively** and alters what Case A tests.

**That is a study-design decision and is explicitly outside my authority.** Escalated as
cancellation-condition candidate 9; it requires Amendment 002 before freeze.

D-02 and D-03 are lower severity: HHI is unverifiable by a participant (they never see all 24
positions), and D-03 supports no derived claim in Case B's report.

**These defects are the strongest argument in this document for the recommendation below.**

---

## 1 · Data structures required

Strictly a **presentation subset** of the V3 `PositionDecision`. The study reports carry none of
`signal_weight_applied`, `defensible_without_forecast`, `evaluation_contract`, the six-component
`ConfidenceProfile`, or the horizon term structure.

```python
@dataclass(frozen=True)
class Policy:                     # 1 instance: Meridian
    portfolio_value: Decimal      # 12_000_000
    n_positions: int              # 24
    hard_cap_pct: Decimal         # 15.0
    core_target_pct: Decimal      # 5.0
    band_pp: Decimal              # 2.0
    sector_cap_pct: Decimal       # 30.0
    liquidity_limit_days: Decimal # 2.0
    gains_budget: Decimal         # 180_000
    gains_used: Decimal           # 120_000

@dataclass(frozen=True)
class PositionState:              # 7 instances (one per case)
    name: str; sector_label: str
    weight_pct: Decimal; value: Decimal
    target_pct: Decimal | None
    cost_basis: Decimal; unrealised: Decimal
    lots_long_pct: Decimal; lots_short_pct: Decimal
    holding_period: str
    adv_20d: Decimal
    sector_exposure_pct: Decimal
    correlations: tuple[Decimal, ...]
    prior_weight_pct: Decimal     # for "what changed"

@dataclass(frozen=True)
class EvidenceClaim:
    text: str
    direction: Literal["REDUCTION", "RETENTION"]
    tier: Literal["CONTEXT"]      # every claim in every study report
    contribution: int             # always 0

@dataclass(frozen=True)
class EliminationEntry:
    action: Literal["ADD","HOLD","TRIM","EXIT"]
    rule: str; threshold: str | None; actual: str | None

@dataclass(frozen=True)
class DatedCatalyst:              # Case B only
    kind: str; days_until: int; source: str; confirmed: bool

@dataclass(frozen=True)
class ReportModel:
    case_id: str
    action: str; mandated: bool
    magnitude_pp: Decimal | None; magnitude_dollars: Decimal | None
    basis: str
    boundary_conditions: tuple[str, ...]
    policy_lines: tuple[tuple[str,str], ...]
    tax_detail: str | None
    portfolio_impact: tuple[tuple[str,str], ...]
    what_changed: str
    evidence: tuple[EvidenceClaim, ...]
    abstention: str | None
    confidence_statement: str
    eliminations: tuple[EliminationEntry, ...]
    catalyst: DatedCatalyst | None
    action_strength: int | None    # Case G ONLY
    strength_decomposition: tuple[tuple[str,int], ...] | None
    terminal_wealth: str           # FIXED constant per Amendment A-004
```

**11 types, ~45 fields.** No engine, no ledger, no combiner.

## 2 · Inputs that must exist

| Input | Count | Status |
|---|---|---|
| `Policy` (Meridian) | 1 | Authored, frozen |
| `PositionState` fixtures | 7 | Authored, frozen — **and carry defects D-01…D-03** |
| Evidence claim text | 13 across 6 reports | Authored, frozen |
| Elimination entries | 19 across 6 reports | Authored, frozen |
| Abstention statements | 2 (D, E) | Authored, frozen |
| Catalyst | 1 (B) | Authored, frozen |
| Score + decomposition | 1 (G) | Authored, frozen |
| Terminal-wealth text | 1 constant | **Fixed by A-004** |

**Every input already exists as prose in the frozen packets.** Converting them to structured fixtures is
re-typing, and re-typing frozen, reviewed, about-to-be-hashed text is a transcription-risk operation
with no offsetting benefit for Phase 1.

## 3 · Sections that can be hard-coded

**For the prototype: all narrative sections.** Each is authored text with no algorithmic derivation:

terminal-wealth disclosure *(constant, mandated by A-004)* · every evidence claim *(all CONTEXT tier,
all contributing 0)* · every elimination trace *(the real engine derives these; the prototype cannot,
because there is no engine)* · both abstention statements · every confidence statement · the Case B
catalyst · every "what changed" line · the Case G score and its decomposition.

## 4 · Sections that require calculation

Nine derived quantities, all pure functions of `PositionState` + `Policy`:

| # | Quantity | Formula | Appears in |
|---|---|---|---|
| C1 | Excess over cap (pp) | `weight − hard_cap` | A, C |
| C2 | Excess over band ceiling (pp) | `weight − (target + band)` | G |
| C3 | Deviation from target (pp) | `target − weight` | B, D, E |
| C4 | Magnitude ($) | `excess_pp/100 × portfolio_value` | A, C, G |
| C5 | Position as % of ADV | `position_value / adv × 100` | A, B, D |
| C6 | **Days to exit** | `position_value / adv` | **A — D-01** |
| C7 | Gain realised on a trim | `magnitude$ × (1 − basis/value)` | C, G |
| C8 | Sector exposure after action | `sector_pct − excess_pp` | A, C, G |
| C9 | **Portfolio HHI** | `Σ wᵢ²` — **needs all 24 weights, which do not exist** | **A, G — D-02** |

**C9 is not computable from the study fixtures at all.** Only one position per case is specified; the
other 23 do not exist. The HHI values in the reports are therefore **necessarily authored**, and D-02
shows one of them is internally impossible.

## 5 · Which calculations can be stubbed without affecting study validity

| Calc | Stub-safe? | Reasoning |
|---|---|---|
| C1, C2, C3 | **Yes** | Participants can verify these by subtraction. Verified correct in all 6 reports |
| C4 | **Yes** | Verified correct (A, C, G within rounding) |
| C5 | **Yes** | Verified correct in A and D; **D-03 in B** |
| **C6** | **NO** | **D-01. Load-bearing in Case A's elimination trace and participant-verifiable** |
| C7 | **Yes** | Verified correct in C ($390k) and G ($196k) |
| C8 | **Yes** | Not participant-verifiable |
| **C9** | **Uncomputable** | **D-02. Not derivable from the fixtures; not participant-verifiable, so lower severity** |

> **The general rule: a derived figure may be stubbed if and only if a participant cannot check it
> against another figure in the same packet.** C6 fails that test — which is exactly how D-01 arose and
> why stubbing is not free.

## 6 · Smallest repository capable of generating the seven reports

### ▶ RECOMMENDED — Option 1: **do not build a generator**

The seven reports **already exist**, authored, QC'd, and awaiting hash. The Ops Package requires
*"static PDF or printed reports… no application, no interactivity"* and warns that *"building anything
interactive would confound format with product."* Cancellation condition 6 —
*"reports cannot be produced as static one-pagers within 5 hours"* — is **already recorded as
SATISFIED**.

Building a generator now would consume hours from a **30-hour cap with explicitly zero slack**, to
regenerate frozen artifacts, while introducing divergence risk between generated output and reviewed
text.

**Build instead a ~90-line verification script and a render step:**

```
tools/phase1/
├── case_facts.py        # 7 PositionState + 1 Policy — facts only, no prose  (~70 lines)
├── verify_reports.py    # recomputes C1–C8, asserts against the frozen text  (~90 lines)
└── render_pdf.sh        # pandoc: markdown → one-page PDF ×7                 (~10 lines)
```

**That is the minimum software with actual value: it validates the frozen artifacts rather than
recreating them.** It is also the tool that found D-01, D-02 and D-03 — a generator would have
*emitted* those numbers, not caught them.

### Option 2 — a full generator *(the literal answer, NOT recommended for Phase 1)*

```
tools/phase1_reportgen/
├── models.py            # the 11 dataclasses above                      ~120 lines
├── policy.py            # Meridian Policy constant                       ~20
├── cases/
│   ├── case_a.py … case_g.py    # 6 fixtures (F has no report)          ~90 each = 540
├── calc.py              # C1–C8; C9 raises NotComputable                 ~80
├── render.py            # ReportModel → the frozen monospace layout      ~150
├── templates/report.txt.j2                                              ~90
├── tests/test_parity.py # generated output == frozen text, byte-for-byte ~60
└── build.py             # emit 6 markdown + 6 PDF                        ~40
                                                              TOTAL ≈ 1,100 lines
```

**`test_parity.py` is the load-bearing file** — without byte-parity against the frozen text, the
generator becomes a second, divergent source of truth for material that is about to be hashed.

## 7 · Implementation plan, ordered by engineering dependency

### Option 1 *(recommended)*

| # | Step | Depends on | Effort |
|---|---|---|---|
| 1 | `case_facts.py` — transcribe the 7 baselines *(facts only, no prose)* | frozen packets | 0.5 h |
| 2 | `verify_reports.py` — C1–C8, assert vs frozen text | 1 | 0.75 h |
| 3 | **Run it; file defects** | 2 | **DONE — D-01…D-03 above** |
| 4 | **Ops-lead decision on D-01** *(blocking; needs Amendment 002)* | 3 | *not engineering* |
| 5 | `render_pdf.sh` — pandoc, one page per case | 4 | 0.5 h |
| 6 | Visual check: 7 PDFs, one page each, page 2 separable | 5 | 0.25 h |
| | **Total** | | **≈ 2 h** |

### Option 2 *(if a generator is mandated)*

models → policy → calc → 6 fixtures → templates → render → **parity test** → build.
Parity must pass **before** any PDF is produced. **≈ 10–12 h.**

## 8 · Effort estimate against the frozen cap

| Option | Engineering | Fits the cap? |
|---|---|---|
| **Option 1** | **≈ 2 h** | **Yes** — absorbed by the already-spent "Materials 5 h" line |
| Option 2 | ≈ 10–12 h | **No.** Ops §9.4 states *"There is no slack"* at 30 h. A 10–12 h build would require either expanding the cap (prohibited) or deleting another line item (prohibited) |

**Option 2 cannot be funded without breaching the frozen budget.**

## 9 · Production survival

| Component | Survives to production? | Why |
|---|---|---|
| `Policy` dataclass | **YES** | Becomes the V3 **S3 Policy Artifact** — versioned, human-authored, externally reviewed |
| `PositionState` dataclass | **YES** | Becomes V3 **S2 Measurement** output |
| `calc.py` C1–C8 | **YES** | These are Layer-1 policy arithmetic — the only layer that works at zero signal |
| C9 (HHI) | **YES, rewritten** | Needs the full book; trivial in production, impossible in fixtures |
| Report layout / section order | **YES** | The V3 report order is architectural, not prototype |
| `EliminationEntry` | **YES** | Becomes the Decision Engine's `EliminationTrace` — the "why not" differentiator |
| `EvidenceClaim` | **PARTIAL** | Shape survives; the hard-coded CONTEXT tier and contribution-0 are stubs for the Reliability Ledger |
| `ReportModel` | **PARTIAL** | A presentation subset of `PositionDecision`; production adds `signal_weight_applied`, `defensible_without_forecast`, `evaluation_contract`, the 6-component confidence profile, the horizon term structure |
| 6 case fixtures | **NO — prototype only** | Fictional composites, deliberately disposable |
| Hard-coded narrative text | **NO — prototype only** | Production derives every one of these from the engine |
| `action_strength` (Case G) | **NO — deliberately** | The Trim Score is **deleted** in V3. It exists solely as the study's exploratory arm |
| `terminal_wealth` constant | **NO** | Production computes it from the decision archive; A-004 fixes it to "not available" precisely because no archive exists |
| `verify_reports.py` | **YES, in spirit** | Becomes the production invariant test: *every derived figure must be recomputable from position state and policy* |
| Templates | **PARTIAL** | Section order survives; monospace study formatting does not |

---

## Recommendation

1. **Build nothing for report generation.** The seven reports exist and are frozen.
2. **Build the ~2-hour verification script.** It is the only software with net value, it fits the cap,
   and it has already earned its cost by surfacing three defects.
3. **Escalate D-01 to the Ops lead before freeze.** Case A's liquidity claim contradicts its own
   baseline by three orders of magnitude, and the correction options are not equivalent — one of them
   changes what Case A tests. That is a study-design decision, and it needs **Amendment 002**.
4. **Add the 2-hour build to the Day 1–2 "Materials" line** — already allocated, already spent, no cap
   impact.
5. **Reject Option 2 for Phase 1.** Revisit it at Phase 2, when the Policy Artifact and Measurement
   layer are being built for real and a generator becomes production code rather than a study prop.
