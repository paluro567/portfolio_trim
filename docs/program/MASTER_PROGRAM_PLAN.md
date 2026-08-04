# MASTER PROGRAM PLAN

**Frozen decisions 1–7 are inputs, not subjects of review.** This plan converts them into an executable
program. No redesign, no new sources, no early purchase.

---

## 1 · Track reconciliation

| Track | Content | May begin | Gated by | Cost profile |
|---|---|---|---|---|
| **A** | Phase 1 product-validation study | **IMMEDIATELY** — blocked only on humans | none | 30 h · $650 |
| **B0** | Data restoration + automated backup | **IMMEDIATELY** | none — see §2 | ~25 h · $120 |
| **B1** | V4 documentation, interface sketches, repo inventory | **IMMEDIATELY** (reversible prep only) | none | ~15 h · $0 |
| **B2** | V4 production engineering P0–P9 | **ONLY AFTER G1 PASS** | G1 | ~40 wk · $0 |
| **C** | V5 descriptive reliability | **In parallel, low cost, after B0** | B0 only | ~8 wk · $0 |
| **D** | V6 MDE / instrument calibration | **In parallel, low cost, after B0** | B0 only | ~6 wk · $0 |
| **E** | V7 clean-data directional validation | **ONLY AFTER G6** | G4 ∧ G5 ∧ G6 | ~16 wk · ≤$2,000 |

### Why C and D are not gated on Phase 1

**Phase 1 and V6 test orthogonal propositions.**

- **Phase 1 asks:** does the *explanation* change a real decision?
- **V6 asks:** can the *instrument* detect anything at all?

A product can fail Phase 1 while remaining scientifically viable in a different form, or pass Phase 1
while being scientifically empty. Running them in parallel is information-maximising and the results
are jointly interpretable:

| | **V6 pass** | **V6 fail** |
|---|---|---|
| **G1 PASS** | Full programme proceeds | Product is real; prediction is not. Redefine as an exposure-management platform |
| **G1 FAIL** | The explanation is not wanted, but the instrument works. A *different* product may exist | **Stop.** Neither the product nor the science is viable |

**Constraint:** C and D are capped at *research scope* — free data, scratchpad drivers, no `src/`
production code, no migrations. This preserves the rule against a large implementation proceeding on an
unvalidated thesis while still buying the information.

### Why B0 (restoration + backup) precedes every gate

It is **disaster recovery for a realised loss**, not product construction. The production database was
destroyed; a PIT fundamentals snapshot and the prediction archive are permanently gone. B0 is also a
hard prerequisite for C and D, which are not product-gated. Withholding it would gate *science* on a
*product* question.

## 2 · Dependency graph

```
        ┌──────────────────────────────────────────────────────────┐
        │ IMMEDIATE — no gate                                       │
        │  A  Phase 1 (blocked on humans only)                      │
        │  B0 Restoration + backup                                  │
        │  B1 V4 docs / interfaces / repo inventory                 │
        └───────┬──────────────────────────────┬───────────────────┘
                │                              │
                ▼                              ▼
        ┌───────────────┐            ┌──────────────────────────────┐
        │  G1 Phase 1   │            │ PARALLEL, LOW COST (after B0) │
        │  PASS/AMB/FAIL│            │  C  V5 descriptive            │
        └───┬───────┬───┘            │  D  V6 MDE sweep              │
            │       │                └──────┬────────────┬──────────┘
       PASS │       │ FAIL                  │            │
            ▼       ▼                       ▼            ▼
      ┌─────────┐  STOP                ┌────────┐   ┌────────┐
      │ G2  V4  │  (90-day pause,      │ G3     │   │ G5 MDE │
      │ B2 P0-P9│   publish negative)  │ CONTEXT│   │        │
      └─────────┘                      └───┬────┘   └───┬────┘
                                           ▼            │
                                      ┌─────────┐       │
                                      │ G4      │◄──────┘  (episode floor)
                                      │ ADVISORY│
                                      └────┬────┘
                                           │  G4 ∧ G5
                                           ▼
                                      ┌──────────────┐
                                      │ G6 PURCHASE  │  ≤ $2,000
                                      └──────┬───────┘
                                             ▼
                                      ┌──────────────┐
                                      │ E  V7        │
                                      │ G7 DIRECTIONAL│
                                      └──────────────┘
```

## 3 · Reconciliation findings requiring explicit record

| # | Finding | Consequence |
|---|---|---|
| **F1** | **G4 (ADVISORY) requires an episode floor**, which V5 supplies. The directional MDE (G5) is a *directional*-promotion input, not a descriptive one | G3 and G4 are reachable from V5 alone. **Frozen decision 5 requires G4 ∧ G5 before purchase regardless**, so sequencing is unaffected. Recorded as an interpretation, not a change |
| **F2** | Phase 1 uses static PDFs and needs **no data layer** | B0 is not a Phase 1 dependency; the two are independent |
| **F3** | V5 and V6 both need the restored substrate | B0 is the true program-critical path, ahead of everything except human recruitment |
| **F4** | The binding blocker is unchanged | **No external moderator. Ops §9.5 condition 1 forbids the architect from moderating and provides no fallback** |

## 4 · Standing prohibitions

| Prohibited until | Activity |
|---|---|
| G1 PASS | Any V4 production code, migration, or service |
| G3 | Any evidence source contributing above zero |
| G4 ∧ G5 | **Any commercial data purchase** |
| G7 | Any forecast-layer work |
| Never | Reinstating the composite score · `se ≡ \|effect/z\|` · `volume × agreement` confidence · declared correlation priors |
| Never | Answering a G1 FAIL by rewriting the report and re-testing |

## 5 · Cash and engineering commitment ladder

| Stage | Cash | Engineering | Reversible? |
|---|---|---|---|
| A + B0 + B1 | $770 | ~70 h | Yes |
| C + D | $0 | ~14 wk | Yes |
| B2 (after G1) | $0 | ~40 wk | Partially |
| E (after G6) | ≤$2,000 | ~16 wk | No |

**Total commitment before any irreversible spend: $770 and ~70 hours.**
