# Phase 1 — Product Validation Study: Execution Package

**Status:** ready to run. No further conceptual review required.
**Gate:** ARCHITECTURE_V3 Phase 1. No development is authorised until this study returns PASS.
**Architecture:** frozen. This document adds no features and proposes no roadmap.

---

## PART 1 — Hypotheses (preregistered)

### Primary hypothesis (H1)

> **When a portfolio manager has committed to an intended action on a real position, reading a V3 report
> changes that intended action or its magnitude, at a rate materially above the rate at which their
> decision changes on re-examination with no new information.**

Measurable (a rate), falsifiable (it can come out at zero), preregistered (thresholds in Part 6),
answerable in a pilot (a within-participant, pre/post design with a sham control).

### Secondary hypotheses

**H2 — Policy-violation detection.** Participants identify more policy breaches after reading the report
than before.

**H3 — Abstention acceptance.** When the report declines to give a directional view, participants accept
the abstention as a legitimate output rather than treating it as a product failure.

**H4 (exploratory) — Score presentation.** The absence of a synthetic 0–100 score does not reduce
participants' ability to triage or act. *Exploratory only: n is too small for a confirmatory claim.*

### The evidence ladder — and where validation actually sits

| Level | What it measures | Counts as validation? |
|---|---|---|
| Stated interest | "This looks interesting" | **No.** Free to say, costless, systematically inflated by politeness |
| Perceived usefulness | "I would find this useful" | **No.** Hypothetical; poorly predicts behaviour |
| Decision comprehension | Can they correctly restate the recommendation and its basis? | **Necessary, not sufficient.** A precondition |
| **Decision change** | Committed action/magnitude changes, with attribution | **YES — this is the primary outcome** |
| Willingness to adopt | Concrete steps taken toward use | Supporting evidence |
| Willingness to pay | A number, unprompted, with a budget line | Commercial signal only; **explicitly excluded from the pass criteria** |

**Standing rule: praise without decision change is a FAIL.** It is recorded, reported, and never
reinterpreted as partial success.

---

## PART 2 — Participants

### Qualifying profiles

**Track A — Professional (target: 3 of 5)**
Portfolio manager, analyst with documented position-sizing input, RIA/advisor with discretionary
authority, family-office principal or staff, or allocator with manager-selection authority.
Minimum 3 years in role. Currently makes or materially shapes position-level decisions on capital that
is not their own.

**Track B — Sophisticated individual (max 2 of 5)**
Manages ≥ $250,000 of own or family capital, ≥ 5 years, ≥ 10 concurrent positions, makes position-level
decisions, and can articulate an existing process (written or verbal) for sizing and trimming.

### Disqualifying criteria

- Index-only or fully passive — makes no position-level decisions
- Intraday or swing traders whose holding period is under one week — horizon mismatch
- Any prior exposure to this platform, its reports, or any of its review documents
- Personal relationship with the builder (politeness bias is the dominant threat at n=5)
- No discretionary authority — cannot state an action they would actually take
- Anyone who asks what result we are hoping for and is told

### Is n = 5 sufficient?

**For H1 — yes, for a restricted claim.** Five participants × five confirmatory cases = 25 paired
observations, but the participant is the unit of independence, so inference is effectively n = 5. This
detects a **large effect** (change rate ~30%+ vs a near-zero baseline) and nothing finer.

**Claims n = 5 CANNOT support — and which are therefore removed from the study rather than reported
weakly:**

- Any point estimate of the change rate ("this changes 34% of decisions") — the interval is far too wide
- Professional vs individual comparison
- Any per-case or per-section effect
- Willingness to pay at any usable precision
- H4 as anything other than exploratory
- Generalisation beyond the six case archetypes tested

**Restricting the claim is the correct response to a small sample. Inflating the analysis is not.**

---

## PART 3 — Experimental design

### Structure: within-participant, pre/post commitment, with a sham control

Arm A is not a separate condition — it is the **pre-report state**. Each case elicits a *committed*
decision using the participant's normal process, then reveals the report, then re-elicits. This is the
maximally powered design at n = 5.

