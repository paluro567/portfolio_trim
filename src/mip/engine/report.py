"""Portfolio Decision Report Generator: TrimAssessment + AttributionReport
in, human-readable decision reports out.

This layer performs NO statistical analysis. Every number is copied from
the two permitted inputs; the only operations are counting, min/max,
sorting, and the max-minus-min spread of existing trim scores. Narratives
are deterministic templates whose every clause is a formatted input field.
Rankings use direct existing values with explicit, tested rules; missing
values (no portfolio context, no evidence) sort into their own explicit
places and are never treated as favorable or unfavorable evidence.

Total market value is NOT available on the permitted inputs (they carry
weight shares, not currency amounts) and is reported as unavailable
rather than fetched from lower layers.

Labels summarize historical evidence; they are not trade instructions or
personalized financial advice.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.engine.attribution import AttributionEngine, AttributionReport, RankedContribution
from mip.engine.trim import HORIZON_SESSIONS, TrimAssessment, TrimConfig

GENERATOR_VERSION = 1
HORIZONS = tuple(HORIZON_SESSIONS)
HORIZON_WORDS = {
    "1w": "1-week",
    "2w": "2-week",
    "1m": "1-month",
    "3m": "3-month",
    "6m": "6-month",
    "1y": "1-year",
}
SUMMARY_HORIZONS = ("1w", "1m", "3m", "6m", "1y")  # per the report contract
TRIM_LABELS = ("Trim", "Strong Trim Candidate")  # post-gate, confidence-guaranteed
MAINTAIN_LABEL = "Maintain"
MIXED_LABEL = "Mixed Evidence"
DISCLAIMER = (
    "Labels summarize historical evidence; they are not trade instructions "
    "or personalized financial advice."
)
MARKET_VALUE_NOTE = (
    "total market value is not carried on TrimAssessment/AttributionReport "
    "(weight shares only) and is not fetched from lower layers"
)


@dataclass(frozen=True)
class ReportOptions:
    """Report shaping only — never statistics. `focus_horizon` selects the
    deep-dive horizon; `top` caps every ranked section; `min_confidence`
    gates the strongest-maintain section (default mirrors the Maintain
    label's confidence floor)."""

    focus_horizon: str = "1m"
    top: int = 10
    min_confidence: float = 0.40

    def __post_init__(self) -> None:
        if self.focus_horizon not in HORIZONS:
            raise ConfigurationError(f"unknown horizon {self.focus_horizon!r}; use {HORIZONS}")
        if self.top < 1:
            raise ConfigurationError("top must be >= 1")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ConfigurationError("min_confidence must be within [0, 1]")


@dataclass(frozen=True)
class HorizonRow:
    """One horizon of the symbol report — every field verbatim from the
    TrimAssessment."""

    horizon: str
    trim_score: float
    evidence_trim_score: float
    portfolio_adjustment: float
    confidence: float
    expected_return: float | None
    expected_excess_return: float | None
    recommendation_label: str
    data_quality_label: str
    primary_driver: str | None
    label_downgraded: bool

    def to_dict(self) -> dict:
        return {
            "horizon": self.horizon,
            "trim_score": self.trim_score,
            "evidence_trim_score": self.evidence_trim_score,
            "portfolio_adjustment": self.portfolio_adjustment,
            "confidence": self.confidence,
            "expected_return": self.expected_return,
            "expected_excess_return": self.expected_excess_return,
            "recommendation_label": self.recommendation_label,
            "data_quality_label": self.data_quality_label,
            "primary_driver": self.primary_driver,
            "label_downgraded": self.label_downgraded,
        }


@dataclass(frozen=True)
class SymbolDecisionReport:
    """One symbol, all horizons, with the deep-dive sections rendered for
    the focus horizon. Attribution rows are carried verbatim so the final
    score is reproducible from this object alone."""

    symbol: str
    as_of: date
    focus_horizon: str
    # portfolio context (verbatim; None/() without a portfolio)
    portfolio_name: str | None
    portfolio_weight: float | None
    risk_contribution: float | None
    diversification_contribution: float | None
    concentration_flags: tuple[str, ...]
    # horizon summary
    horizon_rows: tuple[HorizonRow, ...]
    cross_horizon_interpretation: tuple[str, ...]
    # focus-horizon deep dive
    trim_score: float
    confidence: float
    recommendation_label: str
    strengths: tuple[dict, ...]  # entries lowering the trim score
    strengths_reason: dict | None  # strongest historical reason to stay exposed
    risks: tuple[dict, ...]  # entries raising the trim score
    risks_reason: dict | None  # strongest historical reason to reduce
    uncertainty: dict
    neutral_baseline: float
    attribution_rows: tuple[RankedContribution, ...]
    narrative: str
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "focus_horizon": self.focus_horizon,
            "portfolio_name": self.portfolio_name,
            "portfolio_weight": self.portfolio_weight,
            "risk_contribution": self.risk_contribution,
            "diversification_contribution": self.diversification_contribution,
            "concentration_flags": list(self.concentration_flags),
            "horizon_rows": [row.to_dict() for row in self.horizon_rows],
            "cross_horizon_interpretation": list(self.cross_horizon_interpretation),
            "trim_score": self.trim_score,
            "confidence": self.confidence,
            "recommendation_label": self.recommendation_label,
            "strengths": list(self.strengths),
            "strengths_reason": self.strengths_reason,
            "risks": list(self.risks),
            "risks_reason": self.risks_reason,
            "uncertainty": self.uncertainty,
            "neutral_baseline": self.neutral_baseline,
            "attribution_rows": [row.to_dict() for row in self.attribution_rows],
            "narrative": self.narrative,
            "disclaimer": self.disclaimer,
        }


