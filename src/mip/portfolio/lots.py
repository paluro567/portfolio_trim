"""Deterministic lot accounting: replay the append-only ledger into lots
and closures.

Determinism: transactions arrive in replay order (trade_date, id) from the
repository; FIFO consumes open lots in (open_date, creation sequence)
order; every calculation is Decimal with fixed quantization. Replaying the
same ledger always produces identical lots and closures — the rebuild
command deletes the projections and replays from scratch.

Disposal methods: FIFO is implemented; the method parameter is the seam
for LIFO / highest-cost / specific identification later. Anything else
fails loudly today.

Conventions:
- basis per share = |total_amount| / quantity (fees are already inside
  total_amount by the importer's sign convention).
- SELL: proceeds are allocated to closed slices pro-rata; realized gain =
  proceeds - basis; term = long when held > 365 days.
- TRANSFER_OUT removes shares at cost: proceeds = basis, realized gain 0
  (a transfer is not a taxable disposal here).
- Opening-balance lots use the stated as_of_date as open_date — a BASIS
  date, not an acquisition date, so their holding-period terms are
  indicative only (documented; never fabricated).
- Oversells are rejected: short positions are out of scope this phase.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import (
    POSITION_CLOSING_TYPES,
    POSITION_OPENING_TYPES,
    CostBasisMethod,
    GainTerm,
    TxnType,
)
from mip.domain.models import Transaction
from mip.repositories.portfolio import PortfolioRepository

MONEY = Decimal("0.000001")  # NUMERIC(*, 6)
SHARES = Decimal("0.00000001")  # NUMERIC(20, 8)
LONG_TERM_DAYS = 365


@dataclass
class OpenLot:
    open_transaction_id: int
    open_date: date
    quantity_opened: Decimal
    quantity_remaining: Decimal
    cost_basis_per_share: Decimal
    closures: list[dict] = field(default_factory=list)


class LotEngine:
    """Pure replay: ordered transactions in, lots + closures out."""

    def __init__(self, method: CostBasisMethod = CostBasisMethod.FIFO) -> None:
        if method is not CostBasisMethod.FIFO:
            raise ConfigurationError(
                f"cost basis method {method.value!r} is not implemented; FIFO only"
            )
        self.method = method

    def replay(self, transactions: list[Transaction]) -> list[OpenLot]:
        """Transactions MUST already be in replay order (trade_date, id)."""
        lots_by_instrument: dict[int, list[OpenLot]] = {}
        for txn in transactions:
            if txn.txn_type is TxnType.SPLIT:
                raise ConfigurationError(
                    "split transactions are not supported in this phase " f"(transaction {txn.id})"
                )
            if txn.txn_type in POSITION_OPENING_TYPES:
                self._open(lots_by_instrument, txn)
            elif txn.txn_type in POSITION_CLOSING_TYPES:
                self._close(lots_by_instrument, txn)
            # cash-only types never touch lots
        return [lot for lots in lots_by_instrument.values() for lot in lots]

    def _open(self, lots_by_instrument: dict, txn: Transaction) -> None:
        quantity = Decimal(txn.quantity)
        basis_per_share = (abs(Decimal(txn.total_amount)) / quantity).quantize(
            MONEY, rounding=ROUND_HALF_EVEN
        )
        lots_by_instrument.setdefault(txn.instrument_id, []).append(
            OpenLot(
                open_transaction_id=txn.id,
                open_date=txn.trade_date,
                quantity_opened=quantity.quantize(SHARES),
                quantity_remaining=quantity.quantize(SHARES),
                cost_basis_per_share=basis_per_share,
            )
        )

    def _close(self, lots_by_instrument: dict, txn: Transaction) -> None:
        quantity = Decimal(txn.quantity).quantize(SHARES)
        lots = lots_by_instrument.get(txn.instrument_id, [])
        available = sum((lot.quantity_remaining for lot in lots), Decimal(0))
        if quantity > available:
            raise ConfigurationError(
                f"oversell: transaction {txn.id} ({txn.txn_type.value}) on "
                f"{txn.trade_date} disposes {quantity} but only {available} held "
                "— short positions are out of scope in this phase"
            )
        is_sale = txn.txn_type is TxnType.SELL
        total_proceeds = abs(Decimal(txn.total_amount))
        remaining = quantity
        for lot in lots:  # FIFO: list is already in (open_date, sequence) order
            if remaining <= 0:
                break
            if lot.quantity_remaining <= 0:
                continue
            closed = min(lot.quantity_remaining, remaining)
            cost_basis = (closed * lot.cost_basis_per_share).quantize(MONEY)
            if is_sale:
                proceeds = (total_proceeds * closed / quantity).quantize(MONEY)
            else:  # transfer out: shares leave at cost, no realized gain
                proceeds = cost_basis
            holding_days = (txn.trade_date - lot.open_date).days
            lot.closures.append(
                {
                    "close_transaction_id": txn.id,
                    "close_date": txn.trade_date,
                    "quantity_closed": closed,
                    "proceeds": proceeds,
                    "cost_basis": cost_basis,
                    "realized_gain": (proceeds - cost_basis).quantize(MONEY),
                    "holding_period_days": holding_days,
                    "term": (GainTerm.LONG if holding_days > LONG_TERM_DAYS else GainTerm.SHORT),
                }
            )
            lot.quantity_remaining = (lot.quantity_remaining - closed).quantize(SHARES)
            remaining = (remaining - closed).quantize(SHARES)


def rebuild_lots(session, portfolio_name: str) -> tuple[int, int]:
    """Delete the derived lots/closures and replay the full ledger.
    Returns (lots written, closures written)."""
    repo = PortfolioRepository(session)
    portfolio = repo.require_portfolio(portfolio_name)
    engine = LotEngine(CostBasisMethod(portfolio.cost_basis_method))
    transactions = [t for t in repo.transactions(portfolio.id) if t.instrument_id is not None]

    replayed = engine.replay(transactions)
    repo.delete_derived(portfolio.id)
    lot_count = closure_count = 0
    txn_instrument = {t.id: t.instrument_id for t in transactions}
    for state in replayed:
        lot = repo.insert_lot(
            {
                "portfolio_id": portfolio.id,
                "instrument_id": txn_instrument[state.open_transaction_id],
                "open_transaction_id": state.open_transaction_id,
                "open_date": state.open_date,
                "quantity_opened": state.quantity_opened,
                "quantity_remaining": state.quantity_remaining,
                "cost_basis_per_share": state.cost_basis_per_share,
                "is_closed": state.quantity_remaining == 0,
            }
        )
        lot_count += 1
        for closure in state.closures:
            repo.insert_closure({"lot_id": lot.id, **closure})
            closure_count += 1
    return lot_count, closure_count
