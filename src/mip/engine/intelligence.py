"""Portfolio Intelligence Engine: one coherent research evaluation per
holding, synthesized from every existing evidence source.

Interpretation only — no prediction, no feature generation, no data
ingestion, no new statistics. The engine consumes the models through the
established NormalizedEvidence contract (via DecisionEvidenceEngine's
single gather pass), reuses the frozen combination -> trim -> attribution
chain verbatim, and adds the layers a research analyst needs: thematic
sections, bull/bear theses, key drivers, what changed since the last
archived evaluation, explicit unknowns, and a fully explained
recommendation.

Shadow discipline: evidence in SHADOW_MODELS (currently the analogue
model, per its failed out-of-sample validation) is reported as
informational context only and never contributes to theses, drivers,
scores, or recommendations.

Extensibility: a future evidence source plugs in by implementing the
model contract (`name`, `version`, `evaluate(symbol, as_of) ->
list[ModelScore]`) and registering in `mip.models.ALL_MODELS`; this
engine and everything downstream consume it without change.
"""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.engine.attribution import attribute
from mip.engine.evidence import (
    HORIZONS,
    SHADOW_MODELS,
    DecisionEvidence,
    DecisionEvidenceEngine,
    combine_model_evidence,
)
from mip.engine.trim import TrimAssessment, TrimConfig, assess_symbol
from mip.models.evidence import NormalizedEvidence
from mip.portfolio.analytics import PortfolioAnalyzer, PortfolioPositionAssessment
from mip.repositories.predictions import PredictionRepository

FOCUS = "1m"

# thematic section -> the evidence models that inform it (interpretation
# routing only; the models remain the sole owners of their logic)
SECTION_SOURCES: dict[str, tuple[str, ...]] = {
    "company": ("valuation", "earnings_behavior"),
    "technical": ("momentum_exhaustion", "relative_strength"),
    "macro": ("interest_rate_sensitivity", "macro_regime"),
    "market": ("macro_regime",),
    "sector": ("sector_rotation",),
    "catalysts": ("earnings_behavior",),
}
NOT_MODELED = {
    "company": (
        "business quality, growth, profitability, and capital allocation are "
        "not yet covered by any evidence model (valuation activates once "
        "~1 year of fundamentals snapshots accumulates)"
    ),
}


@dataclass(frozen=True)
class ThesisPoint:
    """One ranked observation with machine-readable provenance: provider
    (model), observation id (label), direction (sign of excess),
    uncertainty (se), horizon, and the study's event span."""

    model: str
    label: str
    description: str
    excess: float
    se: float
    hit_rate: float | None
    n: int
    strength: float  # |excess| / se
    horizon: str
    first_event: str | None = None
    last_event: str | None = None

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "label": self.label,
            "description": self.description,
            "excess": self.excess,
            "se": self.se,
            "direction": "supports_ownership" if self.excess > 0 else "supports_reduction",
            "hit_rate": self.hit_rate,
            "n": self.n,
            "strength": self.strength,
            "horizon": self.horizon,
            "first_event": self.first_event,
            "last_event": self.last_event,
        }


@dataclass(frozen=True)
class EvidenceSection:
    name: str
    verdict: str
    detail: tuple[str, ...]
    sources: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "verdict": self.verdict,
            "detail": list(self.detail),
            "sources": list(self.sources),
        }


@dataclass(frozen=True)
class HoldingIntelligence:
    """The complete, explainable evaluation of one holding — the single
    source of truth for reports, dashboards, and future interfaces."""

    symbol: str
    as_of: date
    portfolio_name: str | None
    sections: dict[str, EvidenceSection]
    bull_thesis: tuple[ThesisPoint, ...]
    bear_thesis: tuple[ThesisPoint, ...]
    key_drivers: tuple[dict, ...]
    what_changed: tuple[dict, ...]
    unknowns: tuple[str, ...]
    horizons: tuple[dict, ...]  # per-horizon trim view
    recommendation: dict
    shadow_evidence: dict
    traceability: dict
    assessments: tuple[TrimAssessment, ...] = field(compare=False, repr=False, default=())

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "portfolio_name": self.portfolio_name,
            "sections": {k: s.to_dict() for k, s in self.sections.items()},
            "bull_thesis": [p.to_dict() for p in self.bull_thesis],
            "bear_thesis": [p.to_dict() for p in self.bear_thesis],
            "key_drivers": list(self.key_drivers),
            "what_changed": list(self.what_changed),
            "unknowns": list(self.unknowns),
            "horizons": list(self.horizons),
            "recommendation": self.recommendation,
            "shadow_evidence": self.shadow_evidence,
            "traceability": self.traceability,
        }


