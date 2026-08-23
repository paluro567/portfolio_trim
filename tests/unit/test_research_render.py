"""The decision brief: what the model may and may not change, and how much fits.

Two families of guarantee are pinned here.

**Integrity.** ``test_a_hostile_model_cannot_change_any_number`` hands the
renderer a research result that actively lies about price, weight, P&L and the
recommended action, and asserts the brief still shows the deterministic values.
That property — not any prompt instruction — is what makes it safe to put a
language model in front of a portfolio. Alongside it, ``_action_label`` is
pinned to always end with the platform's own action word, so an "ADD-BIASED
HOLD" can never quietly become an ADD.

**Length.** The brief cannot be given a hard word cap in a unit test, because
prose length is the model's to choose and the renderer does not truncate
sentences. What IS enforceable, and is enforced here, are the structural caps
the renderer applies — catalysts, watch items, changes, risks, action bullets,
sources and setup bullets — plus the requirement that the brief is dramatically
shorter than the audit that backs it. The realised word count on live output is
measured at run time, not asserted here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from mip.product.contracts import Action
from mip.product.decide import decide
from mip.research_assistant.contracts import (
    Catalyst,
    CatalystType,
    ClaimType,
    Directionality,
    ResearchBias,
    ResearchStatus,
    SetupLabel,
)
from mip.research_assistant.render import (
    HZ_ORDER,
    MAX_CATALYSTS,
    TOP_SOURCES_MAX,
    _action_label,
    _all_claims,
    render_brief,
    render_portfolio_research,
    render_research_audit,
    top_sources,
)
from mip.research_assistant.research import ResearchOutcome
from mip.research_assistant.sources import build_catalogue, validate_and_sanitise
from mip.research_assistant.thesis import ThesisDiff
from tests.unit._research_support import claim, ev, horizon_views, make_result
from tests.unit.test_product_slice import _cons, _pos

NOW = datetime(2026, 8, 21, tzinfo=UTC)
META = {"commit": "abc1234", "feature_date": "2026-07-16"}


_DEFAULT = object()  # distinguishes "use the default result" from "no result"


def _setup(pos=None, result=_DEFAULT, status=ResearchStatus.OK, sources=None, **outcome_kw):
    pos = pos or _pos()
    cons = _cons()
    evidence = [ev("ret_21d")]
    verdicts = decide(evidence, cons, pos)
    catalogue = build_catalogue(sources or [{"url": "https://www.sec.gov/a", "title": "10-Q"}], NOW)
    res = make_result() if result is _DEFAULT else result
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


def _matrix_rows(brief: str) -> list[str]:
    """The data rows of the timeframe decision matrix."""
    section = brief.split("### Timeframe decision matrix", 1)[1]
    section = section.split("*Security view is", 1)[0]
    return [ln for ln in section.splitlines() if ln.startswith("| **")]


def _many_sources(n: int = 104):
    return [{"url": f"https://example{i}.com/a", "title": f"Article {i}"} for i in range(n)]


# ==========================================================================
# INTEGRITY
# ==========================================================================
def test_a_hostile_model_cannot_change_any_number():
    """A model that lies about every deterministic value changes nothing."""
    liar = make_result(llm_view="ADD", agrees=False)
    liar.decision_summary = (
        "The price is $9,999.99, the position is 88% of the portfolio, unrealised P&L is "
        "-$50,000, and the deterministic engine says EXIT at every horizon."
    )
    liar.current_setup.quantitative_setup = "Weight is 0.01% and market value is $1.00."

    pos, verdicts, outcome = _setup(result=liar)
    brief = render_brief(pos, verdicts, outcome, META)

    assert "$110.00" in brief, "deterministic price must render"
    assert "$1,100.00" in brief, "deterministic market value must render"
    assert "6.00%" in brief, "deterministic weight must render"
    assert "$100.00" in brief, "deterministic average cost must render"
    assert "10.00%" in brief, "deterministic unrealised percentage must render"

    for row in _matrix_rows(brief):
        assert "EXIT" not in row, "the model cannot invent an EXIT action"

    for v in verdicts:
        assert f"| {v.horizon} | {v.direction.value} | **{v.action.value}** |" in brief


def test_action_label_always_ends_with_the_deterministic_action():
    """The bias prefix is an annotation; the action word is the platform's."""
    for action in ("ADD", "HOLD", "TRIM", "EXIT"):
        for bias in ResearchBias:
            label = _action_label(action, bias)
            assert label.endswith(action), f"{label} must end with {action}"


