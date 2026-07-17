"""Portfolio analytics math: every formula verified against hand-computed
two-asset cases — plus the architecture conformance gate."""

import ast
import inspect
import math

import numpy as np
import pandas as pd
import pytest

from mip.portfolio.analytics import (
    TRADING_DAYS,
    annualized_volatility,
    diversification_contribution,
    drawdown_stats,
    marginal_risk_contributions,
    portfolio_volatility,
    risk_contributions,
    worst_drawdown_window,
)

# Two-asset case, hand-computed: annual vols 20% and 10%, correlation 0.5,
# weights 60/40. sigma_p^2 = .36*.04 + .16*.01 + 2*.24*.5*.02 = 0.0208.
SIGMA = np.array([0.20, 0.10])
RHO = 0.5
WEIGHTS = np.array([0.6, 0.4])
COV_ANNUAL = np.array(
    [
        [SIGMA[0] ** 2, RHO * SIGMA[0] * SIGMA[1]],
        [RHO * SIGMA[0] * SIGMA[1], SIGMA[1] ** 2],
    ]
)
COV_DAILY = COV_ANNUAL / TRADING_DAYS


def test_portfolio_volatility_matches_hand_computation() -> None:
    assert portfolio_volatility(WEIGHTS, COV_DAILY) == pytest.approx(math.sqrt(0.0208))


def test_risk_contributions_sum_to_one_and_match_hand_values() -> None:
    contributions = risk_contributions(WEIGHTS, COV_DAILY)
    # (Sigma w)_1 = .6*.04 + .4*.01 = .028; (Sigma w)_2 = .6*.01 + .4*.01 = .010
    assert contributions[0] == pytest.approx(0.6 * 0.028 / 0.0208)
    assert contributions[1] == pytest.approx(0.4 * 0.010 / 0.0208)
    assert contributions.sum() == pytest.approx(1.0)


def test_marginal_risk_contribution_is_the_volatility_gradient() -> None:
    marginals = marginal_risk_contributions(WEIGHTS, COV_DAILY)
    sigma_p = math.sqrt(0.0208)
    assert marginals[0] == pytest.approx(0.028 / sigma_p)
    assert marginals[1] == pytest.approx(0.010 / sigma_p)
    # Euler decomposition: sum(w_i * marginal_i) == sigma_p
    assert float(WEIGHTS @ marginals) == pytest.approx(sigma_p)


def test_diversification_contribution_signs() -> None:
    # equal vols, uncorrelated, 50/50: each asset is a diversifier
    cov = np.array([[0.04, 0.0], [0.0, 0.04]]) / TRADING_DAYS
    equal = np.array([0.5, 0.5])
    contribution = diversification_contribution(equal, cov, 0)
    assert contribution == pytest.approx(0.2 - 0.2 / math.sqrt(2))
    assert contribution > 0

    # perfectly correlated equal assets: removing one changes nothing
    cov = np.array([[0.04, 0.04], [0.04, 0.04]]) / TRADING_DAYS
    assert diversification_contribution(equal, cov, 0) == pytest.approx(0.0)


def test_annualized_volatility() -> None:
    returns = pd.Series([0.01, -0.01] * 50)
    expected = returns.std(ddof=1) * math.sqrt(TRADING_DAYS)
    assert annualized_volatility(returns) == pytest.approx(float(expected))


def test_drawdown_stats_hand_case() -> None:
    prices = pd.Series(
        [100.0, 120.0, 90.0, 105.0],
        index=pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]),
    )
    current, worst = drawdown_stats(prices)
    assert worst == pytest.approx(90 / 120 - 1)
    assert current == pytest.approx(105 / 120 - 1)


def test_worst_drawdown_window_finds_peak_and_trough() -> None:
    prices = pd.Series(
        [100.0, 120.0, 90.0, 105.0],
        index=pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]),
    )
    peak, trough = worst_drawdown_window(prices)
    assert peak == pd.Timestamp("2025-01-03") and trough == pd.Timestamp("2025-01-06")


# -- architecture conformance ---------------------------------------------------


def test_portfolio_analytics_knows_no_model_internals() -> None:
    """Portfolio intelligence consumes NormalizedEvidence via the public
    mip.models package only — never an individual model module, never a
    provider."""
    import mip.portfolio.analytics as module

    tree = ast.parse(inspect.getsource(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = tuple(
        f"mip.models.{name}"
        for name in ("rates", "sector", "momentum", "valuation", "earnings", "macro", "relative")
    ) + ("mip.providers", "mip.ingestion", "yfinance", "fredapi")
    for name in imported:
        assert not name.startswith(forbidden), f"forbidden import in analytics: {name}"
    assert "mip.models" in imported  # the sanctioned surface
