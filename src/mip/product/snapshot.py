"""Tier-1 decision snapshot: presentation-only derivations.

This module computes NOTHING new. Every statement it produces is a re-reading of
values already present in `Evidence`, `HorizonVerdict`, `PositionState` and
`Constraint`. It holds no thresholds of its own, casts no votes, and can never
change an action.

Two deliberate sourcing rules keep the snapshot from ever contradicting the
detailed report underneath it:

1. GROUP COUNTS come from `decide.group_tally`, the same production function the
   §"Why this action" headline uses. Calling it with `Direction.POSITIVE` yields
   `(positive, negative, neutral)` group counts for any horizon, whatever the
   view actually is, because `group_tally` partitions by "agrees with the stated
   direction / disagrees / neutral".
2. PER-GROUP SIGNS are parsed out of `HorizonVerdict.contributing`, the audit
   string rendered verbatim in the detail section. The snapshot therefore cannot
   drift from the audit trail: it is the same text, re-shaped.

A regression test asserts (1) and (2) agree.
"""

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal

from mip.product.contracts import (
    Action,
    Constraint,
    Direction,
    Evidence,
    HorizonVerdict,
    PositionState,
    Status,
)
from mip.product.decide import ADD_DISCOURAGE_MULTIPLE, group_tally, portfolio_adjustment
from mip.product.slice import (
    DELIVERY_BOTTOM,
    DELIVERY_TOP,
    OWN_HISTORY_BOTTOM,
    OWN_HISTORY_TOP,
)

HZ_ORDER = ("1w", "1m", "3m", "6m", "1y")

# Markers already used in production by `portfolio_view.summarise` to detect
# which stage-2 effect fired. Re-read here, not re-derived.
_SIZING_MARKER = "position-sizing effect"
_BREACH_MARKER = "risk-limit decision"
_EVENT_MARKER = "timing and position-management effect"

_GROUP_RE = re.compile(r"\[(\w+) -> (POSITIVE|NEGATIVE|NEUTRAL)\]")
_PCTILE_RE = re.compile(r";\s*(\d+)% of its own history")
_EVENT_RE = re.compile(r"\((\d+)d, (\d{4}-\d{2}-\d{2})\)")

_SIGN = {"POSITIVE": "+", "NEGATIVE": "-", "NEUTRAL": "~"}


# ----------------------------------------------------------------- primitives
def group_counts(evidence: list[Evidence], horizon: str) -> tuple[int, int, int]:
    """(positive, negative, neutral) GROUP counts for one horizon.

    Delegates to the production tally so the snapshot and the detail section can
    never report different breadth for the same horizon.
    """
    return group_tally(evidence, horizon, Direction.POSITIVE)


def signed_groups(verdict: HorizonVerdict) -> dict[str, str]:
    """{group: POSITIVE|NEGATIVE} for the groups that actually voted."""
    return {g: d for g, d in _GROUP_RE.findall(" ".join(verdict.contributing)) if d != "NEUTRAL"}


def all_groups(verdict: HorizonVerdict) -> dict[str, str]:
    """{group: POSITIVE|NEGATIVE|NEUTRAL} for every group present at this horizon."""
    return dict(_GROUP_RE.findall(" ".join(verdict.contributing)))


def breadth_cell(evidence: list[Evidence], v: HorizonVerdict) -> str:
    """Compact 'how wide is this verdict' cell for the horizon table."""
    pos, neg, neu = group_counts(evidence, v.horizon)
    total = pos + neg + neu
    if total == 0:
        return "no evidence groups"
    if v.direction is Direction.POSITIVE:
        return f"**{pos} for** / {neg} against / {neu} neutral (of {total})"
    if v.direction is Direction.NEGATIVE:
        return f"**{neg} for** / {pos} against / {neu} neutral (of {total})"
    if v.direction is Direction.CONFLICTED:
        return f"{pos} positive / {neg} negative / {neu} neutral (of {total})"
    return f"0 signed / {neu} neutral (of {total})"


