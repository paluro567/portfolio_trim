# Final Investment Memorandum — Capital Allocation Review

**To:** Partners
**From:** Chairman, Independent Investment Committee
**Re:** Funding the next phase — and specifically, whether Norgate Data + a Windows VM should be it
**Position:** the committee is allocating **its own** capital and **its own** engineering hours.

---

## RECOMMENDATION (stated first)

# **Option D — abandon the Norgate + Windows VM roadmap.**

Not "delay." **Abandon**, and replace it. The evidence now shows the project's failure is produced by
code in this repository, not by the securities in its sample. A dataset purchase does not address the
measured bottleneck, and the roadmap that has data acquisition as its spine should be retired so it
stops firing by default.

**One-sentence answer to the closing question: No — if I were building this on evenings and weekends,
purchasing Norgate and building a Windows VM would not be the next thing I do, and it would not be the
tenth.**

---

## PART 1 — Reassessment of every major conclusion

| # | Conclusion | Class | Supporting evidence | Contradicting evidence | Remaining uncertainty | Conf. |
|---|---|---|---|---|---|---|
| 1 | The combiner arithmetic is exactly as documented | **Established** | Independent replication to **2.84e-14** over 7,514 cells, cross-validated against shipped code | none | none | 99% |
| 2 | The production ensemble is worse than a constant 50% forecast | **Established** | Brier Δ +0.052 to +0.114; **6 horizons, every CI excluding zero** | none | Panel is 7 survivors | 97% |
| 3 | Scores overstate certainty by ~19 points | **Established** | Implied acc 0.694–0.722 vs realized 0.455–0.514; **+18 to +26 pp at all 6 horizons** | none | Whether it holds on a broader panel | 95% |
| 4 | Equal-weight beat production on **shrinkage**, not information | **Established** | Rescaling dispersion closes **96.3–103.6%** of the gap; ordering agreement ρ 0.89–0.98; sign agreement 91–96% | none | none | 96% |
| 5 | `weight = (z/effect)²`, so weighting ranks by inverse effect size | **Established** | **Spearman = exactly −1.000** across all 6 active models; algebraic identity | none | none | 99% |
| 6 | `valuation` contributes exactly nothing | **Established** | 0.000 activation over 7,938 rows; LOO Δ = 0.0000 with **zero-width CI** | none | none | 99% |
| 7 | Noise amplification is **not** the mechanism | **Established** | Empirical 0.811 vs theoretical 1.732 — the combiner *dampens* | none | 1y only, 1.195 | 95% |
| 8 | Breadth saturates for IC precision | **Established** | 500→5,000 names improves SE by **7.8%**; floor is σ_true/√Y | none | Depends on the variance model being right (see Part 7) | 85% |
| 9 | The 1-year edge is an artifact | **Established** | Drop-3 symbols → IC −0.002; 2025 carries +0.41; every CI includes 0 | none | none | 95% |
| 10 | The failure is data-invariant | **Strongly Supported** | 5 of 11 mechanisms "definitely not changed by data", incl. **both** causal ones | Bearish tilt (M11) is partly data-sensitive | Whether calibration differs on a broad panel | 88% |
| 11 | `interest_rate_sensitivity` is helpful | **Moderately Supported** | Only LOO with CI excluding 0 (−0.0381, [−0.0678, −0.0070]) | **1 of 7 tests, no multiplicity correction** | Would it replicate? | 55% |
| 12 | No exploitable signal exists | **Moderately Supported** | Shrinkage optimum λ=0, **no interior optimum**; dir acc <0.50 at 3 of 6 horizons | Paired designs cannot establish absolute skill; CIs ±0.05 | Real but small effect could hide | 70% |
| 13 | Confidence is reproducibly inverted | **Weakly Supported → effectively refuted** | Original CPE finding (0.529 vs 0.584) | **Did not replicate**: +0.0667 [−0.0628, +0.2029]; sign flips across horizons | Underpowered either way | 20% |
| 14 | `macro_regime` is the only unique predictor | **Weakly Supported** | Realized z-corr −0.003 to −0.130 vs others confirms *uniqueness* | **Worst solo performer**: dir acc 0.4758, Brier 0.3389; LOO −0.0026 (CI includes 0) | Uniqueness ≠ usefulness | 30% |
| 15 | Retiring `relative_strength` would help | **Speculative** | Redundancy confirmed (z-corr +0.513 with momentum) | Removal now leans **negative** (−0.0119) | Undecided after 3 attempts | 25% |
| 16 | σ_true's magnitude | **Unknown** | — | — | **Unidentifiable on the surviving panel** (negative implied variance at all 6 horizons) | 0% |
| 17 | The explainability layer has value | **Unknown** | Elaborate, tested, committed examples | **Never shown to a human** | Everything | 0% |
| 18 | Whether IC serial dependence is annual or monthly | **Unknown** | — | — | Shifts required SE by up to √12 | 0% |

