"""Qualitative research and synthesis layer.

This package adds CURRENT, CITED, QUALITATIVE research on top of the
deterministic quantitative product in ``mip.product``. It is strictly
additive:

* it never computes a price, return, percentile, weight, P&L or feature;
* it never produces or overrides a deterministic horizon verdict;
* it never emits a numeric probability or an expected return.

Everything numeric in a rendered brief comes from ``mip.product`` objects that
this package receives as GIVEN FACTS and passes through unchanged. The
relationship to the product evidence boundary is documented in
``docs/RESEARCH_ASSISTANT.md``.

Import direction is one-way: ``mip.research_assistant`` may import from
``mip.product``; ``mip.product`` must never import from here. A test enforces
this (``tests/unit/test_research_boundary.py``).
"""

from mip.research_assistant.config import ResearchSettings, load_research_settings

__all__ = ["ResearchSettings", "load_research_settings"]

# Bumped whenever the prompt text or the response schema changes in a way that
# invalidates cached research. Both are recorded in every persisted artifact.
PROMPT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
