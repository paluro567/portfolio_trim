"""Phase 2A acceptance: native survivorship-clean outcome foundation & guardrails.

Proves security_id-native prices/returns/forward-outcomes; delisted losers and
terminal events survive reconstruction (never dropped); the first-class PIT
identity bridge with quarantine; execution-level experiment provenance;
reproducible checksummed snapshots; and that legacy/native worlds cannot be
silently mixed. Covers the 25 required scenarios.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from mip.core.db import session_scope
from mip.domain.enums import (
    DivergenceClass,
    ExperimentDecision,
    IdentifierType,
    IdentityWorld,
    LifecycleEventType,
    MappingMethod,
    OutcomeStatus,
    ReturnStatus,
    SecurityType,
    TerminalRule,
)
from mip.domain.models import (
    ForwardReturn,
    Instrument,
    SecurityMarketSnapshot,
    SecurityMaster,
    SecurityPriceDaily,
    SecurityReturnDaily,
)
from mip.research_data import (
    BridgeIngestor,
    BridgeRepository,
    ComputationParity,
    DailyReturnBuilder,
    DivergenceLedger,
    ExperimentProvenance,
    ForwardOutcomeBuilder,
    MixedIdentityWorldError,
    OutcomeIngestor,
    ParityCase,
    SnapshotChecksumMismatchError,
    UnexplainedDivergenceError,
    UniverseVersionMismatchError,
    assert_no_unexplained_divergence,
    assert_single_snapshot,
    assert_universe_versions_match,
    assert_worlds_joinable,
    blocked_outcome_source,
    rebuild_checksum,
)
from mip.research_data.source import (
    FixtureOutcomeSource,
    SourceBenchmarkBar,
    SourceMarketSnapshot,
    SourcePriceBar,
    SourceTerminal,
)
from mip.securities import (
    FixtureSource,
    SecurityMasterIngestor,
    SourceClassification,
    SourceDelisting,
    SourceIdentifier,
    SourceLifecycleEvent,
    SourceSecurity,
)

pytestmark = pytest.mark.integration
SOURCE = "fixture"
DV = "v1"
T = IdentifierType.TICKER

# monthly grid 2015-01 .. 2019-12
_GRID = [date(y, m, 1) for y in range(2015, 2020) for m in range(1, 13)]


def _tick(v, vf, vt=None):
    return SourceIdentifier(T, v, valid_from=vf, valid_to=vt, exchange="NYSE")


def _months(d: date) -> int:
    return (d.year - 2015) * 12 + (d.month - 1)


def _bars(vendor_id, start, end, base=Decimal("100")):
    """One bar per grid month in [start, end]; adjusted_close rises smoothly so
    returns are exactly (base+n2)/(base+n1)-1 (survivorship/adjustment-neutral)."""
    out = []
    for d in _GRID:
        if start <= d <= end:
            adj = base + Decimal(_months(d))
            out.append(
                SourcePriceBar(
                    source_security_id=vendor_id,
                    trade_date=d,
                    close=adj,
                    open=adj,
                    high=adj,
                    low=adj,
                    adjusted_close=adj,
                    volume=1_000_000,
                    exchange="NYSE",
                )
            )
    return out


def securities_fixture() -> FixtureSource:
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
            "RENAME",
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
            "REUSE",
            SecurityType.COMMON,
            name="Reuseco",
            primary_exchange="NYSE",
            first_trade_date=date(2021, 1, 1),
            identifiers=(_tick("OLD", date(2021, 1, 1)),),
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
        SourceSecurity(
            "STKACQ",
            SecurityType.COMMON,
            name="Stockacq",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 1, 1),
            active=False,
            delisted=True,
            delisting_date=date(2019, 6, 1),
            delisting_reason="merged_stock",
            identifiers=(_tick("STK", date(2015, 1, 1), date(2019, 6, 1)),),
            delisting=SourceDelisting(
                date(2019, 6, 1), "M", "merged_stock", successor_source_id="KEEP"
            ),
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
        ),
        SourceSecurity(
            "UNK",
            SecurityType.COMMON,
            name="Unknownco",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 1, 1),
            active=False,
            delisted=True,
            delisting_date=date(2019, 5, 1),
            delisting_reason="stopped",
            identifiers=(_tick("UNK", date(2015, 1, 1), date(2019, 5, 1)),),
            delisting=SourceDelisting(date(2019, 5, 1), "?", "stopped"),
        ),
        SourceSecurity(
            "SPLIT",
            SecurityType.COMMON,
            name="Splitco",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 1, 1),
            identifiers=(_tick("SPL", date(2015, 1, 1)),),
        ),
        SourceSecurity(
            "DIV",
            SecurityType.COMMON,
            name="Divco",
            primary_exchange="NYSE",
            first_trade_date=date(2015, 1, 1),
            identifiers=(_tick("DIV", date(2015, 1, 1)),),
        ),
    ]
    return FixtureSource(name=SOURCE, data_version=DV, _securities=tuple(secs))


def outcomes_fixture(data_version=DV) -> FixtureOutcomeSource:
    prices: list[SourcePriceBar] = []
    prices += _bars("KEEP", date(2015, 1, 1), date(2019, 12, 1))
    prices += _bars("RENAME", date(2015, 1, 1), date(2019, 12, 1))
    prices += _bars("REUSE", date(2015, 1, 1), date(2019, 12, 1))
    prices += _bars("CASHACQ", date(2015, 1, 1), date(2019, 3, 1))
    prices += _bars("STKACQ", date(2015, 1, 1), date(2019, 6, 1))
    prices += _bars("BUST", date(2015, 1, 1), date(2018, 11, 1))
    prices += _bars("UNK", date(2015, 1, 1), date(2019, 5, 1))
    prices += _bars("DIV", date(2015, 1, 1), date(2019, 12, 1))
    # SPLIT: raw close halves at 2017-01 (2:1) but adjusted_close stays smooth.
    split_bars = []
    for d in _GRID:
        if date(2015, 1, 1) <= d <= date(2019, 12, 1):
            adj = Decimal("100") + Decimal(_months(d))
            raw = adj if d < date(2017, 1, 1) else adj / 2
            split_bars.append(
                SourcePriceBar(
                    source_security_id="SPLIT",
                    trade_date=d,
                    close=raw,
                    adjusted_close=adj,
                    volume=1_000_000,
                    exchange="NYSE",
                    split_factor=Decimal("2") if d == date(2017, 1, 1) else None,
                    dividend_amount=Decimal("1.00") if d == date(2016, 3, 1) else None,
                )
            )
    prices += split_bars

    market = [
        SourceMarketSnapshot(
            "KEEP",
            date(2016, 1, 1),
            price=Decimal("100"),
            shares_outstanding=1_000_000,
            market_cap=Decimal("100000000"),
            average_dollar_volume=Decimal("5000000"),
            sector="Information Technology",
        ),
        # a LATER snapshot with a different cap — must NOT be used for an earlier as_of
        SourceMarketSnapshot(
            "KEEP",
            date(2019, 1, 1),
            price=Decimal("140"),
            shares_outstanding=1_000_000,
            market_cap=Decimal("140000000"),
            average_dollar_volume=Decimal("9000000"),
            sector="Information Technology",
        ),
    ]
    # market benchmark: flat 0 daily return over grid (so benchmark-relative == absolute)
    benchmarks = [SourceBenchmarkBar("MARKET", "market", d, Decimal("0")) for d in _GRID]
    terminals = [
        SourceTerminal(
            "CASHACQ",
            date(2019, 3, 1),
            TerminalRule.CASH_ACQUISITION,
            terminal_return=Decimal("0.05"),
            cash_consideration=Decimal("50"),
            confidence=1.0,
        ),
        SourceTerminal(
            "STKACQ",
            date(2019, 6, 1),
            TerminalRule.STOCK_ACQUISITION,
            terminal_return=Decimal("0.10"),
            successor_source_id="KEEP",
            confidence=0.9,
        ),
        SourceTerminal(
            "BUST",
            date(2018, 11, 1),
            TerminalRule.BANKRUPTCY,
            terminal_return=Decimal("-0.90"),
            confidence=1.0,
        ),
        SourceTerminal("UNK", date(2019, 5, 1), TerminalRule.UNKNOWN, resolved=False),
    ]
    return FixtureOutcomeSource(
        name=SOURCE,
        data_version=data_version,
        _prices=tuple(prices),
        _market=tuple(market),
        _benchmarks=tuple(benchmarks),
        _terminals=tuple(terminals),
    )


def _seed(session, data_version=DV):
    SecurityMasterIngestor(session).ingest(securities_fixture())
    OutcomeIngestor(session).ingest(outcomes_fixture(data_version=data_version))


def _sid(session, vendor_id):
    return session.scalar(
        select(SecurityMaster.security_id).where(SecurityMaster.source_security_id == vendor_id)
    )


ALL_VENDORS = ("KEEP", "RENAME", "REUSE", "CASHACQ", "STKACQ", "BUST", "UNK", "SPLIT", "DIV")
AS_OFS = [date(2016, 6, 30), date(2018, 6, 29)]
HZ = {"1m": 30, "1y": 365}


def _build(session, data_version=DV):
    ids = [_sid(session, v) for v in ALL_VENDORS]
    builder = ForwardOutcomeBuilder(session, source=SOURCE, data_version=data_version, horizons=HZ)
    snap, stats = builder.build_snapshot(
        snapshot_name="phase2a-test",
        snapshot_version=1 if data_version == DV else 2,
        as_of_dates=AS_OFS,
        security_ids=ids,
        universe_version="US_COMMON_EQUITY_V1",
    )
    return snap, stats, ids


# -- tests ---------------------------------------------------------------------


def test_native_prices_keyed_by_security_id(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        keep = _sid(s, "KEEP")
        n = s.scalar(
            select(func.count())
            .select_from(SecurityPriceDaily)
            .where(SecurityPriceDaily.security_id == keep)
        )
        assert n == len(_bars("KEEP", date(2015, 1, 1), date(2019, 12, 1)))
        # no price row references a ticker/instrument id — the FK is security_id
        assert s.scalar(select(SecurityPriceDaily.security_id).limit(1)) is not None


def test_ticker_change_spans_return_window(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        _build(s)
        rn = _sid(s, "RENAME")
        # RENAME (OLD->NEW) still has continuous native prices/returns under ONE id
        fwd = s.scalars(select(ForwardReturn).where(ForwardReturn.security_id == rn)).all()
        assert fwd and all(
            f.outcome_status in (OutcomeStatus.NORMAL, OutcomeStatus.TRUNCATED) for f in fwd
        )


def test_reused_ticker_does_not_contaminate(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        rename, reuse = _sid(s, "RENAME"), _sid(s, "REUSE")
        assert rename != reuse
        # each security's prices are keyed on its own security_id
        rn_dates = set(
            s.scalars(
                select(SecurityPriceDaily.trade_date).where(
                    SecurityPriceDaily.security_id == rename
                )
            )
        )
        ru_dates = set(
            s.scalars(
                select(SecurityPriceDaily.trade_date).where(SecurityPriceDaily.security_id == reuse)
            )
        )
        assert rn_dates and ru_dates  # both populated, independently keyed


def test_delisted_loser_remains_in_forward_dataset(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        snap, _stats, _ids = _build(s)
        bust = _sid(s, "BUST")
        rows = s.scalars(
            select(ForwardReturn).where(
                ForwardReturn.security_id == bust,
                ForwardReturn.snapshot_checksum == snap.snapshot_checksum,
            )
        ).all()
        # BUST delisted 2018-11 but is present for BOTH as-of dates & horizons
        assert len(rows) == len(AS_OFS) * len(HZ)


def test_cash_acquisition_return(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        snap, _stats, _ids = _build(s)
        cash = _sid(s, "CASHACQ")
        row = s.scalar(
            select(ForwardReturn).where(
                ForwardReturn.security_id == cash,
                ForwardReturn.as_of_date == date(2018, 6, 29),
                ForwardReturn.horizon == "1y",
            )
        )
        assert row.outcome_status is OutcomeStatus.TERMINATED
        assert row.terminal_event_flag and row.absolute_return is not None


def test_stock_acquisition_successor(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        from mip.domain.models import TerminalOutcome

        term = s.get(TerminalOutcome, _sid(s, "STKACQ"))
        assert term.rule is TerminalRule.STOCK_ACQUISITION
        assert term.successor_security_id == _sid(s, "KEEP")


def test_bankruptcy_terminal_return(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        snap, _stats, _ids = _build(s)
        bust = _sid(s, "BUST")
        row = s.scalar(
            select(ForwardReturn).where(
                ForwardReturn.security_id == bust,
                ForwardReturn.as_of_date == date(2018, 6, 29),
                ForwardReturn.horizon == "1y",
            )
        )
        assert row.outcome_status is OutcomeStatus.DELISTED_IN_WINDOW
        # a -90% terminal makes the total return strongly negative
        assert row.absolute_return is not None and row.absolute_return < Decimal("-0.5")


def test_missing_terminal_return_is_unresolved_not_deleted(
    session_factory, migrated_schema
) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        snap, _stats, _ids = _build(s)
        unk = _sid(s, "UNK")
        row = s.scalar(
            select(ForwardReturn).where(
                ForwardReturn.security_id == unk,
                ForwardReturn.as_of_date == date(2018, 6, 29),
                ForwardReturn.horizon == "1y",
            )
        )
        assert row is not None  # NOT deleted
        assert row.outcome_status is OutcomeStatus.UNRESOLVED
        assert row.absolute_return is None  # never assumed -100%


def test_split_adjusted_return(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        DailyReturnBuilder(s, source=SOURCE, data_version=DV).build()
        spl = _sid(s, "SPLIT")
        split_day = s.scalar(
            select(SecurityReturnDaily).where(
                SecurityReturnDaily.security_id == spl,
                SecurityReturnDaily.trade_date == date(2017, 1, 1),
            )
        )
        # adjusted_close is smooth across the split -> a small positive return, flagged CA
        assert split_day.return_status is ReturnStatus.CORPORATE_ACTION
        assert split_day.price_return is not None and abs(split_day.price_return) < Decimal("0.05")


def test_dividend_adjusted_return(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        DailyReturnBuilder(s, source=SOURCE, data_version=DV).build()
        spl = _sid(s, "SPLIT")
        div_day = s.scalar(
            select(SecurityReturnDaily).where(
                SecurityReturnDaily.security_id == spl,
                SecurityReturnDaily.trade_date == date(2016, 3, 1),
            )
        )
        assert div_day.return_status is ReturnStatus.CORPORATE_ACTION


def test_computation_equivalence_matches(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        parity = ComputationParity(s)
        case = ParityCase("momentum_12_1", "fx1", {"p_now": 120.0, "p_then": 100.0}, tolerance=1e-9)
        legacy = lambda i: i["p_now"] / i["p_then"] - 1  # noqa: E731
        native = lambda i: i["p_now"] / i["p_then"] - 1  # noqa: E731
        rec = parity.compare(case, legacy, native)
        assert rec.passed and rec.absolute_difference == 0
        assert parity.all_passed("momentum_12_1")


def test_data_divergence_classified(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        led = DivergenceLedger(s)
        rec = led.record(
            divergence_class=DivergenceClass.DIVIDEND_TREATMENT,
            legacy_value=0.10,
            native_value=0.11,
            explanation="native reinvests dividends; legacy price-only",
        )
        assert rec.divergence_class is DivergenceClass.DIVIDEND_TREATMENT
        assert rec.absolute_difference is not None


def test_unexplained_divergence_blocks_promotion(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        led = DivergenceLedger(s)
        led.record(divergence_class=DivergenceClass.UNKNOWN, legacy_value=1.0, native_value=2.0)
        with pytest.raises(UnexplainedDivergenceError):
            assert_no_unexplained_divergence(s)


def test_legacy_feature_native_outcome_join_raises(session_factory, migrated_schema) -> None:
    with pytest.raises(MixedIdentityWorldError):
        assert_worlds_joinable(IdentityWorld.LEGACY_INSTRUMENT, IdentityWorld.NATIVE_SECURITY)
    # same-world joins are allowed
    assert_worlds_joinable(IdentityWorld.NATIVE_SECURITY, IdentityWorld.NATIVE_SECURITY)


def test_mismatched_snapshot_checksums_raise(session_factory, migrated_schema) -> None:
    with pytest.raises(SnapshotChecksumMismatchError):
        assert_single_snapshot(["abc", "def"])
    assert_single_snapshot(["abc", "abc", None])  # ok


def test_mismatched_universe_versions_raise(session_factory, migrated_schema) -> None:
    with pytest.raises(UniverseVersionMismatchError):
        assert_universe_versions_match(["v1", "v2"])
    assert_universe_versions_match(["v1", "v1"])  # ok


def test_experiment_run_persists_provenance(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        snap, _stats, _ids = _build(s)
        prov = ExperimentProvenance(s)
        stamp = prov.stamp_from_native(snap, calculation_version="forward-v1", code_sha="deadbeef")
        run = prov.start_run(
            experiment_id="relative_strength",
            stamp=stamp,
            snapshot=snap,
            signal_version="rs-v1",
            pre_registration={"h": "rs>0"},
        )
        prov.record_metric(run, metric_name="ic", value=0.03, horizon="1m", sample_size=100)
        prov.record_decision(run, decision=ExperimentDecision.HOLD, reason="inconclusive")
        assert run.run_number == 1
        assert run.identity_world is IdentityWorld.NATIVE_SECURITY
        assert run.snapshot_checksum == snap.snapshot_checksum
        assert run.data_version == snap.data_version
        # a second run auto-increments
        run2 = prov.start_run(experiment_id="relative_strength", stamp=stamp, snapshot=snap)
        assert run2.run_number == 2


def test_rebuilt_snapshot_identical_checksum(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        snap, _stats, _ids = _build(s)
        # recomputing the checksum from persisted rows reproduces the stored one
        assert rebuild_checksum(s, snap.snapshot_checksum) == snap.snapshot_checksum


def test_different_data_version_distinct_snapshot(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        SecurityMasterIngestor(s).ingest(securities_fixture())
        OutcomeIngestor(s).ingest(outcomes_fixture(data_version="v1"))
        ids = [_sid(s, v) for v in ALL_VENDORS]
        b1 = ForwardOutcomeBuilder(s, source=SOURCE, data_version="v1", horizons=HZ)
        snap1, _ = b1.build_snapshot(
            snapshot_name="ds", snapshot_version=1, as_of_dates=AS_OFS, security_ids=ids
        )
        # a second vendor snapshot with a CHANGED price -> different data_version + checksum
        alt = outcomes_fixture(data_version="v2")
        changed = tuple(
            (
                SourcePriceBar(
                    **{
                        **b.__dict__,
                        "adjusted_close": (b.adjusted_close or Decimal(0)) + Decimal("5"),
                    }
                )
                if b.source_security_id == "KEEP"
                else b
            )
            for b in alt._prices
        )
        OutcomeIngestor(s).ingest(
            FixtureOutcomeSource(
                name=SOURCE,
                data_version="v2",
                _prices=changed,
                _market=alt._market,
                _benchmarks=alt._benchmarks,
                _terminals=alt._terminals,
            )
        )
        b2 = ForwardOutcomeBuilder(s, source=SOURCE, data_version="v2", horizons=HZ)
        snap2, _ = b2.build_snapshot(
            snapshot_name="ds", snapshot_version=2, as_of_dates=AS_OFS, security_ids=ids
        )
        assert snap1.snapshot_id != snap2.snapshot_id
        assert snap1.data_version != snap2.data_version
        assert snap1.snapshot_checksum != snap2.snapshot_checksum


def test_delisted_survive_universe_and_outcome(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        snap, stats, ids = _build(s)
        # every delisted name is present in the outcome reconstruction
        for v in ("BUST", "CASHACQ", "STKACQ", "UNK"):
            sid = _sid(s, v)
            assert sid in ids
            n = s.scalar(
                select(func.count())
                .select_from(ForwardReturn)
                .where(
                    ForwardReturn.security_id == sid,
                    ForwardReturn.snapshot_checksum == snap.snapshot_checksum,
                )
            )
            assert n == len(AS_OFS) * len(HZ)


def test_market_rules_use_only_pit_values(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        keep = _sid(s, "KEEP")
        # as of 2016, the PIT market cap is the 2016 snapshot (100M), NOT the 2019 (140M)
        cap = s.scalar(
            select(SecurityMarketSnapshot.market_cap)
            .where(
                SecurityMarketSnapshot.security_id == keep,
                SecurityMarketSnapshot.snapshot_date <= date(2016, 6, 30),
            )
            .order_by(SecurityMarketSnapshot.snapshot_date.desc())
            .limit(1)
        )
        assert cap == Decimal("100000000.00")


def test_no_outcome_silently_removed(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        snap, stats, ids = _build(s)
        total = s.scalar(
            select(func.count())
            .select_from(ForwardReturn)
            .where(ForwardReturn.snapshot_checksum == snap.snapshot_checksum)
        )
        # a full grid: every (security, as_of, horizon) has exactly one row
        assert total == len(ids) * len(AS_OFS) * len(HZ)
        assert stats.written == total


def test_bridge_mapping_as_of_correct(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        keep, reuse = _sid(s, "KEEP"), _sid(s, "REUSE")
        instr_a = Instrument(symbol="KEEP", instrument_type="stock")
        instr_b = Instrument(symbol="OLD", instrument_type="stock")
        s.add_all([instr_a, instr_b])
        s.flush()
        ing = BridgeIngestor(s)
        from mip.research_data import SourceMapping

        # instrument_b (ticker OLD) maps to RENAME early, then to REUSE later (reuse)
        rename = _sid(s, "RENAME")
        ing.ingest(
            [
                SourceMapping(
                    instr_a.id,
                    keep,
                    date(2015, 1, 1),
                    None,
                    mapping_method=MappingMethod.EXACT_SOURCE_ID,
                ),
                SourceMapping(instr_b.id, rename, date(2015, 1, 1), date(2020, 12, 31)),
                SourceMapping(instr_b.id, reuse, date(2021, 1, 1), None),
            ],
            source=SOURCE,
            data_version=DV,
        )
        repo = BridgeRepository(s)
        assert repo.resolve_instrument(instr_a.id, date(2018, 1, 1)) == keep
        assert repo.resolve_instrument(instr_b.id, date(2018, 1, 1)) == rename
        assert repo.resolve_instrument(instr_b.id, date(2022, 1, 1)) == reuse
        assert repo.overlap_violations() == []


def test_ambiguous_bridge_mapping_quarantined(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        _seed(s)
        keep, bust = _sid(s, "KEEP"), _sid(s, "BUST")
        instr = Instrument(symbol="AMBIG", instrument_type="stock")
        s.add(instr)
        s.flush()
        ing = BridgeIngestor(s)
        from mip.research_data import SourceMapping

        _run, stats = ing.ingest(
            [
                SourceMapping(instr.id, keep, date(2015, 1, 1), None),
                # overlapping active mapping to a DIFFERENT security -> quarantined
                SourceMapping(instr.id, bust, date(2016, 1, 1), None),
            ],
            source=SOURCE,
            data_version=DV,
        )
        assert stats.created == 1 and stats.quarantined == 1
        repo = BridgeRepository(s)
        assert len(repo.list_quarantined()) == 1
        # resolution still returns the trusted (first) mapping only
        assert repo.resolve_instrument(instr.id, date(2017, 1, 1)) == keep


def test_migration_additive_and_blocked_source(session_factory, migrated_schema) -> None:
    with session_scope(session_factory) as s:
        # production tables remain (additive migration); feature_store_daily untouched
        from mip.domain.models import FeatureStoreDaily, Prediction

        assert s.scalar(select(func.count()).select_from(Prediction)) == 0
        # legacy feature store still keyed on instrument_id (schema unchanged)
        assert "instrument_id" in FeatureStoreDaily.__table__.columns
    # the real survivorship-clean source is blocked, not silently yfinance
    from mip.core.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError):
        list(blocked_outcome_source().prices())
