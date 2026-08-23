"""Historical survivorship-clean data providers.

The ingestion half of the contract declared in ``mip.calibration.source``.
``mip.calibration`` READS clean data for a study; this package WRITES vendor data
into the platform's existing Phase-1/Phase-2A tables. Same eight logical
datasets, two ends.

Nothing here is vendor-specific by design: ``HistoricalDataProvider`` names
datasets and fields, never a provider. Sharadar is one implementation.

Status: SCAFFOLDING ONLY. No credentials are configured, no paid data has been
fetched, and ``blocked_historical_provider()`` raises rather than falling back
to the survivor-only legacy tables. See
``docs/data/SHARADAR_INGESTION_PLAN.md``.
"""

from mip.providers.historical.contract import (
    HistoricalDataProvider,
    SourceCorporateAction,
    SourceEarningsEvent,
    SourceFundamentalFact,
    blocked_historical_provider,
)

__all__ = [
    "HistoricalDataProvider",
    "SourceCorporateAction",
    "SourceEarningsEvent",
    "SourceFundamentalFact",
    "blocked_historical_provider",
]
