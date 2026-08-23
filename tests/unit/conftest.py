"""Unit-test isolation from real credentials.

The research layer resolves ``OPENAI_API_KEY`` from the environment and then
falls back to ``./.env``, because that is where the rest of the platform is
configured and where the documentation tells the owner to put it.

That fallback is correct for the application and dangerous for tests: a test
that deletes the environment variable to exercise the "no key" path would
otherwise still find the real key in ``.env``, construct a real client, and make
a billable network call. That happened once during development; this fixture
exists so it cannot happen again.

Every unit test therefore runs with the ``.env`` fallback neutralised and the
variable unset. A test that needs the layer to appear operational builds
``ResearchSettings`` directly and injects a fake OpenAI client — never a real
one.
"""

from __future__ import annotations

import pytest

from mip.research_assistant import config as research_config


@pytest.fixture(autouse=True)
def _no_real_credentials(monkeypatch):
    """Autouse: no unit test may reach a real API key by any route."""
    monkeypatch.setattr(research_config, "_dotenv", lambda _name: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
