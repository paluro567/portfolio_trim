"""The concise investment decision brief.

Design rule, enforced by ``tests/unit/test_research_render.py``: **every number
in this document is read from the deterministic objects**, never from the model.
The model supplies prose, classification and judgment; ``PositionState`` and
``HorizonVerdict`` supply price, weight, P&L and action. A model that claims a
different price cannot change what this renders.

The long-form deterministic report is unchanged and remains the audit artifact.
This brief is the primary human-facing document and is deliberately short.
"""

from __future__ import annotations

from typing import Any

from mip.product.contracts import HorizonVerdict, PositionState
from mip.research_assistant.contracts import (
    Claim,
    ClaimType,
    InvestmentResearchResult,
    PortfolioResearchResult,
    ResearchStatus,
    Scenario,
)
from mip.research_assistant.research import ResearchOutcome
from mip.research_assistant.sources import SourceCatalogue

_CLAIM_MARK = {
    ClaimType.FACT: "",
    ClaimType.INFERENCE: " _(inference)_",
    ClaimType.MODEL_JUDGMENT: " _(judgment)_",
    ClaimType.HISTORICAL_STATISTIC: " _(historical stat)_",
    ClaimType.UNVERIFIED: " **_(unverified)_**",
}


def _cite(claim: Claim) -> str:
    if not claim.source_ids:
        return ""
    return " " + " ".join(f"[{sid}]" for sid in claim.source_ids)


def _claim_line(claim: Claim) -> str:
    return f"{claim.text}{_CLAIM_MARK[claim.claim_type]}{_cite(claim)}"


def _bullets(
    claims: list[Claim], limit: int | None = None, empty: str = "_None identified._"
) -> str:
    items = claims[:limit] if limit else claims
    if not items:
        return empty
    return "\n".join(f"- {_claim_line(c)}" for c in items)


def _plain_bullets(items: list[str], limit: int | None = None, empty: str = "_None._") -> str:
    chosen = items[:limit] if limit else items
    if not chosen:
        return empty
    return "\n".join(f"- {t}" for t in chosen)


def _money(v) -> str:
    return "unavailable" if v is None else f"${v:,.2f}"


def _pct(v) -> str:
    return "unavailable" if v is None else f"{v:.2%}"


def _cell(v: Any) -> str:
    return str(v).replace("|", "\\|")


def _scenario_row(name: str, s: Scenario) -> str:
    confirm = "; ".join(s.what_would_confirm[:2]) or "—"
    invalidate = "; ".join(s.what_would_invalidate[:2]) or "—"
    assumptions = "; ".join(s.key_assumptions[:2]) or "—"
    return (
        f"| **{name}** | {_cell(s.likelihood_type.value)} | {_cell(s.likelihood.value)} "
        f"| {_cell(assumptions)} | {_cell(confirm)} | {_cell(invalidate)} |"
    )


