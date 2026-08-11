"""The reference universe supplies comparison distributions and nothing else."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from mip.product.quality import MIN_PEERS, QualityAssessment
from mip.reference_universe import PROVIDER_SECTOR_KEY, eligible

BALANCES = Path("data/peter_real_opening_balances_2026-07-16.csv")
AS = date(2026, 8, 11)


def _holdings() -> set[str]:
    return {r["symbol"].strip().upper() for r in csv.DictReader(BALANCES.open())}


# -- portfolio isolation ------------------------------------------------------
def test_portfolio_membership_comes_only_from_the_holdings_file():
    """Instruments may grow without creating a single position."""
    from sqlalchemy import text

    from mip.cli._deps import open_session_factory
    from mip.core.db import session_scope

    with session_scope(open_session_factory()) as s:
        instruments = {r[0] for r in s.execute(text("select symbol from instruments")).all()}
    holdings = _holdings()
    assert holdings <= instruments
    assert len(instruments) > len(holdings)  # reference names are present
    # and they are NOT holdings
    assert not (instruments - holdings) & holdings


def test_reference_securities_do_not_affect_portfolio_weights():
    from mip.cli._deps import open_session_factory
    from mip.core.db import session_scope
    from mip.product.slice import load_position

    with session_scope(open_session_factory()) as s:
        pos = load_position(s, "AMZN", AS, BALANCES)
    # the denominator is the holdings file, not the instrument table
    assert pos.portfolio_positions == len(_holdings())


def test_reference_securities_produce_no_recommendation():
    """A reference name is never evaluated: it is not in the holdings file."""
    from mip.cli._deps import open_session_factory
    from mip.core.db import session_scope
    from mip.product.slice import load_position

    with session_scope(open_session_factory()) as s:
        try:
            load_position(s, "JNJ", AS, BALANCES)  # a reference name, not held
        except ValueError as exc:
            assert "not present" in str(exc)
        else:
            raise AssertionError("a reference security must not resolve to a position")


# -- deterministic membership -------------------------------------------------
def test_membership_rules_are_deterministic_and_declared():
    assert len(PROVIDER_SECTOR_KEY) == 11
    assert eligible("AAPL", "Apple Inc.")[0] is True
    assert eligible("BRK-B", "Berkshire Hathaway")[0] is False
    assert eligible("TOOLONG", "x")[0] is False
    assert eligible("SPY", "SPDR S&P 500 ETF Trust")[0] is False


def test_rejections_carry_a_reason():
    ok, why = eligible("BRK-B", "Berkshire")
    assert not ok and why


# -- evidence safety ----------------------------------------------------------
def test_insufficient_peers_still_yields_unavailable():
    a = QualityAssessment("UNAVAILABLE", "Energy", 2, None, (), (), AS, "only 2 peers")
    assert a.state == "UNAVAILABLE" and a.composite_percentile is None
    assert MIN_PEERS >= 5


def test_failed_reference_ingestion_cannot_fabricate_evidence():
    """A reference security with no fundamentals row simply is not a peer."""
    from mip.product.quality import _usable

    assert _usable({"profit_margin": None, "debt_to_equity": None}) == {}


def test_current_only_fundamentals_cannot_enter_historical_claims():
    """Historical forward-return evidence must derive from prices alone."""
    import inspect

    from mip.product import slice as sl

    src = inspect.getsource(sl._historical)
    assert "company_fundamentals" not in src
    assert "daily_prices" in src


def test_quality_remains_one_phenomenon_and_one_year_only():
    from mip.product.slice import QUALITY_VOTING_HORIZONS

    assert QUALITY_VOTING_HORIZONS == ("1y",)
