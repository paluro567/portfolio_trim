"""Historical Analogue Intelligence Model (v1): the eighth evidence source.

Where the seven regime models ask "when was this exact named condition
true?", this model asks "when did the COMBINED market, sector, company,
and catalyst state look most similar?" — and measures what the same
stock did afterward. It enters the platform through the identical
NormalizedEvidence contract, so the Decision Evidence Engine combines it
statistically with everything else (with a conservative overlap prior:
analogues share feature information with every model).

Honesty rules inherited from the platform: below the configured minimum
of valid analogues the model returns a neutral score, never a guess;
earnings proximity and thin catalyst data affect dispersion (standard
error) and therefore confidence — never direction; horizons without
complete forward windows shrink the sample honestly.
"""

import math
from datetime import date

from sqlalchemy.orm import Session

from mip.models.base import (
    Z_CLIP,
    ModelScore,
    RegimeEvidence,
    ScoreDiagnostics,
    confidence_from_evidence,
    overlap_inflation,
    score_from_z,
)
from mip.research.analogues import HORIZONS, AnalogueConfig, AnalogueEngine, AnalogueResult

PRIOR_EVENTS = 30.0  # platform-wide confidence prior


class HistoricalAnalogueModel:
    name = "historical_analogues"
    version = 1

    def __init__(self, session: Session, config: AnalogueConfig | None = None) -> None:
        self._engine = AnalogueEngine(session, config)
        self._config = config or AnalogueConfig()

    def evaluate(self, symbol: str, as_of: date | None = None) -> list[ModelScore]:
        result = self._engine.find(symbol, as_of=as_of)
        return [
            self._score_horizon(result, label, sessions) for label, sessions in HORIZONS.items()
        ]

    # -- scoring ------------------------------------------------------------

    def _score_horizon(self, result: AnalogueResult, label: str, sessions: int) -> ModelScore:
        if result.insufficient is not None:
            return self._neutral(result, label, sessions, result.insufficient)
        outcome = result.outcomes.get(label)
        if (
            outcome is None
            or outcome.n < self._config.minimum_valid_analogues
            or outcome.baseline_mean is None
        ):
            reason = (
                f"only {outcome.n if outcome else 0} analogues have a complete "
                f"{label} forward window (need {self._config.minimum_valid_analogues})"
            )
            return self._neutral(result, label, sessions, reason)

        returns_mean = outcome.weighted_mean_return
        effect = returns_mean - outcome.baseline_mean
        spread = (outcome.p75 - outcome.p25) if None not in (outcome.p75, outcome.p25) else None
        # dispersion of the analogue outcomes -> standard error of the mean;
        # IQR/1.349 approximates sigma robustly, floored to avoid zero-variance
        sigma = max((spread / 1.349) if spread else 0.0, 1e-6)
        analogue_dates = [a.date for a in result.analogues[: outcome.n]]
        inflation = overlap_inflation(sorted(analogue_dates), sessions)
        n_eff = outcome.n / inflation
        se = sigma / math.sqrt(max(n_eff, 1e-9))
        z_raw = effect / se
        z = max(-Z_CLIP, min(Z_CLIP, z_raw))
        score = score_from_z(z)
        confidence = confidence_from_evidence(n_eff, 1.0, PRIOR_EVENTS)

        near_earnings = (result.catalysts.get("days_until_earnings") or 99) <= 7
        evidence = RegimeEvidence(
            label="historical_analogues",
            description=(
                f"the {outcome.n} most similar combined market/sector/company/catalyst "
                f"states (top: {', '.join(d.isoformat() for d in analogue_dates[:3])})"
            ),
            feature="analogue_similarity",
            n=outcome.n,
            n_eff=n_eff,
            mean=returns_mean,
            hit_rate=outcome.p_positive,
            baseline_mean=outcome.baseline_mean,
            excess=effect,
            se=se,
            first_event=min(analogue_dates),
            last_event=max(analogue_dates),
        )
        supporting = (evidence,) if effect > 0 else ()
        opposing = (evidence,) if effect < 0 else ()
        explanation = (
            f"The {outcome.n} closest historical analogues returned "
            f"{returns_mean * 100:+.2f}% on average over {label} "
            f"({outcome.p_positive * 100:.0f}% positive"
            + (
                f", {outcome.p_beat_spy * 100:.0f}% beat SPY"
                if outcome.p_beat_spy is not None
                else ""
            )
            + f") vs a {outcome.baseline_mean * 100:+.2f}% unconditional baseline; "
            f"median max drawdown {outcome.median_max_drawdown * 100:.1f}%."
            + (
                " Earnings within 7 calendar days widen the expected dispersion."
                if near_earnings
                else ""
            )
        )
        return ModelScore(
            model=self.name,
            model_version=self.version,
            symbol=result.symbol,
            as_of=result.as_of,
            horizon=label,
            horizon_sessions=sessions,
            score=score,
            confidence=confidence,
            expected_return=returns_mean,
            historical_hit_rate=outcome.p_positive,
            sample_size=outcome.n,
            strongest_supporting_regimes=supporting,
            strongest_negative_regimes=opposing,
            explanation=explanation,
            active_regimes=self._active_labels(result),
            diagnostics=ScoreDiagnostics(
                active_regimes=1,
                evidence_studies=1,
                max_n_eff=n_eff,
                mean_cross_correlation=0.0,
                agreement=1.0,
                z_raw=z_raw,
                z_clipped=z,
                saturated=abs(z_raw) > Z_CLIP,
            ),
            baseline_return=outcome.baseline_mean,
            excess_return=effect,
            context={
                "environment": result.environment,
                "catalysts": result.catalysts,
                "analogues": [a.to_dict() for a in result.analogues[:10]],
                "outcomes": outcome.to_dict(),
            },
        )

    def _active_labels(self, result: AnalogueResult) -> tuple[str, ...]:
        labels = [
            f"analogue {a.date.isoformat()} sim {a.overall:.2f}" for a in result.analogues[:5]
        ]
        environment = ", ".join(
            f"{key}={value}" for key, value in result.environment.items() if isinstance(value, str)
        )
        if environment:
            labels.append(f"environment: {environment}")
        days_until = result.catalysts.get("days_until_earnings")
        if days_until is not None:
            labels.append(f"earnings in {days_until:.0f} calendar days (confirmed)")
        else:
            labels.append("next earnings date: unavailable")
        return tuple(labels)

    def _neutral(
        self, result: AnalogueResult, label: str, sessions: int, reason: str
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
            sample_size=len(result.analogues),
            strongest_supporting_regimes=(),
            strongest_negative_regimes=(),
            explanation=f"No analogue evidence: {reason}.",
            active_regimes=self._active_labels(result) if result.analogues else (),
            context={
                "environment": result.environment,
                "catalysts": result.catalysts,
                "insufficient": reason,
            },
        )
