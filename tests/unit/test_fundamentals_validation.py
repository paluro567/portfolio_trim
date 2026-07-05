from decimal import Decimal

from mip.domain.enums import IssueSeverity
from mip.ingestion.validation import (
    RULE_MARKETCAP_INCONSISTENT,
    RULE_NEGATIVE_FUNDAMENTAL,
    RULE_SHARES_JUMP,
    validate_fundamentals,
)


def snapshot(**overrides: object) -> dict[str, float | None]:
    base: dict[str, float | None] = {
        "market_cap": 1_000_000_000.0,
        "trailing_pe": 25.0,
        "forward_pe": 22.0,
        "price_to_book": 5.0,
        "trailing_eps": 4.0,
        "forward_eps": 4.5,
        "dividend_yield": 0.01,
        "beta": 1.1,
        "shares_outstanding": 10_000_000,
        "revenue_ttm": 500_000_000.0,
        "profit_margin": 0.2,
        "debt_to_equity": 80.0,
    }
    base.update(overrides)  # type: ignore[arg-type]
    return base


def test_clean_snapshot_passes_unchanged() -> None:
    cleaned, findings = validate_fundamentals(
        snapshot(), latest_close=Decimal("100")  # 100 * 10M = 1B: consistent
    )
    assert findings == []
    assert cleaned == snapshot()


def test_missing_fields_tolerated_without_findings() -> None:
    sparse = snapshot(trailing_pe=None, beta=None, revenue_ttm=None)
    cleaned, findings = validate_fundamentals(sparse)
    assert findings == []  # NULLs are normal, never quarantined
    assert cleaned["trailing_pe"] is None


def test_negative_field_nulled_but_snapshot_kept() -> None:
    cleaned, findings = validate_fundamentals(snapshot(market_cap=-5.0))

    assert cleaned["market_cap"] is None  # field nulled
    assert cleaned["trailing_pe"] == 25.0  # rest of the snapshot intact
    assert len(findings) == 1
    assert findings[0].rule == RULE_NEGATIVE_FUNDAMENTAL
    assert findings[0].severity is IssueSeverity.ERROR


def test_marketcap_price_shares_mismatch_flagged() -> None:
    # close 100 * 10M shares = 1B, but market_cap says 5B: unit error
    _, findings = validate_fundamentals(
        snapshot(market_cap=5_000_000_000.0), latest_close=Decimal("100")
    )
    rules = [f.rule for f in findings]
    assert RULE_MARKETCAP_INCONSISTENT in rules
    assert findings[0].severity is IssueSeverity.WARNING


def test_marketcap_check_skipped_without_price() -> None:
    _, findings = validate_fundamentals(snapshot(market_cap=5_000_000_000.0))
    assert findings == []  # no close available -> cross-check impossible


def test_shares_jump_flagged_without_split() -> None:
    _, findings = validate_fundamentals(
        snapshot(shares_outstanding=25_000_000),
        prior_shares=10_000_000,
        latest_close=Decimal("40"),  # 40 * 25M = 1B: consistent
    )
    assert [f.rule for f in findings] == [RULE_SHARES_JUMP]


def test_shares_jump_suppressed_by_recent_split() -> None:
    _, findings = validate_fundamentals(
        snapshot(shares_outstanding=25_000_000),
        prior_shares=10_000_000,
        latest_close=Decimal("40"),
        had_recent_split=True,
    )
    assert findings == []