def render_brief(
    pos: PositionState,
    verdicts: list[HorizonVerdict],
    outcome: ResearchOutcome,
    meta: dict,
) -> str:
    """Render the brief. Works whether or not research succeeded."""
    lines: list[str] = []
    add = lines.append

    actions = {v.horizon: v.action.value for v in verdicts}

    add(f"# {pos.symbol} — Investment Decision Brief")
    add(
        f"\n*As of {pos.as_of.isoformat()}. Deterministic data at commit "
        f"`{meta.get('commit', 'unknown')}`; latest price {pos.price_date or 'unavailable'}.*"
    )

    # ------------------------------------------------------------- 1. Decision
    add("\n## Decision\n")
    action_cells = " · ".join(
        f"{h} **{actions.get(h, 'n/a')}**" for h in ("1w", "1m", "3m", "6m", "1y")
    )
    add("| | |\n| --- | --- |\n" f"| **Deterministic action** | {action_cells} |")
    if outcome.available and outcome.result is not None:
        view = outcome.result.integrated_view
        agree = "agrees" if view.agrees_with_deterministic_action else "**DISAGREES**"
        add(f"| **Research view (security)** | **{view.llm_research_view}** — {agree} |")
        add(f"| **Research uncertainty** | {view.overall_uncertainty.value} |")
    else:
        add("| **Research view (security)** | _unavailable_ |")
    add(f"| **Position** | {_pct(pos.market_weight)} of portfolio · {_money(pos.market_value)} |")
    add(
        f"| **Unrealised** | {_money(pos.unrealized_pnl)} "
        f"({_pct(pos.unrealized_pct)}) at {_money(pos.average_cost)} avg cost |"
    )
    add(f"| **Next catalyst** | {_next_catalyst_line(outcome)} |")
    add(f"| **Research freshness** | {outcome.freshness_note()} |")

    if not outcome.available:
        add(_unavailable_block(outcome))
        add(_quant_appendix(pos, verdicts))
        add(_limitations_block(outcome))
        return "\n".join(lines) + "\n"

    result = outcome.result
    assert result is not None

    view = result.integrated_view
    if not view.agrees_with_deterministic_action:
        add(
            "\n> ### ⚠ The research view disagrees with the deterministic engine\n>\n"
            f"> Deterministic 1m action is **{actions.get('1m', 'n/a')}**; qualitative research "
            f"suggests **{view.llm_research_view}**.\n>\n"
            f"> {view.disagreement_explanation or 'No explanation supplied.'}\n>\n"
            "> Neither overrides the other. The deterministic action is an unvalidated "
            "heuristic; the research view is qualitative judgment. The disagreement is "
            "itself the signal to look closer."
        )

    add("\n**Integrated interpretation.** " + view.integrated_decision_commentary)

    # -------------------------------------------------------- 2. What matters now
    add("\n## What matters now\n")
    add(_plain_bullets(result.what_matters_now, limit=5))

    # ------------------------------------------------------------ 3. Current setup
    setup = result.current_setup
    add("\n## Current setup\n")
    add(f"**Quantitative.** {setup.quantitative_setup}\n")
    add(f"**Market environment.** {setup.market_environment}\n")
    add(f"**Business / fundamental.** {setup.fundamental_setup}\n")
    add(f"**Catalysts.** {setup.catalyst_setup}")

    # ------------------------------------------------------ 4. Recent developments
    add("\n## Recent developments\n")
    add(_bullets(result.recent_developments, limit=6, empty="_Nothing material found._"))
    if result.competitive_context:
        add("\n**Industry and competitive context**\n")
        add(_bullets(result.competitive_context, limit=3))
    if result.analyst_expectations:
        add("\n**Market expectations**\n")
        add(_bullets(result.analyst_expectations, limit=3))

    # ------------------------------------------------------ 5. Why the stock moved
    pa = result.price_action_analysis
    add("\n## Why the stock is moving\n")
    add(f"{pa.observed_move}\n")
    if pa.no_single_catalyst_identified:
        add("**No single verified catalyst identified.**\n")
    add("**Verified drivers**\n")
    add(_bullets(pa.verified_drivers, empty="_None verified from a source._"))
    add("\n**Likely contributors**\n")
    add(_bullets(pa.likely_drivers, empty="_None identified._"))
    if pa.unexplained_components:
        add("\n**Unexplained**\n")
        add(_plain_bullets(pa.unexplained_components))
    add(f"\n*Attribution confidence: {pa.attribution_confidence.value}.*")

    # ---------------------------------------------------------- 5. Earnings/guidance
    ea = result.earnings_analysis
    add("\n## Earnings and guidance\n")
    add(f"{ea.latest_report_summary or '_No recent report summarised._'}\n")
    if ea.key_beats:
        add("**Beats**\n" + _bullets(ea.key_beats, limit=3) + "\n")
    if ea.key_misses:
        add("**Misses**\n" + _bullets(ea.key_misses, limit=3) + "\n")
    if ea.margins:
        add(f"**Margins.** {ea.margins}\n")
    add(f"**Guidance ({ea.guidance_direction.value}).** {ea.guidance or '_None stated._'}\n")
    if ea.management_commentary:
        add("**Management commentary**\n" + _bullets(ea.management_commentary, limit=3) + "\n")
    if ea.expectation_context:
        add(f"**Expectation bar.** {ea.expectation_context}")

    # ----------------------------------------------------------- 6. Bull/base/bear
    add("\n## Bull / Base / Bear\n")
    add(
        "| Scenario | Likelihood type | Likelihood | Key assumptions | "
        "What would confirm | What would invalidate |\n"
        "| --- | --- | --- | --- | --- | --- |"
    )
    add(_scenario_row("Bull", result.bull_case))
    add(_scenario_row("Base", result.base_case))
    add(_scenario_row("Bear", result.bear_case))
    add(
        "\n> Likelihood is an **ordinal qualitative judgment**, not a probability. "
        "This platform has not established calibrated forecasting and emits no numeric "
        "probability or expected return."
    )

    # -------------------------------------------------------- 7. Position management
    aa = result.action_assessment
    add("\n## Position management\n")
    add("**ADD if**\n" + _plain_bullets(aa.add_if, limit=4))
    add("\n**HOLD while**\n" + _plain_bullets(aa.hold_while, limit=4))
    add("\n**TRIM if**\n" + _plain_bullets(aa.trim_if, limit=4))
    add("\n**EXIT if**\n" + _plain_bullets(aa.exit_if, limit=4))
    add(f"\n**Key decision variable.** {aa.key_decision_variable}")
    add(f"\n**Strongest counterargument.** {aa.strongest_counterargument}")
    add(
        f"\n**Position sizing (separate from the security thesis).** "
        f"{view.position_sizing_note}"
    )

    # ------------------------------------------------------------- 8. Catalysts
    add("\n## Key catalysts\n")
    if result.catalysts:
        add("| Date | Verified | Event | Type | Why it matters |\n| --- | --- | --- | --- | --- |")
        for c in result.catalysts[:8]:
            mark = "yes" if c.date_is_verified else "**no**"
            cites = " ".join(f"[{s}]" for s in c.source_ids)
            add(
                f"| {_cell(c.date or 'undated')} | {mark} | {_cell(c.name)} {cites} "
                f"| {_cell(c.type.value)} | {_cell(c.why_it_matters)} |"
            )
    else:
        add("_No catalysts identified._")

    # --------------------------------------------------- 9. What changed / watch
    add("\n## What changed since the last report\n")
    add(_diff_block(outcome, result))

    add("\n## What to watch next\n")
    if result.watch_items:
        for w in result.watch_items[:6]:
            when = f" _(expected {w.expected_date})_" if w.expected_date else ""
            add(f"- **{w.metric_or_event}** — {w.condition}{when}. {w.why_it_matters}")
    else:
        add("_None identified._")

    # ------------------------------------------------ 10. Risks and contradictions
    qq = result.quant_vs_qual
    add("\n## Risks and contradictions\n")
    add("**Risk factors**\n" + _bullets(result.risk_factors, limit=5))
    add("\n**Where quant and research contradict each other**\n")
    add(_bullets(qq.contradictions, empty="_No direct contradiction identified._"))
    if qq.confirmations:
        add("\n**Where they agree**\n" + _bullets(qq.confirmations, limit=3))
    if qq.unresolved:
        add("\n**Unresolved**\n" + _plain_bullets(qq.unresolved, limit=3))
    add(f"\n**What matters most.** {qq.what_matters_most}")
    add(f"\n**What could change the conclusion.** {qq.what_could_change_the_conclusion}")

    # ---------------------------------------------------------------- 11. Sources
    add("\n## Sources\n")
    add(_sources_block(outcome.catalogue))

    # ------------------------------------------------------- 12. Quant appendix
    add(_quant_appendix(pos, verdicts))

    # ----------------------------------------------------------- 13. Limitations
    add(_limitations_block(outcome, result))
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------- fragments
def _next_catalyst_line(outcome: ResearchOutcome) -> str:
    if not outcome.available or outcome.result is None or not outcome.result.catalysts:
        return "none identified"
    dated = [c for c in outcome.result.catalysts if c.date]
    if not dated:
        return f"{outcome.result.catalysts[0].name} (undated)"
    nearest = min(dated, key=lambda c: c.date or "9999")
    mark = "" if nearest.date_is_verified else " (date unverified)"
    return f"{nearest.name} — {nearest.date}{mark}"


