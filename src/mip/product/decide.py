"""Two-stage decision: security view first, portfolio sizing second.

Stage 1 answers "what does the evidence imply about this security over this
horizon?" using ONLY security evidence. Portfolio weight is not an input and
cannot reach it.

Stage 2 answers "given that view and how much I already own, what should I do?"
Portfolio exposure may change the ACTION. It may never change the VIEW.

No probability, no composite score, no hidden numeric formula.
"""

from __future__ import annotations

from decimal import Decimal

from mip.product.contracts import (
    HORIZONS,
    Action,
    Confidence,
    Constraint,
    ConstraintStatus,
    Direction,
    Evidence,
    HorizonVerdict,
    PositionState,
    Status,
)

# Domains that describe the SECURITY. Portfolio state is deliberately absent.
SECURITY_DOMAINS = frozenset(
    {
        "price/technical",
        "sector",
        "market/regime",
        "fundamentals",
        "valuation",
        "earnings",
        "catalysts",
        "historical",
    }
)

# Groups that describe UNCERTAINTY rather than direction. Excluded from the
# directional view by construction: a scheduled event has no sign. They reach the
# recommendation only through the action stage, as a guardrail.
NON_DIRECTIONAL_GROUPS = frozenset({"event_risk"})

# Descriptive sizing reference, NOT a policy limit. Equal weight across the
# holdings actually present. Used only to discourage ADD, never to force TRIM.
ADD_DISCOURAGE_MULTIPLE = Decimal(3)


def directional_view(
    evidence: list[Evidence], horizon: str
) -> tuple[Direction, list[str], list[str]]:
    """Stage 1. Security evidence only, aggregated by PHENOMENON GROUP.

    Four momentum windows agreeing is ONE piece of evidence about momentum, not
    four. Each group casts a single vote: the majority direction of its members,
    or NEUTRAL when its members disagree.
    """
    rel = [
        e
        for e in evidence
        if horizon in e.horizons
        and e.status is not Status.UNAVAILABLE
        and e.domain in SECURITY_DOMAINS
        and e.group not in NON_DIRECTIONAL_GROUPS
    ]
    if not rel:
        return Direction.UNAVAILABLE, [], []

    groups: dict[str, list[Evidence]] = {}
    for e in rel:
        groups.setdefault(e.group, []).append(e)

    votes: dict[str, Direction] = {}
    detail: list[str] = []
    for g, items in sorted(groups.items()):
        pos = [e for e in items if e.direction is Direction.POSITIVE]
        neg = [e for e in items if e.direction is Direction.NEGATIVE]
        if len(pos) > len(neg):
            votes[g] = Direction.POSITIVE
        elif len(neg) > len(pos):
            votes[g] = Direction.NEGATIVE
        else:
            votes[g] = Direction.NEUTRAL
        members = ", ".join(f"{e.name}={e.value}" for e in items)
        detail.append(f"[{g} -> {votes[g].value}] {members}")

    signed = {g: d for g, d in votes.items() if d is not Direction.NEUTRAL}
    if not signed:
        return Direction.NEUTRAL, detail, []
    pos_g = sorted(g for g, d in signed.items() if d is Direction.POSITIVE)
    neg_g = sorted(g for g, d in signed.items() if d is Direction.NEGATIVE)
    if pos_g and neg_g:
        conflict = (
            f"{len(pos_g)} positive group(s) ({', '.join(pos_g)}) against "
            f"{len(neg_g)} negative group(s) ({', '.join(neg_g)})"
        )
        return Direction.CONFLICTED, detail, [conflict]
    return (Direction.POSITIVE if pos_g else Direction.NEGATIVE), detail, []


def independent_groups(evidence: list[Evidence], horizon: str) -> list[str]:
    return sorted(
        {
            e.group
            for e in evidence
            if horizon in e.horizons
            and e.status is not Status.UNAVAILABLE
            and e.domain in SECURITY_DOMAINS
        }
    )