### "What do we actually know now that we did not know three analyses ago?"

Six things, and they are worth more than the roadmap they invalidated:

1. **The failure mechanism is measured, not hypothesised.** `se ≡ |effect/z_raw|` fixes per-model |z|
   near 0.66, producing a ~19-point displacement from neutral; the combiner *transmits* it (0.81x)
   rather than creating it. That is a repository defect, reproducible to 14 decimal places.
2. **The premise that launched two investigations was wrong.** "Equal-weight beats production weighting"
   is not a weighting result — 96–104% of it is one scalar. The two systems rank cells identically
   (ρ 0.89–0.98). We spent two analyses on a weighting question that was a calibration question.
3. **Breadth saturates.** The instinct behind every prior data recommendation — more names, more power —
   is worth **7.8%** from 500 to 5,000 names. The binding constraint is independent *years*, which
   money cannot buy beyond available history.
4. **The prior power arithmetic — including mine, twice — was wrong in method.** The equicorrelation
   discount `n/(1+(n−1)ρ)` is for averaging levels, not for a correlation statistic. Two committee
   recommendations rested on it.
5. **σ_true is the decisive parameter, and nobody had ever named it.** Across its plausible range the
   answer to "would clean data make this decisive?" flips from *comfortably yes* to *unreachable at any
   price*.
6. **The production database is destroyed** — and with it, permanently, the single PIT fundamentals
   snapshot and the immutable prediction archive.

---

## PART 2 — The real bottleneck

| Rank | Bottleneck | Current impact | If solved, improvement | Cost |
|---|---|---|---|---|
| **1** | **Probability generation / calibration** | The only user-facing output is a score that is **19 points too loud** and claims 70% accuracy while delivering 51%. Everything the product says is currently misleading | **Very high.** Converts a broken output into an honest one. An honest "I don't know" is shippable; a confident wrong number is not | ~20 h, $0 |
| **2** | **Data engineering / reproducibility** | **Hard blocker.** The DB is gone; nothing can be run at all. A permanent, realized data loss already occurred | **Absolute** — it gates every other item, including the experiment that could refute this memo | ~25 h, $0 |
| **3** | **Statistical power (σ_true)** | Unmeasured. Determines whether *any* data purchase can ever be decisive | **High** — resolves the central capital question for $0 | ~15 h, $0 |
| **4** | **Product design / explainability value** | Never tested with a human. The largest untested value hypothesis in the project | **High** — may reveal that the actual product is the explanation, not the prediction | ~15 h, $300 |
| **5** | **Validation methodology** | Genuinely strong (PIT poison tests, embargo, pre-registration) — but the shipped `prepare()` scores each system against its own target | Medium — a known defect, already worked around | ~5 h |
| **6** | **Ensemble methodology** | Weighting is provably degenerate (Spearman −1.000) | **Low** — its beneficiary is LOO-harmless. Nothing to weight | — |
| **7** | **Historical data** | Survivorship is real but **does not cause the measured failure** | **Low today** — conditional on #3 | $600+ |
| **8** | **Software architecture** | Excellent. Protocols, guardrails, checksums, 782 tests | ~Zero | — |
| **9–12** | Model quality, feature engineering, confidence *ordering*, portfolio simulation | All downstream of #1–#3 | ~Zero today | — |

**The bottleneck is calibration, sitting behind a data-engineering blocker.** Not data. Not models. Not
weighting.

---

## PART 3 — Decision tree, rebuilt from scratch

Root: *what is the highest expected-value next investment?*