# -- pure reasoning helpers ---------------------------------------------------


def _verdict(evidences: list[NormalizedEvidence]) -> str:
    active = [e for e in evidences if not e.neutral]
    if not active:
        return "no active evidence"
    mean_score = sum(e.score for e in active) / len(active)
    if mean_score >= 60:
        return "supportive"
    if mean_score <= 40:
        return "unfavorable"
    return "mixed"


def build_sections(
    per_model: dict[str, NormalizedEvidence],
    assessment: TrimAssessment,
) -> dict[str, EvidenceSection]:
    sections: dict[str, EvidenceSection] = {}
    for name, sources in SECTION_SOURCES.items():
        evidences = [per_model[m] for m in sources if m in per_model]
        detail: list[str] = []
        for e in evidences:
            detail.append(f"[{e.model_name}] {e.explanation}")
        if name in NOT_MODELED:
            detail.append(f"not modeled: {NOT_MODELED[name]}")
        if name == "market":
            regimes = [r for e in evidences for r in e.active_regimes if not e.neutral]
            if regimes:
                detail.append("active market regimes: " + "; ".join(regimes[:4]))
        sections[name] = EvidenceSection(
            name=name,
            verdict=_verdict(evidences),
            detail=tuple(detail),
            sources=tuple(e.model_name for e in evidences) or ("none",),
        )

    strongest = sorted(
        (
            r
            for m, e in per_model.items()
            if m not in SHADOW_MODELS and not e.neutral
            for r in (*e.supporting_reasons, *e.opposing_reasons)
            if r.se > 0
        ),
        key=lambda r: -abs(r.excess / r.se),
    )[:3]
    sections["historical"] = EvidenceSection(
        name="historical",
        verdict="summarized" if strongest else "no active studies",
        detail=tuple(
            f"{r.description} — n={r.n}, excess {r.excess * 100:+.1f}pp, "
            f"hit rate {r.hit_rate * 100:.0f}%"
            for r in strongest
        ),
        sources=tuple(dict.fromkeys(r.label.split()[0] for r in strongest)) or ("none",),
    )
    portfolio_detail: list[str] = []
    if assessment.portfolio_weight is not None:
        portfolio_detail.append(
            f"weight {assessment.portfolio_weight:.1%}; risk contribution "
            + (
                f"{assessment.risk_contribution:.0%}"
                if assessment.risk_contribution is not None
                else "unavailable"
            )
            + f"; trim adjustment {assessment.portfolio_adjustment:+.1f}"
        )
        portfolio_detail.extend(assessment.concentration_flags)
    else:
        portfolio_detail.append("no portfolio context supplied")
    sections["portfolio"] = EvidenceSection(
        name="portfolio",
        verdict=(
            "concentration pressure" if assessment.portfolio_adjustment > 0 else "no pressure"
        ),
        detail=tuple(portfolio_detail),
        sources=("portfolio_analyzer",),
    )
    return sections


def build_theses(
    per_model: dict[str, NormalizedEvidence], limit: int = 5
) -> tuple[tuple[ThesisPoint, ...], tuple[ThesisPoint, ...]]:
    """Top observations for and against ownership — shadow evidence and
    neutral models never contribute."""
    points: list[ThesisPoint] = []
    for model, evidence in per_model.items():
        if model in SHADOW_MODELS or evidence.neutral:
            continue
        for reason in (*evidence.supporting_reasons, *evidence.opposing_reasons):
            if reason.se <= 0:
                continue
            points.append(
                ThesisPoint(
                    model=model,
                    label=reason.label,
                    description=reason.description,
                    excess=reason.excess,
                    se=reason.se,
                    hit_rate=reason.hit_rate,
                    n=reason.n,
                    strength=abs(reason.excess / reason.se),
                    horizon=evidence.horizon,
                    first_event=(reason.first_event.isoformat() if reason.first_event else None),
                    last_event=(reason.last_event.isoformat() if reason.last_event else None),
                )
            )
    seen: set[tuple[str, str]] = set()
    unique = []
    for point in sorted(points, key=lambda p: (-p.strength, p.model, p.label)):
        key = (point.model, point.label)
        if key not in seen:
            seen.add(key)
            unique.append(point)
    bull = tuple(p for p in unique if p.excess > 0)[:limit]
    bear = tuple(p for p in unique if p.excess < 0)[:limit]
    return bull, bear


