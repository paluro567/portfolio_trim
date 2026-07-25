"""Conditional Probability Model — the SHADOW evidence adapter.

Thin evidence-normalization layer over the research Conditional Probability
Engine: it maps the engine's primary statistic (conditional mean − baseline
mean) and its effective-sample standard error onto ONE ``ModelScore`` per
horizon, carrying the full probabilistic diagnostics in ``context``. No
statistics are computed here beyond z = effect/se and the confidence function;
the Probability Engine in the research layer owns everything else.

Registered in ``SHADOW_MODELS``: evaluated and reported as information, excluded
from the official combined score until it passes ``docs/VALIDATION_GATES.md``.
The decision engine still consumes exactly one effect per horizon; the
per-condition ``ConditionContribution`` diagnostics are context-only and never
become additional evidence.
"""

from datetime import date

from sqlalchemy.orm import Session

from mip.models.base import ModelScore, RegimeEvidence, ScoreDiagnostics
from mip.research.conditional import (
    ConditionalConfig,
    ConditionalEngine,
    ConditionalResult,
    HorizonOutcome,
)
from mip.research.statistics import Z_CLIP, score_from_z

HORIZONS: dict[str, int] = {"1w": 5, "2w": 10, "1m": 21, "3m": 63, "6m": 126, "1y": 252}
PRIOR_EPISODES = 20.0  # effective episodes for confidence 0.5
MIN_EFFECTIVE = 5.0  # below this, a horizon is neutral (no combinable effect)


def conditional_confidence(outcome: HorizonOutcome) -> float:
    """Confidence for one horizon — a single, simple, interpretable function.
    ``volume`` rewards independent episodes (never adjacent dates, since the
    effective sample is episode-based); ``diversity`` penalises domination by
    one symbol or one year. Deliberately NOT the failed analogue logic."""
    effective = outcome.effective.effective
    volume = effective / (effective + PRIOR_EPISODES)
    diversity = 1.0 - max(
        outcome.independence.symbol_concentration,
        outcome.independence.year_concentration,
    )
    return max(0.0, min(1.0, volume * diversity))


