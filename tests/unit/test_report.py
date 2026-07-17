"""Portfolio Decision Report Generator: schemas, rankings, narratives, and
renderers over hand-built assessments with known values. No database."""

import ast
import inspect
import json
from datetime import UTC, datetime

import pytest

from mip.core.exceptions import ConfigurationError
from mip.engine.attribution import attribute
from mip.engine.report import (
    HORIZONS,
    ReportOptions,
    build_portfolio_report,
    build_symbol_report,
    render_portfolio_markdown,
    render_portfolio_text,
    render_symbol_markdown,
    render_symbol_text,
)
from mip.engine.trim import assess_symbol
from tests.unit.test_attribution import MIXED, decision

GENERATED_AT = datetime(2026, 7, 14, 12, 0, 0, tzinfo=UTC)
BULLISH = [("sector_rotation", 0.04, 1.0, 0.01)]

# AAA: varied per-horizon evidence scores; conf 0.8; weight 0.30 / risk 0.10
# -> W = 10, R = -5, A = +5 at every horizon.
AAA_SCORES = {"1w": 80.0, "2w": 60.0, "1m": 10.0, "3m": 30.0, "6m": 50.0, "1y": 20.0}
# E = 50 + 0.8*(50-s); T = E + 5
AAA_TRIMS = {"1w": 31.0, "2w": 47.0, "1m": 87.0, "3m": 71.0, "6m": 55.0, "1y": 79.0}


def make_symbol(
    symbol: str,
    scores: dict[str, float] | None,
    confidence: float = 0.8,
    weight: float | None = None,
    risk: float | None = None,
    contributions=MIXED,
    contradiction: float = 0.1,
):
    evidences = [
        decision(
            score=scores[h] if scores else 50.0,
            confidence=confidence,
            contributions=contributions if scores else [],
            horizon=h,
            contradiction=contradiction,
            weight=weight,
            risk=risk,
            symbol=symbol,
        )
        for h in HORIZONS
    ]
    assessments = assess_symbol(evidences)
    by_horizon = {e.horizon: e for e in evidences}
    return [(a, attribute(a, by_horizon[a.horizon])) for a in assessments]


@pytest.fixture()
def aaa_pairs():
    return make_symbol("AAA", AAA_SCORES, weight=0.30, risk=0.10)


@pytest.fixture()
def portfolio_pairs(aaa_pairs):
    flat = {h: 90.0 for h in HORIZONS}
    return {
        "AAA": aaa_pairs,
        "BBB": make_symbol(
            "BBB", flat, weight=0.10, risk=0.02, contributions=BULLISH, contradiction=0.0
        ),
        "CCC": make_symbol("CCC", None, weight=0.05, risk=0.05),
    }


def build(portfolio_pairs, **kwargs):
    options = ReportOptions(**kwargs) if kwargs else None
    return build_portfolio_report(portfolio_pairs, "main", options, generated_at=GENERATED_AT)


# -- symbol report -----------------------------------------------------------------


def test_symbol_report_contains_all_six_horizons_verbatim(aaa_pairs) -> None:
    report = build_symbol_report(aaa_pairs)
    assert [row.horizon for row in report.horizon_rows] == list(HORIZONS)
    for row, (assessment, _) in zip(report.horizon_rows, aaa_pairs, strict=True):
        assert row.trim_score == pytest.approx(AAA_TRIMS[row.horizon])
        assert row.trim_score == assessment.trim_score
        assert row.evidence_trim_score == assessment.evidence_trim_score
        assert row.portfolio_adjustment == assessment.portfolio_adjustment == 5.0
        assert row.confidence == assessment.confidence
        assert row.recommendation_label == assessment.recommendation_label
        assert row.data_quality_label == assessment.data_quality_label
    assert report.focus_horizon == "1m"
    assert report.trim_score == pytest.approx(87.0)
    assert report.recommendation_label == "Trim"


def test_attribution_rows_reproduce_the_trim_score(aaa_pairs) -> None:
    report = build_symbol_report(aaa_pairs)
    total = report.neutral_baseline + sum(item.contribution for item in report.attribution_rows)
    assert total == pytest.approx(report.trim_score)
    assert report.attribution_rows[-1].cumulative == pytest.approx(report.trim_score)


