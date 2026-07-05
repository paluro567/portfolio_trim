"""Universe definition: parse, validate, and idempotently seed reference data.

The universe file (YAML, versioned in git) is the single declaration of
sectors, sector ETFs, industries, benchmarks, and holdings. Seeding is
idempotent by natural keys (sector name, industry name-within-sector,
symbol): re-running against an unchanged file is a no-op.
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.core.logging import get_logger
from mip.domain.enums import InstrumentType
from mip.repositories.instruments import InstrumentRepository

logger = get_logger(__name__)


@dataclass(frozen=True)
class SectorDef:
    name: str
    etf_symbol: str | None = None
    etf_name: str | None = None
    industries: tuple[str, ...] = ()


@dataclass(frozen=True)
class InstrumentDef:
    symbol: str
    instrument_type: InstrumentType
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    exchange: str | None = None


@dataclass(frozen=True)
class UniverseDefinition:
    version: int
    sectors: tuple[SectorDef, ...]
    instruments: tuple[InstrumentDef, ...]


@dataclass
class SeedResult:
    created: dict[str, int] = field(default_factory=dict)
    existing: dict[str, int] = field(default_factory=dict)

    def count(self, kind: str, was_created: bool) -> None:
        bucket = self.created if was_created else self.existing
        bucket[kind] = bucket.get(kind, 0) + 1


def parse_universe(path: Path) -> UniverseDefinition:
    if not path.is_file():
        raise ConfigurationError(f"universe file not found: {path}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ConfigurationError(f"universe file is not a mapping: {path}")

    sectors: list[SectorDef] = []
    for entry in raw.get("sectors", []):
        etf = entry.get("etf")
        if isinstance(etf, dict):
            etf_symbol, etf_name = etf.get("symbol"), etf.get("name")
        else:
            etf_symbol, etf_name = etf, None
        sectors.append(
            SectorDef(
                name=entry["name"],
                etf_symbol=etf_symbol,
                etf_name=etf_name,
                industries=tuple(entry.get("industries", [])),
            )
        )
    sector_names = {s.name for s in sectors}

    instruments: list[InstrumentDef] = []
    for entry in raw.get("instruments", []):
        symbol = entry.get("symbol")
        if not symbol:
            raise ConfigurationError("universe instrument entry missing 'symbol'")
        try:
            itype = InstrumentType(entry.get("type", ""))
        except ValueError:
            raise ConfigurationError(
                f"universe instrument {symbol}: invalid type {entry.get('type')!r} "
                f"(expected one of {[t.value for t in InstrumentType]})"
            ) from None
        sector, industry = entry.get("sector"), entry.get("industry")
        if industry and not sector:
            raise ConfigurationError(
                f"universe instrument {symbol}: 'industry' requires 'sector' "
                "(industries are scoped to a sector)"
            )
        if sector and sector not in sector_names:
            raise ConfigurationError(
                f"universe instrument {symbol}: unknown sector {sector!r} "
                "(must be declared under 'sectors')"
            )
        instruments.append(
            InstrumentDef(
                symbol=symbol,
                instrument_type=itype,
                name=entry.get("name"),
                sector=sector,
                industry=industry,
                exchange=entry.get("exchange"),
            )
        )

    seen: set[str] = set()
    for inst in instruments:
        if inst.symbol in seen:
            raise ConfigurationError(f"universe defines symbol {inst.symbol} more than once")
        seen.add(inst.symbol)

    return UniverseDefinition(
        version=int(raw.get("version", 1)),
        sectors=tuple(sectors),
        instruments=tuple(instruments),
    )


def seed_universe(
    session: Session, definition: UniverseDefinition, effective_date: date | None = None
) -> SeedResult:
    """Idempotently apply the universe definition to the reference tables."""
    repo = InstrumentRepository(session)
    result = SeedResult()
    effective = effective_date or date.today()

    for sector_def in definition.sectors:
        existed = repo.get_sector(sector_def.name) is not None
        sector = repo.get_or_create_sector(sector_def.name)
        result.count("sectors", not existed)

        for industry_name in sector_def.industries:
            existed = repo.get_industry(sector, industry_name) is not None
            repo.get_or_create_industry(sector, industry_name)
            result.count("industries", not existed)

        if sector_def.etf_symbol:
            etf = repo.get_by_symbol(sector_def.etf_symbol)
            if etf is None:
                etf = repo.create_instrument(
                    symbol=sector_def.etf_symbol,
                    instrument_type=InstrumentType.ETF,
                    name=sector_def.etf_name or f"{sector_def.name} sector ETF",
                    sector=sector,  # direct sector classification, no industry
                    effective_date=effective,
                )
                result.count("instruments", True)
            else:
                result.count("instruments", False)
            if sector.etf_instrument_id != etf.id:
                sector.etf_instrument_id = etf.id  # FK, never a ticker string

    for inst_def in definition.instruments:
        if repo.get_by_symbol(inst_def.symbol) is not None:
            result.count("instruments", False)
            continue
        industry = sector = None
        if inst_def.industry:
            parent = repo.get_or_create_sector(inst_def.sector)  # validated present
            existed = repo.get_industry(parent, inst_def.industry) is not None
            industry = repo.get_or_create_industry(parent, inst_def.industry)
            result.count("industries", not existed)
        elif inst_def.sector:
            sector = repo.get_or_create_sector(inst_def.sector)
        repo.create_instrument(
            symbol=inst_def.symbol,
            instrument_type=inst_def.instrument_type,
            name=inst_def.name,
            industry=industry,
            sector=sector,
            exchange=inst_def.exchange,
            effective_date=effective,
        )
        result.count("instruments", True)

    logger.info("universe.seeded", created=result.created, existing=result.existing)
    return result