```
Is the platform able to run an experiment at all?
│
├── NO (current state: database destroyed) ──► REBUILD THE DATA LAYER. Nothing else is reachable.
│                                              Everything below is gated on this.
▼ (once runnable)
Is the system's OUTPUT honest?
│
├── NO (measured: +18-26pp overclaim, data-invariant) ──► FIX CALIBRATION FIRST.
│      Independent of signal. Independent of data. Cheapest high-value item in the project.
▼
Can ANY dataset make the absolute-signal question decisive?
│
├── UNKNOWN (sigma_true unmeasured) ──► MEASURE sigma_true ON A FREE BROAD PANEL. $0.
│      │
│      ├── sigma_true >= 0.15 ──► No affordable dataset reaches the threshold.
│      │                          NEVER buy data for prediction research. Stop that program.
│      │
│      └── sigma_true <= 0.10 ──► A 200-500 name x 20y clean dataset IS decisive.
│                                 Re-open the vendor question THEN, REST-native only.
▼
Does the project have value independent of prediction?
│
├── UNTESTED ──► HUMAN EVALUATION of the explainability layer. Largest untested hypothesis.
│      ├── YES ──► the product is the explanation. Prediction becomes optional.
│      └── NO  ──► combined with a negative signal result: terminate.
▼
NOT ON THE TREE AT ANY NODE:
   Windows VM (zero scientific content at every node)
   Parallels (same)
   Norgate specifically (a vendor choice, downstream of a gate not yet passed)
   New models, new features (three unmet gates deep)
   Portfolio simulation (its ledger is destroyed; nothing to simulate)
```

---

## PART 4 — Expected value of every candidate

Ranked by return per engineering hour. "P(change)" = probability of materially changing the project's
direction.

| Rank | Investment | Hrs | Cash | Sci. uncertainty ↓ | Product value | Learning | P(change) | Return/hr | Return/$ |
|---|---|---|---|---|---|---|---|---|---|
| **1** | **Rebuild data layer + backups** | 25 | $120 | Enabling (gates all) | Medium | Medium | **1.00** (blocker) | **Very high** | Very high |
| **2** | **Measure σ_true (broad free panel)** | 15 | $180 | **~85%** on the capital question | Low | High | **0.45** | **Very high** | High |
| **3** | **Calibration diagnosis + honest presentation** | 20 | $0 | ~60% on output honesty | **Very high** | High | 0.30 | **Very high** | ∞ |
| **4** | **Human evaluation of explainability** | 15 | $300 | ~80% on U3 | **Very high** | Very high | **0.40** | High | High |
| 5 | Statistical recalibration of per-model `se` | ~30 | $0 | Medium | Medium | High | 0.25 | Medium | ∞ |
| 6 | Simpler ranking system (drop the combiner) | ~20 | $0 | Low | Medium | Medium | 0.20 | Medium | ∞ |
| 7 | Better validation (fix `prepare()` target) | ~5 | $0 | Low | Low | Medium | 0.10 | Medium | ∞ |
| 8 | REST-native data provider | ~60 | ~$700 | Medium — **conditional on #2** | Low | Medium | 0.30 | Low | Low |
| 9 | **Purchase Norgate** | ~70 | ~$630 | Medium — conditional on #2 | Low | Low | 0.25 | **Low** | **Low** |
| 10 | Portfolio simulation | ~40 | $0 | ~0 | Low | Low | 0.05 | Very low | — |
| 11 | Larger free historical dataset (beyond σ_true) | ~30 | $0 | **~7.8%** (saturation) | ~0 | Low | 0.05 | Very low | — |
| 12 | **Build/maintain Windows VM** | ~15 + ongoing | ~$240 | **0%** | 0 | Low | **0.00** | **Zero** | **Negative** |
| 13 | New models / features | months | $0 | ~0 (3 gates unmet) | ~0 | Medium | 0.05 | Negative | — |
| 14 | Stop prediction research | 0 | $0 | 0 | 0 | 0 | 0.30 | — | — |

**Items 1–4 cost 75 hours and $600, are all $0-to-low risk, and include the one experiment most likely
to refute this memo.**

---

## PART 5 — The Norgate decision