def test_cross_horizon_interpretation_sentences(aaa_pairs) -> None:
    report = build_symbol_report(aaa_pairs)
    text = " ".join(report.cross_horizon_interpretation)
    assert "The 1-week trim score is 31.0" in text
    assert "the 1-year score is 79.0" in text
    assert "a spread of 48.0 points" in text
    assert "Confidence peaks" in text
    assert "Largest evidence contributor by horizon: 1w–1y macro_regime." in text
    assert "from 82.0 (evidence only) to 87.0 (+5.0 points)" in text
    assert "trim score moves +40.0 points from 2w (47.0) to 1m (87.0)" in text


def test_strengths_and_risks_keep_conflicting_evidence_visible(aaa_pairs) -> None:
    report = build_symbol_report(aaa_pairs)
    # D = 32: macro +48 (risk), sector -16 (strength); overlay: conc +10, div -5
    assert [e["name"] for e in report.strengths] == ["sector_rotation", "portfolio diversification"]
    assert report.strengths[0]["contribution"] == pytest.approx(-16.0)
    assert report.strengths[1]["contribution"] == pytest.approx(-5.0)
    assert [e["name"] for e in report.risks] == ["macro_regime", "portfolio concentration"]
    assert report.risks[0]["contribution"] == pytest.approx(48.0)
    assert report.risks[1]["contribution"] == pytest.approx(10.0)
    assert report.strengths_reason["excess"] < 0 or report.strengths_reason["excess"] > 0
    assert report.risks_reason is not None


def test_narrative_is_traceable_to_fields(aaa_pairs) -> None:
    report = build_symbol_report(aaa_pairs)
    n = report.narrative
    assert "AAA's 1-month trim score is 87.0 (Trim, confidence 0.80)." in n
    assert "Historical evidence alone supports 82.0" in n
    assert "adds 5.0 points" in n
    assert "sector_rotation and portfolio diversification are the strongest reasons" in n
    assert "macro_regime and portfolio concentration are the largest trim pressures" in n
    assert "Participating models disagree (contradiction 0.10)." in n


def test_narrative_reports_downgrade_and_missing_evidence() -> None:
    evidences = [
        decision(
            score=2.0,
            confidence=0.35,
            contributions=[("macro_regime", -0.06, 1.0, 0.02)],
            horizon=h,
            weight=0.60,
            risk=0.90,
            neutral=("earnings_behavior",),
            omitted=("valuation",),
        )
        for h in HORIZONS
    ]
    assessments = assess_symbol(evidences)
    by_horizon = {e.horizon: e for e in evidences}
    pairs = [(a, attribute(a, by_horizon[a.horizon])) for a in assessments]
    report = build_symbol_report(pairs)
    # E = 50 + 0.35*48 = 66.8, +10 overlay = 76.8 -> Trim band, downgraded at 0.35
    assert report.trim_score == pytest.approx(76.8)
    assert report.recommendation_label == "Trim Consideration"
    assert "downgraded from 'Trim'" in report.narrative
    assert "No active evidence from earnings_behavior" in report.narrative
    assert "valuation could not be evaluated" in report.narrative


def test_uncertainty_block_distinguishes_neutral_from_omitted(aaa_pairs) -> None:
    evidences = [
        decision(
            score=30.0,
            confidence=0.5,
            contributions=MIXED,
            horizon=h,
            neutral=("earnings_behavior",),
            omitted=("valuation",),
        )
        for h in HORIZONS
    ]
    assessments = assess_symbol(evidences)
    by_horizon = {e.horizon: e for e in evidences}
    report = build_symbol_report([(a, attribute(a, by_horizon[a.horizon])) for a in assessments])
    assert report.uncertainty["neutral_models"] == ["earnings_behavior"]
    assert report.uncertainty["omitted_models"] == ["valuation"]
    assessment, _ = next(p for p in aaa_pairs if p[0].horizon == "1m")
    focus = build_symbol_report(aaa_pairs)
    assert focus.uncertainty["warnings"] == list(assessment.limitations)
    assert focus.uncertainty["largest_model_uncertainty"]["model"] == "macro_regime"


def test_symbol_report_rejects_mixed_symbols(aaa_pairs, portfolio_pairs) -> None:
    with pytest.raises(ConfigurationError, match="exactly one symbol"):
        build_symbol_report(aaa_pairs + portfolio_pairs["BBB"])
    with pytest.raises(ConfigurationError, match="no assessments"):
        build_symbol_report([])


# -- portfolio report --------------------------------------------------------------


