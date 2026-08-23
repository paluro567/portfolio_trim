"""The investment decision brief, and its research audit companion.

Two documents, deliberately different in kind:

* ``render_brief`` — the HUMAN-FACING decision tool, organised as
  TIMEFRAME → ACTION → CONVICTION → WHY → WHAT CHANGES IT, with the decision at
  the top. Target 800-1,500 words before the appendix.
* ``render_research_audit`` — everything the brief leaves out: the full source
  catalogue, every claim with its classification and citations, the validation
  report, usage and lineage. Auditability is not reduced, it is relocated.

Design rule, enforced by ``tests/unit/test_research_render.py``: **every number
in the brief is read from the deterministic objects**, never from the model. The
model supplies prose, classification and judgment; ``PositionState`` and
``HorizonVerdict`` supply price, weight, P&L and action. A model that claims a
different price cannot change what this renders.

The research bias (``ADD-BIASED HOLD``) is an interpretation layered on the
deterministic action, never a replacement: ``_action_label`` always ends with
the platform's own action word.
"""

from __future__ import annotations

import re
from typing import Any

from mip.product.contracts import HorizonVerdict, PositionState, Status
from mip.product.event import HORIZON_DAYS
from mip.research_assistant.contracts import (
    Catalyst,
    Claim,
    ClaimType,
    HorizonResearchView,
    InvestmentResearchResult,
    PortfolioResearchResult,
    ResearchBias,
    Scenario,
)
from mip.research_assistant.integrated import IntegratedHorizon, build_integrated_horizons
from mip.research_assistant.research import ResearchOutcome
from mip.research_assistant.sources import _QUALITY_RANK, SourceCatalogue

HZ_ORDER = ("1w", "1m", "3m", "6m", "1y")

# How many sources the BRIEF shows. The rest live in the research audit.
TOP_SOURCES_MAX = 12
MAX_CATALYSTS = 5
MAX_WATCH = 5
MAX_CHANGES = 5
MAX_RISKS = 5

_CLAIM_MARK = {
    ClaimType.FACT: "",
    ClaimType.INFERENCE: " _(inference)_",
    ClaimType.MODEL_JUDGMENT: " _(judgment)_",
    ClaimType.HISTORICAL_STATISTIC: " _(historical stat)_",
    ClaimType.UNVERIFIED: " **_(unverified)_**",
}


# --------------------------------------------------------------------- helpers
def _cite(claim: Claim) -> str:
    return " " + " ".join(f"[{s}]" for s in claim.source_ids) if claim.source_ids else ""


def _claim_line(claim: Claim) -> str:
    return f"{claim.text}{_CLAIM_MARK[claim.claim_type]}{_cite(claim)}"


def _bullets(
    claims: list[Claim], limit: int | None = None, empty: str = "_None identified._"
) -> str:
    items = claims[:limit] if limit else claims
    return "\n".join(f"- {_claim_line(c)}" for c in items) if items else empty


def _plain_bullets(items: list[str], limit: int | None = None, empty: str = "_None._") -> str:
    chosen = items[:limit] if limit else items
    return "\n".join(f"- {t}" for t in chosen) if chosen else empty


def _money(v) -> str:
    return "unavailable" if v is None else f"${v:,.2f}"


def _pct(v) -> str:
    return "unavailable" if v is None else f"{v:.2%}"


def _cell(v: Any) -> str:
    """Escape a value for a Markdown table cell and keep it on one visual line."""
    return str(v).replace("|", "\\|").replace("\n", " ").strip()


def _short(v: Any, words: int) -> str:
    """A table-cell-sized excerpt.

    The brief is a decision tool, so its tables stay scannable; the untruncated
    text is always preserved in the research audit, which is why shortening here
    costs no information.
    """
    text = _cell(v)
    parts = text.split()
    if len(parts) <= words:
        return text

    clipped = " ".join(parts[:words])
    # Prefer ending on a sentence boundary rather than mid-phrase, provided the
    # sentence ends late enough in the budget to still carry the point.
    cut = max(clipped.rfind(". "), clipped.rfind("? "), clipped.rfind("! "))
    if cut > 0 and len(clipped[: cut + 1].split()) >= int(words * 0.6):
        return clipped[: cut + 1]
    return clipped.rstrip(",;:.") + " …"


def _action_label(action: str, bias: ResearchBias | None) -> str:
    """Composite display label. ALWAYS ends with the deterministic action word.

    Thin alias over ``integrated.display_action`` so the label rule lives in
    exactly one place — the integrated layer — and the renderer cannot drift
    from it.
    """
    from mip.research_assistant.integrated import display_action

    return display_action(action, bias)