def portfolio_effect_kind(v: HorizonVerdict) -> str | None:
    """Which stage-2 effect changed this horizon's action, if any."""
    if _BREACH_MARKER in v.rationale:
        return "BREACH"
    if _SIZING_MARKER in v.rationale:
        return "CONCENTRATION"
    if _EVENT_MARKER in v.rationale:
        return "EVENT"
    return None


def _ratio_text(ratio: Decimal) -> str:
    """Format the equal-weight multiple so it cannot appear to contradict itself.

    A position at 2.999x an equal weight is genuinely below the 3x reference, but
    printed at one decimal it reads "3.0x ... below the 3x reference". Precision
    is escalated only when the rounded value would land exactly on the reference
    while the true value does not.
    """
    for places in (1, 2, 3):
        text = f"{ratio:.{places}f}"
        if Decimal(text) != ADD_DISCOURAGE_MULTIPLE or ratio == ADD_DISCOURAGE_MULTIPLE:
            return text
    return f"{ratio:.3f}"


def _signed_items(evidence: list[Evidence], direction: Direction, limit: int) -> list[Evidence]:
    """First `limit` signed items in production evidence order, deduped by name."""
    out: list[Evidence] = []
    seen: set[str] = set()
    for e in evidence:
        if e.status is Status.UNAVAILABLE or e.direction is not direction or e.name in seen:
            continue
        seen.add(e.name)
        out.append(e)
        if len(out) == limit:
            break
    return out


def _item_line(e: Evidence) -> str:
    """One bullet: name, observed value, the human phrase, and its group."""
    detail = e.explanation.split(". ")[0].strip().rstrip(".")
    if len(detail) > 150:
        detail = detail[:147].rstrip() + "..."
    return f"`{e.name}` = {e.value} — {detail} *[{e.group}]*"


# ------------------------------------------------------------ horizon summary
def horizon_structure(verdicts: list[HorizonVerdict]) -> list[str]:
    """Replacement for the old executive summary.

    The previous renderer printed `verdicts[0].rationale` - the 1w reasoning -
    with no horizon label, so a report whose 6m/1y horizons said ADD could open
    with a sentence reading "the security view is NEGATIVE ... implies TRIM".
    Nothing here may speak for the report as a whole unless every horizon agrees,
    and every sentence names the horizons it covers.
    """
    out: list[str] = []
    actions = {v.action for v in verdicts}
    views = {v.direction for v in verdicts}

    if len(actions) == 1 and len(views) == 1:
        v = verdicts[0]
        out.append(
            f"**All five horizons agree: {v.direction.value} view, {v.action.value}.** "
            f"The statement below therefore holds for the whole report."
        )
        out.append(f"\n{_horizon_sentence(verdicts)}")
        return out

    if len(actions) == 1:
        out.append(
            f"**The action is {next(iter(actions)).value} at all five horizons, but the "
            f"security view is not uniform.** No single horizon speaks for the report."
        )
    else:
        out.append(
            "**The horizons disagree. No single horizon speaks for this report.** "
            f"Actions by horizon: {_action_map(verdicts)}."
        )
    out.append(f"\n{_horizon_sentence(verdicts)}")
    return out


def _action_map(verdicts: list[HorizonVerdict]) -> str:
    return ", ".join(f"{v.horizon} {v.action.value}" for v in verdicts)


def _horizon_sentence(verdicts: list[HorizonVerdict]) -> str:
    """One labelled clause per horizon. Never an unlabelled global claim."""
    parts = []
    for v in verdicts:
        parts.append(f"**{v.horizon}** {v.direction.value} -> {v.action.value}")
    return "Per horizon: " + "; ".join(parts) + "."