@dataclass(frozen=True)
class PortfolioDecisionReport:
    """Every current holding, ranked by explicit rules on existing values,
    at one focus horizon (cross-horizon section spans all six)."""

    portfolio_name: str
    as_of: date
    generated_at: datetime
    focus_horizon: str
    overview: dict
    highest_trim: tuple[dict, ...]
    strongest_maintain: tuple[dict, ...]
    portfolio_pressure: tuple[dict, ...]
    diversification: tuple[dict, ...]
    model_agreement: tuple[dict, ...]
    greatest_uncertainty: tuple[dict, ...]
    cross_horizon_changes: tuple[dict, ...]
    position_summaries: tuple[dict, ...]
    narrative: str
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "portfolio_name": self.portfolio_name,
            "as_of": self.as_of.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "focus_horizon": self.focus_horizon,
            "overview": self.overview,
            "highest_trim": list(self.highest_trim),
            "strongest_maintain": list(self.strongest_maintain),
            "portfolio_pressure": list(self.portfolio_pressure),
            "diversification": list(self.diversification),
            "model_agreement": list(self.model_agreement),
            "greatest_uncertainty": list(self.greatest_uncertainty),
            "cross_horizon_changes": list(self.cross_horizon_changes),
            "position_summaries": list(self.position_summaries),
            "narrative": self.narrative,
            "disclaimer": self.disclaimer,
        }


Pair = tuple[TrimAssessment, AttributionReport]


def _focus_pair(pairs: list[Pair], horizon: str) -> Pair:
    for assessment, attribution in pairs:
        if assessment.horizon == horizon:
            return assessment, attribution
    raise ConfigurationError(f"no assessment for horizon {horizon!r}")


def _primary_driver(assessment: TrimAssessment) -> str | None:
    return assessment.primary_trim_drivers[0] if assessment.primary_trim_drivers else None


def _primary_hold(assessment: TrimAssessment) -> str | None:
    return assessment.primary_hold_strengths[0] if assessment.primary_hold_strengths else None


def _largest_limitation(assessment: TrimAssessment) -> str:
    return next(
        (note for note in assessment.limitations if not note.startswith("labels summarize")),
        "none",
    )


def _segments(names: list[str | None]) -> list[tuple[str, str, str | None]]:
    """Compress per-horizon values into (first_horizon, last_horizon, value)
    runs, preserving order."""
    runs: list[tuple[str, str, str | None]] = []
    for horizon, name in zip(HORIZONS, names, strict=True):
        if runs and runs[-1][2] == name:
            runs[-1] = (runs[-1][0], horizon, name)
        else:
            runs.append((horizon, horizon, name))
    return runs


def _interpretation(pairs: list[Pair]) -> tuple[str, ...]:
    rows = [a for a, _ in pairs]
    sentences: list[str] = []
    first, last = rows[0], rows[-1]
    sentences.append(
        f"The {HORIZON_WORDS[first.horizon]} trim score is {first.trim_score:.1f} "
        f"({first.recommendation_label}) and the {HORIZON_WORDS[last.horizon]} score is "
        f"{last.trim_score:.1f} ({last.recommendation_label}), a spread of "
        f"{abs(last.trim_score - first.trim_score):.1f} points."
    )
    peak = max(rows, key=lambda a: (a.confidence, a.horizon))
    trough = min(rows, key=lambda a: (a.confidence, a.horizon))
    sentences.append(
        f"Confidence peaks at {peak.horizon} ({peak.confidence:.2f}) and is lowest at "
        f"{trough.horizon} ({trough.confidence:.2f})."
    )
    dominant = [
        next((item.name for item in attribution.contribution_ranking if item.kind == "model"), None)
        for _, attribution in pairs
    ]
    described = [
        f"{start}–{end} {name}" if start != end else f"{start} {name}"
        for start, end, name in _segments(dominant)
        if name is not None
    ]
    if described:
        sentences.append("Largest evidence contributor by horizon: " + "; ".join(described) + ".")
    adjustments = {a.portfolio_adjustment for a in rows}
    if adjustments != {0.0}:
        for a in rows:
            if a.portfolio_adjustment:
                sentences.append(
                    f"The portfolio overlay moves {a.horizon} from "
                    f"{a.evidence_trim_score:.1f} (evidence only) to {a.trim_score:.1f} "
                    f"({a.portfolio_adjustment:+.1f} points)."
                )
    sentences.extend(rows[0].diagnostics.cross_horizon_notes)
    return tuple(sentences)


def _strength_risk_entries(attribution: AttributionReport) -> tuple[list[dict], list[dict]]:
    strengths: list[dict] = []
    risks: list[dict] = []
    for c in attribution.evidence_contributions:
        entry = {
            "name": c.model_name,
            "kind": "model",
            "contribution": c.contribution,
            "expected_excess_return": c.expected_excess_return,
            "confidence": c.confidence,
        }
        if c.contribution < 0:
            strengths.append(entry)
        elif c.contribution > 0:
            risks.append(entry)
    concentration = attribution.portfolio_contributions.concentration_adjustment
    diversification = attribution.portfolio_contributions.diversification_adjustment
    if concentration > 0:
        risks.append(
            {"name": "portfolio concentration", "kind": "portfolio", "contribution": concentration}
        )
    if diversification < 0:
        strengths.append(
            {
                "name": "portfolio diversification",
                "kind": "portfolio",
                "contribution": diversification,
            }
        )
    strengths.sort(key=lambda e: (e["contribution"], e["name"]))
    risks.sort(key=lambda e: (-e["contribution"], e["name"]))
    return strengths, risks