def test_bias_only_annotates_a_hold():
    """An ADD that research also likes is not an 'ADD-BIASED ADD'."""
    assert _action_label("HOLD", ResearchBias.ADD_BIASED) == "ADD-BIASED HOLD"
    assert _action_label("HOLD", ResearchBias.TRIM_BIASED) == "TRIM-BIASED HOLD"
    assert _action_label("HOLD", ResearchBias.NEUTRAL) == "HOLD"
    assert _action_label("ADD", ResearchBias.ADD_BIASED) == "ADD"
    assert _action_label("TRIM", ResearchBias.TRIM_BIASED) == "TRIM"


def test_research_bias_is_rendered_without_changing_the_deterministic_action():
    views = horizon_views(biases=dict.fromkeys(HZ_ORDER, ResearchBias.ADD_BIASED))
    pos, verdicts, outcome = _setup(result=make_result(views=views))
    brief = render_brief(pos, verdicts, outcome, META)

    assert "ADD-BIASED HOLD" in brief
    for v in verdicts:
        assert f"| {v.horizon} | {v.direction.value} | **{v.action.value}** |" in brief
        assert v.action is Action.HOLD


def test_deterministic_and_research_views_stay_separate():
    pos, verdicts, outcome = _setup(result=make_result(llm_view="TRIM", agrees=False))
    brief = render_brief(pos, verdicts, outcome, META)
    assert "| **Research view** |" in brief
    assert "Security view" in brief and "Action" in brief


def test_disagreement_is_displayed_prominently_not_buried():
    pos, verdicts, outcome = _setup(result=make_result(llm_view="EXIT", agrees=False))
    brief = render_brief(pos, verdicts, outcome, META)

    assert "⚠ Research disagrees with the deterministic engine" in brief
    assert "Neither overrides the other" in brief
    assert brief.index("Research disagrees") < brief.index("## 3. Current setup")


def test_agreement_raises_no_banner():
    pos, verdicts, outcome = _setup(result=make_result(agrees=True))
    assert "Research disagrees" not in render_brief(pos, verdicts, outcome, META)


# ==========================================================================
# TIMEFRAME STRUCTURE
# ==========================================================================
def test_matrix_has_exactly_five_rows_in_horizon_order():
    pos, verdicts, outcome = _setup()
    rows = _matrix_rows(render_brief(pos, verdicts, outcome, META))
    assert len(rows) == 5
    for hz, row in zip(HZ_ORDER, rows, strict=True):
        assert row.startswith(f"| **{hz}** |")


def test_each_horizon_carries_view_action_conviction_setup_and_change_condition():
    views = horizon_views(setups={"1w": SetupLabel.CAUTIOUS, "1y": SetupLabel.CONSTRUCTIVE})
    pos, verdicts, outcome = _setup(result=make_result(views=views))
    brief = render_brief(pos, verdicts, outcome, META)

    for hz in HZ_ORDER:
        assert f"{hz} rationale sentence." in brief
        assert f"{hz} positive driver" in brief
        assert f"{hz} negative driver" in brief
        assert f"{hz} would change on this" in brief
    assert "CAUTIOUS" in brief and "CONSTRUCTIVE" in brief


def test_a_missing_horizon_view_degrades_to_a_deterministic_row():
    """A partial model response must not lose a horizon or raise."""
    partial = make_result(views=[v for v in horizon_views() if v.horizon != "3m"])
    pos, verdicts, outcome = _setup(result=partial)
    brief = render_brief(pos, verdicts, outcome, META)

    assert len(_matrix_rows(brief)) == 5, "all five horizons still appear"
    assert "_no research view for this horizon_" in brief


def test_duplicate_or_unknown_horizons_are_ignored():
    views = horizon_views()
    views[0].horizon = "1W"  # case variation, still valid
    views[1].horizon = "7d"  # not a real horizon
    pos, verdicts, outcome = _setup(result=make_result(views=views))
    assert len(_matrix_rows(render_brief(pos, verdicts, outcome, META))) == 5


def test_why_signals_differ_section_names_short_medium_and_long_drivers():
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)

    assert "## 2. Why the signals differ by timeframe" in brief
    assert "Short-horizon price evidence conflicts" in brief
    assert "**Short term (1w–1m).**" in brief
    assert "**Medium term (3m–6m).**" in brief
    assert "**Long term (1y).**" in brief


def test_decision_summary_appears_before_everything_else():
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    assert brief.index("## 1. Decision summary") < brief.index("### Timeframe decision matrix")
    assert brief.index("### Timeframe decision matrix") < brief.index("## 2. Why the signals")


