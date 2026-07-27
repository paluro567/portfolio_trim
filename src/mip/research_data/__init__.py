"""Phase 2A — native survivorship-clean outcome foundation & migration guardrails.

Everything keys on the permanent ``security_id`` (never ticker / instrument_id).
Delisted/inactive securities and terminal outcomes are preserved, never dropped;
legacy and native identity worlds can never be silently mixed (guardrails); every
research artifact carries explicit integrity/version stamps and traces to an
immutable experiment-run record. Nothing here touches production scoring.

Phase 2A establishes the native outcome and provenance foundation. It does NOT
migrate production feature families (Phase 2B) or prove the Trim Score predicts.
"""

from mip.research_data.bridge import (
    BridgeIngestor,
    BridgeRepository,
    BridgeStats,
    SourceMapping,
)
from mip.research_data.experiments import ExperimentProvenance
from mip.research_data.guardrails import (
    DataVersionMismatchError,
    IntegrityStamp,
    LegacyTickerJoinError,
    MissingIntegrityStampError,
    MixedIdentityWorldError,
    ResearchIntegrityError,
    SnapshotChecksumMismatchError,
    UnexplainedDivergenceError,
    UniverseVersionMismatchError,
    assert_no_unexplained_divergence,
    assert_single_snapshot,
    assert_universe_versions_match,
    assert_worlds_joinable,
    guard_stamp,
)
from mip.research_data.ingest import OutcomeIngestor, OutcomeIngestStats
from mip.research_data.outcomes import (
    DailyReturnBuilder,
    ForwardOutcomeBuilder,
    ForwardStats,
    rebuild_checksum,
)
from mip.research_data.parity import (
    ComputationParity,
    DivergenceLedger,
    ParityCase,
)
from mip.research_data.source import (
    APPROVED_PROVIDERS,
    FixtureOutcomeSource,
    OutcomeSource,
    SourceBenchmarkBar,
    SourceMarketSnapshot,
    SourcePriceBar,
    SourceTerminal,
    blocked_outcome_source,
)

__all__ = [
    "APPROVED_PROVIDERS",
    "BridgeIngestor",
    "BridgeRepository",
    "BridgeStats",
    "ComputationParity",
    "DailyReturnBuilder",
    "DataVersionMismatchError",
    "DivergenceLedger",
    "ExperimentProvenance",
    "FixtureOutcomeSource",
    "ForwardOutcomeBuilder",
    "ForwardStats",
    "IntegrityStamp",
    "LegacyTickerJoinError",
    "MissingIntegrityStampError",
    "MixedIdentityWorldError",
    "OutcomeIngestStats",
    "OutcomeIngestor",
    "OutcomeSource",
    "ParityCase",
    "ResearchIntegrityError",
    "SnapshotChecksumMismatchError",
    "SourceBenchmarkBar",
    "SourceMapping",
    "SourceMarketSnapshot",
    "SourcePriceBar",
    "SourceTerminal",
    "UnexplainedDivergenceError",
    "UniverseVersionMismatchError",
    "assert_no_unexplained_divergence",
    "assert_single_snapshot",
    "assert_universe_versions_match",
    "assert_worlds_joinable",
    "blocked_outcome_source",
    "guard_stamp",
    "rebuild_checksum",
]
