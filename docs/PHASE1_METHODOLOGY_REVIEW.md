# Methodology Review of PHASE1_STUDY_PACKAGE.md

**Reviewer:** independent experimental-methodology review
**Scope:** whether the pass/fail criteria establish that the V3 report **improves decision quality**, or
merely that it **influences** participants. No architecture changes, no product features, no expansion
into a large trial.

---

## Verdict up front

**The study is not runnable as written.** Its primary outcome measures **influence**, and influence is
sign-blind. As specified, a report that reliably made decisions *worse* would pass every threshold.

The defect is real but narrow, and it is fixable **without new participants, new sessions, or a larger
trial** — by classifying the decision changes that the study is already collecting.

---

## PART 1 — Attacking "decision change above sham"

### What it proves

1. The artefact carries information the participant did not have, or had not attended to.
2. That information is salient enough to override a **committed**, written position.
3. The effect is not ordinary reconsideration — the sham control is a genuine and well-designed
   safeguard, and it survives this review intact.

### What it does not prove

1. **That the new decision is better.** The measure has no sign.
2. **That the change is defensible.** Deference ("the report said trim") scores identically to reasoning.
3. **That the mechanism is information rather than persuasion.** Structured, numerate, confident-looking
   documents move people. That is one of the most robust findings in judgment research.

### The decisive objection

> **A plausible-looking report containing arbitrary but internally coherent content would very likely
> clear the 30% threshold.**

Nothing in the current design distinguishes *"this report is informative"* from *"this report is
persuasive."* Since the entire V3 architecture is built to prevent confident-looking outputs that are
not earned, **authorising development on an influence measure alone would validate exactly the property
the architecture exists to eliminate.**

### Is it sufficient to authorise development?

**No — but it remains necessary.** If the report changes nothing, quality is moot. The correct repair is
not to replace the outcome but to make the gate conjunctive.

---

## PART 2 — Decision quality without returns

Nine dimensions were proposed. Most overlap, several are unobservable at this sample, and one is
circular. **The smallest defensible set is three**, scored independently and **never summed**.

| ID | Dimension | Observable question | Covers |
|---|---|---|---|
| **Q1** | **Reasoning–action coherence** | Does the stated action follow from the stated reason, and is the magnitude connected to it? | objective–action consistency, proportionality of size change |
| **Q2** | **Material-constraint engagement** | Does the reasoning engage the constraints materially present in this case — tax, liquidity, concentration, dated event? | constraint identification, explicit tax/liquidity/concentration treatment |
| **Q3** | **Claim support** | Does the reasoning avoid asserting a directional view the available information cannot support, and is stated confidence proportionate to the basis? | confidence calibration, unsupported directional claims, abstention validity |

**Reported as a triple `(Q1, Q2, Q3)`. No composite. No weighting.** A composite would require exchange
rates between incommensurable dimensions — the same defect this project already rejected in its
decision architecture, and it would be worse here because the weights would be invisible.

### Policy compliance is deliberately excluded

It is the most circular measure available: the platform supplies the policy, so scoring "did they comply
with the policy" scores "did they agree with us." **In this study the policy is case *context* the
participant may legitimately reject**, and rejection is scored under Q1 (is the alternative coherent?),
never as non-compliance. See Part 7.

---

## PART 3 — Blinded evaluation

### Unit of evaluation

The **individual decision record**, never the pair:

```
{case context (as shown), stated action, magnitude, stated confidence, reasoning verbatim}
```

Records are anonymised, stripped of timestamps and participant identity, **shuffled across participants
and cases**, and scored one at a time. Evaluators never see a pre/post pair together, so position
cannot leak condition.

### Blinding, and its honest limits

Post-report records may quote report-specific figures ("the 13.4pp breach"), which leaks condition.

- **Redaction pass:** a non-evaluator removes numeric strings that appear *only* in the report, replacing
  them with `[figure]`. Reasoning structure is preserved.
- **Measured, not assumed:** evaluators are asked to guess pre/post on every record. **Guess accuracy is
  reported.** At chance (~50%) blinding held; materially above chance, the quality result is reported as
  partially unblinded and downgraded to AMBIGUOUS-supporting evidence.

Measuring blinding integrity is more honest than asserting it.

### Who may evaluate

**Three evaluators.** Investment professionals or sophisticated allocators meeting the Track A screener.

**Disqualified:** the architect; the moderator; any study participant; anyone who has read any project
document. **At least one evaluator must have had no exposure to this project of any kind.**

