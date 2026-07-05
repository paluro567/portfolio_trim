from datetime import date

import pandas as pd

from mip.domain.enums import IssueSeverity
from mip.ingestion.validation import (
    RULE_DUPLICATE_DATE,
    RULE_FREQUENCY_MISMATCH,
    RULE_MISSING_PERIODS,
    RULE_VALUE_OUT_OF_RANGE,
    validate_macro,
)


def frame(*rows: tuple[date, float | None]) -> pd.DataFrame:
    return pd.DataFrame({"obs_date": [r[0] for r in rows], "value": [r[1] for r in rows]})


def validate(f: pd.DataFrame, frequency: str = "D", **kwargs: object):
    defaults: dict[str, object] = {"frequency": frequency, "accepted": set()}
    defaults.update(kwargs)
    return validate_macro(f, **defaults)


def test_clean_series_passes() -> None:
    report = validate(frame((date(2026, 6, 1), 4.2), (date(2026, 6, 2), 4.25)))
    assert len(report.valid) == 2
    assert report.row_findings == [] and report.frame_findings == []


def test_nan_value_passes_through_for_null_storage() -> None:
    report = validate(frame((date(2026, 6, 1), 4.2), (date(2026, 6, 2), float("nan"))))
    assert len(report.valid) == 2  # '.' rows load (as NULL), never quarantined
    assert report.row_findings == []


def test_duplicate_observation_quarantined() -> None:
    report = validate(frame((date(2026, 6, 1), 4.2), (date(2026, 6, 1), 4.3)))
    assert len(report.valid) == 1
    assert report.row_findings[0].rule == RULE_DUPLICATE_DATE
    assert report.row_findings[0].severity is IssueSeverity.ERROR


def test_out_of_range_value_quarantined() -> None:
    report = validate(
        frame((date(2026, 6, 1), 4.2), (date(2026, 6, 2), 99.0)),
        min_value=-2.0,
        max_value=25.0,
    )
    assert list(report.valid["obs_date"]) == [date(2026, 6, 1)]
    finding = report.row_findings[0]
    assert finding.rule == RULE_VALUE_OUT_OF_RANGE
    assert finding.severity is IssueSeverity.ERROR


def test_out_of_range_accepted_suppression() -> None:
    report = validate(
        frame((date(2026, 6, 1), 99.0)),
        min_value=0.0,
        max_value=25.0,
        accepted={(RULE_VALUE_OUT_OF_RANGE, date(2026, 6, 1))},
    )
    assert len(report.valid) == 1  # human accepted -> loads, not re-flagged
    assert report.row_findings == []


def test_monthly_series_with_two_obs_in_one_month_flagged() -> None:
    report = validate(
        frame((date(2026, 1, 1), 100.0), (date(2026, 1, 15), 101.0), (date(2026, 2, 1), 102.0)),
        frequency="M",
    )
    findings = {f.rule for f in report.frame_findings}
    assert RULE_FREQUENCY_MISMATCH in findings
    assert len(report.valid) == 3  # rows load; the metadata is what's suspect


def test_missing_monthly_periods_flagged() -> None:
    report = validate(
        frame((date(2026, 1, 1), 100.0), (date(2026, 5, 1), 104.0)),  # Feb-Apr missing
        frequency="M",
    )
    findings = {f.rule: f for f in report.frame_findings}
    assert RULE_MISSING_PERIODS in findings
    assert findings[RULE_MISSING_PERIODS].severity is IssueSeverity.WARNING


def test_daily_gap_flagged() -> None:
    report = validate(
        frame((date(2026, 6, 1), 4.2), (date(2026, 6, 25), 4.3)),  # 24-day hole
        frequency="D",
    )
    assert {f.rule for f in report.frame_findings} == {RULE_MISSING_PERIODS}


def test_normal_weekend_gaps_not_flagged() -> None:
    report = validate(
        frame((date(2026, 6, 5), 4.2), (date(2026, 6, 8), 4.3)),  # Fri -> Mon
        frequency="D",
    )
    assert report.frame_findings == []