def _baseline_action(direction: Direction, n_signed: int) -> tuple[Action, str]:
    """Stage 1 -> the action the security view alone implies."""
    if direction is Direction.POSITIVE:
        return Action.ADD, "the security view is positive"
    if direction is Direction.NEGATIVE:
        return (
            Action.TRIM,
            f"the security view is negative on {n_signed} independent reading(s)",
        )
    if direction is Direction.CONFLICTED:
        return Action.HOLD, "security evidence conflicts, so no change is indicated"
    if direction is Direction.UNAVAILABLE:
        return Action.HOLD, "no security evidence is available for this horizon"
    return Action.HOLD, "the security view is neutral"


def confidence_for(
    evidence: list[Evidence],
    horizon: str,
    direction: Direction,
    conflicts: list[str],
    pos: PositionState,
) -> tuple[Confidence, list[str]]:
    basis: list[str] = []
    if direction is Direction.UNAVAILABLE:
        return Confidence.VERY_LOW, ["no security evidence available for this horizon"]

    rel = [
        e
        for e in evidence
        if horizon in e.horizons
        and e.status is not Status.UNAVAILABLE
        and e.domain in SECURITY_DOMAINS
        and e.group not in NON_DIRECTIONAL_GROUPS
    ]
    groups = sorted({e.group for e in rel})
    basis.append(
        f"{len(groups)} independent phenomenon group(s): {', '.join(groups)} "
        f"(from {len(rel)} raw items - correlated items are counted once)"
    )

    cap = Confidence.MODERATE
    if len(groups) >= 2 and not conflicts:
        basis.append("MODERATE permitted: >=2 independent groups, no contradiction")
    else:
        cap = Confidence.LOW
        basis.append("capped LOW: fewer than 2 groups, or a contradiction is present")
    if conflicts:
        cap = Confidence.LOW
        basis.append("capped LOW: directional evidence conflicts")
    if pos.unavailable:
        cap = Confidence.LOW
        basis.append(f"capped LOW: portfolio input missing ({pos.unavailable[0]})")
    if cap is Confidence.MODERATE:
        cap = Confidence.LOW
        basis.append("capped LOW: every directional reading here is EXPERIMENTAL")
    basis.append("HIGH is prohibited in this release")
    return cap, basis


def portfolio_adjustment(
    pos: PositionState, constraints: list[Constraint]
) -> tuple[str | None, str]:
    """Stage 2 inputs. Returns (effect, explanation). Never touches the view."""
    breach = next((c for c in constraints if c.status is ConstraintStatus.BREACH), None)
    if breach is not None:
        return (
            "BREACH",
            f"{breach.name}: observed {breach.observed} against a limit of "
            f"{breach.threshold}. {breach.reason}",
        )
    if pos.market_weight is None:
        return (
            None,
            "Portfolio market value is not computable, so no sizing effect can be "
            "assessed. The action reflects the security view alone.",
        )
    equal = Decimal(1) / Decimal(pos.portfolio_positions)
    ratio = pos.market_weight / equal
    if ratio >= ADD_DISCOURAGE_MULTIPLE:
        return (
            "CONCENTRATED",
            f"The position is {pos.market_weight:.2%} of portfolio market value, "
            f"{ratio:.1f}x an equal weight across {pos.portfolio_positions} holdings "
            f"({equal:.2%}). Equal weight is a descriptive reference, not a policy "
            f"limit: no hard cap has been supplied. This suppresses ADD; it does not "
            f"by itself justify TRIM.",
        )
    return (
        "NORMAL",
        f"The position is {pos.market_weight:.2%} of portfolio market value, "
        f"{ratio:.1f}x an equal weight across {pos.portfolio_positions} holdings. "
        f"No sizing effect applies.",
    )


def event_state_for(evidence: list[Evidence], horizon: str) -> tuple[str, str]:
    """(status, detail) for this horizon. Never returns a direction."""
    hit = next(
        (e for e in evidence if e.name == f"event_state_{horizon}"),
        None,
    )
    if hit is None or hit.status is Status.UNAVAILABLE:
        return "UNAVAILABLE", (hit.missing_reason if hit else "no event item emitted")
    return hit.value.split(" (")[0], hit.value