class ConditionalProbabilityModel:
    name = "conditional_probability"
    version = 1

    def __init__(self, session: Session, config: ConditionalConfig | None = None) -> None:
        self._engine = ConditionalEngine(session, config)

    def evaluate(self, symbol: str, as_of: date | None = None) -> list[ModelScore]:
        result = self._engine.evaluate(symbol, as_of=as_of)
        return [
            self._score_horizon(result, label, sessions) for label, sessions in HORIZONS.items()
        ]

    # -- scoring -----------------------------------------------------------

    def _score_horizon(self, result: ConditionalResult, label: str, sessions: int) -> ModelScore:
        outcome = result.outcomes.get(label)
        if result.insufficient is not None or outcome is None:
            return self._neutral(result, label, sessions, result.insufficient or "no outcomes")
        if (
            outcome.effect is None
            or outcome.effect_se is None
            or outcome.effect_se <= 0.0
            or outcome.effective.effective < MIN_EFFECTIVE
        ):
            return self._neutral(
                result,
                label,
                sessions,
                f"insufficient conditional support at {label} "
                f"(effective {outcome.effective.effective:.1f})",
            )

        z_raw = outcome.effect / outcome.effect_se
        z = max(-Z_CLIP, min(Z_CLIP, z_raw))
        score = score_from_z(z)
        confidence = conditional_confidence(outcome)
        study = self._study(outcome)
        supporting = (study,) if outcome.effect > 0 else ()
        negative = (study,) if outcome.effect < 0 else ()
        return ModelScore(
            model=self.name,
            model_version=self.version,
            symbol=result.symbol,
            as_of=result.as_of,
            horizon=label,
            horizon_sessions=sessions,
            score=score,
            confidence=confidence,
            expected_return=outcome.absolute.mean,
            historical_hit_rate=outcome.absolute.p_positive,
            sample_size=outcome.absolute.n,
            strongest_supporting_regimes=supporting,
            strongest_negative_regimes=negative,
            explanation=self._explanation(result, outcome, label),
            active_regimes=tuple(c.name for c in result.active_conditions),
            diagnostics=ScoreDiagnostics(
                active_regimes=len(result.active_conditions),
                evidence_studies=1,
                max_n_eff=outcome.effective.effective,
                mean_cross_correlation=0.0,
                agreement=1.0,
                z_raw=z_raw,
                z_clipped=z,
                saturated=abs(z_raw) > Z_CLIP,
            ),
            baseline_return=outcome.baseline_absolute.mean,
            excess_return=outcome.effect,
            context=self._context(result, outcome, label),
        )

    def _study(self, outcome: HorizonOutcome) -> RegimeEvidence:
        return RegimeEvidence(
            label="conditional_probability",
            description=(
                f"cross-sectional history under {outcome.independence.distinct_symbols} symbols / "
                f"{outcome.independence.distinct_calendar_episodes} episodes matching the "
                "current condition set"
            ),
            feature="conditional_conjunction",
            n=outcome.absolute.n,
            n_eff=outcome.effective.effective,
            mean=outcome.absolute.mean if outcome.absolute.mean is not None else 0.0,
            hit_rate=(
                outcome.absolute.p_positive if outcome.absolute.p_positive is not None else 0.0
            ),
            baseline_mean=(
                outcome.baseline_absolute.mean
                if outcome.baseline_absolute.mean is not None
                else 0.0
            ),
            excess=outcome.effect if outcome.effect is not None else 0.0,
            se=outcome.effect_se if outcome.effect_se is not None else 1e-6,
            first_event=outcome.first_date or date(1970, 1, 1),
            last_event=outcome.last_date or date(1970, 1, 1),
        )

    def _explanation(self, result: ConditionalResult, outcome: HorizonOutcome, label: str) -> str:
        base = outcome.baseline_absolute
        return (
            f"Across {outcome.absolute.n} historical observations "
            f"({outcome.independence.distinct_calendar_episodes} independent episodes, "
            f"{outcome.independence.distinct_symbols} symbols) matching the current "
            f"{result.fallback_level} conditions, the {label} forward return averaged "
            f"{(outcome.absolute.mean or 0) * 100:+.1f}% "
            f"({(outcome.absolute.p_positive or 0) * 100:.0f}% positive) vs a "
            f"{(base.mean or 0) * 100:+.1f}% unconditional baseline — an excess of "
            f"{(outcome.effect or 0) * 100:+.1f}pp. Shadow research evidence."
        )

    def _context(self, result: ConditionalResult, outcome: HorizonOutcome, label: str) -> dict:
        return {
            "template_set_version": result.template_set_version,
            "engine_version": result.engine_version,
            "fallback_level": result.fallback_level,
            "active_conditions": [c.to_dict() for c in result.active_conditions],
            "dropped_conditions": list(result.dropped_conditions),
            "outcome": outcome.to_dict(),
            "contributions": [c.to_dict() for c in result.contributions.get(label, ())],
            "status": "shadow_research_evidence",
        }

    def _neutral(
        self, result: ConditionalResult, label: str, sessions: int, reason: str
    ) -> ModelScore:
        return ModelScore(
            model=self.name,
            model_version=self.version,
            symbol=result.symbol,
            as_of=result.as_of,
            horizon=label,
            horizon_sessions=sessions,
            score=50.0,
            confidence=0.0,
            expected_return=None,
            historical_hit_rate=None,
            sample_size=0,
            strongest_supporting_regimes=(),
            strongest_negative_regimes=(),
            explanation=f"No conditional evidence at {label}: {reason}. Shadow research evidence.",
            active_regimes=tuple(c.name for c in result.active_conditions),
            context={
                "template_set_version": result.template_set_version,
                "fallback_level": result.fallback_level,
                "insufficient": reason,
                "status": "shadow_research_evidence",
            },
        )
