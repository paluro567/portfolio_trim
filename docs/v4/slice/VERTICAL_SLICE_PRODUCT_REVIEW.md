# Vertical Slice — Product Usefulness Review

Evaluated as the portfolio owner, not as the engineer.

## Does it surface information that could change a real decision?

**Partly.** Three things earn their place:

- **+33.75% unrealised on AMZN ($5,170 on a $15,321 basis).** A fact worth knowing before trading, computed from the user's own cost and the repository's price.
- **`rel_ret_spy_63d = −6.97%`** — this position has *underperformed SPY* over three months despite the market being in a bull regime (`regime_bull = 1.0`) with VIX at its **19th percentile**. That combination is genuinely decision-relevant and is not obvious from a broker screen.
- **Options exposure is understated.** The report says outright that an AMZN call is excluded from the schema. Discovering that from raw data would take real effort.

## Does it distinguish portfolio risk from directional attractiveness?

**Yes — this is the part that works best.** The directional view is NEGATIVE at four of five horizons; the action is ABSTAIN at all five. The report never lets a weak directional reading masquerade as a portfolio instruction, and the elimination trace names the exact missing input blocking each alternative.

## Does it expose important missing information?

**Yes, and unusually well.** Five UNAVAILABLE evidence items, four NOT_EVALUABLE constraints, and two missing portfolio inputs, each with a reason. Section 20 ranks what would change the answer. Nothing is silently defaulted.

## Is the recommendation traceable?

**Yes.** Every input is in `inputs.json` with the source CSV's sha256 and the commit; the report is byte-reproducible; the elimination trace is generated from the same code path that produced the decision, not narrated afterward.

## Is any section pretending to know more than it does?

**No — and I looked hard.** Historical distributions carry four explicit caveats (PIT, survivorship, holdings-based universe selection, overlapping windows). Percentile readings state the base rate. Confidence is capped at LOW with the reasons enumerated. The report states plainly that **no item is VALIDATED**.

The one place worth watching: `forward_return_1y` shows *median +27.95%, positive 86%*. That is arithmetically correct for AMZN 2010–2026, and it is the most seductive number in the report. It is labelled DESCRIPTIVE with survivorship and selection caveats attached — but a reader in a hurry could still misread it as a forecast.

## Is it materially better than reviewing raw data manually?

**Yes, but narrowly.** The consolidation is real — position economics, technical percentiles, regime, and a complete missing-data inventory in one deterministic artifact. The manual equivalent is perhaps 20 minutes of work per holding and would probably omit the options-exposure gap.

## Would it be worth opening before making a trade?

**Yes — once.** It would tell you what you own, what has happened, and precisely what the system cannot tell you. It would not tell you what to do.

---

## Verdict: **PARTIALLY USEFUL**

## Single biggest reason it is not more useful

**No `PolicyArtifact` exists.** Every one of the four deterministic constraints returns `NOT_EVALUABLE` for the same reason: there is no target weight, no hard cap, no gains budget. That single absence is what forces ABSTAIN at all five horizons, and it is why the report can describe the position but never act on it.

Cost-basis weight is already computed — **9.04% of 52 positions**. One number, a hard cap, would turn that from a fact into an evaluable constraint and let the action move off ABSTAIN. It is a *policy* input, not an engineering problem: it requires the owner to state a limit, not the system to compute one.

Second-largest: **tax lots**. Even with a breached cap, TRIM cannot be justified without knowing the tax cost of selling.
