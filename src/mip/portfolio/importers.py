"""Broker-independent import framework.

An importer parses one file format into CanonicalTransaction DTOs; the
ImportService validates them, filters duplicates via (portfolio,
external_id), and appends the survivors to the ledger under an
ingestion_runs batch (run_type='portfolio_import', archive_path = source
file) — the lineage row every imported transaction points at.

A broker adapter (e.g. Webull, once a real export sample exists) is just
another PortfolioImporter subclass mapping its columns into the canonical
DTO; the ledger never changes. Rows without a broker id get a
deterministic content-hash external_id, so re-importing the same file is
always a no-op (duplicate prevention without trusting the source).

Sign conventions for total_amount (signed cash impact):
  buy/fee/withdrawal   negative     sell/dividend/deposit   positive
  opening_balance / transfer_in / transfer_out: NOT cash — total_amount
  carries the cost basis (positive), marked non-cash by the txn_type.
"""

import abc
import csv
import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import (
    CASH_ONLY_TYPES,
    POSITION_CLOSING_TYPES,
    POSITION_OPENING_TYPES,
    RunStatus,
    RunType,
    TxnType,
)
from mip.repositories.ingestion_runs import IngestionRunRepository
from mip.repositories.instruments import InstrumentRepository
from mip.repositories.portfolio import PortfolioRepository


@dataclass(frozen=True)
class CanonicalTransaction:
    """The one transaction shape every importer must produce."""

    txn_type: TxnType
    trade_date: date
    symbol: str | None  # None for cash-only rows
    quantity: Decimal | None
    price: Decimal | None
    fees: Decimal
    total_amount: Decimal
    external_id: str
    note: str | None = None

    def validate(self, row_number: int) -> None:
        problems: list[str] = []
        if self.txn_type is TxnType.SPLIT:
            problems.append("split transactions are not supported in this phase")
        if self.txn_type in POSITION_OPENING_TYPES + POSITION_CLOSING_TYPES:
            if not self.symbol:
                problems.append("position transaction needs a symbol")
            if self.quantity is None or self.quantity <= 0:
                problems.append("position transaction needs a positive quantity")
            if self.total_amount == 0:
                problems.append("position transaction needs a non-zero total_amount")
        if self.txn_type in CASH_ONLY_TYPES and self.quantity not in (None, Decimal(0)):
            problems.append(f"{self.txn_type.value} must not carry a quantity")
        if self.fees < 0:
            problems.append("fees must be non-negative")
        if problems:
            raise ConfigurationError(f"row {row_number}: " + "; ".join(problems))


class PortfolioImporter(abc.ABC):
    """One file format -> canonical transactions. Stateless and DB-free."""

    @abc.abstractmethod
    def parse(self, path: Path) -> list[CanonicalTransaction]: ...


def _decimal(raw: str, field: str, row_number: int) -> Decimal:
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ConfigurationError(f"row {row_number}: {field} is not a number: {raw!r}") from exc


def _content_hash(*parts: object) -> str:
    joined = "|".join("" if p is None else str(p) for p in parts)
    return "sha256:" + hashlib.sha256(joined.encode()).hexdigest()[:24]


class GenericCsvImporter(PortfolioImporter):
    """Canonical CSV: type,date,symbol,quantity,price,fees,amount and
    optional external_id,note. `amount` follows the signed-cash convention
    (module docstring); missing external ids become content hashes."""

    REQUIRED = ("type", "date", "symbol", "quantity", "price", "fees", "amount")

    def parse(self, path: Path) -> list[CanonicalTransaction]:
        with open(path, newline="") as handle:
            reader = csv.DictReader(handle)
            missing = [c for c in self.REQUIRED if c not in (reader.fieldnames or [])]
            if missing:
                raise ConfigurationError(f"{path.name}: missing columns {missing}")
            out: list[CanonicalTransaction] = []
            for row_number, row in enumerate(reader, start=2):  # 1 = header
                raw_type = (row["type"] or "").strip().lower()
                try:
                    txn_type = TxnType(raw_type)
                except ValueError as exc:
                    raise ConfigurationError(
                        f"row {row_number}: unknown transaction type {raw_type!r}"
                    ) from exc
                symbol = (row["symbol"] or "").strip().upper() or None
                quantity = (
                    _decimal(row["quantity"], "quantity", row_number)
                    if (row["quantity"] or "").strip()
                    else None
                )
                price = (
                    _decimal(row["price"], "price", row_number)
                    if (row["price"] or "").strip()
                    else None
                )
                fees = (
                    _decimal(row["fees"], "fees", row_number)
                    if (row["fees"] or "").strip()
                    else Decimal(0)
                )
                amount = _decimal(row["amount"], "amount", row_number)
                trade_date = date.fromisoformat(row["date"].strip())
                external_id = (row.get("external_id") or "").strip() or _content_hash(
                    raw_type, trade_date, symbol, quantity, price, fees, amount
                )
                txn = CanonicalTransaction(
                    txn_type=txn_type,
                    trade_date=trade_date,
                    symbol=symbol,
                    quantity=quantity,
                    price=price,
                    fees=fees,
                    total_amount=amount,
                    external_id=external_id,
                    note=(row.get("note") or "").strip() or None,
                )
                txn.validate(row_number)
                out.append(txn)
        return out