def test_overview_counts_and_extremes(portfolio_pairs) -> None:
    report = build(portfolio_pairs)
    o = report.overview
    assert o["n_positions"] == 3
    assert o["total_market_value"] is None and "not carried" in o["total_market_value_note"]
    assert o["trim_candidates"] == 1  # AAA at 87 (Trim)
    assert o["maintain_candidates"] == 1  # BBB at 16 (Maintain)
    assert o["mixed_evidence"] == 0
    assert o["insufficient_evidence"] == 1  # CCC
    assert o["largest_position"] == {"symbol": "AAA", "portfolio_weight": 0.30}
    assert o["largest_risk_contributor"] == {"symbol": "AAA", "risk_contribution": 0.10}
    assert o["largest_concentration_adjustment"]["symbol"] == "AAA"
    assert o["largest_concentration_adjustment"]["value"] == pytest.approx(10.0)
    assert o["largest_diversification_benefit"]["symbol"] == "AAA"
    assert o["largest_diversification_benefit"]["value"] == pytest.approx(-5.0)


def test_highest_trim_ordering_and_top(portfolio_pairs) -> None:
    report = build(portfolio_pairs)
    assert [e["symbol"] for e in report.highest_trim] == ["AAA", "CCC", "BBB"]
    assert report.highest_trim[0]["trim_score"] == pytest.approx(87.0)
    trimmed = build(portfolio_pairs, top=2)
    assert [e["symbol"] for e in trimmed.highest_trim] == ["AAA", "CCC"]


def test_strongest_maintain_is_confidence_gated(portfolio_pairs) -> None:
    report = build(portfolio_pairs)
    # ascending trim among confidence >= 0.40: BBB (16), AAA (87); CCC (conf 0) excluded
    assert [e["symbol"] for e in report.strongest_maintain] == ["BBB", "AAA"]
    assert report.strongest_maintain[0]["primary_hold_strength"] == "sector_rotation"
    strict = build(portfolio_pairs, min_confidence=0.9)
    assert strict.strongest_maintain == ()


def test_pressure_and_diversification_orderings(portfolio_pairs) -> None:
    report = build(portfolio_pairs)
    assert [e["symbol"] for e in report.portfolio_pressure] == ["AAA"]  # +5 only
    assert report.portfolio_pressure[0]["portfolio_adjustment"] == pytest.approx(5.0)
    assert [e["symbol"] for e in report.diversification] == ["BBB"]  # -2 only
    assert report.diversification[0]["portfolio_adjustment"] == pytest.approx(-2.0)
    # CCC (adjustment exactly 0) is in neither: zero is never favorable/unfavorable
    assert all(e["symbol"] != "CCC" for e in report.portfolio_pressure + report.diversification)


def test_agreement_and_uncertainty_orderings(portfolio_pairs) -> None:
    report = build(portfolio_pairs)
    # agreement: ascending contradiction, no-evidence excluded
    assert [e["symbol"] for e in report.model_agreement] == ["BBB", "AAA"]
    # uncertainty: no_evidence first, then contradiction desc
    assert [e["symbol"] for e in report.greatest_uncertainty] == ["CCC", "AAA", "BBB"]
    assert report.greatest_uncertainty[0]["data_quality_label"] == "no_evidence"


def test_cross_horizon_changes_ranked_by_spread(portfolio_pairs) -> None:
    report = build(portfolio_pairs)
    first = report.cross_horizon_changes[0]
    assert first["symbol"] == "AAA"
    assert first["spread"] == pytest.approx(56.0)  # 87 at 1m minus 31 at 1w
    assert first["min_horizon"] == "1w" and first["max_horizon"] == "1m"
    assert any("trim score moves" in note for note in first["cross_horizon_notes"])
    spreads = [e["spread"] for e in report.cross_horizon_changes]
    assert spreads == sorted(spreads, reverse=True)


def test_insufficient_evidence_position_is_clearly_labeled(portfolio_pairs) -> None:
    report = build(portfolio_pairs)
    ccc = next(p for p in report.position_summaries if p["symbol"] == "CCC")
    assert ccc["recommendation_label"] == "Insufficient Evidence"
    assert ccc["confidence"] == 0.0
    assert ccc["largest_limitation"].startswith("no model produced combinable evidence")