def _symbol_narrative(assessment: TrimAssessment, strengths: list[dict], risks: list[dict]) -> str:
    word = HORIZON_WORDS[assessment.horizon]
    sentences = [
        f"{assessment.symbol}'s {word} trim score is {assessment.trim_score:.1f} "
        f"({assessment.recommendation_label}, confidence {assessment.confidence:.2f})."
    ]
    if assessment.portfolio_adjustment:
        direction = "adds" if assessment.portfolio_adjustment > 0 else "subtracts"
        sentences.append(
            f"Historical evidence alone supports {assessment.evidence_trim_score:.1f}; "
            f"the portfolio overlay {direction} "
            f"{abs(assessment.portfolio_adjustment):.1f} points."
        )
    elif assessment.portfolio_weight is None:
        sentences.append("The score is evidence-only; no portfolio context was supplied.")
    if strengths:
        top = strengths[:2]
        names = " and ".join(e["name"] for e in top)
        phrase = "are the strongest reasons" if len(top) > 1 else "is the strongest reason"
        sentences.append(f"{names} {phrase} to maintain exposure.")
    if risks:
        top = risks[:2]
        names = " and ".join(e["name"] for e in top)
        phrase = (
            "are the largest trim pressures" if len(top) > 1 else "is the largest trim pressure"
        )
        sentences.append(f"{names} {phrase}.")
    if any(e["kind"] == "model" for e in strengths) and any(e["kind"] == "model" for e in risks):
        sentences.append(
            f"Participating models disagree (contradiction "
            f"{assessment.contradictory_evidence:.2f})."
        )
    if assessment.neutral_models or assessment.omitted_models:
        missing: list[str] = []
        if assessment.neutral_models:
            missing.append(f"no active evidence from {', '.join(assessment.neutral_models)}")
        if assessment.omitted_models:
            missing.append(f"{', '.join(assessment.omitted_models)} could not be evaluated")
        sentences.append("; ".join(missing).capitalize() + ".")
    if assessment.diagnostics.label_downgraded:
        sentences.append(
            f"The label was downgraded from "
            f"{assessment.diagnostics.label_before_gate!r} because confidence "
            f"{assessment.confidence:.2f} is below the "
            f"{assessment.diagnostics.confidence_floor:.2f} floor."
        )
    return " ".join(sentences)


def build_symbol_report(
    pairs: list[Pair], options: ReportOptions | None = None
) -> SymbolDecisionReport:
    """Pure: the six (TrimAssessment, AttributionReport) pairs of one
    symbol in, one report out."""
    opts = options or ReportOptions()
    if not pairs:
        raise ConfigurationError("no assessments to report")
    symbols = {a.symbol for a, _ in pairs}
    if len(symbols) != 1:
        raise ConfigurationError(f"symbol report needs exactly one symbol, got {sorted(symbols)}")
    pairs = sorted(pairs, key=lambda pair: HORIZONS.index(pair[0].horizon))
    focus_assessment, focus_attribution = _focus_pair(pairs, opts.focus_horizon)

    rows = tuple(
        HorizonRow(
            horizon=a.horizon,
            trim_score=a.trim_score,
            evidence_trim_score=a.evidence_trim_score,
            portfolio_adjustment=a.portfolio_adjustment,
            confidence=a.confidence,
            expected_return=a.expected_return,
            expected_excess_return=a.expected_excess_return,
            recommendation_label=a.recommendation_label,
            data_quality_label=a.data_quality_label,
            primary_driver=_primary_driver(a),
            label_downgraded=a.diagnostics.label_downgraded,
        )
        for a, _ in pairs
    )
    strengths, risks = _strength_risk_entries(focus_attribution)
    uncertainty = {
        "contradictory_evidence": focus_assessment.contradictory_evidence,
        "largest_model_uncertainty": focus_attribution.largest_uncertainty,
        "neutral_models": list(focus_assessment.neutral_models),
        "omitted_models": list(focus_assessment.omitted_models),
        "effective_sample_size": focus_assessment.effective_sample_size,
        "data_quality_label": focus_assessment.data_quality_label,
        "warnings": list(focus_assessment.limitations),
    }
    return SymbolDecisionReport(
        symbol=focus_assessment.symbol,
        as_of=focus_assessment.as_of,
        focus_horizon=opts.focus_horizon,
        portfolio_name=focus_assessment.portfolio_name,
        portfolio_weight=focus_assessment.portfolio_weight,
        risk_contribution=focus_assessment.risk_contribution,
        diversification_contribution=focus_assessment.diversification_contribution,
        concentration_flags=focus_assessment.concentration_flags,
        horizon_rows=rows,
        cross_horizon_interpretation=_interpretation(pairs),
        trim_score=focus_assessment.trim_score,
        confidence=focus_assessment.confidence,
        recommendation_label=focus_assessment.recommendation_label,
        strengths=tuple(strengths[: opts.top]),
        strengths_reason=focus_assessment.strongest_opposing_reason,
        risks=tuple(risks[: opts.top]),
        risks_reason=focus_assessment.strongest_supporting_reason,
        uncertainty=uncertainty,
        neutral_baseline=focus_attribution.neutral_baseline,
        attribution_rows=focus_attribution.contribution_ranking,
        narrative=_symbol_narrative(focus_assessment, strengths, risks),
    )


def _quality_rank(assessment: TrimAssessment) -> int:
    return {"no_evidence": 0, "sparse": 1}.get(assessment.data_quality_label, 2)


