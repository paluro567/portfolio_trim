"""Portfolio-level command centre: every holding, one triage view, one ranking."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from mip.product.contracts import Action, Direction, Evidence, HorizonVerdict, Status
from mip.product.decide import independent_groups


@dataclass(frozen=True, slots=True)
class HoldingRow:
    symbol: str
    weight: Decimal | None
    verdicts: tuple[HorizonVerdict, ...]
    positive: str
    negative: str
    sizing: str
    risk: str
    catalyst: str
    freshness: str
    completeness: str
    n_groups: int
    priority: int
    priority_why: tuple[str, ...]

    def action(self, h: str) -> str:
        return next(v.action.value for v in self.verdicts if v.horizon == h)

    def view(self, h: str) -> str:
        return next(v.direction.value for v in self.verdicts if v.horizon == h)

    def strength(self, h: str) -> str:
        return next(v.confidence.value for v in self.verdicts if v.horizon == h)


def _best(evidence: list[Evidence], direction: Direction) -> str:
    hits = [e for e in evidence if e.direction is direction and e.status is not Status.UNAVAILABLE]
    if not hits:
        return "none"
    e = hits[0]
    return f"{e.name} = {e.value}"


def summarise(
    symbol: str,
    pos,
    evidence: list[Evidence],
    verdicts: list[HorizonVerdict],
    days_stale: int | None,
) -> HoldingRow:
    avail = [e for e in evidence if e.status is not Status.UNAVAILABLE]
    groups = independent_groups(evidence, "1m")
    catalyst = next(
        (
            e.value
            for e in evidence
            if e.name == "next_earnings_date" and e.status is not Status.UNAVAILABLE
        ),
        "unknown",
    )
    risk = "concentration" if (pos.market_weight or 0) > Decimal("0.05") else "none flagged"
    if days_stale is None:
        fresh = "UNKNOWN"
    elif days_stale <= 1:
        fresh = "CURRENT"
    elif days_stale <= 4:
        fresh = "STALE"
    else:
        fresh = "BLOCKING(1W)"

    acts = {v.action for v in verdicts}
    dirs = {v.direction for v in verdicts}
    why: list[str] = []
    p = 0
    if acts & {Action.EXIT}:
        p += 60
        why.append("EXIT indicated")
    if acts & {Action.TRIM}:
        p += 40
        why.append("TRIM indicated")
    if acts & {Action.ADD}:
        p += 25
        why.append("ADD indicated")
    if Direction.CONFLICTED in dirs:
        p += 15
        why.append("evidence conflicts")
    if pos.market_weight is not None and pos.market_weight > Decimal("0.05"):
        p += int(pos.market_weight * 100)
        why.append(f"material weight {pos.market_weight:.1%}")
    if "d away" in catalyst:
        try:
            d = int(catalyst.split("(")[1].split("d")[0])
            if d <= 14:
                p += 20
                why.append(f"earnings in {d}d")
        except (IndexError, ValueError):
            pass
    if len(groups) <= 2:
        p += 10
        why.append(f"only {len(groups)} independent group(s)")
    if fresh.startswith("BLOCKING"):
        p += 10
        why.append("data stale")

    return HoldingRow(
        symbol=symbol,
        weight=pos.market_weight,
        verdicts=tuple(verdicts),
        positive=_best(evidence, Direction.POSITIVE),
        negative=_best(evidence, Direction.NEGATIVE),
        sizing=(
            "suppressed ADD"
            if any("position-sizing effect" in v.rationale for v in verdicts)
            else (
                "risk-limit override"
                if any("risk-limit decision" in v.rationale for v in verdicts)
                else "none"
            )
        ),
        risk=risk,
        catalyst=catalyst,
        freshness=fresh,
        completeness=f"{len(avail)}/{len(evidence)}",
        n_groups=len(groups),
        priority=p,
        priority_why=tuple(why),
    )


HZ = ("1w", "1m", "3m", "6m", "1y")


def render_portfolio(rows: list[HoldingRow], meta: dict) -> str:
    lines: list[str] = []
    add = lines.append
    add("# Portfolio Command Centre")
    add(
        f"\n*As of {meta['as_of']}. {len(rows)} holdings. Prices through "
        f"{meta['latest_price']}. Generated at commit `{meta['commit']}`.*"
    )
    add(
        "\n> Column **View** is the security assessment. Column **Action** is the "
        "portfolio decision. They are computed separately: portfolio weight cannot "
        "reach the view. Evidence strength is an experimental evidence-quality "
        "label, not a probability."
    )

    def bucket(pred):
        return [r for r in rows if pred(r)]

    act_req = bucket(lambda r: {r.action(h) for h in HZ} & {"ADD", "TRIM", "EXIT"})
    review = bucket(
        lambda r: r not in act_req
        and (
            "CONFLICTED" in {r.view(h) for h in HZ}
            or (r.weight or 0) > Decimal("0.05")
            or r.freshness.startswith("BLOCKING")
            or r.n_groups <= 2
        )
    )
    quiet = [r for r in rows if r not in act_req and r not in review]

    for title, group, note in (
        ("ACTION REQUIRED", act_req, "an ADD, TRIM or EXIT is indicated at one or more horizons"),
        (
            "REVIEW REQUIRED",
            review,
            "conflicting evidence, material weight, thin evidence, or stale data",
        ),
        ("NO IMMEDIATE ACTION", quiet, "HOLD across all horizons with no flag raised"),
    ):
        add(f"\n## {title} ({len(group)})\n")
        add(f"*{note}*\n")
        if not group:
            add("None.")
            continue
        add("| Ticker | Weight | 1W | 1M | 3M | 6M | 1Y | View (1M) | Strength | Groups | Fresh |")
        add("| --- | ---: | --- | --- | --- | --- | --- | --- | --- | ---: | --- |")
        for r in sorted(group, key=lambda x: -(x.weight or 0)):
            w = f"{r.weight:.2%}" if r.weight is not None else "n/a"
            add(
                f"| **{r.symbol}** | {w} | {r.action('1w')} | {r.action('1m')} | "
                f"{r.action('3m')} | {r.action('6m')} | {r.action('1y')} | "
                f"{r.view('1m')} | {r.strength('1m')} | {r.n_groups} | {r.freshness} |"
            )

    add("\n## Research attention priority\n")
    add(
        "*Ranks where to look first. **Not** a prediction ranking and not an "
        "expected-return ordering.*\n"
    )
    add("| # | Ticker | Weight | Why it ranks here |")
    add("| ---: | --- | ---: | --- |")
    for i, r in enumerate(sorted(rows, key=lambda x: -x.priority)[:15], 1):
        w = f"{r.weight:.2%}" if r.weight is not None else "n/a"
        add(f"| {i} | **{r.symbol}** | {w} | {'; '.join(r.priority_why) or 'no flags'} |")

    add("\n## Evidence detail per holding\n")
    add(
        add(
            "| Ticker | Weight | 1W | 1M | 3M | 6M | 1Y | View (1M) "
            "| Strength | Groups | Fresh |"
        )
    )
    add("| --- | --- | --- | --- | --- | ---: |")
    for r in sorted(rows, key=lambda x: -(x.weight or 0)):
        add(
            f"| **{r.symbol}** | {r.positive} | {r.negative} | {r.sizing} | "
            f"{r.catalyst} | {r.completeness} |"
        )
    add("")
    return "\n".join(lines)
