# DATA PURCHASE AUTHORIZATION CONTRACT

**No provider is selected in this document.** Capabilities and ceilings only.
**Nothing here authorizes a purchase today.**

---

## 1 · The four conditions — ALL required

```
C1  ≥1 evidence source has reached ADVISORY  (G4)
C2  V6 shows a realistic effect is detectable at an attainable clean universe  (G5 PASS or AMBIGUOUS)
C3  Survivorship bias, delisting returns, identifier history, or PIT universe
    construction are demonstrably the REMAINING blockers to DIRECTIONAL validation
C4  A provider meets every mandatory capability within the cost and engineering ceilings
```

**C3 is the condition most likely to be waved through.** It requires a written analysis showing that
after G4 and G5, *no cheaper blocker remains*. If the binding blocker is the aggregation layer
(V6 Arm 2 ≫ Arm 1), or an unfixed calibration defect, **C3 fails and the purchase is not authorised** —
data would be bought to feed a chain that destroys signal.

## 2 · Mandatory capabilities — each a hard gate

| # | Capability | Threshold | Prevents |
|---|---|---|---|
| **M1** | Delisted securities with full price history to termination | ≥20% of all ids ever listed | Survivorship bias — the reason for the purchase |
| **M2** | **Delisting returns**, numeric, method documented | **≥80% non-null** on delisted names | Silent truncation of losers |
| **M3** | History depth | **≥20 years** | Insufficient independent annual blocks |
| **M4** | Corporate actions, with raw prices retained | splits + dividends complete; ex-dates correct | Unreproducible total return |
| **M5** | PIT identifier history | ticker changes and reuse resolvable without collision | Identity bleed between companies |
| **M6** | Reproducible vintages | same window pulled twice ⇒ identical checksum | Irreproducible studies |
| **M7** | Universe breadth | **≥200 eligible names** at a past as-of date | Below the MDE requirement |

**Any M-row failing ⇒ reject, regardless of price.**

## 3 · Strongly preferred

| Capability | Why |
|---|---|
| PIT index membership (add/drop dated) | A vendor-supplied universe beats a discretionary rule we must defend |
| **Bulk export** | The cheapest path to a one-time 20-year corpus |
| **Retention after lapse** | $X buys a permanent corpus rather than a rental |
| PIT sector classification | Sector-relative targets |

## 4 · Ceilings

| Ceiling | Value | Rationale |
|---|---|---|
| **Maximum annual cost** | **$2,000** | Above this the purchase competes with a year of engineering |
| **Absolute first-year cash** | **$2,500** incl. any OS, VM or licence | Hard stop |
| **Maximum engineering burden** | **3 engineer-weeks** for adapter + ingest + validation | A provider needing more is disqualified on integration cost alone |
| **Maximum time to first ingested name** | **1 week** from licence | Longer indicates a delivery-path problem |

## 5 · Operating-system and delivery requirements

### REST-native alternative is PREFERRED

Default preference. Reasons: no OS dependency · no VM to maintain · inside the test suite · no
additional licence cost · reproducible in CI.

### A Windows VM is accepted ONLY if ALL hold

```
V1  No REST-native provider meets every mandatory capability M1-M7
V2  A ONE-TIME bulk export is impossible (a maintained live feed is genuinely required)
V3  The total including OS + VM licensing stays within the $2,500 ceiling
V4  The ingestion path is scripted and reproducible, not manual
V5  The VM is documented as a bounded EXPORT operation, not a maintained daily service
```

**If V2 fails — i.e. a one-time bulk export IS possible — the VM is rejected and a one-time cloud
instance (~$20) is used instead.** A research corpus is built once, not streamed.

**A maintained Windows VM sits outside the test suite and the migration chain, weakening the
reproducibility discipline (M6) that is the platform's best asset.** That cost is real and is charged
against the provider's score.

## 6 · Evaluation template *(vendor-neutral; scored from actual data, never documentation)*

| # | Test to run | Pass | Cand. A | Cand. B |
|---|---|---|---|---|
| M1 | `COUNT(DISTINCT id WHERE delist_date IS NOT NULL)` on the trial tier | ≥20% | | |
| M2 | `% of delisted ids with non-NULL terminal return` | ≥80% | | |
| M3 | `MIN(price_date)` for one survivor and one delisted name | ≥20 yr | | |
| M4 | Reproduce one known split + one dividend from raw | exact | | |
| M5 | Resolve one ticker change and one ticker reuse | no collision | | |
| M6 | Pull the same window twice; compare checksums | identical | | |
| M7 | `COUNT(DISTINCT id)` eligible at a past as-of | ≥200 | | |
| — | True annual cost for the minimum passing bundle | ≤$2,000 | | |
| — | **Total operating cost** incl. VM/OS/maintenance hours | ≤$2,500 | | |
| — | Time to first ingested name | ≤1 wk | | |
| — | Fits the existing `OutcomeSource` Protocol without **structural** DTO change | field additions only | | |

**Decision rule:** any M-row failure ⇒ reject. Among survivors, select on **total operating cost**,
never on cash price, reputation, or coverage beyond M7.

## 7 · Authorization instrument

```
DATA PURCHASE AUTHORIZATION

C1  ADVISORY source: ______________  promoted ______  ledger record ______
C2  G5 result: ▢ PASS  ▢ AMBIGUOUS(declared reduced claim)   MDE = ______ at ______ names x ______ yrs
C3  Remaining-blocker analysis attached  ▢     Cheaper blockers ruled out: ______________
C4  Provider meets M1-M7  ▢    Total operating cost $______  (ceiling $2,500)
    Delivery: ▢ REST-native   ▢ Windows VM (V1-V5 ALL satisfied ▢)

Sponsor (CIO) signature ______________________  Date ____________

** NOT VALID WITHOUT ALL FOUR CONDITIONS EVIDENCED **
```

## 8 · Status today

| Condition | Status |
|---|---|
| C1 ADVISORY source | ❌ **None. The ledger is empty and V5 has not run** |
| C2 G5 / MDE | ❌ **Never measured. V6 has not run** |
| C3 Remaining blocker | ❌ **Cannot be assessed until C1 and C2 exist** |
| C4 Provider | ❌ Not evaluated — evaluation is premature before C1–C3 |

# NOT AUTHORIZED. 0 of 4 conditions met.