def diff_against_previous(
    assessments: list[TrimAssessment], previous: dict[str, dict]
) -> tuple[dict, ...]:
    """What changed vs the latest archived evaluation, per horizon.
    `previous` maps horizon -> archived prediction fields."""
    changes: list[dict] = []
    for assessment in assessments:
        prior = previous.get(assessment.horizon)
        if prior is None:
            changes.append(
                {
                    "horizon": assessment.horizon,
                    "note": "first archived evaluation — no prior to compare",
                }
            )
            continue
        if prior.get("trim_engine_version") not in (None, assessment.engine_version):
            changes.append(
                {
                    "horizon": assessment.horizon,
                    "note": (
                        f"prior evaluation used trim engine "
                        f"v{prior['trim_engine_version']} (current "
                        f"v{assessment.engine_version}) — incompatible, not compared"
                    ),
                }
            )
            continue
        delta = assessment.trim_score - prior["trim_score"]
        record = {
            "horizon": assessment.horizon,
            "previous_as_of": prior["as_of"],
            "trim_delta": round(delta, 2),
            "previous_trim": prior["trim_score"],
            "current_trim": assessment.trim_score,
            "label_change": (
                f"{prior['recommendation_label']} -> {assessment.recommendation_label}"
                if prior["recommendation_label"] != assessment.recommendation_label
                else None
            ),
            "notes": [],
        }
        prior_driver = (prior.get("primary_trim_drivers") or [None])[0]
        current_driver = (
            assessment.primary_trim_drivers[0] if assessment.primary_trim_drivers else None
        )
        if prior_driver != current_driver:
            record["notes"].append(
                f"primary trim driver changed: {prior_driver or '—'} -> {current_driver or '—'}"
            )
        prior_participants = set(prior.get("participating_models") or [])
        current_participants = set(assessment.participating_models)
        joined = sorted(current_participants - prior_participants)
        left = sorted(prior_participants - current_participants)
        if joined:
            record["notes"].append("evidence appeared: " + ", ".join(joined))
        if left:
            record["notes"].append("evidence went quiet: " + ", ".join(left))
        prior_confidence = prior.get("confidence")
        if prior_confidence is not None and abs(assessment.confidence - prior_confidence) >= 0.15:
            record["notes"].append(
                f"confidence moved {prior_confidence:.2f} -> {assessment.confidence:.2f}"
            )
        prior_excess = prior.get("expected_excess_return")
        current_excess = assessment.expected_excess_return
        if (
            prior_excess is not None
            and current_excess is not None
            and (prior_excess > 0) != (current_excess > 0)
        ):
            record["notes"].append(
                f"evidence direction flipped: expected excess "
                f"{prior_excess * 100:+.2f}% -> {current_excess * 100:+.2f}%"
            )
        prior_adjustment = prior.get("portfolio_adjustment")
        if (
            prior_adjustment is not None
            and abs(assessment.portfolio_adjustment - prior_adjustment) > 1.0
        ):
            record["notes"].append(
                f"portfolio adjustment moved {prior_adjustment:+.1f} -> "
                f"{assessment.portfolio_adjustment:+.1f}"
            )
        changes.append(record)
    return tuple(changes)


