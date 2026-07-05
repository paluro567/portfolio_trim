"""Repository for macro_series (header) and macro_observations (detail).

observations_available_as_of() is the publication-lag gate (D13): every
downstream consumer — feature calculators, the future research engine —
must read observations through it, never with a bare obs_date filter.
"""

from datetime import date
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from mip.core.logging import get_logger
from mip.domain.models import MacroObservation, MacroSeries
from mip.reference.macro_catalog import SeriesDef

logger = get_logger(__name__)


class MacroRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- series headers ----------------------------------------------------

    def get_series(self, provider: str, provider_code: str) -> MacroSeries | None:
        return self._session.scalar(
            select(MacroSeries).where(
                MacroSeries.provider == provider,
                MacroSeries.provider_code == provider_code,
            )
        )

    def sync_series(self, provider: str, definition: SeriesDef) -> MacroSeries:
        """Create or update the header row from the catalog (idempotent).
        Header metadata is catalog-owned: catalog edits propagate here."""
        series = self.get_series(provider, definition.code)
        if series is None:
            series = MacroSeries(
                provider=provider,
                provider_code=definition.code,
                name=definition.name,
                frequency=definition.frequency,
                units=definition.units,
                seasonally_adjusted=definition.seasonally_adjusted,
                publication_lag_days=definition.publication_lag_days,
            )
            self._session.add(series)
            self._session.flush()
            return series

        changes = {
            "name": definition.name,
            "frequency": definition.frequency,
            "units": definition.units,
            "seasonally_adjusted": definition.seasonally_adjusted,
            "publication_lag_days": definition.publication_lag_days,
        }
        for attr, new in changes.items():
            old = getattr(series, attr)
            if old != new:
                logger.info(
                    "macro.series_metadata_changed",
                    code=definition.code,
                    field=attr,
                    old=old,
                    new=new,
                )
                setattr(series, attr, new)
        self._session.flush()
        return series

    def list_series(self) -> list[MacroSeries]:
        return list(self._session.scalars(select(MacroSeries).order_by(MacroSeries.provider_code)))

    # -- observations --------------------------------------------------------

    def latest_obs_date(self, series_id: int) -> date | None:
        return self._session.scalar(
            select(func.max(MacroObservation.obs_date)).where(
                MacroObservation.series_id == series_id
            )
        )

    def get_observations(self, series_id: int, dates: list[date]) -> dict[date, MacroObservation]:
        if not dates:
            return {}
        rows = self._session.scalars(
            select(MacroObservation).where(
                MacroObservation.series_id == series_id,
                MacroObservation.obs_date.in_(dates),
            )
        )
        return {row.obs_date: row for row in rows}

    def recent_observations(self, series_id: int, limit: int = 12) -> list[MacroObservation]:
        return list(
            self._session.scalars(
                select(MacroObservation)
                .where(MacroObservation.series_id == series_id)
                .order_by(MacroObservation.obs_date.desc())
                .limit(limit)
            )
        )

    def insert_observations(self, rows: list[dict[str, Any]], run_id: int) -> int:
        if not rows:
            return 0
        stmt = (
            pg_insert(MacroObservation)
            .values([{**row, "ingestion_run_id": run_id} for row in rows])
            .on_conflict_do_nothing(index_elements=["series_id", "obs_date"])
            .returning(MacroObservation.obs_date)
        )
        return len(self._session.execute(stmt).fetchall())

    def apply_revision(self, series_id: int, obs_date: date, value: Any, run_id: int) -> None:
        self._session.execute(
            update(MacroObservation)
            .where(
                MacroObservation.series_id == series_id,
                MacroObservation.obs_date == obs_date,
            )
            .values(value=value, last_updated_at=func.now(), ingestion_run_id=run_id)
        )

    # -- publication-lag gate (D13) -------------------------------------------

    def observations_available_as_of(self, series_id: int, as_of: date) -> list[MacroObservation]:
        """Observations knowable on `as_of`: obs_date + publication lag has
        elapsed. THE read path for all downstream consumers."""
        published = MacroObservation.obs_date + func.make_interval(
            0, 0, 0, MacroSeries.publication_lag_days  # years, months, weeks, DAYS
        )
        return list(
            self._session.scalars(
                select(MacroObservation)
                .join(MacroSeries, MacroSeries.id == MacroObservation.series_id)
                .where(MacroObservation.series_id == series_id, published <= as_of)
                .order_by(MacroObservation.obs_date)
            )
        )