| | **A: Norgate + VM now** | **B: Norgate, VM later** | **C: Delay both** | **D: Abandon the roadmap** |
|---|---|---|---|---|
| Scientific value | Low — addresses a bottleneck measured *not* to be the bottleneck | Low — same | Medium | **Medium-high** — redirects to the measured bottleneck |
| Engineering value | **Negative** — a hand-maintained VM sits outside the test suite and weakens the reproducibility discipline that is this platform's best asset | Neutral | Medium | **High** — rebuild + calibration are durable |
| Product value | ~0 | ~0 | Medium | **High** — honest output + tested explainability |
| Career/learning value | Low (VM sysadmin) | Low-medium | Medium | **High** — calibration, power analysis, user research are transferable |
| Cash | ~$870 | ~$630 | $0 | $0 now; $400 escrowed against a trigger |
| Engineering effort | **~105 h — exceeds the entire budget** | ~90 h | ~40 h | ~75 h |
| Risk | **High** — spends everything on an unmeasured gate | High | Low | **Low** |
| Opportunity cost | **Total** — nothing else gets done | Near-total | Low | Low |
| Confidence | 15% | 20% | 70% | **80%** |

### Recommendation: **Option D.**

### Why D dominates each alternative

**Over A.** A costs ~105 engineering hours against a 100-hour budget and ~$870 of $1,000, and buys
zero movement on the measured bottleneck. The two mechanisms that fully explain the ensemble failure —
`se ≡ |effect/z|` and the aggregation space — are a formula and an inequality. They produce identical
results on any dataset. A is not merely lower-EV; it is the single allocation that guarantees nothing
else happens.

**Over B.** B removes the VM's cost but keeps the premise: that the next thing this project needs is
better outcome data. That premise has now been *tested* and found false for the failure at hand. B also
fires before σ_true is measured, i.e. it buys a dataset without knowing whether any dataset can reach
the required precision — and per the saturation result, the honest answer may be *none can*.

**Over C.** C is operationally close to D for six months, and this is the closest call in the memo. It
loses on **governance**. A "delay" keeps the purchase on the books as the default destination, and this
project has defaulted toward data acquisition in three consecutive reviews — including twice on
arithmetic now known to be wrong. **D forces any future purchase to re-earn its place against a
specific measured trigger (σ_true ≤ 0.10) rather than resuming by inertia.** Killing a bad default is
worth more than deferring it.

**A note on what D does not say.** D abandons *this roadmap* — Norgate as the organizing next step, and
the Windows VM permanently. It does not forbid ever buying data. It says the trigger is σ_true, the
vendor must be REST-native, and neither question is open today.

---

## PART 6 — Opportunity cost if Option A were chosen

**Cash:** ~$630 Norgate + ~$100 Parallels + ~$140 Windows = **~$870 of $1,000** (87%).
**Hours:** VM setup ~15 + adapter ~40 + ingest & validate ~30 + study run ~20 = **~105 of 100** (105%).

**Option A consumes the entire budget and overruns it.** Precisely what would not get done:

| Not done | Hours lost | Consequence |
|---|---|---|
| Data-layer rebuild | 25 | The platform stays unable to run **any** experiment — including the Norgate study itself, which needs the rebuilt schema |
| σ_true measurement | 15 | The purchase proceeds without knowing whether it can reach the required precision. Per the saturation result, at σ_true ≥ 0.15 **no** dataset can |
| Calibration fix | 20 | The scores stay 19 points too loud. **The study runs on the same broken output** |
| Human evaluation | 15 | The largest untested value hypothesis stays untested for another cycle |
| Backups | 10 | A project that has *already* permanently lost data remains unprotected |

**Six months later, under A:** survivorship-clean outcomes joined to an ensemble that still loses to a
constant 50% forecast — because the reason it loses is data-invariant. You would know the no-signal
verdict more precisely (if σ_true happened to cooperate), and you would still not know whether the
reporting layer is worth anything, whether calibration is fixable, or whether any dataset could have
been decisive.

**Six months later, under D:** a rebuilt and backed-up platform; a measured σ_true that either unlocks
or permanently closes the data question; an honest score; and a tested answer on whether the project has
a product at all. Roughly **four resolved unknowns versus one**, at **zero** incremental cash.

---

## PART 7 — Red team: the case against this memo

