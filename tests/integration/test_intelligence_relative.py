"""Relative Strength Model gate tests against Postgres.

SPY grinds up steadily; XLR (the mapped sector ETF) persistently trails
SPY, so stock leadership is always "solo" breadth-wise. Two stocks with
opposite leadership physics, strengths escalating INTO the present so
"top decile of its own history" holds at the chosen as_ofs without ties:

  RS1 persistent leader: 130-session leadership runs (+0.55%/day) separated
      by 130 quiet sessions; history ends 110 sessions into the strongest
      run — leadership has always persisted, so scores must sit above
      neutral.
  RS2 mean-reverting leader: 70-session bursts (+0.9%/day) that roll into
      60-session givebacks (-0.6%/day, deepest most recently); history ends
      66 sessions into the strongest burst — by 3m every previous burst had
      rolled over. Early-burst and early-giveback as_ofs exercise emerging
      leadership and the leadership-cracking (false-breakout) signature."""

import math
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from mip.core.config import Settings
from mip.core.db import session_scope
from mip.domain.enums import InstrumentType, RunStatus
from mip.domain.models import TradingDay
from mip.features.pipeline import FeaturePipeline
from mip.models.relative import HORIZONS, RelativeStrengthModel
from mip.repositories.instruments import InstrumentRepository
from mip.repositories.prices import PriceRepository
from tests.integration.test_feature_pipeline import weekdays
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration

START = date(2019, 1, 1)
TODAY = date(2026, 7, 10)
DAYS = weekdays(START, TODAY)
N = len(DAYS)

SPY_DRIFT = 0.0010


def _schedule(tail: tuple[int, str], repeating: list[tuple[int, str]]) -> list[tuple[str, int]]:
    """(phase, backward-cycle-index) per session, tail at the very end."""
    blocks: list[tuple[int, str, int]] = [(tail[0], tail[1], 0)]
    cycle = 1
    while sum(b[0] for b in blocks) < N:
        for length, phase in repeating:
            blocks.append((length, phase, cycle))
        cycle += 1
    per_session: list[tuple[str, int]] = []
    for length, phase, b in blocks:
        per_session.extend([(phase, b)] * length)
    return list(reversed(per_session[:N]))


def _prices(schedule, rates, step: float) -> list[float]:
    """Strong-phase strength decays with the backward cycle index: the most
    recent run/giveback is the most extreme, so current readings sit at the
    top of their own history by construction (no percentile ties)."""
    values = [100.0]
    for i in range(1, N):
        phase, b = schedule[i]
        base = rates[phase] - step * b if phase != "quiet" else rates[phase]
        if phase == "give":
            base = rates[phase] + step * b  # recent givebacks are the deepest
        values.append(values[-1] * (1 + base + 0.0004 * math.sin(0.9 * i)))
    return [round(v, 6) for v in values]


SCHED_1 = _schedule((110, "lead"), [(130, "quiet"), (130, "lead")])
RS1 = _prices(SCHED_1, {"lead": 0.0055, "quiet": 0.0005}, step=0.0003)

SCHED_2 = _schedule((66, "lead"), [(60, "give"), (70, "lead")])
RS2 = _prices(SCHED_2, {"lead": 0.0090, "give": -0.0060}, step=0.0004)

SPY = [round(400.0 * (1 + SPY_DRIFT) ** i, 6) for i in range(N)]
XLR = [round(100.0 * (1 + SPY_DRIFT - 0.0005) ** i, 6) for i in range(N)]  # trails SPY


def last_index_of(schedule, phase: str, day_in_phase: int) -> int:
    for i in range(N - 1, -1, -1):
        if schedule[i][0] != phase or i < day_in_phase:
            continue
        run_start = i
        while run_start > 0 and schedule[run_start - 1][0] == phase:
            run_start -= 1
        if i - run_start == day_in_phase:
            return i
    raise AssertionError(f"no session at day {day_in_phase} of a {phase} phase")


