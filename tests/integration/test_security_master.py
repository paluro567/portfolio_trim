"""Phase 1 acceptance: point-in-time security master & universe integrity.

Proves survivorship-clean historical identity — a delisted/failed company
remains present in historical reconstruction — plus ticker change/reuse, PIT
resolution, lifecycle events, reproducible universe builds, idempotency,
data-version lineage, and quarantine of ambiguous identity.
"""

from datetime import date

import pytest
from sqlalchemy import func, select

from mip.core.db import session_scope
from mip.domain.enums import (
    IdentifierType,
    LifecycleEventType,
    SecurityType,
)
from mip.domain.models import DataQualityIssue, SecurityMaster
from mip.repositories.securities import SecurityRepository
from mip.securities import (
    US_COMMON_EQUITY_V1,
    FixtureSource,
    SecurityMasterIngestor,
    UniverseBuilder,
    check_security_master,
    check_universe_membership,
)
from mip.securities.source import (
    SourceClassification,
    SourceDelisting,
    SourceIdentifier,
    SourceLifecycleEvent,
    SourceSecurity,
)

pytestmark = pytest.mark.integration
T = IdentifierType.TICKER


def _tick(value, vf, vt=None, exch="NYSE"):
    return SourceIdentifier(T, value, valid_from=vf, valid_to=vt, exchange=exch)


def sample(data_version="v1") -> FixtureSource:
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
        # ticker change OLD -> NEW
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
        # ticker REUSE: a *different* security later takes "OLD"
        SourceSecurity(
            "R2",
            SecurityType.COMMON,
            name="Reuseco",
            primary_exchange="NYSE",
            first_trade_date=date(2021, 1, 1),
            identifiers=(_tick("OLD", date(2021, 1, 1)),),
        ),
        # cash acquisition -> delisted
        SourceSecurity(
            "CASH",
            SecurityType.COMMON,
            name="Cashco",
            primary_exchange="NYSE",
            first_trade_date=date(2016, 1, 1),
            active=False,
            delisted=True,
            delisting_date=date(2019, 3, 15),
            delisting_reason="acquired_cash",
            identifiers=(_tick("CASH", date(2016, 1, 1), date(2019, 3, 15)),),
            delisting=SourceDelisting(date(2019, 3, 15), "M", "acquired_cash"),
            lifecycle_events=(
                SourceLifecycleEvent(LifecycleEventType.ACQUIRED, date(2019, 3, 15)),
            ),
        ),
        # stock acquisition by KEEP
        SourceSecurity(
            "STKA",
            SecurityType.COMMON,
            name="Stockacq",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 6, 1),
            active=False,
            delisted=True,
            delisting_date=date(2019, 6, 1),
            delisting_reason="merged_stock",
            identifiers=(_tick("STKA", date(2015, 6, 1), date(2019, 6, 1)),),
            delisting=SourceDelisting(
                date(2019, 6, 1), "M", "merged_stock", successor_source_id="KEEP"
            ),
            lifecycle_events=(
                SourceLifecycleEvent(
                    LifecycleEventType.MERGED, date(2019, 6, 1), successor_source_id="KEEP"
                ),
            ),
        ),
        # bankruptcy
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
        # exchange transfer NASDAQ -> NYSE
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
        # two share classes (distinct securities)
        SourceSecurity(
            "FOOA",
            SecurityType.COMMON,
            name="Foo A",
            share_class="A",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 1, 1),
            identifiers=(_tick("FOOA", date(2015, 1, 1)),),
        ),
        SourceSecurity(
            "FOOB",
            SecurityType.COMMON,
            name="Foo B",
            share_class="B",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 1, 1),
            identifiers=(_tick("FOOB", date(2015, 1, 1)),),
        ),
        # spin-off
        SourceSecurity(
            "PRNT",
            SecurityType.COMMON,
            name="Parentco",
            primary_exchange="NYSE",
            first_trade_date=date(2013, 1, 1),
            identifiers=(_tick("PRNT", date(2013, 1, 1)),),
        ),
        SourceSecurity(
            "SPIN",
            SecurityType.COMMON,
            name="Spinco",
            primary_exchange="NYSE",
            first_trade_date=date(2020, 1, 1),
            identifiers=(_tick("SPIN", date(2020, 1, 1)),),
            lifecycle_events=(
                SourceLifecycleEvent(
                    LifecycleEventType.SPUN_OFF, date(2020, 1, 1), predecessor_source_id="PRNT"
                ),
            ),
        ),
        # ETF (ineligible type — excluded from universe)
        SourceSecurity(
            "ETF1",
            SecurityType.ETF,
            name="An ETF",
            primary_exchange="NYSE",
            first_trade_date=date(2010, 1, 1),
            identifiers=(_tick("ETF1", date(2010, 1, 1)),),
        ),
        # conflicting identifiers: A and B both claim CUSIP 111 over overlap -> B quarantined
        SourceSecurity(
            "CFA",
            SecurityType.COMMON,
            name="Conflict A",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 1, 1),
            identifiers=(
                _tick("CFA", date(2015, 1, 1)),
                SourceIdentifier(IdentifierType.CUSIP, "111", date(2015, 1, 1)),
            ),
        ),
        SourceSecurity(
            "CFB",
            SecurityType.COMMON,
            name="Conflict B",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 1, 1),
            identifiers=(
                _tick("CFB", date(2015, 1, 1)),
                SourceIdentifier(IdentifierType.CUSIP, "111", date(2016, 1, 1)),
            ),
        ),
        # missing permanent id -> quarantined
        SourceSecurity("", SecurityType.COMMON, name="No id"),
    ]
    return FixtureSource(name="fixture", data_version=data_version, _securities=tuple(secs))