def test_first_screen_answers_the_decision_questions():
    """Everything the first-screen acceptance test requires precedes section 3."""
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    head = brief.split("## 3. Current setup")[0]

    assert "Key decision variable" in head
    assert "Next catalyst" in head
    assert "Research view" in head
    assert "Why the signals differ" in head
    assert len(_matrix_rows(brief)) == 5


# ==========================================================================
# SECTION CONTENT AND CAPS
# ==========================================================================
def test_all_required_sections_present_in_order():
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    expected = [
        "## 1. Decision summary",
        "### Timeframe decision matrix",
        "## 2. Why the signals differ by timeframe",
        "## 3. Current setup",
        "## 4. Position management",
        "## 5. Key catalysts",
        "## 6. What changed",
        "## 7. Key risks and contradictions",
        "## 8. Bull / base / bear",
        "## 9. Top sources",
        "## 10. Position and deterministic verdicts",
        "## Limitations",
    ]
    positions = [brief.index(section) for section in expected]
    assert positions == sorted(positions), "sections must appear in order"


def test_position_management_has_all_four_action_conditions():
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    for label in ("**ADD if**", "**HOLD while**", "**TRIM if**", "**EXIT if**"):
        assert label in brief, label
    assert "Sizing (separate from the security thesis)" in brief


def test_catalysts_are_capped_and_verified_dates_come_first():
    def cat(name, verified):
        return Catalyst(
            name=name,
            date="2026-09-01",
            date_is_verified=verified,
            type=CatalystType.PRODUCT,
            directionality=Directionality.UNCLEAR,
            potential_impact="x",
            why_it_matters="y",
            source_ids=[],
        )

    many = [cat(f"unverified-{i}", False) for i in range(6)] + [cat("verified-1", True)]
    pos, verdicts, outcome = _setup(result=make_result(catalysts=many))
    brief = render_brief(pos, verdicts, outcome, META)

    section = brief.split("## 5. Key catalysts")[1].split("**Watch variables**")[0]
    rows = [ln for ln in section.splitlines() if ln.startswith("| 2026-")]
    assert len(rows) <= MAX_CATALYSTS
    assert "verified-1" in rows[0], "verified dates rank first"


def test_catalysts_and_watch_variables_are_separate():
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    assert "**Watch variables** — continuous, not dated events." in brief
    assert brief.index("## 5. Key catalysts") < brief.index("**Watch variables**")


def test_catalyst_affected_horizons_are_computed_from_the_date():
    """The horizon a catalyst touches is arithmetic, not a model opinion."""
    near = Catalyst(
        name="near event",
        date="2026-07-18",  # two days after the 2026-07-16 as_of
        date_is_verified=True,
        type=CatalystType.EARNINGS,
        directionality=Directionality.UNCLEAR,
        potential_impact="x",
        why_it_matters="y",
        source_ids=[],
    )
    pos, verdicts, outcome = _setup(result=make_result(catalysts=[near]))
    assert "| 1w+ |" in render_brief(pos, verdicts, outcome, META)


def test_what_changed_uses_status_labels_and_is_capped():
    pos, verdicts, outcome = _setup()
    outcome.diff = ThesisDiff(has_previous=True, previous_as_of="2026-08-14")
    brief = render_brief(pos, verdicts, outcome, META)
    section = brief.split("## 6. What changed")[1].split("## 7.")[0]
    assert "**UNCHANGED**" in section
    assert len([ln for ln in section.splitlines() if ln.startswith("- ")]) <= 5


def test_what_changed_reports_measured_view_and_action_changes():
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
    assert "HOLD → **TRIM**" in brief
    assert "1m: HOLD -> TRIM" in brief


def test_risks_lead_with_contradictions_and_are_capped():
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    section = brief.split("## 7. Key risks")[1].split("## 8.")[0]
    bullets = [ln for ln in section.splitlines() if ln.startswith("- ")]
    assert bullets and bullets[0].startswith("- **CONTRADICTION**")
    assert len(bullets) <= 5


def test_scenarios_render_as_one_compact_table_with_ordinal_likelihood():
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    assert "| Scenario | Likelihood | Core thesis | Key confirmation | Key failure |" in brief
    for name in ("**Bull**", "**Base**", "**Bear**"):
        assert name in brief
    assert "ordinal qualitative judgment" in brief
    assert "no numeric probability and no expected return" in brief