def build_unknowns(
    per_model: dict[str, NormalizedEvidence],
    assessment: TrimAssessment,
    omitted: tuple[str, ...],
) -> tuple[dict, ...]:
    """Structured, machine-readable unknowns. The kinds are DISTINCT
    states, never conflated: neutral (evaluated, honestly nothing),
    omitted (could not evaluate), data_quality (thin/conflicted sample),
    shadow (rejected evidence, informational), coverage_gap (dimension no
    model measures), risk_decomposition (portfolio covariance window)."""
    unknowns: list[dict] = []
    for model, evidence in per_model.items():
        if evidence.neutral and model not in SHADOW_MODELS:
            unknowns.append({"kind": "neutral", "model": model, "detail": evidence.explanation})
    for model in omitted:
        unknowns.append(
            {
                "kind": "omitted",
                "model": model,
                "detail": "could not be evaluated in this data environment",
            }
        )
    if assessment.data_quality_label in ("sparse", "no_evidence", "conflicted"):
        unknowns.append(
            {
                "kind": "data_quality",
                "model": None,
                "detail": (
                    f"focus-horizon data quality is {assessment.data_quality_label!r} — "
                    "interpret direction, not magnitude"
                ),
            }
        )
    for shadow in sorted(SHADOW_MODELS & set(per_model)):
        unknowns.append(
            {
                "kind": "shadow",
                "model": shadow,
                "detail": (
                    "shadow-only (failed out-of-sample validation); reported as "
                    "information, excluded from every score and thesis"
                ),
            }
        )
    if assessment.risk_contribution is None and assessment.portfolio_weight is not None:
        unknowns.append(
            {
                "kind": "risk_decomposition",
                "model": None,
                "detail": "portfolio risk decomposition unavailable (covariance window)",
            }
        )
    unknowns.append({"kind": "coverage_gap", "model": None, "detail": NOT_MODELED["company"]})
    return tuple(unknowns)


def build_recommendation(
    assessment: TrimAssessment,
    bull: tuple[ThesisPoint, ...],
    bear: tuple[ThesisPoint, ...],
    shadow_context: dict,
    config: TrimConfig | None = None,
) -> dict:
    """The trim verdict, fully explained. The label is the deterministic
    band lookup on the frozen TrimConfig thresholds (unchanged since the
    trim phase — no new thresholds); labels summarize historical evidence
    and are not trade instructions."""
    config = config or TrimConfig()
    index = config.band_index(assessment.trim_score)
    boundaries = []
    if index > 0:
        lower_band = config.bands[index - 1]
        boundaries.append(
            f"a {assessment.trim_score - lower_band.upper:.1f}-point decrease "
            f"crosses into {lower_band.label!r}"
        )
    if index < len(config.bands) - 1:
        band = config.bands[index]
        boundaries.append(
            f"a {band.upper - assessment.trim_score:.1f}-point increase "
            f"crosses into {config.bands[index + 1].label!r}"
        )
    supporting = bear if assessment.trim_score >= 50 else bull
    conflicting = bull if assessment.trim_score >= 50 else bear
    catalysts = (shadow_context or {}).get("catalysts") or {}
    days_until = catalysts.get("days_until_earnings")
    return {
        "label": assessment.recommendation_label,
        "trim_score": assessment.trim_score,
        "horizon": assessment.horizon,
        "mapping_rule": (
            "deterministic band lookup on the frozen trim thresholds with the "
            "existing confidence gates (no thresholds introduced or tuned)"
        ),
        "confidence": assessment.confidence,
        "why": [f"[{p.model}] {p.description}" for p in supporting[:3]]
        or ["evidence is balanced; no directional case dominates"],
        "conflicting_evidence": [f"[{p.model}] {p.description}" for p in conflicting[:3]],
        "major_risks": [f"[{p.model}] {p.description}" for p in bear[:3]],
        "conditions_to_change": boundaries,
        "expected_catalysts": (
            [f"next earnings in {days_until:.0f} calendar days (confirmed)"]
            if days_until is not None
            else ["next earnings date unavailable"]
        ),
        "disclaimer": "labels summarize historical evidence; not personalized financial advice",
    }


# -- the engine ---------------------------------------------------------------


