"""Repository for the reference aggregate: instruments, sectors, industries,
symbol history.

Symbol-change rule (D11): `instruments.symbol` is only the CURRENT symbol;
the temporal id↔symbol map lives in symbol_history. change_symbol() closes
the open history row and opens a new one, so old symbols keep resolving for
their validity period.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.domain.enums import InstrumentType
from mip.domain.models import Industry, Instrument, Sector, SymbolHistory


class InstrumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- sectors / industries -------------------------------------------

    def get_sector(self, name: str) -> Sector | None:
        return self._session.scalar(select(Sector).where(Sector.name == name))

    def get_or_create_sector(self, name: str) -> Sector:
        sector = self.get_sector(name)
        if sector is None:
            sector = Sector(name=name)
            self._session.add(sector)
            self._session.flush()
        return sector

    def get_industry(self, sector: Sector, name: str) -> Industry | None:
        return self._session.scalar(
            select(Industry).where(Industry.sector_id == sector.id, Industry.name == name)
        )

    def get_or_create_industry(self, sector: Sector, name: str) -> Industry:
        industry = self.get_industry(sector, name)
        if industry is None:
            industry = Industry(sector_id=sector.id, name=name)
            self._session.add(industry)
            self._session.flush()
        return industry

    def list_sectors(self) -> list[Sector]:
        return list(self._session.scalars(select(Sector).order_by(Sector.name)))

    # -- instruments -----------------------------------------------------

    def get_by_symbol(self, symbol: str) -> Instrument | None:
        """Look up by CURRENT symbol."""
        return self._session.scalar(select(Instrument).where(Instrument.symbol == symbol))

    def create_instrument(
        self,
        symbol: str,
        instrument_type: InstrumentType,
        name: str | None = None,
        industry: Industry | None = None,
        sector: Sector | None = None,
        exchange: str | None = None,
        effective_date: date | None = None,
    ) -> Instrument:
        instrument = Instrument(
            symbol=symbol,
            instrument_type=instrument_type,
            name=name,
            industry_id=industry.id if industry else None,
            sector_id=sector.id if sector else None,
            exchange=exchange,
        )
        self._session.add(instrument)
        self._session.flush()
        self._session.add(
            SymbolHistory(
                instrument_id=instrument.id,
                symbol=symbol,
                valid_from=effective_date or date.today(),
            )
        )
        self._session.flush()
        return instrument

    def change_symbol(self, instrument: Instrument, new_symbol: str, effective: date) -> None:
        """Rename the instrument; history keeps the old symbol resolvable."""
        open_record = self._session.scalar(
            select(SymbolHistory).where(
                SymbolHistory.instrument_id == instrument.id,
                SymbolHistory.valid_to.is_(None),
            )
        )
        if open_record is not None:
            open_record.valid_to = effective
        self._session.add(
            SymbolHistory(instrument_id=instrument.id, symbol=new_symbol, valid_from=effective)
        )
        instrument.symbol = new_symbol
        self._session.flush()

    def resolve_symbol(self, symbol: str, as_of: date) -> Instrument | None:
        """Resolve a symbol to the instrument it referred to on a given date."""
        return self._session.scalar(
            select(Instrument)
            .join(SymbolHistory, SymbolHistory.instrument_id == Instrument.id)
            .where(
                SymbolHistory.symbol == symbol,
                SymbolHistory.valid_from <= as_of,
                (SymbolHistory.valid_to.is_(None)) | (SymbolHistory.valid_to > as_of),
            )
        )

    def list_instruments(self) -> list[Instrument]:
        return list(self._session.scalars(select(Instrument).order_by(Instrument.symbol)))