| Case | Condition | Purpose |
|---|---|---|
| 1–5 | **A → B** (commit, then V3 report, then re-elicit) | Confirmatory. Primary outcome |
| 6 | **A → A′** (commit, 3-minute distractor, then re-elicit with **no report**) | **Sham control.** Measures baseline decision instability |
| 7 | **A → C** (commit, then score-bearing report) | Exploratory. H4 |

**The sham control is the design's most important element.** Without it, any observed change rate is
uninterpretable, because people revise decisions on reconsideration alone. The primary outcome is the
*difference* between the report condition and the sham.

### Ordering and balance

Cases 1–5 are presented in a Latin-square rotation across the five participants, so no case occupies the
same position twice. The sham (6) and score case (7) are randomly interleaved among positions 3–7,
never first or last. Participants are not told any case differs from any other.

### Bias controls

| Threat | Control |
|---|---|
| **Ordering effects** | Latin square; sham and score cases never in a fixed slot |
| **Familiarity with securities** | All cases are **disguised composites**. Sector and business model described generically; no tickers, no company names, no recognisable figures |
| **Hindsight bias** | **No subsequent price action is ever shown or referenced.** Dates masked as "T", "T−90d". Moderator never confirms what happened |
| **Researcher prompting** | The moderator is **not the architect** and has not read the design documents. Script read verbatim. No improvised follow-ups beyond the listed probes |
| **Social desirability** | Opening statement explicitly frames "not useful" as a valuable result the team needs. No mention of effort invested, and no reference to prior versions |
| **Confirmation bias** | Pre-decision is **written and committed** before the report is visible. Recorded by the moderator before revealing |
| **Inferring the desired answer** | Participants are told the study compares "several report formats," not that one is preferred. The sham case makes "no change" a visibly normal outcome. The post-form lists "Nothing changed" as the **first** option |
| **Baseline instability** | The sham control, measured directly rather than assumed |

### Study flow

1. **Screen** (10 min, async) — questionnaire, Part 10 §B
2. **Schedule** — 90-minute session, video, recorded with consent
3. **Consent and framing** (5 min) — script, Part 7 §1
4. **Warm-up case** (5 min) — an unscored practice case, discarded from analysis, to normalise the format
5. **Cases 1–7** (~8 min each, 56 min) — commit → reveal → re-elicit → probes
6. **Debrief** (15 min) — trust, abstention, conflict, score comparison, adoption, WTP
7. **Close** (5 min) — incentive, no disclosure of hypotheses until all sessions complete

---

## PART 4 — Test materials

### Prototype scope

**Static PDF or printed reports. One page per case. No application, no interactivity, no navigation.**
Building anything interactive would confound format with product and is out of scope.

### Required sections per report (V3 order, natural units only, no composite score)

1. Action + natural-units magnitude ("TRIM — reduce by 13.4pp of portfolio")
2. Policy status (weight vs target vs cap, in percentage points)
3. Portfolio impact (concentration, cluster, sector deltas)
4. Supporting evidence and conflicting evidence — **both, side by side, tier-labelled**
5. Confidence profile (basis: policy-arithmetic vs evidence; never a single number)
6. Elimination trace ("why not EXIT: ...")
7. What changed since last review
8. What would reverse this decision (boundary conditions)
9. Terminal-wealth disclosure (recommendations vs do-nothing, prior period)
10. Abstention statement where applicable

### The seven cases

