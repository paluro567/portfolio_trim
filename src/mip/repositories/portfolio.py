"""Repository for the portfolio aggregate (D3): the append-only transaction
ledger plus its derived projections (lots, closures, snapshots).

Append-only enforcement lives at this seam: the repository exposes INSERT
and READ for transactions — no update, no delete. Corrections are reversing
entries (D14). Derived tables may be deleted and rebuilt at any time."""

from datetime import date
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import CostBasisMethod
from mip.domain.models import Lot, LotClosure, Portfolio, PositionSnapshot, Transaction


class PortfolioRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- portfolios ---------------------------------------------------------

    def create_portfolio(
        self,
        name: str,
        base_currency: str = "USD",
        cost_basis_method: CostBasisMethod = CostBasisMethod.FIFO,
        description: str | None = None,
    ) -> Portfolio:
        if self.get_portfolio(name) is not None:
            raise ConfigurationError(f"portfolio {name!r} already exists")
        portfolio = Portfolio(
            name=name,
            base_currency=base_currency,
            cost_basis_method=cost_basis_method,
            description=description,
        )
        self._session.add(portfolio)
        self._session.flush()
        return portfolio

    def get_portfolio(self, name: str) -> Portfolio | None:
        return self._session.scalar(select(Portfolio).where(Portfolio.name == name))

    def require_portfolio(self, name: str) -> Portfolio:
        portfolio = self.get_portfolio(name)
        if portfolio is None:
            raise ConfigurationError(
                f"unknown portfolio {name!r}; create it with: mip portfolio create {name}"
            )
        return portfolio

    def list_portfolios(self) -> list[Portfolio]:
        return list(self._session.scalars(select(Portfolio).order_by(Portfolio.name)))

    # -- transactions (append-only: INSERT and READ only) ---------------------

    def existing_external_ids(self, portfolio_id: int, external_ids: list[str]) -> set[str]:
        if not external_ids:
            return set()
        rows = self._session.scalars(
            select(Transaction.external_id).where(
                Transaction.portfolio_id == portfolio_id,
                Transaction.external_id.in_(external_ids),
            )
        )
        return set(rows)

    def append_transactions(self, rows: list[dict[str, Any]]) -> int:
        """Plain INSERTs — duplicates must be filtered by the caller (the
        DB unique constraint on (portfolio, external_id) is the backstop)."""
        for row in rows:
            self._session.add(Transaction(**row))
        self._session.flush()
        return len(rows)

    def transactions(self, portfolio_id: int, through: date | None = None) -> list[Transaction]:
        """The ledger in REPLAY ORDER: (trade_date, id). id is BIGSERIAL on
        an append-only table, so this ordering is stable forever — the root
        of deterministic replay."""
        stmt = select(Transaction).where(Transaction.portfolio_id == portfolio_id)
        if through is not None:
            stmt = stmt.where(Transaction.trade_date <= through)
        stmt = stmt.order_by(Transaction.trade_date, Transaction.id)
        return list(self._session.scalars(stmt))

    # -- derived projections (delete + rebuild is sanctioned) -------------------

    def delete_derived(self, portfolio_id: int) -> None:
        lot_ids = select(Lot.id).where(Lot.portfolio_id == portfolio_id)
        self._session.execute(delete(LotClosure).where(LotClosure.lot_id.in_(lot_ids)))
        self._session.execute(delete(Lot).where(Lot.portfolio_id == portfolio_id))
        self._session.flush()

    def insert_lot(self, row: dict[str, Any]) -> Lot:
        lot = Lot(**row)
        self._session.add(lot)
        self._session.flush()
        return lot

    def insert_closure(self, row: dict[str, Any]) -> LotClosure:
        closure = LotClosure(**row)
        self._session.add(closure)
        self._session.flush()
        return closure

    def lots(self, portfolio_id: int, open_only: bool = False) -> list[Lot]:
        stmt = select(Lot).where(Lot.portfolio_id == portfolio_id)
        if open_only:
            stmt = stmt.where(Lot.is_closed.is_(False))
        return list(self._session.scalars(stmt.order_by(Lot.open_date, Lot.id)))

    def closures(self, portfolio_id: int) -> list[LotClosure]:
        lot_ids = select(Lot.id).where(Lot.portfolio_id == portfolio_id)
        return list(
            self._session.scalars(
                select(LotClosure)
                .where(LotClosure.lot_id.in_(lot_ids))
                .order_by(LotClosure.close_date, LotClosure.id)
            )
        )

    # -- snapshots ---------------------------------------------------------------

    def delete_snapshots(self, portfolio_id: int) -> None:
        self._session.execute(
            delete(PositionSnapshot).where(PositionSnapshot.portfolio_id == portfolio_id)
        )
        self._session.flush()

    def upsert_snapshots(self, rows: list[dict[str, Any]]) -> int:
        """Guarded upsert (like the feature stores): unchanged rows keep
        their computed_at, so identical rebuilds are byte-identical."""
        affected = 0
        for start in range(0, len(rows), 5000):
            chunk = rows[start : start + 5000]
            stmt = pg_insert(PositionSnapshot).values(chunk)
            changed = (
                PositionSnapshot.quantity.is_distinct_from(stmt.excluded.quantity)
                | PositionSnapshot.cost_basis.is_distinct_from(stmt.excluded.cost_basis)
                | PositionSnapshot.market_value.is_distinct_from(stmt.excluded.market_value)
                | PositionSnapshot.unrealized_gain.is_distinct_from(stmt.excluded.unrealized_gain)
                | PositionSnapshot.weight.is_distinct_from(stmt.excluded.weight)
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["portfolio_id", "instrument_id", "snapshot_date"],
                set_={
                    "quantity": stmt.excluded.quantity,
                    "cost_basis": stmt.excluded.cost_basis,
                    "market_value": stmt.excluded.market_value,
                    "unrealized_gain": stmt.excluded.unrealized_gain,
                    "weight": stmt.excluded.weight,
                    "computed_at": func.now(),
                },
                where=changed,
            ).returning(PositionSnapshot.instrument_id)
            affected += len(self._session.execute(stmt).fetchall())
        return affected

    def snapshots_on(self, portfolio_id: int, snapshot_date: date) -> list[PositionSnapshot]:
        return list(
            self._session.scalars(
                select(PositionSnapshot)
                .where(
                    PositionSnapshot.portfolio_id == portfolio_id,
                    PositionSnapshot.snapshot_date == snapshot_date,
                )
                .order_by(PositionSnapshot.instrument_id)
            )
        )

    def latest_snapshot_date(self, portfolio_id: int) -> date | None:
        return self._session.scalar(
            select(func.max(PositionSnapshot.snapshot_date)).where(
                PositionSnapshot.portfolio_id == portfolio_id
            )
        )