def _historical_cell(cell: IntegratedHorizon | None) -> str:
    """The historical-evidence cell.

    Shows figures only when the calibration is presentable. An unavailable or
    rejected calibration says so in words, because a blank cell reads as "no
    result" when the truth is "we are not entitled to a result".
    """
    if cell is None:
        return "unavailable"
    hist = cell.historical
    status = hist.get("validation_status")
    if status == "UNAVAILABLE":
        return "unavailable"
    if status == "REJECTED":
        return "REJECTED"
    bits = []
    if hist.get("positive_return_rate") is not None:
        bits.append(f"{hist['positive_return_rate']:.0%} positive")
    if hist.get("spy_outperformance_rate") is not None:
        bits.append(f"{hist['spy_outperformance_rate']:.0%} beat SPY")
    if hist.get("median_forward_return") is not None:
        bits.append(f"median {hist['median_forward_return']:+.1%}")
    if hist.get("sample_n") is not None:
        bits.append(f"N={hist['sample_n']:,}")
    if not bits:
        return str(status or "unavailable")
    return " · ".join(bits) + f"<br>_{status}_"


def _historical_note(integrated: list[IntegratedHorizon]) -> str:
    """One honest paragraph about the historical channel's standing."""
    reasons = {
        (h.historical.get("unavailable_reason") or "")
        for h in integrated
        if h.historical.get("validation_status") == "UNAVAILABLE"
    }
    reasons.discard("")
    if not reasons:
        return (
            "Historical evidence below is an empirical frequency over past occurrences of "
            "the same deterministic state. It is not a forecast and not a probability."
        )
    # The full blocker list belongs in the readiness audit, not in a decision
    # brief; two reasons carry the point and the rest is one link away.
    ordered = sorted(reasons, key=len)
    headline = "; ".join(ordered[:2])
    more = f" (+{len(ordered) - 2} further blockers)" if len(ordered) > 2 else ""
    return (
        "**Historical evidence is unavailable at every horizon.** No forward-outcome "
        f"calibration has been produced: {headline}{more}. Nothing is shown in its place — "
        "a fabricated frequency would be worse than an absent one. Full audit: "
        "`docs/HISTORICAL_CALIBRATION_READINESS.md`."
    )


def _views_by_horizon(result: InvestmentResearchResult | None) -> dict[str, HorizonResearchView]:
    """Index the model's per-horizon views defensively.

    The strict-schema subset cannot enforce list length or enum membership on
    ``horizon``, so a malformed or partial response must degrade to a
    deterministic-only row rather than raise.
    """
    if result is None:
        return {}
    out: dict[str, HorizonResearchView] = {}
    for view in result.horizon_views:
        key = (view.horizon or "").strip().lower()
        if key in HZ_ORDER and key not in out:
            out[key] = view
    return out


def _catalyst_horizons(catalyst: Catalyst, as_of) -> str:
    """Which horizons a dated catalyst falls inside. Computed, not asked for."""
    if not catalyst.date:
        return "—"
    from datetime import date as _date

    try:
        when = _date.fromisoformat(catalyst.date)
    except (ValueError, TypeError):
        return "—"
    days = (when - as_of).days
    if days < 0:
        return "past"
    inside = [h for h in HZ_ORDER if days <= HORIZON_DAYS[h]]
    if not inside:
        return "beyond 1y"
    return f"{inside[0]}+" if len(inside) > 1 else inside[0]


_EVENT_RE = re.compile(r"\((\d+)d, (\d{4}-\d{2}-\d{2})\)")


def _platform_event(evidence: list | None) -> tuple[str, int] | None:
    """The scheduled earnings date the PLATFORM already knows, if any.

    The model verifies catalyst dates against sources and is rightly cautious,
    so it often reports the next report as undated. The platform's own event
    store has the date, and it is a fact rather than a research finding — so it
    is rendered from here, not from the model.
    """
    if not evidence:
        return None
    item = next(
        (e for e in evidence if e.name == "event_state_1y" and e.status is not Status.UNAVAILABLE),
        None,
    )
    if item is None:
        return None
    hit = _EVENT_RE.search(item.value or "")
    return (hit.group(2), int(hit.group(1))) if hit else None


def _all_claims(result: InvestmentResearchResult) -> list[Claim]:
    groups: list[list[Claim]] = [
        result.recent_developments,
        result.competitive_context,
        result.analyst_expectations,
        result.risk_factors,
        result.earnings_analysis.key_beats,
        result.earnings_analysis.key_misses,
        result.earnings_analysis.segments,
        result.earnings_analysis.management_commentary,
        result.price_action_analysis.verified_drivers,
        result.price_action_analysis.likely_drivers,
        result.quant_vs_qual.confirmations,
        result.quant_vs_qual.contradictions,
        result.thesis_changes.positive_changes,
        result.thesis_changes.negative_changes,
        result.action_assessment.supports_add,
        result.action_assessment.supports_hold,
        result.action_assessment.supports_trim,
        result.action_assessment.supports_exit,
        result.bull_case.evidence,
        result.base_case.evidence,
        result.bear_case.evidence,
    ]
    return [c for group in groups for c in group]


