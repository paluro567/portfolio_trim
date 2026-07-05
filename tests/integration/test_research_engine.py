"""Phase 6 gate tests: the Historical Research Engine against Postgres.

Reuses the Phase 5 fixture: TEST1/SPY/XLT with linear closes, DGS10 rising
0.01/day (lag 1), a one-day VIX spike to 30 on 2026-06-01 (lag 1), and a
reported earnings beat on 2026-05-06 (actual 1.5 vs estimate 1.4)."""

from datetime import date

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from mip.core.db import session_scope
from mip.core.exceptions import ConfigurationError
from mip.domain.models import FeatureDefinition, FeatureStoreMarketDaily
from mip.research import (
    ResearchEngine,
    ResearchFilter,
    ResearchQuery,
    ResearchWindow,
    SampleMode,
)
from tests.integration.test_feature_pipeline import (  # noqa: F401
    PRICE_DAYS,
    build,
    close_for,
    env,
    value_of,
)

pytestmark = pytest.mark.integration

VIX_EVENT = date(2026, 6, 2)  # spike OBSERVED 2026-06-01, public one day later


def run_query(env, symbol, filters, mode=SampleMode.EVENTS, horizons=(1, 5), window=None):
    factory, _ = env
    with session_scope(factory) as session:
        query = ResearchQuery(
            symbol=symbol,
            filters=filters,
            window=window or ResearchWindow(),
            horizons=horizons,
            mode=mode,
        )
        return ResearchEngine(session).run(query)


def test_event_dates_respect_publication_lag(env) -> None:
    """THE look-ahead regression: the VIX spike was observed 2026-06-01 but
    published (lag 1) on 06-02 — the event must fall on 06-02."""
    build(env, ["TEST1"])
    result = run_query(env, "TEST1", (ResearchFilter("vix_level", ">", 25.0),))

    assert result.event_dates == (VIX_EVENT,)
    assert date(2026, 6, 1) not in result.event_dates


def test_forward_returns_golden(env) -> None:
    build(env, ["TEST1"])
    result = run_query(env, "TEST1", (ResearchFilter("vix_level", ">", 25.0),))

    i = PRICE_DAYS.index(VIX_EVENT)
    fwd_1 = close_for("TEST1", i + 1) / close_for("TEST1", i) - 1
    fwd_5 = close_for("TEST1", i + 5) / close_for("TEST1", i) - 1
    assert result.metrics[1].sample_size == 1
    assert result.metrics[1].mean == pytest.approx(fwd_1, abs=1e-10)
    assert result.metrics[5].mean == pytest.approx(fwd_5, abs=1e-10)


def test_episode_collapsing_vs_all_days(env) -> None:
    """DGS10 rises 0.01/session forever -> one long rising-rate episode:
    mode=events yields exactly one sample; mode=all yields every stored
    regime==1 day that is also a price day (correct sample selection)."""
    build(env, ["TEST1"])
    filters = (ResearchFilter("regime_rising_rates", "==", 1.0),)

    events = run_query(env, "TEST1", filters, mode=SampleMode.EVENTS)
    all_days = run_query(env, "TEST1", filters, mode=SampleMode.ALL)

    factory, _ = env
    with session_scope(factory) as session:
        stored = session.scalars(
            select(FeatureStoreMarketDaily.feature_date)
            .join(
                FeatureDefinition,
                FeatureDefinition.id == FeatureStoreMarketDaily.feature_id,
            )
            .where(
                FeatureDefinition.name == "regime_rising_rates",
                FeatureStoreMarketDaily.value == 1,
            )
        ).all()
    expected = sorted(set(stored) & set(PRICE_DAYS))

    assert len(events.event_dates) == 1
    assert events.event_dates[0] == expected[0]
    assert list(all_days.event_dates) == expected


def test_multiple_filters_are_anded(env) -> None:
    build(env, ["TEST1"])
    result = run_query(
        env,
        "TEST1",
        (
            ResearchFilter("vix_level", ">", 25.0),
            ResearchFilter("regime_rising_rates", "==", 1.0),
        ),
        mode=SampleMode.ALL,
    )
    assert result.event_dates == (VIX_EVENT,)  # spike day inside the rising episode