def decide(
    evidence: list[Evidence], constraints: list[Constraint], pos: PositionState
) -> list[HorizonVerdict]:
    effect, effect_text = portfolio_adjustment(pos, constraints)
    verdicts: list[HorizonVerdict] = []

    for horizon, _ in HORIZONS:
        direction, contributing, conflicts = directional_view(evidence, horizon)
        conf, basis = confidence_for(evidence, horizon, direction, conflicts, pos)
        baseline, why_baseline = _baseline_action(direction, len(contributing))

        event_status, event_detail = event_state_for(evidence, horizon)
        action = baseline
        changed = False
        event_changed = False
        if effect == "BREACH":
            action = Action.EXIT if direction is Direction.NEGATIVE else Action.TRIM
            changed = action is not baseline
        elif effect == "CONCENTRATED" and baseline is Action.ADD:
            action = Action.HOLD
            changed = True
        elif event_status == "IMMINENT" and baseline is Action.ADD:
            # Same established pattern as the concentration guardrail: an
            # unresolved binary event suppresses INITIATING exposure. It never
            # forces a reduction, because proximity carries no sign.
            action = Action.HOLD
            event_changed = True

        if changed and effect == "BREACH":
            sizing = (
                f"A deterministic portfolio limit is breached, which overrides the "
                f"security view. {effect_text} This action is a **risk-limit decision**"
                + (
                    ", reinforced by negative security evidence."
                    if direction is Direction.NEGATIVE
                    else ", not a bearish view on the company."
                )
            )
        elif changed:
            sizing = (
                f"Directional evidence is positive, but existing exposure prevents that "
                f"from translating into ADD. {effect_text} This is a **position-sizing "
                f"effect, not a bearish view on the company**."
            )
        elif event_changed:
            sizing = (
                f"Portfolio exposure did not change this action. {effect_text} "
                f"However an unresolved scheduled event is **IMMINENT** "
                f"({event_detail}). The directional evidence remains "
                f"{direction.value} and is **unchanged**; increasing exposure "
                f"immediately before an unresolved binary event is suppressed by the "
                f"experimental event-risk guardrail. This is a **timing and "
                f"position-management effect, not a view on the outcome** - the "
                f"guardrail is symmetric and carries no expectation of direction."
            )
        else:
            note = (
                f" Scheduled-event state for this horizon: {event_status}."
                if event_status not in ("UNAVAILABLE",)
                else ""
            )
            sizing = (
                f"Portfolio exposure did **not** change this action. {effect_text} "
                f"The recommendation is driven by the security view.{note}"
            )

        rationale = (
            f"Security view is {direction.value}: {why_baseline}, which alone implies "
            f"{baseline.value}. {sizing}"
        )

        elim: list[tuple[str, str]] = []
        for cand in (Action.ADD, Action.HOLD, Action.TRIM, Action.EXIT):
            if cand is action:
                continue
            if cand is Action.ADD:
                elim.append(
                    (
                        "ADD",
                        (
                            "existing exposure suppresses it"
                            if effect == "CONCENTRATED"
                            else (
                                "a portfolio limit is breached"
                                if effect == "BREACH"
                                else f"the security view is {direction.value}, not positive"
                            )
                        ),
                    )
                )
            elif cand is Action.HOLD:
                elim.append(
                    (
                        "HOLD",
                        (
                            "a breached limit cannot be left unaddressed"
                            if effect == "BREACH"
                            else f"the security view is {direction.value}, which indicates "
                            f"{baseline.value} rather than no change"
                        ),
                    )
                )
            elif cand is Action.TRIM:
                elim.append(
                    (
                        "TRIM",
                        "no limit is breached and the security view is not negative; "
                        "concentration alone does not justify reducing exposure without a "
                        "supplied hard cap",
                    )
                )
            else:
                elim.append(
                    (
                        "EXIT",
                        "the security view is not negative enough, and no risk limit "
                        "requires full liquidation",
                    )
                )

        verdicts.append(
            HorizonVerdict(
                horizon=horizon,
                direction=direction,
                action=action,
                confidence=conf,
                contributing=tuple(contributing),
                conflicts=tuple(conflicts),
                rationale=rationale,
                eliminations=tuple(elim),
                confidence_basis=tuple(basis),
            )
        )
    return verdicts
