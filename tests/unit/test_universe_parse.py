from pathlib import Path

import pytest

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import InstrumentType
from mip.reference.universe import parse_universe

VALID = """
version: 1
sectors:
  - name: Information Technology
    etf: XLK
    industries: [Software]
instruments:
  - {symbol: SPY, type: etf, name: S&P 500 ETF}
  - {symbol: AAPL, type: stock, sector: Information Technology, industry: Technology Hardware}
"""


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "universe.yaml"
    path.write_text(content)
    return path


def test_parses_valid_universe(tmp_path: Path) -> None:
    definition = parse_universe(_write(tmp_path, VALID))

    assert definition.version == 1
    assert definition.sectors[0].name == "Information Technology"
    assert definition.sectors[0].etf_symbol == "XLK"
    assert definition.sectors[0].industries == ("Software",)
    symbols = {i.symbol: i for i in definition.instruments}
    assert symbols["SPY"].instrument_type is InstrumentType.ETF
    assert symbols["AAPL"].sector == "Information Technology"
    assert symbols["AAPL"].industry == "Technology Hardware"


def test_missing_file_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="not found"):
        parse_universe(tmp_path / "nope.yaml")


def test_unknown_sector_reference_rejected(tmp_path: Path) -> None:
    content = """
sectors:
  - {name: Financials, etf: XLF}
instruments:
  - {symbol: AAPL, type: stock, sector: Technology, industry: Hardware}
"""
    with pytest.raises(ConfigurationError, match="unknown sector 'Technology'"):
        parse_universe(_write(tmp_path, content))


def test_industry_without_sector_rejected(tmp_path: Path) -> None:
    content = """
instruments:
  - {symbol: AAPL, type: stock, industry: Hardware}
"""
    with pytest.raises(ConfigurationError, match="'industry' requires 'sector'"):
        parse_universe(_write(tmp_path, content))


def test_invalid_type_rejected(tmp_path: Path) -> None:
    content = """
instruments:
  - {symbol: AAPL, type: bond}
"""
    with pytest.raises(ConfigurationError, match="invalid type 'bond'"):
        parse_universe(_write(tmp_path, content))


def test_duplicate_symbol_rejected(tmp_path: Path) -> None:
    content = """
instruments:
  - {symbol: SPY, type: etf}
  - {symbol: SPY, type: index}
"""
    with pytest.raises(ConfigurationError, match="more than once"):
        parse_universe(_write(tmp_path, content))
