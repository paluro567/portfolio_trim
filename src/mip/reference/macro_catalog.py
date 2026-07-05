"""FRED series catalog: parse and validate fred_series.yaml.

The catalog is the single declaration of which macro series exist. Every
series MUST declare publication_lag_days explicitly — the parser rejects
omissions so look-ahead protection can never be silently skipped (D13).
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from mip.core.exceptions import ConfigurationError

VALID_FREQUENCIES = {"D", "W", "M", "Q"}


@dataclass(frozen=True)
class SeriesDef:
    code: str
    name: str
    category: str
    frequency: str  # 'D' | 'W' | 'M' | 'Q'
    publication_lag_days: int
    units: str | None = None
    seasonally_adjusted: bool | None = None
    min_value: float | None = None
    max_value: float | None = None


@dataclass(frozen=True)
class MacroCatalog:
    version: int
    series: tuple[SeriesDef, ...]

    def get(self, code: str) -> SeriesDef | None:
        return next((s for s in self.series if s.code == code), None)

    @property
    def codes(self) -> list[str]:
        return [s.code for s in self.series]


def parse_macro_catalog(path: Path) -> MacroCatalog:
    if not path.is_file():
        raise ConfigurationError(f"macro catalog not found: {path}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ConfigurationError(f"macro catalog is not a mapping: {path}")

    series: list[SeriesDef] = []
    for category in raw.get("categories", []):
        category_name = category.get("name")
        if not category_name:
            raise ConfigurationError("macro catalog category missing 'name'")
        for entry in category.get("series", []):
            code = entry.get("code")
            if not code:
                raise ConfigurationError(
                    f"macro catalog: series entry without 'code' in {category_name}"
                )
            for required in ("name", "frequency", "publication_lag_days"):
                if entry.get(required) is None:
                    raise ConfigurationError(
                        f"macro catalog: series {code} missing required field "
                        f"'{required}' — publication lags must be explicit, never implied"
                    )
            frequency = entry["frequency"]
            if frequency not in VALID_FREQUENCIES:
                raise ConfigurationError(
                    f"macro catalog: series {code} has invalid frequency {frequency!r} "
                    f"(expected one of {sorted(VALID_FREQUENCIES)})"
                )
            lag = int(entry["publication_lag_days"])
            if lag < 0:
                raise ConfigurationError(
                    f"macro catalog: series {code} has negative publication_lag_days"
                )
            series.append(
                SeriesDef(
                    code=code,
                    name=entry["name"],
                    category=category_name,
                    frequency=frequency,
                    publication_lag_days=lag,
                    units=entry.get("units"),
                    seasonally_adjusted=entry.get("seasonally_adjusted"),
                    min_value=entry.get("min_value"),
                    max_value=entry.get("max_value"),
                )
            )

    codes = [s.code for s in series]
    duplicates = {c for c in codes if codes.count(c) > 1}
    if duplicates:
        raise ConfigurationError(f"macro catalog defines duplicate codes: {sorted(duplicates)}")
    if not series:
        raise ConfigurationError(f"macro catalog defines no series: {path}")

    return MacroCatalog(version=int(raw.get("version", 1)), series=tuple(series))
