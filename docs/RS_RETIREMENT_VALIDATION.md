# Scientific Validation — Revision: Retire `relative_strength`

One revision, run through the full falsification sequence with a frozen pre-registration and
pre-declared kill criteria. Shadow validation by reconstruction (baseline-7 vs drop-6) on the captured
walk-forward — **no production change, no new model, no weight tuning.**

## Executive summary — should this revision continue?

**Yes, but NOT to production.** Decision: **Collect More Data / Continue Research.** The revision is
supported by a demonstrated root cause and shows a *small, directionally-consistent, harmless* effect
(directional accuracy improves at **every** horizon, +0.004 to +0.013; it does **not** damage the
1-year ranking or calibration). But it **fails the promotion bar**: the 1-month improvement's
block-bootstrap 95% CI **includes zero** (+0.020, CI [−0.005, +0.039]) and reverses in 2 of 5
leave-one-year-out folds. Burden of proof is on the revision; incremental value is *not demonstrated*.
The binding constraint is statistical power (≈31 survivorship-biased names, one 2022–2026 era), not the
hypothesis — so the correct scientific action is more evidence, not promotion and not rejection.

## Stage 1 — Candidate & its demonstrated root cause

- **Weakness:** `relative_strength` is net-negative at 1m (dropping it → 0.513 vs 0.499); standalone
  sub-coin (0.478).
- **Root cause (demonstrated in the root-cause phase, not assumed):** (a) **redundancy** — E2:
  0.37 correlated with momentum, 0.36 with sector (the price cluster); (b) **contrarian-mistiming** —
  E6: its aggregate score correlates −0.287 with SPY's forward return (bullish into tops).
- **Why before every other revision:** it is the *only* candidate whose root cause is empirically
  demonstrated **and** testable now with existing data (a removal — cannot overfit forward; presupposes
  no unresolved question, unlike anything that adds signal to a possibly-beta system).

## Stage 2 — Mechanism

