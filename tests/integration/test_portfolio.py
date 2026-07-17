"""Portfolio ledger + portfolio intelligence against Postgres.

A hand-computable synthetic portfolio: AAA is opened with a synthetic
opening balance (40 sh, $2,000 basis), topped up with a real buy, and
partially sold FIFO; BBB is a single buy. AAA and BBB share one sector and
a common return driver, so sector concentration and correlation flags are
known by construction. Every lot, gain, weight, and snapshot value is
asserted against Decimals computed in the test, not against the code."""

import json
import math
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from mip.core.config import Settings
from mip.core.db import session_scope
from mip.core.exceptions import ConfigurationError
from mip.domain.enums import GainTerm, InstrumentType, RunStatus, RunType, TxnType
from mip.domain.models import IngestionRun, TradingDay
from mip.features.pipeline import FeaturePipeline
from mip.portfolio.analytics import PortfolioAnalyzer
from mip.portfolio.importers import GenericCsvImporter, ImportService, OpeningBalanceCsvImporter
from mip.portfolio.lots import rebuild_lots
from mip.portfolio.snapshots import SnapshotBuilder
from mip.repositories.instruments import InstrumentRepository
from mip.repositories.portfolio import PortfolioRepository
from mip.repositories.prices import PriceRepository
from tests.integration.test_feature_pipeline import weekdays
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration

START = date(2024, 1, 1)
TODAY = date(2026, 7, 10)
DAYS = weekdays(START, TODAY)
N = len(DAYS)


def _prices(base: float, drift: float, amp: float, phase: float = 0.0) -> list[float]:
    values = [base]
    for i in range(1, N):
        values.append(values[-1] * (1 + drift + amp * math.sin(0.5 * i + phase)))
    return [round(v, 6) for v in values]


AAA = _prices(50.0, 0.0010, 0.004)  # shares one driver with BBB -> high correlation
BBB = _prices(40.0, 0.0005, 0.004)
SPY = _prices(400.0, 0.0004, 0.001)
XLT = _prices(100.0, 0.0004, 0.001, phase=1.0)

OPEN_AT = DAYS[300]
BUY_AAA_AT = DAYS[320]
BUY_BBB_AT = DAYS[330]
SELL_AAA_AT = DAYS[400]


def opening_csv(tmp_path):
    path = tmp_path / "opening.csv"
    path.write_text(
        "symbol,as_of_date,quantity,total_cost_basis,source,notes\n"
        f"AAA,{OPEN_AT},40,2000,webull screenshot,pre-history holdings\n"
    )
    return path


def trades_csv(tmp_path):
    path = tmp_path / "trades.csv"
    path.write_text(
        "type,date,symbol,quantity,price,fees,amount,external_id,note\n"
        f"buy,{BUY_AAA_AT},AAA,60,55,5,-3305,T1,\n"
        f"buy,{BUY_BBB_AT},BBB,50,40,0,-2000,T2,\n"
        f"sell,{SELL_AAA_AT},AAA,30,60,1,1799,T3,\n"
        f"dividend,{DAYS[410]},AAA,,,0,25,T4,\n"
        f"fee,{DAYS[411]},,,,0,-2,T5,\n"
    )
    return path


@pytest.fixture()
def portfolio_env(
    migrated_schema: None,
    session_factory: sessionmaker[Session],
    test_database_url: str,
    tmp_path,
):
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        spy = repo.create_instrument("SPY", InstrumentType.ETF, effective_date=START)
        xlt = repo.create_instrument("XLT", InstrumentType.ETF, effective_date=START)
        sector = repo.get_or_create_sector("Testtech")
        sector.etf_instrument_id = xlt.id
        session.flush()
        industry = repo.get_or_create_industry(sector, "Widgets")
        aaa = repo.create_instrument(
            "AAA", InstrumentType.STOCK, industry=industry, effective_date=START
        )
        bbb = repo.create_instrument(
            "BBB", InstrumentType.STOCK, sector=sector, effective_date=START
        )
        session.add_all(
            TradingDay(exchange="NYSE", calendar_date=d) for d in weekdays(START, date(2026, 7, 31))
        )
        prices = PriceRepository(session)
        for instrument, closes in ((spy, SPY), (xlt, XLT), (aaa, AAA), (bbb, BBB)):
            prices.insert_rows(
                [
                    {
                        "instrument_id": instrument.id,
                        "price_date": d,
                        "close": Decimal(str(c)),
                        "adj_close": Decimal(str(c)),
                        "volume": 1000,
                    }
                    for d, c in zip(DAYS, closes, strict=True)
                ],
                run_id=None,
            )
    return session_factory


