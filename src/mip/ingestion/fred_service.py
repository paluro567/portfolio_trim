"""Macro ingestion service — the Phase 2 pattern applied to FRED series.

Shape per series: catalog lookup -> header sync -> cursor with
per-frequency revision overlap -> fetch (retry) -> validate -> archive ->
insert new -> diff overlap -> data_revisions + update -> staleness check.
Per-series failures are isolated (status=partial). Macro revisions reach
further back than price ticks, so the overlap window scales with the
series frequency rather than a fixed session count.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from mip.core.config import Settings
from mip.core.exceptions import MIPError
from mip.core.logging import get_logger
from mip.core.retry import retry
from mip.domain.enums import IssueSeverity, RunStatus, RunType
from mip.domain.models import IngestionRun
from mip.ingestion.archive import RawDataArchive
from mip.ingestion.revisions import to_decimal
from mip.ingestion.validation import RULE_STALE_SERIES, validate_macro
from mip.providers.base import MacroProvider
from mip.reference.macro_catalog import MacroCatalog, SeriesDef
from mip.repositories.ingestion_runs import IngestionRunRepository
from mip.repositories.macro import MacroRepository
from mip.repositories.quality import QualityRepository

logger = get_logger(__name__)

ENTITY_TYPE = "macro_obs"

# Revision-detection overlap per frequency (reference periods, not days):
# macro values (CPI, payrolls, GDP) are revised for months after release.
_OVERLAP = {
    "D": timedelta(days=14),
    "W": timedelta(weeks=8),
    "M": timedelta(days=185),  # ~6 months
    "Q": timedelta(days=460),  # ~5 quarters
}

# A series is stale when today - last_obs exceeds lag + 3 periods.
_PERIOD_DAYS = {"D": 1, "W": 7, "M": 31, "Q": 92}


@dataclass
class SeriesOutcome:
    code: str
    status: str = "ok"  # 'ok' | 'failed'
    inserted: int = 0
    updated: int = 0
    quarantined: int = 0
    warnings: int = 0
    revisions: int = 0
    error: str | None = None


class MacroIngestionService:
    def __init__(
        self,
        session: Session,
        provider: MacroProvider,
        archive: RawDataArchive,
        settings: Settings,
        catalog: MacroCatalog,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._session = session
        self._provider = provider
        self._archive = archive
        self._settings = settings
        self._catalog = catalog
        self._today = today
        self._runs = IngestionRunRepository(session)
        self._macro = MacroRepository(session)
        self._quality = QualityRepository(session)
        self._fetch = retry(
            max_attempts=settings.retry_max_attempts,
            backoff_seconds=settings.retry_backoff_seconds,
            sleep=sleep,
        )(provider.fetch_series)

    def ingest(
        self, codes: Sequence[str] | None = None
    ) -> tuple[IngestionRun, list[SeriesOutcome]]:
        requested = list(codes) if codes else self._catalog.codes
        run = self._runs.start(RunType.MACRO, self._provider.name, ",".join(requested))
        logger.info("macro.run_started", run_id=run.id, series=len(requested))

        outcomes: list[SeriesOutcome] = []
        for code in requested:
            definition = self._catalog.get(code)
            if definition is None:
                # Unknown codes fail loudly: the catalog is the only source
                # of series (and of the mandatory publication lag).
                outcomes.append(
                    SeriesOutcome(
                        code=code,
                        status="failed",
                        error=f"series {code!r} not in fred_series.yaml",
                    )
                )
                continue
            try:
                outcomes.append(self._ingest_series(run, definition))
            except MIPError as exc:
                logger.error("macro.series_failed", run_id=run.id, code=code, error=str(exc))
                outcomes.append(SeriesOutcome(code=code, status="failed", error=str(exc)))

        failed = {o.code: o.error for o in outcomes if o.status == "failed"}
        if not outcomes or len(failed) == len(outcomes):
            status = RunStatus.FAILED
        elif failed:
            status = RunStatus.PARTIAL
        else:
            status = RunStatus.SUCCESS

        self._runs.complete(
            run,
            status=status,
            rows_inserted=sum(o.inserted for o in outcomes),
            rows_updated=sum(o.updated for o in outcomes),
            archive_path=str(self._archive.root / "macro"),
            error_detail={"failed_series": failed} if failed else None,
        )
        logger.info(
            "macro.run_completed",
            run_id=run.id,
            status=status.value,
            inserted=run.rows_inserted,
            updated=run.rows_updated,
            failed=len(failed),
        )
        return run, outcomes

    # -- per-series flow -------------------------------------------------------

    def _ingest_series(self, run: IngestionRun, definition: SeriesDef) -> SeriesOutcome:
        code = definition.code
        outcome = SeriesOutcome(code=code)
        series = self._macro.sync_series(self._provider.name, definition)

        cursor = self._macro.latest_obs_date(series.id)
        if cursor is None:
            fetch_start = self._settings.history_start_date
        else:
            fetch_start = cursor - _OVERLAP[definition.frequency]
        fetch_end = self._today()

        frame = self._fetch(code, fetch_start, fetch_end)
        if not frame.empty:
            frame = frame[
                (frame["obs_date"] >= fetch_start) & (frame["obs_date"] <= fetch_end)
            ].reset_index(drop=True)

        report = validate_macro(
            frame,
            frequency=definition.frequency,
            accepted=self._quality.accepted_row_rules(ENTITY_TYPE, f"{code}/"),
            min_value=definition.min_value,
            max_value=definition.max_value,
        )

        for finding in report.row_findings:
            self._quality.add_issue(
                run.id,
                ENTITY_TYPE,
                f"{code}/{finding.entity_date}",
                finding.rule,
                finding.severity,
                finding.observed,
            )
            if finding.severity is IssueSeverity.ERROR:
                outcome.quarantined += 1
            else:
                outcome.warnings += 1
        for finding in report.frame_findings:
            self._quality.add_issue(
                run.id,
                ENTITY_TYPE,
                f"{code}/{fetch_start}..{fetch_end}",
                finding.rule,
                finding.severity,
                finding.observed,
                details=dict(finding.detail),
            )
            outcome.warnings += 1

        if not report.valid.empty:
            self._archive.write(
                "macro",
                code,
                report.valid,
                report.valid["obs_date"].iloc[0],
                report.valid["obs_date"].iloc[-1],
                run.id,
            )
        if not report.rejected.empty:
            self._archive.write(
                "macro",
                code,
                report.rejected,
                report.rejected["obs_date"].iloc[0],
                report.rejected["obs_date"].iloc[-1],
                run.id,
                rejected=True,
            )

        outcome.inserted = self._macro.insert_observations(
            self._obs_rows(series.id, report.valid), run.id
        )

        # Diff re-fetched overlap against stored values (D12).
        if cursor is not None and not report.valid.empty:
            overlap = report.valid[report.valid["obs_date"] <= cursor]
            stored = self._macro.get_observations(series.id, list(overlap["obs_date"]))
            for _, incoming in overlap.iterrows():
                row = stored.get(incoming["obs_date"])
                if row is None:
                    continue  # backfill, already inserted above
                old = row.value.quantize(Decimal("0.000001")) if row.value is not None else None
                new = to_decimal(incoming["value"])  # already at storage precision
                if old == new:
                    continue
                self._quality.record_revision(
                    "macro_observations",
                    f"{code}/{row.obs_date}",
                    "value",
                    str(row.value) if row.value is not None else None,
                    str(new) if new is not None else None,
                    run.id,
                )
                self._macro.apply_revision(series.id, row.obs_date, new, run.id)
                outcome.updated += 1
                outcome.revisions += 1

        # staleness: silence beyond lag + 3 reference periods is a broken feed
        last = self._macro.latest_obs_date(series.id)
        if last is not None:
            allowance = definition.publication_lag_days + 3 * _PERIOD_DAYS[definition.frequency]
            silent_days = (self._today() - last).days
            if silent_days > allowance:
                self._quality.add_issue(
                    run.id,
                    ENTITY_TYPE,
                    f"{code}/{last}",
                    RULE_STALE_SERIES,
                    IssueSeverity.WARNING,
                    f"no observation for {silent_days} days (allowance {allowance})",
                )
                outcome.warnings += 1

        logger.info(
            "macro.series_done",
            run_id=run.id,
            code=code,
            inserted=outcome.inserted,
            updated=outcome.updated,
            quarantined=outcome.quarantined,
            revisions=outcome.revisions,
        )
        return outcome

    @staticmethod
    def _obs_rows(series_id: int, frame: pd.DataFrame) -> list[dict[str, Any]]:
        return [
            {
                "series_id": series_id,
                "obs_date": r["obs_date"],
                "value": to_decimal(r["value"]),  # NaN -> NULL, never zero
            }
            for _, r in frame.iterrows()
        ]
