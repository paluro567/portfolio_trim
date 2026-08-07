"""Directional view, portfolio action, confidence and elimination trace.

Directional attractiveness and portfolio action are computed separately and
never collapsed. Deterministic constraints override experimental directional
evidence. No probability, no composite score, no hidden numeric formula.
"""

from __future__ import annotations

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


def directional_view(
    evidence: list[Evidence], horizon: str
) -> tuple[Direction, list[str], list[str]]:
    rel = [e for e in evidence if horizon in e.horizons and e.status is not Status.UNAVAILABLE]
    signed = [e for e in rel if e.direction in (Direction.POSITIVE, Direction.NEGATIVE)]
    if not rel:
        return Direction.UNAVAILABLE, [], []
    if not signed:
        return Direction.NEUTRAL, [f"{e.name}={e.value}" for e in rel[:4]], []
    pos = [e.name for e in signed if e.direction is Direction.POSITIVE]
    neg = [e.name for e in signed if e.direction is Direction.NEGATIVE]
    contributing = [f"{e.name}={e.value} ({e.direction.value})" for e in signed]
    if pos and neg:
        return Direction.CONFLICTED, contributing, [f"+{', +'.join(pos)} vs -{', -'.join(neg)}"]
    return (Direction.POSITIVE if pos else Direction.NEGATIVE), contributing, []


def confidence_for(
    evidence: list[Evidence],
    horizon: str,
    direction: Direction,
    conflicts: list[str],
    pos: PositionState,
) -> tuple[Confidence, list[str]]:
    """Transparent caps only. HIGH is prohibited in this slice."""
    basis: list[str] = []
    if direction is Direction.UNAVAILABLE:
        return Confidence.VERY_LOW, ["directional evidence unavailable for this horizon"]

    rel = [e for e in evidence if horizon in e.horizons and e.status is not Status.UNAVAILABLE]
    domains = {e.domain for e in rel}
    basis.append(f"{len(domains)} evidence domain(s) available: {', '.join(sorted(domains))}")

    cap = Confidence.MODERATE
    if len(domains) >= 2 and not conflicts:
        basis.append("MODERATE permitted: >=2 independent domains, no major contradiction")
    else:
        cap = Confidence.LOW
        basis.append("capped at LOW: fewer than 2 independent domains or a contradiction present")

    if conflicts:
        cap = Confidence.LOW
        basis.append("capped at LOW: conflicting directional evidence")

    if pos.unavailable:
        cap = Confidence.LOW
        basis.append(f"capped at LOW: material portfolio input missing ({pos.unavailable[0]})")

    # every directional reading in this slice is experimental
    cap = Confidence.LOW if cap is Confidence.MODERATE else cap
    basis.append("capped at LOW: all directional readings here are EXPERIMENTAL")
    basis.append("HIGH is prohibited in the first vertical slice")
    return cap, basis


def decide(
    evidence: list[Evidence], constraints: list[Constraint], pos: PositionState
) -> list[HorizonVerdict]:
    verdicts: list[HorizonVerdict] = []
    breached = [c for c in constraints if c.status is ConstraintStatus.BREACH]
    blocking: list[str] = []
    cap = next((c for c in constraints if c.name.startswith("Concentration vs hard cap")), None)
    if cap is not None and cap.status is ConstraintStatus.NOT_EVALUABLE:
        blocking.append(f"{cap.name} is NOT_EVALUABLE: {cap.reason}")

    for horizon, _ in HORIZONS:
        direction, contributing, conflicts = directional_view(evidence, horizon)
        conf, basis = confidence_for(evidence, horizon, direction, conflicts, pos)

        elim: list[tuple[str, str]] = []
        if breached:
            c = breached[0]
            action = Action.TRIM
            rationale = (
                f"Deterministic constraint BREACHED: {c.name} - observed {c.observed} "
                f"against a limit of {c.threshold}. {c.reason} A deterministic breach "
                f"overrides directional evidence, which is EXPERIMENTAL."
            )
            elim = [
                ("ADD", "a hard limit is already breached; adding increases the breach"),
                ("HOLD", "holding leaves a breached hard limit unaddressed"),
                (
                    "EXIT",
                    "the breach is of a position-size limit; reducing to the limit "
                    "resolves it, so full liquidation is not required",
                ),
                (
                    "ABSTAIN",
                    "the breach is deterministic and does not depend on any missing "
                    "or experimental input",
                ),
            ]
        elif blocking:
            action = Action.ABSTAIN
            rationale = (
                "No portfolio action can be justified. "
                + " ".join(blocking)
                + " Directional evidence alone is EXPERIMENTAL and may not drive an action."
            )
            elim = [
                (
                    "ADD",
                    "no target allocation has been supplied, so there is no basis for "
                    "increasing exposure; directional evidence is EXPERIMENTAL",
                ),
                (
                    "HOLD",
                    "HOLD asserts the position is within policy. The required policy "
                    "values have not been supplied, so that assertion cannot be made",
                ),
                (
                    "TRIM",
                    "no deterministic constraint is breached; tax impact is unavailable; "
                    "directional evidence is not sufficiently negative and is EXPERIMENTAL",
                ),
                ("EXIT", "no policy or risk condition requires full liquidation"),
            ]
        else:
            action = Action.HOLD
            passing = [c for c in constraints if c.status is ConstraintStatus.PASS]
            rationale = (
                "Every evaluable deterministic constraint passes"
                + (f" ({passing[0].reason})" if passing else "")
                + ". The position is within policy, so no action is required. The "
                "directional view is reported separately and, being EXPERIMENTAL, does "
                "not by itself justify trading."
            )
            elim = [
                (
                    "ADD",
                    "no supplied policy value calls for increasing exposure; "
                    "directional evidence is EXPERIMENTAL",
                ),
                ("TRIM", "no deterministic constraint is breached"),
                ("EXIT", "no policy or risk condition requires full liquidation"),
                (
                    "ABSTAIN",
                    "sufficient policy and portfolio information is available to act",
                ),
            ]

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