def import_everything(factory, tmp_path, portfolio="main") -> None:
    with session_scope(factory) as session:
        PortfolioRepository(session).create_portfolio(portfolio)
        service = ImportService(session)
        service.run(portfolio, OpeningBalanceCsvImporter(), opening_csv(tmp_path))
        service.run(portfolio, GenericCsvImporter(), trades_csv(tmp_path))


# -- ledger ---------------------------------------------------------------------


def test_create_and_duplicate_portfolio(portfolio_env) -> None:
    with session_scope(portfolio_env) as session:
        repo = PortfolioRepository(session)
        portfolio = repo.create_portfolio("main", description="taxable")
        assert portfolio.cost_basis_method == "FIFO"
        with pytest.raises(ConfigurationError, match="already exists"):
            repo.create_portfolio("main")


def test_dry_run_validates_without_writing(portfolio_env, tmp_path) -> None:
    with session_scope(portfolio_env) as session:
        repo = PortfolioRepository(session)
        portfolio = repo.create_portfolio("main")
        report = ImportService(session).run(
            "main", GenericCsvImporter(), trades_csv(tmp_path), dry_run=True
        )
        assert report.dry_run and report.parsed == 5 and report.inserted == 0
        assert repo.transactions(portfolio.id) == []


def test_import_commit_lineage_and_duplicate_prevention(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        repo = PortfolioRepository(session)
        portfolio = repo.require_portfolio("main")
        ledger = repo.transactions(portfolio.id)
        assert len(ledger) == 6  # 1 opening + 5 trades, in replay order
        assert [t.trade_date for t in ledger] == sorted(t.trade_date for t in ledger)
        assert all(t.ingestion_run_id is not None for t in ledger)  # batch lineage
        run = session.get(IngestionRun, ledger[-1].ingestion_run_id)
        assert run.run_type == RunType.PORTFOLIO_IMPORT and run.status == RunStatus.SUCCESS
        assert run.archive_path.endswith("trades.csv")

        # re-importing the same files is a complete no-op
        report = ImportService(session).run("main", GenericCsvImporter(), trades_csv(tmp_path))
        assert report.duplicates == 5 and report.inserted == 0
        assert len(repo.transactions(portfolio.id)) == 6


def test_ledger_is_append_only_at_the_database(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    # unique (portfolio, external_id) is the DB backstop; the broken
    # session is rolled back by session_scope, so raises wraps the scope
    with pytest.raises(IntegrityError), session_scope(portfolio_env) as session:
        repo = PortfolioRepository(session)
        portfolio = repo.require_portfolio("main")
        repo.append_transactions(
            [
                {
                    "portfolio_id": portfolio.id,
                    "txn_type": TxnType.FEE,
                    "trade_date": DAYS[500],
                    "total_amount": Decimal("-1"),
                    "fees": Decimal("0"),
                    "external_id": "T5",
                }
            ]
        )


# -- lots -----------------------------------------------------------------------


def test_fifo_lots_realized_gains_and_determinism(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        lots_written, closures_written = rebuild_lots(session, "main")
        assert (lots_written, closures_written) == (3, 1)

        repo = PortfolioRepository(session)
        portfolio = repo.require_portfolio("main")
        lots = repo.lots(portfolio.id)
        opening, buy_aaa, buy_bbb = lots
        assert opening.cost_basis_per_share == Decimal("50.000000")  # 2000 / 40
        assert opening.quantity_remaining == Decimal("10")  # FIFO sold 30 of 40 first
        assert not opening.is_closed
        assert buy_aaa.cost_basis_per_share == Decimal("55.083333")  # 3305 / 60 w/ fee
        assert buy_aaa.quantity_remaining == Decimal("60")
        assert buy_bbb.quantity_remaining == Decimal("50")

        (closure,) = repo.closures(portfolio.id)
        assert closure.quantity_closed == Decimal("30")
        assert closure.proceeds == Decimal("1799.000000")
        assert closure.cost_basis == Decimal("1500.000000")
        assert closure.realized_gain == Decimal("299.000000")
        assert closure.term == GainTerm.SHORT  # 100 sessions ~ 140 days
        # the closed slice came from the SYNTHETIC opening lot, and the
        # ledger says so permanently
        open_txn = next(
            t for t in repo.transactions(portfolio.id) if t.id == opening.open_transaction_id
        )
        assert open_txn.txn_type == TxnType.OPENING_BALANCE
        assert "SYNTHETIC" in open_txn.note

        def serialize(session_inner):
            r = PortfolioRepository(session_inner)
            p = r.require_portfolio("main")
            return [
                (
                    lot.open_transaction_id,
                    lot.open_date,
                    str(lot.quantity_opened),
                    str(lot.quantity_remaining),
                    str(lot.cost_basis_per_share),
                )
                for lot in r.lots(p.id)
            ], [
                (c.close_date, str(c.quantity_closed), str(c.proceeds), str(c.realized_gain))
                for c in r.closures(p.id)
            ]

        first = serialize(session)
        rebuild_lots(session, "main")  # replaying the same ledger
        assert serialize(session) == first  # ... yields identical projections


def test_oversell_is_rejected_at_rebuild(portfolio_env, tmp_path) -> None:
    path = tmp_path / "oversell.csv"
    path.write_text(
        "type,date,symbol,quantity,price,fees,amount,external_id,note\n"
        f"buy,{DAYS[300]},AAA,5,50,0,-250,O1,\n"
        f"sell,{DAYS[310]},AAA,10,55,0,550,O2,\n"
    )
    with session_scope(portfolio_env) as session:
        PortfolioRepository(session).create_portfolio("shorty")
        ImportService(session).run("shorty", GenericCsvImporter(), path)
        with pytest.raises(ConfigurationError, match="oversell"):
            rebuild_lots(session, "shorty")


# -- snapshots -------------------------------------------------------------------


def test_snapshots_are_reproducible_and_hand_verifiable(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        rebuild_lots(session, "main")
        builder = SnapshotBuilder(session)
        first_changed = builder.build("main")
        assert first_changed > 0
        assert builder.build("main") == 0  # byte-identical rebuild: nothing changes

        repo = PortfolioRepository(session)
        portfolio = repo.require_portfolio("main")
        latest = repo.latest_snapshot_date(portfolio.id)
        rows = repo.snapshots_on(portfolio.id, latest)
        assert len(rows) == 2  # AAA and BBB

        index = DAYS.index(latest)
        by_symbol = {}
        instruments = InstrumentRepository(session)
        for snapshot in rows:
            for symbol in ("AAA", "BBB"):
                if instruments.get_by_symbol(symbol).id == snapshot.instrument_id:
                    by_symbol[symbol] = snapshot
        aaa, bbb = by_symbol["AAA"], by_symbol["BBB"]
        assert aaa.quantity == Decimal("70")  # 40 opening - 30 sold + 60 bought
        assert bbb.quantity == Decimal("50")
        # market value = quantity x adjusted close, straight off the array
        assert aaa.market_value == (Decimal("70") * Decimal(str(AAA[index]))).quantize(
            Decimal("0.000001")
        )
        assert aaa.cost_basis == Decimal("500.000000") + Decimal("3304.999980")
        assert aaa.unrealized_gain == aaa.market_value - aaa.cost_basis
        assert float(aaa.weight) + float(bbb.weight) == pytest.approx(1.0, abs=1e-6)


# -- portfolio intelligence ---------------------------------------------------------


def test_analyze_structure_and_risk(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        assessments = PortfolioAnalyzer(session).analyze("main", with_evidence=False)
        assert [a.symbol for a in assessments] == ["AAA", "BBB"]  # by weight
        aaa, bbb = assessments

        assert aaa.weight_rank == 1 and bbb.weight_rank == 2
        assert aaa.portfolio_weight + bbb.portfolio_weight == pytest.approx(1.0)
        assert aaa.hhi_contribution == pytest.approx(aaa.portfolio_weight**2)
        assert aaa.sector == "Testtech" and aaa.industry == "Widgets"
        assert bbb.sector == "Testtech" and bbb.industry is None
        assert aaa.sector_weight == pytest.approx(1.0)  # both holdings, one sector
        assert any("sector Testtech" in f for f in aaa.concentration_flags)
        assert any("position weight" in f for f in aaa.concentration_flags)

        # shared return driver: the pair must be flagged as duplicated risk
        assert aaa.highest_correlations[0][0] == "BBB"
        assert aaa.highest_correlations[0][1] > 0.9
        assert any("highly correlated with BBB" in f for f in aaa.correlation_flags)

        assert aaa.annualized_volatility is not None and aaa.annualized_volatility > 0
        assert aaa.risk_contribution + bbb.risk_contribution == pytest.approx(1.0)
        assert aaa.marginal_risk_contribution > 0
        assert aaa.diversification_contribution is not None
        assert aaa.current_drawdown is not None and aaa.current_drawdown <= 0
        assert aaa.max_drawdown <= aaa.current_drawdown + 1e-12
        assert aaa.drawdown_contribution is not None
        assert aaa.average_cost == (aaa.cost_basis / aaa.quantity).quantize(Decimal("0.000001"))
        assert not aaa.evidence and not aaa.skipped_models  # evidence disabled


def test_analyze_is_point_in_time(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        analyzer = PortfolioAnalyzer(session)
        early = analyzer.analyze("main", as_of=DAYS[310], with_evidence=False)
        assert [a.symbol for a in early] == ["AAA"]  # BBB not bought yet
        assert early[0].portfolio_weight == pytest.approx(1.0)
        assert early[0].quantity == Decimal("40")  # sell hasn't happened yet
        assert early[0].as_of == DAYS[310]


def test_analyze_consumes_normalized_evidence_only(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    settings = Settings(
        database_url="postgresql+psycopg://ignored/ignored",
        rawdata_root=tmp_path,
        history_start_date=START,
        _env_file=None,
    )
    with session_scope(portfolio_env) as session:
        pipeline = FeaturePipeline(session=session, settings=settings, today=lambda: TODAY)
        run, _ = pipeline.build(["AAA", "BBB", "XLT", "SPY"])
        assert run.status is RunStatus.SUCCESS
    with session_scope(portfolio_env) as session:
        (aaa,) = PortfolioAnalyzer(session).analyze("main", symbols=["AAA"])
        from mip.models.evidence import KNOWN_MODELS

        assert set(aaa.evidence) | set(aaa.skipped_models) == set(KNOWN_MODELS)
        for horizons in aaa.evidence.values():
            assert set(horizons) == {"1w", "2w", "1m", "3m", "6m", "1y"}
            for cell in horizons.values():
                assert {"score", "confidence", "neutral"} <= set(cell)
        # no fundamentals were seeded: valuation must arrive honestly neutral
        assert all(cell["neutral"] for cell in aaa.evidence["valuation"].values())


# -- CLI ------------------------------------------------------------------------------


def test_cli_end_to_end(portfolio_env, tmp_path, monkeypatch, test_database_url, restore_logging):
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    runner = CliRunner()
    assert runner.invoke(app, ["portfolio", "create", "cli"]).exit_code == 0
    listing = runner.invoke(app, ["portfolio", "list"])
    assert "cli" in listing.output

    opening = str(opening_csv(tmp_path))
    trades = str(trades_csv(tmp_path))
    dry = runner.invoke(
        app, ["portfolio", "opening-balances", opening, "--portfolio", "cli", "--dry-run"]
    )
    assert dry.exit_code == 0 and "DRY RUN" in dry.output
    assert (
        runner.invoke(
            app, ["portfolio", "opening-balances", opening, "--portfolio", "cli"]
        ).exit_code
        == 0
    )
    committed = runner.invoke(app, ["portfolio", "import", trades, "--portfolio", "cli"])
    assert committed.exit_code == 0 and "inserted 5" in committed.output

    txns = runner.invoke(app, ["portfolio", "transactions", "--portfolio", "cli"])
    assert txns.exit_code == 0 and "6 transactions" in txns.output

    rebuilt = runner.invoke(app, ["portfolio", "rebuild", "--portfolio", "cli"])
    assert rebuilt.exit_code == 0 and "3 lots" in rebuilt.output

    positions = runner.invoke(app, ["portfolio", "positions", "--portfolio", "cli"])
    assert positions.exit_code == 0 and "AAA" in positions.output and "BBB" in positions.output

    table = runner.invoke(app, ["portfolio", "analyze", "--portfolio", "cli", "--no-evidence"])
    assert table.exit_code == 0, table.output
    assert "AAA" in table.output and "positions as of" in table.output

    as_json = runner.invoke(
        app, ["portfolio", "analyze", "--portfolio", "cli", "--json", "--no-evidence"]
    )
    assert as_json.exit_code == 0, as_json.output
    payload = json.loads(as_json.output[as_json.output.index("[") :])
    assert {p["symbol"] for p in payload} == {"AAA", "BBB"}
    assert all("normalized_evidence_by_model_and_horizon" in p for p in payload)
    assert not any(
        label in json.dumps(payload) for label in ('"hold"', '"trim"', '"sell_label"')
    )  # descriptive only: no recommendation labels in this phase
