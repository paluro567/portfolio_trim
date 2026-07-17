"""Portfolio Intelligence: structure, risk, and evidence context for every
current position. Descriptive analytics only — no price prediction, no
Hold/Trim/Sell labels (the Decision Engine's job, later).

All statistics use trailing windows of adjusted closes ENDING at as_of
(never a future price — the same PIT discipline as the models):

- weights w_i = market value share; HHI contribution = w_i².
- annualized volatility = stdev(daily returns) · sqrt(252).
- portfolio variance = w'Σw on the overlapping-return window; a position's
  risk contribution = w_i(Σw)_i / (w'Σw) (percentages sum to 1); marginal
  risk contribution = (Σw)_i / σ_p (∂σ_p/∂w_i).
- diversification contribution = σ_p(portfolio without the position,
  reweighted) − σ_p(full): positive = removing it would RAISE portfolio
  volatility (it diversifies); negative = it concentrates risk.
- drawdowns from the full stored history ≤ as_of; a position's drawdown
  contribution = w_i · (its return over the portfolio's own worst trailing
  peak-to-trough window).
- positions without MIN_OVERLAP overlapping return days are excluded from
  covariance statistics and flagged, never guessed.

Intelligence context consumes NormalizedEvidence ONLY, produced through
each model's public IntelligenceModel interface + the normalization layer —
this module knows no model internals. Models that cannot evaluate in the
current data environment (ConfigurationError) are skipped and named in the
assessment rather than crashing portfolio analytics.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.domain.models import DailyPrice, Industry, Instrument
from mip.models import ALL_MODELS, NormalizedEvidence, normalize_scores
from mip.portfolio.lots import MONEY, LotEngine
from mip.repositories.portfolio import PortfolioRepository

TRADING_DAYS = 252


# -- pure math (unit-testable without a database) --------------------------------


def annualized_volatility(returns: pd.Series) -> float:
    return float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def portfolio_volatility(weights: np.ndarray, covariance: np.ndarray) -> float:
    return float(np.sqrt(weights @ covariance @ weights * TRADING_DAYS))


def risk_contributions(weights: np.ndarray, covariance: np.ndarray) -> np.ndarray:
    """Fraction of portfolio variance each position contributes; sums to 1."""
    variance = float(weights @ covariance @ weights)
    if variance <= 0:
        return np.zeros_like(weights)
    return weights * (covariance @ weights) / variance


def marginal_risk_contributions(weights: np.ndarray, covariance: np.ndarray) -> np.ndarray:
    """d(sigma_p)/d(w_i), annualized."""
    sigma = portfolio_volatility(weights, covariance)
    if sigma <= 0:
        return np.zeros_like(weights)
    return (covariance @ weights) * TRADING_DAYS / sigma


def diversification_contribution(weights: np.ndarray, covariance: np.ndarray, index: int) -> float:
    """sigma_p(without position `index`, reweighted) - sigma_p(full).
    Positive: removing the position raises volatility (it diversifies)."""
    full = portfolio_volatility(weights, covariance)
    keep = [i for i in range(len(weights)) if i != index]
    if not keep:
        return 0.0
    reduced = weights[keep]
    total = reduced.sum()
    if total <= 0:
        return 0.0
    reduced = reduced / total
    without = portfolio_volatility(reduced, covariance[np.ix_(keep, keep)])
    return without - full


def drawdown_stats(prices: pd.Series) -> tuple[float, float]:
    """(current drawdown, maximum drawdown) from a price series; <= 0."""
    running_max = prices.cummax()
    drawdowns = prices / running_max - 1.0
    return float(drawdowns.iloc[-1]), float(drawdowns.min())


def worst_drawdown_window(portfolio_index: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp]:
    """(peak date, trough date) of the deepest drawdown in the series."""
    running_max = portfolio_index.cummax()
    drawdowns = portfolio_index / running_max - 1.0
    trough = drawdowns.idxmin()
    peak = portfolio_index.loc[:trough].idxmax()
    return peak, trough


# -- the assessment contract ---------------------------------------------------------


@dataclass(frozen=True)
class PortfolioPositionAssessment:
    """Descriptive assessment of one position. NOT a recommendation."""

    portfolio_id: int
    portfolio_name: str
    symbol: str
    as_of: date
    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal
    market_value: Decimal
    unrealized_gain: Decimal
    portfolio_weight: float
    weight_rank: int
    hhi_contribution: float
    sector: str | None
    industry: str | None
    sector_weight: float | None
    industry_weight: float | None
    annualized_volatility: float | None
    risk_contribution: float | None  # fraction of portfolio variance
    marginal_risk_contribution: float | None
    diversification_contribution: float | None
    current_drawdown: float | None
    max_drawdown: float | None
    drawdown_contribution: float | None
    highest_correlations: tuple[tuple[str, float], ...]  # (symbol, rho), desc
    concentration_flags: tuple[str, ...]
    correlation_flags: tuple[str, ...]
    strengths: tuple[str, ...]
    risks: tuple[str, ...]
    evidence: dict[str, dict[str, dict]]  # model -> horizon -> summary
    skipped_models: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "portfolio_id": self.portfolio_id,
            "portfolio_name": self.portfolio_name,
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "quantity": str(self.quantity),
            "average_cost": str(self.average_cost),
            "cost_basis": str(self.cost_basis),
            "market_value": str(self.market_value),
            "unrealized_gain": str(self.unrealized_gain),
            "portfolio_weight": self.portfolio_weight,
            "weight_rank": self.weight_rank,
            "hhi_contribution": self.hhi_contribution,
            "sector": self.sector,
            "industry": self.industry,
            "sector_weight": self.sector_weight,
            "industry_weight": self.industry_weight,
            "annualized_volatility": self.annualized_volatility,
            "risk_contribution": self.risk_contribution,
            "marginal_risk_contribution": self.marginal_risk_contribution,
            "diversification_contribution": self.diversification_contribution,
            "current_drawdown": self.current_drawdown,
            "max_drawdown": self.max_drawdown,
            "drawdown_contribution": self.drawdown_contribution,
            "highest_correlations": [[s, r] for s, r in self.highest_correlations],
            "concentration_flags": list(self.concentration_flags),
            "correlation_flags": list(self.correlation_flags),
            "strengths": list(self.strengths),
            "risks": list(self.risks),
            "normalized_evidence_by_model_and_horizon": self.evidence,
            "skipped_models": list(self.skipped_models),
        }


class PortfolioAnalyzer:
    def __init__(
        self,
        session: Session,
        weight_limit: float = 0.15,
        sector_limit: float = 0.35,
        correlation_threshold: float = 0.75,
        window_sessions: int = TRADING_DAYS,
        min_overlap: int = 60,
    ) -> None:
        self._session = session
        self._repo = PortfolioRepository(session)
        self.weight_limit = weight_limit
        self.sector_limit = sector_limit
        self.correlation_threshold = correlation_threshold
        self.window_sessions = window_sessions
        self.min_overlap = min_overlap

    # -- public ------------------------------------------------------------

    def analyze(
        self,
        portfolio_name: str,
        as_of: date | None = None,
        symbols: list[str] | None = None,
        with_evidence: bool = True,
    ) -> list[PortfolioPositionAssessment]:
        portfolio = self._repo.require_portfolio(portfolio_name)
        positions = self._positions(portfolio.id, as_of)
        if not positions:
            raise ConfigurationError(
                f"portfolio {portfolio_name!r} holds no positions"
                + (f" as of {as_of}" if as_of else "")
            )
        instruments = self._instruments(list(positions))
        prices = {i: self._adj_close_series(i, as_of) for i in positions}  # full history <= as_of
        resolved_as_of = as_of or max(
            (s.index[-1].date() for s in prices.values() if not s.empty),
            default=date.today(),
        )

        market_values = {
            i: (quantity * self._last_price(prices[i])).quantize(MONEY)
            for i, (quantity, _basis) in positions.items()
            if not prices[i].empty
        }
        missing_price = [i for i in positions if i not in market_values]
        if missing_price:
            names = [instruments[i].symbol for i in missing_price]
            raise ConfigurationError(f"no adjusted closes stored for held symbols: {names}")
        total_value = sum(market_values.values())
        ids = sorted(positions, key=lambda i: market_values[i], reverse=True)
        weights = {i: float(market_values[i] / total_value) for i in ids}

        # sector / industry weights
        sector_weight: dict[str, float] = {}
        industry_weight: dict[str, float] = {}
        for i in ids:
            sector, industry = self._classification(instruments[i])
            if sector:
                sector_weight[sector] = sector_weight.get(sector, 0.0) + weights[i]
            if industry:
                industry_weight[industry] = industry_weight.get(industry, 0.0) + weights[i]

        # trailing return window (inner-joined dates) for covariance stats
        returns = pd.DataFrame(
            {i: prices[i].tail(self.window_sessions + 1).pct_change().dropna() for i in ids}
        ).dropna()
        risk = self._risk_block(ids, weights, returns)
        correlations = returns.corr() if len(returns) >= self.min_overlap else None

        # portfolio drawdown window over the return window
        drawdown_window = None
        if len(returns) >= self.min_overlap:
            weight_vector = np.array([weights[i] for i in ids])
            portfolio_index = (1.0 + returns[ids] @ weight_vector).cumprod()
            drawdown_window = worst_drawdown_window(portfolio_index)

        wanted = None
        if symbols:
            wanted = {s.strip().upper() for s in symbols}

        assessments = []
        for rank, i in enumerate(ids, start=1):
            symbol = instruments[i].symbol
            if wanted and symbol not in wanted:
                continue
            assessments.append(
                self._assess(
                    portfolio,
                    i,
                    symbol,
                    rank,
                    resolved_as_of,
                    positions,
                    market_values,
                    weights,
                    instruments,
                    sector_weight,
                    industry_weight,
                    prices,
                    returns,
                    correlations,
                    risk,
                    drawdown_window,
                    ids,
                    with_evidence,
                )
            )
        return assessments

    # -- internals ------------------------------------------------------------

    def _positions(
        self, portfolio_id: int, as_of: date | None
    ) -> dict[int, tuple[Decimal, Decimal]]:
        """instrument_id -> (quantity, cost basis) from a ledger replay
        through as_of (deterministic; independent of stored snapshots)."""
        transactions = [
            t
            for t in self._repo.transactions(portfolio_id, through=as_of)
            if t.instrument_id is not None
        ]
        lots = LotEngine().replay(transactions)
        txn_instrument = {t.id: t.instrument_id for t in transactions}
        positions: dict[int, tuple[Decimal, Decimal]] = {}
        for lot in lots:
            if lot.quantity_remaining <= 0:
                continue
            instrument_id = txn_instrument[lot.open_transaction_id]
            quantity, basis = positions.get(instrument_id, (Decimal(0), Decimal(0)))
            positions[instrument_id] = (
                quantity + lot.quantity_remaining,
                basis + (lot.quantity_remaining * lot.cost_basis_per_share).quantize(MONEY),
            )
        return positions

    def _instruments(self, instrument_ids: list[int]) -> dict[int, Instrument]:
        rows = self._session.scalars(select(Instrument).where(Instrument.id.in_(instrument_ids)))
        return {r.id: r for r in rows}

    def _classification(self, instrument: Instrument) -> tuple[str | None, str | None]:
        if instrument.industry_id is not None:
            industry = self._session.get(Industry, instrument.industry_id)
            if industry is not None:
                sector = industry.sector
                return (sector.name if sector else None), industry.name
        if instrument.sector_id is not None:
            from mip.domain.models import Sector

            sector = self._session.get(Sector, instrument.sector_id)
            return (sector.name if sector else None), None
        return None, None

    def _adj_close_series(self, instrument_id: int, as_of: date | None) -> pd.Series:
        rows = self._session.execute(
            select(DailyPrice.price_date, DailyPrice.adj_close)
            .where(
                DailyPrice.instrument_id == instrument_id,
                DailyPrice.adj_close.is_not(None),
            )
            .order_by(DailyPrice.price_date)
        ).all()
        series = pd.Series(
            [float(v) for _, v in rows],
            index=pd.DatetimeIndex(pd.to_datetime([d for d, _ in rows])),
        )
        if as_of is not None and not series.empty:
            series = series[series.index <= pd.Timestamp(as_of)]
        return series

    @staticmethod
    def _last_price(series: pd.Series) -> Decimal:
        return Decimal(str(series.iloc[-1]))

    def _risk_block(self, ids, weights, returns) -> dict | None:
        if len(returns) < self.min_overlap or len(ids) == 0:
            return None
        weight_vector = np.array([weights[i] for i in ids])
        weight_vector = weight_vector / weight_vector.sum()
        covariance = returns[ids].cov(ddof=1).to_numpy()
        return {
            "ids": list(ids),
            "weights": weight_vector,
            "covariance": covariance,
            "sigma": portfolio_volatility(weight_vector, covariance),
            "contributions": risk_contributions(weight_vector, covariance),
            "marginals": marginal_risk_contributions(weight_vector, covariance),
        }

    def _evidence(
        self, symbol: str, as_of: date
    ) -> tuple[dict[str, dict[str, dict]], tuple[str, ...]]:
        """NormalizedEvidence per model/horizon via the public model
        interface + normalization layer only. Models that cannot evaluate
        in this data environment are skipped by name, never guessed."""
        summary: dict[str, dict[str, dict]] = {}
        skipped: list[str] = []
        for model_cls in ALL_MODELS:
            try:
                scores = model_cls(self._session).evaluate(symbol, as_of=as_of)
                batch = normalize_scores(scores)
            except ConfigurationError:
                skipped.append(model_cls.name)
                continue
            summary[batch[0].model_name] = {e.horizon: self._evidence_summary(e) for e in batch}
        return summary, tuple(skipped)

    @staticmethod
    def _evidence_summary(evidence: NormalizedEvidence) -> dict:
        return {
            "score": round(evidence.score, 1),
            "confidence": round(evidence.confidence, 3),
            "neutral": evidence.neutral,
            "expected_excess_return": evidence.expected_excess_return,
            "evidence_strength": round(evidence.evidence_strength, 3),
        }

    def _assess(
        self,
        portfolio,
        instrument_id,
        symbol,
        rank,
        as_of,
        positions,
        market_values,
        weights,
        instruments,
        sector_weight,
        industry_weight,
        prices,
        returns,
        correlations,
        risk,
        drawdown_window,
        ids,
        with_evidence,
    ) -> PortfolioPositionAssessment:
        quantity, basis = positions[instrument_id]
        market_value = market_values[instrument_id]
        weight = weights[instrument_id]
        sector, industry = self._classification(instruments[instrument_id])

        series = prices[instrument_id]
        window = series.tail(self.window_sessions + 1)
        vol = annualized_volatility(window.pct_change().dropna()) if len(window) > 20 else None
        current_dd, max_dd = drawdown_stats(series) if len(series) > 20 else (None, None)

        risk_contribution = marginal = diversification = None
        if risk is not None and instrument_id in risk["ids"]:
            index = risk["ids"].index(instrument_id)
            risk_contribution = float(risk["contributions"][index])
            marginal = float(risk["marginals"][index])
            diversification = diversification_contribution(
                risk["weights"], risk["covariance"], index
            )

        drawdown_contribution = None
        if drawdown_window is not None and instrument_id in returns.columns:
            peak, trough = drawdown_window
            if peak < trough:
                segment = returns[instrument_id].loc[peak:trough].iloc[1:]
                drawdown_contribution = weight * float((1.0 + segment).prod() - 1.0)

        highest: list[tuple[str, float]] = []
        correlation_flags: list[str] = []
        if correlations is not None and instrument_id in correlations.columns:
            others = correlations[instrument_id].drop(index=instrument_id)
            ranked = others.sort_values(ascending=False)
            highest = [
                (instruments[i].symbol, round(float(r), 3)) for i, r in ranked.head(3).items()
            ]
            for i, rho in ranked.items():
                if rho >= self.correlation_threshold:
                    correlation_flags.append(
                        f"highly correlated with {instruments[i].symbol} "
                        f"(ρ={rho:.2f} over {len(returns)} sessions)"
                    )
        elif correlations is None:
            correlation_flags.append(
                f"insufficient overlapping price history (<{self.min_overlap} sessions) "
                "for correlation and risk statistics"
            )

        concentration_flags: list[str] = []
        if weight > self.weight_limit:
            concentration_flags.append(
                f"position weight {weight:.1%} exceeds the {self.weight_limit:.0%} limit"
            )
        if sector and sector_weight.get(sector, 0.0) > self.sector_limit:
            concentration_flags.append(
                f"sector {sector} weight {sector_weight[sector]:.1%} exceeds the "
                f"{self.sector_limit:.0%} limit"
            )

        evidence, skipped = self._evidence(symbol, as_of) if with_evidence else ({}, ())

        strengths, risks_out = self._narrative(
            weight,
            risk_contribution,
            diversification,
            evidence,
            concentration_flags,
            correlation_flags,
            current_dd,
        )

        average_cost = (basis / quantity).quantize(Decimal("0.000001")) if quantity else Decimal(0)
        return PortfolioPositionAssessment(
            portfolio_id=portfolio.id,
            portfolio_name=portfolio.name,
            symbol=symbol,
            as_of=as_of,
            quantity=quantity,
            average_cost=average_cost,
            cost_basis=basis,
            market_value=market_value,
            unrealized_gain=(market_value - basis).quantize(MONEY),
            portfolio_weight=weight,
            weight_rank=rank,
            hhi_contribution=weight**2,
            sector=sector,
            industry=industry,
            sector_weight=sector_weight.get(sector) if sector else None,
            industry_weight=industry_weight.get(industry) if industry else None,
            annualized_volatility=vol,
            risk_contribution=risk_contribution,
            marginal_risk_contribution=marginal,
            diversification_contribution=diversification,
            current_drawdown=current_dd,
            max_drawdown=max_dd,
            drawdown_contribution=drawdown_contribution,
            highest_correlations=tuple(highest),
            concentration_flags=tuple(concentration_flags),
            correlation_flags=tuple(correlation_flags),
            strengths=strengths,
            risks=risks_out,
            evidence=evidence,
            skipped_models=skipped,
        )

    @staticmethod
    def _narrative(
        weight,
        risk_contribution,
        diversification,
        evidence,
        concentration_flags,
        correlation_flags,
        current_dd,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Descriptive strengths/risks assembled from measured facts —
        deliberately NOT recommendations."""
        strengths: list[str] = []
        risks: list[str] = []
        if diversification is not None and diversification > 0:
            strengths.append(
                f"diversifier: removing it would raise portfolio volatility by "
                f"{diversification:.2%}"
            )
        if risk_contribution is not None and risk_contribution > weight * 1.5:
            risks.append(
                f"risk contribution {risk_contribution:.0%} far exceeds its " f"{weight:.0%} weight"
            )
        strong = [
            (model, horizon, cell)
            for model, horizons in evidence.items()
            for horizon, cell in horizons.items()
            if not cell["neutral"] and cell["score"] >= 65 and cell["confidence"] >= 0.3
        ]
        weak = [
            (model, horizon, cell)
            for model, horizons in evidence.items()
            for horizon, cell in horizons.items()
            if not cell["neutral"] and cell["score"] <= 35 and cell["confidence"] >= 0.3
        ]
        if strong:
            models = sorted({m for m, _, _ in strong})
            strengths.append(
                f"strong evidence from {', '.join(models)} "
                f"({len(strong)} horizon reading(s) ≥ 65)"
            )
        if weak:
            models = sorted({m for m, _, _ in weak})
            risks.append(
                f"weak evidence from {', '.join(models)} " f"({len(weak)} horizon reading(s) ≤ 35)"
            )
        if current_dd is not None and current_dd < -0.25:
            risks.append(f"currently {current_dd:.0%} below its historical peak")
        risks.extend(concentration_flags)
        risks.extend(correlation_flags)
        return tuple(strengths), tuple(risks)