# ------------------------------------------------------------------- thesis
def core_thesis(
    pos: PositionState, evidence: list[Evidence], verdicts: list[HorizonVerdict]
) -> str:
    """Two to three sentences, composed only from values already computed.

    Sentence 1 states the horizon structure. Sentence 2 names the groups doing
    the work at each end of the horizon range. Sentence 3 appears only when a
    portfolio effect actually changed an action.
    """
    by_h = {v.horizon: v for v in verdicts}
    short = [h for h in ("1w", "1m", "3m") if h in by_h]
    long = [h for h in ("6m", "1y") if h in by_h]

    def _phrase(hs: list[str]) -> str:
        views = {by_h[h].direction.value for h in hs}
        if len(views) == 1:
            return f"{'/'.join(hs)} {next(iter(views))}"
        return "; ".join(f"{h} {by_h[h].direction.value}" for h in hs)

    s1 = f"Views run {_phrase(short)} and {_phrase(long)}."

    def _merge(hs: list[str]) -> dict[str, set[str]]:
        """Signs a group casts anywhere in this horizon range, kept as a SET.

        Collapsing to a single sign would hide a group that votes one way early
        and the other way later, which is exactly the kind of horizon difference
        the thesis exists to surface.
        """
        merged: dict[str, set[str]] = {}
        for h in hs:
            for g, s in signed_groups(by_h[h]).items():
                merged.setdefault(g, set()).add(s)
        return merged

    near_groups = _merge(short)
    far_groups = _merge(long)

    def _named(d: dict[str, set[str]]) -> str:
        if not d:
            return "no group casts a signed vote"
        return ", ".join(
            f"`{g}`({'+/-' if len(s) > 1 else _SIGN[next(iter(s))]})" for g, s in sorted(d.items())
        )

    s2 = (
        f"Over 1w-3m the signed evidence is {_named(near_groups)}; "
        f"over 6m-1y it is {_named(far_groups)}."
    )

    changed = [v.horizon for v in verdicts if portfolio_effect_kind(v)]
    if changed:
        kind = portfolio_effect_kind(by_h[changed[0]])
        weight = f"{pos.market_weight:.2%}" if pos.market_weight is not None else "an unknown share"
        if kind == "CONCENTRATION":
            s3 = (
                f" Existing exposure ({weight} of portfolio market value) holds the action "
                f"below the security view at {', '.join(changed)} - a sizing effect, not a "
                f"bearish view."
            )
        elif kind == "BREACH":
            s3 = f" A deterministic portfolio limit is breached at {', '.join(changed)}."
        else:
            s3 = (
                f" An unresolved scheduled event suppresses increasing exposure at "
                f"{', '.join(changed)}."
            )
        return s1 + " " + s2 + s3
    return s1 + " " + s2


# --------------------------------------------------------- why horizons differ
def why_horizons_differ(verdicts: list[HorizonVerdict]) -> list[str]:
    """Explain the horizon shape from the evidence that actually differs.

    Two mechanisms produce every horizon difference in this engine and both are
    visible in the audit strings: a group may be ADMITTED to only some horizons,
    and a group present at several horizons may VOTE DIFFERENTLY at each.
    """
    present: dict[str, list[str]] = {}
    votes: dict[str, dict[str, str]] = {}
    for v in verdicts:
        for g, d in all_groups(v).items():
            present.setdefault(g, []).append(v.horizon)
            votes.setdefault(g, {})[v.horizon] = d

    out: list[str] = []
    if len({v.direction for v in verdicts}) == 1:
        out.append(
            "All five horizons reach the same view. The groups that vote still change "
            "across horizons; the direction does not."
        )
    for v in verdicts:
        sg = signed_groups(v)
        rendered = (
            ", ".join(f"`{g}`({_SIGN[s]})" for g, s in sorted(sg.items()))
            if sg
            else "*no group casts a signed vote*"
        )
        out.append(
            f"- **{v.horizon} {v.direction.value} -> {v.action.value}** — signed: {rendered}"
        )

    horizons_in_report = [v.horizon for v in verdicts]
    # A group that never signs anywhere explains no horizon difference, however
    # it is gated. Only groups that actually vote somewhere are described.
    voting = {g for g, per_h in votes.items() if any(s != "NEUTRAL" for s in per_h.values())}
    gated = [
        (g, hs)
        for g, hs in sorted(present.items())
        if g in voting and hs and len(hs) < len(horizons_in_report)
    ]
    flips = []
    for g, per_h in sorted(votes.items()):
        signs = {s for s in per_h.values() if s != "NEUTRAL"}
        if len(signs) > 1:
            flips.append(g)
    goes_quiet = []
    for g, per_h in sorted(votes.items()):
        signed_at = [h for h, s in per_h.items() if s != "NEUTRAL"]
        if signed_at and len(signed_at) < len(per_h):
            goes_quiet.append((g, signed_at))

    mech: list[str] = []
    if gated:
        mech.append(
            "Admitted to only some horizons: "
            + "; ".join(f"`{g}` at {', '.join(hs)}" for g, hs in gated)
            + "."
        )
    if goes_quiet:
        mech.append(
            "Signed at some horizons and neutral at others: "
            + "; ".join(f"`{g}` signs at {', '.join(hs)}" for g, hs in goes_quiet)
            + "."
        )
    if flips:
        mech.append("Changes sign across horizons: " + ", ".join(f"`{g}`" for g in flips) + ".")
    if mech:
        out.append("")
        out.append("**Mechanism.** " + " ".join(mech))
    return out