def _unavailable_block(outcome: ResearchOutcome) -> str:
    label = {
        ResearchStatus.DISABLED: "disabled",
        ResearchStatus.FAILED: "failed",
    }.get(outcome.status, "unavailable")
    return (
        f"\n## Qualitative research: UNAVAILABLE\n\n"
        f"> Research was **{label}** for this holding, so this brief contains no current "
        f"news, catalyst, earnings or price-action analysis.\n>\n"
        f"> **Reason:** {outcome.failure_reason or 'not stated'}\n>\n"
        f"> The deterministic quantitative assessment below is unaffected and remains "
        f"complete. The full long-form report is also unchanged."
    )


def _diff_block(outcome: ResearchOutcome, result: InvestmentResearchResult) -> str:
    parts: list[str] = []
    diff = outcome.diff
    if diff is None or not diff.has_previous:
        parts.append("_First research report for this holding; nothing to compare against._")
    elif not diff.any_change:
        parts.append(
            f"_No structural change since {diff.previous_as_of}: same research view, "
            f"same deterministic actions, same scenario bands, same catalysts._"
        )
    else:
        parts.append(
            f"**Measured changes since {diff.previous_as_of}** (computed, not narrated):\n"
        )
        if diff.view_changed:
            parts.append(f"- Research view: {diff.previous_view} → **{diff.current_view}**")
        for change in diff.action_changes:
            parts.append(f"- Deterministic action {change}")
        for change in diff.likelihood_changes:
            parts.append(f"- Scenario likelihood {change}")
        if diff.new_catalysts:
            parts.append(f"- New catalysts: {', '.join(diff.new_catalysts)}")
        if diff.dropped_catalysts:
            parts.append(f"- Catalysts no longer listed: {', '.join(diff.dropped_catalysts)}")
        if diff.new_watch_items:
            parts.append(f"- New watch items: {', '.join(diff.new_watch_items)}")
        if diff.resolved_watch_items:
            parts.append(f"- Watch items dropped: {', '.join(diff.resolved_watch_items)}")
        if diff.new_risks:
            parts.append(f"- New risks: {'; '.join(diff.new_risks)}")
        if diff.thesis_text_changed:
            parts.append("- The base-case thesis text was rewritten")

    tc = result.thesis_changes
    if tc.positive_changes or tc.negative_changes:
        parts.append("\n**Research narrative of what changed**\n")
        if tc.positive_changes:
            parts.append("_Improved:_\n" + _bullets(tc.positive_changes, limit=3))
        if tc.negative_changes:
            parts.append("_Deteriorated:_\n" + _bullets(tc.negative_changes, limit=3))
    return "\n".join(parts)


