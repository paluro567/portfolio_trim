"""Persisted investment thesis and the what-changed comparison.

The thesis artifact on disk is the source of truth, never model memory. Each
report writes a new version, keeps a bounded history, and hashes the content so
a thesis can be shown to have changed rather than asserted to have changed.

The what-changed diff is computed in PYTHON by comparing two artifacts. The
model also narrates thesis changes from its own research, and both are
rendered — but only the Python diff can state authoritatively that a label,
band, catalyst or watch item actually moved between two dated reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from mip.research_assistant.cache import artifact_hash
from mip.research_assistant.contracts import InvestmentResearchResult

MAX_HISTORY = 24

# Excluded from the thesis hash: lineage and timestamps describe the PREDECESSOR
# or the run, not this thesis, so including them would give an unchanged thesis a
# new hash merely for knowing what came before it.
_NOT_SUBSTANCE = frozenset({"history", "updated_at", "prior_conclusion", "prior_as_of"})


def build_thesis(
    symbol: str,
    as_of: date,
    result: InvestmentResearchResult,
    deterministic_actions: dict[str, str],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assemble the thesis record for this run, carrying prior state forward."""
    body: dict[str, Any] = {
        "as_of": as_of.isoformat(),
        "base_case": _scenario(result.base_case),
        "bear_case": _scenario(result.bear_case),
        "bull_case": _scenario(result.bull_case),
        "catalysts": [
            {
                "date": c.date,
                "date_is_verified": c.date_is_verified,
                "directionality": c.directionality.value,
                "name": c.name,
                "type": c.type.value,
            }
            for c in result.catalysts
        ],
        "current_thesis": result.base_case.thesis,
        "deterministic_actions": dict(sorted(deterministic_actions.items())),
        "key_decision_variable": result.action_assessment.key_decision_variable,
        "llm_research_view": result.integrated_view.llm_research_view,
        "overall_uncertainty": result.integrated_view.overall_uncertainty.value,
        "risk_factors": [c.text for c in result.risk_factors],
        "symbol": symbol.upper(),
        "unresolved_questions": list(result.quant_vs_qual.unresolved),
        "updated_at": datetime.now(UTC).isoformat(),
        "watch_items": [
            {
                "condition": w.condition,
                "expected_date": w.expected_date,
                "metric_or_event": w.metric_or_event,
            }
            for w in result.watch_items
        ],
    }

    prior_history = list((previous or {}).get("history", []))
    if previous:
        prior_history.append(
            {
                "as_of": previous.get("as_of"),
                "content_hash": previous.get("content_hash"),
                "current_thesis": previous.get("current_thesis"),
                "deterministic_actions": previous.get("deterministic_actions"),
                "llm_research_view": previous.get("llm_research_view"),
                "updated_at": previous.get("updated_at"),
            }
        )
    body["history"] = prior_history[-MAX_HISTORY:]
    body["prior_conclusion"] = (previous or {}).get("llm_research_view")
    body["prior_as_of"] = (previous or {}).get("as_of")

    # The hash answers exactly one question: "is this the same thesis?". So it
    # covers the substance only — not the timestamp, not the history log, and not
    # the lineage pointers, which describe the PREDECESSOR rather than this
    # thesis. Including them would give an unchanged thesis a new hash merely for
    # knowing what came before it, which is the opposite of what the hash is for.
    substantive = {k: v for k, v in body.items() if k not in _NOT_SUBSTANCE}
    body["content_hash"] = artifact_hash(substantive)
    return body


def _scenario(scenario: Any) -> dict[str, Any]:
    return {
        "assumptions": list(scenario.key_assumptions),
        "likelihood": scenario.likelihood.value,
        "likelihood_type": scenario.likelihood_type.value,
        "thesis": scenario.thesis,
    }


@dataclass(slots=True)
class ThesisDiff:
    """Python-computed change record between two thesis artifacts."""

    has_previous: bool
    previous_as_of: str | None = None
    view_changed: bool = False
    previous_view: str | None = None
    current_view: str | None = None
    action_changes: list[str] = field(default_factory=list)
    likelihood_changes: list[str] = field(default_factory=list)
    new_catalysts: list[str] = field(default_factory=list)
    dropped_catalysts: list[str] = field(default_factory=list)
    new_watch_items: list[str] = field(default_factory=list)
    resolved_watch_items: list[str] = field(default_factory=list)
    new_risks: list[str] = field(default_factory=list)
    thesis_text_changed: bool = False

    @property
    def any_change(self) -> bool:
        return bool(
            self.view_changed
            or self.action_changes
            or self.likelihood_changes
            or self.new_catalysts
            or self.dropped_catalysts
            or self.new_watch_items
            or self.resolved_watch_items
            or self.new_risks
            or self.thesis_text_changed
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_changes": self.action_changes,
            "any_change": self.any_change,
            "current_view": self.current_view,
            "dropped_catalysts": self.dropped_catalysts,
            "has_previous": self.has_previous,
            "likelihood_changes": self.likelihood_changes,
            "new_catalysts": self.new_catalysts,
            "new_risks": self.new_risks,
            "new_watch_items": self.new_watch_items,
            "previous_as_of": self.previous_as_of,
            "previous_view": self.previous_view,
            "resolved_watch_items": self.resolved_watch_items,
            "thesis_text_changed": self.thesis_text_changed,
            "view_changed": self.view_changed,
        }


def diff_thesis(previous: dict[str, Any] | None, current: dict[str, Any]) -> ThesisDiff:
    if not previous:
        return ThesisDiff(has_previous=False, current_view=current.get("llm_research_view"))

    diff = ThesisDiff(
        has_previous=True,
        previous_as_of=previous.get("as_of"),
        previous_view=previous.get("llm_research_view"),
        current_view=current.get("llm_research_view"),
    )
    diff.view_changed = diff.previous_view != diff.current_view
    diff.thesis_text_changed = previous.get("current_thesis") != current.get("current_thesis")

    prev_actions = previous.get("deterministic_actions") or {}
    curr_actions = current.get("deterministic_actions") or {}
    for horizon in sorted(set(prev_actions) | set(curr_actions)):
        before, after = prev_actions.get(horizon), curr_actions.get(horizon)
        if before != after:
            diff.action_changes.append(f"{horizon}: {before or 'n/a'} -> {after or 'n/a'}")

    for case in ("bull_case", "base_case", "bear_case"):
        before = (previous.get(case) or {}).get("likelihood")
        after = (current.get(case) or {}).get("likelihood")
        if before != after:
            label = case.replace("_case", "").upper()
            diff.likelihood_changes.append(f"{label}: {before or 'n/a'} -> {after or 'n/a'}")

    prev_cat = {c.get("name") for c in previous.get("catalysts") or []}
    curr_cat = {c.get("name") for c in current.get("catalysts") or []}
    diff.new_catalysts = sorted(n for n in curr_cat - prev_cat if n)
    diff.dropped_catalysts = sorted(n for n in prev_cat - curr_cat if n)

    prev_watch = {w.get("metric_or_event") for w in previous.get("watch_items") or []}
    curr_watch = {w.get("metric_or_event") for w in current.get("watch_items") or []}
    diff.new_watch_items = sorted(w for w in curr_watch - prev_watch if w)
    diff.resolved_watch_items = sorted(w for w in prev_watch - curr_watch if w)

    prev_risk = set(previous.get("risk_factors") or [])
    diff.new_risks = sorted(r for r in set(current.get("risk_factors") or []) - prev_risk if r)
    return diff