# ---------------------------------------------------------- portfolio effect
def portfolio_effect(
    pos: PositionState, constraints: list[Constraint], verdicts: list[HorizonVerdict]
) -> str:
    _, text = portfolio_adjustment(pos, constraints)
    changed = [v.horizon for v in verdicts if portfolio_effect_kind(v)]
    if not changed:
        return (
            "**No.** Portfolio exposure did not change the action at any horizon; every "
            f"action is the security view unmodified. {text}"
        )
    kinds = {portfolio_effect_kind(v) for v in verdicts if portfolio_effect_kind(v)}
    natural = {
        v.horizon: v.rationale.split("which alone implies ", 1)[-1].split(".")[0]
        for v in verdicts
        if portfolio_effect_kind(v)
    }
    detail = ", ".join(f"{h} would be {a} on the security view alone" for h, a in natural.items())
    label = {
        "CONCENTRATION": "existing exposure",
        "BREACH": "a breached deterministic limit",
        "EVENT": "an imminent unresolved scheduled event",
    }
    which = " and ".join(label[k] for k in sorted(kinds))
    return f"**Yes, at {', '.join(changed)}** — {which} changed the action ({detail}). {text}"


# -------------------------------------------------------------- next catalyst
def next_catalyst(evidence: list[Evidence]) -> str:
    anchor = next(
        (e for e in evidence if e.name == "event_state_1y" and e.status is not Status.UNAVAILABLE),
        None,
    )
    if anchor is None:
        reason = next(
            (e.missing_reason for e in evidence if e.name == "event_state_1y"),
            "no scheduled-event item was emitted",
        )
        return f"**UNAVAILABLE** — {reason}."
    m = _EVENT_RE.search(anchor.value)
    if not m:
        state = anchor.value.split(" (")[0].replace("_", " ").lower()
        return f"**No dated event.** Scheduled-event state: {state}."
    days, when = m.group(1), m.group(2)
    inside = [
        e.horizons[0]
        for e in evidence
        if e.name.startswith("event_state_")
        and e.status is not Status.UNAVAILABLE
        and e.value.startswith("WITHIN_HORIZON")
    ]
    mag = next((e for e in evidence if e.name == "event_move_magnitude"), None)
    parts = [f"**Next scheduled report {when}, {days} days out.**"]
    parts.append(
        f"Inside the {', '.join(inside)} window{'s' if len(inside) != 1 else ''}."
        if inside
        else "Outside every horizon window."
    )
    if mag is not None and mag.status is not Status.UNAVAILABLE:
        parts.append(
            f"Past reaction on the first session after each of the last reports: {mag.value}."
        )
    parts.append("A date carries no direction and never votes.")
    return " ".join(parts)