def _sources_block(catalogue: SourceCatalogue | None) -> str:
    if catalogue is None or not catalogue.sources:
        return "_No sources captured._"
    rows = ["| ID | Type | Published | Source |", "| --- | --- | --- | --- |"]
    for s in catalogue.sources:
        title = _cell(s.title or s.url)
        rows.append(
            f"| {s.id} | {s.source_type.value} | {s.published_date or '—'} "
            f"| [{title}]({s.url}) |"
        )
    mix = ", ".join(f"{k} {v}" for k, v in catalogue.quality_mix().items())
    rows.append(
        f"\n*Source mix: {mix}. URLs are captured by the platform from the search "
        f"tool, never written by the model.*"
    )
    return "\n".join(rows)


def _quant_appendix(pos: PositionState, verdicts: list[HorizonVerdict]) -> str:
    rows = [
        "\n## Quantitative appendix (deterministic)\n",
        "Every value below is computed by the platform. The research layer cannot "
        "alter any of it.\n",
        "| Horizon | Security view | Action | Confidence |",
        "| --- | --- | --- | --- |",
    ]
    for v in verdicts:
        rows.append(
            f"| {v.horizon} | {v.direction.value} | **{v.action.value}** | {v.confidence.value} |"
        )
    rows.append(
        f"\n| Field | Value |\n| --- | --- |\n"
        f"| Quantity | {pos.quantity if pos.quantity is not None else 'unavailable'} |\n"
        f"| Average cost | {_money(pos.average_cost)} |\n"
        f"| Current price | {_money(pos.market_price)} |\n"
        f"| Market value | {_money(pos.market_value)} |\n"
        f"| Cost basis | {_money(pos.cost_basis)} |\n"
        f"| Unrealised P&L | {_money(pos.unrealized_pnl)} ({_pct(pos.unrealized_pct)}) |\n"
        f"| Market weight | {_pct(pos.market_weight)} |\n"
        f"| Portfolio positions | {pos.portfolio_positions} |"
    )
    rows.append(
        "\n*Full evidence, constraints, elimination traces and methodology are in the "
        "long-form deterministic report alongside this brief.*"
    )
    return "\n".join(rows)