class OpeningBalanceCsvImporter(PortfolioImporter):
    """Initialize a portfolio from CURRENT holdings when trade history is
    unavailable. CSV: symbol,as_of_date,quantity plus total_cost_basis OR
    average_cost, and optional source,notes. Rows become synthetic
    txn_type='opening_balance' transactions — permanently distinguishable
    from real trades, with no fabricated acquisition dates."""

    def parse(self, path: Path) -> list[CanonicalTransaction]:
        with open(path, newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            for column in ("symbol", "as_of_date", "quantity"):
                if column not in fields:
                    raise ConfigurationError(f"{path.name}: missing column {column!r}")
            if "total_cost_basis" not in fields and "average_cost" not in fields:
                raise ConfigurationError(f"{path.name}: needs total_cost_basis or average_cost")
            out: list[CanonicalTransaction] = []
            for row_number, row in enumerate(reader, start=2):
                symbol = (row["symbol"] or "").strip().upper()
                as_of = date.fromisoformat(row["as_of_date"].strip())
                quantity = _decimal(row["quantity"], "quantity", row_number)
                if (row.get("total_cost_basis") or "").strip():
                    basis = _decimal(row["total_cost_basis"], "total_cost_basis", row_number)
                elif (row.get("average_cost") or "").strip():
                    basis = quantity * _decimal(row["average_cost"], "average_cost", row_number)
                else:
                    raise ConfigurationError(
                        f"row {row_number}: needs total_cost_basis or average_cost"
                    )
                source = (row.get("source") or "").strip() or "unspecified"
                notes = (row.get("notes") or "").strip()
                note = (
                    f"SYNTHETIC opening balance (source: {source}; basis as of "
                    f"{as_of.isoformat()}, not an acquisition date)"
                    + (f" — {notes}" if notes else "")
                )
                txn = CanonicalTransaction(
                    txn_type=TxnType.OPENING_BALANCE,
                    trade_date=as_of,
                    symbol=symbol,
                    quantity=quantity,
                    price=(basis / quantity).quantize(Decimal("0.000001")) if quantity else None,
                    fees=Decimal(0),
                    total_amount=basis,
                    external_id=_content_hash("opening_balance", as_of, symbol, quantity, basis),
                    note=note,
                )
                txn.validate(row_number)
                out.append(txn)
        return out


@dataclass(frozen=True)
class ImportReport:
    dry_run: bool
    parsed: int
    duplicates: int
    inserted: int
    unknown_symbols: tuple[str, ...]
    run_id: int | None

    def to_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "parsed": self.parsed,
            "duplicates": self.duplicates,
            "inserted": self.inserted,
            "unknown_symbols": list(self.unknown_symbols),
            "run_id": self.run_id,
        }


class ImportService:
    """Validate -> dedupe -> append under an ingestion_runs batch."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._portfolios = PortfolioRepository(session)
        self._instruments = InstrumentRepository(session)
        self._runs = IngestionRunRepository(session)

    def run(
        self,
        portfolio_name: str,
        importer: PortfolioImporter,
        path: Path,
        dry_run: bool = False,
    ) -> ImportReport:
        portfolio = self._portfolios.require_portfolio(portfolio_name)
        transactions = importer.parse(path)

        instrument_ids: dict[str, int] = {}
        unknown: set[str] = set()
        for txn in transactions:
            if txn.symbol and txn.symbol not in instrument_ids:
                instrument = self._instruments.get_by_symbol(txn.symbol)
                if instrument is None:
                    unknown.add(txn.symbol)
                else:
                    instrument_ids[txn.symbol] = instrument.id
        if unknown:
            raise ConfigurationError(
                f"unknown symbols in {path.name}: {sorted(unknown)}; "
                "add them to universe.yaml and run: mip universe seed"
            )

        seen: set[str] = set()
        for txn in transactions:  # in-file duplicates are import errors
            if txn.external_id in seen:
                raise ConfigurationError(
                    f"{path.name}: duplicate external_id in file: {txn.external_id}"
                )
            seen.add(txn.external_id)

        existing = self._portfolios.existing_external_ids(
            portfolio.id, [t.external_id for t in transactions]
        )
        fresh = [t for t in transactions if t.external_id not in existing]

        if dry_run:
            return ImportReport(
                dry_run=True,
                parsed=len(transactions),
                duplicates=len(existing),
                inserted=0,
                unknown_symbols=(),
                run_id=None,
            )

        run = self._runs.start(RunType.PORTFOLIO_IMPORT, "csv", portfolio.name)
        rows = [
            {
                "portfolio_id": portfolio.id,
                "instrument_id": instrument_ids.get(t.symbol) if t.symbol else None,
                "txn_type": t.txn_type,
                "trade_date": t.trade_date,
                "quantity": t.quantity,
                "price": t.price,
                "fees": t.fees,
                "total_amount": t.total_amount,
                "external_id": t.external_id,
                "note": t.note,
                "ingestion_run_id": run.id,
            }
            for t in fresh
        ]
        inserted = self._portfolios.append_transactions(rows)
        self._runs.complete(
            run,
            status=RunStatus.SUCCESS,
            rows_inserted=inserted,
            rows_updated=0,
            archive_path=str(path),
        )
        return ImportReport(
            dry_run=False,
            parsed=len(transactions),
            duplicates=len(existing),
            inserted=inserted,
            unknown_symbols=(),
            run_id=run.id,
        )