def test_window_bounds_events_not_outcomes(env) -> None:
    build(env, ["TEST1"])
    result = run_query(
        env,
        "TEST1",
        (ResearchFilter("vix_level", ">", 25.0),),
        window=ResearchWindow(start=date(2026, 6, 1), end=date(2026, 6, 3)),
        horizons=(21,),
    )
    # event inside the window; its 21-session outcome resolves after window.end
    assert result.event_dates == (VIX_EVENT,)
    assert result.metrics[21].sample_size == 1


def test_eps_surprise_beat_is_pit_safe(env) -> None:
    build(env, ["TEST1"])
    # feature absent before the report, present from the event date
    assert value_of(env, "eps_surprise", date(2026, 5, 5), "TEST1") is None
    assert value_of(env, "eps_surprise", date(2026, 5, 6), "TEST1") == pytest.approx(
        (1.5 - 1.4) / 1.4, abs=1e-8
    )

    result = run_query(env, "TEST1", (ResearchFilter("eps_surprise", ">", 0.0),))
    assert result.event_dates[0] == date(2026, 5, 6)  # beat event = report date


def test_cross_symbol_filter_reads_other_instrument(env) -> None:
    build(env, ["TEST1", "XLT"])
    # XLT rises linearly -> its ret_21d is positive from its first stored day
    result = run_query(
        env,
        "TEST1",
        (ResearchFilter("ret_21d", ">", 0.0, symbol="XLT"),),
    )
    assert len(result.event_dates) == 1
    assert result.event_dates[0] == PRICE_DAYS[21]  # first day XLT ret_21d exists


def test_baseline_covers_all_eligible_days(env) -> None:
    build(env, ["TEST1"])
    result = run_query(env, "TEST1", (ResearchFilter("vix_level", ">", 25.0),), horizons=(1,))
    # vix_level is evaluable from the 2nd price day (lag 1) -> eligible = N-1
    assert result.eligible_days == len(PRICE_DAYS) - 1
    # the last eligible day has no next price -> baseline n = eligible - 1
    assert result.baseline[1].sample_size == result.eligible_days - 1
    assert result.baseline[1].hit_rate == pytest.approx(1.0)  # prices only rise


def test_results_are_reproducible(env) -> None:
    build(env, ["TEST1"])
    filters = (ResearchFilter("regime_rising_rates", "==", 1.0),)
    first = run_query(env, "TEST1", filters, mode=SampleMode.ALL, horizons=(1, 5, 21))
    second = run_query(env, "TEST1", filters, mode=SampleMode.ALL, horizons=(1, 5, 21))
    assert first.to_dict() == second.to_dict()


def test_unknown_symbol_and_feature_fail_loudly(env) -> None:
    build(env, ["TEST1"])
    with pytest.raises(ConfigurationError, match="unknown symbol"):
        run_query(env, "NOPE", (ResearchFilter("vix_level", ">", 25.0),))
    with pytest.raises(ConfigurationError, match="unknown feature"):
        run_query(env, "TEST1", (ResearchFilter("not_a_feature", ">", 0.0),))


@pytest.fixture()
def restore_logging():
    """The CLI configures structlog against CliRunner's captured stderr,
    which click closes after invoke; rebind to the real stream afterward
    so later tests don't log into a closed file."""
    yield
    from mip.core.logging import configure_logging

    configure_logging()


def test_cli_export_csv_and_json(
    env, tmp_path, monkeypatch, test_database_url, restore_logging
) -> None:
    build(env, ["TEST1"])
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    runner = CliRunner()
    csv_path = tmp_path / "study.csv"
    result = runner.invoke(
        app,
        ["research", "export", "TEST1", "-f", "vix_level > 25", "--out", str(csv_path)],
    )
    assert result.exit_code == 0, result.output
    lines = csv_path.read_text().strip().splitlines()
    assert lines[0].startswith("event_date,fwd_1d,fwd_5d")
    assert lines[1].startswith("2026-06-02,")

    json_path = tmp_path / "study.json"
    result = runner.invoke(
        app,
        ["research", "export", "TEST1", "-f", "vix_level > 25", "--out", str(json_path)],
    )
    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(json_path.read_text())
    assert payload["sample_size"] == 1
    assert payload["event_dates"] == ["2026-06-02"]
    assert "metrics" in payload and "baseline" in payload