### The three strongest arguments against me

**1. The entire diagnosis rests on 7 survivor names, 6 of them large-cap tech.**
Every root-cause number — the +19-point overclaim, the 96–104% shrinkage decomposition, Spearman
−1.000 — comes from one narrow panel. Per-model `z` calibration could plausibly be panel-specific: on
a broad, diverse universe the models might be far better calibrated, and the "data-invariant" claim
would collapse into "we measured a quirk of six tech stocks." **I have never tested calibration on
anything else.** This is the most dangerous hole in the memo.

**2. Fixing calibration may produce a rigorous way of saying nothing.**
If the honest output is 50 everywhere, the product value I assign to item #3 is illusory. The bull case
for buying data is that it is the only route to a system that says something *and* is right.
Optimising the honesty of a worthless output could be the highest-quality waste of time available.

**3. My power model could be wrong again — I have already been wrong once on this exact calculation.**
The breadth-saturation result depends on treating date-level ICs as independent only across **annual**
blocks. If they are closer to independent monthly, SE at 500×20 drops toward 0.0065 and the purchase is
comfortably decisive. I misapplied the equicorrelation discount twice before catching it. A second
error in the opposite direction is entirely plausible, and it would reverse Part 5.

### Evidence that most threatens the recommendation

A σ_true measurement returning **≤ 0.05**, combined with evidence that IC serial dependence is closer to
monthly than annual. That combination makes a ~200-name × 20-year clean dataset decisive and cheap, and
converts Option D into a sequencing error.

### Assumptions least certain / never tested

| Assumption | Status |
|---|---|
| σ_true magnitude | **Never measured** — unidentifiable at 7-name breadth |
| IC serial dependence (annual vs monthly) | **Never tested.** Shifts the required SE by up to √12 |
| Per-model calibration generalises beyond 7 tech names | **Never tested** |
| The explainability layer has value | **Never tested** in the project's entire history |
| Engineering time is genuinely scarce here | **Never answered** — I asked; it remains open, and it is the premise of every opportunity-cost argument in this memo |

### The experiment that would most quickly prove me wrong

**Measure σ_true and the IC autocorrelation structure on a broad free panel — 15 hours, $0.**

Note this is **funded as item #2 in Part 9.** The committee is deliberately paying for the experiment
most likely to refute its own recommendation, and doing it before any irreversible spend. That is the
point of the allocation, not an accident of it.

---

## PART 8 — What would change my mind

| Recommendation | Exact trigger that reverses it |
|---|---|
| **Abandon Norgate roadmap** | σ_true ≤ 0.10 **and** IC autocorrelation consistent with ≥ 6 effective blocks/year ⇒ a ~200–500 name × 20y clean dataset reaches SE ≤ 0.02 ⇒ **re-open the vendor question immediately** (REST-native first) |
| **Abandon Norgate roadmap** | Per-model calibration measured on a ≥ 200-name free panel shows implied-vs-realized gap < 5 pp ⇒ the overconfidence was a 7-name artifact ⇒ the "data-invariant" claim fails and data returns to the top of the ranking |
| **Never build the Windows VM** | **No realistic evidence reverses this.** The VM has zero scientific content at every node of the decision tree; it is a delivery mechanism for one vendor, and a research corpus is built once. If Norgate ever became uniquely necessary, a **one-time ~$20 cloud instance** for bulk export satisfies the requirement without a maintained VM. There is no future state in which *maintaining* a VM is the scientifically correct choice |
| **Calibration first** | Human evaluation shows users ignore the numeric score entirely and read only the narrative ⇒ calibration drops below explainability in priority |
| **Fund human evaluation** | Two consecutive evaluators cannot articulate any decision the report changed ⇒ stop; U3 resolved negative |
| **Stop funding model/feature work** | A signal is validated on clean data with a CI excluding zero ⇒ the freeze lifts immediately |
| **Rebuild the data layer** | Nothing. It is an unconditional blocker |

---

## PART 9 — Capital allocation: 100 hours, $1,000

### Engineering hours

