"""Historical Research Engine (Phase 6): conditional forward-return
studies over the feature store. Retrieval, aggregation, and statistical
summary only — no prediction models live here."""

from mip.research.engine import ResearchEngine, ResearchResult
from mip.research.metrics import ResearchMetric, summarize
from mip.research.query import (
    DEFAULT_HORIZONS,
    ResearchFilter,
    ResearchQuery,
    ResearchWindow,
    SampleMode,
    parse_filter,
)

__all__ = [
    "DEFAULT_HORIZONS",
    "ResearchEngine",
    "ResearchFilter",
    "ResearchMetric",
    "ResearchQuery",
    "ResearchResult",
    "ResearchWindow",
    "SampleMode",
    "parse_filter",
    "summarize",
]
