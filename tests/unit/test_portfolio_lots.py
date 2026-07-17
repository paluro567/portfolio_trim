"""FIFO lot engine: hand-computed scenarios, pure replay, no database."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import CostBasisMethod, GainTerm, TxnType
from mip.portfolio.lots import LotEngine

AAA = 1


def txn(
    txn_id: int,
    txn_type: TxnType,
    trade_date: date,
    quantity: str | None,
    total: str,
    instrument_id: int = AAA,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=txn_id,
        txn_type=txn_type,
        trade_date=trade_date,
        quantity=Decimal(quantity) if quantity else None,
        total_amount=Decimal(total),
        instrument_id=instrument_id,
    )


def test_buy_and_partial_sell_fifo() -> None:
    ledger = [
        txn(1, TxnType.BUY, date(2025, 1, 6), "10", "-1005"),  # 100.50/share w/ fee
        txn(2, TxnType.SELL, date(2025, 3, 3), "4", "475"),
    ]
    lots = LotEngine().replay(ledger)

    assert len(lots) == 1
    lot = lots[0]
    assert lot.cost_basis_per_share == Decimal("100.500000")
    assert lot.quantity_remaining == Decimal("6")
    closure = lot.closures[0]
    assert closure["quantity_closed"] == Decimal("4")
    assert closure["proceeds"] == Decimal("475.000000")
    assert closure["cost_basis"] == Decimal("402.000000")
    assert closure["realized_gain"] == Decimal("73.000000")
    assert closure["term"] is GainTerm.SHORT


def test_fifo_consumes_oldest_lot_first_across_lots() -> None:
    ledger = [
        txn(1, TxnType.BUY, date(2024, 1, 8), "10", "-1000"),  # 100/share
        txn(2, TxnType.BUY, date(2024, 6, 3), "10", "-2000"),  # 200/share
        txn(3, TxnType.SELL, date(2025, 7, 1), "15", "3750"),  # 250/share
    ]
    lots = LotEngine().replay(ledger)
    first, second = lots

    assert first.quantity_remaining == 0 and first.closures[0]["quantity_closed"] == 10
    # proceeds pro-rata: 10/15 and 5/15 of 3750
    assert first.closures[0]["proceeds"] == Decimal("2500.000000")
    assert first.closures[0]["realized_gain"] == Decimal("1500.000000")
    assert first.closures[0]["term"] is GainTerm.LONG  # 540 days
    assert second.quantity_remaining == 5
    assert second.closures[0]["proceeds"] == Decimal("1250.000000")
    assert second.closures[0]["realized_gain"] == Decimal("250.000000")
    assert second.closures[0]["term"] is GainTerm.LONG  # 393 days > 365


def test_oversell_is_rejected() -> None:
    ledger = [
        txn(1, TxnType.BUY, date(2025, 1, 6), "10", "-1000"),
        txn(2, TxnType.SELL, date(2025, 2, 3), "11", "1200"),
    ]
    with pytest.raises(ConfigurationError, match="oversell"):
        LotEngine().replay(ledger)


def test_transfer_out_realizes_no_gain() -> None:
    ledger = [
        txn(1, TxnType.BUY, date(2025, 1, 6), "10", "-1000"),
        txn(2, TxnType.TRANSFER_OUT, date(2025, 5, 5), "4", "400"),
    ]
    (lot,) = LotEngine().replay(ledger)
    closure = lot.closures[0]
    assert closure["proceeds"] == closure["cost_basis"] == Decimal("400.000000")
    assert closure["realized_gain"] == Decimal("0.000000")


def test_opening_balance_creates_a_synthetic_lot_at_stated_basis() -> None:
    ledger = [txn(1, TxnType.OPENING_BALANCE, date(2025, 6, 2), "20", "5000")]
    (lot,) = LotEngine().replay(ledger)
    assert lot.cost_basis_per_share == Decimal("250.000000")
    assert lot.open_date == date(2025, 6, 2)  # the stated basis date, nothing invented
    assert lot.quantity_remaining == Decimal("20")


def test_cash_only_types_never_touch_lots() -> None:
    ledger = [
        txn(1, TxnType.BUY, date(2025, 1, 6), "10", "-1000"),
        txn(2, TxnType.DIVIDEND, date(2025, 2, 3), None, "12.50"),
        txn(3, TxnType.FEE, date(2025, 2, 4), None, "-1.00"),
        txn(4, TxnType.DEPOSIT, date(2025, 2, 5), None, "500"),
    ]
    (lot,) = LotEngine().replay(ledger)
    assert lot.quantity_remaining == Decimal("10") and lot.closures == []


def test_split_transactions_fail_loudly() -> None:
    ledger = [txn(1, TxnType.SPLIT, date(2025, 1, 6), "10", "0")]
    with pytest.raises(ConfigurationError, match="split"):
        LotEngine().replay(ledger)


def test_replay_is_deterministic() -> None:
    ledger = [
        txn(1, TxnType.BUY, date(2024, 1, 8), "10", "-1000"),
        txn(2, TxnType.BUY, date(2024, 6, 3), "7.5", "-1500"),
        txn(3, TxnType.SELL, date(2025, 1, 6), "12.5", "3125"),
        txn(4, TxnType.BUY, date(2025, 2, 3), "3", "-700", instrument_id=2),
    ]

    def serialize(lots):
        return [
            (
                lot.open_transaction_id,
                lot.open_date,
                lot.quantity_opened,
                lot.quantity_remaining,
                lot.cost_basis_per_share,
                tuple(tuple(sorted(c.items())) for c in lot.closures),
            )
            for lot in lots
        ]

    assert serialize(LotEngine().replay(ledger)) == serialize(LotEngine().replay(ledger))


def test_unimplemented_disposal_methods_fail_loudly() -> None:
    with pytest.raises(ConfigurationError, match="not implemented"):
        LotEngine(CostBasisMethod.SPECIFIC_ID)
