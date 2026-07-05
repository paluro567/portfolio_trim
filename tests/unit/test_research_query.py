"""Query vocabulary: filter parsing, validation, sample-mode semantics."""

from datetime import date

import pandas as pd
import pytest

from mip.core.exceptions import ConfigurationError
from mip.research.engine import collapse_to_events, forward_returns
from mip.research.query import ResearchFilter, ResearchQuery, ResearchWindow, parse_filter


def test_parse_simple_filter() -> None:
    f = parse_filter("vix_level > 25")
    assert f == ResearchFilter(feature="vix_level", op=">", value=25.0, symbol=None)


def test_parse_two_char_operator_not_split() -> None:
    f = parse_filter("dgs10_chg_21d >= 0.5")
    assert f.op == ">=" and f.value == 0.5


def test_parse_cross_symbol_filter() -> None:
    f = parse_filter("xlk:rel_ret_spy_21d > 0")
    assert f.symbol == "XLK" and f.feature == "rel_ret_spy_21d"


@pytest.mark.parametrize("bad", ["vix_level", "vix_level > banana", "> 25", "vix ~ 3"])
def test_parse_rejects_malformed(bad: str) -> None:
    with pytest.raises(ConfigurationError):
        parse_filter(bad)


def test_filter_rejects_unknown_operator() -> None:
    with pytest.raises(ConfigurationError, match="unknown operator"):
        ResearchFilter(feature="vix_level", op="~", value=1.0)


def test_query_requires_filters_and_valid_horizons() -> None:
    with pytest.raises(ConfigurationError, match="at least one filter"):
        ResearchQuery(symbol="AMD", filters=())
    with pytest.raises(ConfigurationError, match="positive sessions"):
        ResearchQuery(
            symbol="AMD",
            filters=(ResearchFilter("vix_level", ">", 25.0),),
            horizons=(0,),
        )


def test_query_describe_is_readable() -> None:
    query = ResearchQuery(
        symbol="AMD",
        filters=(
            ResearchFilter("regime_bull", "==", 1.0),
            ResearchFilter("rel_ret_spy_21d", ">", 0.0, symbol="XLK"),
        ),
        window=ResearchWindow(start=date(2015, 1, 1)),
    )
    assert query.describe() == ("AMD where regime_bull == 1 AND XLK:rel_ret_spy_21d > 0 [events]")


# -- pure engine helpers ---------------------------------------------------


def _mask(values: list[bool]) -> pd.Series:
    index = pd.bdate_range("2026-01-05", periods=len(values))
    return pd.Series(values, index=index)


def test_collapse_to_events_takes_episode_starts() -> None:
    mask = _mask([False, True, True, False, True, True, True, False])
    events = collapse_to_events(mask)
    assert list(events) == [mask.index[1], mask.index[4]]


def test_collapse_to_events_first_row_can_start_episode() -> None:
    mask = _mask([True, True, False])
    assert list(collapse_to_events(mask)) == [mask.index[0]]


def test_forward_returns_golden_and_truncation() -> None:
    index = pd.bdate_range("2026-01-05", periods=6)
    prices = pd.Series([100.0, 110.0, 121.0, 133.1, 146.41, 161.051], index=index)
    events = pd.DatetimeIndex([index[1], index[4]])

    frame = forward_returns(prices, events, (1, 3))

    assert frame.loc[index[1], "fwd_1d"] == pytest.approx(0.10)
    assert frame.loc[index[1], "fwd_3d"] == pytest.approx(146.41 / 110.0 - 1)
    assert frame.loc[index[4], "fwd_1d"] == pytest.approx(0.10)
    # index[4] + 3 sessions is past the end of history -> NaN, not a guess
    assert pd.isna(frame.loc[index[4], "fwd_3d"])
