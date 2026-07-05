"""Feature pipeline: DB -> contexts -> calculators (topo order) -> stores.

Reads ONLY from PostgreSQL (never providers). Market features are computed
first and become available as dependencies to instrument features.
Incremental runs recompute a trailing overlap window so upstream price
revisions propagate into features. All macro data enters contexts with
availability dates attached — the single publication-lag gate (D13)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.core.config import Settings
from mip.core.logging import get_logger
from mip.domain.enums import FeatureScope, InstrumentType, RunStatus, RunType
from mip.domain.models import (
    DailyPrice,
    IngestionRun,
    Instrument,
    MacroObservation,
    MacroSeries,
    TradingDay,
)
from mip.features.base import FeatureCalculator, FeatureContext
from mip.features.registry import build_registry, topological_order
from mip.repositories.features import FeatureRepository, to_feature_value
from mip.repositories.ingestion_runs import IngestionRunRepository
from mip.repositories.instruments import InstrumentRepository

logger = get_logger(__name__)

_PRICE_COLUMNS = ("open", "high", "low", "close", "adj_close")


@dataclass
class BuildStats:
    market_rows: int = 0
    instrument_rows: int = 0
    instruments: int = 0
    features: int = 0
    errors: dict[str, str] = field(default_factory=dict)


class FeaturePipeline:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        registry: list[FeatureCalculator] | None = None,
        today: callable = date.today,
    ) -> None:
        self._session = session
        self._settings = settings
        self._today = today
        self._repo = FeatureRepository(session)
        self._runs = IngestionRunRepository(session)
        self._instruments = InstrumentRepository(session)
        self._calculators = topological_order(registry or build_registry())

    # -- public ----------------------------------------------------------

    def build(
        self,
        symbols: Sequence[str] | None = None,
        rebuild_from: date | None = None,
    ) -> tuple[IngestionRun, BuildStats]:
        run = self._runs.start(RunType.FEATURES, "mip", ",".join(symbols) if symbols else "ALL")
        stats = BuildStats(features=len(self._calculators))
        end = self._today()

        definitions = {
            calc.spec.name: self._repo.sync_definition(calc.spec) for calc in self._calculators
        }
        market_calcs = [c for c in self._calculators if c.spec.scope is FeatureScope.MARKET]
        instrument_calcs = [c for c in self._calculators if c.spec.scope is FeatureScope.INSTRUMENT]
        max_lookback = max((c.spec.lookback_sessions for c in self._calculators), default=0)

        macro = self._load_macro()
        benchmarks = self._load_benchmark_prices()

        # -- market pass ---------------------------------------------------
        market_ids = [definitions[c.spec.name].id for c in market_calcs]
        market_start = rebuild_from or self._window_start(self._repo.latest_market_date(market_ids))
        market_dates = self._trading_dates(market_start, end, max_lookback)
        market_features: dict[str, pd.Series] = {}
        market_rows: list[dict] = []
        if len(market_dates):
            ctx = FeatureContext(dates=market_dates, benchmarks=benchmarks, macro=macro)
            for calc in market_calcs:
                ctx.features = market_features
                series = calc.compute(ctx)
                market_features[calc.spec.name] = series
                market_rows.extend(
                    self._rows(
                        series,
                        market_start,
                        end,
                        feature_id=definitions[calc.spec.name].id,
                    )
                )
            self._ensure_partitions(market_rows)
            stats.market_rows = self._repo.upsert_market_values(market_rows)

        # -- instrument pass --------------------------------------------------
        for instrument in self._resolve(symbols):
            try:
                stats.instrument_rows += self._build_instrument(
                    instrument,
                    instrument_calcs,
                    definitions,
                    market_features,
                    benchmarks,
                    macro,
                    rebuild_from,
                    end,
                    max_lookback,
                )
                stats.instruments += 1
            except Exception as exc:  # keep symbols isolated, like ingestion
                logger.error(
                    "features.instrument_failed",
                    run_id=run.id,
                    symbol=instrument.symbol,
                    error=str(exc),
                )
                stats.errors[instrument.symbol] = str(exc)

        status = RunStatus.SUCCESS if not stats.errors else RunStatus.PARTIAL
        self._runs.complete(
            run,
            status=status,
            rows_inserted=stats.market_rows + stats.instrument_rows,
            rows_updated=0,
            error_detail={"failed": stats.errors} if stats.errors else None,
        )
        logger.info(
            "features.run_completed",
            run_id=run.id,
            status=status.value,
            market_rows=stats.market_rows,
            instrument_rows=stats.instrument_rows,
            instruments=stats.instruments,
        )
        return run, stats

    # -- per-instrument -------------------------------------------------------

    def _build_instrument(
        self,
        instrument: Instrument,
        calcs: list[FeatureCalculator],
        definitions: dict,
        market_features: dict[str, pd.Series],
        benchmarks: dict[str, pd.DataFrame],
        macro: dict[str, pd.DataFrame],
        rebuild_from: date | None,
        end: date,
        max_lookback: int,
    ) -> int:
        feature_ids = [definitions[c.spec.name].id for c in calcs]
        start = rebuild_from or self._window_start(
            self._repo.latest_instrument_date(instrument.id, feature_ids)
        )
        prices = self._load_prices(instrument.id, start, end, max_lookback)
        if prices.empty:
            return 0

        ctx = FeatureContext(
            dates=prices.index,
            prices=prices,
            benchmarks=benchmarks,
            sector_etf=self._sector_etf_symbol(instrument),
            macro=macro,
            fundamentals=self._load_fundamentals(instrument.id),
            earnings_reported=self._load_earnings_reported(instrument.id),
            earnings_announced=self._load_earnings_announced(instrument.id),
            features=dict(market_features),
        )
        rows: list[dict] = []
        for calc in calcs:
            series = calc.compute(ctx)
            ctx.features[calc.spec.name] = series
            rows.extend(
                self._rows(
                    series,
                    start,
                    end,
                    feature_id=definitions[calc.spec.name].id,
                    instrument_id=instrument.id,
                )
            )
        self._ensure_partitions(rows)
        written = self._repo.upsert_instrument_values(rows)
        logger.info(
            "features.instrument_done",
            symbol=instrument.symbol,
            rows=written,
            window_start=str(start),
        )
        return written

    # -- helpers -------------------------------------------------------------------

    def _resolve(self, symbols: Sequence[str] | None) -> list[Instrument]:
        if symbols is not None:
            found = [self._instruments.get_by_symbol(s) for s in symbols]
            missing = [s for s, i in zip(symbols, found, strict=True) if i is None]
            if missing:
                from mip.core.exceptions import ConfigurationError

                raise ConfigurationError(f"unknown symbols: {missing}")
            return [i for i in found if i is not None]
        return [
            i
            for i in self._instruments.list_instruments()
            if i.is_active and i.instrument_type is not InstrumentType.INDEX
        ]

    def _window_start(self, cursor: date | None) -> date:
        if cursor is None:
            return self._settings.history_start_date
        overlap = self._settings.feature_rebuild_overlap_sessions
        return cursor - timedelta(days=overlap * 2)  # calendar buffer ~ sessions

    def _rows(
        self,
        series: pd.Series,
        start: date,
        end: date,
        feature_id: int,
        instrument_id: int | None = None,
    ) -> list[dict]:
        window = series[
            (series.index >= pd.Timestamp(start)) & (series.index <= pd.Timestamp(end))
        ].dropna()
        rows = []
        for ts, value in window.items():
            row: dict = {
                "feature_date": ts.date(),
                "feature_id": feature_id,
                "value": to_feature_value(value),
            }
            if instrument_id is not None:
                row["instrument_id"] = instrument_id
            rows.append(row)
        return rows

    def _ensure_partitions(self, rows: list[dict]) -> None:
        if rows:
            years = {r["feature_date"].year for r in rows}
            self._repo.ensure_partitions(min(years), max(years))

    def _trading_dates(self, start: date, end: date, lookback: int) -> pd.DatetimeIndex:
        buffered = start - timedelta(days=lookback * 2 + 10)
        days = list(
            self._session.scalars(
                select(TradingDay.calendar_date)
                .where(
                    TradingDay.calendar_date >= buffered,
                    TradingDay.calendar_date <= end,
                )
                .order_by(TradingDay.calendar_date)
            )
        )
        return pd.DatetimeIndex(pd.to_datetime(days))

    def _load_prices(
        self, instrument_id: int, start: date, end: date, lookback: int
    ) -> pd.DataFrame:
        buffered = start - timedelta(days=lookback * 2 + 10)
        rows = self._session.execute(
            select(DailyPrice)
            .where(
                DailyPrice.instrument_id == instrument_id,
                DailyPrice.price_date >= buffered,
                DailyPrice.price_date <= end,
            )
            .order_by(DailyPrice.price_date)
        ).scalars()
        records = [
            {
                "date": r.price_date,
                **{
                    c: float(getattr(r, c)) if getattr(r, c) is not None else float("nan")
                    for c in _PRICE_COLUMNS
                },
                "volume": float(r.volume) if r.volume is not None else float("nan"),
            }
            for r in rows
        ]
        if not records:
            return pd.DataFrame()
        frame = pd.DataFrame(records)
        frame["date"] = pd.to_datetime(frame["date"])
        return frame.set_index("date").sort_index()

    def _load_benchmark_prices(self) -> dict[str, pd.DataFrame]:
        """SPY + every sector ETF, full history (shared across instruments)."""
        from mip.domain.models import Sector

        symbols = {"SPY"}
        etf_ids = self._session.execute(
            select(Instrument.symbol).join(Sector, Sector.etf_instrument_id == Instrument.id)
        ).scalars()
        symbols |= set(etf_ids)

        benchmarks: dict[str, pd.DataFrame] = {}
        for symbol in sorted(symbols):
            instrument = self._instruments.get_by_symbol(symbol)
            if instrument is None:
                continue
            frame = self._load_prices(
                instrument.id, self._settings.history_start_date, self._today(), 300
            )
            if not frame.empty:
                benchmarks[symbol] = frame
        return benchmarks

    def _sector_etf_symbol(self, instrument: Instrument) -> str | None:
        from mip.domain.models import Sector

        sector_id = instrument.sector_id
        if sector_id is None and instrument.industry is not None:
            sector_id = instrument.industry.sector_id
        if sector_id is None:
            return None
        row = self._session.execute(
            select(Instrument.symbol)
            .join(Sector, Sector.etf_instrument_id == Instrument.id)
            .where(Sector.id == sector_id)
        ).scalar()
        return row

    def _load_macro(self) -> dict[str, pd.DataFrame]:
        """All observations for all series, availability attached (D13)."""
        rows = self._session.execute(
            select(
                MacroSeries.provider_code,
                MacroObservation.obs_date,
                MacroObservation.value,
                MacroSeries.publication_lag_days,
            ).join(MacroObservation, MacroObservation.series_id == MacroSeries.id)
        ).all()
        frames: dict[str, pd.DataFrame] = {}
        by_code: dict[str, list] = {}
        for code, obs_date, value, lag in rows:
            by_code.setdefault(code, []).append(
                (
                    obs_date,
                    float(value) if value is not None else float("nan"),
                    obs_date + timedelta(days=lag),
                )
            )
        for code, records in by_code.items():
            frame = pd.DataFrame(records, columns=["obs_date", "value", "available_from"])
            frame["obs_date"] = pd.to_datetime(frame["obs_date"])
            frames[code] = frame.set_index("obs_date").sort_index()
        return frames

    def _load_fundamentals(self, instrument_id: int) -> pd.DataFrame:
        from mip.domain.models import CompanyFundamentals

        rows = self._session.scalars(
            select(CompanyFundamentals)
            .where(CompanyFundamentals.instrument_id == instrument_id)
            .order_by(CompanyFundamentals.as_of_date)
        ).all()
        if not rows:
            return pd.DataFrame()
        fields = (
            "market_cap",
            "trailing_pe",
            "forward_pe",
            "price_to_book",
            "trailing_eps",
            "forward_eps",
            "dividend_yield",
            "beta",
            "shares_outstanding",
            "revenue_ttm",
            "profit_margin",
            "debt_to_equity",
        )
        frame = pd.DataFrame(
            [
                {
                    "as_of_date": r.as_of_date,
                    **{
                        f: float(getattr(r, f)) if getattr(r, f) is not None else float("nan")
                        for f in fields
                    },
                }
                for r in rows
            ]
        )
        frame["as_of_date"] = pd.to_datetime(frame["as_of_date"])
        return frame.set_index("as_of_date").sort_index()

    def _load_earnings_reported(self, instrument_id: int) -> pd.DataFrame:
        from mip.domain.models import EarningsObservation

        rows = self._session.execute(
            select(
                EarningsObservation.earnings_date,
                EarningsObservation.eps_actual,
            )
            .where(
                EarningsObservation.instrument_id == instrument_id,
                EarningsObservation.eps_actual.is_not(None),
            )
            .order_by(EarningsObservation.earnings_date, EarningsObservation.observed_at)
        ).all()
        if not rows:
            return pd.DataFrame(columns=["earnings_date", "eps_actual"])
        frame = pd.DataFrame(rows, columns=["earnings_date", "eps_actual"])
        frame["eps_actual"] = frame["eps_actual"].astype(float)
        # latest observation per event
        return frame.groupby("earnings_date", as_index=False).last()

    def _load_earnings_announced(self, instrument_id: int) -> pd.DataFrame:
        from mip.domain.models import EarningsObservation

        rows = self._session.execute(
            select(
                EarningsObservation.observed_at,
                EarningsObservation.earnings_date,
            ).where(EarningsObservation.instrument_id == instrument_id)
        ).all()
        if not rows:
            return pd.DataFrame(columns=["known_from", "earnings_date"])
        frame = pd.DataFrame(rows, columns=["known_from", "earnings_date"])
        frame["known_from"] = pd.to_datetime(frame["known_from"]).dt.date
        return frame
