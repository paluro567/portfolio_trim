"""The investment brief: what the model may and may not change.

The headline test here is ``test_a_hostile_model_cannot_change_any_number``.
It hands the renderer a research result that actively lies about the price,
weight, P&L and recommended action, and asserts that the brief still shows the
deterministic values. That property — not any prompt instruction — is what makes
it safe to put a language model in front of a portfolio.
"""

from __future__ import annotations

from datetime import UTC, datetime

from mip.product.decide import decide
from mip.research_assistant.contracts import ClaimType, ResearchStatus
from mip.research_assistant.render import render_brief, render_portfolio_research
from mip.research_assistant.research import ResearchOutcome
from mip.research_assistant.sources import build_catalogue, validate_and_sanitise
from mip.research_assistant.thesis import ThesisDiff
from tests.unit._research_support import claim, ev, make_result
from tests.unit.test_product_slice import _cons, _pos

NOW = datetime(2026, 8, 21, tzinfo=UTC)
META = {"commit": "abc1234", "feature_date": "2026-07-16"}


def _setup(pos=None, result=None, status=ResearchStatus.OK, **outcome_kw):
    pos = pos or _pos()
    cons = _cons()
    evidence = [ev("ret_21d")]
    verdicts = decide(evidence, cons, pos)
    catalogue = build_catalogue([{"url": "https://www.sec.gov/a", "title": "10-Q"}], NOW)
    res = result if result is not None else make_result()
    validation = validate_and_sanitise(res, catalogue) if res is not None else None
    outcome = ResearchOutcome(
        symbol=pos.symbol,
        as_of=pos.as_of,
        status=status,
        result=res,
        catalogue=catalogue,
        validation=validation,
        generated_at="2026-08-21T00:00:00+00:00",
        model="test-model",
        **outcome_kw,
    )
    return pos, verdicts, outcome


# ==========================================================================
# THE REGRESSION TEST REQUIRED BY THE SPEC
# ==========================================================================
def test_a_hostile_model_cannot_change_any_number():
    """A model that lies about every deterministic value changes nothing."""
    liar = make_result(llm_view="ADD", agrees=False)
    liar.current_setup.quantitative_setup = (
        "The price is $9,999.99, the position is 88% of the portfolio, "
        "unrealised P&L is -$50,000, the 21-day return is -95%, and the "
        "deterministic engine says EXIT at every horizon."
    )
    liar.company_summary = "Market value is $1.00 and the weight is 0.01%."

    pos, verdicts, outcome = _setup(result=liar)
    brief = render_brief(pos, verdicts, outcome, META)

    # The deterministic values survive, in the decision block and the appendix.
    assert "$110.00" in brief, "deterministic current price must be rendered"
    assert "$1,100.00" in brief, "deterministic market value must be rendered"
    assert "6.00%" in brief, "deterministic market weight must be rendered"
    assert "$100.00" in brief, "deterministic average cost must be rendered"
    assert "10.00%" in brief, "deterministic unrealised percentage must be rendered"

    # The model's invented figures never become the reported numbers.
    assert "$9,999.99" not in brief.split("## Current setup")[0]
    assert "88% of the portfolio" not in brief.split("## Current setup")[0]

    # The deterministic action is what the decision block reports.
    deterministic = {v.horizon: v.action.value for v in verdicts}
    for horizon, action in deterministic.items():
        assert f"{horizon} **{action}**" in brief

    # The model's own view is shown, but clearly as a SEPARATE field.
    assert "Research view (security)" in brief
    assert "**ADD**" in brief


def test_deterministic_action_and_llm_view_are_separate_fields():
    pos, verdicts, outcome = _setup(result=make_result(llm_view="TRIM", agrees=False))
    brief = render_brief(pos, verdicts, outcome, META)
    assert "**Deterministic action**" in brief
    assert "**Research view (security)**" in brief


def test_disagreement_is_displayed_prominently_not_buried():
    pos, verdicts, outcome = _setup(result=make_result(llm_view="EXIT", agrees=False))
    brief = render_brief(pos, verdicts, outcome, META)

    assert "⚠" in brief
    assert "disagrees with the deterministic engine" in brief
    assert "Neither overrides the other" in brief
    # The warning appears early, before the supporting detail.
    assert brief.index("disagrees with the deterministic engine") < brief.index("## Current setup")