EMERGING_AS_OF = DAYS[last_index_of(SCHED_2, "lead", 16)]  # early burst after a giveback
CRACKING_AS_OF = DAYS[last_index_of(SCHED_2, "give", 6)]  # leadership just failed


@pytest.fixture()
def relative_env(
    migrated_schema: None,
    session_factory: sessionmaker[Session],
    test_database_url: str,
    tmp_path,
):
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        spy = repo.create_instrument("SPY", InstrumentType.ETF, effective_date=START)
        xlr = repo.create_instrument("XLR", InstrumentType.ETF, effective_date=START)
        sector = repo.get_or_create_sector("Relative Tech")
        sector.etf_instrument_id = xlr.id
        session.flush()
        rs1 = repo.create_instrument(
            "RS1", InstrumentType.STOCK, sector=sector, effective_date=START
        )
        rs2 = repo.create_instrument(
            "RS2", InstrumentType.STOCK, sector=sector, effective_date=START
        )

        session.add_all(
            TradingDay(exchange="NYSE", calendar_date=d) for d in weekdays(START, date(2026, 7, 31))
        )

        prices = PriceRepository(session)
        for instrument, closes in ((spy, SPY), (xlr, XLR), (rs1, RS1), (rs2, RS2)):
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

    settings = Settings(
        database_url=test_database_url,
        rawdata_root=tmp_path,
        history_start_date=START,
        _env_file=None,
    )
    with session_scope(session_factory) as session:
        pipeline = FeaturePipeline(session=session, settings=settings, today=lambda: TODAY)
        run, _ = pipeline.build(["RS1", "RS2", "XLR", "SPY"])
        assert run.status is RunStatus.SUCCESS
    return session_factory


def evaluate(factory, symbol, as_of=None):
    with session_scope(factory) as session:
        return RelativeStrengthModel(session).evaluate(symbol, as_of=as_of)


def test_fixture_shape() -> None:
    assert SCHED_1[-1] == ("lead", 0) and SCHED_1[-110][0] == "lead"
    assert SCHED_2[-1] == ("lead", 0) and SCHED_2[-66][0] == "lead"
    assert (N - 110) / 260 > 6  # RS1: enough leadership cycles
    assert (N - 66) / 130 > 12  # RS2: plenty of burst/giveback cycles


# -- persistent leadership vs leadership exhaustion --------------------------------


def test_persistent_leadership_scores_favorably(relative_env) -> None:
    scores = {s.horizon: s for s in evaluate(relative_env, "RS1")}  # tail = deep lead
    s = scores["1m"]
    lit = set(s.active_regimes)
    assert "persistent alpha" in lit
    assert "leadership intact" in lit
    assert "solo leadership (sector weak)" in lit  # breadth divergence
    assert lit & {"strong leader vs XLR", "leader vs XLR"}, lit
    for horizon in ("1m", "3m"):
        assert scores[horizon].score > 55.0, horizon
        top = scores[horizon].strongest_supporting_regimes[0]
        assert top.excess > 0 and top.mean > top.baseline_mean
    assert "leadership like this has persisted" in s.explanation
    assert "% hit rate" in s.explanation


def test_leadership_exhaustion_scores_unfavorably(relative_env) -> None:
    """The SAME top-decile leadership readings as RS1 — but this stock's
    bursts have always rolled over by 3m, and the model must learn that."""
    scores = {s.horizon: s for s in evaluate(relative_env, "RS2")}  # tail = deep burst
    s = scores["3m"]
    assert "strong market leader" in s.active_regimes or "persistent alpha" in s.active_regimes
    assert s.score < 45.0
    top = s.strongest_negative_regimes[0]
    assert top.excess < 0 and top.mean < top.baseline_mean
    assert "leadership like this has faded" in s.explanation


