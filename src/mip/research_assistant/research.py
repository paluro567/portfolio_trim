"""Orchestration: payload -> research -> validate -> persist.

The single most important property of this module is that **it never raises**.
Qualitative research is an enhancement; the deterministic report must survive
every possible failure of it. Every path returns a ``ResearchOutcome``, and a
failed one carries the reason so the report can say plainly what went wrong
instead of silently dropping a holding.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from mip.research_assistant import PROMPT_VERSION, SCHEMA_VERSION
from mip.research_assistant.cache import ArtifactStore, artifact_hash, cache_key, is_fresh
from mip.research_assistant.client import CallUsage, ResearchClient, ResearchUnavailableError
from mip.research_assistant.config import ResearchSettings
from mip.research_assistant.contracts import (
    InvestmentResearchResult,
    PortfolioResearchResult,
    ResearchStatus,
)
from mip.research_assistant.payload import HoldingPayload
from mip.research_assistant.prompts import (
    EXTRACTION_SYSTEM,
    PORTFOLIO_SYSTEM,
    RESEARCH_SYSTEM,
    extraction_user_prompt,
    portfolio_user_prompt,
    research_user_prompt,
)
from mip.research_assistant.sources import (
    SourceCatalogue,
    ValidationReport,
    build_catalogue,
    validate_and_sanitise,
)
from mip.research_assistant.thesis import ThesisDiff, build_thesis, diff_thesis


@dataclass(slots=True)
class ResearchOutcome:
    """Everything the renderer needs, whether research succeeded or not."""

    symbol: str
    as_of: date
    status: ResearchStatus
    result: InvestmentResearchResult | None = None
    catalogue: SourceCatalogue | None = None
    validation: ValidationReport | None = None
    thesis: dict[str, Any] | None = None
    diff: ThesisDiff | None = None
    usage: CallUsage | None = None
    failure_reason: str | None = None
    generated_at: str | None = None
    model: str | None = None
    from_cache: bool = False

    @property
    def available(self) -> bool:
        return self.result is not None and self.status in (
            ResearchStatus.OK,
            ResearchStatus.CACHED,
        )

    def freshness_note(self) -> str:
        if not self.available:
            return "unavailable"
        stamp = self.generated_at or "unknown time"
        return f"{'cached from ' if self.from_cache else 'generated '}{stamp}"


def run_research(
    payload: HoldingPayload,
    deterministic_actions: dict[str, str],
    *,
    settings: ResearchSettings,
    store: ArtifactStore,
    client: ResearchClient | None = None,
    deterministic_report_hash: str | None = None,
    refresh: bool = False,
    now: datetime | None = None,
) -> ResearchOutcome:
    """Research one holding. Never raises; failures come back as an outcome."""
    now = now or datetime.now(UTC)
    symbol, as_of = payload.symbol, payload.as_of
    payload_hash = payload.content_hash()
    key = cache_key(
        symbol=symbol,
        as_of=as_of,
        payload_hash=payload_hash,
        model=settings.model,
        prompt_version=PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
    )

    # -- 1. cache
    if not refresh:
        cached = store.load_research(symbol, as_of)
        if cached and is_fresh(cached, key=key, freshness_hours=settings.freshness_hours, now=now):
            restored = _restore(cached, symbol, as_of, store)
            if restored is not None:
                return restored

    # -- 2. is the layer usable at all?
    reason = settings.disabled_reason()
    if reason is not None:
        return ResearchOutcome(
            symbol=symbol,
            as_of=as_of,
            status=ResearchStatus.DISABLED,
            failure_reason=reason,
            model=settings.model,
        )

    # -- 3. live calls, each of which may fail without taking the report down
    try:
        active = client or ResearchClient(settings)
        payload_json = payload.as_prompt_json()

        call1 = active.research(
            RESEARCH_SYSTEM,
            research_user_prompt(symbol, as_of.isoformat(), payload_json),
        )
        catalogue = build_catalogue(call1.raw_sources, now)

        result, usage2 = active.extract(
            EXTRACTION_SYSTEM,
            extraction_user_prompt(
                symbol,
                as_of.isoformat(),
                payload_json,
                call1.text,
                catalogue.prompt_table(),
            ),
            InvestmentResearchResult,
        )
        validation = validate_and_sanitise(result, catalogue)
        usage = (call1.usage + usage2) if call1.usage else usage2
    except ResearchUnavailableError as exc:
        return ResearchOutcome(
            symbol=symbol,
            as_of=as_of,
            status=ResearchStatus.FAILED,
            failure_reason=str(exc),
            model=settings.model,
        )
    except Exception as exc:  # noqa: BLE001 - a bug here must not lose the holding
        return ResearchOutcome(
            symbol=symbol,
            as_of=as_of,
            status=ResearchStatus.FAILED,
            failure_reason=f"unexpected {type(exc).__name__}: {exc}",
            model=settings.model,
        )

    # -- 4. thesis memory and the Python-computed diff
    previous_thesis = store.load_thesis(symbol)
    thesis = build_thesis(symbol, as_of, result, deterministic_actions, previous_thesis)
    diff = diff_thesis(previous_thesis, thesis)

    # -- 5. persist. A write failure must not lose the research we just paid for.
    generated_at = now.isoformat()
    artifact = {
        "as_of": as_of.isoformat(),
        "cache_key": key,
        "deterministic_actions": dict(sorted(deterministic_actions.items())),
        "deterministic_report_hash": deterministic_report_hash,
        "generated_at": generated_at,
        "model": settings.model,
        "payload_hash": payload_hash,
        "prompt_version": PROMPT_VERSION,
        "research_result": result.model_dump(mode="json"),
        "research_writeup": call1.text,
        "response_id": usage.response_id if usage else None,
        "schema_version": SCHEMA_VERSION,
        "sources": catalogue.to_list(),
        "status": ResearchStatus.OK.value,
        "symbol": symbol.upper(),
        "thesis_diff": diff.to_dict(),
        "usage": usage.to_dict() if usage else None,
        "validation": validation.to_dict(),
    }
    artifact["content_hash"] = artifact_hash(
        {k: v for k, v in artifact.items() if k != "content_hash"}
    )
    try:
        store.write_research(symbol, as_of, artifact)
        store.write_thesis(symbol, thesis)
    except OSError as exc:  # persistence is best-effort; the outcome still stands
        validation.probability_violations.append(f"artifact-write-failed:{exc}")

    return ResearchOutcome(
        symbol=symbol,
        as_of=as_of,
        status=ResearchStatus.OK,
        result=result,
        catalogue=catalogue,
        validation=validation,
        thesis=thesis,
        diff=diff,
        usage=usage,
        generated_at=generated_at,
        model=settings.model,
        from_cache=False,
    )


def _restore(
    artifact: dict[str, Any], symbol: str, as_of: date, store: ArtifactStore
) -> ResearchOutcome | None:
    """Rebuild an outcome from a cached artifact. Returns None if unusable."""
    try:
        result = InvestmentResearchResult.model_validate(artifact["research_result"])
    except Exception:  # noqa: BLE001 - a stale/incompatible artifact is simply a miss
        return None

    catalogue = build_catalogue(
        [
            {
                "url": s.get("url"),
                "title": s.get("title"),
                "published_date": s.get("published_date"),
            }
            for s in artifact.get("sources", [])
        ],
        datetime.now(UTC),
    )
    validation = ValidationReport()
    raw_validation = artifact.get("validation") or {}
    validation.claims_total = raw_validation.get("claims_total", 0)
    validation.claims_cited = raw_validation.get("claims_cited", 0)
    validation.unknown_source_ids = list(raw_validation.get("unknown_source_ids", []))
    validation.facts_downgraded = list(raw_validation.get("facts_downgraded", []))
    validation.urls_emitted_by_model = list(raw_validation.get("urls_emitted_by_model", []))
    validation.probability_violations = list(raw_validation.get("probability_violations", []))

    thesis = store.load_thesis(symbol)
    diff_body = artifact.get("thesis_diff") or {}
    diff = ThesisDiff(
        has_previous=diff_body.get("has_previous", False),
        previous_as_of=diff_body.get("previous_as_of"),
        view_changed=diff_body.get("view_changed", False),
        previous_view=diff_body.get("previous_view"),
        current_view=diff_body.get("current_view"),
        action_changes=list(diff_body.get("action_changes", [])),
        likelihood_changes=list(diff_body.get("likelihood_changes", [])),
        new_catalysts=list(diff_body.get("new_catalysts", [])),
        dropped_catalysts=list(diff_body.get("dropped_catalysts", [])),
        new_watch_items=list(diff_body.get("new_watch_items", [])),
        resolved_watch_items=list(diff_body.get("resolved_watch_items", [])),
        new_risks=list(diff_body.get("new_risks", [])),
        thesis_text_changed=diff_body.get("thesis_text_changed", False),
    )

    usage_body = artifact.get("usage") or {}
    usage = (
        CallUsage(
            model=usage_body.get("model", artifact.get("model", "unknown")),
            input_tokens=usage_body.get("input_tokens"),
            output_tokens=usage_body.get("output_tokens"),
            total_tokens=usage_body.get("total_tokens"),
            reasoning_tokens=usage_body.get("reasoning_tokens"),
            web_search_calls=usage_body.get("web_search_calls", 0),
            elapsed_seconds=usage_body.get("elapsed_seconds", 0.0),
            response_id=usage_body.get("response_id"),
        )
        if usage_body
        else None
    )

    return ResearchOutcome(
        symbol=symbol,
        as_of=as_of,
        status=ResearchStatus.CACHED,
        result=result,
        catalogue=catalogue,
        validation=validation,
        thesis=thesis,
        diff=diff,
        usage=usage,
        generated_at=artifact.get("generated_at"),
        model=artifact.get("model"),
        from_cache=True,
    )


# ------------------------------------------------------- portfolio-level synthesis
def summarise_for_portfolio(outcome: ResearchOutcome, payload: HoldingPayload) -> dict[str, Any]:
    """Compact per-holding summary. Never the full research or any web content."""
    position = payload.body["position"]
    base: dict[str, Any] = {
        "symbol": outcome.symbol,
        "market_weight": position.get("market_weight"),
        "equal_weight_multiple": position.get("equal_weight_multiple"),
        "sector": payload.body["identity"].get("sector"),
        "deterministic_actions": {
            row["horizon"]: row["action"] for row in payload.body["deterministic_verdicts"]
        },
        "research_available": outcome.available,
    }
    if not outcome.available or outcome.result is None:
        base["research_unavailable_reason"] = outcome.failure_reason
        return base

    r = outcome.result
    base.update(
        {
            "llm_research_view": r.integrated_view.llm_research_view,
            "agrees_with_deterministic": r.integrated_view.agrees_with_deterministic_action,
            "overall_uncertainty": r.integrated_view.overall_uncertainty.value,
            "what_matters_now": r.what_matters_now[:3],
            "base_case": r.base_case.thesis,
            "top_risks": [c.text for c in r.risk_factors[:3]],
            "catalysts": [
                {"name": c.name, "date": c.date, "type": c.type.value} for c in r.catalysts[:4]
            ],
            "key_decision_variable": r.action_assessment.key_decision_variable,
            "contradictions": [c.text for c in r.quant_vs_qual.contradictions[:2]],
        }
    )
    return base


def run_portfolio_synthesis(
    as_of: date,
    summaries: list[dict[str, Any]],
    *,
    settings: ResearchSettings,
    store: ArtifactStore,
    client: ResearchClient | None = None,
    now: datetime | None = None,
) -> tuple[PortfolioResearchResult | None, CallUsage | None, str | None]:
    """One synthesis call over compact summaries. Returns (result, usage, error)."""
    import json

    now = now or datetime.now(UTC)
    reason = settings.disabled_reason()
    if reason is not None:
        return None, None, reason
    if not summaries:
        return None, None, "no per-holding research summaries to synthesise"

    try:
        active = client or ResearchClient(settings)
        result, usage = active.extract(
            PORTFOLIO_SYSTEM,
            portfolio_user_prompt(
                as_of.isoformat(), json.dumps(summaries, indent=2, sort_keys=True, default=str)
            ),
            PortfolioResearchResult,
        )
    except ResearchUnavailableError as exc:
        return None, None, str(exc)
    except Exception as exc:  # noqa: BLE001
        return None, None, f"unexpected {type(exc).__name__}: {exc}"

    artifact = {
        "as_of": as_of.isoformat(),
        "generated_at": now.isoformat(),
        "model": settings.model,
        "prompt_version": PROMPT_VERSION,
        "result": result.model_dump(mode="json"),
        "schema_version": SCHEMA_VERSION,
        "summaries_count": len(summaries),
        "usage": usage.to_dict() if usage else None,
    }
    artifact["content_hash"] = artifact_hash(
        {k: v for k, v in artifact.items() if k != "content_hash"}
    )
    try:
        store.write_portfolio(as_of, artifact)
    except OSError:
        pass
    return result, usage, None
