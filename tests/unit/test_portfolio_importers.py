"""Import framework: parsing, validation, deterministic dedupe ids, and the
synthetic opening-balance contract — file-level, no database."""

from datetime import date
from decimal import Decimal

import pytest

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import TxnType
from mip.portfolio.importers import GenericCsvImporter, OpeningBalanceCsvImporter

GENERIC = """type,date,symbol,quantity,price,fees,amount,external_id,note
buy,2025-01-06,aaa,10,100,5,-1005,B1,first buy
sell,2025-03-03,AAA,4,119,1,475,,
dividend,2025-04-01,AAA,,,0,12.50,DIV1,
fee,2025-04-02,,,,0,-1.00,FEE1,platform fee
transfer_in,2025-05-05,AAA,3,,0,330,TIN1,ACAT from old broker
"""


def write(tmp_path, name: str, content: str):
    path = tmp_path / name
    path.write_text(content)
    return path


def test_generic_csv_parses_all_supported_types(tmp_path) -> None:
    rows = GenericCsvImporter().parse(write(tmp_path, "t.csv", GENERIC))
    assert [r.txn_type for r in rows] == [
        TxnType.BUY,
        TxnType.SELL,
        TxnType.DIVIDEND,
        TxnType.FEE,
        TxnType.TRANSFER_IN,
    ]
    buy = rows[0]
    assert buy.symbol == "AAA" and buy.quantity == Decimal("10")
    assert buy.total_amount == Decimal("-1005") and buy.fees == Decimal("5")
    assert buy.external_id == "B1"
    assert rows[3].symbol is None  # cash-only fee


def test_missing_external_id_becomes_a_deterministic_content_hash(tmp_path) -> None:
    path = write(tmp_path, "t.csv", GENERIC)
    first = GenericCsvImporter().parse(path)[1]
    second = GenericCsvImporter().parse(path)[1]
    assert first.external_id.startswith("sha256:")
    assert first.external_id == second.external_id  # same content, same id, forever


def test_generic_csv_rejects_bad_rows(tmp_path) -> None:
    cases = {
        "unknown transaction type": "type,date,symbol,quantity,price,fees,amount\n"
        "yolo,2025-01-06,AAA,1,1,0,-1\n",
        "not a number": "type,date,symbol,quantity,price,fees,amount\n"
        "buy,2025-01-06,AAA,ten,1,0,-10\n",
        "positive quantity": "type,date,symbol,quantity,price,fees,amount\n"
        "buy,2025-01-06,AAA,-5,1,0,-5\n",
        "needs a symbol": "type,date,symbol,quantity,price,fees,amount\n"
        "buy,2025-01-06,,5,1,0,-5\n",
        "must not carry a quantity": "type,date,symbol,quantity,price,fees,amount\n"
        "dividend,2025-01-06,AAA,5,1,0,5\n",
        "not supported": "type,date,symbol,quantity,price,fees,amount\n"
        "split,2025-01-06,AAA,2,,0,0\n",
    }
    for message, content in cases.items():
        with pytest.raises(ConfigurationError, match=message):
            GenericCsvImporter().parse(write(tmp_path, "bad.csv", content))


def test_generic_csv_rejects_missing_columns(tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="missing columns"):
        GenericCsvImporter().parse(write(tmp_path, "cols.csv", "type,date\nbuy,2025-01-06\n"))


OPENING = """symbol,as_of_date,quantity,total_cost_basis,average_cost,source,notes
AAA,2025-06-02,20,5000,,webull screenshot,pre-history holdings
BBB,2025-06-02,10,,55.5,webull screenshot,
"""


def test_opening_balances_are_marked_synthetic(tmp_path) -> None:
    rows = OpeningBalanceCsvImporter().parse(write(tmp_path, "ob.csv", OPENING))
    aaa, bbb = rows
    assert aaa.txn_type is TxnType.OPENING_BALANCE
    assert aaa.trade_date == date(2025, 6, 2)
    assert aaa.total_amount == Decimal("5000")
    assert aaa.price == Decimal("250.000000")  # derived average, informational
    assert "SYNTHETIC" in aaa.note and "not an acquisition date" in aaa.note
    assert "webull screenshot" in aaa.note
    assert bbb.total_amount == Decimal("555.0")  # from average_cost x quantity
    assert aaa.external_id.startswith("sha256:")


def test_opening_balances_require_a_basis(tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="total_cost_basis or average_cost"):
        OpeningBalanceCsvImporter().parse(
            write(tmp_path, "ob.csv", "symbol,as_of_date,quantity\nAAA,2025-06-02,20\n")
        )
    with pytest.raises(ConfigurationError, match="total_cost_basis or average_cost"):
        OpeningBalanceCsvImporter().parse(
            write(
                tmp_path,
                "ob2.csv",
                "symbol,as_of_date,quantity,total_cost_basis\nAAA,2025-06-02,20,\n",
            )
        )