# ------------------------------------------------------------------ key risk
def key_risk(pos: PositionState, evidence: list[Evidence], verdicts: list[HorizonVerdict]) -> str:
    """The single most decision-relevant caution, chosen by a fixed precedence.

    No new risk metric: every branch restates a value already computed elsewhere
    in the report.
    """
    age = (pos.as_of - pos.price_date).days if pos.price_date else None
    if age is not None and age > 4:
        return (
            f"**Stale prices.** The latest close is {age} calendar days old, so the 1w "
            f"row is unsupported."
        )

    thin = [
        (v.horizon, v.direction.value, next(iter(signed_groups(v))))
        for v in verdicts
        if v.direction in (Direction.POSITIVE, Direction.NEGATIVE) and len(signed_groups(v)) == 1
    ]
    if thin:
        h, view, grp = thin[0]
        pos_c, neg_c, neu_c = group_counts(evidence, h)
        return (
            f"**Thin verdict at {h}.** The {view} security view rests on `{grp}` alone; "
            f"{neu_c} of {pos_c + neg_c + neu_c} groups are neutral. One group changing "
            f"its reading removes the whole basis for that horizon."
        )

    if pos.market_weight is not None and pos.portfolio_positions:
        equal = Decimal(1) / Decimal(pos.portfolio_positions)
        if pos.market_weight / equal >= ADD_DISCOURAGE_MULTIPLE:
            return (
                f"**Concentration.** The position is {pos.market_weight:.2%} of portfolio "
                f"market value, {_ratio_text(pos.market_weight / equal)}x an equal weight. No hard "
                f"cap has been supplied, so this can only suppress ADD."
            )

    worst = _signed_items(evidence, Direction.NEGATIVE, 1)
    if worst:
        return f"**Strongest opposing evidence.** {_item_line(worst[0])}"
    return (
        "**No single dominant risk is identifiable from the evidence in this report.** "
        "Every directional reading here remains EXPERIMENTAL."
    )


# ------------------------------------------------ what would change the view
_PCTILE_RULE = (
    f"own-history percentile; POSITIVE at or above {OWN_HISTORY_TOP:.0%}, "
    f"NEGATIVE at or below {OWN_HISTORY_BOTTOM:.0%}"
)


def _watch_token(e: Evidence) -> tuple[str, str] | None:
    """(token, rule) for one signing item.

    The rule is the production band that produced the reading, imported from the
    module that applies it, so the sentence cannot describe a rule the engine
    does not use. Items sharing a rule are collapsed behind one statement of it.
    """
    pc = _PCTILE_RE.search(e.explanation)
    if pc is not None:
        return f"`{e.name}` {pc.group(1)}%", _PCTILE_RULE
    if e.name == "valuation_position":
        return (
            f"`valuation_position` {e.value}",
            "votes NEGATIVE only in EXPENSIVE / ABOVE NORMAL, POSITIVE only in "
            "CHEAP / BELOW NORMAL",
        )
    if e.name == "company_quality_position":
        return (
            f"`company_quality_position` {e.value}",
            "votes POSITIVE only in STRONG / ABOVE_PEER, NEGATIVE only in WEAK / BELOW_PEER",
        )
    if e.name == "earnings_delivery_record":
        return (
            f"`earnings_delivery_record` {e.value}",
            f"votes only when the peer percentile is above {DELIVERY_TOP:.0%} or below "
            f"{DELIVERY_BOTTOM:.0%}",
        )
    return None


def _watch_clause(items: list[Evidence]) -> str:
    """One compact 'watch' clause, grouping items that share a band rule."""
    by_rule: dict[str, list[str]] = {}
    for e in items:
        hit = _watch_token(e)
        if hit is None:
            continue
        token, rule = hit
        if token not in by_rule.setdefault(rule, []):
            by_rule[rule].append(token)
    if not by_rule:
        return ""
    parts = [f"{', '.join(tokens)} ({rule})" for rule, tokens in by_rule.items()]
    return " Watch: " + "; ".join(parts) + "."


def _fragility(v: HorizonVerdict) -> int:
    """How easily this horizon's view could move. Ordering only, never a decision."""
    sg = signed_groups(v)
    if v.direction in (Direction.POSITIVE, Direction.NEGATIVE) and len(sg) == 1:
        return 3
    if v.direction is Direction.CONFLICTED:
        return 2
    if sg:
        return 1
    return 0


