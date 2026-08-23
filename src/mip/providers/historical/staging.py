"""Staged ingestion: RAW → NORMALIZED → PIT_CLEAN → CALIBRATION_READY.

Each stage has one job, and the boundaries exist so a failure can be localised
to a stage rather than discovered as a strange number in a study months later.

The important boundary is NORMALIZED → PIT_CLEAN. Everything upstream is
mechanical translation; that step is where the as-of discipline is imposed, and
it is the only place a restated value can be excluded. A row that reaches
CALIBRATION_READY carries a guarantee: it was knowable on its stamped date.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Stage(StrEnum):
    RAW = "RAW"
    NORMALIZED = "NORMALIZED"
    PIT_CLEAN = "PIT_CLEAN"
    CALIBRATION_READY = "CALIBRATION_READY"


@dataclass(frozen=True, slots=True)
class StageSpec:
    stage: Stage
    input_of: str
    output_of: str
    validation: tuple[str, ...]
    idempotency: str
    lineage: str
    error_handling: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_handling": self.error_handling,
            "idempotency": self.idempotency,
            "input": self.input_of,
            "lineage": self.lineage,
            "output": self.output_of,
            "stage": self.stage.value,
            "validation": list(self.validation),
        }


STAGES: tuple[StageSpec, ...] = (
    StageSpec(
        stage=Stage.RAW,
        input_of="Vendor API responses / bulk exports, byte-for-byte.",
        output_of=(
            "Immutable archived payloads under the existing RawData/ convention, one "
            "file per (table, fetch window), with the vendor's own columns preserved."
        ),
        validation=(
            "payload is parseable",
            "row count recorded",
            "declared vendor schema version recorded",
        ),
        idempotency=(
            "Content-hashed filename. Re-fetching an identical window is a logged "
            "no-op; differing bytes for a window already archived is an error, not an "
            "overwrite — the same immutability rule the price archive already uses."
        ),
        lineage="ingestion_runs row, run_type='historical_backfill', with the fetch window.",
        error_handling="Partial fetch fails the window; no partial archive is written.",
    ),
    StageSpec(
        stage=Stage.NORMALIZED,
        input_of="RAW payloads.",
        output_of=(
            "Vendor-neutral DTOs (SourceSecurity, SourcePriceBar, SourceFundamentalFact, "
            "SourceEarningsEvent, SourceCorporateAction, SourceClassification, "
            "SourceConstituent, SourceDelisting). No vendor column names survive."
        ),
        validation=(
            "every record carries a non-empty source_security_id",
            "dates parse and are not in the future",
            "numeric fields are finite",
            "unmapped vendor columns are recorded, not silently dropped",
        ),
        idempotency="Pure function of the RAW payload; re-running yields identical DTOs.",
        lineage="Each DTO records the RAW content hash it came from.",
        error_handling=(
            "A record that cannot be normalised is QUARANTINED into the existing "
            "data_quality_issues ledger with its reason, never discarded."
        ),
    ),
    StageSpec(
        stage=Stage.PIT_CLEAN,
        input_of="NORMALIZED DTOs.",
        output_of=(
            "The platform's Phase-1/2A tables keyed on the permanent security_id: "
            "security_master, security_identifier_history, historical_classification, "
            "delisting_event, universe_membership, security_price_daily."
        ),
        validation=(
            "identity resolved on the vendor PERMANENT id, never on ticker",
            "as-reported dimensions only for fundamentals; restated dimensions rejected",
            "every fundamental fact carries a filing date <= its stamped availability",
            "every earnings event carries an observation date",
            "no record's availability date precedes its event date",
            "delisted securities have a delisting_event row",
        ),
        idempotency=(
            "Guarded upsert on the natural key, so a re-run converges rather than "
            "duplicating. Vendor `lastupdated` drives revision detection."
        ),
        lineage="source + source_security_id + ingestion_run_id + data_version on every row.",
        error_handling=(
            "Identity conflicts (missing permanent id, identifier overlap) are "
            "quarantined, matching the Phase-1 SecurityMasterIngestor behaviour. "
            "A restated-dimension record is rejected loudly, not downgraded."
        ),
    ),
    StageSpec(
        stage=Stage.CALIBRATION_READY,
        input_of="PIT_CLEAN tables.",
        output_of=(
            "A checksummed research_dataset_snapshot: the frozen (security, date) panel "
            "with forward outcomes and terminal outcomes for delisted names."
        ),
        validation=(
            "the calibration readiness gate passes",
            "no security disappears without a terminal outcome",
            "universe membership is dense across the study period",
            "snapshot checksum is reproducible from the same inputs",
        ),
        idempotency="Snapshot is content-addressed; an identical panel yields the same checksum.",
        lineage="Snapshot records universe_version, signal signature and data_version.",
        error_handling="Gate failure blocks snapshot creation; no partial panel is published.",
    ),
)


def stage_spec(stage: Stage) -> StageSpec:
    return next(s for s in STAGES if s.stage is stage)


def contract_summary() -> list[dict[str, Any]]:
    return [s.to_dict() for s in STAGES]