def _ingest(session, data_version="v1"):
    return SecurityMasterIngestor(session).ingest(sample(data_version))


def _sid(session, source_security_id):
    return session.scalar(
        select(SecurityMaster.security_id).where(
            SecurityMaster.source_security_id == source_security_id
        )
    )


# -- tests ---------------------------------------------------------------------


def test_ingest_and_identity(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _run, stats = _ingest(s)
        repo = SecurityRepository(s)
        # 12 valid securities ingested; 2 quarantined (conflict B + missing id)
        assert stats.created == 13
        assert stats.quarantined == 2
        # same ticker
        assert repo.resolve_ticker("KEEP", date(2018, 1, 1)) == _sid(s, "KEEP")
        # ticker change: OLD before 2020-06, NEW after — same security
        r1 = _sid(s, "R1")
        assert repo.resolve_ticker("OLD", date(2018, 1, 1)) == r1
        assert repo.resolve_ticker("NEW", date(2021, 1, 1)) == r1
        assert repo.ticker_as_of(r1, date(2018, 1, 1)) == "OLD"
        assert repo.ticker_as_of(r1, date(2022, 1, 1)) == "NEW"


def test_ticker_reuse_by_different_security(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _ingest(s)
        repo = SecurityRepository(s)
        assert repo.resolve_ticker("OLD", date(2018, 1, 1)) == _sid(s, "R1")
        assert repo.resolve_ticker("OLD", date(2022, 1, 1)) == _sid(s, "R2")
        assert _sid(s, "R1") != _sid(s, "R2")


def test_delisting_and_successors(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _ingest(s)
        repo = SecurityRepository(s)
        delisted = {
            d.security_id for d in repo.delisted_between(date(2018, 1, 1), date(2019, 12, 31))
        }
        assert {_sid(s, x) for x in ("CASH", "STKA", "BUST")} <= delisted
        # stock acquisition successor resolved to KEEP's internal id
        from mip.domain.models import DelistingEvent

        stka = s.get(DelistingEvent, _sid(s, "STKA"))
        assert stka.successor_security_id == _sid(s, "KEEP")
        # bankruptcy lifecycle recorded
        events = repo.lifecycle_as_of(_sid(s, "BUST"), date(2020, 1, 1))
        assert any(e.event_type is LifecycleEventType.BANKRUPT for e in events)
        # spin-off predecessor linked
        spin = repo.lifecycle_as_of(_sid(s, "SPIN"), date(2021, 1, 1))
        assert spin[0].predecessor_security_id == _sid(s, "PRNT")


def test_exchange_transfer_and_classification_pit(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _ingest(s)
        repo = SecurityRepository(s)
        xfer = _sid(s, "XFER")
        idents_16 = repo.identifiers_as_of(xfer, date(2016, 1, 1))
        idents_20 = repo.identifiers_as_of(xfer, date(2020, 1, 1))
        assert idents_16[0].exchange == "NASDAQ"
        assert idents_20[0].exchange == "NYSE"
        # PIT classification
        cls = repo.classification_as_of(_sid(s, "KEEP"), date(2016, 6, 1))
        assert cls is not None and cls.sector == "Information Technology"
        # share classes are distinct securities
        assert _sid(s, "FOOA") != _sid(s, "FOOB")


def test_quarantine_ambiguous_and_missing_id(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        run, _ = _ingest(s)
        issues = list(
            s.scalars(select(DataQualityIssue).where(DataQualityIssue.ingestion_run_id == run.id))
        )
        rules = {i.rule for i in issues}
        assert "ambiguous_identity" in rules
        assert "missing_permanent_id" in rules
        # conflict B was NOT ingested; conflict A was
        assert _sid(s, "CFB") is None
        assert _sid(s, "CFA") is not None


def test_idempotent_reingestion(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _ingest(s)
        from mip.domain.models import SecurityIdentifierHistory

        n_master = s.scalar(select(func.count()).select_from(SecurityMaster))
        n_ident = s.scalar(select(func.count()).select_from(SecurityIdentifierHistory))
        # second ingest of the same snapshot -> updates, no new rows
        _run2, stats2 = _ingest(s)
        assert stats2.created == 0
        assert stats2.updated == 13
        assert s.scalar(select(func.count()).select_from(SecurityMaster)) == n_master
        assert s.scalar(select(func.count()).select_from(SecurityIdentifierHistory)) == n_ident


def test_data_version_lineage(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _ingest(s, data_version="v1")
        keep = s.get(SecurityMaster, _sid(s, "KEEP"))
        assert keep.data_version == "v1"
        _ingest(s, data_version="v2")  # re-ingest with a new snapshot version
        s.expire_all()
        keep = s.get(SecurityMaster, _sid(s, "KEEP"))
        assert keep.data_version == "v2"  # lineage updated, identity preserved


def test_universe_reconstruction_survivorship_and_reproducibility(
    session_factory, migrated_schema
) -> None:
    dates = [date(2016, 6, 30), date(2018, 6, 29), date(2019, 6, 28), date(2022, 6, 30)]
    with session_scope(session_factory) as s:
        _ingest(s)
        builder = UniverseBuilder(s, data_version="v1")
        _run, manifest1 = builder.build(US_COMMON_EQUITY_V1, dates)
        defn_id = manifest1["universe_definition_id"]
        repo = SecurityRepository(s)

        # SURVIVORSHIP: a bankrupt, inactive-today company is present historically
        members_2016 = {m.security_id for m in repo.members_as_of(defn_id, date(2016, 6, 30))}
        assert _sid(s, "BUST") in members_2016  # delisted 2018 but alive in 2016
        # membership never extends past delisting
        assert _sid(s, "CASH") in {
            m.security_id for m in repo.members_as_of(defn_id, date(2018, 6, 29))
        }
        assert _sid(s, "CASH") not in {
            m.security_id for m in repo.members_as_of(defn_id, date(2019, 6, 28))
        }
        # membership before listing excluded (SPIN listed 2020 -> not a 2016 member)
        assert _sid(s, "SPIN") not in members_2016
        # ETFs excluded (ineligible type)
        assert _sid(s, "ETF1") not in members_2016
        # eligibility helper requires an as-of date
        assert repo.is_eligible(defn_id, _sid(s, "KEEP"), date(2018, 6, 29)) is True

        # REPRODUCIBILITY: rebuild with the same frozen definition + data -> same checksum
        _run2, manifest2 = builder.build(US_COMMON_EQUITY_V1, dates)
        assert manifest2["checksum"] == manifest1["checksum"]

        # data-quality: no membership-after-delisting or before-listing findings
        assert check_universe_membership(s, defn_id) == []
        assert check_security_master(s) == []