def change_conditions(
    pos: PositionState,
    evidence: list[Evidence],
    verdicts: list[HorizonVerdict],
    limit: int | None = None,
) -> list[str]:
    """Observable conditions that would move a horizon's view or action.

    Derived entirely from the rules already applied: which groups signed, and the
    band each signing item would have to leave. No new signal, no new threshold.
    """
    by_name = {e.name: e for e in evidence}
    per_horizon: list[tuple[int, int, str]] = []

    for rank, v in enumerate(verdicts):
        sg = signed_groups(v)
        items = [
            by_name[n]
            for g in sorted(sg)
            for n in _members_of(v, g)
            if n in by_name and by_name[n].direction is not Direction.NEUTRAL
        ]
        if v.direction in (Direction.POSITIVE, Direction.NEGATIVE):
            only = " — the ONLY signed group" if len(sg) == 1 else ""
            # Naming the resulting action is only informative when it would
            # actually move; a suppressed horizon is already sitting on HOLD.
            consequence = (
                "the view becomes NEUTRAL (the action is already HOLD)"
                if v.action is Action.HOLD
                else f"the view becomes NEUTRAL and the action {Action.HOLD.value}"
            )
            head = (
                f"**{v.horizon}** — {v.direction.value} rests on "
                f"{', '.join(f'`{g}`' for g in sorted(sg))}{only}; if "
                f"{'it goes' if len(sg) == 1 else 'they all go'} neutral, {consequence}."
            )
        elif v.direction is Direction.CONFLICTED:
            pos_g = sorted(g for g, s in sg.items() if s == "POSITIVE")
            neg_g = sorted(g for g, s in sg.items() if s == "NEGATIVE")
            head = (
                f"**{v.horizon}** — CONFLICTED: {', '.join(f'`{g}`' for g in pos_g)} against "
                f"{', '.join(f'`{g}`' for g in neg_g)}; the view resolves the moment either "
                f"side stops signing."
            )
        else:
            head = (
                f"**{v.horizon}** — no group casts a signed vote; any single group signing "
                f"would move the view off NEUTRAL."
            )
        per_horizon.append((_fragility(v), rank, head + _watch_clause(items)))

    portfolio_line: str | None = None
    changed = [v for v in verdicts if portfolio_effect_kind(v) == "CONCENTRATION"]
    if changed and pos.market_weight is not None and pos.portfolio_positions:
        equal = Decimal(1) / Decimal(pos.portfolio_positions)
        threshold = equal * ADD_DISCOURAGE_MULTIPLE
        portfolio_line = (
            f"**Portfolio** — the ADD suppression at {', '.join(v.horizon for v in changed)} "
            f"lifts if market-value weight falls below {threshold:.2%} "
            f"({ADD_DISCOURAGE_MULTIPLE}x an equal weight across "
            f"{pos.portfolio_positions} holdings); it is {pos.market_weight:.2%} now."
        )

    if limit is None:
        ordered = [text for _, _, text in per_horizon]
        return ordered + ([portfolio_line] if portfolio_line else [])

    # Tier 1 has room for a few conditions only. Spend them on the horizons a
    # reader most needs explained: first the odd ones out - a horizon whose action
    # is in the minority is the one that provokes the question - then the most
    # fragile views, a single-group verdict ahead of a conflict. Ordering only:
    # no view, action or confidence is touched.
    counts = Counter(v.action for v in verdicts)
    top = max(counts.values())
    keyed = [
        (0 if counts[verdicts[idx].action] < top else 1, -frag, idx, text)
        for frag, idx, text in per_horizon
    ]
    head_room = limit - (1 if portfolio_line else 0)
    picked = sorted(keyed)[:head_room]
    ordered = [text for *_, idx, text in sorted(picked, key=lambda t: t[2])]
    return ([portfolio_line] if portfolio_line else []) + ordered


def _members_of(v: HorizonVerdict, group: str) -> list[str]:
    """Item names inside one group, read back out of the audit string."""
    for chunk in v.contributing:
        m = _GROUP_RE.match(chunk)
        if m and m.group(1) == group:
            body = chunk[m.end() :].strip()
            return [part.split("=", 1)[0].strip() for part in body.split(", ") if "=" in part]
    return []