class PortfolioIntelligenceEngine:
    """Synthesis on top of the frozen evidence -> decision -> trim ->
    attribution chain: ONE model pass per holding feeds everything."""

    def __init__(self, session: Session, config: TrimConfig | None = None) -> None:
        self._session = session
        self._decision = DecisionEvidenceEngine(session)
        self._config = config or TrimConfig()
        self._predictions = PredictionRepository(session)

    def evaluate(
        self,
        symbols: list[str] | None = None,
        portfolio: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, HoldingIntelligence]:
        assessments_by_symbol: dict[str, PortfolioPositionAssessment] = {}
        if portfolio is not None:
            for position in PortfolioAnalyzer(self._session).analyze(
                portfolio, as_of=as_of, with_evidence=False
            ):
                assessments_by_symbol[position.symbol] = position
        if symbols is None:
            if portfolio is None:
                raise ConfigurationError("provide symbols or --portfolio")
            symbols = sorted(assessments_by_symbol)
        else:
            symbols = [s.strip().upper() for s in symbols]
        return {
            symbol: self._holding(symbol, assessments_by_symbol.get(symbol), as_of)
            for symbol in symbols
        }

    # -- per holding -------------------------------------------------------

    def _previous(self, symbol: str, portfolio_key: str, before: date) -> dict[str, dict]:
        rows = self._predictions.latest_before(symbol, portfolio_key, before)
        return {
            row.horizon: {
                "as_of": row.as_of.isoformat(),
                "trim_score": row.trim_score,
                "recommendation_label": row.recommendation_label,
                "primary_trim_drivers": row.primary_trim_drivers,
                "participating_models": row.participating_models,
                "confidence": row.confidence,
                "expected_excess_return": row.expected_excess_return,
                "portfolio_adjustment": row.portfolio_adjustment,
                "trim_engine_version": row.trim_engine_version,
            }
            for row in rows
        }

    def _holding(
        self,
        symbol: str,
        position: PortfolioPositionAssessment | None,
        as_of: date | None,
    ) -> HoldingIntelligence:
        by_model, omitted, resolved = self._decision.gather(symbol, as_of)
        evidences: list[DecisionEvidence] = [
            combine_model_evidence(
                symbol,
                horizon,
                resolved,
                {m: horizons[horizon] for m, horizons in by_model.items()},
                omitted=omitted,
                assessment=position,
            )
            for horizon in HORIZONS
        ]
        assessments = assess_symbol(evidences, self._config)
        by_horizon_evidence = {e.horizon: e for e in evidences}
        focus = next(a for a in assessments if a.horizon == FOCUS)
        focus_attribution = attribute(focus, by_horizon_evidence[FOCUS])
        focus_models = {m: horizons[FOCUS] for m, horizons in by_model.items()}

        bull, bear = build_theses(focus_models)
        shadow_context = {
            m: focus_models[m].context or {} for m in SHADOW_MODELS & set(focus_models)
        }
        shadow_payload = {
            m: {
                "score": focus_models[m].score,
                "explanation": focus_models[m].explanation,
                "status": "shadow — informational only, excluded from all scores",
                "context": shadow_context.get(m, {}),
            }
            for m in SHADOW_MODELS & set(focus_models)
        }
        previous = self._previous(symbol, focus.portfolio_name or "", resolved)

        return HoldingIntelligence(
            symbol=symbol,
            as_of=resolved,
            portfolio_name=focus.portfolio_name,
            sections=build_sections(focus_models, focus),
            bull_thesis=bull,
            bear_thesis=bear,
            key_drivers=tuple(r.to_dict() for r in focus_attribution.contribution_ranking),
            what_changed=diff_against_previous(list(assessments), previous),
            unknowns=build_unknowns(focus_models, focus, omitted),
            horizons=tuple(
                {
                    "horizon": a.horizon,
                    "trim_score": a.trim_score,
                    "confidence": a.confidence,
                    "label": a.recommendation_label,
                    "expected_excess": a.expected_excess_return,
                    "quality": a.data_quality_label,
                }
                for a in assessments
            ),
            recommendation=build_recommendation(
                focus, bull, bear, next(iter(shadow_context.values()), {}), self._config
            ),
            shadow_evidence=shadow_payload,
            traceability={
                "focus_horizon": FOCUS,
                "participating_models": list(focus.participating_models),
                "neutral_models": list(focus.neutral_models),
                "shadow_models": list(by_horizon_evidence[FOCUS].shadow_models),
                "omitted_models": list(omitted),
                "attribution_sums_to": focus_attribution.trim_score,
                "trim_engine_version": focus.engine_version,
            },
            assessments=tuple(assessments),
        )


# -- institutional report -----------------------------------------------------


