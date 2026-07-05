"""Phase 1 gate tests: universe seed, classification constraints, symbol history."""

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from mip.core.db import session_scope
from mip.domain.enums import InstrumentType
from mip.domain.models import Industry, Instrument, Sector, SymbolHistory
from mip.reference.universe import parse_universe, seed_universe
from mip.repositories.instruments import InstrumentRepository

pytestmark = pytest.mark.integration

UNIVERSE = """
version: 1
sectors:
  - name: Information Technology
    etf: XLK
    industries: [Software]
  - name: Financials
    etf: XLF
instruments:
  - {symbol: SPY, type: etf, name: SPDR S&P 500 ETF}
  - symbol: AAPL
    type: stock
    name: Apple
    sector: Information Technology
    industry: Technology Hardware
  - {symbol: MSFT, type: stock, name: Microsoft, sector: Information Technology, industry: Software}
"""


@pytest.fixture()
def universe_file(tmp_path: Path) -> Path:
    path = tmp_path / "universe.yaml"
    path.write_text(UNIVERSE)
    return path


def _snapshot(session: Session) -> dict[str, object]:
    return {
        "sectors": session.execute(select(func.count()).select_from(Sector)).scalar_one(),
        "industries": session.execute(select(func.count()).select_from(Industry)).scalar_one(),
        "instruments": session.execute(select(func.count()).select_from(Instrument)).scalar_one(),
        "history": session.execute(select(func.count()).select_from(SymbolHistory)).scalar_one(),
        "instrument_ids": dict(session.execute(select(Instrument.symbol, Instrument.id)).all()),
    }


def test_seed_is_idempotent(
    migrated_schema: None, session_factory: sessionmaker[Session], universe_file: Path
) -> None:
    definition = parse_universe(universe_file)

    with session_scope(session_factory) as session:
        first = seed_universe(session, definition)
    with session_scope(session_factory) as session:
        before = _snapshot(session)

    with session_scope(session_factory) as session:
        second = seed_universe(session, definition)
    with session_scope(session_factory) as session:
        after = _snapshot(session)

    assert sum(first.created.values()) > 0
    assert sum(second.created.values()) == 0  # second run creates nothing
    assert before == after  # identical row counts AND identical ids


def test_check_constraint_rejects_double_classification(
    migrated_schema: None, session_factory: sessionmaker[Session], universe_file: Path
) -> None:
    with session_scope(session_factory) as session:
        seed_universe(session, parse_universe(universe_file))

    with pytest.raises(IntegrityError, match="ck_instruments_single_classification"):
        with session_scope(session_factory) as session:
            sector = session.scalar(select(Sector).where(Sector.name == "Information Technology"))
            industry = session.scalar(select(Industry).where(Industry.name == "Software"))
            session.add(
                Instrument(
                    symbol="BAD",
                    instrument_type=InstrumentType.STOCK,
                    industry_id=industry.id,
                    sector_id=sector.id,  # both set -> must be rejected
                )
            )


def test_stock_resolves_sector_through_industry(
    migrated_schema: None, session_factory: sessionmaker[Session], universe_file: Path
) -> None:
    with session_scope(session_factory) as session:
        seed_universe(session, parse_universe(universe_file))
        repo = InstrumentRepository(session)

        aapl = repo.get_by_symbol("AAPL")
        assert aapl is not None
        assert aapl.sector_id is None  # stocks carry industry only (3NF)
        assert aapl.industry.name == "Technology Hardware"
        assert aapl.industry.sector.name == "Information Technology"


def test_sector_etf_is_an_instrument_fk(
    migrated_schema: None, session_factory: sessionmaker[Session], universe_file: Path
) -> None:
    with session_scope(session_factory) as session:
        seed_universe(session, parse_universe(universe_file))

        tech = session.scalar(select(Sector).where(Sector.name == "Information Technology"))
        assert tech.etf_instrument_id is not None
        etf = session.get(Instrument, tech.etf_instrument_id)  # resolves to a ROW, not a string
        assert etf.symbol == "XLK"
        assert etf.instrument_type is InstrumentType.ETF
        assert etf.sector_id == tech.id  # ETF carries direct sector classification


def test_symbol_change_preserves_history(
    migrated_schema: None, session_factory: sessionmaker[Session]
) -> None:
    listed = date(2012, 5, 18)
    renamed = date(2022, 6, 9)

    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        inst = repo.create_instrument(
            "FB", InstrumentType.STOCK, name="Meta Platforms", effective_date=listed
        )
        instrument_id = inst.id
        repo.change_symbol(inst, "META", effective=renamed)

    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)

        records = session.scalars(
            select(SymbolHistory)
            .where(SymbolHistory.instrument_id == instrument_id)
            .order_by(SymbolHistory.valid_from)
        ).all()
        assert [(r.symbol, r.valid_from, r.valid_to) for r in records] == [
            ("FB", listed, renamed),
            ("META", renamed, None),
        ]

        assert repo.get_by_symbol("META").id == instrument_id  # current symbol updated
        assert repo.get_by_symbol("FB") is None
        # old symbol still resolves for its validity period
        assert repo.resolve_symbol("FB", date(2020, 1, 1)).id == instrument_id
        assert repo.resolve_symbol("FB", date(2023, 1, 1)) is None
        assert repo.resolve_symbol("META", date(2023, 1, 1)).id == instrument_id
        assert repo.resolve_symbol("META", date(2020, 1, 1)) is None
