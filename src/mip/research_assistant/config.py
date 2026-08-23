"""Configuration for the research-assistant layer.

The API key is read from the environment and is NEVER stored on a settings
object that gets serialised, logged or hashed. ``ResearchSettings`` therefore
carries only a boolean saying whether a key was present; the key itself is
fetched on demand by the client at call time and never leaves this module or
the OpenAI SDK.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# The default model. Chosen because it is a current Responses-API model that
# supports the built-in web_search tool, structured outputs and strong
# reasoning, while balancing intelligence against cost across a 50+ holding
# portfolio run. `gpt-5.6-sol` is the higher-capability sibling and can be
# selected with OPENAI_MODEL when a single holding warrants it.
DEFAULT_MODEL = "gpt-5.6-terra"

_KEY_ENV = "OPENAI_API_KEY"


def _dotenv(name: str) -> str | None:
    """Read one value from ``./.env``.

    The rest of the platform configures itself from ``.env`` via
    pydantic-settings, so documenting "put OPENAI_API_KEY in .env" and then
    reading only ``os.environ`` was a defect: the key was invisible to this
    layer unless separately exported. The environment still wins; this is only
    consulted when the variable is unset.

    Deliberately minimal and never logged. Path is cwd-relative, matching the
    ``env_file=".env"`` behaviour in ``mip.core.config``.
    """
    path = Path(".env")
    if not path.is_file():
        return None
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() != name:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value or None
    except OSError:
        return None
    return None


def _env(name: str) -> str | None:
    """Environment first, then ``.env``."""
    raw = os.environ.get(name)
    if raw is not None and raw.strip() != "":
        return raw
    return _dotenv(name)


def _flag(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = _env(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    return max(minimum, value)


@dataclass(frozen=True, slots=True)
class ResearchSettings:
    """Everything the layer needs except the secret itself."""

    enabled: bool
    api_key_present: bool
    model: str
    max_search_calls: int
    freshness_hours: int
    timeout_seconds: int
    max_output_tokens: int
    research_root: Path

    @property
    def operational(self) -> bool:
        """True when a live call may actually be attempted."""
        return self.enabled and self.api_key_present

    def disabled_reason(self) -> str | None:
        if not self.enabled:
            return "MIP_OPENAI_ENABLED is false"
        if not self.api_key_present:
            return f"{_KEY_ENV} is not set in the environment"
        return None

    def to_dict(self) -> dict:
        """Serialisable form. Deliberately contains no secret."""
        return {
            "enabled": self.enabled,
            "freshness_hours": self.freshness_hours,
            "max_output_tokens": self.max_output_tokens,
            "max_search_calls": self.max_search_calls,
            "model": self.model,
            "research_root": str(self.research_root),
            "timeout_seconds": self.timeout_seconds,
        }


def load_research_settings() -> ResearchSettings:
    key = _env(_KEY_ENV) or ""
    return ResearchSettings(
        enabled=_flag("MIP_OPENAI_ENABLED", True),
        api_key_present=bool(key.strip()),
        model=(_env("OPENAI_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        max_search_calls=_int("MIP_OPENAI_MAX_SEARCH_CALLS", 8, minimum=1),
        freshness_hours=_int("MIP_OPENAI_RESEARCH_FRESHNESS_HOURS", 18, minimum=0),
        timeout_seconds=_int("MIP_OPENAI_TIMEOUT_SECONDS", 300, minimum=10),
        max_output_tokens=_int("MIP_OPENAI_MAX_OUTPUT_TOKENS", 16000, minimum=1000),
        research_root=Path(_env("MIP_RESEARCH_ROOT") or "data/investment_research"),
    )


def read_api_key() -> str | None:
    """Fetch the key at call time. Callers must never store or log the result."""
    key = (_env(_KEY_ENV) or "").strip()
    return key or None