def test_emerging_leadership_scores_favorably(relative_env) -> None:
    scores = {s.horizon: s for s in evaluate(relative_env, "RS2", as_of=EMERGING_AS_OF)}
    s = scores["1m"]
    assert "weak but recovering" in s.active_regimes
    assert s.score > 55.0  # historically these turns launched 70-session bursts


def test_leadership_cracking_scores_unfavorably(relative_env) -> None:
    """False-breakout signature: long-window leadership still top-tercile,
    5-session relative return in the gutter — historically the giveback."""
    scores = {s.horizon: s for s in evaluate(relative_env, "RS2", as_of=CRACKING_AS_OF)}
    s = scores["1m"]
    assert "leadership cracking" in s.active_regimes
    assert s.score < 45.0


# -- honesty and PIT ----------------------------------------------------------------


def test_insufficient_history_is_neutral(relative_env) -> None:
    scores = evaluate(relative_env, "RS1", as_of=DAYS[100])
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert (
            "Insufficient relative-return history" in s.explanation or "fewer than" in s.explanation
        )


def test_point_in_time_no_future_evidence(relative_env) -> None:
    as_of = DAYS[2 * N // 3]
    scores = evaluate(relative_env, "RS2", as_of=as_of)
    for s in scores:
        assert s.as_of == as_of
        for evidence in s.strongest_supporting_regimes + s.strongest_negative_regimes:
            assert evidence.last_event <= as_of


# -- statistical hygiene ---------------------------------------------------------------


def test_overlap_correction_and_diagnostics(relative_env) -> None:
    scores = {s.horizon: s for s in evaluate(relative_env, "RS1")}
    s = scores["1m"]
    diag = s.diagnostics
    assert diag is not None
    assert diag.active_regimes == len(s.active_regimes)
    assert 1 <= diag.evidence_studies <= diag.active_regimes
    assert 0.0 <= diag.mean_cross_correlation <= 1.0
    # every family watches the same leadership runs; at longer horizons the
    # Bartlett kernel spans the offsets between family episode starts and
    # the shared runs must show up as substantial measured correlation
    assert scores["6m"].diagnostics.mean_cross_correlation > 0.3
    assert abs(diag.z_clipped) <= 4.0
    assert diag.saturated == (abs(diag.z_raw) > 4.0)
    if diag.saturated:
        assert "Score saturated" in s.explanation
    for e in s.strongest_supporting_regimes + s.strongest_negative_regimes:
        assert e.n_eff <= e.n + 1e-9
        assert e.n >= 5
    payload = s.to_dict()
    assert payload["baseline_return"] is not None
    assert payload["excess_return"] == pytest.approx(s.expected_return - s.baseline_return)


def test_reproducible(relative_env) -> None:
    first = [s.to_dict() for s in evaluate(relative_env, "RS1")]
    second = [s.to_dict() for s in evaluate(relative_env, "RS1")]
    assert first == second


def test_score_stability_day_over_day(relative_env) -> None:
    latest = {s.horizon: s.score for s in evaluate(relative_env, "RS1")}
    previous = {s.horizon: s.score for s in evaluate(relative_env, "RS1", as_of=DAYS[-2])}
    for horizon in HORIZONS:
        assert abs(latest[horizon] - previous[horizon]) < 15.0


# -- CLI -----------------------------------------------------------------------------


def test_cli_relative_command(
    relative_env, monkeypatch, test_database_url, restore_logging
) -> None:
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    result = CliRunner().invoke(app, ["intelligence", "relative", "RS1", "RS2"])
    assert result.exit_code == 0, result.output
    assert "RS1" in result.output and "RS2" in result.output
    assert "active strength regimes" in result.output

    result = CliRunner().invoke(app, ["intelligence", "relative", "RS1", "--json"])
    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output[result.output.index("[") :])
    assert payload[0]["symbol"] == "RS1"
    assert len(payload[0]["scores"]) == len(HORIZONS)
    assert payload[0]["scores"][0]["model"] == "relative_strength"