def top_sources(result: InvestmentResearchResult | None, catalogue: SourceCatalogue | None) -> list:
    """The sources that actually carry the recommendation.

    Ranked by how often the research cites them, then by source quality. The
    model's own ``cited_source_ids`` is deliberately not used for this — on the
    first live run it listed 8 while 48 claims carried citations — so the count
    is taken from the claims themselves.
    """
    if catalogue is None or not catalogue.sources:
        return []
    if result is None:
        return catalogue.sources[:TOP_SOURCES_MAX]

    counts: dict[str, int] = {}
    for claim in _all_claims(result):
        for sid in claim.source_ids:
            counts[sid] = counts.get(sid, 0) + 1
    for catalyst in result.catalysts:
        for sid in catalyst.source_ids:
            counts[sid] = counts.get(sid, 0) + 1

    cited = [s for s in catalogue.sources if counts.get(s.id)]
    cited.sort(key=lambda s: (-counts.get(s.id, 0), _QUALITY_RANK[s.source_type], s.id))
    return cited[:TOP_SOURCES_MAX]


# ==========================================================================
# THE BRIEF
# ==========================================================================
def render_brief(
    pos: PositionState,
    verdicts: list[HorizonVerdict],
    outcome: ResearchOutcome,
    meta: dict,
    evidence: list | None = None,
    integrated: list[IntegratedHorizon] | None = None,
) -> str:
    lines: list[str] = []
    add = lines.append
    result = outcome.result if outcome.available else None
    views = _views_by_horizon(result)
    actions = {v.horizon: v.action.value for v in verdicts}
    ordered = sorted(verdicts, key=lambda v: HZ_ORDER.index(v.horizon))
    if integrated is None:
        # No calibration supplied: every historical cell reports UNAVAILABLE,
        # which is the honest reading rather than a blank column.
        integrated = build_integrated_horizons(pos, verdicts, [], {}, result)
    by_hz = {i.horizon: i for i in integrated}

    add(f"# {pos.symbol} — Investment Decision Brief")
    add(
        f"\n*As of {pos.as_of.isoformat()} · {_pct(pos.market_weight)} of portfolio · "
        f"{_money(pos.market_value)} · unrealised {_pct(pos.unrealized_pct)} · "
        f"research {outcome.freshness_note()}*"
    )

    # ------------------------------------------------------ 1. Decision summary
    add("\n## 1. Decision summary\n")
    if result is not None:
        add(result.decision_summary)
    else:
        add(
            f"**Qualitative research is UNAVAILABLE for this holding** "
            f"({outcome.failure_reason or 'reason not stated'}). The deterministic actions "
            f"below stand on their own and are unaffected."
        )

    add("\n### Timeframe decision matrix\n")
    add(
        "| Horizon | View | Action | Historical evidence | Setup · conviction | Why "
        "| What would change it |\n"
        "| --- | --- | --- | --- | --- | --- | --- |"
    )
    for verdict in ordered:
        view = views.get(verdict.horizon)
        cell = by_hz.get(verdict.horizon)
        label = (
            cell.integrated_view["display_action"]
            if cell is not None
            else _action_label(verdict.action.value, view.research_bias if view else None)
        )
        hist = _historical_cell(cell)
        if view is None:
            add(
                f"| **{verdict.horizon}** | {verdict.direction.value} | **{label}** "
                f"| {hist} | — | _no research view for this horizon_ | — |"
            )
            continue
        drivers = (
            f"<br>**+** {_short(view.primary_positive_driver, 9)} "
            f"· **−** {_short(view.primary_negative_driver, 9)}"
        )
        add(
            f"| **{verdict.horizon}** | {verdict.direction.value} | **{label}** "
            f"| {hist} | {view.setup.value} · {view.conviction.value} "
            f"| {_short(view.rationale, 32)}{drivers} | {_short(view.what_changes_it, 18)} |"
        )

    add(
        "\n*View is the platform's deterministic reading of the SECURITY. Action is its "
        "deterministic PORTFOLIO decision; an `ADD-BIASED` / `TRIM-BIASED` prefix is research "
        "interpretation only and never changes the action. Historical evidence is an empirical "
        "frequency over past states, NOT a forecast. Setup and conviction are qualitative "
        "judgments, not probabilities.*"
    )

    add(f"\n{_historical_note(integrated)}")

    add(_headline_block(result, outcome, actions))

    # ------------------------------------------- 2. Why the signals differ
    add("\n## 2. Why the signals differ by timeframe\n")
    if result is not None:
        hd = result.horizon_differences
        add(f"{hd.why_they_diverge}\n")
        add(f"- **Short term (1w–1m).** {hd.short_term_drivers}")
        add(f"- **Medium term (3m–6m).** {hd.medium_term_drivers}")
        add(f"- **Long term (1y).** {hd.long_term_drivers}")
    else:
        add(_deterministic_horizon_differences(ordered))

    if result is None:
        add(_position_block(pos, ordered))
        add(_limitations_block(outcome, None))
        return "\n".join(lines) + "\n"

    # ---------------------------------------------------------- 3. Current setup
    setup = result.current_setup
    add("\n## 3. Current setup\n")
    add("**Quantitative**\n")
    add(_sentences(setup.quantitative_setup, 4))
    add("\n**Company / fundamental**\n")
    add(_sentences(setup.fundamental_setup, 4))
    add("\n**Market environment**\n")
    add(_sentences(setup.market_environment, 3))

    # ----------------------------------------------------- 4. Position management
    aa = result.action_assessment
    add("\n## 4. Position management\n")
    add("**ADD if**\n" + _plain_bullets([_short(x, 28) for x in aa.add_if], limit=3))
    add("\n**HOLD while**\n" + _plain_bullets([_short(x, 28) for x in aa.hold_while], limit=3))
    add("\n**TRIM if**\n" + _plain_bullets([_short(x, 28) for x in aa.trim_if], limit=3))
    add("\n**EXIT if**\n" + _plain_bullets([_short(x, 28) for x in aa.exit_if], limit=3))
    add(
        f"\n**Sizing (separate from the security thesis).** "
        f"{_short(result.integrated_view.position_sizing_note, 45)}"
    )

    # ----------------------------------------------------------- 5. Key catalysts
    add("\n## 5. Key catalysts\n")
    ranked = [c for c in result.catalysts if c.date_is_verified] + [
        c for c in result.catalysts if not c.date_is_verified
    ]
    scheduled = _platform_event(evidence)
    if ranked or scheduled:
        add(
            "| Date | Verified | Event | Affects | Why it matters |\n"
            "| --- | --- | --- | --- | --- |"
        )
    if scheduled is not None:
        when, days = scheduled
        inside = [h for h in HZ_ORDER if days <= HORIZON_DAYS[h]]
        affects = (f"{inside[0]}+" if len(inside) > 1 else inside[0]) if inside else "beyond 1y"
        add(
            f"| {when} | platform | Next scheduled earnings report | {affects} "
            f"| Dated by the platform's own event store ({days} days out), not by research. "
            f"Resolves the quarter's operating evidence. |"
        )
    if ranked:
        for c in ranked[: MAX_CATALYSTS - (1 if scheduled else 0)]:
            cites = " ".join(f"[{s}]" for s in c.source_ids)
            add(
                f"| {_cell(c.date or 'undated')} | {'yes' if c.date_is_verified else '**no**'} "
                f"| {_short(c.name, 10)} {cites} | {_catalyst_horizons(c, pos.as_of)} "
                f"| {_short(c.why_it_matters, 22)} |"
            )
    elif scheduled is None:
        add("_No dated catalysts identified._")

    add("\n**Watch variables** — continuous, not dated events.\n")
    if result.watch_items:
        for w in result.watch_items[:MAX_WATCH]:
            when = f" _(by {w.expected_date})_" if w.expected_date else ""
            add(f"- **{_short(w.metric_or_event, 8)}** — {_short(w.condition, 20)}{when}")
    else:
        add("_None identified._")

    # ------------------------------------------------------------ 6. What changed
    add("\n## 6. What changed\n")
    add(_what_changed(outcome, result))

    # ------------------------------------------- 7. Key risks and contradictions
    add("\n## 7. Key risks and contradictions\n")
    add(_risks_block(result))

    # ---------------------------------------------------------- 8. Bull/base/bear
    add("\n## 8. Bull / base / bear\n")
    add(
        "| Scenario | Likelihood | Core thesis | Key confirmation | Key failure |\n"
        "| --- | --- | --- | --- | --- |"
    )
    add(_scenario_row("Bull", result.bull_case))
    add(_scenario_row("Base", result.base_case))
    add(_scenario_row("Bear", result.bear_case))
    add(
        "\n*Likelihood is an ordinal qualitative judgment. This report contains no numeric "
        "probability and no expected return.*"
    )

    # ------------------------------------------------------------- 9. Top sources
    add("\n## 9. Top sources\n")
    add(_top_sources_block(result, outcome))

    # -------------------------------------------------- 10. Position + verdicts
    add(_position_block(pos, ordered))
    add(_limitations_block(outcome, result))
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ fragments
def _headline_block(
    result: InvestmentResearchResult | None,
    outcome: ResearchOutcome,
    actions: dict[str, str],
) -> str:
    """The questions the first screen must answer beyond the matrix."""
    rows = ["\n| | |", "| --- | --- |"]
    if result is not None:
        rows.append(
            f"| **Key decision variable** | "
            f"{_cell(result.action_assessment.key_decision_variable)} |"
        )
    rows.append(f"| **Next catalyst** | {_cell(_next_catalyst_line(outcome))} |")
    if result is not None:
        view = result.integrated_view
        agree = (
            "agrees with the deterministic action"
            if view.agrees_with_deterministic_action
            else "**DISAGREES** with the deterministic action"
        )
        rows.append(f"| **Research view** | **{_cell(view.llm_research_view)}** — {agree} |")

    block = "\n".join(rows)
    if result is not None and not result.integrated_view.agrees_with_deterministic_action:
        block += (
            "\n\n> **⚠ Research disagrees with the deterministic engine.** Deterministic 1m "
            f"action is **{actions.get('1m', 'n/a')}**; research suggests "
            f"**{result.integrated_view.llm_research_view}**. "
            f"{result.integrated_view.disagreement_explanation or ''} Neither overrides the "
            "other — the disagreement is itself the signal to look closer."
        )
    return block


