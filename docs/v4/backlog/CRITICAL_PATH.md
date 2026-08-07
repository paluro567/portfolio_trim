# V4 — Critical Path (Part 2)

## 1 · Dependency graph (P0 → P4)

```
P0-01 ─┬─ P0-02 ── P0-03
       ├─ P0-04 ─┬─ P0-05 ─┐
       │         ├─ P0-06 ─┼─ P0-07
       │         └─────────┘
       ├─ P0-08
       ├─ P0-11
       └─ P0-09 ─┬─ P0-10 ── P0-14
                 ├─ P0-12 ── P0-13
                 ├─ P1-01 ─┬─ P1-02
                 │         ├─ P1-03
                 │         ├─ P1-04 ── P1-05 ─┐
                 │         └─ P1-06 ── P1-07  │
                 └─ P1-08 ── P1-09 ── P1-10 ──┼─ P1-11
                                              └─ P1-12
                                     P1-10 ── P2-01 ─┬─ P2-02 ─┐
                                                     ├─ P2-03 ─┼─ P2-05
                                                     └─ P2-04 ─┘
                                                          │
                                                     P2-06 ─┬─ P2-07
                                                            ├─ P2-08
                                                            ├─ P2-09
                                                            └─ P2-10
                                                          │
                                                     P3-01 ─┬─ P3-07
                                                            └─ P3-02 ── P3-03
                                                                  └──── P3-04 ── P3-05 ── P3-06
                                                                                    │
                                     P4-01 ── P4-02 ─┬─ P4-11
                                                     └─ P4-03 ── P4-04 ── P4-05 ── P4-06 ── P4-07 ── P4-08 ── P4-09
                                                                                                          │
                                                                                                     P4-10 ─┬─ P4-12
                                                                                                            └─ P4-13 ─┬─ P4-17
                                                                                                                      └─ P4-14 ─┬─ P4-18 ── P4-21
                                                                                                                                ├─ P4-19
                                                                                                                                └─ P4-15 ─┬─ P4-16
                                                                                                                                          └─ P4-20
```

## 2 · First executable task

**P0-01 — commit the working tree (74 dirty paths at HEAD `1b2aec9f`) and tag `pre-P0`.**
Nothing else can start: no rollback point exists, no manifest can be hashed over an uncommitted tree, and every subsequent task's DoD requires a clean tree.

## 3 · Longest dependency chain

```
P0-01 → P0-09 → P1-08 → P1-09 → P1-10 → P2-01 → P2-02 → P2-06 → P3-01 → P3-02
      → P3-04 → P3-05 → P4-01 → P4-02 → P4-03 → P4-04 → P4-05 → P4-06 → P4-07
      → P4-08 → P4-09 → P4-10 → P4-13 → P4-14 → P4-15 → P4-20
```

**27 tasks · 74 engineer-days · ≈ 15 weeks of pure serial work.** Total P0–P4 effort is 115 days, so the theoretical parallel floor is ~15 weeks against a 23-week plan — the slack absorbs review, integration and the HIGH-risk P4 tasks.

## 4 · Blocking tasks — a slip here slips the programme

| Task | Why blocking | Slack |
|---|---|---|
| **P0-01** | gates literally everything | **zero** |
| **P0-09** | identity spine; every L0 module depends on `security_id` | zero |
| **P1-09** | FIFO lots feed every measurement | zero |
| **P1-10** | `PositionSnapshot` is the pipeline's stage-1 input | zero |
| **P2-01** | `CalculationResult`/`NotComputable` is the type every calc returns | zero |
| **P2-06** | `PositionState` is the input to policy evaluation | zero |
| **P3-05** | `ConstraintEvaluation` is the input to S1 | zero |
| **P4-09** | boundary inversion — hardest calculation, HIGH risk | 3 d |
| **P4-14** | renderer gates all 7 golden tests | 2 d |

## 5 · Parallelisable work

| Band | Tasks that may run concurrently | Note |
|---|---|---|
| A (after P0-01) | P0-02/03 · P0-04→07 · P0-08 · P0-11 · P0-09 | five independent streams; a second engineer pays for itself here |
| B (after P0-09) | P0-10/14 · P0-12/13 · P1-01 · P1-08 | ledger work is independent of market data |
| C (after P1-01) | P1-02 · P1-03 · P1-04→05 · P1-06→07 | four independent streams |
| D (after P2-01) | P2-02 · P2-03 · P2-04 | C1–C6, C7–C12, P1–P7 are mutually independent |
| E (after P2-06) | P2-07 · P2-08 · P2-09 · P2-10 | — |
| F (after P3-01) | P3-07 · P3-02 chain | — |
| G (after P4-02) | P4-11 · P4-03 chain | — |
| H (after P4-13) | P4-17 · P4-14 chain | semantic tests are written against the model, not the render |
| I (after P4-14) | P4-18 · P4-19 · P4-15 | — |

**S1–S9 (P4-02…P4-08) are strictly serial.** Each stage consumes the survivor set of the previous one; there is no way to parallelise the cascade.

## 6 · Final integration task

**P4-20 — `test_zero_signal.py`: the full 13-stage pipeline with `src/mip_evidence/` and `src/mip_forecast/` deleted from disk, producing a complete `RenderedReport` with evidence contribution 0 and `forecast_contribution == 0.0`.**

It is the last task because it exercises every stage and is the executable form of the frozen P1 principle. **P4 is complete when it passes alongside the fourteen acceptance assertions and `verify_reports.py` exit 0** — at which point the production system reproduces the frozen contract with no Evidence and no Forecast layer built.
