"""Repository for feature definitions and the two feature stores.

- sync_definition(): (name, version) is immutable — same version with
  different params is a hard error demanding a version bump (D6).
- upserts guard with IS DISTINCT FROM so unchanged rows keep computed_at
  (idempotent rebuilds, byte-for-byte).
- get_matrix(): date x symbol x feature for model training; market
  features broadcast across symbols.
"""

from datetime import date
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import FeatureScope
from mip.domain.models import (
    FeatureDefinition,
    FeatureStoreDaily,
    FeatureStoreMarketDaily,
    Instrument,
)
from mip.features.base import FeatureSpec

_VALUE_QUANTUM = Decimal("0.00000001")  # NUMERIC(20,8)


def to_feature_value(value: float) -> Decimal:
    return Decimal(str(round(float(value), 8))).quantize(_VALUE_QUANTUM)


class FeatureRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- definitions --------------------------------------------------------

    def sync_definition(self, spec: FeatureSpec) -> FeatureDefinition:
        existing = self._session.scalar(
            select(FeatureDefinition).where(
                FeatureDefinition.name == spec.name,
                FeatureDefinition.version == spec.version,
            )
        )
        params = {k: v for k, v in spec.params.items()}
        if existing is not None:
            if (existing.params or {}) != params or existing.scope != spec.scope:
                raise ConfigurationError(
                    f"feature {spec.name} v{spec.version} already exists with different "
                    f"params/scope — bump the version instead of redefining "
                    f"(stored: {existing.params}, registry: {params})"
                )
            if existing.description != spec.description:
                existing.description = spec.description  # prose may improve
            return existing
        definition = FeatureDefinition(
            name=spec.name,
            version=spec.version,
            scope=spec.scope,
            description=spec.description,
            params=params,
            uses_adjusted_prices=spec.uses_adjusted_prices,
        )
        self._session.add(definition)
        self._session.flush()
        return definition

    def list_definitions(self) -> list[FeatureDefinition]:
        return list(
            self._session.scalars(
                select(FeatureDefinition).order_by(
                    FeatureDefinition.name, FeatureDefinition.version
                )
            )
        )

    def get_definition(self, name: str, version: int | None = None) -> FeatureDefinition | None:
        stmt = select(FeatureDefinition).where(FeatureDefinition.name == name)
        if version is None:
            stmt = stmt.order_by(FeatureDefinition.version.desc()).limit(1)
        else:
            stmt = stmt.where(FeatureDefinition.version == version)
        return self._session.scalar(stmt)

    # -- partitions ------------------------------------------------------------

    def ensure_partitions(self, start_year: int, end_year: int) -> None:
        for table in ("feature_store_daily", "feature_store_market_daily"):
            for year in range(start_year, end_year + 1):
                self._session.execute(
                    text(
                        f"CREATE TABLE IF NOT EXISTS {table}_y{year} "
                        f"PARTITION OF {table} "
                        f"FOR VALUES FROM ('{year}-01-01') TO ('{year + 1}-01-01')"
                    )
                )

    # -- cursors -----------------------------------------------------------------

    def latest_instrument_date(self, instrument_id: int, feature_ids: list[int]) -> date | None:
        if not feature_ids:
            return None
        return self._session.scalar(
            select(func.max(FeatureStoreDaily.feature_date)).where(
                FeatureStoreDaily.instrument_id == instrument_id,
                FeatureStoreDaily.feature_id.in_(feature_ids),
            )
        )

    def latest_market_date(self, feature_ids: list[int]) -> date | None:
        if not feature_ids:
            return None
        return self._session.scalar(
            select(func.max(FeatureStoreMarketDaily.feature_date)).where(
                FeatureStoreMarketDaily.feature_id.in_(feature_ids)
            )
        )

    # -- writes ---------------------------------------------------------------------

    def upsert_instrument_values(self, rows: list[dict[str, Any]]) -> int:
        return self._upsert(
            FeatureStoreDaily, ["instrument_id", "feature_date", "feature_id"], rows
        )

    def upsert_market_values(self, rows: list[dict[str, Any]]) -> int:
        return self._upsert(FeatureStoreMarketDaily, ["feature_date", "feature_id"], rows)

    def _upsert(self, model: type, keys: list[str], rows: list[dict[str, Any]]) -> int:
        affected = 0
        for start in range(0, len(rows), 5000):
            chunk = rows[start : start + 5000]
            stmt = pg_insert(model).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=keys,
                set_={"value": stmt.excluded.value, "computed_at": func.now()},
                where=(model.value.is_distinct_from(stmt.excluded.value)),
            ).returning(model.feature_id)
            affected += len(self._session.execute(stmt).fetchall())
        return affected

    # -- matrix builder (date x symbol x feature) --------------------------------------

    def get_matrix(
        self,
        feature_names: list[str],
        symbols: list[str],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        definitions = [self.get_definition(name) for name in feature_names]
        missing = [n for n, d in zip(feature_names, definitions, strict=True) if d is None]
        if missing:
            raise ConfigurationError(f"unknown features: {missing}")

        instrument_rows = self._session.execute(
            select(Instrument.id, Instrument.symbol).where(Instrument.symbol.in_(symbols))
        ).all()
        id_to_symbol = dict(instrument_rows)
        unknown = set(symbols) - set(id_to_symbol.values())
        if unknown:
            raise ConfigurationError(f"unknown symbols: {sorted(unknown)}")

        by_scope: dict[FeatureScope, dict[int, str]] = {
            FeatureScope.INSTRUMENT: {},
            FeatureScope.MARKET: {},
        }
        for definition in definitions:
            by_scope[definition.scope][definition.id] = definition.name

        index = pd.MultiIndex.from_tuples([], names=["date", "symbol"])
        matrix = pd.DataFrame(index=index)

        if by_scope[FeatureScope.INSTRUMENT]:
            rows = self._session.execute(
                select(
                    FeatureStoreDaily.feature_date,
                    FeatureStoreDaily.instrument_id,
                    FeatureStoreDaily.feature_id,
                    FeatureStoreDaily.value,
                ).where(
                    FeatureStoreDaily.instrument_id.in_(id_to_symbol),
                    FeatureStoreDaily.feature_id.in_(by_scope[FeatureScope.INSTRUMENT]),
                    FeatureStoreDaily.feature_date.between(start, end),
                )
            ).all()
            if rows:
                frame = pd.DataFrame(rows, columns=["date", "instrument_id", "feature_id", "value"])
                frame["symbol"] = frame["instrument_id"].map(id_to_symbol)
                frame["feature"] = frame["feature_id"].map(by_scope[FeatureScope.INSTRUMENT])
                frame["value"] = frame["value"].astype(float)
                matrix = frame.pivot_table(
                    index=["date", "symbol"], columns="feature", values="value"
                )

        if by_scope[FeatureScope.MARKET]:
            rows = self._session.execute(
                select(
                    FeatureStoreMarketDaily.feature_date,
                    FeatureStoreMarketDaily.feature_id,
                    FeatureStoreMarketDaily.value,
                ).where(
                    FeatureStoreMarketDaily.feature_id.in_(by_scope[FeatureScope.MARKET]),
                    FeatureStoreMarketDaily.feature_date.between(start, end),
                )
            ).all()
            if rows:
                market = pd.DataFrame(rows, columns=["date", "feature_id", "value"])
                market["feature"] = market["feature_id"].map(by_scope[FeatureScope.MARKET])
                market["value"] = market["value"].astype(float)
                wide = market.pivot_table(index="date", columns="feature", values="value")
                if matrix.empty:
                    # market-only request: broadcast over requested symbols
                    index = pd.MultiIndex.from_product(
                        [wide.index, sorted(id_to_symbol.values())],
                        names=["date", "symbol"],
                    )
                    matrix = pd.DataFrame(index=index)
                dates = matrix.index.get_level_values("date")
                for column in wide.columns:
                    matrix[column] = wide[column].reindex(dates).values

        matrix.columns.name = None
        return matrix.sort_index()