def _sentences(text: str, limit: int, words: int = 30) -> str:
    """Split a prose block into at most ``limit`` bullets, each capped in length.

    The untruncated prose is preserved verbatim in the research audit.
    """
    if not text:
        return "_Not stated._"
    parts = [p.strip() for p in text.replace("\n", " ").split(". ") if p.strip()]
    bullets = [_short(p if p.endswith(".") else p + ".", words) for p in parts[:limit]]
    return "\n".join(f"- {b}" for b in bullets) if bullets else "_Not stated._"


def _deterministic_horizon_differences(verdicts: list[HorizonVerdict]) -> str:
    """Fallback when research is unavailable: state the mechanical differences."""
    by_view: dict[str, list[str]] = {}
    for v in verdicts:
        by_view.setdefault(v.direction.value, []).append(v.horizon)
    if len(by_view) == 1:
        return f"The deterministic security view is {next(iter(by_view))} at every horizon."
    parts = [f"**{view}** at {', '.join(hz)}" for view, hz in by_view.items()]
    return (
        "The deterministic security view differs by horizon: "
        + "; ".join(parts)
        + ". Qualitative research was unavailable, so no explanation of the mechanism can be "
        "offered here — see the long-form deterministic report for which evidence groups are "
        "admitted at each horizon."
    )


