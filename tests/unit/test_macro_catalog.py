from pathlib import Path

import pytest

from mip.core.exceptions import ConfigurationError
from mip.reference.macro_catalog import parse_macro_catalog

PROJECT_ROOT = Path(__file__).resolve().parents[2]

VALID = """
version: 1
categories:
  - name: Treasury Yields
    series:
      - code: DGS10
        name: 10-Year Treasury
        frequency: D
        publication_lag_days: 1
        min_value: -2
        max_value: 25
"""


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "fred_series.yaml"
    path.write_text(content)
    return path


def test_parses_valid_catalog(tmp_path: Path) -> None:
    catalog = parse_macro_catalog(_write(tmp_path, VALID))
    series = catalog.get("DGS10")
    assert series is not None
    assert series.category == "Treasury Yields"
    assert series.frequency == "D"
    assert series.publication_lag_days == 1
    assert series.min_value == -2 and series.max_value == 25


def test_missing_publication_lag_rejected(tmp_path: Path) -> None:
    content = """
categories:
  - name: Test
    series:
      - {code: DGS10, name: X, frequency: D}
"""
    with pytest.raises(ConfigurationError, match="publication_lag_days"):
        parse_macro_catalog(_write(tmp_path, content))


def test_invalid_frequency_rejected(tmp_path: Path) -> None:
    content = """
categories:
  - name: Test
    series:
      - {code: DGS10, name: X, frequency: hourly, publication_lag_days: 1}
"""
    with pytest.raises(ConfigurationError, match="invalid frequency"):
        parse_macro_catalog(_write(tmp_path, content))


def test_duplicate_codes_rejected(tmp_path: Path) -> None:
    content = """
categories:
  - name: A
    series:
      - {code: DGS10, name: X, frequency: D, publication_lag_days: 1}
  - name: B
    series:
      - {code: DGS10, name: Y, frequency: D, publication_lag_days: 1}
"""
    with pytest.raises(ConfigurationError, match="duplicate"):
        parse_macro_catalog(_write(tmp_path, content))


def test_negative_lag_rejected(tmp_path: Path) -> None:
    content = """
categories:
  - name: Test
    series:
      - {code: DGS10, name: X, frequency: D, publication_lag_days: -1}
"""
    with pytest.raises(ConfigurationError, match="negative"):
        parse_macro_catalog(_write(tmp_path, content))


def test_missing_file_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="not found"):
        parse_macro_catalog(tmp_path / "nope.yaml")


REQUIRED_CODES = {
    "DGS2",
    "DGS5",
    "DGS10",
    "DGS30",
    "FEDFUNDS",
    "SOFR",
    "CPIAUCSL",
    "CPILFESL",
    "PPIACO",
    "PAYEMS",
    "UNRATE",
    "GDPC1",
    "GDP",
    "UMCSENT",
    "RSAFS",
    "HOUST",
    "PERMIT",
    "VIXCLS",
}


def test_shipped_catalog_is_valid_and_complete() -> None:
    """The real fred_series.yaml: parses, covers the Phase 3 series list,
    and (by parser construction) every series has an explicit lag."""
    catalog = parse_macro_catalog(PROJECT_ROOT / "fred_series.yaml")

    assert REQUIRED_CODES <= set(catalog.codes)
    for series in catalog.series:
        assert series.publication_lag_days >= 0  # explicit, parser-enforced
        assert series.min_value is not None and series.max_value is not None
    categories = {s.category for s in catalog.series}
    assert {
        "Treasury Yields",
        "Fed Policy",
        "Inflation",
        "Employment",
        "Economic Growth",
        "Consumer",
        "Housing",
        "Volatility",
    } <= categories