| # | Archetype | Participant receives | **Withheld** |
|---|---|---|---|
| **1** | **Above hard cap** — 28.4% weight vs 15% cap, appreciated, liquid | Portfolio summary, position detail, written policy extract, V3 report | Subsequent prices; that this is the "obvious" case |
| **2** | **Below target, near-term event risk** — 3.1% vs 5% target, earnings in 4 days | As above + confirmed dated catalyst | Earnings outcome; any estimate or expectation |
| **3** | **Appreciated winner, embedded gains** — 19% weight, 340% unrealised, high tax cost | As above + tax-lot detail | Subsequent prices; the tax rate's effect on the recommendation |
| **4** | **Loser within policy** — 2.8% weight, −44%, inside every limit. **Correct answer: no action** | As above | That this case is designed to test false-positive action |
| **5** | **Conflicting evidence, no defensible view** — 8% weight, mid-band, evidence points both ways | As above; report shows conflict preserved, not averaged | That abstention is the designed outcome |
| **6** | **SHAM** — a case in the same format; participant re-decides after a 3-minute unrelated distractor with **no report** | Portfolio + position only | That no report is coming |
| **7** | **SCORE ARM** — a case comparable to 1–5, report identical except it carries a 0–100 score | As cases 1–5, plus the score | That the score is the variable under test |

**Universally withheld:** the study hypotheses; that some cases have a designed "correct" answer; all
subsequent price action; the existence of prior platform versions; any indication of effort invested.

---

## PART 5 — Outcome measures

### PRIMARY OUTCOME

> **Attributed decision change rate** = the proportion of confirmatory cases (1–5) in which the
> participant's committed action **or** magnitude changes after reading the report, **and** the
> participant names a specific report section as the reason, **minus** the sham-control change rate.

| Element | Definition |
|---|---|
| **Operational definition** | Action change: any move between {ADD, HOLD, TRIM, EXIT}. Magnitude change: ≥ 25% relative change **or** ≥ 2pp of portfolio weight. Attribution: participant names a section unprompted, or selects one from a full list including "none of these" |
| **Collection** | Written pre-form (committed, moderator-witnessed) and post-form per case |
| **Scoring** | Binary per case. Two coders score independently from the forms and transcript; disagreements resolved by a third. Cohen's κ reported |
| **Interpretation** | The rate at which the artefact changes real intended behaviour, net of ordinary reconsideration |
| **Known limitations** | Hypothetical decisions, not executed trades. Disguised cases. Novelty effect. Cannot detect small effects |

**Why this and not the alternatives:** policy-violation detection (H2) is easier to move and would
overstate value — spotting a cap breach is a spreadsheet capability. Decision *change* is the only
measure that separates this product from a compliance report.

**Note on the ceiling:** cases 4 and 5 are designed such that "no change" is correct. The achievable
ceiling is therefore ~60%, not 100%. Thresholds in Part 6 are set against that ceiling.

### Secondary outcomes

| Measure | Definition | Collection | Scoring | Limitation |
|---|---|---|---|---|
| **Policy-violation detection (H2)** | Breaches correctly identified, pre vs post | Pre/post free text | Against a ground-truth list per case | Easy to move; low information |
| **Abstention acceptance (H3)** | On case 5: accepts the "no view" as legitimate vs rejects it | Debrief probe, coded 3-way | Accept / Tolerate / Reject | Single case; politeness pressure |
| **Unsupported-confidence reduction** | Confidence (1–5) pre vs post on case 5 specifically | Both forms | Change in stated confidence | Confidence is self-reported |
| **Decision comprehension** | Can the participant restate the recommendation and its basis unaided? | Verbal, coded | Correct / partial / incorrect | Necessary, not sufficient |
| **Score comparison (H4)** | Case 7 behaviour + forced-choice preference at debrief | Post-form + debrief | Descriptive only | n = 5, exploratory |
| **Adoption evidence** | Concrete steps offered *unprompted* (asks for access, offers own portfolio, asks about frequency) | Transcript | Count of unprompted concrete asks | Weak at n = 5 |
| **Willingness to pay** | Unprompted number with a stated budget source | Debrief | Recorded, not thresholded | **Explicitly excluded from pass criteria** |

---

## PART 6 — Success and kill criteria (frozen before data collection)

Primary = attributed decision change rate on cases 1–5, **net of sham**, ceiling ≈ 60%.

### PASS — development authorised

**All three must hold:**
1. Net attributed change rate **≥ 30%** (≥ 8 of 25 confirmatory cases, sham-adjusted)
2. **≥ 3 of 5 participants** individually show ≥ 1 attributed change
3. **≥ 2 distinct report sections** cited as causes across the study