def _portfolio_narrative(
    portfolio_name: str, focus: list[Pair], overview: dict, horizon: str
) -> str:
    sentences = [
        f"Across {overview['n_positions']} positions in {portfolio_name!r} at the "
        f"{HORIZON_WORDS[horizon]} horizon: {overview['trim_candidates']} trim "
        f"candidate(s), {overview['maintain_candidates']} maintain candidate(s), "
        f"{overview['mixed_evidence']} with mixed evidence, and "
        f"{overview['insufficient_evidence']} with insufficient evidence."
    ]
    if overview["largest_position"]:
        largest = overview["largest_position"]
        sentences.append(
            f"The largest position is {largest['symbol']} "
            f"({largest['portfolio_weight']:.1%} weight)."
        )
    if overview["largest_risk_contributor"]:
        riskiest = overview["largest_risk_contributor"]
        sentences.append(
            f"The largest risk contributor is {riskiest['symbol']} "
            f"({riskiest['risk_contribution']:.0%} of portfolio variance)."
        )
    ranked = sorted(focus, key=lambda pair: (-pair[0].trim_score, pair[0].symbol))
    top, bottom = ranked[0][0], ranked[-1][0]
    sentences.append(
        f"The strongest trim evidence is {top.symbol} ({top.trim_score:.1f}, "
        f"{top.recommendation_label}); the strongest maintain evidence is "
        f"{bottom.symbol} ({bottom.trim_score:.1f}, {bottom.recommendation_label})."
    )
    return " ".join(sentences)


def build_portfolio_report(
    by_symbol: dict[str, list[Pair]],
    portfolio_name: str,
    options: ReportOptions | None = None,
    generated_at: datetime | None = None,
) -> PortfolioDecisionReport:
    """Pure given `generated_at`: every holding's pairs in, one report out."""
    opts = options or ReportOptions()
    if not by_symbol:
        raise ConfigurationError(f"portfolio {portfolio_name!r} has no assessable holdings")
    focus: list[Pair] = [
        _focus_pair(pairs, opts.focus_horizon) for _, pairs in sorted(by_symbol.items())
    ]
    as_of = max(a.as_of for a, _ in focus)

    with_weight = [a for a, _ in focus if a.portfolio_weight is not None]
    with_risk = [a for a, _ in focus if a.risk_contribution is not None]
    largest_position = max(with_weight, key=lambda a: (a.portfolio_weight, a.symbol), default=None)
    largest_risk = max(with_risk, key=lambda a: (a.risk_contribution, a.symbol), default=None)
    concentrations = [
        (r.portfolio_contributions.concentration_adjustment, a.symbol)
        for a, r in focus
        if r.portfolio_contributions.concentration_adjustment > 0
    ]
    diversifications = [
        (r.portfolio_contributions.diversification_adjustment, a.symbol)
        for a, r in focus
        if r.portfolio_contributions.diversification_adjustment < 0
    ]
    labels = [a.recommendation_label for a, _ in focus]
    overview = {
        "n_positions": len(focus),
        "total_market_value": None,
        "total_market_value_note": MARKET_VALUE_NOTE,
        "largest_position": (
            {
                "symbol": largest_position.symbol,
                "portfolio_weight": largest_position.portfolio_weight,
            }
            if largest_position
            else None
        ),
        "largest_risk_contributor": (
            {"symbol": largest_risk.symbol, "risk_contribution": largest_risk.risk_contribution}
            if largest_risk
            else None
        ),
        "largest_concentration_adjustment": (
            {"symbol": max(concentrations)[1], "value": max(concentrations)[0]}
            if concentrations
            else None
        ),
        "largest_diversification_benefit": (
            {"symbol": min(diversifications)[1], "value": min(diversifications)[0]}
            if diversifications
            else None
        ),
        "trim_candidates": sum(label in TRIM_LABELS for label in labels),
        "maintain_candidates": sum(label == MAINTAIN_LABEL for label in labels),
        "mixed_evidence": sum(label == MIXED_LABEL for label in labels),
        "insufficient_evidence": sum(a.data_quality_label == "no_evidence" for a, _ in focus),
    }

    def entry(assessment: TrimAssessment) -> dict:
        return {
            "symbol": assessment.symbol,
            "trim_score": assessment.trim_score,
            "confidence": assessment.confidence,
            "recommendation_label": assessment.recommendation_label,
            "primary_trim_driver": _primary_driver(assessment),
            "label_downgraded": assessment.diagnostics.label_downgraded,
        }

    highest_trim = tuple(
        entry(a) for a, _ in sorted(focus, key=lambda p: (-p[0].trim_score, p[0].symbol))
    )[: opts.top]
    strongest_maintain = tuple(
        entry(a) | {"primary_hold_strength": _primary_hold(a)}
        for a, _ in sorted(focus, key=lambda p: (p[0].trim_score, p[0].symbol))
        if a.confidence >= opts.min_confidence
    )[: opts.top]
    portfolio_pressure = tuple(
        {
            "symbol": a.symbol,
            "portfolio_adjustment": a.portfolio_adjustment,
            "portfolio_weight": a.portfolio_weight,
            "risk_contribution": a.risk_contribution,
            "concentration_flags": list(a.concentration_flags),
        }
        for a, _ in sorted(focus, key=lambda p: (-p[0].portfolio_adjustment, p[0].symbol))
        if a.portfolio_adjustment > 0
    )[: opts.top]
    diversification = tuple(
        {
            "symbol": a.symbol,
            "portfolio_adjustment": a.portfolio_adjustment,
            "portfolio_weight": a.portfolio_weight,
            "risk_contribution": a.risk_contribution,
        }
        for a, _ in sorted(focus, key=lambda p: (p[0].portfolio_adjustment, p[0].symbol))
        if a.portfolio_adjustment < 0
    )[: opts.top]
    model_agreement = tuple(
        {
            "symbol": a.symbol,
            "contradictory_evidence": a.contradictory_evidence,
            "confidence": a.confidence,
            "participating_models": len(a.participating_models),
        }
        for a, _ in sorted(
            focus, key=lambda p: (p[0].contradictory_evidence, -p[0].confidence, p[0].symbol)
        )
        if a.data_quality_label
        != "no_evidence"  # zero contradiction from zero models is not agreement
    )[: opts.top]
    greatest_uncertainty = tuple(
        {
            "symbol": a.symbol,
            "data_quality_label": a.data_quality_label,
            "contradictory_evidence": a.contradictory_evidence,
            "confidence": a.confidence,
            "neutral_models": list(a.neutral_models),
            "omitted_models": list(a.omitted_models),
        }
        for a, _ in sorted(
            focus,
            key=lambda p: (
                _quality_rank(p[0]),
                -p[0].contradictory_evidence,
                p[0].confidence,
                p[0].symbol,
            ),
        )
    )[: opts.top]

    def spread(pairs: list[Pair]) -> dict:
        assessments = [a for a, _ in pairs]
        low = min(assessments, key=lambda a: (a.trim_score, a.horizon))
        high = max(assessments, key=lambda a: (a.trim_score, a.horizon))
        return {
            "symbol": assessments[0].symbol,
            "spread": high.trim_score - low.trim_score,
            "min_horizon": low.horizon,
            "min_score": low.trim_score,
            "min_label": low.recommendation_label,
            "max_horizon": high.horizon,
            "max_score": high.trim_score,
            "max_label": high.recommendation_label,
            "cross_horizon_notes": list(assessments[0].diagnostics.cross_horizon_notes),
        }

    cross_horizon = tuple(
        sorted(
            (spread(pairs) for pairs in by_symbol.values()),
            key=lambda s: (-s["spread"], s["symbol"]),
        )
    )[: opts.top]

    position_summaries = tuple(
        {
            "symbol": a.symbol,
            "trim_scores": {
                h: next(x.trim_score for x, _ in by_symbol[a.symbol] if x.horizon == h)
                for h in SUMMARY_HORIZONS
            },
            "confidence": a.confidence,
            "recommendation_label": a.recommendation_label,
            "primary_trim_driver": _primary_driver(a),
            "primary_hold_strength": _primary_hold(a),
            "portfolio_adjustment": a.portfolio_adjustment,
            "largest_limitation": _largest_limitation(a),
        }
        for a, _ in focus
    )

    return PortfolioDecisionReport(
        portfolio_name=portfolio_name,
        as_of=as_of,
        generated_at=generated_at or datetime.now(UTC),
        focus_horizon=opts.focus_horizon,
        overview=overview,
        highest_trim=highest_trim,
        strongest_maintain=strongest_maintain,
        portfolio_pressure=portfolio_pressure,
        diversification=diversification,
        model_agreement=model_agreement,
        greatest_uncertainty=greatest_uncertainty,
        cross_horizon_changes=cross_horizon,
        position_summaries=position_summaries,
        narrative=_portfolio_narrative(portfolio_name, focus, overview, opts.focus_horizon),
    )