**Briefing (true and uninformative):** *"Score each of these investment decision records on three
dimensions."* They are **not** told that reports exist, that records are paired, that conditions differ,
or what the study is testing.

### Adjudication of legitimate disagreement

Professionals will disagree, and forcing consensus would manufacture precision.

1. Three evaluators score independently.
2. **2-of-3 agreement** on a dimension sets the code.
3. **No 2-of-3 majority → the dimension is coded `UNRESOLVED`.** It is not adjudicated further and it is
   not forced.
4. `UNRESOLVED` is reported as a rate, not discarded.
5. **If the `UNRESOLVED` rate exceeds 30%, the quality gate is declared uninformative** and the study
   result is capped at AMBIGUOUS regardless of the influence rate.

That last rule prevents an unreliable measure from silently authorising development.

---

## PART 4 — Classification of change

Applied to each confirmatory case by comparing the blind-scored pre and post records. **Observable
reasoning and constraint engagement only — never realised returns.**

| Code | Criteria | Example |
|---|---|---|
| **IMPROVED** | Post engages a material constraint the pre missed (Q2↑), **and** Q1 maintained or better, **and** Q3 not worse | Pre: *"trim a bit, it's gotten big."* Post: *"trim to the cap, staged over two weeks — at 4 days' volume I'd move the price against myself."* Liquidity newly engaged; coherence intact |
| **DEFENSIBLE** | Action or magnitude changed; Q1 coherent; **no** new constraint engaged and **no** added support | Pre: *"trim 5%, it's oversized."* Post: *"trim 8%, it's oversized."* Different, coherent, not demonstrably better |
| **UNCHANGED** | No material change to action or magnitude | — |
| **UNSUPPORTED** | Change occurs but stated reasoning does not support it — deference, a cited factor absent from the case, or confidence rising with no added basis | Pre: *"hold, confidence 3."* Post: *"trim 10%, confidence 5 — the report says to."* Authority substituting for reasoning |
| **DEGRADED** | Post is **less** coherent (Q1↓), **abandons** a constraint the pre engaged (Q2↓), **or** asserts a directional view the case cannot support (Q3↓) | On the abstention case — Pre: *"hold, no strong view, confidence 2."* Post: *"trim 6%, confidence 4"* citing conflicting evidence as though it were directional |

**Case 5 (conflicting evidence, designed abstention) is the harm probe.** It is the case most likely to
elicit a manufactured directional view, and the classification above is built to catch exactly that.

---

## PART 5 — Revised outcome structure

### Option C — a dual gate. Both must pass.

Not A (influence alone authorises a persuasion effect). Not B (n=5 cannot demonstrate improvement, and a
beneficial-change rate would be a precision claim the sample cannot support).

**The two gates carry deliberately asymmetric evidentiary standards, because the sample supports one and
not the other:**

| Gate | Claim type | What n=5 supports |
|---|---|---|
| **Influence** | Positive claim, with a rate | Detectable at a large effect. Keep the 30% threshold |
| **Quality** | **Harm screen + existence proof** | Can detect *predominant* harm and can demonstrate *at least some* improvement. **Cannot estimate a benefit rate** |

### Revised primary hypothesis

> **Reading a V3 report changes a portfolio manager's committed intended action or magnitude at a rate
> materially above sham reconsideration, AND those changes are not predominantly unsupported or
> degraded, AND at least some changes are independently judged to improve constraint engagement.**

### Revised secondary outcomes

Unchanged: policy-violation detection (H2), abstention acceptance (H3), score arm (H4, exploratory),
comprehension, adoption, WTP.

**Added:** distribution of change classifications; inter-evaluator agreement (κ); `UNRESOLVED` rate;
blinding-integrity guess accuracy.

**Removed:** none.

---

## PART 6 — Revised thresholds (preregistered)

Denominator for quality codes = **attributed changes only** (`COUNTED` cases). Unchanged decisions are
not classifiable.

### PASS — development authorised (all six)

1. Net attributed change rate **≥ 30%** *(influence)*
2. **≥ 3 of 5 participants** individually show ≥ 1 attributed change *(participant-level independence)*
3. **≥ 2 distinct report sections** cited across the study *(value beyond cap-breach detection)*
4. **UNSUPPORTED + DEGRADED ≤ 25%** of attributed changes *(harm screen)*
5. **≥ 2 changes coded IMPROVED, occurring in ≥ 2 different participants** *(existence proof, deliberately weak — this is what n=5 supports)*
6. `UNRESOLVED` **≤ 30%** and blinding guess accuracy **≤ 65%** *(the quality measure is informative)*

