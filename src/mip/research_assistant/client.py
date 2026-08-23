"""OpenAI Responses API client.

Two calls per holding:

1. **Research call** — ``responses.create`` with the built-in ``web_search``
   tool and ``include=["web_search_call.action.sources"]``. Produces prose plus
   live ``url_citation`` annotations and the tool's own source list.
2. **Extraction call** — ``responses.parse`` with ``text_format`` set to the
   Pydantic contract, no tools. Converts the prose into the strict object.

Splitting them is not a stylistic choice: annotations come back empty when
structured outputs and web search are combined in one call, and empty
annotations would leave nothing to validate citations against.

The API key is read at call time and never stored on an object, logged, or
included in any artifact.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

from mip.research_assistant.config import ResearchSettings, read_api_key

T = TypeVar("T", bound=BaseModel)


class ResearchUnavailableError(RuntimeError):
    """The layer could not produce research. Always caught by the orchestrator."""


@dataclass(slots=True)
class CallUsage:
    """Per-call cost observability. Never affects correctness."""

    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None
    web_search_calls: int = 0
    elapsed_seconds: float = 0.0
    response_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "input_tokens": self.input_tokens,
            "model": self.model,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "response_id": self.response_id,
            "total_tokens": self.total_tokens,
            "web_search_calls": self.web_search_calls,
        }

    def __add__(self, other: CallUsage) -> CallUsage:
        def _add(a: int | None, b: int | None) -> int | None:
            if a is None and b is None:
                return None
            return (a or 0) + (b or 0)

        return CallUsage(
            model=self.model,
            input_tokens=_add(self.input_tokens, other.input_tokens),
            output_tokens=_add(self.output_tokens, other.output_tokens),
            total_tokens=_add(self.total_tokens, other.total_tokens),
            reasoning_tokens=_add(self.reasoning_tokens, other.reasoning_tokens),
            web_search_calls=self.web_search_calls + other.web_search_calls,
            elapsed_seconds=self.elapsed_seconds + other.elapsed_seconds,
            response_id=self.response_id or other.response_id,
        )


@dataclass(slots=True)
class ResearchCallResult:
    text: str
    raw_sources: list[dict[str, Any]] = field(default_factory=list)
    usage: CallUsage | None = None


# ------------------------------------------------------------- response readers
def _get(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field from an SDK object or a plain dict, whichever we were given."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _response_text(response: Any) -> str:
    text = _get(response, "output_text")
    if isinstance(text, str) and text.strip():
        return text
    chunks: list[str] = []
    for item in _get(response, "output", []) or []:
        if _get(item, "type") != "message":
            continue
        for part in _get(item, "content", []) or []:
            value = _get(part, "text")
            if isinstance(value, str):
                chunks.append(value)
    return "\n".join(chunks)


def _refusal(response: Any) -> str | None:
    for item in _get(response, "output", []) or []:
        if _get(item, "type") != "message":
            continue
        for part in _get(item, "content", []) or []:
            if _get(part, "type") == "refusal":
                return _get(part, "refusal") or "model refused"
    return None


def collect_sources(response: Any) -> list[dict[str, Any]]:
    """Every source the tool actually used, plus every inline citation.

    Both channels are read because they can disagree: the tool's source list is
    what was retrieved, annotations are what the text actually cites. The union
    is the citable catalogue.
    """
    found: list[dict[str, Any]] = []

    def _add(url: Any, title: Any = None, published: Any = None) -> None:
        if isinstance(url, str) and url.strip():
            found.append(
                {
                    "url": url.strip(),
                    "title": title if isinstance(title, str) else None,
                    "published_date": published if isinstance(published, str) else None,
                }
            )

    for item in _get(response, "output", []) or []:
        kind = _get(item, "type")
        if kind == "web_search_call":
            action = _get(item, "action")
            for src in _get(action, "sources", []) or []:
                _add(_get(src, "url"), _get(src, "title"), _get(src, "published_date"))
        elif kind == "message":
            for part in _get(item, "content", []) or []:
                for ann in _get(part, "annotations", []) or []:
                    if _get(ann, "type") == "url_citation":
                        _add(_get(ann, "url"), _get(ann, "title"), _get(ann, "published_date"))
    return found


def _usage(response: Any, model: str, elapsed: float) -> CallUsage:
    raw = _get(response, "usage")
    details = _get(raw, "output_tokens_details")
    searches = sum(
        1
        for item in (_get(response, "output", []) or [])
        if _get(item, "type") == "web_search_call"
    )
    return CallUsage(
        model=model,
        input_tokens=_get(raw, "input_tokens"),
        output_tokens=_get(raw, "output_tokens"),
        total_tokens=_get(raw, "total_tokens"),
        reasoning_tokens=_get(details, "reasoning_tokens"),
        web_search_calls=searches,
        elapsed_seconds=elapsed,
        response_id=_get(response, "id"),
    )


# --------------------------------------------------------------------- the client
class ResearchClient:
    """Thin, testable wrapper. Inject ``openai_client`` in tests; never network."""

    def __init__(self, settings: ResearchSettings, openai_client: Any | None = None) -> None:
        self._settings = settings
        self._client = openai_client
        if self._client is None:
            key = read_api_key()
            if not key:
                raise ResearchUnavailableError("OPENAI_API_KEY is not set in the environment")
            from openai import OpenAI

            self._client = OpenAI(api_key=key, timeout=settings.timeout_seconds)

    @property
    def model(self) -> str:
        return self._settings.model

    def research(self, system: str, user: str) -> ResearchCallResult:
        """Call 1. Web search enabled; free-form prose out; annotations captured."""
        started = time.monotonic()
        try:
            response = self._client.responses.create(
                model=self._settings.model,
                instructions=system,
                input=user,
                tools=[
                    {
                        "type": "web_search",
                        "search_context_size": "high",
                    }
                ],
                include=["web_search_call.action.sources"],
                max_output_tokens=self._settings.max_output_tokens,
                store=False,
            )
        except Exception as exc:  # noqa: BLE001 - every failure degrades gracefully
            raise ResearchUnavailableError(
                f"research call failed: {type(exc).__name__}: {exc}"
            ) from exc
        elapsed = time.monotonic() - started

        refusal = _refusal(response)
        if refusal:
            raise ResearchUnavailableError(f"model refused the research call: {refusal}")

        text = _response_text(response)
        if not text.strip():
            raise ResearchUnavailableError("research call returned no text")

        return ResearchCallResult(
            text=text,
            raw_sources=collect_sources(response),
            usage=_usage(response, self._settings.model, elapsed),
        )

    def extract(self, system: str, user: str, schema: type[T]) -> tuple[T, CallUsage]:
        """Call 2. Strict structured output; no tools, no web access."""
        started = time.monotonic()
        try:
            response = self._client.responses.parse(
                model=self._settings.model,
                instructions=system,
                input=user,
                text_format=schema,
                max_output_tokens=self._settings.max_output_tokens,
                store=False,
            )
        except Exception as exc:  # noqa: BLE001
            raise ResearchUnavailableError(
                f"extraction call failed: {type(exc).__name__}: {exc}"
            ) from exc
        elapsed = time.monotonic() - started

        refusal = _refusal(response)
        if refusal:
            raise ResearchUnavailableError(f"model refused the extraction call: {refusal}")

        parsed = _get(response, "output_parsed")
        if parsed is None:
            raise ResearchUnavailableError("extraction call returned no parsed object")
        if not isinstance(parsed, schema):
            # Defensive: some SDK paths hand back a dict rather than the model.
            try:
                parsed = schema.model_validate(parsed)
            except Exception as exc:  # noqa: BLE001
                raise ResearchUnavailableError(
                    f"structured output failed validation: {exc}"
                ) from exc

        return parsed, _usage(response, self._settings.model, elapsed)
