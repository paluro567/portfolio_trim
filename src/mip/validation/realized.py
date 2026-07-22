"""Stage C: realized forward outcomes for every frozen scoring date.

Computed exclusively from stored daily prices AFTER predictions were
frozen — the walk-forward discipline. A horizon without a complete
forward window stays incomplete and is excluded from that horizon's
metrics (never padded)."""

import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import select

from mip.core.db import session_scope
from mip.domain.models import DailyPrice, Instrument
from mip.research.analogues import HORIZONS


def _adj_close(session, symbol: str) -> pd.Series:
    rows = session.execute(
        select(DailyPrice.price_date, DailyPrice.adj_close)
        .join(Instrument, Instrument.id == DailyPrice.instrument_id)
        .where(Instrument.symbol == symbol, DailyPrice.adj_close.is_not(None))
        .order_by(DailyPrice.price_date)
    ).all()
    return pd.Series(
        [float(r[1]) for r in rows],
        index=pd.DatetimeIndex(pd.to_datetime([r[0] for r in rows])),
    )


def realized_outcomes(
    factory, symbols: list[str], dates_by_symbol: dict[str, list[date]]
) -> pd.DataFrame:
    """One row per (symbol, as_of, horizon): actual return, SPY-relative,
    path drawdown/adverse excursion, realized vol, completeness."""
    out: list[dict] = []
    with session_scope(factory) as session:
        spy = _adj_close(session, "SPY")
        for symbol in symbols:
            prices = _adj_close(session, symbol)
            if prices.empty:
                continue
            values = prices.to_numpy()
            positions = {ts: i for i, ts in enumerate(prices.index)}
            spy_values = spy.to_numpy()
            spy_positions = {ts: i for i, ts in enumerate(spy.index)}
            for as_of in dates_by_symbol.get(symbol, []):
                ts = pd.Timestamp(as_of)
                pos = positions.get(ts)
                if pos is None:
                    eligible = prices.index[prices.index <= ts]
                    if len(eligible) == 0:
                        continue
                    ts = eligible[-1]
                    pos = positions[ts]
                spy_pos = spy_positions.get(ts)
                for label, sessions in HORIZONS.items():
                    complete = pos + sessions < len(values)
                    row: dict = {
                        "symbol": symbol,
                        "as_of": as_of,
                        "horizon": label,
                        "complete": complete,
                    }
                    if complete:
                        window = values[pos : pos + sessions + 1]
                        path = window / window[0]
                        actual = float(path[-1] - 1.0)
                        row.update(
                            actual=actual,
                            adverse=float(path[1:].min() - 1.0),
                            drawdown=float((window / np.maximum.accumulate(window) - 1.0).min()),
                            fwd_vol=(
                                float(np.diff(np.log(window)).std(ddof=1) * math.sqrt(252))
                                if sessions > 1
                                else 0.0
                            ),
                        )
                        if spy_pos is not None and spy_pos + sessions < len(spy_values):
                            spy_ret = float(
                                spy_values[spy_pos + sessions] / spy_values[spy_pos] - 1.0
                            )
                            row["spy_rel"] = actual - spy_ret
                    out.append(row)
    return pd.DataFrame(out)


def write_outcomes(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False)