def render_institutional(hi: HoldingIntelligence) -> str:
    """The institutional research report — every line traceable to the
    intelligence object, which is itself traceable to point-in-time
    evidence."""
    lines: list[str] = []
    focus = next(h for h in hi.horizons if h["horizon"] == FOCUS)
    rec = hi.recommendation

    lines.append(f"# {hi.symbol} — Institutional Research Report")
    lines.append(
        f"*As of {hi.as_of}; focus horizon {FOCUS}"
        + (f"; portfolio {hi.portfolio_name}" if hi.portfolio_name else "")
        + ".*\n"
    )
    lines.append("## Executive Summary")
    lines.append(
        f"Trim score {focus['trim_score']:.1f} ({rec['label']}) at confidence "
        f"{focus['confidence']:.2f}; evidence quality {focus['quality']}. "
        + (
            hi.bull_thesis[0].description
            if focus["trim_score"] < 50 and hi.bull_thesis
            else (
                hi.bear_thesis[0].description
                if hi.bear_thesis
                else "No dominant directional evidence."
            )
        )
    )
    lines.append("\n## Investment Thesis (Bull)")
    for p in hi.bull_thesis or ():
        lines.append(
            f"- [{p.model}] {p.description} (excess {p.excess * 100:+.1f}pp, "
            f"hit {p.hit_rate * 100:.0f}%, n={p.n})"
        )
    if not hi.bull_thesis:
        lines.append("- no active supporting studies")
    lines.append("\n## Bear Thesis")
    for p in hi.bear_thesis or ():
        lines.append(
            f"- [{p.model}] {p.description} (excess {p.excess * 100:+.1f}pp, "
            f"hit {p.hit_rate * 100:.0f}%, n={p.n})"
        )
    if not hi.bear_thesis:
        lines.append("- no active opposing studies")

    titles = {
        "macro": "Macro Environment",
        "market": "Market Environment",
        "sector": "Sector Environment",
        "company": "Company Fundamentals & Valuation",
        "technical": "Technical Condition",
        "catalysts": "Catalysts",
        "historical": "Historical Research",
        "portfolio": "Portfolio Context",
    }
    for key in (
        "macro",
        "market",
        "sector",
        "company",
        "technical",
        "catalysts",
        "historical",
        "portfolio",
    ):
        section = hi.sections[key]
        lines.append(f"\n## {titles[key]}  ({section.verdict})")
        for item in section.detail:
            lines.append(f"- {item}")

    lines.append("\n## Key Drivers (exact attribution, sums to the trim score)")
    for driver in hi.key_drivers:
        lines.append(
            f"- {driver['name']}: {driver['contribution']:+.2f} -> {driver['cumulative']:.2f}"
        )
    lines.append("\n## What Changed")
    for change in hi.what_changed:
        if "note" in change:
            lines.append(f"- {change['horizon']}: {change['note']}")
            continue
        summary = (
            f"- {change['horizon']}: {change['previous_trim']:.1f} -> "
            f"{change['current_trim']:.1f} ({change['trim_delta']:+.1f}"
            f" vs {change['previous_as_of']})"
        )
        if change.get("label_change"):
            summary += f"; {change['label_change']}"
        lines.append(summary)
        for note in change.get("notes", []):
            lines.append(f"    - {note}")
    lines.append("\n## Unknowns & Items To Monitor")
    for unknown in hi.unknowns:
        prefix = f"[{unknown['kind']}] " + (f"{unknown['model']}: " if unknown["model"] else "")
        lines.append(f"- {prefix}{unknown['detail']}")
    lines.append("\n## Horizon View")
    for h in hi.horizons:
        excess = f"{h['expected_excess'] * 100:+.2f}%" if h["expected_excess"] is not None else "—"
        lines.append(
            f"- {h['horizon']:>3}: trim {h['trim_score']:5.1f}  conf {h['confidence']:.2f}  "
            f"excess {excess}  {h['label']} [{h['quality']}]"
        )
    lines.append("\n## Recommendation")
    lines.append(
        f"**{rec['label']}** (trim {rec['trim_score']:.1f}, confidence {rec['confidence']:.2f})"
    )
    lines.append("\nWhy:")
    for item in rec["why"]:
        lines.append(f"- {item}")
    lines.append("\nConflicting evidence:")
    for item in rec["conflicting_evidence"] or ["- none"]:
        lines.append(f"- {item}" if not item.startswith("-") else item)
    lines.append("\nConditions that would change this assessment:")
    for item in rec["conditions_to_change"]:
        lines.append(f"- {item}")
    lines.append("\nExpected catalysts:")
    for item in rec["expected_catalysts"]:
        lines.append(f"- {item}")
    if hi.shadow_evidence:
        lines.append("\n## Shadow Evidence (informational only — excluded from all scores)")
        for name, payload in hi.shadow_evidence.items():
            lines.append(f"- {name}: {payload['explanation']} [{payload['status']}]")
    lines.append(f"\n*{rec['disclaimer']}.*")
    return "\n".join(lines)