### FAIL — the project stops (any one)

- Net attributed change rate **< 15%**
- **≥ 4 of 5** participants show zero attributed changes
- Recruitment of five qualified participants fails within the cap
- **UNSUPPORTED + DEGRADED > 40%** of attributed changes *(harm predominates)*
- **Any single participant shows ≥ 2 DEGRADED classifications** *(person-level harm signal — a report that repeatedly worsens one person's reasoning is disqualifying even if the aggregate looks acceptable)*

### AMBIGUOUS — one narrowly scoped follow-up

Everything else, explicitly including: influence met but IMPROVED count 0–1; harm in the 25–40% band;
change concentrated in ≤ 2 participants; `UNRESOLVED` > 30%; blinding compromised.

**The anti-redesign rule from the original package stands unchanged**, and now also applies to failures
of the quality gate. A harm failure may **not** be answered by rewriting the report and re-testing.

### On precision

No confidence intervals are reported for any rate. All thresholds are **conjunctive counts**, not
estimates. The study reports what happened in 25 case-observations across 5 people and claims nothing
about a population.

---

## PART 7 — Circularity

### The risk

If decisions are scored against the platform's own policy, "good decision" collapses into "agreed with
the platform," and the study validates conformity rather than quality.

### Six safeguards

1. **Policy compliance is not a quality dimension.** Removed entirely (Part 2).
2. **The policy is context, not ground truth.** A participant may reject the 15% cap; rejection is scored
   on Q1 coherence, never as non-compliance.
3. **Evaluators are never shown what the report recommended**, nor told a report exists.
4. **The three dimensions are general decision-quality concepts** — coherence, constraint engagement,
   claim support — not platform constructs. None derives from V3's architecture.
5. **≥ 1 evaluator has had no exposure to this project.**
6. **The Q2 constraint list per case is authored externally** — by a professional who is not the
   architect — **before any scoring begins**, and frozen. The platform does not define what counts as a
   material constraint in its own test cases.

Safeguard 6 is the strongest. **The ground truth for "what mattered in this case" is written by someone
outside the project.** That is what removes the platform as sole author of its own success criterion.

---

## PART 8 — Verdict

### 1. Is the study runnable without modification?

**No.** It would authorise development on a persuasion effect, and it cannot distinguish a beneficial
change from a harmful one.

### 2. The single minimum modification

> **Add a blinded, externally-anchored classification of the decision changes the study already
> collects, and make the pass gate conjunctive on influence *and* non-harm.**

No new participants. No new sessions. No new cases. No new instruments — the reasoning text is already
captured on the response forms and transcripts.

**Cost:** ~5 additional hours (evaluator recruitment and briefing 2 h; external constraint lists 1 h;
redaction and blinding prep 1 h; scoring coordination 1 h) and **$150** (3 × $50).

**Revised cap: 30 hours / $650.** If the 25 h / $500 cap is hard, **drop the exploratory score arm
(case 7) to fund the harm screen.** A safety check on the primary outcome is worth strictly more than
an exploratory format comparison that n=5 cannot resolve anyway.

### 3. Evidence justifying continued development

All six PASS conditions in Part 6: influence above sham, spread across ≥ 3 participants, citing ≥ 2
distinct sections, with ≤ 25% unsupported-or-degraded changes, ≥ 2 improvements in ≥ 2 different
participants, and an informative quality measure.

### 4. Outcome requiring the project to stop

Influence below 15%; or ≥ 4 of 5 participants unmoved; or recruitment failure; or **> 40% of changes
unsupported-or-degraded**; or **any participant degraded twice**.

### 5. Can this pilot establish decision improvement?

**No — and it should not claim to.**

It can establish three things: that the report **influences** committed decisions beyond reconsideration;
that its influence is **not predominantly harmful**; and that **at least some** changes improve
constraint engagement under blind external judgment.

That is **sufficient evidence to justify a larger field test on real portfolios — and nothing more.**
Any language in a Phase 1 report claiming the product "improves decision quality" would overstate what
25 observations across five people can support. The honest formulation is:

> *"The report changed committed decisions at a rate above reconsideration; blinded external evaluators
> did not find those changes predominantly unsupported or degraded, and judged at least two of them to
> improve constraint engagement."*

---

# Corrected sections — ready to insert into PHASE1_STUDY_PACKAGE.md

## ▸ Replaces Part 1, "Primary hypothesis (H1)"

> **H1 (revised).** Reading a V3 report changes a portfolio manager's **committed** intended action or
> magnitude at a rate materially above the rate at which their decision changes on reconsideration with
> no new information — **and** those changes, judged blind by external investment professionals against
> externally-authored constraint lists, are **not predominantly unsupported or degraded**, **and at
> least some** are judged to improve material-constraint engagement.
>
> **Rationale for the conjunction:** decision change is sign-blind. A confident-looking report
> containing arbitrary content would likely clear an influence-only threshold. Authorising development
> on influence alone would validate precisely the property the V3 architecture exists to prevent.

## ▸ Replaces Part 5, "PRIMARY OUTCOME"

> **PRIMARY OUTCOME — dual gate.**
>
> **Gate 1 (influence):** attributed decision change rate on cases 1–5, net of the sham control.
> *Definitions unchanged from the original package.*
>
> **Gate 2 (quality):** the distribution of blind classifications across all attributed changes:
> `IMPROVED` / `DEFENSIBLE` / `UNSUPPORTED` / `DEGRADED` / `UNRESOLVED`, coded on
> **Q1 reasoning–action coherence**, **Q2 material-constraint engagement**, **Q3 claim support** —
> scored independently, reported as a triple, **never summed into a composite**.
>
> **Both gates must pass. Neither substitutes for the other.**
>
> *Limitation, stated in advance:* at n = 5, Gate 2 is a **harm screen plus an existence proof**. It
> cannot estimate a rate of beneficial change, and no such rate will be reported.

## ▸ Replaces Part 6 in full

> ### PASS — development authorised (all six required)
> 1. Net attributed change rate **≥ 30%**
> 2. **≥ 3 of 5 participants** show ≥ 1 attributed change
> 3. **≥ 2 distinct report sections** cited across the study
> 4. **UNSUPPORTED + DEGRADED ≤ 25%** of attributed changes
> 5. **≥ 2 changes coded IMPROVED, in ≥ 2 different participants**
> 6. `UNRESOLVED` **≤ 30%** and blinding guess accuracy **≤ 65%**
>
> ### FAIL — the project stops (any one)
> - Net rate **< 15%**
> - **≥ 4 of 5** participants show zero attributed changes
> - Recruitment fails within the cap
> - **UNSUPPORTED + DEGRADED > 40%**
> - **Any single participant with ≥ 2 DEGRADED**
>
> ### AMBIGUOUS — one narrowly scoped follow-up
> All other combinations, including: influence met but IMPROVED ≤ 1; harm 25–40%; change concentrated
> in ≤ 2 participants; `UNRESOLVED` > 30%; blinding compromised.
>
> ### Unchanged
> The anti-redesign rule applies to quality-gate failures exactly as to influence failures. **A harm
> result may not be answered by rewriting the report and re-testing.**
>
> ### Still not a pass, under any circumstance
> High ratings · stated willingness to use · any WTP figure · enthusiasm from one participant ·
> **decision change with no evidence that the changes are defensible.**

## ▸ New Part 5b — Blinded quality evaluation

> **Unit:** the individual decision record `{case context, action, magnitude, confidence, reasoning}` —
> never the pair.
> **Preparation:** anonymise; strip timestamps and participant IDs; redact numeric strings appearing
> only in the report; shuffle across participants and cases.
> **Evaluators:** three, meeting the Track A screener; excluding the architect, the moderator, and all
> participants; **≥ 1 with no exposure to the project**. Briefed only as *"score these investment
> decision records on three dimensions."*
> **Ground truth:** the per-case material-constraint list for Q2 is **authored by an external
> professional before scoring begins** and frozen.
> **Adjudication:** 2-of-3 agreement sets the code; no majority → `UNRESOLVED`, not forced, and reported
> as a rate.
> **Blinding integrity:** evaluators guess pre/post on every record; **guess accuracy is reported** and
> caps the result at AMBIGUOUS if above 65%.

## ▸ Amendment to Part 10 §4 — budget

> **Revised cap: 30 hours / $650.** Increment: evaluator recruitment and briefing 2 h; external
> constraint lists 1 h; redaction and blinding prep 1 h; scoring coordination 1 h; evaluator payment
> $150.
> **If the 25 h / $500 cap is binding: remove the exploratory score arm (case 7) to fund the quality
> gate.** A harm screen on the primary outcome dominates an exploratory format comparison the sample
> cannot resolve.
