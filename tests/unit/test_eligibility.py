"""The per-horizon embargo rule: boundary, horizon, and data-quality
behavior of the centralized label-observability component."""

from datetime import date, timedelta

from mip.research.analogues import HORIZONS
from mip.validation.eligibility import (
    CROSSES_SCORING_DATE,
    ELIGIBLE,
    MISSING_CALENDAR,
    OBSERVATION_AFTER_CUTOFF,
    OUTCOME_UNAVAILABLE,
    eligible_mask,
    label_observable,
)


def weekdays(start: date, count: int, skip: set[date] = frozenset()) -> list[date]:
    days, current = [], start
    while len(days) < count:
        if current.weekday() < 5 and current not in skip:
            days.append(current)
        current += timedelta(days=1)
    return days


SESSIONS = weekdays(date(2024, 1, 1), 400)


def test_boundary_around_the_cutoff() -> None:
    scoring = SESSIONS[300]
    h = 21
    # ends before scoring: eligible
    assert label_observable(SESSIONS[300 - 22], scoring, h, SESSIONS) == (True, ELIGIBLE)
    # ends exactly ON the scoring session: eligible — the platform scores
    # after the close of T and T's close is a model input (documented)
    assert label_observable(SESSIONS[300 - 21], scoring, h, SESSIONS) == (True, ELIGIBLE)
    # one session too late: the window crosses the scoring date
    assert label_observable(SESSIONS[300 - 20], scoring, h, SESSIONS) == (
        False,
        CROSSES_SCORING_DATE,
    )
    # observation after the cutoff entirely
    assert label_observable(SESSIONS[301], scoring, h, SESSIONS) == (
        False,
        OBSERVATION_AFTER_CUTOFF,
    )


def test_weekend_holiday_month_and_year_boundaries() -> None:
    # a Friday scoring date: the weekend does not count as sessions
    holiday = date(2024, 12, 25)
    sessions = weekdays(date(2024, 11, 1), 60, skip={holiday})
    friday = next(s for s in sessions if s.weekday() == 4 and s > date(2024, 12, 26))
    pos = sessions.index(friday)
    h = 5
    assert label_observable(sessions[pos - 5], friday, h, sessions) == (True, ELIGIBLE)
    assert label_observable(sessions[pos - 4], friday, h, sessions) == (
        False,
        CROSSES_SCORING_DATE,
    )
    # the Christmas holiday is absent from the calendar: mapping fails honestly
    assert label_observable(holiday, friday, h, sessions) == (False, MISSING_CALENDAR)
    # year-end boundary: sessions spanning 2024->2025 count across the break
    year_end_sessions = weekdays(date(2024, 12, 20), 20)
    scoring = year_end_sessions[12]
    assert label_observable(year_end_sessions[7], scoring, 5, year_end_sessions) == (
        True,
        ELIGIBLE,
    )
    assert label_observable(year_end_sessions[8], scoring, 5, year_end_sessions) == (
        False,
        CROSSES_SCORING_DATE,
    )


def test_every_supported_horizon_and_monotone_embargo_width() -> None:
    scoring = SESSIONS[350]
    eligible_counts = {}
    observations = SESSIONS[:350]
    for label, h in HORIZONS.items():
        flags, reasons = eligible_mask(observations, scoring, h, SESSIONS)
        eligible_counts[label] = sum(flags)
        # the newest eligible observation sits exactly h sessions back
        newest = max(i for i, ok in enumerate(flags) if ok)
        assert newest == 350 - h
    ordered = [eligible_counts[label] for label in ("1w", "2w", "1m", "3m", "6m", "1y")]
    assert ordered == sorted(ordered, reverse=True)  # longer horizon -> larger embargo
    # exact embargo width: crossings run from position 350-h+1 up to the
    # last position whose window still fits the 400-session calendar
    # (windows past the calendar end are OUTCOME_UNAVAILABLE, not crossing)
    for label, h in HORIZONS.items():
        _, reasons = eligible_mask(observations, scoring, h, SESSIONS)
        expected_crossing = min(349, 399 - h) - (350 - h)
        assert reasons[CROSSES_SCORING_DATE] == expected_crossing, label
        assert reasons[OUTCOME_UNAVAILABLE] == max(0, 349 - (399 - h)), label


def test_data_quality_paths() -> None:
    scoring = SESSIONS[390]
    # window would extend beyond the known calendar entirely
    assert label_observable(SESSIONS[380], SESSIONS[399], 252, SESSIONS) == (
        False,
        OUTCOME_UNAVAILABLE,
    )
    # sparse symbol: observation date never traded
    assert label_observable(date(2024, 1, 6), scoring, 5, SESSIONS) == (
        False,
        MISSING_CALENDAR,
    )  # a Saturday
    # scoring date not itself a session: maps to the last session before it
    saturday = SESSIONS[389] + timedelta(days=(5 - SESSIONS[389].weekday()) % 7 or 7)
    ok, reason = label_observable(SESSIONS[384], SESSIONS[389], 5, SESSIONS)
    ok_sat, _ = label_observable(SESSIONS[384], saturday, 5, SESSIONS)
    assert (ok, reason) == (True, ELIGIBLE) and ok_sat is True
    # observation before all history
    assert label_observable(date(2023, 1, 2), scoring, 5, SESSIONS)[1] == MISSING_CALENDAR