# -- rendering (deterministic; no analysis) ----------------------------------------


def _fmt(value, spec: str = "+.2%") -> str:
    return format(value, spec) if value is not None else "—"


def _md_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def render_symbol_text(report: SymbolDecisionReport) -> str:
    lines = [f"{report.symbol} — decision report (as of {report.as_of})"]
    if report.portfolio_name:
        lines.append(
            f"portfolio {report.portfolio_name}: weight {_fmt(report.portfolio_weight, '.1%')}, "
            f"risk {_fmt(report.risk_contribution, '.0%')}, diversification "
            f"{_fmt(report.diversification_contribution, '+.2%')}"
        )
    lines += ["", report.narrative, "", "HORIZONS:"]
    lines.append(
        f"{'HZN':>4} {'TRIM':>6} {'EVID':>6} {'ADJ':>6} {'CONF':>5} {'EXP':>8} "
        f"{'EXCESS':>8} {'QUALITY':<11} {'LABEL':<22} {'PRIMARY DRIVER'}"
    )
    for row in report.horizon_rows:
        mark = "*" if row.label_downgraded else ""
        lines.append(
            f"{row.horizon:>4} {row.trim_score:>6.1f} {row.evidence_trim_score:>6.1f} "
            f"{row.portfolio_adjustment:>+6.1f} {row.confidence:>5.2f} "
            f"{_fmt(row.expected_return):>8} {_fmt(row.expected_excess_return):>8} "
            f"{row.data_quality_label:<11} {row.recommendation_label + mark:<22} "
            f"{row.primary_driver or '—'}"
        )
    lines += ["", "CROSS-HORIZON INTERPRETATION:"]
    lines += [f"  - {sentence}" for sentence in report.cross_horizon_interpretation]

    lines += ["", f"STRENGTHS ({report.focus_horizon} — evidence against trimming):"]
    for e in report.strengths or ():
        lines.append(f"  {e['name']:<28} {e['contribution']:>+7.2f} points")
    if not report.strengths:
        lines.append("  none")
    if report.strengths_reason:
        r = report.strengths_reason
        lines.append(f"  strongest: [{r['model']}] {r['description']}")
    lines += ["", f"RISKS ({report.focus_horizon} — evidence for trimming):"]
    for e in report.risks or ():
        lines.append(f"  {e['name']:<28} {e['contribution']:>+7.2f} points")
    if not report.risks:
        lines.append("  none")
    if report.risks_reason:
        r = report.risks_reason
        lines.append(f"  strongest: [{r['model']}] {r['description']}")
    for flag in report.concentration_flags:
        lines.append(f"  - {flag}")

    u = report.uncertainty
    lines += ["", "UNCERTAINTY:"]
    lines.append(
        f"  contradiction {u['contradictory_evidence']:.2f}; effective sample "
        f"{u['effective_sample_size']:.1f}; quality {u['data_quality_label']}"
    )
    if u["largest_model_uncertainty"]:
        lines.append(
            f"  least precise: {u['largest_model_uncertainty']['model']} "
            f"(se {u['largest_model_uncertainty']['standard_error'] * 100:.2f}pp)"
        )
    lines.append(f"  neutral: {', '.join(u['neutral_models']) or 'none'}")
    lines.append(f"  omitted: {', '.join(u['omitted_models']) or 'none'}")
    lines += [f"  - {warning}" for warning in u["warnings"]]

    lines += ["", f"ATTRIBUTION ({report.focus_horizon} — sums exactly to the trim score):"]
    lines.append(f"  {'neutral baseline':<28} {'':>8} {report.neutral_baseline:>8.2f}")
    for item in report.attribution_rows:
        lines.append(f"  {item.name:<28} {item.contribution:>+8.2f} {item.cumulative:>8.2f}")
    lines.append(f"  {'trim score':<28} {'':>8} {report.trim_score:>8.2f}")
    lines += ["", f"({report.disclaimer})"]
    return "\n".join(lines)