def test_fact_inference_and_judgment_marks_survive_the_redesign():
    result = make_result()
    result.risk_factors = [
        claim("a sourced risk", ClaimType.FACT, ["S1"]),
        claim("an inferred risk", ClaimType.INFERENCE, []),
        claim("a judged risk", ClaimType.MODEL_JUDGMENT, []),
    ]
    pos, verdicts, outcome = _setup(result=result)
    brief = render_brief(pos, verdicts, outcome, META)

    assert "a sourced risk [S1]" in brief
    assert "an inferred risk _(inference)_" in brief
    assert "a judged risk _(judgment)_" in brief


def test_an_unsupported_fact_is_still_downgraded_and_disclosed():
    result = make_result()
    result.risk_factors = [claim("unsupported", ClaimType.FACT, ["S404"])]
    pos, verdicts, outcome = _setup(result=result)
    brief = render_brief(pos, verdicts, outcome, META)
    assert "unsupported **_(unverified)_**" in brief


# ==========================================================================
# SOURCES: BRIEF SHOWS A FEW, AUDIT KEEPS ALL
# ==========================================================================
def test_brief_shows_only_top_sources_not_the_full_catalogue():
    pos, verdicts, outcome = _setup(sources=_many_sources())
    brief = render_brief(pos, verdicts, outcome, META)

    shown = [ln for ln in brief.splitlines() if ln.startswith("| S") and "](http" in ln]
    assert len(shown) <= TOP_SOURCES_MAX
    assert len(outcome.catalogue.sources) == 104
    assert "of 104 retrieved sources" in brief


def test_top_sources_are_ranked_by_how_often_research_cites_them():
    result = make_result()
    # The default fixture cites S1 throughout, so clear every citation first —
    # otherwise this measures the fixture rather than the ranking.
    for c in _all_claims(result):
        c.source_ids = []
    for c in result.catalysts:
        c.source_ids = []
    result.risk_factors = [claim("a", ClaimType.FACT, ["S3"])]
    result.recent_developments = [
        claim("b", ClaimType.FACT, ["S3", "S2"]),
        claim("c", ClaimType.FACT, ["S3", "S2", "S1"]),
    ]
    pos, verdicts, outcome = _setup(result=result, sources=_many_sources(10))
    chosen = [s.id for s in top_sources(result, outcome.catalogue)]
    assert chosen[:3] == ["S3", "S2", "S1"]


def test_uncited_sources_do_not_reach_the_brief():
    result = make_result()
    result.risk_factors = [claim("only S2", ClaimType.FACT, ["S2"])]
    result.recent_developments = []
    result.competitive_context = []
    result.analyst_expectations = []
    result.catalysts = []
    pos, verdicts, outcome = _setup(result=result, sources=_many_sources(10))
    chosen = {s.id for s in top_sources(result, outcome.catalogue)}
    assert "S2" in chosen
    assert "S9" not in chosen


def test_source_links_remain_valid_markdown_to_the_captured_url():
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    assert "[10-Q](https://www.sec.gov/a)" in brief
    assert "never written by the model" in brief


# ==========================================================================
# THE AUDIT COMPANION
# ==========================================================================
def test_audit_preserves_the_full_source_catalogue():
    pos, verdicts, outcome = _setup(sources=_many_sources())
    audit = render_research_audit(pos, verdicts, outcome, META)
    for sid in ("S1", "S50", "S104"):
        assert f"| {sid} |" in audit
    assert "104 sources." in audit


def test_audit_preserves_provenance_validation_and_per_horizon_detail():
    pos, verdicts, outcome = _setup()
    audit = render_research_audit(pos, verdicts, outcome, META)

    assert "## Provenance" in audit
    assert "## Citation validation" in audit
    assert "## Per-horizon research views" in audit
    assert "## Full source catalogue" in audit
    assert "## Limitations (full)" in audit
    for hz in HZ_ORDER:
        assert f"### {hz} —" in audit


def test_audit_keeps_content_the_brief_drops():
    pos, verdicts, outcome = _setup()
    audit = render_research_audit(pos, verdicts, outcome, META)
    brief = render_brief(pos, verdicts, outcome, META)

    assert "## Price action" in audit and "## Price action" not in brief
    assert "## Company summary" in audit
    assert "## Scenarios (full)" in audit
    assert "## Action assessment (full)" in audit
    assert len(audit) > len(brief), "the audit is the long document, the brief is not"