def test_agreement_does_not_raise_a_warning_banner():
    pos, verdicts, outcome = _setup(result=make_result(agrees=True))
    brief = render_brief(pos, verdicts, outcome, META)
    assert "disagrees with the deterministic engine" not in brief


# ------------------------------------------------------- fact vs inference
def test_inference_and_judgment_are_visibly_marked():
    result = make_result()
    result.recent_developments = [
        claim("a sourced fact", ClaimType.FACT, ["S1"]),
        claim("an inference", ClaimType.INFERENCE, []),
        claim("a judgment", ClaimType.MODEL_JUDGMENT, []),
    ]
    pos, verdicts, outcome = _setup(result=result)
    brief = render_brief(pos, verdicts, outcome, META)

    assert "a sourced fact [S1]" in brief
    assert "an inference _(inference)_" in brief
    assert "a judgment _(judgment)_" in brief


def test_an_unsupported_fact_is_rendered_as_unverified():
    result = make_result(extra_claim=claim("unsupported", ClaimType.FACT, ["S404"]))
    pos, verdicts, outcome = _setup(result=result)
    brief = render_brief(pos, verdicts, outcome, META)
    assert "unsupported **_(unverified)_**" in brief
    assert "downgraded to UNVERIFIED" in brief


# ----------------------------------------------------------- probability policy
def test_no_numeric_probability_language_reaches_the_brief():
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    assert "ordinal qualitative judgment" in brief
    assert "no numeric probability and no expected return" in brief.lower()


def test_scenario_table_shows_likelihood_type_alongside_likelihood():
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    assert "| Scenario | Likelihood type | Likelihood |" in brief
    assert "QUALITATIVE_LLM" in brief


# --------------------------------------------------------------- structure
def test_brief_answers_the_position_management_questions():
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    for heading in (
        "## Decision",
        "## What matters now",
        "## Current setup",
        "## Recent developments",
        "## Why the stock is moving",
        "## Earnings and guidance",
        "## Bull / Base / Bear",
        "## Position management",
        "## Key catalysts",
        "## What changed since the last report",
        "## What to watch next",
        "## Risks and contradictions",
        "## Sources",
        "## Quantitative appendix (deterministic)",
        "## Limitations",
    ):
        assert heading in brief, heading
    for label in ("**ADD if**", "**HOLD while**", "**TRIM if**", "**EXIT if**"):
        assert label in brief, label


def test_security_thesis_and_position_sizing_stay_separate():
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    assert "Position sizing (separate from the security thesis)" in brief


def test_brief_is_concise_relative_to_the_long_form_report():
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    # The long-form deterministic report runs ~400 lines; the brief must not.
    assert len(brief.splitlines()) < 200


def test_sources_are_numbered_and_carry_platform_owned_urls():
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    assert "| S1 | SEC_FILING |" in brief
    assert "https://www.sec.gov/a" in brief
    assert "never written by the model" in brief


def test_unverified_catalyst_dates_are_flagged():
    from mip.research_assistant.contracts import Catalyst, CatalystType, Directionality

    result = make_result(
        catalysts=[
            Catalyst(
                name="Rumoured launch",
                date="2026-10-01",
                date_is_verified=False,
                type=CatalystType.PRODUCT,
                directionality=Directionality.POSITIVE,
                potential_impact="x",
                why_it_matters="y",
                source_ids=[],
            )
        ]
    )
    pos, verdicts, outcome = _setup(result=result)
    brief = render_brief(pos, verdicts, outcome, META)
    assert "| **no** |" in brief
    assert "date unverified" in brief


# -------------------------------------------------------------- failure modes
def test_failed_research_still_renders_a_usable_brief():
    pos, verdicts, outcome = _setup(result=None, status=ResearchStatus.FAILED)
    outcome.failure_reason = "503 upstream unavailable"
    brief = render_brief(pos, verdicts, outcome, META)

    assert "Qualitative research: UNAVAILABLE" in brief
    assert "503 upstream unavailable" in brief
    assert "## Quantitative appendix (deterministic)" in brief
    assert "$110.00" in brief, "deterministic numbers survive a research failure"
    assert "## Limitations" in brief


