"""Sharadar adapter — MAPPING AND STUB ONLY. Fetches nothing.

Every Sharadar-specific name in the application lives in this file. The rest of
the codebase speaks only the vendor-neutral contract, so replacing Sharadar with
another provider means writing a sibling module and changing one setting.

**Verification status.** Facts marked VERIFIED were read from Sharadar's own
documentation during this work. Facts marked *requires external verification*
are field-level details that could not be confirmed from a fetchable page and
must be checked against the data dictionary before any ingestion code is
written — they are recorded as expectations, not as truth.

VERIFIED from https://sharadar.com/docs/fundamentals :
  * SF1 dimensions are ARQ/ARY/ART ("as reported") and MRQ/MRY/MRT ("most
    recent reported"). AR is "a point-in-time view with data time-indexed to the
    date the form 10 regulatory filing was submitted to the SEC" and EXCLUDES
    restatements; MR "includes restatements" and is time-indexed to the report
    period. **Only AR dimensions are admissible here.**
  * `datekey`, `reportperiod`, `calendardate`, `lastupdated` are the SF1 date
    fields; `lastupdated` is the vendor's revision marker.
  * TICKERS covers "common stock securities (primary class) that are active OR
    DELISTED from Nasdaq, NYSE or NYSEMKT" — the survivorship requirement.
  * History to 1998; updated daily at 17:30 and 23:30 ET; reporting lag < 1 day.

VERIFIED from https://www.quantrocket.com/sharadar/ :
  * Fundamentals since 1990, prices since 1998, S&P 500 constituents since 1957,
    insiders since 2005, institutions since 2013, 8-K events since 1993.

VERIFIED from the fsharadar docs :
  * DAILY carries ev, evebit, evebitda, marketcap, pb, pe, ps.
  * SEP is split-adjusted OHLCV; ACTIONS carries splits and dividends.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from mip.core.exceptions import ConfigurationError
from mip.providers.historical.config import (
    SHARADAR_TABLES,
    HistoricalProviderSettings,
    load_provider_settings,
)


@dataclass(frozen=True, slots=True)
class TableMapping:
    """How one logical dataset is satisfied by one Sharadar table."""

    logical_dataset: str
    sharadar_table: str
    primary_key: tuple[str, ...]
    date_fields: tuple[str, ...]
    availability_field: str | None  # the field that makes a row PIT-safe
    key_columns: tuple[str, ...]
    limitations: str
    verified: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "availability_field": self.availability_field,
            "date_fields": list(self.date_fields),
            "key_columns": list(self.key_columns),
            "limitations": self.limitations,
            "logical_dataset": self.logical_dataset,
            "primary_key": list(self.primary_key),
            "sharadar_table": self.sharadar_table,
            "verified": self.verified,
        }


# The mapping from the eight logical datasets in `mip.calibration.source` to
# Sharadar tables. `verified=False` means the COLUMN NAMES are an expectation
# requiring confirmation against the data dictionary; the table-level mapping is
# sound either way.
TABLE_MAPPINGS: tuple[TableMapping, ...] = (
    TableMapping(
        logical_dataset="security_master",
        sharadar_table=SHARADAR_TABLES["tickers"],
        primary_key=("permaticker",),
        date_fields=("firstpricedate", "lastpricedate", "firstadded", "lastupdated"),
        availability_field=None,
        key_columns=(
            "permaticker",
            "ticker",
            "name",
            "exchange",
            "category",
            "isdelisted",
            "cusips",
            "siccode",
        ),
        limitations=(
            "Covers common stock primary class on Nasdaq/NYSE/NYSEMKT (VERIFIED). "
            "Non-primary share classes and OTC names are out of scope, so the "
            "universe is 'US listed common stock', not 'all equities'."
        ),
        verified=False,
    ),
    TableMapping(
        logical_dataset="prices",
        sharadar_table=SHARADAR_TABLES["prices"],
        primary_key=("ticker", "date"),
        date_fields=("date", "lastupdated"),
        availability_field="date",
        key_columns=("open", "high", "low", "close", "volume", "closeadj", "closeunadj"),
        limitations=(
            "Keyed on TICKER, not permaticker (requires external verification) — the "
            "adapter must join through TICKERS to obtain the permanent id, or ticker "
            "reuse will silently merge two different companies. `closeadj` is "
            "dividend+split adjusted and is RESTATED as new actions occur, so it is "
            "not itself point-in-time."
        ),
        verified=False,
    ),
    TableMapping(
        logical_dataset="fundamentals_pit",
        sharadar_table=SHARADAR_TABLES["fundamentals"],
        primary_key=("ticker", "dimension", "datekey"),
        date_fields=("datekey", "reportperiod", "calendardate", "lastupdated"),
        availability_field="datekey",
        key_columns=("dimension", "datekey", "reportperiod", "revenue", "eps", "netmargin", "de"),
        limitations=(
            "ONLY ARQ/ARY/ART are point-in-time (VERIFIED). MRQ/MRY/MRT include "
            "restatements and must never be used for calibration. A single "
            "(ticker, dimension, reportperiod) may appear multiple times as amended "
            "filings arrive, so the PIT selection rule must pick the latest datekey "
            "<= as_of, not the latest row."
        ),
        verified=True,
    ),
    TableMapping(
        logical_dataset="sector_history",
        sharadar_table=SHARADAR_TABLES["tickers"],
        primary_key=("permaticker",),
        date_fields=("lastupdated",),
        availability_field=None,
        key_columns=("sector", "industry", "sicsector", "sicindustry", "famasector"),
        limitations=(
            "**CRITICAL: believed to be CURRENT classification only, with no history** "
            "(requires external verification). If confirmed, sector-relative historical "
            "calibration is DEGRADED: applying today's sector to 2012 is non-PIT and "
            "must be labelled as such, or the sector_relative group must be dropped "
            "from the reconstructed signal."
        ),
        verified=False,
    ),
    TableMapping(
        logical_dataset="earnings_history",
        sharadar_table=SHARADAR_TABLES["fundamentals"],
        primary_key=("ticker", "dimension", "datekey"),
        date_fields=("datekey", "reportperiod"),
        availability_field="datekey",
        key_columns=("eps", "epsdil", "reportperiod", "datekey"),
        limitations=(
            "SF1 gives the REPORTED figure and its filing date, which is a genuine "
            "observation date. It does NOT give analyst consensus. Sharadar sells no "
            "estimates product — Nasdaq lists Zacks (ZEE/ZSEE/ZEEH) separately — so "
            "**beat/miss versus contemporaneous consensus cannot be reconstructed from "
            "Sharadar alone**. This is the binding gap for 1M/3M/6M/1Y calibration."
        ),
        verified=False,
    ),
    TableMapping(
        logical_dataset="corporate_actions",
        sharadar_table=SHARADAR_TABLES["actions"],
        primary_key=("ticker", "date", "action"),
        date_fields=("date",),
        availability_field="date",
        key_columns=("action", "value", "contraticker", "contraname"),
        limitations=(
            "Carries splits and dividends (VERIFIED). Whether delisting actions and "
            "merger consideration appear here, and in what form, requires external "
            "verification — that determines whether terminal returns can be derived."
        ),
        verified=False,
    ),
    TableMapping(
        logical_dataset="delistings",
        sharadar_table=SHARADAR_TABLES["tickers"],
        primary_key=("permaticker",),
        date_fields=("lastpricedate",),
        availability_field=None,
        key_columns=("isdelisted", "lastpricedate"),
        limitations=(
            "TICKERS gives the FACT of delisting and the last price date (VERIFIED that "
            "delisted names are covered). It does NOT obviously give a DELISTING RETURN. "
            "The terminal return must be derived from the final SEP price plus any "
            "merger/liquidation consideration in ACTIONS — and where consideration is "
            "unknown the outcome must be recorded UNRESOLVED, never assumed to be -100%."
        ),
        verified=False,
    ),
    TableMapping(
        logical_dataset="universe_membership",
        sharadar_table=SHARADAR_TABLES["tickers"] + " + " + SHARADAR_TABLES["daily_metrics"],
        primary_key=("permaticker", "date"),
        date_fields=("date", "firstpricedate", "lastpricedate"),
        availability_field="date",
        key_columns=("marketcap", "category", "exchange", "isdelisted"),
        limitations=(
            "There is no ready-made 'all US common stock as of date T' table. Membership "
            "is CONSTRUCTED: a security is in the universe on T if firstpricedate <= T "
            "<= lastpricedate, category is common stock, exchange is in the allowed set, "
            "and the DAILY marketcap/price/liquidity filters pass on T. SP500 is "
            "available separately for index membership (VERIFIED, since 1957)."
        ),
        verified=False,
    ),
)

REQUIRED_TABLES = ("SHARADAR/TICKERS", "SHARADAR/SEP", "SHARADAR/SF1", "SHARADAR/ACTIONS")
OPTIONAL_TABLES = ("SHARADAR/DAILY", "SHARADAR/SP500", "SHARADAR/EVENTS", "SHARADAR/SFP")


@dataclass
class SharadarProvider:
    """Adapter stub. Constructing it without a key raises; nothing fetches.

    Implementing the ``load_*`` methods is Phase 2 onward of the plan and is
    deliberately NOT done here: the column names several of them depend on are
    still unverified, and writing an ingestion against guessed columns would
    produce a loader that appears to work.
    """

    settings: HistoricalProviderSettings

    @classmethod
    def from_env(cls) -> SharadarProvider:
        settings = load_provider_settings()
        reason = settings.blocked_reason()
        if reason:
            raise ConfigurationError(
                f"Sharadar provider is not configured: {reason}. "
                f"See docs/data/SHARADAR_INGESTION_PLAN.md."
            )
        return cls(settings=settings)

    @property
    def name(self) -> str:
        return "sharadar"

    @property
    def coverage(self) -> tuple[date, date]:
        # VERIFIED: prices from 1998, fundamentals from 1990. The binding start
        # for a joint price+fundamentals study is 1998.
        return date(1998, 1, 1), date.today()

    def _not_implemented(self, method: str):
        raise NotImplementedError(
            f"SharadarProvider.{method} is not implemented. This is scaffolding: the "
            f"column names it depends on require verification against the data "
            f"dictionary, and no subscription is configured. See "
            f"docs/data/SHARADAR_INGESTION_PLAN.md phase ordering."
        )

    def load_security_master(self):
        self._not_implemented("load_security_master")

    def load_universe_membership(self, as_of: date):
        self._not_implemented("load_universe_membership")

    def load_prices(self, source_security_ids, start, end):
        self._not_implemented("load_prices")

    def load_fundamentals_pit(self, source_security_ids, as_of: date):
        self._not_implemented("load_fundamentals_pit")

    def load_sector_history(self, source_security_ids, as_of: date):
        self._not_implemented("load_sector_history")

    def load_earnings_history(self, source_security_ids, as_of: date):
        self._not_implemented("load_earnings_history")

    def load_corporate_actions(self, source_security_ids, start, end):
        self._not_implemented("load_corporate_actions")

    def load_delistings(self, source_security_ids):
        self._not_implemented("load_delistings")


def mapping_for(logical_dataset: str) -> TableMapping | None:
    return next((m for m in TABLE_MAPPINGS if m.logical_dataset == logical_dataset), None)


def unverified_mappings() -> tuple[TableMapping, ...]:
    """Mappings whose column names still need checking against the data dictionary."""
    return tuple(m for m in TABLE_MAPPINGS if not m.verified)