def test_audit_renders_when_research_failed():
    pos, verdicts, outcome = _setup(result=None, status=ResearchStatus.FAILED)
    outcome.failure_reason = "503 upstream unavailable"
    audit = render_research_audit(pos, verdicts, outcome, META)
    assert "## Research unavailable" in audit
    assert "503 upstream unavailable" in audit


# ==========================================================================
# LENGTH
# ==========================================================================
def test_position_management_bullets_are_capped_at_three():
    result = make_result(catalysts=[], watch_items=[], risk_factors=[])
    for bucket in ("add_if", "hold_while", "trim_if", "exit_if"):
        setattr(result.action_assessment, bucket, [f"condition {i}" for i in range(9)])

    pos, verdicts, outcome = _setup(result=result, sources=_many_sources())
    brief = render_brief(pos, verdicts, outcome, META)

    section = brief.split("## 4. Position management")[1].split("## 5.")[0]
    for label in ("**ADD if**", "**HOLD while**", "**TRIM if**", "**EXIT if**"):
        block = section.split(label)[1].split("\n**")[0]
        assert len([ln for ln in block.splitlines() if ln.startswith("- ")]) <= 3


def test_brief_body_stays_within_the_target_band():
    """The brief is a decision tool, not a dossier."""
    pos, verdicts, outcome = _setup()
    brief = render_brief(pos, verdicts, outcome, META)
    body = brief.split("## 10. Position and deterministic verdicts")[0]
    assert len(body.split()) < 1500


# ==========================================================================
# FAILURE MODES
# ==========================================================================
def test_failed_research_still_renders_the_deterministic_decision():
    pos, verdicts, outcome = _setup(result=None, status=ResearchStatus.FAILED)
    outcome.failure_reason = "503 upstream unavailable"
    brief = render_brief(pos, verdicts, outcome, META)

    assert "Qualitative research is UNAVAILABLE" in brief
    assert "503 upstream unavailable" in brief
    assert len(_matrix_rows(brief)) == 5, "the matrix still shows all five horizons"
    assert "$110.00" in brief
    assert "## Limitations" in brief


def test_failed_research_explains_horizon_differences_deterministically():
    pos, verdicts, outcome = _setup(result=None, status=ResearchStatus.FAILED)
    brief = render_brief(pos, verdicts, outcome, META)
    assert "## 2. Why the signals differ by timeframe" in brief
    assert "deterministic security view" in brief


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


def test_cached_research_discloses_its_timestamp():
    pos, verdicts, outcome = _setup(status=ResearchStatus.CACHED, from_cache=True)
    assert "cached from 2026-08-21" in render_brief(pos, verdicts, outcome, META)


# ==========================================================================
# PORTFOLIO VIEW (unchanged behaviour)
# ==========================================================================
def test_portfolio_research_complements_rather_than_replaces():
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


def test_table_cells_are_truncated_but_the_audit_keeps_the_full_text():
    """Brief tables stay scannable; nothing is lost because the audit has it all."""
    long_tail = "TAILWORD"
    result = make_result()
    result.horizon_views[0].rationale = " ".join(["word"] * 60 + [long_tail])
    result.bull_case.thesis = " ".join(["thesis"] * 60 + [long_tail])

    pos, verdicts, outcome = _setup(result=result)
    brief = render_brief(pos, verdicts, outcome, META)
    audit = render_research_audit(pos, verdicts, outcome, META)

    assert "…" in brief, "long cells are elided in the brief"
    assert long_tail not in brief, "the tail is cut from the brief table"
    assert long_tail in audit, "the audit preserves the full text"


def test_platform_scheduled_earnings_date_is_rendered_from_the_evidence_not_the_model():
    """The platform knows the date; the model is often rightly unsure of it."""
    from mip.product.contracts import Direction

    event = ev(
        "event_state_1y",
        group="event_risk",
        direction=Direction.NEUTRAL,
        domain="catalysts",
        value="WITHIN_HORIZON (76d, 2026-10-29)",
    )
    pos, verdicts, outcome = _setup(result=make_result(catalysts=[]))
    brief = render_brief(pos, verdicts, outcome, META, [event])

    # 76 days out, measured against the 2026-07-16 as_of, first lands inside 3m.
    assert "| 2026-10-29 | platform | Next scheduled earnings report | 3m+ |" in brief
    assert "not by research" in brief


def test_catalyst_table_absent_only_when_neither_source_has_a_date():
    pos, verdicts, outcome = _setup(result=make_result(catalysts=[]))
    brief = render_brief(pos, verdicts, outcome, META, evidence=None)
    assert "_No dated catalysts identified._" in brief