def _what_changed(outcome: ResearchOutcome, result: InvestmentResearchResult) -> str:
    """Measured change first (Python-computed), then the research narrative."""
    out: list[str] = []
    diff = outcome.diff
    if diff is None or not diff.has_previous:
        out.append("- **UNCHANGED** — first research report for this holding; nothing to compare.")
    elif not diff.any_change:
        out.append(
            f"- **UNCHANGED** — no structural change since {diff.previous_as_of}: same research "
            f"view, same deterministic actions, same scenario bands, same catalysts."
        )
    else:
        if diff.view_changed:
            out.append(
                f"- **CHANGED** — research view {diff.previous_view} → **{diff.current_view}**"
            )
        for change in diff.action_changes[:2]:
            out.append(f"- **CHANGED** — deterministic action {change}")
        for change in diff.likelihood_changes[:2]:
            out.append(f"- **CHANGED** — scenario likelihood {change}")
        if diff.new_catalysts:
            out.append(f"- **NEW** — catalysts: {', '.join(diff.new_catalysts[:3])}")
        if diff.new_risks:
            out.append(f"- **DETERIORATED** — new risks: {'; '.join(diff.new_risks[:2])}")

    tc = result.thesis_changes
    for claim in tc.positive_changes[: max(0, MAX_CHANGES - len(out))]:
        out.append(f"- **IMPROVED** — {_claim_line(claim)}")
    for claim in tc.negative_changes[: max(0, MAX_CHANGES - len(out))]:
        out.append(f"- **DETERIORATED** — {_claim_line(claim)}")
    return "\n".join(out[:MAX_CHANGES]) if out else "_No material change._"


def _risks_block(result: InvestmentResearchResult) -> str:
    """Contradictions first — they are the most decision-relevant risk."""
    out: list[str] = []
    for claim in result.quant_vs_qual.contradictions[:2]:
        out.append(f"- **CONTRADICTION** — {_claim_line(claim)}")
    for claim in result.risk_factors[: MAX_RISKS - len(out)]:
        out.append(f"- {_claim_line(claim)}")
    return "\n".join(out[:MAX_RISKS]) if out else "_None identified._"


