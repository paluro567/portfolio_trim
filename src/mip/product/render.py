"""Deterministic Markdown renderer for the V4 vertical slice.

Layout is tiered: a decision snapshot that can be read in about a minute, the
supporting investment evidence underneath it, and the audit trail below that.
Nothing here computes a view, an action or a confidence - every value rendered
was decided upstream in `slice`, `decide` and `snapshot`.
"""

from __future__ import annotations

from mip.product import snapshot
from mip.product.contracts import (
    Constraint,
    Evidence,
    HorizonVerdict,
    PositionState,
    Status,
)
from mip.product.decide import portfolio_adjustment

DISCLOSURE = (
    "Confidence is an experimental evidence-quality assessment, not a probability "
    "of being correct."
)


def fmt_pct(v) -> str:
    return "unavailable" if v is None else f"{v:.2%}"


def _money(v) -> str:
    return "unavailable" if v is None else f"${v:,.2f}"


def _cell(v) -> str:
    """Escape a value for a Markdown table cell.

    Some observed values legitimately contain a pipe - `median |move| 7.3%` -
    which silently splits the row into extra columns when written raw.
    """
    return str(v).replace("|", "\\|")


def _sec(n, title: str) -> str:
    return f"\n## {n}. {title}\n"


def _tier(label: str) -> str:
    return f"\n---\n\n### {label}\n\n---\n"


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
    _age = (pos.as_of - pos.price_date).days if pos.price_date else None
    stale = ""
    if _age is not None and _age > 1:
        stale = (
            f" **Price is {_age} calendar days stale** "
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
    if _age is not None and _age > 4:
        add(
            "\n> **1W caution.** The latest price is more than four calendar days old. "
            "Treat the 1-week row as unsupported until prices are refreshed."
        )

    # ================================================== TIER 1 — snapshot
    add(_tier("TIER 1 — DECISION SNAPSHOT"))

    add(_sec(1, "Decision snapshot"))
    add(
        f"**{pos.symbol}** {_money(pos.market_price)} · {pos.quantity} shares · "
        f"**{fmt_pct(pos.market_weight)} of portfolio** · market value "
        f"{_money(pos.market_value)} · unrealised {_money(pos.unrealized_pnl)}"
        f"{f' ({pos.unrealized_pct:+.2%})' if pos.unrealized_pct is not None else ''} · "
        f"average cost ${pos.average_cost}"
    )
    add("")
    add("| Horizon | Security view | Portfolio action | Evidence groups | Strength |")
    add("| --- | --- | --- | --- | --- |")
    for v in verdicts:
        add(
            f"| **{v.horizon}** | {v.direction.value} | **{v.action.value}** | "
            f"{snapshot.breadth_cell(evidence, v)} | {v.confidence.value} (experimental) |"
        )
    add(
        "\n*Security view* is the assessment of the security; *portfolio action* is what "
        "to do about the position. They are computed separately: portfolio weight cannot "
        "reach the view. *Evidence groups* counts independent phenomenon groups, not raw "
        "items - four momentum windows agreeing is one group, not four."
    )

    add(_sec(2, "Executive summary"))
    for line in snapshot.horizon_structure(verdicts):
        add(line)

    add(_sec(3, "Core thesis"))
    add(snapshot.core_thesis(pos, evidence, verdicts))

    add(_sec(4, "Top support"))
    sup = snapshot.support_bullets(evidence)
    if sup:
        for b in sup:
            add(f"- {b}")
    else:
        add("*No item in this report carries a positive reading.*")

    add(_sec(5, "Top concerns"))
    con = snapshot.concern_bullets(evidence)
    if con:
        for b in con:
            add(f"- {b}")
    else:
        add("*No item in this report carries a negative reading.*")

    add(_sec(6, "Why the horizons differ"))
    for line in snapshot.why_horizons_differ(verdicts):
        add(line)

    add(_sec(7, "Portfolio effect"))
    add(snapshot.portfolio_effect(pos, constraints, verdicts))

    add(_sec(8, "Next catalyst"))
    add(snapshot.next_catalyst(evidence))

    add(_sec(9, "Key risk"))
    add(snapshot.key_risk(pos, evidence, verdicts))

    add(_sec(10, "What would change the view"))
    for c in snapshot.change_conditions(pos, evidence, verdicts, limit=3):
        add(f"- {c}")
    add("\n*Full per-horizon conditions are in the audit tier below.*")

    # ================================== TIER 2 — supporting investment evidence
    add(_tier("TIER 2 — SUPPORTING INVESTMENT EVIDENCE"))

    add(_sec(11, "Why this action, by horizon"))
    for v in verdicts:
        add(f"\n**{v.horizon} — {v.action.value}.** {v.rationale}")
        if v.contributing:
            add(f"\n  Directional evidence considered: {'; '.join(v.contributing)}.")
        if v.conflicts:
            add(f"\n  Conflicts: {'; '.join(v.conflicts)}.")
        add(f"\n  Confidence basis: {'; '.join(v.confidence_basis)}.")

    add(_sec(12, "Current position state"))
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

    add(_sec(13, "Portfolio context"))
    add(
        f"Portfolio holds **{pos.portfolio_positions} positions**. This holding is "
        f"{f'{pos.cost_weight:.2%}' if pos.cost_weight is not None else 'an unavailable share'} "
        f"of total **cost basis**."
    )
    add("\n**Unavailable portfolio inputs:**\n")
    for u in pos.unavailable:
        add(f"- {u}")

    add("\n**Portfolio concentration effect on the recommendation**\n")
    add(portfolio_adjustment(pos, constraints)[1])

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

    # evidence by domain. An item is explained in prose ONCE per report; later
    # sections list it in their table and point at the section that explains it.
    explained: dict[str, int] = {}
    order = [
        (14, "Market and regime context", "market/regime"),
        (15, "Sector context", "sector"),
        (16, "Company evidence", "company"),
        (17, "Fundamental and earnings evidence", "fundamentals"),
        (18, "Valuation evidence", "valuation"),
        (19, "Catalyst evidence", "catalysts"),
        (20, "Price and technical evidence", "price/technical"),
        (21, "Historical evidence", "historical"),
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
                f"| `{e.name}` | {e.status.value} | {_cell(e.value)} | {e.as_of} | "
                f"{', '.join(e.horizons)} | {e.direction.value} |"
            )

        fresh = [e for e in avail if e.name not in explained]
        repeats = [e for e in avail if e.name in explained]

        # A limitations paragraph shared by several items in this section is
        # printed once, naming the items it governs.
        shared: dict[str, list[str]] = {}
        for e in fresh:
            shared.setdefault(e.limitations, []).append(e.name)
        for e in fresh:
            add(f"\n- **`{e.name}`** — {e.explanation}")
            if len(shared[e.limitations]) == 1:
                add(f"  - *Limitations:* {e.limitations}")
        for lim, names in shared.items():
            if len(names) > 1:
                add(f"\n*Limitations — applies to " f"{', '.join(f'`{x}`' for x in names)}:* {lim}")
        for e in repeats:
            add(f"\n- **`{e.name}`** — explained in section {explained[e.name]} above.")
        for e in fresh:
            explained[e.name] = n

        miss = [e for e in items if e.status is Status.UNAVAILABLE]
        if miss:
            add("\n**Unavailable in this domain:**\n")
            for e in miss:
                add(f"- `{e.name}` — {e.missing_reason}")

    add(_sec(22, "Historical analogues"))
    add(
        "**UNAVAILABLE.** The analogue engine is a SHADOW component excluded from the "
        "product decision path, and the Arm 2 readiness review established that its "
        "feature-consumer structure could not be validated. Not used."
    )

    add(_sec(23, "Risk factors"))
    add("| Risk | Status | Note |")
    add("| --- | --- | --- |")
    for name, status, note in snapshot.risk_rows(pos, evidence, verdicts):
        add(f"| {name} | {status} | {_cell(note)} |")

    # ============================================ TIER 3 — audit / methodology
    add(_tier("TIER 3 — AUDIT AND METHODOLOGY"))

    add(_sec(24, "Data freshness"))
    add("| Field | Value |")
    add("| --- | --- |")
    add(f"| AS-OF DATE | {pos.as_of.isoformat()} |")
    add(f"| LATEST SECURITY PRICE | {pos.price_date or 'unavailable'} |")
    add(f"| LATEST FEATURE / OBSERVED DATA | {meta.get('feature_date', 'unavailable')} |")
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

    add(_sec(25, "Deterministic constraints"))
    add("| Constraint | Status | Observed | Threshold | Reason |")
    add("| --- | --- | --- | --- | --- |")
    for c in constraints:
        add(
            f"| {c.name} | **{c.status.value}** | {_cell(c.observed)} | "
            f"{_cell(c.threshold)} | {_cell(c.reason)} |"
        )

    # Identical elimination sets are printed once, naming the horizons they cover.
    add(_sec(26, "Why not the alternative actions"))
    groups: dict[tuple[tuple[str, str], ...], list[str]] = {}
    for v in verdicts:
        groups.setdefault(tuple(v.eliminations), []).append(v.horizon)
    for elims, hs in groups.items():
        add(f"\n**{', '.join(hs)}**\n")
        for act, why in elims:
            add(f"- **{act} rejected** — {why}")

    add(_sec(27, "What would change this recommendation"))
    add(
        "Conditions below are read off the rules this report already applies. "
        "No new signal and no new threshold is introduced.\n"
    )
    for c in snapshot.change_conditions(pos, evidence, verdicts):
        add(f"- {c}")
    add(
        "\n**Structural gaps that would widen what this report can say:** a policy "
        "artifact with position limits (making concentration evaluable and a hard-cap "
        "breach detectable); tax lots with acquisition dates (making the cost of "
        "trimming computable); listed options represented in the schema; and a "
        "point-in-time fundamentals history, which would let valuation be compared "
        "with the security's own past rather than only with peers."
    )

    add(_sec(28, "Missing evidence"))
    missing_rows = [e for e in evidence if e.status is Status.UNAVAILABLE]
    if not missing_rows:
        add("*Every evidence item this slice implements produced a value for this holding.*")
    else:
        add("| Item | Domain | Why unavailable |")
        add("| --- | --- | --- |")
        for e in missing_rows:
            add(f"| `{e.name}` | {e.domain} | {_cell(e.missing_reason)} |")

    add(_sec(29, "Evidence-status disclosure"))
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

    add(_sec(30, "Limitations"))
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