*Condition 3 exists to prevent the entire result resting on one feature — e.g. everyone merely noticing
a concentration breach, which a spreadsheet would also surface.*

### AMBIGUOUS — one narrowly scoped follow-up permitted

Net rate **15–29%**, **or** rate ≥ 30% but concentrated in ≤ 2 participants.

**Follow-up constraints, binding:**
- **Exactly one** follow-up. It may not produce another.
- **One** pre-declared change only, named before any new data is collected.
- **No architecture change.** Report content and format may change; the system may not.
- Same thresholds, no relaxation.
- Same time and money cap (Part 10 §5).
- If the follow-up does not reach PASS → **FAIL**, with no further options.

### FAIL — the project stops

Net rate **< 15%**, **or** ≥ 4 of 5 participants show zero attributed changes, **or** recruitment of five
qualified participants fails within the time cap.

**The anti-redesign rule.** On FAIL:
1. Development stops. No code is written against V3.
2. **The response to a FAIL may not be to modify the report and re-test.** That path is available once,
   and only from AMBIGUOUS.
3. Resumption requires a **new product hypothesis** and a sponsor **other than the architect**.
4. A minimum 90-day pause precedes any resumption proposal.
5. The negative result is written up and published internally in full.

*This project has deferred this study three times and answered each prior negative with an architecture
revision. The rule exists because that is the demonstrated failure mode.*

### Explicitly not a pass under any circumstance

- Participants rating the report highly
- Participants saying they would use it
- Participants finding it "more rigorous than what they have"
- Any willingness-to-pay figure
- Enthusiasm from a single participant

**Praise without decision change is FAIL.**

---

## PART 7 — Moderator guide (read verbatim)

### 1. Opening

> "Thank you for the time. I'm evaluating some portfolio report formats. I did not design them and I have
> no stake in which one performs better.
>
> I'll show you several positions from a portfolio. For each one I'll ask what you would do and why —
> your normal judgement, no right answers. Then I'll show you some additional material and ask you again.
> Sometimes your view will change and sometimes it won't. **Both are equally useful to me** — a format
> that doesn't change anything is exactly what I need to find out.
>
> Please think aloud. If something is unclear, confusing, or not worth reading, say so plainly — that is
> the most useful thing you can tell me. Any questions before we start?"

### 2. Per case — commit phase

> "Here's a position and the relevant portfolio context. Take as long as you need.
>
> When you're ready, tell me: **what would you do with this position, and roughly how much?**"
>
> [Record verbatim. Then:]
>
> "Please write that on the form — the action, the size, and how confident you are from 1 to 5. And in
> one line, the main reason."
>
> [**Moderator confirms the form is complete before revealing anything.**]

### 3. Per case — reveal phase