| Hrs | Allocation | Expected return | Risk | Why it beat the alternatives |
|---|---|---|---|---|
| **25** | **Rebuild the data layer** — re-ingest ~500 names of prices + FRED macro into the surviving 16-migration schema; verify the rebuild reproduces the archived captures | Enabling. Gates 100% of everything else | Low — schema and ingestion code survive | It is not an investment, it is a precondition. No other hour can be spent until these are |
| **20** | **Calibration diagnosis + honest score presentation** — per-model implied-vs-realized curves; shrink or suppress the displayed score | Converts a misleading output into an honest one. **The only item that improves the product today regardless of signal** | Low | Highest product value per hour in the project, $0, data-invariant, and measured with CIs excluding zero at 6 horizons |
| **15** | **Measure σ_true + IC autocorrelation** on the rebuilt broad panel | Resolves the central capital question for $0; **most likely single experiment to refute this memo** | Low | Decides a ~$700 purchase and a ~60-hour build before either is committed |
| **15** | **Human evaluation of the explainability layer** — structured sessions, decision recorded before and after reading | Tests the largest untested value hypothesis in the project's history | Medium — small n, possible politeness bias (mitigated by paying) | Three consecutive reviews flagged this as the biggest blind spot and it has never been touched |
| **10** | **Reproducibility insurance** — automated backup of DB + validation artifacts; restore drill | Protects every other hour | Very low | The project has *already* permanently lost a PIT fundamentals snapshot and its prediction archive. This is a realized loss, not a hypothetical |
| **15** | **Contingency** | — | — | The rebuild will surface surprises; every honest plan carries slack. Unallocated slack is a lie, allocated slack is a plan |
| **100** | | | | |

### Cash

| $ | Allocation | Expected return | Risk | Why it beat the alternatives |
|---|---|---|---|---|
| **$300** | **Human-evaluation incentives** — 3 finance-literate evaluators, ~1 structured hour each | Tests whether the project has a product at all | Medium | Paying buys *honest* feedback instead of polite feedback. The highest-EV discretionary dollar available |
| **$180** | **Cloud compute** — broad-panel rebuild, σ_true bootstrap, walk-forward at scale | Removes the 22x compute wall; keeps the local DB unwedged | Low | The scaling cost was always the real budget item, not the subscription |
| **$120** | **Offsite automated backup** (12 months) | Insurance on 100% of remaining work | Very low | The single highest-confidence dollar in this memo. The loss it prevents has already occurred once |
| **$400** | **Conditional data escrow** — released **only** on σ_true ≤ 0.10, to a **REST-native** survivorship-clean vendor | Preserves the option without funding the premise | Low | Allocated to a named trigger, not to a vendor. If the trigger never fires the money is never spent — which is the correct outcome, not a failure of allocation |
| **$1,000** | | | | |

**Explicitly $0 to:** Norgate, Parallels, Windows licences, additional models, additional features,
portfolio simulation.

---

## PART 10 — Investment memorandum

### 1. What has actually been proven?

That the platform's arithmetic is exactly as documented (replication to 2.8e-14); that the production
ensemble is **worse than a constant 50% forecast at all six horizons with every CI excluding zero**;
that its scores claim ~70% accuracy while delivering ~51%; that equal-weight's apparent victory was
**96–104% shrinkage** and the two systems rank cells identically (ρ 0.89–0.98); that
`weight = (z/effect)²` ranks models by inverse effect size (**Spearman exactly −1.000**); that
`valuation` contributes provably nothing; and that IC precision **saturates in breadth** — 10x the names
buys 7.8%.

### 2. What has been disproven?

That the ensemble has predictive value. That the weighting was the problem. That noise amplification
was the mechanism (the combiner *dampens*, 0.81 vs a theoretical 1.73). That redundancy
under-declaration caused the overconfidence (errors run both ways; the largest is an *over*-statement).
That the one-year edge was real. That confidence is reproducibly inverted (it did not replicate). That
`macro_regime` is a useful unique predictor (unique, yes; worst solo performer). And — most expensively
— **that buying more names is the route to statistical power.**

### 3. What remains unknown?

σ_true. The serial dependence of date-level ICs. Whether any signal exists at all. Whether per-model
calibration generalises past 7 tech names. Whether the explainability layer has any value. And whether
engineering time here is genuinely scarce — the premise underneath every opportunity-cost argument in
this memo, which I have asked about and which remains unanswered.

