"""Shared builders for the research-assistant tests.

No test in this package may touch the real OpenAI API. Everything here is a
local stand-in shaped like the SDK's response objects, so the client's readers
are exercised against the structure they will actually meet.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

from mip.product.contracts import Direction, Evidence, Status
from mip.research_assistant.contracts import (
    ActionAssessment,
    Catalyst,
    CatalystType,
    Claim,
    ClaimType,
    CurrentSetup,
    Directionality,
    EarningsAnalysis,
    HorizonDifferences,
    HorizonResearchView,
    IntegratedView,
    InvestmentResearchResult,
    LikelihoodType,
    PriceActionAnalysis,
    QualitativeLikelihood,
    QuantVsQual,
    ResearchBias,
    Scenario,
    SetupLabel,
    ThesisChanges,
    WatchItem,
)

ALL_H = ("1w", "1m", "3m", "6m", "1y")


# ------------------------------------------------------------------- evidence
def ev(
    name: str,
    group: str = "absolute_momentum",
    direction: Direction = Direction.NEUTRAL,
    *,
    domain: str = "price/technical",
    value: str = "+0.1000",
    hz: tuple[str, ...] = ALL_H,
    status: Status = Status.DESCRIPTIVE,
    explanation: str | None = None,
) -> Evidence:
    return Evidence(
        name,
        domain,
        status,
        value,
        "feature_store_daily",
        date(2026, 7, 16),
        hz,
        explanation if explanation is not None else f"{name}; 55% of its own history",
        "limitation text",
        direction=direction,
        group=group,
    )


# -------------------------------------------------------------- result builder
def claim(text: str, kind: ClaimType = ClaimType.FACT, ids: list[str] | None = None) -> Claim:
    return Claim(text=text, claim_type=kind, source_ids=ids if ids is not None else ["S1"])


def scenario(thesis: str = "base thesis", likelihood=QualitativeLikelihood.MODERATE) -> Scenario:
    return Scenario(
        thesis=thesis,
        likelihood_type=LikelihoodType.QUALITATIVE_LLM,
        likelihood=likelihood,
        likelihood_rationale="because the evidence points that way",
        key_assumptions=["demand holds"],
        evidence=[claim("supporting fact")],
        what_would_confirm=["margin expands"],
        what_would_invalidate=["guidance cut"],
    )


def horizon_views(
    biases: dict[str, ResearchBias] | None = None,
    setups: dict[str, SetupLabel] | None = None,
) -> list[HorizonResearchView]:
    """Five per-horizon views, one per horizon, distinct by default."""
    biases = biases or {}
    setups = setups or {}
    return [
        HorizonResearchView(
            horizon=hz,
            setup=setups.get(hz, SetupLabel.MIXED),
            research_bias=biases.get(hz, ResearchBias.NEUTRAL),
            conviction=QualitativeLikelihood.MODERATE,
            rationale=f"{hz} rationale sentence.",
            primary_positive_driver=f"{hz} positive driver",
            primary_negative_driver=f"{hz} negative driver",
            what_changes_it=f"{hz} would change on this",
        )
        for hz in ALL_H
    ]


def make_result(
    symbol: str = "TEST",
    *,
    agrees: bool = True,
    llm_view: str = "HOLD",
    catalysts: list[Catalyst] | None = None,
    watch_items: list[WatchItem] | None = None,
    risk_factors: list[Claim] | None = None,
    extra_claim: Claim | None = None,
    views: list[HorizonResearchView] | None = None,
    decision_summary: str = (
        "TEST is a HOLD across all horizons. The setup is most constructive at 6m-1y "
        "while intermediate momentum is mixed, and position size rather than the "
        "security thesis is what prevents an ADD."
    ),
) -> InvestmentResearchResult:
    return InvestmentResearchResult(
        symbol=symbol,
        decision_summary=decision_summary,
        horizon_views=views if views is not None else horizon_views(),
        horizon_differences=HorizonDifferences(
            short_term_drivers="Momentum and event proximity dominate.",
            medium_term_drivers="Earnings trend and guidance dominate.",
            long_term_drivers="Company quality and valuation dominate.",
            why_they_diverge=(
                "Short-horizon price evidence conflicts with the longer business case."
            ),
        ),
        company_summary="A company that does things.",
        what_matters_now=["earnings in two weeks", "margin trend"],
        current_setup=CurrentSetup(
            quantitative_setup="momentum is mid-range",
            market_environment="bull regime, low VIX",
            fundamental_setup="quality above peers",
            catalyst_setup="earnings approaching",
        ),
        recent_developments=[extra_claim or claim("shipped a product")],
        earnings_analysis=EarningsAnalysis(
            latest_report_summary="beat on revenue",
            key_beats=[claim("revenue above consensus")],
            key_misses=[],
            margins="gross margin 34%",
            segments=[],
            guidance="reaffirmed full year",
            guidance_direction=Directionality.MIXED,
            management_commentary=[claim("management cited demand")],
            expectation_context="bar was already high",
        ),
        price_action_analysis=PriceActionAnalysis(
            observed_move="down 4% over 21 sessions",
            verified_drivers=[claim("sector sold off")],
            likely_drivers=[claim("rate move", ClaimType.INFERENCE, [])],
            unexplained_components=["residual 1%"],
            attribution_confidence=QualitativeLikelihood.MODERATE,
            no_single_catalyst_identified=False,
        ),
        catalysts=(
            catalysts
            if catalysts is not None
            else [
                Catalyst(
                    name="Q3 earnings",
                    date="2026-08-26",
                    date_is_verified=True,
                    type=CatalystType.EARNINGS,
                    directionality=Directionality.UNCLEAR,
                    potential_impact="large",
                    why_it_matters="resets the guidance bar",
                    source_ids=["S1"],
                )
            ]
        ),
        competitive_context=[],
        analyst_expectations=[],
        bull_case=scenario("bull thesis", QualitativeLikelihood.LOW),
        base_case=scenario("base thesis", QualitativeLikelihood.MODERATE),
        bear_case=scenario("bear thesis", QualitativeLikelihood.LOW),
        risk_factors=(
            risk_factors if risk_factors is not None else [claim("customer concentration")]
        ),
        thesis_changes=ThesisChanges(
            positive_changes=[claim("new contract")],
            negative_changes=[],
            unchanged=["strategy"],
        ),
        quant_vs_qual=QuantVsQual(
            confirmations=[claim("both point to deceleration")],
            contradictions=[claim("quant says weak, research says improving")],
            unresolved=["margin trajectory"],
            what_matters_most="the guidance bar",
            what_could_change_the_conclusion="a guidance cut",
        ),
        action_assessment=ActionAssessment(
            supports_add=[claim("valuation reset")],
            supports_hold=[claim("thesis intact")],
            supports_trim=[],
            supports_exit=[],
            add_if=["margin re-expands for two quarters"],
            hold_while=["guidance is reaffirmed"],
            trim_if=["guidance is cut"],
            exit_if=["the core customer is lost"],
            strongest_counterargument="the bar is already high",
            key_decision_variable="gross margin trajectory",
        ),
        integrated_view=IntegratedView(
            llm_research_view=llm_view,
            agrees_with_deterministic_action=agrees,
            disagreement_explanation=(
                None if agrees else "research sees a catalyst the quant cannot"
            ),
            integrated_decision_commentary="the two views mostly line up",
            position_sizing_note="already a full position; sizing argues against adding",
            overall_uncertainty=QualitativeLikelihood.MODERATE,
            uncertainty_explanation="limited recent disclosure",
        ),
        watch_items=(
            watch_items
            if watch_items is not None
            else [
                WatchItem(
                    metric_or_event="gross margin",
                    condition="above 35% next quarter",
                    why_it_matters="it is the decision variable",
                    expected_date="2026-08-26",
                )
            ]
        ),
        limitations=["no transcript was available"],
        cited_source_ids=["S1"],
    )


# ------------------------------------------------------------- fake SDK shapes
def _ns(**kw: Any) -> SimpleNamespace:
    return SimpleNamespace(**kw)


def fake_search_response(
    text: str = "research write-up\n\nSYNTHESIS\nthings agree",
    urls: list[tuple[str, str]] | None = None,
    *,
    searches: int = 2,
    refusal: str | None = None,
) -> SimpleNamespace:
    """Mimic a Responses object from a web-search-enabled call."""
    urls = urls if urls is not None else [("https://www.sec.gov/x", "10-Q filing")]
    content: list[Any] = []
    if refusal:
        content.append(_ns(type="refusal", refusal=refusal))
    else:
        content.append(
            _ns(
                type="output_text",
                text=text,
                annotations=[
                    _ns(type="url_citation", url=u, title=t, published_date="2026-08-01")
                    for u, t in urls
                ],
            )
        )
    output = [
        _ns(
            type="web_search_call",
            action=_ns(sources=[_ns(url=u, title=t, published_date=None) for u, t in urls]),
        )
    ] * searches
    output.append(_ns(type="message", content=content))
    return _ns(
        id="resp_test_1",
        output_text="" if refusal else text,
        output=output,
        usage=_ns(
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            output_tokens_details=_ns(reasoning_tokens=100),
        ),
    )


def fake_parse_response(parsed: Any, refusal: str | None = None) -> SimpleNamespace:
    content = (
        [_ns(type="refusal", refusal=refusal)]
        if refusal
        else [_ns(type="output_text", text="{}", annotations=[])]
    )
    return _ns(
        id="resp_test_2",
        output_text="{}",
        output=[_ns(type="message", content=content)],
        output_parsed=None if refusal else parsed,
        usage=_ns(
            input_tokens=2000,
            output_tokens=800,
            total_tokens=2800,
            output_tokens_details=_ns(reasoning_tokens=200),
        ),
    )


class FakeOpenAI:
    """Stands in for ``openai.OpenAI``. Records calls; never touches a network."""

    def __init__(
        self,
        search_response: Any = None,
        parse_response: Any = None,
        *,
        search_error: Exception | None = None,
        parse_error: Exception | None = None,
    ) -> None:
        self.search_response = search_response
        self.parse_response = parse_response
        self.search_error = search_error
        self.parse_error = parse_error
        self.create_calls: list[dict] = []
        self.parse_calls: list[dict] = []
        self.responses = _ns(create=self._create, parse=self._parse)

    def _create(self, **kw: Any) -> Any:
        self.create_calls.append(kw)
        if self.search_error:
            raise self.search_error
        return self.search_response if self.search_response is not None else fake_search_response()

    def _parse(self, **kw: Any) -> Any:
        self.parse_calls.append(kw)
        if self.parse_error:
            raise self.parse_error
        if self.parse_response is not None:
            return self.parse_response
        return fake_parse_response(make_result())
