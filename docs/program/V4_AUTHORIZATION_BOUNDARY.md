# V4 AUTHORIZATION BOUNDARY

**Purpose: prevent a large implementation proceeding on an unvalidated product thesis.**
Test applied to every activity: *if Phase 1 FAILS, is this work wasted?* If yes → prohibited.

---

## Classification

| Activity | Class | Rationale |
|---|---|---|
| **Repository inventory** | ✅ **Permitted** | Pure discovery. Useful under any product definition |
| **Architecture documentation** | ✅ **Permitted** | Already complete. Costless to hold |
| **Interface sketches** (Protocols, dataclass signatures) | ✅ **Permitted** | Reversible, no runtime, no schema. Sharpens V5/V6 design |
| **Data restoration** (prices, macro, into the surviving schema) | ✅ **Permitted** | **Disaster recovery for a realised loss**, not product building. Hard prerequisite for V5/V6, which are not product-gated |
| **Automated offsite backup + restore drill** | ✅ **Permitted — MANDATORY FIRST** | A permanent loss already occurred. Deferring it risks a second |
| **Prototype verification** (`tools/phase1/verify_reports.py`) | ✅ **Permitted** | Study-scope; already built and green |
| **V5/V6 research drivers** (scratchpad only) | ✅ **Permitted, capped** | Free, reversible, no `src/`, no migrations |
| **Domain objects** (`PositionState`, `PolicyArtifact`, `CalculationResult`…) | ⚠️ **Permitted as UNEXECUTED SKETCHES only** | Type declarations with no behaviour, no persistence, no tests. **The moment a domain object acquires a repository, it is prohibited** |
| **Database migrations** | ❌ **Prohibited** | Schema is a commitment. Migrations are forward-only and hard to unwind |
| **Production services** (M5–M15) | ❌ **Prohibited** | The implementation itself |
| **Report generator** | ❌ **Prohibited** | Explicitly rejected by the engineering assessment: the seven reports already exist frozen; a generator regenerates them and creates a divergent source of truth |
| **Evidence engine** | ❌ **Prohibited** | Two gates downstream (G3, G4) |
| **Forecast layer** | ❌ **Prohibited** | Four gates downstream (G7). May never be built |
| **Acceptance test harness** | 🔶 **After PASS** | Depends on domain objects and the renderer |
| **CI pipeline** | 🔶 **After PASS** | Meaningless without code to gate |
| **Calculation engine C1–C12** | 🔶 **After PASS** | Genuinely tempting — it is small, deterministic, and useful. **Still prohibited:** it is production `src/` code and the boundary must be bright, not negotiated |

## The bright line

> **Permitted:** documents · sketches · restoration · backup · free research in scratchpad.
> **Prohibited:** anything under `src/mip*/`, any migration, any test asserting production behaviour.

`src/` is the boundary because it is unambiguous. A boundary that requires case-by-case judgement will
be argued away one commit at a time — which is precisely how the anti-redesign rule gets defeated.

## Effort ceiling before G1

| Permitted activity | Hours |
|---|---|
| Repository inventory | 4 |
| Interface sketches | 8 |
| Data restoration | 20 |
| Backup + restore drill | 5 |
| Prototype verification (done) | 0 |
| **Total** | **≤ 40 hours** |

**Any pre-G1 activity exceeding 40 hours is prohibited regardless of classification.** A ceiling on
total effort is the backstop when a category argument fails.

## Waste analysis under G1 FAIL

| Permitted work | Wasted on FAIL? |
|---|---|
| Repo inventory · architecture docs | No — informs any redefinition |
| Interface sketches | Mostly no — the domain survives a product pivot |
| **Data restoration + backup** | **No — required by V5/V6, which are not product-gated** |
| Verifier | No — already delivered its value (three defects) |

**Zero permitted activity is wasted by a Phase 1 FAIL.** That is the test the boundary was built to pass.