def test_position_summaries_fields(portfolio_pairs) -> None:
    report = build(portfolio_pairs)
    assert [p["symbol"] for p in report.position_summaries] == ["AAA", "BBB", "CCC"]
    aaa = report.position_summaries[0]
    assert set(aaa["trim_scores"]) == {"1w", "1m", "3m", "6m", "1y"}
    assert aaa["trim_scores"]["1m"] == pytest.approx(87.0)
    assert aaa["primary_trim_driver"] == "macro_regime"
    assert aaa["primary_hold_strength"] == "sector_rotation"
    assert aaa["portfolio_adjustment"] == pytest.approx(5.0)


def test_portfolio_narrative_is_traceable(portfolio_pairs) -> None:
    report = build(portfolio_pairs)
    n = report.narrative
    assert "Across 3 positions in 'main' at the 1-month horizon" in n
    assert "1 trim candidate(s), 1 maintain candidate(s)" in n
    assert "The largest position is AAA (30.0% weight)." in n
    assert "The strongest trim evidence is AAA (87.0, Trim)" in n
    assert "the strongest maintain evidence is BBB (16.0, Maintain)" in n


def test_deterministic_and_json_round_trip(portfolio_pairs, aaa_pairs) -> None:
    first = build(portfolio_pairs)
    second = build(portfolio_pairs)
    assert first == second
    payload = first.to_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert payload["generated_at"] == GENERATED_AT.isoformat()
    symbol_payload = build_symbol_report(aaa_pairs).to_dict()
    assert json.loads(json.dumps(symbol_payload)) == symbol_payload


def test_renderers_cover_every_section(portfolio_pairs, aaa_pairs) -> None:
    symbol_report = build_symbol_report(aaa_pairs)
    text = render_symbol_text(symbol_report)
    for needle in (
        "AAA — decision report",
        "HORIZONS:",
        "CROSS-HORIZON INTERPRETATION:",
        "STRENGTHS (1m",
        "RISKS (1m",
        "UNCERTAINTY:",
        "ATTRIBUTION (1m",
        "neutral baseline",
        "not trade instructions",
    ):
        assert needle in text, needle
    md = render_symbol_markdown(symbol_report)
    assert "# AAA — Decision Report" in md
    assert "| Horizon | Trim |" in md
    assert "| **trim score** |" in md

    portfolio_report = build(portfolio_pairs)
    ptext = render_portfolio_text(portfolio_report)
    for needle in (
        "PORTFOLIO DECISION REPORT — main",
        "OVERVIEW:",
        "total market value: unavailable",
        "HIGHEST TRIM EVIDENCE (1m):",
        "STRONGEST MAINTAIN EVIDENCE",
        "GREATEST PORTFOLIO PRESSURE:",
        "GREATEST DIVERSIFICATION BENEFIT:",
        "GREATEST MODEL AGREEMENT:",
        "GREATEST UNCERTAINTY:",
        "LARGEST CROSS-HORIZON CHANGES:",
        "POSITION SUMMARIES:",
    ):
        assert needle in ptext, needle
    pmd = render_portfolio_markdown(portfolio_report)
    assert "# Portfolio Decision Report — main" in pmd
    assert "## Position Summaries" in pmd


def collect_keys(value, keys: set[str]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            keys.add(k)
            collect_keys(v, keys)
    elif isinstance(value, list):
        for item in value:
            collect_keys(item, keys)


def test_no_banned_action_fields(portfolio_pairs, aaa_pairs) -> None:
    banned = {
        "order",
        "order_quantity",
        "quantity",
        "shares",
        "shares_to_trade",
        "trade_quantity",
        "execution",
        "execution_instruction",
        "broker",
        "broker_action",
        "action",
    }
    for payload in (build(portfolio_pairs).to_dict(), build_symbol_report(aaa_pairs).to_dict()):
        keys: set[str] = set()
        collect_keys(payload, keys)
        assert not banned & keys


def test_report_layer_is_isolated_and_statistics_free() -> None:
    import mip.engine.report as module

    tree = ast.parse(inspect.getsource(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = (
        "mip.engine.evidence",  # DecisionEvidence is below this layer
        "mip.models",
        "mip.portfolio",
        "mip.research",
        "mip.features",
        "mip.providers",
        "mip.repositories",
        "mip.domain",
        "mip.ingestion",
    )
    for name in imported:
        assert not name.startswith(forbidden), f"forbidden import in report layer: {name}"
    mip_imports = {name for name in imported if name.startswith("mip.")}
    assert mip_imports == {"mip.engine.attribution", "mip.engine.trim", "mip.core.exceptions"}
    # "no new statistical calculations" — concretely: no numeric libraries
    assert not imported & {"math", "statistics", "numpy", "pandas", "scipy"}