# ---------------------------------------------------------------- risk table
def risk_rows(
    pos: PositionState, evidence: list[Evidence], verdicts: list[HorizonVerdict]
) -> list[tuple[str, str, str]]:
    """(risk, status, note) derived from the report's own values.

    Replaces a hardcoded table that asserted concentration and event risk were
    UNAVAILABLE in every report, twelve lines below the sections that stated
    both.
    """
    rows: list[tuple[str, str, str]] = []

    if pos.market_weight is None:
        why = next(
            (u for u in pos.unavailable if "market-value portfolio weight" in u),
            "market-value weight is not computable",
        )
        rows.append(("Concentration", "UNAVAILABLE", why))
    else:
        equal = Decimal(1) / Decimal(pos.portfolio_positions)
        ratio = pos.market_weight / equal
        material = ratio >= ADD_DISCOURAGE_MULTIPLE
        rows.append(
            (
                "Concentration",
                "**MATERIAL**" if material else "NOTED",
                f"{pos.market_weight:.2%} of portfolio market value, "
                f"{_ratio_text(ratio)}x an equal "
                f"weight across {pos.portfolio_positions} holdings"
                + (
                    f"; at or above the {ADD_DISCOURAGE_MULTIPLE}x reference, so ADD is "
                    f"suppressed. No hard cap supplied, so TRIM is never forced"
                    if material
                    else f"; below the {ADD_DISCOURAGE_MULTIPLE}x reference, so no sizing "
                    f"effect applies"
                ),
            )
        )

    rows.append(
        (
            "Liquidity",
            "UNAVAILABLE",
            "average daily volume is not wired into this slice, so days-to-liquidate "
            "cannot be computed",
        )
    )

    anchor = next(
        (e for e in evidence if e.name == "event_state_1y" and e.status is not Status.UNAVAILABLE),
        None,
    )
    if anchor is None:
        rows.append(
            (
                "Event risk",
                "UNAVAILABLE",
                next(
                    (
                        e.missing_reason or "no scheduled-event data"
                        for e in evidence
                        if e.name == "event_state_1y"
                    ),
                    "no scheduled-event data",
                ),
            )
        )
    else:
        m = _EVENT_RE.search(anchor.value)
        inside = [
            e.horizons[0]
            for e in evidence
            if e.name.startswith("event_state_")
            and e.status is not Status.UNAVAILABLE
            and e.value.startswith("WITHIN_HORIZON")
        ]
        mag = next(
            (
                e
                for e in evidence
                if e.name == "event_move_magnitude" and e.status is not Status.UNAVAILABLE
            ),
            None,
        )
        if m:
            note = f"next scheduled report {m.group(2)}, {m.group(1)} days out; " + (
                f"inside {', '.join(inside)}" if inside else "outside every horizon window"
            )
        else:
            note = anchor.value.split(" (")[0].replace("_", " ").lower()
        if mag is not None:
            note += f"; past first-session reaction {mag.value}"
        rows.append(("Event risk", "NOTED", note))

    thin = [
        v.horizon
        for v in verdicts
        if len(signed_groups(v)) == 1 and v.direction in (Direction.POSITIVE, Direction.NEGATIVE)
    ]
    if thin:
        rows.append(
            (
                "Evidence breadth",
                "**MATERIAL**",
                f"the view at {', '.join(thin)} rests on a single signed group; a change in "
                f"that one group removes the entire basis for the horizon",
            )
        )

    rows.append(
        (
            "Undisclosed exposure",
            "**MATERIAL**",
            "the broker export excludes listed options; "
            "`data/unsupported_positions_2026-07-16.csv` records call positions that are "
            "**not** represented in this report, so portfolio exposure is understated "
            "wherever that file lists this symbol",
        )
    )
    return rows


# ------------------------------------------------------------------ headline
def support_bullets(evidence: list[Evidence], limit: int = 3) -> list[str]:
    return [_item_line(e) for e in _signed_items(evidence, Direction.POSITIVE, limit)]


def concern_bullets(evidence: list[Evidence], limit: int = 3) -> list[str]:
    return [_item_line(e) for e in _signed_items(evidence, Direction.NEGATIVE, limit)]