def render_symbol_markdown(report: SymbolDecisionReport) -> str:
    lines = [
        f"# {report.symbol} — Decision Report",
        "",
        f"*As of {report.as_of}; focus horizon {report.focus_horizon}.*",
        "",
        report.narrative,
        "",
        "## Horizons",
        "",
        _md_row(
            [
                "Horizon",
                "Trim",
                "Evidence",
                "Adj",
                "Conf",
                "Expected",
                "Excess",
                "Quality",
                "Label",
                "Driver",
            ]
        ),
        _md_row(["---"] * 10),
    ]
    for row in report.horizon_rows:
        mark = r"\*" if row.label_downgraded else ""
        lines.append(
            _md_row(
                [
                    row.horizon,
                    f"{row.trim_score:.1f}",
                    f"{row.evidence_trim_score:.1f}",
                    f"{row.portfolio_adjustment:+.1f}",
                    f"{row.confidence:.2f}",
                    _fmt(row.expected_return),
                    _fmt(row.expected_excess_return),
                    row.data_quality_label,
                    row.recommendation_label + mark,
                    row.primary_driver or "—",
                ]
            )
        )
    lines += ["", "## Cross-Horizon Interpretation", ""]
    lines += [f"- {sentence}" for sentence in report.cross_horizon_interpretation]
    lines += ["", f"## Strengths ({report.focus_horizon})", ""]
    lines += [f"- **{e['name']}** {e['contribution']:+.2f} points" for e in report.strengths] or [
        "- none"
    ]
    if report.strengths_reason:
        r = report.strengths_reason
        lines.append(f"- strongest: **[{r['model']}]** {r['description']}")
    lines += ["", f"## Risks ({report.focus_horizon})", ""]
    lines += [f"- **{e['name']}** {e['contribution']:+.2f} points" for e in report.risks] or [
        "- none"
    ]
    if report.risks_reason:
        r = report.risks_reason
        lines.append(f"- strongest: **[{r['model']}]** {r['description']}")
    lines += [f"- {flag}" for flag in report.concentration_flags]
    u = report.uncertainty
    lines += ["", "## Uncertainty", ""]
    lines.append(
        f"- contradiction {u['contradictory_evidence']:.2f}; effective sample "
        f"{u['effective_sample_size']:.1f}; quality {u['data_quality_label']}"
    )
    lines.append(f"- neutral: {', '.join(u['neutral_models']) or 'none'}")
    lines.append(f"- omitted: {', '.join(u['omitted_models']) or 'none'}")
    lines += [f"- {warning}" for warning in u["warnings"]]
    lines += [
        "",
        f"## Attribution ({report.focus_horizon})",
        "",
        _md_row(["Component", "Contribution", "Cumulative"]),
        _md_row(["---"] * 3),
        _md_row(["neutral baseline", "", f"{report.neutral_baseline:.2f}"]),
    ]
    for item in report.attribution_rows:
        lines.append(_md_row([item.name, f"{item.contribution:+.2f}", f"{item.cumulative:.2f}"]))
    lines.append(_md_row(["**trim score**", "", f"**{report.trim_score:.2f}**"]))
    lines += ["", f"*{report.disclaimer}*"]
    return "\n".join(lines)


def _ranked_lines(
    title: str, entries: tuple[dict, ...], fields: list[tuple[str, str]]
) -> list[str]:
    lines = ["", title]
    if not entries:
        return lines + ["  none"]
    for e in entries:
        parts = []
        for key, spec in fields:
            value = e.get(key)
            parts.append(
                f"{key} {format(value, spec)}" if value is not None and spec else f"{value}"
            )
        lines.append("  " + "  ".join(parts))
    return lines


