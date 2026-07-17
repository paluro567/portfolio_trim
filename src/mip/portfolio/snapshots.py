"""Reproducible daily position snapshots: ledger x trading calendar x
adjusted closes.

For every trading day from the first transaction to the latest priced
session, replay the ledger incrementally (same LotEngine, same replay
order) and record quantity, cost basis (raw transaction prices, via open
lots), market value (adjusted close, latest at or before the snapshot day
— never a future price), unrealized gain, and portfolio weight. The upsert
is guarded, so rebuilding from the same ledger and prices is byte-identical
and writes zero changed rows the second time."""

import bisect
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import RunStatus, RunType
from mip.domain.models import DailyPrice, PositionSnapshot, TradingDay
from mip.portfolio.lots import MONEY, LotEngine
from mip.repositories.ingestion_runs import IngestionRunRepository
from mip.repositories.portfolio import PortfolioRepository

WEIGHT = Decimal("0.00000001")  # NUMERIC(10, 8)


class SnapshotBuilder:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = PortfolioRepository(session)
        self._runs = IngestionRunRepository(session)

    def build(self, portfolio_name: str, through: date | None = None) -> int:
        """(Re)build snapshots for every trading day from the first
        transaction through `through` (default: latest priced session).
        Returns the number of changed snapshot rows."""
        portfolio = self._repo.require_portfolio(portfolio_name)
        transactions = [
            t for t in self._repo.transactions(portfolio.id) if t.instrument_id is not None
        ]
        if not transactions:
            raise ConfigurationError(
                f"portfolio {portfolio_name!r} has no position transactions to snapshot"
            )
        instrument_ids = sorted({t.instrument_id for t in transactions})
        prices = {i: self._adjusted_closes(i) for i in instrument_ids}
        last_priced = max((max(p) for p in prices.values() if p), default=None)
        if last_priced is None:
            raise ConfigurationError("no adjusted closes stored for the held instruments")
        end = min(through or last_priced, last_priced)
        start = transactions[0].trade_date
        days = list(
            self._session.scalars(
                select(TradingDay.calendar_date)
                .where(TradingDay.calendar_date >= start, TradingDay.calendar_date <= end)
                .order_by(TradingDay.calendar_date)
            )
        )
        if not days:
            raise ConfigurationError("no trading-calendar days cover the ledger window")

        run = self._runs.start(RunType.SNAPSHOTS, "mip", portfolio.name)
        engine = LotEngine()
        rows: list[dict] = []
        cursor = 0
        replayed_through: list = []  # incremental ledger prefix
        sorted_price_dates = {i: sorted(p) for i, p in prices.items()}
        for day in days:
            while cursor < len(transactions) and transactions[cursor].trade_date <= day:
                replayed_through.append(transactions[cursor])
                cursor += 1
            lots = engine.replay(replayed_through)  # deterministic prefix replay
            by_instrument: dict[int, tuple[Decimal, Decimal]] = {}
            txn_instrument = {t.id: t.instrument_id for t in replayed_through}
            for lot in lots:
                if lot.quantity_remaining <= 0:
                    continue
                instrument_id = txn_instrument[lot.open_transaction_id]
                quantity, basis = by_instrument.get(instrument_id, (Decimal(0), Decimal(0)))
                by_instrument[instrument_id] = (
                    quantity + lot.quantity_remaining,
                    basis + (lot.quantity_remaining * lot.cost_basis_per_share).quantize(MONEY),
                )
            if not by_instrument:
                continue
            values: dict[int, Decimal | None] = {}
            for instrument_id, (quantity, _basis) in by_instrument.items():
                close = self._latest_close(
                    prices[instrument_id], sorted_price_dates[instrument_id], day
                )
                values[instrument_id] = (
                    (quantity * close).quantize(MONEY) if close is not None else None
                )
            total = sum((v for v in values.values() if v is not None), Decimal(0))
            for instrument_id, (quantity, basis) in sorted(by_instrument.items()):
                market_value = values[instrument_id]
                rows.append(
                    {
                        "portfolio_id": portfolio.id,
                        "instrument_id": instrument_id,
                        "snapshot_date": day,
                        "quantity": quantity,
                        "cost_basis": basis,
                        "market_value": market_value,
                        "unrealized_gain": (
                            (market_value - basis).quantize(MONEY)
                            if market_value is not None
                            else None
                        ),
                        "weight": (
                            (market_value / total).quantize(WEIGHT, rounding=ROUND_HALF_EVEN)
                            if market_value is not None and total > 0
                            else None
                        ),
                    }
                )
        changed = self._repo.upsert_snapshots(rows)
        self._runs.complete(run, status=RunStatus.SUCCESS, rows_inserted=changed, rows_updated=0)
        return changed

    # -- prices ------------------------------------------------------------

    def _adjusted_closes(self, instrument_id: int) -> dict[date, Decimal]:
        rows = self._session.execute(
            select(DailyPrice.price_date, DailyPrice.adj_close).where(
                DailyPrice.instrument_id == instrument_id,
                DailyPrice.adj_close.is_not(None),
            )
        ).all()
        return {d: Decimal(v) for d, v in rows}

    @staticmethod
    def _latest_close(
        prices: dict[date, Decimal], sorted_dates: list[date], day: date
    ) -> Decimal | None:
        """Latest close at or before `day` — never a future price."""
        if day in prices:
            return prices[day]
        position = bisect.bisect_right(sorted_dates, day)
        if position == 0:
            return None
        return prices[sorted_dates[position - 1]]


def snapshot_count(session: Session, portfolio_id: int) -> int:
    return session.scalar(select(func.count()).where(PositionSnapshot.portfolio_id == portfolio_id))
