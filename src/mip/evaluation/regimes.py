"""Regime analytics: does prediction quality change with the market
environment the prediction was made in?

Each archived as_of date is classified along four independent dimensions
with DECLARED thresholds (constants, not learned):

    trend       bull / bear            SPY close >= / < its trailing
                                       200-session mean
    volatility  high_vix / low_vix     VIXCLS >= / < 20
    rates       rising / falling       FEDFUNDS vs ~6 months earlier
    inflation   inflationary /         CPI YoY accelerating /
                disinflationary        decelerating vs ~6 months earlier

Classification uses realized series values at as_of — it describes the
environment a prediction lived through; nothing here feeds back into
scoring."""

from bisect import bisect_right
from datetime import date, timedelta
from typing import Any

from mip.evaluation.analytics import _mean, _share

TREND_WINDOW = 200
VIX_HIGH = 20.0
COMPARISON_LOOKBACK = timedelta(days=182)  # ~6 months
YOY = timedelta(days=365)

DIMENSIONS = ("trend", "volatility", "rates", "inflation")

Series = list[tuple[date, float]]  # sorted by date ascending


def _value_on_or_before(series: Series, day: date) -> float | None:
    index = bisect_right(series, (day, float("inf")))
    return series[index - 1][1] if index else None


class RegimeClassifier:
    """Pure given its input series; `from_repository` loads the real ones."""

    def __init__(self, spy_closes: Series, vix: Series, fedfunds: Series, cpi: Series) -> None:
        self._spy = spy_closes
        self._vix = vix
        self._fedfunds = fedfunds
        self._cpi = cpi

    @classmethod
    def from_repository(cls, repo, through: date) -> "RegimeClassifier":
        return cls(
            spy_closes=repo.closes_through("SPY", through, limit=10_000),
            vix=repo.macro_values("VIXCLS", through),
            fedfunds=repo.macro_values("FEDFUNDS", through),
            cpi=repo.macro_values("CPIAUCSL", through),
        )

    def _trend(self, as_of: date) -> str | None:
        index = bisect_right(self._spy, (as_of, float("inf")))
        window = self._spy[max(0, index - TREND_WINDOW) : index]
        if len(window) < TREND_WINDOW:
            return None
        closes = [close for _, close in window]
        return "bull" if closes[-1] >= sum(closes) / len(closes) else "bear"

    def _volatility(self, as_of: date) -> str | None:
        vix = _value_on_or_before(self._vix, as_of)
        if vix is None:
            return None
        return "high_vix" if vix >= VIX_HIGH else "low_vix"

    def _rates(self, as_of: date) -> str | None:
        now = _value_on_or_before(self._fedfunds, as_of)
        prior = _value_on_or_before(self._fedfunds, as_of - COMPARISON_LOOKBACK)
        if now is None or prior is None:
            return None
        return "rising_rates" if now > prior else "falling_rates"

    def _yoy(self, day: date) -> float | None:
        now = _value_on_or_before(self._cpi, day)
        base = _value_on_or_before(self._cpi, day - YOY)
        if now is None or base is None or base == 0:
            return None
        return now / base - 1.0

    def _inflation(self, as_of: date) -> str | None:
        now = self._yoy(as_of)
        prior = self._yoy(as_of - COMPARISON_LOOKBACK)
        if now is None or prior is None:
            return None
        return "inflationary" if now >= prior else "disinflationary"

    def classify(self, as_of: date) -> dict[str, str | None]:
        return {
            "trend": self._trend(as_of),
            "volatility": self._volatility(as_of),
            "rates": self._rates(as_of),
            "inflation": self._inflation(as_of),
        }


def regime_analytics(rows: list[dict], classifier: RegimeClassifier) -> list[dict]:
    """Group realized outcomes by each regime label the prediction was
    made under. Uses only fields already measured elsewhere."""
    labels_cache: dict[date, dict[str, str | None]] = {}
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        as_of = row["as_of"]
        if as_of not in labels_cache:
            labels_cache[as_of] = classifier.classify(as_of)
        for dimension in DIMENSIONS:
            label = labels_cache[as_of][dimension]
            if label is not None:
                grouped.setdefault((dimension, label), []).append(row)
    table: list[dict[str, Any]] = []
    for dimension in DIMENSIONS:
        for (dim, label), subset in sorted(grouped.items()):
            if dim != dimension:
                continue
            table.append(
                {
                    "dimension": dimension,
                    "regime": label,
                    "n": len(subset),
                    "direction_accuracy": _share(
                        [
                            r["direction_correct"]
                            for r in subset
                            if r["direction_correct"] is not None
                        ]
                    ),
                    "mae": _mean(
                        [r["absolute_error"] for r in subset if r["absolute_error"] is not None]
                    ),
                    "avg_actual_excess": _mean(
                        [
                            r["actual_excess_return"]
                            for r in subset
                            if r["actual_excess_return"] is not None
                        ]
                    ),
                }
            )
    return table