def render_portfolio_text(report: PortfolioDecisionReport) -> str:
    o = report.overview
    lines = [
        f"PORTFOLIO DECISION REPORT — {report.portfolio_name} "
        f"(as of {report.as_of}, focus {report.focus_horizon}, "
        f"generated {report.generated_at.isoformat()})",
        "",
        report.narrative,
        "",
        "OVERVIEW:",
        f"  positions {o['n_positions']}; trim candidates {o['trim_candidates']}; "
        f"maintain {o['maintain_candidates']}; mixed {o['mixed_evidence']}; "
        f"insufficient {o['insufficient_evidence']}",
        f"  total market value: unavailable ({o['total_market_value_note']})",
    ]
    if o["largest_position"]:
        lines.append(
            f"  largest position: {o['largest_position']['symbol']} "
            f"({o['largest_position']['portfolio_weight']:.1%})"
        )
    if o["largest_risk_contributor"]:
        lines.append(
            f"  largest risk contributor: {o['largest_risk_contributor']['symbol']} "
            f"({o['largest_risk_contributor']['risk_contribution']:.0%})"
        )
    if o["largest_concentration_adjustment"]:
        c = o["largest_concentration_adjustment"]
        lines.append(f"  largest concentration adjustment: {c['symbol']} (+{c['value']:.1f} pts)")
    if o["largest_diversification_benefit"]:
        d = o["largest_diversification_benefit"]
        lines.append(f"  largest diversification benefit: {d['symbol']} ({d['value']:.1f} pts)")

    lines += ["", f"HIGHEST TRIM EVIDENCE ({report.focus_horizon}):"]
    for e in report.highest_trim:
        mark = "*" if e["label_downgraded"] else ""
        lines.append(
            f"  {e['symbol']:<6} {e['trim_score']:>6.1f}  conf {e['confidence']:.2f}  "
            f"{e['recommendation_label'] + mark:<22} driver {e['primary_trim_driver'] or '—'}"
        )
    lines += ["", f"STRONGEST MAINTAIN EVIDENCE (confidence-gated, {report.focus_horizon}):"]
    for e in report.strongest_maintain:
        lines.append(
            f"  {e['symbol']:<6} {e['trim_score']:>6.1f}  conf {e['confidence']:.2f}  "
            f"{e['recommendation_label']:<22} strength {e['primary_hold_strength'] or '—'}"
        )
    if not report.strongest_maintain:
        lines.append("  none above the confidence gate")
    lines += ["", "GREATEST PORTFOLIO PRESSURE:"]
    for e in report.portfolio_pressure:
        lines.append(
            f"  {e['symbol']:<6} {e['portfolio_adjustment']:>+6.1f} pts  weight "
            f"{_fmt(e['portfolio_weight'], '.1%')}  risk {_fmt(e['risk_contribution'], '.0%')}"
        )
    if not report.portfolio_pressure:
        lines.append("  none")
    lines += ["", "GREATEST DIVERSIFICATION BENEFIT:"]
    for e in report.diversification:
        lines.append(
            f"  {e['symbol']:<6} {e['portfolio_adjustment']:>+6.1f} pts  weight "
            f"{_fmt(e['portfolio_weight'], '.1%')}  risk {_fmt(e['risk_contribution'], '.0%')}"
        )
    if not report.diversification:
        lines.append("  none")
    lines += ["", "GREATEST MODEL AGREEMENT:"]
    for e in report.model_agreement:
        lines.append(
            f"  {e['symbol']:<6} contradiction {e['contradictory_evidence']:.2f}  "
            f"conf {e['confidence']:.2f}  models {e['participating_models']}"
        )
    if not report.model_agreement:
        lines.append("  none with evidence")
    lines += ["", "GREATEST UNCERTAINTY:"]
    for e in report.greatest_uncertainty:
        lines.append(
            f"  {e['symbol']:<6} {e['data_quality_label']:<11} contradiction "
            f"{e['contradictory_evidence']:.2f}  conf {e['confidence']:.2f}  "
            f"neutral {len(e['neutral_models'])}  omitted {len(e['omitted_models'])}"
        )
    lines += ["", "LARGEST CROSS-HORIZON CHANGES:"]
    for e in report.cross_horizon_changes:
        lines.append(
            f"  {e['symbol']:<6} spread {e['spread']:>5.1f}: {e['min_horizon']} "
            f"{e['min_score']:.1f} ({e['min_label']}) → {e['max_horizon']} "
            f"{e['max_score']:.1f} ({e['max_label']})"
        )
        lines += [f"    - {note}" for note in e["cross_horizon_notes"]]

    lines += ["", "POSITION SUMMARIES:"]
    header = "".join(f"{h:>7}" for h in SUMMARY_HORIZONS)
    lines.append(f"  {'SYM':<6}{header}  {'CONF':>5}  {'LABEL':<22} {'LIMITATION'}")
    for p in report.position_summaries:
        scores = "".join(f"{p['trim_scores'][h]:>7.1f}" for h in SUMMARY_HORIZONS)
        lines.append(
            f"  {p['symbol']:<6}{scores}  {p['confidence']:>5.2f}  "
            f"{p['recommendation_label']:<22} {p['largest_limitation']}"
        )
    lines += ["", f"({report.disclaimer})"]
    return "\n".join(lines)