def _limitations_block(
    outcome: ResearchOutcome, result: InvestmentResearchResult | None = None
) -> str:
    parts = ["\n## Limitations\n"]
    parts.append(
        "- Deterministic directional readings are **unvalidated heuristics**, not forecasts. "
        "No signal in this platform has established predictive reliability."
    )
    parts.append(
        "- Scenario likelihoods are ordinal judgments. This report contains **no numeric "
        "probability and no expected return**."
    )
    parts.append(
        "- Claims are marked _(inference)_, _(judgment)_ or **_(unverified)_** where they "
        "are not sourced facts. Unmarked claims carry citations."
    )
    if outcome.validation is not None:
        v = outcome.validation
        parts.append(f"- Citation validation: {v.summary()}.")
        if v.facts_downgraded:
            parts.append(
                f"- {len(v.facts_downgraded)} statement(s) were asserted as fact without a "
                f"traceable source and were **downgraded to UNVERIFIED** before rendering."
            )
        if v.probability_violations:
            parts.append(
                f"- {len(v.probability_violations)} probability-policy violation(s) were "
                f"detected in model output and are flagged in the artifact."
            )
    if result is not None:
        for item in result.limitations[:5]:
            parts.append(f"- {item}")
    parts.append(
        "- Fundamentals are current-value snapshots, not point-in-time vintages; sector "
        "classification and the earnings schedule are not point-in-time either."
    )
    return "\n".join(parts)


# ------------------------------------------------------ portfolio-level rendering
def render_portfolio_research(
    result: PortfolioResearchResult | None,
    as_of: str,
    meta: dict,
    error: str | None = None,
) -> str:
    lines = [
        "# Portfolio Research Synthesis",
        f"\n*As of {as_of}. " f"Deterministic data at commit `{meta.get('commit', 'unknown')}`.*",
    ]
    lines.append(
        "\n> This complements `PORTFOLIO.md`; it does not replace it. Nothing here is a "
        "forecast or a ranking by expected return."
    )
    if result is None:
        lines.append(
            f"\n## UNAVAILABLE\n\n> Portfolio synthesis could not be produced.\n>\n"
            f"> **Reason:** {error or 'not stated'}\n>\n"
            f"> Per-holding briefs and the deterministic portfolio report are unaffected."
        )
        return "\n".join(lines) + "\n"

    lines.append(f"\n## Summary\n\n{result.summary}")

    def flags(title: str, rows, note: str) -> None:
        lines.append(f"\n## {title}\n\n*{note}*\n")
        if not rows:
            lines.append("_None identified._")
            return
        lines.append("| Symbol | Reason | Detail |\n| --- | --- | --- |")
        for f in rows:
            lines.append(f"| **{_cell(f.symbol)}** | {_cell(f.reason)} | {_cell(f.detail)} |")

    def clusters(title: str, rows, note: str) -> None:
        lines.append(f"\n## {title}\n\n*{note}*\n")
        if not rows:
            lines.append("_None identified._")
            return
        for c in rows:
            lines.append(
                f"- **{c.name}** — {', '.join(c.symbols)}\n"
                f"  - Shared exposure: {c.shared_exposure}\n"
                f"  - Why it matters: {c.why_it_matters}"
            )

    flags(
        "Highest-priority reviews",
        result.highest_priority_reviews,
        "Where to look first. Not a prediction ranking.",
    )
    clusters(
        "Clustered risks",
        result.clustered_risks,
        "Risks that repeat across holdings and are invisible position by position.",
    )
    clusters(
        "Shared macro exposures",
        result.shared_macro_exposures,
        "Common factor sensitivity across the book.",
    )
    clusters(
        "Upcoming catalyst clusters",
        result.upcoming_catalyst_clusters,
        "Windows where several holdings resolve uncertainty at once.",
    )
    flags(
        "Cross-position contradictions",
        result.cross_position_contradictions,
        "Where the book is implicitly betting both ways.",
    )
    flags(
        "Quant vs research disagreement",
        result.quant_qual_disagreements,
        "Largest gaps between the deterministic engine and qualitative research.",
    )
    flags(
        "Large weights with deteriorating evidence",
        result.large_weights_deteriorating,
        "Size and direction of travel considered together.",
    )
    flags(
        "Attractive but size-constrained",
        result.attractive_but_size_constrained,
        "Security thesis and position sizing are separate questions.",
    )

    lines.append("\n## Limitations\n")
    for item in result.limitations[:8]:
        lines.append(f"- {item}")
    lines.append(
        "- Built from compact per-holding summaries, not from re-reading each holding's "
        "sources. Verify against the individual briefs before acting."
    )
    return "\n".join(lines) + "\n"
