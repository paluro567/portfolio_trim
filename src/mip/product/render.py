"""Deterministic Markdown renderer for the V4 vertical slice."""

from __future__ import annotations

from mip.product.contracts import (
    Constraint,
    Evidence,
    HorizonVerdict,
    PositionState,
    Status,
)

DISCLOSURE = (
    "Confidence is an experimental evidence-quality assessment, not a probability "
    "of being correct."
)


def fmt_pct(v) -> str:
    return "unavailable" if v is None else f"{v:.2%}"


def _money(v) -> str:
    return "unavailable" if v is None else f"${v:,.2f}"


def _sec(n: int, title: str) -> str:
    return f"\n## {n}. {title}\n"


def render(
    pos: PositionState,
    evidence: list[Evidence],
    constraints: list[Constraint],
    verdicts: list[HorizonVerdict],
    meta: dict,
) -> str:
    lines: list[str] = []
    add = lines.append

    add(f"# {pos.symbol} — Portfolio Decision Support")
    stale = ""
    if pos.price_date is not None and (pos.as_of - pos.price_date).days > 1:
        stale = (
            f" **Price is {(pos.as_of - pos.price_date).days} calendar days stale** "
            f"(last close {pos.price_date.isoformat()})."
        )
    add(
        f"\n*As of {pos.as_of.isoformat()}. Generated from repository data at "
        f"commit `{meta['commit']}`. Latest price date {pos.price_date or 'unavailable'}; "
        f"latest observed data {meta.get('feature_date', 'unavailable')}.*{stale}"
    )
    add(
        f"\n> **{DISCLOSURE}** This report contains no probability estimate, no expected "
        f"return, and no predictive score. Directional readings are EXPERIMENTAL: no "
        f"predictive reliability has been established for any signal used here."
    )

    add("\n## 1b. Data freshness\n")
    add("| Field | Value |")
    add("| --- | --- |")
    add(f"| AS-OF DATE | {pos.as_of.isoformat()} |")
    add(f"| LATEST SECURITY PRICE | {pos.price_date or 'unavailable'} |")
    add(f"| LATEST FEATURE / OBSERVED DATA | {meta.get('feature_date', 'unavailable')} |")
    _age = (pos.as_of - pos.price_date).days if pos.price_date else None
    add(f"| DATA AGE | {'unavailable' if _age is None else f'{_age} calendar day(s)'} |")
    _fresh = (
        "UNKNOWN"
        if _age is None
        else (
            "CURRENT"
            if _age <= 1
            else (
                "STALE - 1W reading is weakened"
                if _age <= 4
                else "BLOCKING - 1W evidence is too old to support a 1-week view"
            )
        )
    )
    add(f"| FRESHNESS STATUS | **{_fresh}** |")
    if _age is not None and _age > 4:
        add(
            "\n> **1W caution.** The latest price is more than four calendar days old. "
            "Treat the 1-week row as unsupported until prices are refreshed."
        )

    # 2 executive summary
    add(_sec(2, "Executive summary"))
    acts = {v.action for v in verdicts}
    add(
        f"Across all five horizons the recommended action is "
        f"**{' / '.join(sorted(a.value for a in acts))}**."
    )
    add(f"\n{verdicts[0].rationale}")
    add(
        f"\nPosition: **{pos.quantity} shares at ${pos.average_cost} average cost** "
        f"(cost basis {_money(pos.cost_basis)}). Market value {_money(pos.market_value)}; "
        f"unrealised "
        f"{_money(pos.unrealized_pnl)}"
        f"{f' ({pos.unrealized_pct:+.2%})' if pos.unrealized_pct is not None else ''}."
    )

    # 3-5 by horizon
    add(_sec(3, "Action, directional view and confidence by horizon"))
    add("| Horizon | 1. Security / directional view | 2. Portfolio action | Evidence strength |")
    add("| --- | --- | --- | --- |")
    for v in verdicts:
        add(
            f"| {v.horizon} | {v.direction.value} | **{v.action.value}** | "
            f"{v.confidence.value} (experimental) |"
        )
    add(
        "\nColumn 1 is the view on the *security*. Column 2 is what to do about the "
        "*position*. They are computed separately; portfolio weight cannot reach column 1."
    )
    add(f"\n*{DISCLOSURE}*")

    # 6 position state
    add(_sec(6, "Current position state"))
    add("| Field | Value | Kind |")
    add("| --- | --- | --- |")
    add(f"| Quantity | {pos.quantity} | fact (broker export) |")
    add(f"| Average cost | ${pos.average_cost} | fact (broker export) |")
    add(f"| Cost basis | {_money(pos.cost_basis)} | calculation |")
    add(f"| Market price | {_money(pos.market_price)} | fact (daily_prices, {pos.price_date}) |")
    add(f"| Market value | {_money(pos.market_value)} | calculation |")
    add(
        f"| Unrealised P&L | {_money(pos.unrealized_pnl)}"
        f"{f' ({pos.unrealized_pct:+.2%})' if pos.unrealized_pct is not None else ''} | "
        "calculation |"
    )
    add(
        f"| **Market-value weight** | "
        f"{fmt_pct(pos.market_weight)} of "
        f"{_money(pos.portfolio_market_value)} portfolio | **calculation** |"
    )
    add(
        f"| Cost-basis weight | "
        f"{f'{pos.cost_weight:.2%}' if pos.cost_weight is not None else 'unavailable'} "
        f"of {pos.portfolio_positions} positions | calculation |"
    )

    # 7 portfolio context
    add(_sec(7, "Portfolio context"))
    add(
        f"Portfolio holds **{pos.portfolio_positions} positions**. This holding is "
        f"{f'{pos.cost_weight:.2%}' if pos.cost_weight is not None else 'an unavailable share'} "
        f"of total **cost basis**."
    )
    add("\n**Unavailable portfolio inputs:**\n")
    for u in pos.unavailable:
        add(f"- {u}")

    add("\n**Portfolio concentration effect on the recommendation**\n")
    v0 = verdicts[0]
    sizing = v0.rationale.split("implies", 1)[-1]
    add(sizing.split(".", 1)[-1].strip() if "." in sizing else sizing.strip())

    pol = meta.get("policy") or {}
    if any(v.action.value == "ADD" for v in verdicts):
        add(
            "\n> **ADD is not directly actionable.** The holdings file records positions "
            "only; it carries no cash balance, so available capital is unknown. Read ADD "
            "as *the security evidence would support increasing exposure*, not as an "
            "instruction that funds exist to do so."
        )

    add("\n**Portfolio policy**\n")
    if pol.get("status") == "SUPPLIED":
        add(
            f"- Supplied by the portfolio owner. Version `{pol['policy_version']}`, "
            f"effective {pol['effective_date']}, source `{pol['source']}`."
        )
        add(
            f"- Hard cap **{pol['hard_cap_pct']}%** of portfolio market value; "
            f"core target **{pol['core_target_pct']}%**."
        )
    else:
        missing = ", ".join(pol.get("missing", []))
        template = pol.get("path", "config/policy/personal.yaml")
        add(f"- **NOT SUPPLIED.** {pol.get('reason', 'no policy loaded')}")
        add(f"- Required and unset: {missing}")
        add(f"- Template awaiting the owner's values: `{template}`")
        add(
            "- The system does not invent position limits. Until these are supplied, "
            "policy-dependent constraints stay NOT_EVALUABLE, no hard-cap breach can "
            "be detected, and concentration can only suppress ADD - never force TRIM."
        )

    # 8-15 evidence by domain
    order = [
        (8, "Market and regime context", "market/regime"),
        (8.5, "Sector context", "sector"),
        (9, "Company evidence", "company"),
        (10, "Fundamental and earnings evidence", "fundamentals"),
        (11, "Valuation evidence", "valuation"),
        (12, "Catalyst evidence", "catalysts"),
        (13, "Price and technical evidence", "price/technical"),
        (14, "Historical evidence", "historical"),
    ]
    for n, title, dom in order:
        add(_sec(n, title))
        items = [e for e in evidence if e.domain == dom]
        if dom == "fundamentals":
            items += [e for e in evidence if e.domain == "earnings"]
        if dom == "company":
            items = [e for e in evidence if e.domain == "fundamentals"][:3]
        if not items:
            add("**UNAVAILABLE** — no evidence of this domain is implemented in this slice.")
            continue
        avail = [e for e in items if e.status is not Status.UNAVAILABLE]
        if not avail:
            add("**UNAVAILABLE**\n")
            for e in items:
                add(f"- `{e.name}` — {e.missing_reason}")
            continue
        add("| Item | Status | Observed | As of | Horizons | Reading |")
        add("| --- | --- | --- | --- | --- | --- |")
        for e in avail:
            add(
                f"| `{e.name}` | {e.status.value} | {e.value} | {e.as_of} | "
                f"{', '.join(e.horizons)} | {e.direction.value} |"
            )
        for e in avail:
            add(f"\n- **`{e.name}`** — {e.explanation}")
            add(f"  - *Limitations:* {e.limitations}")
        miss = [e for e in items if e.status is Status.UNAVAILABLE]
        if miss:
            add("\n**Unavailable in this domain:**\n")
            for e in miss:
                add(f"- `{e.name}` — {e.missing_reason}")

    # 15 analogues
    add(_sec(15, "Historical analogues"))
    add(
        "**UNAVAILABLE.** The analogue engine is a SHADOW component excluded from the "
        "product decision path, and the Arm 2 readiness review established that its "
        "feature-consumer structure could not be validated. Not used."
    )

    # 16 risk
    add(_sec(16, "Risk factors"))
    add("| Risk | Status | Note |")
    add("| --- | --- | --- |")
    add("| Concentration | UNAVAILABLE | market-value weight not computable |")
    add("| Liquidity | UNAVAILABLE | average daily volume not wired into this slice |")
    add("| Event risk | UNAVAILABLE | no earnings or catalyst data |")
    add(
        "| Undisclosed exposure | **MATERIAL** | the broker export excludes listed options; "
        "`data/unsupported_positions_2026-07-16.csv` records an AMZN call position that is "
        "**not** represented here, so true exposure is understated |"
    )

    # 17 constraints
    add(_sec(17, "Deterministic constraints"))
    add("| Constraint | Status | Observed | Threshold | Reason |")
    add("| --- | --- | --- | --- | --- |")
    for c in constraints:
        add(f"| {c.name} | **{c.status.value}** | {c.observed} | {c.threshold} | {c.reason} |")

    # 18-19 why / why not
    add(_sec(18, "Why this action"))
    for v in verdicts:
        add(f"\n**{v.horizon} — {v.action.value}.** {v.rationale}")
        if v.contributing:
            add(f"\n  Directional evidence considered: {'; '.join(v.contributing)}.")
        if v.conflicts:
            add(f"\n  Conflicts: {'; '.join(v.conflicts)}.")
        add(f"\n  Confidence basis: {'; '.join(v.confidence_basis)}.")

    add(_sec(19, "Why not the alternative actions"))
    for v in verdicts:
        add(f"\n**{v.horizon}**\n")
        for act, why in v.eliminations:
            add(f"- **{act} rejected** — {why}")

    # 20 what would change it
    add(_sec(20, "What would change this recommendation"))
    add(
        "1. **A PolicyArtifact with position limits.** This is the single largest gap. "
        "With a target weight and a hard cap, concentration becomes evaluable and the "
        "action can move off ABSTAIN."
    )
    add(
        "2. **Tax lots with acquisition dates.** Without them the cost of trimming is "
        "unknown, so TRIM cannot be justified even if a constraint were breached."
    )
    add(
        "3. **Prices for every held position**, making total portfolio market value and "
        "therefore true market-value weight computable."
    )
    add(
        "4. **Options exposure represented in the schema**, so the AMZN call is included "
        "in exposure rather than silently excluded."
    )
    add(
        "5. **Point-in-time fundamentals**, which would activate the valuation, earnings "
        "and fundamentals sections."
    )

    # 21 missing
    add(_sec(21, "Missing evidence"))
    add("| Item | Domain | Why unavailable |")
    add("| --- | --- | --- |")
    for e in evidence:
        if e.status is Status.UNAVAILABLE:
            add(f"| `{e.name}` | {e.domain} | {e.missing_reason} |")

    # 22 status disclosure
    add(_sec(22, "Evidence-status disclosure"))
    counts = {s.value: sum(1 for e in evidence if e.status is s) for s in Status}
    add("| Status | Count | Meaning |")
    add("| --- | --- | --- |")
    add(
        f"| VALIDATED | {counts['VALIDATED']} | supported by completed evidence appropriate "
        "to its scope |"
    )
    add(
        f"| DESCRIPTIVE | {counts['DESCRIPTIVE']} | factual or computed; claims no "
        "predictive reliability |"
    )
    add(
        f"| EXPERIMENTAL | {counts['EXPERIMENTAL']} | directional reading that has not "
        "earned validated status |"
    )
    add(f"| UNAVAILABLE | {counts['UNAVAILABLE']} | repository lacks the data or implementation |")
    add(
        "\n**No item in this report is VALIDATED.** No directional signal in this platform "
        "has established predictive reliability; the V6 research programme closed with that "
        "question unresolved and underpowered."
    )

    # 23 limitations
    add(_sec(23, "Limitations"))
    add("- Every directional reading is **EXPERIMENTAL**. None is a forecast.")
    add(
        "- Historical distributions are this symbol's **own** history, conditioned on its "
        "survival, drawn from a universe selected because it is a current holding, and "
        "computed on overlapping windows. Descriptive only."
    )
    add(
        "- The portfolio is represented by a manual broker export dated 2026-07-16; "
        "positions may have changed."
    )
    add("- Listed options are excluded from the schema, so exposure is understated.")
    add("- No policy layer exists, so no position limit is enforced anywhere in this report.")
    add(f"\n*{DISCLOSURE}*")
    add("")
    return "\n".join(lines)