### 4. What is the project's biggest bottleneck?

**Probability generation and calibration**, sitting behind a **data-engineering blocker** (the destroyed
database). Not data. Not models. Not weighting.

### 5. Is purchasing Norgate justified today?

**No.** It does not address the measured bottleneck; the two mechanisms that fully explain the failure
are a formula and an inequality that produce identical results on any dataset. And it would fire before
σ_true is measured — the parameter that determines whether *any* dataset can reach the required
precision.

### 6. Is setting up and maintaining a Windows VM scientifically justified today?

**No — and not on any future date either.** It carries zero scientific content, it is a delivery
mechanism for one vendor, a research corpus is built once rather than streamed, and a maintained VM sits
outside the test suite, weakening the reproducibility discipline that is this platform's genuinely
best asset. If that vendor ever became uniquely necessary, a one-time ~$20 cloud instance for bulk
export satisfies the need.

### 7. What should replace that investment?

Rebuild the data layer, make the output honest, measure σ_true, and find out whether anyone values the
explanations. Four resolved unknowns instead of one, at zero incremental cash.

### 8. How should the next 100 engineering hours be spent?

25 rebuild · 20 calibration · 15 σ_true · 15 human evaluation · 10 backups · 15 contingency.

### 9. How should the next $1,000 be spent?

$300 evaluator incentives · $180 cloud compute · $120 offsite backup · $400 escrowed against σ_true ≤ 0.10.

### 10. If this were my own money and my own weekends, what exactly would I do next?

Rebuild the database and set up backups — because right now the project cannot run a single experiment
and has already lost data permanently. Then, in the same sitting, plot implied accuracy against realized
accuracy per model, and shrink the displayed score until it stops lying. Then measure σ_true and let that
one number decide, permanently, whether this project ever buys data. Then show the reports to three
people who invest their own money and write down what they actually did differently.

I would not open a vendor website. I would not install Parallels.

---

### Allocation summary

| Priority | Investment | Hours | Cash | Expected ROI | Confidence | Reason |
|---|---|---|---|---|---|---|
| **1** | Rebuild data layer + reproducibility | 25 | $120 | **Enabling — gates 100%** | 95% | The platform cannot run any experiment; data has already been permanently lost |
| **2** | Calibration: honest score presentation | 20 | $0 | **Very high** | 90% | +18–26 pp overclaim at 6 horizons, CIs excluding zero; data-invariant; the only item improving the product today |
| **3** | Measure σ_true + IC autocorrelation | 15 | $180 | **Very high** | 85% | Decides a ~$700 purchase and a ~60 h build for $0 — and is the experiment most likely to refute this memo |
| **4** | Human evaluation of explainability | 15 | $300 | **High** | 65% | Largest untested value hypothesis in the project's history |
| **5** | Contingency | 15 | $0 | — | — | The rebuild will surface surprises |
| **6** | Conditional data escrow | 0 | $400 | Conditional | 40% | Released only on σ_true ≤ 0.10, REST-native vendor only |
| **7** | Norgate subscription | **0** | **$0** | Low | 15% | Does not address the measured bottleneck; premature to an unmeasured gate |
| **8** | Windows VM / Parallels | **0** | **$0** | **Zero** | 95% | Zero scientific content at every node; weakens reproducibility; a one-time cloud export dominates it |
| **9** | New models / features | **0** | **$0** | Negative | 90% | Three unmet gates deep; ~0% historical promotion rate |
| | **Total** | **100** | **$1,000** | | | |

---

### Closing question

> *"If you were personally building this project on evenings and weekends, would purchasing Norgate data
> and building a Windows VM be the next thing you do?"*

# **No.**

The project's scores are provably 19 points too loud, its database is gone, and the one number that
decides whether any dataset could ever help has never been measured. I would fix the honesty, restore
the platform, and measure that number — and I would let it, not a vendor's catalogue, decide what comes
next.

**What reverses this:** σ_true ≤ 0.10 with IC autocorrelation consistent with ≥ 6 effective blocks per
year, **or** per-model calibration on a ≥ 200-name panel showing an implied-vs-realized gap under 5 pp.
Either result puts data back at the top of the ranking within the week. The Windows VM stays rejected
regardless.