def _scenario_row(name: str, s: Scenario) -> str:
    confirm = "; ".join(s.what_would_confirm[:1]) or "—"
    invalidate = "; ".join(s.what_would_invalidate[:1]) or "—"
    return (
        f"| **{name}** | {_cell(s.likelihood.value)} | {_short(s.thesis, 26)} "
        f"| {_short(confirm, 16)} | {_short(invalidate, 16)} |"
    )


def _top_sources_block(result: InvestmentResearchResult | None, outcome: ResearchOutcome) -> str:
    chosen = top_sources(result, outcome.catalogue)
    total = len(outcome.catalogue.sources) if outcome.catalogue else 0
    if not chosen:
        return "_No sources captured._"
    rows = ["| ID | Type | Published | Source |", "| --- | --- | --- | --- |"]
    for s in chosen:
        rows.append(
            f"| {s.id} | {s.source_type.value} | {s.published_date or '—'} "
            f"| [{_cell(s.title or s.url)}]({s.url}) |"
        )
    rows.append(
        f"\n*Showing the {len(chosen)} most-cited of {total} retrieved sources. The full "
        f"catalogue, every claim and its citations are in the research audit file alongside "
        f"this brief. URLs are captured by the platform from the search tool, never written "
        f"by the model.*"
    )
    return "\n".join(rows)


def _next_catalyst_line(outcome: ResearchOutcome) -> str:
    if not outcome.available or outcome.result is None or not outcome.result.catalysts:
        return "none identified"
    dated = [c for c in outcome.result.catalysts if c.date]
    if not dated:
        return f"{outcome.result.catalysts[0].name} (undated)"
    nearest = min(dated, key=lambda c: c.date or "9999")
    mark = "" if nearest.date_is_verified else " (date unverified)"
    return f"{nearest.name} — {nearest.date}{mark}"


def _position_block(pos: PositionState, verdicts: list[HorizonVerdict]) -> str:
    rows = [
        "\n## 10. Position and deterministic verdicts\n",
        "Computed by the platform. The research layer cannot alter any of it.\n",
        "| Quantity | Avg cost | Price | Market value | Unrealised | Weight |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {pos.quantity if pos.quantity is not None else 'n/a'} | {_money(pos.average_cost)} "
        f"| {_money(pos.market_price)} | {_money(pos.market_value)} "
        f"| {_money(pos.unrealized_pnl)} ({_pct(pos.unrealized_pct)}) "
        f"| {_pct(pos.market_weight)} of {pos.portfolio_positions} positions |",
        "",
        "| Horizon | Security view | Action | Confidence |",
        "| --- | --- | --- | --- |",
    ]
    for v in verdicts:
        rows.append(
            f"| {v.horizon} | {v.direction.value} | **{v.action.value}** | {v.confidence.value} |"
        )
    rows.append(
        "\n*Full evidence, constraints, elimination traces and methodology are in the long-form "
        "deterministic report; full sources and claims are in the research audit.*"
    )
    return "\n".join(rows)


def _limitations_block(outcome: ResearchOutcome, result: InvestmentResearchResult | None) -> str:
    parts = ["\n## Limitations\n"]
    parts.append(
        "- Deterministic directional readings are **unvalidated heuristics**, not forecasts."
    )
    parts.append(
        "- Conviction and likelihood are ordinal judgments: **no numeric probability, no "
        "expected return**."
    )
    parts.append(
        "- Claims marked _(inference)_, _(judgment)_ or **_(unverified)_** are not sourced facts."
    )
    if outcome.validation is not None:
        parts.append(f"- Citation validation: {outcome.validation.summary()}.")
    if result is not None and result.limitations:
        parts.append(f"- {result.limitations[0]}")
    parts.append("- Full limitations, sources and methodology: see the research audit file.")
    return "\n".join(parts)


