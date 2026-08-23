"""Client behaviour, orchestration, caching, thesis history and failure modes.

No test here may reach the network. The OpenAI client is always injected.

The governing requirement is that the research layer is an ENHANCEMENT: every
failure mode must produce an outcome the report can render, never an exception
that loses a holding.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest

from mip.product.decide import decide
from mip.research_assistant import PROMPT_VERSION, SCHEMA_VERSION
from mip.research_assistant.cache import ArtifactStore, cache_key, is_fresh
from mip.research_assistant.client import ResearchClient, ResearchUnavailableError, collect_sources
from mip.research_assistant.config import ResearchSettings
from mip.research_assistant.contracts import InvestmentResearchResult, ResearchStatus
from mip.research_assistant.payload import build_payload
from mip.research_assistant.research import (
    run_portfolio_synthesis,
    run_research,
    summarise_for_portfolio,
)
from mip.research_assistant.thesis import build_thesis, diff_thesis
from tests.unit._research_support import (
    FakeOpenAI,
    ev,
    fake_parse_response,
    fake_search_response,
    make_result,
)
from tests.unit.test_product_slice import _cons, _pos

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def _settings(tmp_path, **kw) -> ResearchSettings:
    base = dict(
        enabled=True,
        api_key_present=True,
        model="test-model",
        max_search_calls=4,
        freshness_hours=18,
        timeout_seconds=60,
        max_output_tokens=4000,
        research_root=tmp_path / "research",
    )
    base.update(kw)
    return ResearchSettings(**base)


def _payload(symbol="TEST"):
    pos = _pos(symbol=symbol)
    cons = _cons()
    evidence = [ev("ret_21d")]
    verdicts = decide(evidence, cons, pos)
    return build_payload(pos, evidence, cons, verdicts), verdicts


def _actions(verdicts):
    return {v.horizon: v.action.value for v in verdicts}


# --------------------------------------------------------------------- client
def test_research_call_enables_web_search_and_requests_sources():
    fake = FakeOpenAI()
    client = ResearchClient(_settings_stub(), openai_client=fake)
    client.research("sys", "user")

    kw = fake.create_calls[0]
    assert kw["tools"] == [{"type": "web_search", "search_context_size": "high"}]
    assert kw["include"] == ["web_search_call.action.sources"]
    assert kw["store"] is False, "responses must not be retained server-side"


def test_extraction_call_uses_structured_output_and_no_tools():
    fake = FakeOpenAI()
    client = ResearchClient(_settings_stub(), openai_client=fake)
    client.extract("sys", "user", InvestmentResearchResult)

    kw = fake.parse_calls[0]
    assert kw["text_format"] is InvestmentResearchResult
    assert "tools" not in kw, "the extraction step must not have web access"


def _settings_stub():
    return ResearchSettings(
        enabled=True,
        api_key_present=True,
        model="test-model",
        max_search_calls=4,
        freshness_hours=18,
        timeout_seconds=60,
        max_output_tokens=4000,
        research_root=None,  # type: ignore[arg-type]
    )


def test_sources_are_collected_from_both_tool_output_and_annotations():
    response = fake_search_response(urls=[("https://a.com/1", "A"), ("https://b.com/2", "B")])
    found = {s["url"] for s in collect_sources(response)}
    assert found == {"https://a.com/1", "https://b.com/2"}


def test_usage_counts_web_search_calls():
    fake = FakeOpenAI(search_response=fake_search_response(searches=3))
    client = ResearchClient(_settings_stub(), openai_client=fake)
    result = client.research("s", "u")
    assert result.usage is not None
    assert result.usage.web_search_calls == 3
    assert result.usage.input_tokens == 1000


def test_a_refusal_becomes_research_unavailable():
    fake = FakeOpenAI(search_response=fake_search_response(refusal="I cannot help"))
    client = ResearchClient(_settings_stub(), openai_client=fake)
    with pytest.raises(ResearchUnavailableError, match="refused"):
        client.research("s", "u")


def test_an_empty_response_becomes_research_unavailable():
    fake = FakeOpenAI(search_response=fake_search_response(text=""))
    client = ResearchClient(_settings_stub(), openai_client=fake)
    with pytest.raises(ResearchUnavailableError, match="no text"):
        client.research("s", "u")


def test_a_missing_parsed_object_becomes_research_unavailable():
    fake = FakeOpenAI(parse_response=fake_parse_response(None))
    client = ResearchClient(_settings_stub(), openai_client=fake)
    with pytest.raises(ResearchUnavailableError, match="no parsed object"):
        client.extract("s", "u", InvestmentResearchResult)


def test_a_dict_shaped_parse_result_is_revalidated_not_trusted_blindly():
    payload = make_result().model_dump(mode="json")
    fake = FakeOpenAI(parse_response=fake_parse_response(payload))
    client = ResearchClient(_settings_stub(), openai_client=fake)
    parsed, _ = client.extract("s", "u", InvestmentResearchResult)
    assert isinstance(parsed, InvestmentResearchResult)


def test_malformed_parse_result_is_rejected():
    fake = FakeOpenAI(parse_response=fake_parse_response({"nonsense": True}))
    client = ResearchClient(_settings_stub(), openai_client=fake)
    with pytest.raises(ResearchUnavailableError, match="failed validation"):
        client.extract("s", "u", InvestmentResearchResult)


def test_client_refuses_to_construct_without_a_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ResearchUnavailableError, match="OPENAI_API_KEY"):
        ResearchClient(_settings_stub())


# --------------------------------------------------------------- orchestration
def test_successful_run_produces_an_available_outcome(tmp_path):
    payload, verdicts = _payload()
    store = ArtifactStore(root=tmp_path)
    outcome = run_research(
        payload,
        _actions(verdicts),
        settings=_settings(tmp_path),
        store=store,
        client=ResearchClient(_settings_stub(), openai_client=FakeOpenAI()),
        now=NOW,
    )
    assert outcome.status is ResearchStatus.OK
    assert outcome.available
    assert outcome.result is not None
    assert outcome.catalogue is not None and outcome.catalogue.sources


def test_api_failure_degrades_to_a_failed_outcome_and_never_raises(tmp_path):
    payload, verdicts = _payload()
    fake = FakeOpenAI(search_error=RuntimeError("503 upstream unavailable"))
    outcome = run_research(
        payload,
        _actions(verdicts),
        settings=_settings(tmp_path),
        store=ArtifactStore(root=tmp_path),
        client=ResearchClient(_settings_stub(), openai_client=fake),
        now=NOW,
    )
    assert outcome.status is ResearchStatus.FAILED
    assert not outcome.available
    assert "503" in (outcome.failure_reason or "")


def test_extraction_failure_also_degrades_gracefully(tmp_path):
    payload, verdicts = _payload()
    fake = FakeOpenAI(parse_error=ValueError("schema blew up"))
    outcome = run_research(
        payload,
        _actions(verdicts),
        settings=_settings(tmp_path),
        store=ArtifactStore(root=tmp_path),
        client=ResearchClient(_settings_stub(), openai_client=fake),
        now=NOW,
    )
    assert outcome.status is ResearchStatus.FAILED
    assert "schema blew up" in (outcome.failure_reason or "")


def test_disabled_layer_returns_disabled_not_failed(tmp_path):
    payload, verdicts = _payload()
    outcome = run_research(
        payload,
        _actions(verdicts),
        settings=_settings(tmp_path, enabled=False),
        store=ArtifactStore(root=tmp_path),
        now=NOW,
    )
    assert outcome.status is ResearchStatus.DISABLED
    assert "MIP_OPENAI_ENABLED" in (outcome.failure_reason or "")


def test_missing_key_reports_disabled_with_the_variable_name(tmp_path):
    payload, verdicts = _payload()
    outcome = run_research(
        payload,
        _actions(verdicts),
        settings=_settings(tmp_path, api_key_present=False),
        store=ArtifactStore(root=tmp_path),
        now=NOW,
    )
    assert outcome.status is ResearchStatus.DISABLED
    assert "OPENAI_API_KEY" in (outcome.failure_reason or "")


# ---------------------------------------------------------------- persistence
def test_artifact_records_reproducibility_metadata_and_no_secret(tmp_path):
    payload, verdicts = _payload()
    store = ArtifactStore(root=tmp_path)
    run_research(
        payload,
        _actions(verdicts),
        settings=_settings(tmp_path),
        store=store,
        client=ResearchClient(_settings_stub(), openai_client=FakeOpenAI()),
        deterministic_report_hash="deadbeef",
        now=NOW,
    )
    body = json.loads(store.research_path("TEST", date(2026, 7, 16)).read_text())

    assert body["symbol"] == "TEST"
    assert body["model"] == "test-model"
    assert body["prompt_version"] == PROMPT_VERSION
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["payload_hash"] == payload.content_hash()
    assert body["deterministic_report_hash"] == "deadbeef"
    assert body["response_id"] == "resp_test_1"
    assert body["content_hash"]
    assert body["sources"] and body["validation"]

    raw = json.dumps(body).lower()
    for forbidden in ("api_key", "sk-", "authorization", "bearer "):
        assert forbidden not in raw, forbidden


def test_thesis_artifact_is_written_and_hashed(tmp_path):
    payload, verdicts = _payload()
    store = ArtifactStore(root=tmp_path)
    run_research(
        payload,
        _actions(verdicts),
        settings=_settings(tmp_path),
        store=store,
        client=ResearchClient(_settings_stub(), openai_client=FakeOpenAI()),
        now=NOW,
    )
    thesis = store.load_thesis("TEST")
    assert thesis is not None
    assert thesis["content_hash"]
    assert thesis["current_thesis"] == "base thesis"
    assert thesis["deterministic_actions"]


# --------------------------------------------------------------------- caching
def test_cache_key_covers_prompt_and_schema_versions():
    args = dict(
        symbol="X",
        as_of=date(2026, 8, 1),
        payload_hash="h",
        model="m",
        prompt_version="1.0.0",
        schema_version="1.0.0",
    )
    base = cache_key(**args)
    assert base != cache_key(**{**args, "prompt_version": "1.0.1"})
    assert base != cache_key(**{**args, "schema_version": "1.0.1"})
    assert base != cache_key(**{**args, "model": "other"})
    assert base != cache_key(**{**args, "payload_hash": "other"})


def test_second_run_is_served_from_cache_without_calling_the_api(tmp_path):
    payload, verdicts = _payload()
    store = ArtifactStore(root=tmp_path)
    settings = _settings(tmp_path)
    fake = FakeOpenAI()
    client = ResearchClient(_settings_stub(), openai_client=fake)

    run_research(
        payload, _actions(verdicts), settings=settings, store=store, client=client, now=NOW
    )
    calls_after_first = len(fake.create_calls)

    second = run_research(
        payload,
        _actions(verdicts),
        settings=settings,
        store=store,
        client=client,
        now=NOW + timedelta(hours=1),
    )
    assert second.status is ResearchStatus.CACHED
    assert second.from_cache and second.available
    assert len(fake.create_calls) == calls_after_first, "cache hit must make no API call"


def test_refresh_flag_forces_a_new_call(tmp_path):
    payload, verdicts = _payload()
    store = ArtifactStore(root=tmp_path)
    settings = _settings(tmp_path)
    fake = FakeOpenAI()
    client = ResearchClient(_settings_stub(), openai_client=fake)

    run_research(
        payload, _actions(verdicts), settings=settings, store=store, client=client, now=NOW
    )
    run_research(
        payload,
        _actions(verdicts),
        settings=settings,
        store=store,
        client=client,
        refresh=True,
        now=NOW + timedelta(hours=1),
    )
    assert len(fake.create_calls) == 2


def test_stale_cache_is_not_reused(tmp_path):
    payload, verdicts = _payload()
    store = ArtifactStore(root=tmp_path)
    settings = _settings(tmp_path, freshness_hours=6)
    fake = FakeOpenAI()
    client = ResearchClient(_settings_stub(), openai_client=fake)

    run_research(
        payload, _actions(verdicts), settings=settings, store=store, client=client, now=NOW
    )
    later = run_research(
        payload,
        _actions(verdicts),
        settings=settings,
        store=store,
        client=client,
        now=NOW + timedelta(hours=48),
    )
    assert later.status is ResearchStatus.OK
    assert len(fake.create_calls) == 2


def test_freshness_rejects_a_mismatched_key_or_a_failed_artifact():
    artifact = {"cache_key": "k", "status": "OK", "generated_at": NOW.isoformat()}
    assert is_fresh(artifact, key="k", freshness_hours=24, now=NOW)
    assert not is_fresh(artifact, key="other", freshness_hours=24, now=NOW)
    assert not is_fresh({**artifact, "status": "FAILED"}, key="k", freshness_hours=24, now=NOW)
    assert not is_fresh(
        {**artifact, "generated_at": "nonsense"}, key="k", freshness_hours=24, now=NOW
    )


def test_a_changed_payload_invalidates_the_cache(tmp_path):
    from decimal import Decimal

    store = ArtifactStore(root=tmp_path)
    settings = _settings(tmp_path)
    fake = FakeOpenAI()
    client = ResearchClient(_settings_stub(), openai_client=fake)

    payload, verdicts = _payload()
    run_research(
        payload, _actions(verdicts), settings=settings, store=store, client=client, now=NOW
    )

    pos2 = _pos(market_price=Decimal("999"))
    evidence = [ev("ret_21d")]
    cons = _cons()
    v2 = decide(evidence, cons, pos2)
    payload2 = build_payload(pos2, evidence, cons, v2)

    run_research(
        payload2,
        _actions(v2),
        settings=settings,
        store=store,
        client=client,
        now=NOW + timedelta(minutes=5),
    )
    assert len(fake.create_calls) == 2, "different numbers must trigger fresh research"


# ------------------------------------------------------------- thesis history
def test_first_thesis_has_no_previous_and_reports_nothing_changed():
    result = make_result()
    thesis = build_thesis("TEST", date(2026, 8, 1), result, {"1m": "HOLD"}, None)
    diff = diff_thesis(None, thesis)
    assert not diff.has_previous
    assert not diff.any_change


def test_diff_detects_a_changed_research_view_and_action():
    old = build_thesis("TEST", date(2026, 8, 1), make_result(llm_view="HOLD"), {"1m": "HOLD"}, None)
    new = build_thesis("TEST", date(2026, 8, 8), make_result(llm_view="TRIM"), {"1m": "TRIM"}, old)
    diff = diff_thesis(old, new)

    assert diff.view_changed
    assert diff.previous_view == "HOLD" and diff.current_view == "TRIM"
    assert "1m: HOLD -> TRIM" in diff.action_changes
    assert diff.any_change


def test_diff_detects_new_and_dropped_catalysts():
    from mip.research_assistant.contracts import Catalyst, CatalystType, Directionality

    def cat(name):
        return Catalyst(
            name=name,
            date="2026-09-01",
            date_is_verified=True,
            type=CatalystType.PRODUCT,
            directionality=Directionality.UNCLEAR,
            potential_impact="x",
            why_it_matters="y",
            source_ids=[],
        )

    old = build_thesis("T", date(2026, 8, 1), make_result(catalysts=[cat("A")]), {}, None)
    new = build_thesis("T", date(2026, 8, 8), make_result(catalysts=[cat("B")]), {}, old)
    diff = diff_thesis(old, new)
    assert diff.new_catalysts == ["B"] and diff.dropped_catalysts == ["A"]


def test_thesis_history_is_appended_and_bounded():
    thesis = None
    for _ in range(30):
        thesis = build_thesis("T", date(2026, 8, 1), make_result(), {"1m": "HOLD"}, thesis)
    assert len(thesis["history"]) == 24


def test_thesis_hash_ignores_history_and_timestamp():
    a = build_thesis("T", date(2026, 8, 1), make_result(), {"1m": "HOLD"}, None)
    b = build_thesis("T", date(2026, 8, 1), make_result(), {"1m": "HOLD"}, a)
    assert a["content_hash"] == b["content_hash"], "unchanged substance means unchanged hash"


# -------------------------------------------------------- portfolio synthesis
def test_portfolio_summary_is_compact_and_carries_no_web_content(tmp_path):
    payload, verdicts = _payload()
    outcome = run_research(
        payload,
        _actions(verdicts),
        settings=_settings(tmp_path),
        store=ArtifactStore(root=tmp_path),
        client=ResearchClient(_settings_stub(), openai_client=FakeOpenAI()),
        now=NOW,
    )
    summary = summarise_for_portfolio(outcome, payload)

    assert summary["symbol"] == "TEST"
    assert summary["llm_research_view"] == "HOLD"
    assert len(summary["what_matters_now"]) <= 3
    raw = json.dumps(summary)
    assert "http" not in raw, "summaries must not carry sources or web content"
    assert len(raw) < 4000, "summaries must stay compact for the synthesis call"


def test_portfolio_summary_of_a_failed_holding_says_so(tmp_path):
    payload, verdicts = _payload()
    outcome = run_research(
        payload,
        _actions(verdicts),
        settings=_settings(tmp_path, enabled=False),
        store=ArtifactStore(root=tmp_path),
        now=NOW,
    )
    summary = summarise_for_portfolio(outcome, payload)
    assert summary["research_available"] is False
    assert summary["research_unavailable_reason"]


def test_portfolio_synthesis_returns_an_error_rather_than_raising(tmp_path):
    result, usage, error = run_portfolio_synthesis(
        date(2026, 8, 21),
        [],
        settings=_settings(tmp_path),
        store=ArtifactStore(root=tmp_path),
        now=NOW,
    )
    assert result is None and usage is None
    assert "no per-holding research summaries" in (error or "")


def test_portfolio_synthesis_writes_an_artifact(tmp_path):
    from mip.research_assistant.contracts import PortfolioResearchResult

    portfolio_result = PortfolioResearchResult(
        as_of="2026-08-21",
        highest_priority_reviews=[],
        clustered_risks=[],
        shared_macro_exposures=[],
        upcoming_catalyst_clusters=[],
        cross_position_contradictions=[],
        quant_qual_disagreements=[],
        large_weights_deteriorating=[],
        attractive_but_size_constrained=[],
        summary="all quiet",
        limitations=["small sample"],
    )
    fake = FakeOpenAI(parse_response=fake_parse_response(portfolio_result))
    store = ArtifactStore(root=tmp_path)
    result, usage, error = run_portfolio_synthesis(
        date(2026, 8, 21),
        [{"symbol": "TEST"}],
        settings=_settings(tmp_path),
        store=store,
        client=ResearchClient(_settings_stub(), openai_client=fake),
        now=NOW,
    )
    assert error is None and result is not None and usage is not None
    body = json.loads(store.portfolio_path(date(2026, 8, 21)).read_text())
    assert body["summaries_count"] == 1 and body["content_hash"]