def render_portfolio_markdown(report: PortfolioDecisionReport) -> str:
    o = report.overview
    lines = [
        f"# Portfolio Decision Report — {report.portfolio_name}",
        "",
        f"*As of {report.as_of}; focus horizon {report.focus_horizon}; "
        f"generated {report.generated_at.isoformat()}.*",
        "",
        report.narrative,
        "",
        "## Overview",
        "",
        f"- positions: {o['n_positions']}",
        f"- total market value: unavailable ({o['total_market_value_note']})",
        f"- trim candidates: {o['trim_candidates']}; maintain: {o['maintain_candidates']}; "
        f"mixed: {o['mixed_evidence']}; insufficient: {o['insufficient_evidence']}",
    ]
    if o["largest_position"]:
        lines.append(
            f"- largest position: {o['largest_position']['symbol']} "
            f"({o['largest_position']['portfolio_weight']:.1%})"
        )
    if o["largest_risk_contributor"]:
        lines.append(
            f"- largest risk contributor: {o['largest_risk_contributor']['symbol']} "
            f"({o['largest_risk_contributor']['risk_contribution']:.0%})"
        )
    if o["largest_concentration_adjustment"]:
        c = o["largest_concentration_adjustment"]
        lines.append(f"- largest concentration adjustment: {c['symbol']} (+{c['value']:.1f} pts)")
    if o["largest_diversification_benefit"]:
        d = o["largest_diversification_benefit"]
        lines.append(f"- largest diversification benefit: {d['symbol']} ({d['value']:.1f} pts)")

    def section(title: str, rows: list[list[str]], headers: list[str]) -> None:
        lines.extend(["", f"## {title}", ""])
        if not rows:
            lines.append("*none*")
            return
        lines.append(_md_row(headers))
        lines.append(_md_row(["---"] * len(headers)))
        lines.extend(_md_row(row) for row in rows)

    section(
        f"Highest Trim Evidence ({report.focus_horizon})",
        [
            [
                e["symbol"],
                f"{e['trim_score']:.1f}",
                f"{e['confidence']:.2f}",
                e["recommendation_label"] + (r"\*" if e["label_downgraded"] else ""),
                e["primary_trim_driver"] or "—",
            ]
            for e in report.highest_trim
        ],
        ["Symbol", "Trim", "Conf", "Label", "Primary driver"],
    )
    section(
        "Strongest Maintain Evidence (confidence-gated)",
        [
            [
                e["symbol"],
                f"{e['trim_score']:.1f}",
                f"{e['confidence']:.2f}",
                e["recommendation_label"],
                e["primary_hold_strength"] or "—",
            ]
            for e in report.strongest_maintain
        ],
        ["Symbol", "Trim", "Conf", "Label", "Primary hold strength"],
    )
    section(
        "Greatest Portfolio Pressure",
        [
            [
                e["symbol"],
                f"{e['portfolio_adjustment']:+.1f}",
                _fmt(e["portfolio_weight"], ".1%"),
                _fmt(e["risk_contribution"], ".0%"),
            ]
            for e in report.portfolio_pressure
        ],
        ["Symbol", "Adjustment", "Weight", "Risk"],
    )
    section(
        "Greatest Diversification Benefit",
        [
            [
                e["symbol"],
                f"{e['portfolio_adjustment']:+.1f}",
                _fmt(e["portfolio_weight"], ".1%"),
                _fmt(e["risk_contribution"], ".0%"),
            ]
            for e in report.diversification
        ],
        ["Symbol", "Adjustment", "Weight", "Risk"],
    )
    section(
        "Greatest Model Agreement",
        [
            [
                e["symbol"],
                f"{e['contradictory_evidence']:.2f}",
                f"{e['confidence']:.2f}",
                str(e["participating_models"]),
            ]
            for e in report.model_agreement
        ],
        ["Symbol", "Contradiction", "Conf", "Models"],
    )
    section(
        "Greatest Uncertainty",
        [
            [
                e["symbol"],
                e["data_quality_label"],
                f"{e['contradictory_evidence']:.2f}",
                f"{e['confidence']:.2f}",
                ", ".join(e["neutral_models"]) or "—",
                ", ".join(e["omitted_models"]) or "—",
            ]
            for e in report.greatest_uncertainty
        ],
        ["Symbol", "Quality", "Contradiction", "Conf", "Neutral", "Omitted"],
    )
    section(
        "Largest Cross-Horizon Changes",
        [
            [
                e["symbol"],
                f"{e['spread']:.1f}",
                f"{e['min_horizon']} {e['min_score']:.1f} ({e['min_label']})",
                f"{e['max_horizon']} {e['max_score']:.1f} ({e['max_label']})",
            ]
            for e in report.cross_horizon_changes
        ],
        ["Symbol", "Spread", "Low", "High"],
    )
    section(
        "Position Summaries",
        [
            [
                p["symbol"],
                *(f"{p['trim_scores'][h]:.1f}" for h in SUMMARY_HORIZONS),
                f"{p['confidence']:.2f}",
                p["recommendation_label"],
                p["primary_trim_driver"] or "—",
                p["primary_hold_strength"] or "—",
                f"{p['portfolio_adjustment']:+.1f}",
                p["largest_limitation"],
            ]
            for p in report.position_summaries
        ],
        [
            "Symbol",
            *(h.upper() for h in SUMMARY_HORIZONS),
            "Conf",
            "Label",
            "Trim driver",
            "Hold strength",
            "Adj",
            "Limitation",
        ],
    )
    lines += ["", f"*{report.disclaimer}*"]
    return "\n".join(lines)


class ReportGenerator:
    """Obtains (TrimAssessment, AttributionReport) pairs through the
    attribution engine and builds reports. Touches nothing below those
    two objects."""

    def __init__(self, session: Session, config: TrimConfig | None = None) -> None:
        self._attribution = AttributionEngine(session, config)

    def symbol_report(
        self,
        symbol: str,
        portfolio: str | None = None,
        as_of: date | None = None,
        options: ReportOptions | None = None,
    ) -> SymbolDecisionReport:
        pairs = self._attribution.assessed(symbols=[symbol], portfolio=portfolio, as_of=as_of)
        return build_symbol_report(pairs[symbol.strip().upper()], options)

    def portfolio_report(
        self,
        portfolio: str,
        as_of: date | None = None,
        options: ReportOptions | None = None,
        generated_at: datetime | None = None,
    ) -> PortfolioDecisionReport:
        by_symbol = self._attribution.assessed(portfolio=portfolio, as_of=as_of)
        return build_portfolio_report(by_symbol, portfolio, options, generated_at)