def test_disabled_research_explains_itself():
    pos, verdicts, outcome = _setup(result=None, status=ResearchStatus.DISABLED)
    outcome.failure_reason = "OPENAI_API_KEY is not set in the environment"
    brief = render_brief(pos, verdicts, outcome, META)
    assert "**disabled**" in brief
    assert "OPENAI_API_KEY" in brief


def test_missing_position_data_renders_as_unavailable_not_zero():
    pos = _pos(
        market_price=None,
        market_value=None,
        unrealized_pnl=None,
        unrealized_pct=None,
        market_weight=None,
    )
    pos, verdicts, outcome = _setup(pos=pos)
    brief = render_brief(pos, verdicts, outcome, META)
    assert "unavailable" in brief
    assert "$0.00" not in brief


# ------------------------------------------------------------- what changed
def test_first_report_says_there_is_nothing_to_compare():
    pos, verdicts, outcome = _setup()
    outcome.diff = ThesisDiff(has_previous=False)
    brief = render_brief(pos, verdicts, outcome, META)
    assert "First research report" in brief


def test_measured_changes_are_reported_as_computed_not_narrated():
    pos, verdicts, outcome = _setup()
    outcome.diff = ThesisDiff(
        has_previous=True,
        previous_as_of="2026-08-14",
        view_changed=True,
        previous_view="HOLD",
        current_view="TRIM",
        action_changes=["1m: HOLD -> TRIM"],
        new_catalysts=["FDA decision"],
    )
    brief = render_brief(pos, verdicts, outcome, META)
    assert "Measured changes since 2026-08-14" in brief
    assert "computed, not narrated" in brief
    assert "HOLD → **TRIM**" in brief
    assert "FDA decision" in brief


def test_no_change_since_last_report_is_stated_explicitly():
    pos, verdicts, outcome = _setup()
    outcome.diff = ThesisDiff(has_previous=True, previous_as_of="2026-08-14")
    brief = render_brief(pos, verdicts, outcome, META)
    assert "No structural change since 2026-08-14" in brief


def test_cached_research_discloses_its_timestamp():
    pos, verdicts, outcome = _setup(status=ResearchStatus.CACHED, from_cache=True)
    brief = render_brief(pos, verdicts, outcome, META)
    assert "cached from 2026-08-21" in brief


# ------------------------------------------------------------ portfolio view
def test_portfolio_research_renders_and_complements_rather_than_replaces():
    from mip.research_assistant.contracts import (
        PortfolioCluster,
        PortfolioFlag,
        PortfolioResearchResult,
    )

    result = PortfolioResearchResult(
        as_of="2026-08-21",
        highest_priority_reviews=[PortfolioFlag(symbol="AMZN", reason="weight", detail="10.5%")],
        clustered_risks=[
            PortfolioCluster(
                name="AI capex",
                symbols=["NVDA", "SMCI"],
                shared_exposure="hyperscaler spend",
                why_it_matters="correlated",
            )
        ],
        shared_macro_exposures=[],
        upcoming_catalyst_clusters=[],
        cross_position_contradictions=[],
        quant_qual_disagreements=[],
        large_weights_deteriorating=[],
        attractive_but_size_constrained=[],
        summary="concentrated in AI infrastructure",
        limitations=["compact summaries only"],
    )
    text = render_portfolio_research(result, "2026-08-21", {"commit": "abc1234"})

    assert "complements `PORTFOLIO.md`; it does not replace it" in text
    assert "**AMZN**" in text and "AI capex" in text
    assert "Nothing here is a forecast" in text


def test_failed_portfolio_synthesis_renders_an_explanation():
    text = render_portfolio_research(None, "2026-08-21", {}, error="rate limited")
    assert "UNAVAILABLE" in text and "rate limited" in text
    assert "Per-holding briefs and the deterministic portfolio report are unaffected" in text