New information introduced: **none — that is the mechanism.** The claim is that removing a redundant,
mildly mistimed copy of price information *reduces variance* in the combination without discarding
unique information. It should matter most at **short horizons** (where the price cluster is noisiest)
and must be **harmless at 1y** (the system's only skill). No production model should meaningfully change
except the loss of a correlated vote.

## Stage 3 — Pre-registration (frozen before the robustness battery)

- **H1:** removing `relative_strength` does not reduce — and weakly improves — OOS directional/rank
  performance, without harming 1y ranking or calibration.
- **H0:** removing it degrades performance (it carries non-redundant value), especially at 1y.
- **Primary metric:** 1m directional-accuracy delta with block-bootstrap CI. **Secondary:** rank
  correlation per horizon (esp. 1y), Brier, leave-one-year-out stability.
- **Promotion threshold:** 1m Δ CI lower bound **> 0** AND 1y rank corr not materially reduced AND
  Brier not worse.

## Stage 3.5 — Pre-registered kill criteria

- **K1:** 1m improvement CI includes 0, or reverses under leave-one-year-out.
- **K2:** 1y rank correlation deteriorates materially (the system's only skill).
- **K3:** calibration (Brier) worsens.

## Stage 4–5 — Shadow results & stress tests

| Horizon | Δ dir-acc (drop−base) | Δ rank-corr | Brier (base→drop) |
|---|---|---|---|
| 1w | +0.004 | +0.014 | 0.315→0.316 |
| 1m | **+0.013** | +0.010 | 0.304→0.303 |
| 3m | +0.007 | +0.011 (turns positive) | 0.314→0.314 |
| 6m | +0.007 | −0.002 | 0.299→0.301 |
| 1y | +0.011 | **−0.004** | 0.280→0.280 |

- **K2 did NOT fire (decisive, and it refutes a prior belief):** removing RS moves the 1y rank
  correlation only 0.172 → **0.168** (−0.004, noise). Its apparent 1y standalone value (E3: +0.072) is
  **redundant** — the other models already carry it. So RS is redundant *even at 1y*; removal is "free."
- **K3 did NOT fire:** Brier unchanged at every horizon — calibration intact.
- **K1 DID fire:** 1m bootstrap Δhit **+0.020, CI [−0.005, +0.039]** (includes 0; 93% of draws
  positive). Leave-one-year-out 1m: +0.027 (2022), −0.011 (2023), +0.024 (2024), −0.005 (2025), +0.048
  (2026) — **positive in 3/5 years, negative in 2.** The improvement is directionally consistent but
  **not statistically robust.**

## Stage 6 — Failure investigation (why it didn't clear the bar)

Not a wrong hypothesis — an **underpowered** one. The effect is small (a variance reduction, not new
alpha), and the sample is small and survivorship-biased (≈31 names, one era). A small true effect on a
small sample yields a CI that straddles zero. The mechanism (redundancy) is confirmed; the *magnitude*
is simply below what this sample can resolve at 95%.

## Stage 7 — Evidence scorecard & decision

| Criterion | Result |
|---|---|
| Root cause confirmed | **Yes** (E2 redundancy + E6 mistiming) |
| Mechanism supported | **Partial-Yes** — redundancy confirmed even at 1y; mistiming small |
| Standalone signal | RS itself is sub-coin (that's the point) |
| Incremental signal | **Weak / not significant** (1m CI includes 0) |
| Orthogonal | N/A (a removal) |
| Robust across regimes/years | **Partial** — 3/5 years positive; both regimes ≈ neutral-positive |
| Survives bootstrap | **No** (1m CI [−0.005, +0.039]) |
| Calibration / 1y ranking preserved | **Yes** (no deterioration) |
| Production worthy | **Not yet — underpowered** |

**Decision (exactly one): COLLECT MORE DATA.** Do **not** promote (incremental value unproven). Do
**not** reject/archive (root cause holds; effect is harmless-to-positive with no downside). The
limiting factor is sample power; widen the universe (survivorship-clean, more names) and lengthen the
history, then re-run the identical pre-registered test.

## Investment Committee memo

> **Recommendation: do not change production; fund more data, not a code change.**
>
> We evaluated retiring `relative_strength`. Its root cause is demonstrated: it is a redundant copy of
> price information (0.36–0.37 correlated with two other models) and is mildly mistimed (bullish into
> market tops). Removing it is *harmless-to-helpful* — directional accuracy rises at every horizon and,
> critically, it does **not** damage our one genuine skill (1-year ranking, unchanged 0.172→0.168) or
> calibration. That result also corrects an earlier belief: RS's long-horizon value is redundant, not
> unique.
>
> **But we cannot promote it.** The improvement is not statistically significant on our current sample
> (1-month CI includes zero; it reverses in two of five years). Under our own standard — *every
> production model must have demonstrated value, and the burden of proof is on the change* — this clears
> neither bar cleanly: RS's value was never demonstrated (argues for removal), yet the removal's benefit
> is not demonstrated either (argues for patience). The honest reading is **underpowered, not wrong.**
> We recommend collecting more data (a wider, survivorship-clean universe) and re-running the identical
> frozen test. This decision is also second-order to the open question of whether our 1-year edge is
> real information or market beta — which should be resolved first.

## Knowledge update

- **Hypothesis tested:** removing `relative_strength` improves OOS performance. **Supported
  directionally, not significantly.**
- **Assumption disproven:** that `relative_strength` contributes *unique* value at 1y. It does not —
  its 1y contribution is redundant (removal barely moves the 1y rank corr). This **weakens** any future
  case for keeping it and **strengthens** the parsimony argument.
- **New understanding:** the three price-cluster models are so correlated that dropping one is nearly
  free at every horizon — the ensemble's information is carried by macro + the *shared* price signal,
  not by having three copies of the latter.
- **Priority shifts:** (a) the small-sample / survivorship problem is now the *binding constraint on
  every incremental test* — expanding the universe is a prerequisite for any promotion decision, not a
  nicety; (b) resolving the 1-year beta-vs-information question remains upstream of everything.
- **Framework validated:** a reasonable, well-motivated, harmless revision was correctly **withheld
  from production** for lack of demonstrated incremental value — exactly the discipline intended.
