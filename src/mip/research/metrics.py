"""Statistical summary of a set of forward returns: ResearchMetric.

Pure computation — no I/O. The 95% confidence interval uses the normal
approximation (mean ± 1.96·s/√n); with typical event counts the difference
from Student-t is smaller than the noise it brackets, and it keeps scipy
out of the dependency tree.
"""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

Z_95 = 1.959963984540054  # NormalDist().inv_cdf(0.975)
HISTOGRAM_BINS = 10


@dataclass(frozen=True)
class ResearchMetric:
    """Distribution summary of forward returns for one horizon."""

    horizon: int
    sample_size: int
    mean: float | None = None
    median: float | None = None
    volatility: float | None = None  # sample std (ddof=1)
    hit_rate: float | None = None  # fraction of returns > 0
    max_gain: float | None = None
    max_loss: float | None = None
    q25: float | None = None
    q75: float | None = None
    ci_low: float | None = None  # 95% CI for the mean
    ci_high: float | None = None
    histogram: tuple[tuple[float, float, int], ...] = ()  # (bin_lo, bin_hi, count)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["histogram"] = [list(b) for b in self.histogram]
        return payload


def summarize(horizon: int, returns: pd.Series) -> ResearchMetric:
    values = returns.dropna().astype(float)
    n = len(values)
    if n == 0:
        return ResearchMetric(horizon=horizon, sample_size=0)

    mean = float(values.mean())
    std = float(values.std(ddof=1)) if n >= 2 else None
    ci_low = ci_high = None
    if std is not None:
        half_width = Z_95 * std / float(np.sqrt(n))
        ci_low, ci_high = mean - half_width, mean + half_width

    counts, edges = np.histogram(values, bins=min(HISTOGRAM_BINS, n))
    histogram = tuple(
        (float(edges[i]), float(edges[i + 1]), int(counts[i])) for i in range(len(counts))
    )

    return ResearchMetric(
        horizon=horizon,
        sample_size=n,
        mean=mean,
        median=float(values.median()),
        volatility=std,
        hit_rate=float((values > 0).mean()),
        max_gain=float(values.max()),
        max_loss=float(values.min()),
        q25=float(values.quantile(0.25)),
        q75=float(values.quantile(0.75)),
        ci_low=ci_low,
        ci_high=ci_high,
        histogram=histogram,
    )