# ==========================================================================
# THE RESEARCH AUDIT — everything the brief deliberately leaves out
# ==========================================================================
def render_research_audit(
    pos: PositionState,
    verdicts: list[HorizonVerdict],
    outcome: ResearchOutcome,
    meta: dict,
) -> str:
    """Full auditability: every source, every claim, validation, lineage."""
    lines: list[str] = []
    add = lines.append
    # Same availability rule as the brief: a FAILED or DISABLED outcome renders
    # as unavailable even if a stale result object is still attached.
    result = outcome.result if outcome.available else None

    add(f"# {pos.symbol} — Research Audit ({pos.as_of.isoformat()})")
    add(
        "\n*Companion to the decision brief. Everything the brief summarises or omits is "
        "recorded here in full. Nothing here is a forecast.*"
    )

    add("\n## Provenance\n")
    add("| Field | Value |\n| --- | --- |")
    add(f"| Status | {outcome.status.value} |")
    add(f"| Model | {outcome.model or 'n/a'} |")
    add(f"| Generated | {outcome.generated_at or 'n/a'} |")
    add(f"| From cache | {outcome.from_cache} |")
    add(f"| Deterministic commit | `{meta.get('commit', 'unknown')}` |")
    add(f"| Feature date | {meta.get('feature_date', 'unavailable')} |")
    if outcome.usage is not None:
        u = outcome.usage
        add(f"| Response id | `{u.response_id or 'n/a'}` |")
        add(f"| Tokens | {u.input_tokens or 0:,} in / {u.output_tokens or 0:,} out |")
        add(f"| Web searches | {u.web_search_calls} |")
        add(f"| Elapsed | {u.elapsed_seconds:.1f}s |")
    if outcome.thesis is not None:
        add(f"| Thesis hash | `{outcome.thesis.get('content_hash', 'n/a')}` |")

    if outcome.validation is not None:
        v = outcome.validation
        add("\n## Citation validation\n")
        add(f"- Claims: **{v.claims_cited} cited / {v.claims_total} total**")
        add(f"- Verdict: {v.summary()}")
        add(f"- Unknown source IDs stripped: {v.unknown_source_ids or 'none'}")
        add(f"- Facts downgraded to UNVERIFIED: {len(v.facts_downgraded)}")
        for text in v.facts_downgraded[:10]:
            add(f"  - {text}")
        add(f"- Model-authored URLs stripped: {len(v.urls_emitted_by_model)}")
        add(f"- Probability-policy violations: {v.probability_violations or 'none'}")

    if result is None:
        add("\n## Research unavailable\n")
        add(f"> {outcome.failure_reason or 'not stated'}")
        return "\n".join(lines) + "\n"

    add("\n## Decision summary\n")
    add(result.decision_summary)
    add("\n## Company summary\n")
    add(result.company_summary)

    add("\n## Per-horizon research views\n")
    indexed = _views_by_horizon(result)
    for hz in HZ_ORDER:
        view = indexed.get(hz)
        if view is None:
            add(f"\n### {hz} — _no research view returned_")
            continue
        add(
            f"\n### {hz} — {view.setup.value} · bias {view.research_bias.value} · "
            f"conviction {view.conviction.value}"
        )
        add(f"\n{view.rationale}\n")
        add(f"- Positive driver: {view.primary_positive_driver}")
        add(f"- Negative driver: {view.primary_negative_driver}")
        add(f"- What changes it: {view.what_changes_it}")

    hd = result.horizon_differences
    add("\n## Horizon differences\n")
    add(f"**Why they diverge.** {hd.why_they_diverge}\n")
    add(f"- Short term: {hd.short_term_drivers}")
    add(f"- Medium term: {hd.medium_term_drivers}")
    add(f"- Long term: {hd.long_term_drivers}")

    add("\n## Current setup (full)\n")
    add(f"**Quantitative.** {result.current_setup.quantitative_setup}\n")
    add(f"**Market environment.** {result.current_setup.market_environment}\n")
    add(f"**Business / fundamental.** {result.current_setup.fundamental_setup}\n")
    add(f"**Catalysts.** {result.current_setup.catalyst_setup}")

    add("\n## What matters now\n")
    add(_plain_bullets(result.what_matters_now))
    add("\n## Recent developments\n")
    add(_bullets(result.recent_developments))
    add("\n## Industry and competitive context\n")
    add(_bullets(result.competitive_context))
    add("\n## Market expectations\n")
    add(_bullets(result.analyst_expectations))

    pa = result.price_action_analysis
    add("\n## Price action\n")
    add(f"{pa.observed_move}\n")
    if pa.no_single_catalyst_identified:
        add("**No single verified catalyst identified.**\n")
    add("**Verified drivers**\n" + _bullets(pa.verified_drivers, empty="_None verified._"))
    add("\n**Likely contributors**\n" + _bullets(pa.likely_drivers))
    if pa.unexplained_components:
        add("\n**Unexplained**\n" + _plain_bullets(pa.unexplained_components))
    add(f"\n*Attribution confidence: {pa.attribution_confidence.value}.*")

    ea = result.earnings_analysis
    add("\n## Earnings and guidance\n")
    add(f"{ea.latest_report_summary or '_No recent report summarised._'}\n")
    add("**Beats**\n" + _bullets(ea.key_beats))
    add("\n**Misses**\n" + _bullets(ea.key_misses))
    if ea.margins:
        add(f"\n**Margins.** {ea.margins}")
    if ea.segments:
        add("\n**Segments**\n" + _bullets(ea.segments))
    add(f"\n**Guidance ({ea.guidance_direction.value}).** {ea.guidance or '_None stated._'}")
    add("\n**Management commentary**\n" + _bullets(ea.management_commentary))
    if ea.expectation_context:
        add(f"\n**Expectation bar.** {ea.expectation_context}")

    add("\n## Scenarios (full)\n")
    for name, sc in (
        ("Bull", result.bull_case),
        ("Base", result.base_case),
        ("Bear", result.bear_case),
    ):
        add(f"\n### {name} — {sc.likelihood.value} ({sc.likelihood_type.value})\n")
        add(f"{sc.thesis}\n")
        add(f"*Rationale.* {sc.likelihood_rationale}\n")
        add("**Assumptions**\n" + _plain_bullets(sc.key_assumptions))
        add("\n**Evidence**\n" + _bullets(sc.evidence))
        add("\n**Would confirm**\n" + _plain_bullets(sc.what_would_confirm))
        add("\n**Would invalidate**\n" + _plain_bullets(sc.what_would_invalidate))

    add("\n## All catalysts\n")
    if result.catalysts:
        add("| Date | Verified | Event | Type | Direction | Impact | Why |")
        add("| --- | --- | --- | --- | --- | --- | --- |")
        for c in result.catalysts:
            cites = " ".join(f"[{s}]" for s in c.source_ids)
            add(
                f"| {_cell(c.date or 'undated')} | {c.date_is_verified} | {_cell(c.name)} {cites} "
                f"| {c.type.value} | {c.directionality.value} | {_cell(c.potential_impact)} "
                f"| {_cell(c.why_it_matters)} |"
            )
    else:
        add("_None._")

    add("\n## All watch items\n")
    for w in result.watch_items:
        add(
            f"- **{w.metric_or_event}** — {w.condition} "
            f"({w.expected_date or 'no date'}). {w.why_it_matters}"
        )

    add("\n## Quant vs qualitative\n")
    add("**Confirmations**\n" + _bullets(result.quant_vs_qual.confirmations))
    add("\n**Contradictions**\n" + _bullets(result.quant_vs_qual.contradictions))
    add("\n**Unresolved**\n" + _plain_bullets(result.quant_vs_qual.unresolved))
    add(f"\n**What matters most.** {result.quant_vs_qual.what_matters_most}")
    add(
        f"\n**What could change the conclusion.** "
        f"{result.quant_vs_qual.what_could_change_the_conclusion}"
    )

    aa = result.action_assessment
    add("\n## Action assessment (full)\n")
    add("**Supports ADD**\n" + _bullets(aa.supports_add))
    add("\n**Supports HOLD**\n" + _bullets(aa.supports_hold))
    add("\n**Supports TRIM**\n" + _bullets(aa.supports_trim))
    add("\n**Supports EXIT**\n" + _bullets(aa.supports_exit))
    add(f"\n**Strongest counterargument.** {aa.strongest_counterargument}")
    add(f"\n**Key decision variable.** {aa.key_decision_variable}")

    add("\n## All risk factors\n")
    add(_bullets(result.risk_factors))

    add("\n## Thesis changes (research narrative)\n")
    add("**Positive**\n" + _bullets(result.thesis_changes.positive_changes))
    add("\n**Negative**\n" + _bullets(result.thesis_changes.negative_changes))
    add("\n**Unchanged**\n" + _plain_bullets(result.thesis_changes.unchanged))

    if outcome.diff is not None:
        add("\n## Measured thesis diff (Python-computed)\n")
        add(f"```\n{outcome.diff.to_dict()}\n```")

    add("\n## Full source catalogue\n")
    add(_full_sources(outcome.catalogue))

    add("\n## Limitations (full)\n")
    add(_plain_bullets(result.limitations))
    return "\n".join(lines) + "\n"


def _full_sources(catalogue: SourceCatalogue | None) -> str:
    if catalogue is None or not catalogue.sources:
        return "_No sources captured._"
    rows = ["| ID | Type | Published | Domain | Source |", "| --- | --- | --- | --- | --- |"]
    for s in catalogue.sources:
        rows.append(
            f"| {s.id} | {s.source_type.value} | {s.published_date or '—'} | {s.domain} "
            f"| [{_cell(s.title or s.url)}]({s.url}) |"
        )
    mix = ", ".join(f"{k} {v}" for k, v in catalogue.quality_mix().items())
    rows.append(f"\n*{len(catalogue.sources)} sources. Mix: {mix}.*")
    return "\n".join(rows)


# ------------------------------------------------------ portfolio-level rendering
def render_portfolio_research(
    result: PortfolioResearchResult | None,
    as_of: str,
    meta: dict,
    error: str | None = None,
) -> str:
    lines = [
        "# Portfolio Research Synthesis",
        f"\n*As of {as_of}. Deterministic data at commit `{meta.get('commit', 'unknown')}`.*",
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
