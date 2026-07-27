"""Deterministic demo data for the native outcome foundation (docs/samples/CLI).

Small survivorship-AWARE sample: it deliberately REPRESENTS a delisted loser and
a cash acquisition so the CLI exercises terminal handling end to end. NOT a
production survivorship-clean source — the real feed stays blocked.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from mip.domain.enums import IdentifierType, LifecycleEventType, SecurityType, TerminalRule
from mip.research_data.source import (
    FixtureOutcomeSource,
    SourceBenchmarkBar,
    SourceMarketSnapshot,
    SourcePriceBar,
    SourceTerminal,
)
from mip.securities.source import (
    FixtureSource,
    SourceDelisting,
    SourceIdentifier,
    SourceLifecycleEvent,
    SourceSecurity,
)

_GRID = [date(y, m, 1) for y in range(2015, 2020) for m in range(1, 13)]


def _months(d: date) -> int:
    return (d.year - 2015) * 12 + (d.month - 1)


def _tick(v, vf, vt=None):
    return SourceIdentifier(IdentifierType.TICKER, v, valid_from=vf, valid_to=vt, exchange="NYSE")


def _bars(vendor_id, start, end):
    out = []
    for d in _GRID:
        if start <= d <= end:
            adj = Decimal("100") + Decimal(_months(d))
            out.append(
                SourcePriceBar(
                    source_security_id=vendor_id,
                    trade_date=d,
                    close=adj,
                    adjusted_close=adj,
                    volume=1_000_000,
                    exchange="NYSE",
                )
            )
    return out


def demo_securities(data_version: str = "demo-v1") -> FixtureSource:
    secs = [
        SourceSecurity(
            "KEEP",
            SecurityType.COMMON,
            name="Keepco",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 1, 1),
            identifiers=(_tick("KEEP", date(2015, 1, 1)),),
        ),
        SourceSecurity(
            "BUST",
            SecurityType.COMMON,
            name="Bustco",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 1, 1),
            active=False,
            delisted=True,
            delisting_date=date(2018, 11, 1),
            delisting_reason="bankruptcy",
            identifiers=(_tick("BUST", date(2015, 1, 1), date(2018, 11, 1)),),
            delisting=SourceDelisting(date(2018, 11, 1), "B", "bankruptcy"),
            lifecycle_events=(
                SourceLifecycleEvent(LifecycleEventType.BANKRUPT, date(2018, 11, 1)),
            ),
        ),
        SourceSecurity(
            "CASHACQ",
            SecurityType.COMMON,
            name="Cashco",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 1, 1),
            active=False,
            delisted=True,
            delisting_date=date(2019, 3, 1),
            delisting_reason="acquired_cash",
            identifiers=(_tick("CASH", date(2015, 1, 1), date(2019, 3, 1)),),
            delisting=SourceDelisting(date(2019, 3, 1), "M", "acquired_cash"),
        ),
    ]
    return FixtureSource(name="fixture", data_version=data_version, _securities=tuple(secs))


def demo_outcomes(data_version: str = "demo-v1") -> FixtureOutcomeSource:
    prices = (
        _bars("KEEP", date(2015, 1, 1), date(2019, 12, 1))
        + _bars("BUST", date(2015, 1, 1), date(2018, 11, 1))
        + _bars("CASHACQ", date(2015, 1, 1), date(2019, 3, 1))
    )
    benchmarks = [SourceBenchmarkBar("MARKET", "market", d, Decimal("0")) for d in _GRID]
    market = [
        SourceMarketSnapshot(
            "KEEP",
            date(2016, 1, 1),
            price=Decimal("100"),
            shares_outstanding=1_000_000,
            market_cap=Decimal("100000000"),
            average_dollar_volume=Decimal("5000000"),
            sector="Information Technology",
        )
    ]
    terminals = [
        SourceTerminal(
            "BUST", date(2018, 11, 1), TerminalRule.BANKRUPTCY, terminal_return=Decimal("-0.90")
        ),
        SourceTerminal(
            "CASHACQ",
            date(2019, 3, 1),
            TerminalRule.CASH_ACQUISITION,
            terminal_return=Decimal("0.05"),
            cash_consideration=Decimal("50"),
        ),
    ]
    return FixtureOutcomeSource(
        name="fixture",
        data_version=data_version,
        _prices=tuple(prices),
        _market=tuple(market),
        _benchmarks=tuple(benchmarks),
        _terminals=tuple(terminals),
    )


DEMO_AS_OFS = [date(2016, 6, 30), date(2018, 6, 29)]
DEMO_HORIZONS = {"1m": 30, "1y": 365}
