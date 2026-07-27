"""A small, deterministic demo security-master snapshot.

Used by `mip securities ingest --fixture` so the Phase-1 interfaces are
exercisable without a licensed vendor feed. It intentionally covers the hard
cases — a ticker change, ticker reuse by a different security, a bankruptcy, an
exchange transfer, an ETF (excluded from the equity universe), and a security
with no permanent id (quarantined) — so the demo is representative, not a happy
path. It is NOT research data: real ingestion remains BLOCKED (see source.py).
"""

from __future__ import annotations

from datetime import date

from mip.domain.enums import IdentifierType, LifecycleEventType, SecurityType
from mip.securities.source import (
    FixtureSource,
    SourceClassification,
    SourceDelisting,
    SourceIdentifier,
    SourceLifecycleEvent,
    SourceSecurity,
)

_T = IdentifierType.TICKER


def _tick(value: str, vf: date, vt: date | None = None, exch: str = "NYSE") -> SourceIdentifier:
    return SourceIdentifier(_T, value, valid_from=vf, valid_to=vt, exchange=exch)


def demo_source(data_version: str = "demo-v1") -> FixtureSource:
    secs = [
        SourceSecurity(
            "KEEP",
            SecurityType.COMMON,
            name="Keepco",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 1, 1),
            identifiers=(_tick("KEEP", date(2015, 1, 1)),),
            classifications=(
                SourceClassification("GICS", date(2015, 1, 1), sector="Information Technology"),
            ),
        ),
        SourceSecurity(
            "R1",
            SecurityType.COMMON,
            name="Renameco",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 1, 1),
            identifiers=(
                _tick("OLD", date(2015, 1, 1), date(2020, 6, 1)),
                _tick("NEW", date(2020, 6, 1)),
            ),
            lifecycle_events=(
                SourceLifecycleEvent(LifecycleEventType.TICKER_CHANGED, date(2020, 6, 1)),
            ),
        ),
        SourceSecurity(
            "R2",
            SecurityType.COMMON,
            name="Reuseco",
            primary_exchange="NYSE",
            first_trade_date=date(2021, 1, 1),
            identifiers=(_tick("OLD", date(2021, 1, 1)),),
        ),
        SourceSecurity(
            "BUST",
            SecurityType.COMMON,
            name="Bustco",
            primary_exchange="NYSE",
            first_trade_date=date(2014, 1, 1),
            active=False,
            delisted=True,
            delisting_date=date(2018, 11, 1),
            delisting_reason="bankruptcy",
            identifiers=(_tick("BUST", date(2014, 1, 1), date(2018, 11, 1)),),
            delisting=SourceDelisting(date(2018, 11, 1), "B", "bankruptcy"),
            lifecycle_events=(
                SourceLifecycleEvent(LifecycleEventType.BANKRUPT, date(2018, 11, 1)),
            ),
        ),
        SourceSecurity(
            "XFER",
            SecurityType.COMMON,
            name="Xferco",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 1, 1),
            identifiers=(
                _tick("XFER", date(2015, 1, 1), date(2019, 1, 1), "NASDAQ"),
                _tick("XFER", date(2019, 1, 1), None, "NYSE"),
            ),
            lifecycle_events=(
                SourceLifecycleEvent(LifecycleEventType.EXCHANGE_CHANGED, date(2019, 1, 1)),
            ),
        ),
        SourceSecurity(
            "ETF1",
            SecurityType.ETF,
            name="An ETF",
            primary_exchange="NYSE",
            first_trade_date=date(2010, 1, 1),
            identifiers=(_tick("ETF1", date(2010, 1, 1)),),
        ),
        SourceSecurity("", SecurityType.COMMON, name="No id"),  # -> quarantined
    ]
    return FixtureSource(name="demo", data_version=data_version, _securities=tuple(secs))
