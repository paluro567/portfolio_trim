from datetime import date

import pandas as pd

from mip.domain.enums import IssueSeverity
from mip.ingestion.validation import (
    RULE_DUPLICATE_DATE,
    RULE_NEGATIVE_VOLUME,
    RULE_NONPOSITIVE_CLOSE,
    RULE_OHLC_INCOHERENT,
    RULE_RETURN_JUMP,
    RULE_STALE_CLOSES,
    RULE_ZERO_VOLUME,
    validate_prices,
)


def row(d: date, close: float, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "price_date": d,
        "open": close * 0.99,
        "high": close * 1.01,
        "low": close * 0.98,
        "close": close,
        "adj_close": close,
        "volume": 1_000,
    }
    base.update(overrides)
    return base


def frame(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def validate(f: pd.DataFrame, **kwargs: object):
    defaults: dict[str, object] = {"split_dates": set(), "accepted": set()}
    defaults.update(kwargs)
    return validate_prices(f, **defaults)


def test_clean_frame_passes() -> None:
    report = validate(frame(row(date(2026, 6, 1), 100), row(date(2026, 6, 2), 101)))
    assert len(report.valid) == 2
    assert report.rejected.empty
    assert report.row_findings == []


def test_ohlc_incoherent_quarantined() -> None:
    bad = row(date(2026, 6, 2), 100, high=90.0, low=95.0)  # high < low
    report = validate(frame(row(date(2026, 6, 1), 100), bad))

    assert list(report.valid["price_date"]) == [date(2026, 6, 1)]
    assert list(report.rejected["rule"]) == [RULE_OHLC_INCOHERENT]
    finding = report.row_findings[0]
    assert finding.severity is IssueSeverity.ERROR
    assert finding.entity_date == date(2026, 6, 2)


def test_nonpositive_close_quarantined() -> None:
    report = validate(frame(row(date(2026, 6, 1), -5.0)))
    assert report.valid.empty
    assert report.row_findings[0].rule == RULE_NONPOSITIVE_CLOSE


def test_negative_volume_quarantined_zero_volume_warns() -> None:
    report = validate(
        frame(
            row(date(2026, 6, 1), 100, volume=-10),
            row(date(2026, 6, 2), 100, volume=0),
        )
    )
    rules = {f.rule: f.severity for f in report.row_findings}
    assert rules[RULE_NEGATIVE_VOLUME] is IssueSeverity.ERROR
    assert rules[RULE_ZERO_VOLUME] is IssueSeverity.WARNING
    assert list(report.valid["price_date"]) == [date(2026, 6, 2)]  # warning row loads


def test_duplicate_dates_keep_first() -> None:
    report = validate(frame(row(date(2026, 6, 1), 100), row(date(2026, 6, 1), 200)))
    assert len(report.valid) == 1
    assert report.row_findings[0].rule == RULE_DUPLICATE_DATE


def test_return_jump_without_action_quarantined() -> None:
    report = validate(frame(row(date(2026, 6, 1), 100), row(date(2026, 6, 2), 145)))
    assert report.row_findings[0].rule == RULE_RETURN_JUMP
    assert report.row_findings[0].severity is IssueSeverity.ERROR
    assert list(report.valid["price_date"]) == [date(2026, 6, 1)]


def test_return_jump_with_matching_split_passes() -> None:
    report = validate(
        frame(row(date(2026, 6, 1), 100), row(date(2026, 6, 2), 50)),
        split_dates={date(2026, 6, 2)},
    )
    assert report.row_findings == []
    assert len(report.valid) == 2


def test_return_jump_uses_prior_close_at_boundary() -> None:
    from decimal import Decimal

    report = validate(frame(row(date(2026, 6, 2), 145)), prior_close=Decimal("100"))
    assert report.row_findings[0].rule == RULE_RETURN_JUMP


def test_accepted_issue_suppresses_and_loads() -> None:
    report = validate(
        frame(row(date(2026, 6, 1), 100), row(date(2026, 6, 2), 145)),
        accepted={(RULE_RETURN_JUMP, date(2026, 6, 2))},
    )
    assert report.row_findings == []
    assert len(report.valid) == 2  # human said it's real -> row loads


def test_quarantined_row_does_not_advance_prev_close() -> None:
    # bad tick spike: next day compared against last GOOD close
    report = validate(
        frame(
            row(date(2026, 6, 1), 100),
            row(date(2026, 6, 2), 150),  # quarantined jump
            row(date(2026, 6, 3), 101),  # vs 100, not vs 150 -> passes
        )
    )
    assert [f.entity_date for f in report.row_findings] == [date(2026, 6, 2)]
    assert list(report.valid["price_date"]) == [date(2026, 6, 1), date(2026, 6, 3)]


def test_stale_closes_flagged_as_frame_warning() -> None:
    rows = [row(date(2026, 6, d), 100.0) for d in range(1, 7)]
    report = validate(frame(*rows), stale_run_length=5)

    assert len(report.frame_findings) == 1
    finding = report.frame_findings[0]
    assert finding.rule == RULE_STALE_CLOSES
    assert finding.severity is IssueSeverity.WARNING
    assert len(report.valid) == 6  # stale rows still load