> "Here's some additional material on the same position. Read it however you normally would — skim or
> read closely, whatever's natural. Tell me when you're done."
>
> [No commentary. Do not explain any section. If asked what something means: *"Whatever it means to you —
> that's part of what I'm trying to learn."*]

### 4. Per case — re-elicit

> "Now: **what would you do with this position, and roughly how much?**"
>
> [Record. Then:]
>
> "Please complete the second form."
>
> [Post-form leads with: *"Nothing changed"* as the first option.]

### 5. Per case — probes (asked only after the post-form is complete)

- "Talk me through how you got to that."
- *If changed:* "What specifically led you there?" → *if vague:* "Can you point to the part of the page?"
- *If unchanged:* "Was there anything on the page you'd have acted on in a different situation?"
- "Was anything on that page not worth your time?"

### 6. Sham case

Identical script, except the reveal phase is replaced by:

> "Before you finalise — I'd like to ask you about something unrelated for a few minutes."
>
> [3 minutes of unrelated conversation about their normal review process. Then:]
>
> "Coming back to that position — what would you do, and roughly how much?"

### 7. Debrief

**Trust**
- "How much would you rely on something like this? What would that depend on?"
- "Was there anything you'd want to verify before acting on it?"

**Abstention** *(after re-showing case 5)*
- "On this one, the report says it has no reliable directional view. What's your reaction?"
- "Is that more or less useful to you than a page that gave you a direction? Say why."

**Conflict**
- "This page shows evidence pointing both ways rather than combining it into one answer. How did you read that?"

**Score** *(show cases 5 and 7 side by side)*
- "These two formats differ. What's the difference, in your words?"
- "If you had fifty positions to get through on a Monday morning, which would you rather have? Why?"
- "Is there anything the one with the number lets you do that the other doesn't?"

**Adoption**
- "Where, if anywhere, would something like this sit in what you already do?"
- "What would have to be true for you to use it?"
- *(Do not offer access. Record only unprompted asks.)*

**Commercial** *(asked last, always)*
- "If this existed, how would it get paid for in your setup?"
- *If a number is offered:* "What budget would that come out of?"
- *(Never propose a price. Never name a range.)*

**Close**
- "Anything you expected to see and didn't?"
- "Anything you'd remove?"
- "I'll share what we find once all sessions are done. Thank you."

**Banned phrasings:** "Did this help?" · "Do you like…" · "Would you find it useful?" ·
"Was it better than…" · anything containing *improve*, *powerful*, *sophisticated*, or *rigorous*.

---

## PART 8 — Analysis plan

### Categories, analysed separately and never pooled

| Category | Data | Method |
|---|---|---|
| **Behavioural** | Pre/post action and magnitude, attribution | Primary outcome; two independent coders; κ reported |
| **Quantitative ratings** | Confidence 1–5, comprehension codes | Descriptive only. No inferential statistics at n = 5 |
| **Qualitative** | Transcript, think-aloud | Thematic coding; report disconfirming quotes alongside confirming ones |
| **Adoption** | Unprompted concrete asks | Count and quote |
| **Commercial** | WTP, budget source | Recorded verbatim. **Never entered into the pass rule** |

### How to read disagreement between categories

| Pattern | Reading | Action |
|---|---|---|
| **Behaviour changes, ratings lukewarm** | **The strongest possible result.** Behaviour is the outcome; muted enthusiasm removes the politeness confound | PASS if thresholds met |
| **Ratings high, behaviour unchanged** | **FAIL — and the single most likely outcome.** This is what politeness, novelty, and craft-appreciation produce. It is what the study exists to detect | FAIL. Report as such. Do not reinterpret |
| **Behaviour changes but attribution is diffuse** | Possible reconsideration effect rather than a report effect | Check against sham. If sham is comparable → AMBIGUOUS at best |
| **One participant drives everything** | Fails PASS condition 2 by design | AMBIGUOUS |
| **Change concentrated on the cap breach only** | Fails PASS condition 3 — a spreadsheet capability | AMBIGUOUS |
| **High WTP, no behaviour change** | Commercial interest in a category, not evidence for this artefact | Does not affect the verdict |

**"Praised but did not change anything" means the product is admired and not used.** That is the
modal failure of research-heavy tools and it is a FAIL, not a partial success.

---

## PART 9 — Threats to validity

| Threat | Severity | Mitigation | Residual |
|---|---|---|---|
| **n = 5** | **Severe** | Restrict claims to large-effect detection; conjunctive thresholds | Cannot estimate a rate; no subgroups |
| **Participant politeness** | **Severe** | Non-architect moderator; explicit "not useful is useful" framing; exclude personal contacts; behaviour over ratings | Cannot eliminate. **This is why behaviour, not rating, is primary** |
| **Hypothetical decisions** | **Severe** | Disguised but realistic cases; require magnitude, not just direction | Stated intent ≠ executed trade. **The pilot cannot bridge this** |
| **Selection** | High | Balanced tracks; screener; disqualify prior exposure | Volunteers skew favourable |
| **Artificial cases** | High | Composites from real archetypes; withhold outcomes | Six archetypes ≠ a real book |
| **Novelty** | High | Sham control; ask what they'd *remove* | A single session cannot measure durability |
| **Researcher bias** | Medium | Verbatim script; frozen thresholds; two blind coders | Case selection remains an authored choice |
| **No longitudinal use** | Medium | Out of scope; named as a Phase 5 question | Cannot address sustained value |

### What this pilot CAN conclude

- Whether the report changes committed intentions at a **large** rate, net of reconsideration
- Whether abstention is accepted or rejected as an output
- Whether participants can restate the recommendation and its basis
- Whether the absence of a score visibly impairs triage *(exploratory)*
- Whether five qualified people can be recruited at all

### What it CANNOT conclude

- The true decision-change rate to any useful precision
- Whether real trades would differ
- Whether value persists past novelty
- Whether anyone will pay, or how much
- Whether it beats an incumbent tool
- Anything about professionals vs individuals
- Anything about report sections not exercised by these six archetypes

---

## PART 10 — Execution package

### A. Preregistration record

Complete and freeze **before recruitment**: hypotheses (Part 1) · primary outcome and its operational
definition (Part 5) · thresholds (Part 6) · analysis plan (Part 8) · case specifications (Part 4) ·
moderator script (Part 7) · coder identities · time and money cap. **Timestamp, hash, and commit before
the first session.** Any deviation is recorded as a deviation, never as a revised plan.

### B. Screener

1. Do you currently make or materially influence buy/sell/size decisions on an investment portfolio? *(No → disqualify)*
2. Whose capital? *(Own only → Track B; others' → Track A)*
3. How long in that role? *(Track A < 3 yrs, Track B < 5 yrs → disqualify)*
4. Approximate portfolio value? *(Track B < $250k → disqualify)*
5. Roughly how many positions? *(< 10 → disqualify)*
6. Typical holding period? *(< 1 week → disqualify)*
7. Do you follow a written or articulable process for sizing and trimming? *(Describe)*
8. Have you seen any research reports or documents from this project? *(Yes → disqualify)*
9. Do you know the person who built it? *(Yes → disqualify)*
10. Available for 90 minutes, recorded, in the next three weeks? *(No → schedule out or replace)*

### C. Recruitment message

> **Subject: 90 minutes — feedback on portfolio report formats ($100)**
>
> I'm running a small study on how portfolio decision reports are read by people who actually make
> position decisions. I'm looking for five participants who currently manage or materially influence a
> real portfolio.
>
> It's a 90-minute recorded video session. I'll show you several positions and ask what you'd do, then
> show additional material and ask again. There are no right answers, and finding that a format doesn't
> help is as useful to me as finding that it does.
>
> $100 for your time. I'm not selling anything and there's no follow-up unless you want one.
>
> Reply and I'll send five screening questions.

### D. Response form (per case)

**PRE — complete before any additional material**
Case ID ▢ · Action: ADD / HOLD / TRIM / EXIT ▢ · Magnitude (% of portfolio) ▢ ·
Confidence 1–5 ▢ · Main reason (one line) ▢

**POST — complete after**
1. Compared with what you wrote: ▢ **Nothing changed** ▢ Action changed ▢ Size changed ▢ Both changed
2. Action now ▢ · Magnitude now ▢ · Confidence now ▢
3. *(if anything changed)* What led to that? — free text ▢
4. *(if anything changed)* Which parts were relevant? — full section checklist **including "none of these"** ▢
5. Anything not worth reading? ▢

### E. Scoring rubric

| Code | Rule |
|---|---|
| **CHANGE-A** | Action moved between categories |
| **CHANGE-M** | Magnitude moved ≥ 25% relative **or** ≥ 2pp of portfolio |
| **ATTRIB** | A specific section named in Q3 or ticked in Q4 (excluding "none of these") |
| **COUNTED** | (CHANGE-A ∨ CHANGE-M) ∧ ATTRIB |
| **SHAM-CHANGE** | Same rules applied to case 6 |
| **DETECT** | Policy breaches correctly named, pre vs post, against ground truth |
| **ABSTAIN** | ACCEPT / TOLERATE / REJECT on case 5 |
| **COMPREHEND** | CORRECT / PARTIAL / INCORRECT restatement |

Two coders score independently from forms and transcripts, blind to hypotheses. κ reported. Third coder
resolves disagreements.

### F. Analysis template

```
Recruited / qualified / completed:            __ / __ / __
Confirmatory cases scored:                    __ (target 25)
COUNTED cases:                                __ / 25  = ___%
SHAM-CHANGE rate:                             __ / 5   = ___%
NET attributed change rate:                   ___%          ← PRIMARY
Participants with ≥1 COUNTED:                 __ / 5
Distinct sections cited:                      __
Inter-coder κ:                                ___
DETECT pre → post:                            __ → __
ABSTAIN:            ACCEPT __  TOLERATE __  REJECT __
COMPREHEND:         CORRECT __  PARTIAL __  INCORRECT __
Score-arm preference (case 5 vs 7):           __ no-score / __ score / __ indifferent
Unprompted adoption asks:                     __
WTP offered (recorded, not scored):           ______
```

### G. Decision rule

```
IF net_rate ≥ 30% AND participants_with_change ≥ 3 AND distinct_sections ≥ 2   → PASS
ELIF net_rate < 15% OR participants_with_change ≤ 1 OR recruitment failed      → FAIL
ELSE                                                                           → AMBIGUOUS
```

### H. Final recommendation template

> **Phase 1 result: [PASS / AMBIGUOUS / FAIL]**
> Net attributed change rate: __% (threshold 30% / 15%). Participants with ≥1 change: __/5.
> Distinct sections cited: __. Sham baseline: __%. κ: __.
> **Verdict:** [Development authorised at Phase 2 / One follow-up authorised, single change: ____ /
> Project stops; 90-day pause; negative result published]
> **Deviations from preregistration:** [none / list]
> **What we now know that we did not:** ____
> **What remains unknown:** ____

---

## Conclusions

### 1. The single primary hypothesis

> Reading a V3 report changes a portfolio manager's **committed** intended action or magnitude, at a
> rate materially above the rate at which their decision changes on reconsideration with no new
> information.

### 2. Exact pass threshold

**Net attributed change rate ≥ 30%** (≥ 8 of 25 confirmatory cases, sham-adjusted, against a ~60%
design ceiling) **AND ≥ 3 of 5 participants** individually showing ≥ 1 attributed change **AND ≥ 2
distinct report sections** cited.

### 3. Exact kill threshold

**Net attributed change rate < 15%**, **or** ≥ 4 of 5 participants showing zero attributed changes,
**or** failure to recruit five qualified participants within the cap.

### 4. Maximum time and money

**25 engineering/research hours and $500, hard stop.** Breakdown: materials 5 h · recruitment and
screening 6 h · five 90-minute sessions plus notes 10 h · analysis 4 h. Incentives $500 (5 × $100).
**If recruitment has not produced five qualified participants at the 25-hour mark, that is a FAIL and
is reported as one** — inability to reach the user is a finding about the market, not a scheduling
problem.

### 5. The decision under every outcome

| Outcome | Decision |
|---|---|
| **PASS** | Proceed to Phase 2 (policy artifact + Layer 1). No architecture changes. Re-test at Phase 4 |
| **AMBIGUOUS — diffuse across participants** | One follow-up, one pre-declared report-content change, same thresholds, same cap. No architecture change |
| **AMBIGUOUS — concentrated in ≤ 2 participants** | One follow-up with **different participants only**. No content change permitted |
| **AMBIGUOUS — change driven only by the cap breach** | One follow-up with cases 1 and 7 **removed** — test whether anything beyond breach detection moves a decision |
| **FAIL — low change rate** | **Stop.** 90-day pause. Publish the negative result. Resumption needs a new hypothesis and a different sponsor |
| **FAIL — recruitment** | **Stop.** The user could not be reached. Publish |
| **PASS on behaviour, zero WTP** | **Proceed.** WTP is explicitly outside the pass rule; a real commercial test belongs after Phase 2 ships something |
| **High ratings, no behaviour change** | **FAIL.** Report verbatim. Do not reinterpret, do not redesign, do not re-test |

**The last row is the one this study exists to catch, and the one the project's own history predicts.**
