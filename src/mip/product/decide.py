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

# Descriptive sizing reference, NOT a policy limit. Equal weight across the
# holdings actually present. Used only to discourage ADD, never to force TRIM.
ADD_DISCOURAGE_MULTIPLE = Decimal(3)


def directional_view(
    evidence: list[Evidence], horizon: str
) -> tuple[Direction, list[str], list[str]]:
    """Stage 1. Security evidence only."""
    rel = [
        e
        for e in evidence
        if horizon in e.horizons
        and e.status is not Status.UNAVAILABLE
        and e.domain in SECURITY_DOMAINS
    ]
    signed = [e for e in rel if e.direction in (Direction.POSITIVE, Direction.NEGATIVE)]
    if not rel:
        return Direction.UNAVAILABLE, [], []
    if not signed:
        return Direction.NEUTRAL, [f"{e.name}={e.value}" for e in rel[:5]], []
    pos = [e for e in signed if e.direction is Direction.POSITIVE]
    neg = [e for e in signed if e.direction is Direction.NEGATIVE]
    contributing = [f"{e.name}={e.value} ({e.direction.value})" for e in signed]
    if pos and neg:
        conflict = (
            f"{len(pos)} positive ({', '.join(e.name for e in pos)}) against "
            f"{len(neg)} negative ({', '.join(e.name for e in neg)})"
        )
        return Direction.CONFLICTED, contributing, [conflict]
    return (Direction.POSITIVE if pos else Direction.NEGATIVE), contributing, []


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
    ]
    domains = sorted({e.domain for e in rel})
    basis.append(f"{len(domains)} security-evidence domain(s): {', '.join(domains)}")

    cap = Confidence.MODERATE
    if len(domains) >= 2 and not conflicts:
        basis.append("MODERATE permitted: >=2 independent domains, no contradiction")
    else:
        cap = Confidence.LOW
        basis.append("capped LOW: fewer than 2 domains, or a contradiction is present")
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


def decide(
    evidence: list[Evidence], constraints: list[Constraint], pos: PositionState
) -> list[HorizonVerdict]:
    effect, effect_text = portfolio_adjustment(pos, constraints)
    verdicts: list[HorizonVerdict] = []

    for horizon, _ in HORIZONS:
        direction, contributing, conflicts = directional_view(evidence, horizon)
        conf, basis = confidence_for(evidence, horizon, direction, conflicts, pos)
        baseline, why_baseline = _baseline_action(direction, len(contributing))

        action = baseline
        changed = False
        if effect == "BREACH":
            action = Action.EXIT if direction is Direction.NEGATIVE else Action.TRIM
            changed = action is not baseline
        elif effect == "CONCENTRATED" and baseline is Action.ADD:
            action = Action.HOLD
            changed = True

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
        else:
            sizing = (
                f"Portfolio exposure did **not** change this action. {effect_text} "
                f"The recommendation is driven by the security view."
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
