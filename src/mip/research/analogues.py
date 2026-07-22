"""Historical analogue engine: hierarchical similarity over four domains.

Finds the historical dates whose COMBINED state — market environment,
sector environment, company state, and catalyst timeline — most resembles
the scoring date, then measures what happened to the same holding
afterward. This complements (never replaces) the regime-conditioning
system: regimes ask "when was this exact named condition true?", the
analogue engine asks "when did the whole environment look most similar?".

Staged candidate selection (all knobs on AnalogueConfig):

    1. rank ALL eligible history by market-environment similarity,
       keep the top `market_candidate_count`;
    2. within those, rank by sector-environment similarity, keep
       `sector_candidate_count` (pass-through when no sector benchmark);
    3. rank by company-state similarity;
    4. rerank by the weighted overall similarity (market/sector/company/
       catalyst weights, renormalized over available domains);
    5. temporal deduplication (>= `min_gap_sessions` between analogues),
       keep the top `final_analogue_count`.

Similarity is cosine over per-feature z-scores. Normalization statistics
use only history <= the scoring date (the comparison is made today with
today's knowledge; nothing from after the scoring date enters any
vector). Forward returns are never part of any vector. Candidates need
`minimum_history_days` of prior symbol history; horizons without a
complete forward window are excluded from that horizon's outcomes.
"""

import math
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import FeatureScope
from mip.domain.models import DailyPrice
from mip.repositories.features import FeatureRepository
from mip.repositories.instruments import InstrumentRepository
from mip.research.engine import forward_returns

HORIZONS = {"1w": 5, "2w": 10, "1m": 21, "3m": 63, "6m": 126, "1y": 252}

# -- domain feature sets (all already registered in the Feature Store) -----

MARKET_FEATURES = (
    "fedfunds_level",
    "fedfunds_chg_6m",
    "dgs2_chg_63d",
    "dgs10_chg_63d",
    "curve_slope_10y2y",
    "curve_slope_10y2y_chg_63d",
    "cpi_yoy",
    "cpi_yoy_accel",
    "unrate_chg_6m",
    "payems_yoy",
    "rsafs_yoy",
    "umcsent_chg_6m",
    "vix_level",
    "vix_pctile_252d",
    "vix_chg_21d",
    "sector_breadth_ma50",
    "regime_bull",
    "regime_high_vol",
)
MARKET_CONTEXT = (  # benchmark instrument features completing the market picture
    ("SPY", "ret_63d"),
    ("SPY", "vol_21d"),
    ("SPY", "price_to_ma200"),
    ("QQQ", "ret_63d"),
    ("IWM", "rel_ret_spy_63d"),
    ("XLK", "rel_ret_spy_63d"),
)
SECTOR_ETF_FEATURES = ("ret_21d", "ret_63d", "vol_21d", "rel_ret_spy_63d", "price_to_ma50")
HOLDING_SECTOR_FEATURES = ("rel_ret_sector_21d", "rel_ret_sector_63d", "rel_ret_sector_126d")
COMPANY_FEATURES = (
    "ret_5d",
    "ret_21d",
    "ret_63d",
    "ret_126d",
    "ret_252d",
    "vol_21d",
    "vol_ratio_21_63",
    "price_to_ma50",
    "price_to_ma200",
    "ma50_ma200_spread",
    "dist_52w_high",
    "dist_52w_low",
    "rel_ret_spy_21d",
    "rel_ret_spy_63d",
    "atr14_pct",
)
CATALYST_FEATURES = (
    "days_until_earnings",
    "days_since_earnings",
    "earnings_recency",
    "eps_surprise",
)
DOMAINS = ("market", "sector", "company", "catalysts")


@dataclass(frozen=True)
class AnalogueConfig:
    """Every knob of the analogue search — configuration-driven, never
    hardcoded in the algorithm."""

    market_candidate_count: int = 500
    sector_candidate_count: int = 200
    final_analogue_count: int = 30
    minimum_history_days: int = 504
    minimum_valid_analogues: int = 10
    min_gap_sessions: int = 10  # temporal deduplication between analogues
    market_weight: float = 0.35
    sector_weight: float = 0.20
    company_weight: float = 0.30
    catalyst_weight: float = 0.15
    min_domain_coverage: float = 0.6  # shared-dimension fraction required

    def __post_init__(self) -> None:
        weights = (
            self.market_weight,
            self.sector_weight,
            self.company_weight,
            self.catalyst_weight,
        )
        if any(w < 0 for w in weights) or sum(weights) <= 0:
            raise ConfigurationError("similarity weights must be non-negative and sum > 0")
        if self.final_analogue_count < 1 or self.minimum_valid_analogues < 1:
            raise ConfigurationError("analogue counts must be positive")
        if not 0.0 < self.min_domain_coverage <= 1.0:
            raise ConfigurationError("min_domain_coverage must be in (0, 1]")

    def weight(self, domain: str) -> float:
        return {
            "market": self.market_weight,
            "sector": self.sector_weight,
            "company": self.company_weight,
            "catalysts": self.catalyst_weight,
        }[domain]


@dataclass(frozen=True)
class Analogue:
    """One selected historical date with its per-domain similarity."""

    date: date
    overall: float
    market: float
    sector: float | None
    company: float
    catalysts: float | None
    coverage: float  # shared-dimension fraction across scored domains

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "overall": self.overall,
            "market": self.market,
            "sector": self.sector,
            "company": self.company,
            "catalysts": self.catalysts,
            "coverage": self.coverage,
        }


@dataclass(frozen=True)
class HorizonOutcomes:
    """What happened after the analogues, one horizon — similarity-weighted
    with unweighted statistics kept for comparison. Only analogues with a
    COMPLETE forward window enter (n is the valid count)."""

    horizon: str
    sessions: int
    n: int
    mean_return: float | None
    median_return: float | None
    weighted_mean_return: float | None
    spy_relative_mean: float | None
    sector_relative_mean: float | None
    p_positive: float | None
    p_beat_spy: float | None
    median_max_drawdown: float | None
    median_adverse_excursion: float | None
    median_favorable_excursion: float | None
    mean_forward_vol: float | None
    p10: float | None
    p25: float | None
    p75: float | None
    p90: float | None
    baseline_mean: float | None  # unconditional same-symbol mean, same construction

    def to_dict(self) -> dict:
        return {
            "horizon": self.horizon,
            "sessions": self.sessions,
            "n": self.n,
            "mean_return": self.mean_return,
            "median_return": self.median_return,
            "weighted_mean_return": self.weighted_mean_return,
            "spy_relative_mean": self.spy_relative_mean,
            "sector_relative_mean": self.sector_relative_mean,
            "p_positive": self.p_positive,
            "p_beat_spy": self.p_beat_spy,
            "median_max_drawdown": self.median_max_drawdown,
            "median_adverse_excursion": self.median_adverse_excursion,
            "median_favorable_excursion": self.median_favorable_excursion,
            "mean_forward_vol": self.mean_forward_vol,
            "p10": self.p10,
            "p25": self.p25,
            "p75": self.p75,
            "p90": self.p90,
            "baseline_mean": self.baseline_mean,
        }


@dataclass(frozen=True)
class AnalogueResult:
    symbol: str
    as_of: date
    analogues: tuple[Analogue, ...]
    outcomes: dict[str, HorizonOutcomes] = field(default_factory=dict)
    environment: dict[str, str | float | None] = field(default_factory=dict)
    catalysts: dict[str, float | None] = field(default_factory=dict)
    insufficient: str | None = None  # honest reason when no analogue set exists

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "analogues": [a.to_dict() for a in self.analogues],
            "outcomes": {h: o.to_dict() for h, o in self.outcomes.items()},
            "environment": self.environment,
            "catalysts": self.catalysts,
            "insufficient": self.insufficient,
        }


def cosine_similarity(target: np.ndarray, candidate: np.ndarray) -> tuple[float | None, float]:
    """Cosine over dimensions present in BOTH vectors; returns
    (similarity | None, coverage). Missing dimensions are masked, never
    imputed; insufficient shared coverage yields None upstream."""
    mask = ~(np.isnan(target) | np.isnan(candidate))
    coverage = float(mask.sum()) / len(target) if len(target) else 0.0
    if not mask.any():
        return None, 0.0
    a, b = target[mask], candidate[mask]
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    if norm == 0.0:
        return 0.0, coverage
    return float(np.dot(a, b) / norm), coverage


def zscore_frame(frame: pd.DataFrame, through: pd.Timestamp) -> pd.DataFrame:
    """Per-column z-scores using ONLY history <= `through` (point-in-time
    with respect to the scoring date). Constant columns are dropped."""
    basis = frame.loc[:through]
    mean = basis.mean()
    std = basis.std(ddof=0)
    keep = std[std > 0].index
    return (frame[keep] - mean[keep]) / std[keep]


class AnalogueEngine:
    """Reads ONLY the feature stores and daily prices — the same access
    surface as the research engine it belongs beside."""

    def __init__(self, session: Session, config: AnalogueConfig | None = None) -> None:
        self._session = session
        self._features = FeatureRepository(session)
        self._instruments = InstrumentRepository(session)
        self._config = config or AnalogueConfig()

    # -- public ------------------------------------------------------------

    def find(self, symbol: str, as_of: date | None = None) -> AnalogueResult:
        symbol = symbol.strip().upper()
        cfg = self._config
        frames = self._domain_frames(symbol)
        company = frames["company"]
        if company.empty:
            raise ConfigurationError(f"no company features stored for {symbol!r}")

        target_ts = self._resolve_as_of(company, as_of)
        resolved = target_ts.date()
        scored = {name: zscore_frame(frame, target_ts) for name, frame in frames.items()}

        index = company.index
        target_pos = index.get_loc(target_ts)
        # candidates need full prior history AND must sit at least the
        # dedup gap before the scoring date (yesterday is not an analogue,
        # it is autocorrelation)
        cutoff = max(0, target_pos - cfg.min_gap_sessions)
        candidates = list(index[cfg.minimum_history_days : cutoff])
        environment = self._environment_labels(frames["market"], target_ts)
        catalysts = self._catalyst_snapshot(frames["catalysts"], target_ts)
        if len(candidates) < cfg.minimum_valid_analogues:
            return AnalogueResult(
                symbol=symbol,
                as_of=resolved,
                analogues=(),
                environment=environment,
                catalysts=catalysts,
                insufficient=(
                    f"only {len(candidates)} candidate dates have the required "
                    f"{cfg.minimum_history_days} sessions of prior history"
                ),
            )

        similarities = self._staged_selection(scored, target_ts, candidates)
        if len(similarities) < cfg.minimum_valid_analogues:
            return AnalogueResult(
                symbol=symbol,
                as_of=resolved,
                analogues=(),
                environment=environment,
                catalysts=catalysts,
                insufficient=(
                    f"only {len(similarities)} candidates share enough feature coverage "
                    f"(need {cfg.minimum_valid_analogues})"
                ),
            )
        deduped = self._deduplicate(similarities, index)
        chosen = deduped[: cfg.final_analogue_count]
        if len(chosen) < cfg.minimum_valid_analogues:
            return AnalogueResult(
                symbol=symbol,
                as_of=resolved,
                analogues=(),
                environment=environment,
                catalysts=catalysts,
                insufficient=(
                    f"only {len(chosen)} analogues remain after temporal deduplication "
                    f"(need {cfg.minimum_valid_analogues})"
                ),
            )
        outcomes = self._outcomes(symbol, chosen, candidates, target_ts)
        return AnalogueResult(
            symbol=symbol,
            as_of=resolved,
            analogues=tuple(chosen),
            outcomes=outcomes,
            environment=environment,
            catalysts=catalysts,
        )

    def environment(self, as_of: date | None = None) -> dict[str, str | float | None]:
        """Deterministic market-environment labels for a date (diagnostics)."""
        market = {name: self._series(name) for name in MARKET_FEATURES}
        market.update({f"{sym}:{name}": self._series(name, sym) for sym, name in MARKET_CONTEXT})
        frame = pd.DataFrame(market)
        if frame.empty:
            raise ConfigurationError("no market features stored")
        ts = (
            frame.index[-1]
            if as_of is None
            else frame.index[frame.index <= pd.Timestamp(as_of)][-1]
        )
        return {"as_of": ts.date().isoformat(), **self._environment_labels(frame, ts)}

    def catalyst_state(self, symbol: str, as_of: date | None = None) -> dict[str, float | None]:
        """Point-in-time catalyst snapshot for one holding (diagnostics)."""
        symbol = symbol.strip().upper()
        frame = pd.DataFrame({name: self._series(name, symbol) for name in CATALYST_FEATURES})
        if frame.empty or len(frame.index) == 0:
            return {name: None for name in CATALYST_FEATURES}
        eligible = frame.index if as_of is None else frame.index[frame.index <= pd.Timestamp(as_of)]
        if len(eligible) == 0:
            return {name: None for name in CATALYST_FEATURES}
        return self._catalyst_snapshot(frame, eligible[-1])

    # -- domain data -------------------------------------------------------

    def _series(self, name: str, instrument_symbol: str | None = None) -> pd.Series:
        definition = self._features.get_definition(name)
        if definition is None:
            return pd.Series(dtype=float)
        if definition.scope is FeatureScope.MARKET:
            return self._features.get_market_series(definition.id)
        instrument = self._instruments.get_by_symbol(instrument_symbol)
        if instrument is None:
            return pd.Series(dtype=float)
        return self._features.get_instrument_series(definition.id, instrument.id)

    def _domain_frames(self, symbol: str) -> dict[str, pd.DataFrame]:
        market = {name: self._series(name) for name in MARKET_FEATURES}
        market.update({f"{sym}:{name}": self._series(name, sym) for sym, name in MARKET_CONTEXT})
        company = {name: self._series(name, symbol) for name in COMPANY_FEATURES}
        catalysts = {name: self._series(name, symbol) for name in CATALYST_FEATURES}

        sector: dict[str, pd.Series] = {}
        instrument = self._instruments.get_by_symbol(symbol)
        etf = self._instruments.sector_etf_symbol(instrument) if instrument is not None else None
        if etf is not None and etf != symbol:
            sector.update({f"etf:{name}": self._series(name, etf) for name in SECTOR_ETF_FEATURES})
            sector.update({name: self._series(name, symbol) for name in HOLDING_SECTOR_FEATURES})
        self._sector_etf = etf

        return {
            "market": pd.DataFrame(market),
            "sector": pd.DataFrame(sector),
            "company": pd.DataFrame(company),
            "catalysts": pd.DataFrame(catalysts),
        }

    def _resolve_as_of(self, company: pd.DataFrame, as_of: date | None) -> pd.Timestamp:
        index = company.index
        if as_of is None:
            return index[-1]
        eligible = index[index <= pd.Timestamp(as_of)]
        if len(eligible) == 0:
            raise ConfigurationError(f"no features on or before {as_of.isoformat()}")
        return eligible[-1]

    # -- selection ---------------------------------------------------------

    def _domain_similarity(
        self, scored: pd.DataFrame, target_ts: pd.Timestamp, ts: pd.Timestamp
    ) -> tuple[float | None, float]:
        if scored.empty or target_ts not in scored.index or ts not in scored.index:
            return None, 0.0
        similarity, coverage = cosine_similarity(
            scored.loc[target_ts].to_numpy(dtype=float),
            scored.loc[ts].to_numpy(dtype=float),
        )
        if similarity is None or coverage < self._config.min_domain_coverage:
            return None, coverage
        return similarity, coverage

    def _staged_selection(
        self,
        scored: dict[str, pd.DataFrame],
        target_ts: pd.Timestamp,
        candidates: list[pd.Timestamp],
    ) -> list[Analogue]:
        cfg = self._config

        # stage 1 — market environment
        market_ranked: list[tuple[pd.Timestamp, float, float]] = []
        for ts in candidates:
            similarity, coverage = self._domain_similarity(scored["market"], target_ts, ts)
            if similarity is not None:
                market_ranked.append((ts, similarity, coverage))
        market_ranked.sort(key=lambda item: (-item[1], item[0]))
        stage = market_ranked[: cfg.market_candidate_count]

        # stage 2 — sector environment (pass-through without a benchmark)
        sector_scores: dict[pd.Timestamp, tuple[float | None, float]] = {}
        if not scored["sector"].empty:
            enriched = []
            for ts, market_sim, coverage in stage:
                sector_sim, sector_cov = self._domain_similarity(scored["sector"], target_ts, ts)
                sector_scores[ts] = (sector_sim, sector_cov)
                enriched.append((ts, market_sim, coverage, sector_sim))
            enriched.sort(key=lambda item: (-(item[3] if item[3] is not None else -2.0), item[0]))
            stage = [(ts, m, c) for ts, m, c, _ in enriched[: cfg.sector_candidate_count]]

        # stages 3 + 4 — company ranking, catalyst rerank via weighted overall
        analogues: list[Analogue] = []
        for ts, market_sim, market_cov in stage:
            company_sim, company_cov = self._domain_similarity(scored["company"], target_ts, ts)
            if company_sim is None:
                continue
            sector_sim, sector_cov = sector_scores.get(ts, (None, 0.0))
            catalyst_sim, catalyst_cov = self._domain_similarity(scored["catalysts"], target_ts, ts)
            parts: dict[str, float | None] = {
                "market": market_sim,
                "sector": sector_sim,
                "company": company_sim,
                "catalysts": catalyst_sim,
            }
            weight_total = sum(self._config.weight(d) for d, v in parts.items() if v is not None)
            overall = (
                sum(self._config.weight(d) * v for d, v in parts.items() if v is not None)
                / weight_total
            )
            coverages = [market_cov, company_cov] + [
                c
                for c, v in ((sector_cov, sector_sim), (catalyst_cov, catalyst_sim))
                if v is not None
            ]
            analogues.append(
                Analogue(
                    date=ts.date(),
                    overall=overall,
                    market=market_sim,
                    sector=sector_sim,
                    company=company_sim,
                    catalysts=catalyst_sim,
                    coverage=float(np.mean(coverages)),
                )
            )
        analogues.sort(key=lambda a: (-a.overall, a.date))
        return analogues

    def _deduplicate(self, ranked: list[Analogue], index: pd.DatetimeIndex) -> list[Analogue]:
        """Best-first greedy selection with a minimum session gap, so a
        single episode cannot flood the analogue set with adjacent days."""
        positions = {ts.date(): pos for pos, ts in enumerate(index)}
        kept: list[Analogue] = []
        kept_positions: list[int] = []
        gap = self._config.min_gap_sessions
        for analogue in ranked:
            pos = positions[analogue.date]
            if all(abs(pos - other) >= gap for other in kept_positions):
                kept.append(analogue)
                kept_positions.append(pos)
        return kept

    # -- outcomes ----------------------------------------------------------

    def _adj_close(self, symbol: str) -> pd.Series:
        instrument = self._instruments.get_by_symbol(symbol)
        if instrument is None:
            return pd.Series(dtype=float)
        rows = self._session.execute(
            select(DailyPrice.price_date, DailyPrice.adj_close)
            .where(DailyPrice.instrument_id == instrument.id, DailyPrice.adj_close.is_not(None))
            .order_by(DailyPrice.price_date)
        ).all()
        if not rows:
            return pd.Series(dtype=float)
        return pd.Series(
            [float(r[1]) for r in rows],
            index=pd.DatetimeIndex(pd.to_datetime([r[0] for r in rows])),
        )

    def _outcomes(
        self,
        symbol: str,
        analogues: list[Analogue],
        candidate_universe: list[pd.Timestamp],
        as_of_ts: pd.Timestamp,
    ) -> dict[str, HorizonOutcomes]:
        # PIT alignment: outcomes may use only prices observable by as_of —
        # analogue windows crossing the scoring date yield NaN and drop out
        # per horizon, exactly as they do in live inference.
        prices = self._adj_close(symbol).loc[:as_of_ts]
        spy = self._adj_close("SPY").loc[:as_of_ts]
        etf = getattr(self, "_sector_etf", None)
        sector_prices = self._adj_close(etf).loc[:as_of_ts] if etf else pd.Series(dtype=float)

        events = pd.DatetimeIndex([pd.Timestamp(a.date) for a in analogues])
        horizons = tuple(HORIZONS.values())
        own = forward_returns(prices, events, horizons)
        spy_fwd = (
            forward_returns(spy, events, horizons) if not spy.empty else pd.DataFrame(index=events)
        )
        sector_fwd = (
            forward_returns(sector_prices, events, horizons)
            if not sector_prices.empty
            else pd.DataFrame(index=events)
        )
        baseline_events = pd.DatetimeIndex(candidate_universe)
        baseline_fwd = forward_returns(prices, baseline_events, horizons)
        weights_all = np.array([a.overall for a in analogues], dtype=float)

        results: dict[str, HorizonOutcomes] = {}
        values = prices.to_numpy()
        position_of = {ts: pos for pos, ts in enumerate(prices.index)}
        for label, sessions in HORIZONS.items():
            column = own[f"fwd_{sessions}d"].to_numpy(dtype=float)
            valid = ~np.isnan(column)
            n = int(valid.sum())
            if n == 0:
                results[label] = HorizonOutcomes(label, sessions, 0, *([None] * 16))
                continue
            returns = column[valid]
            weights = weights_all[valid]
            weights = weights / weights.sum() if weights.sum() > 0 else None
            path_mdd, path_mae, path_mfe, path_vol = [], [], [], []
            for ts in events[valid]:
                pos = position_of.get(ts)
                window = values[pos : pos + sessions + 1]
                path = window / window[0]
                path_mae.append(float(path[1:].min() - 1.0))
                path_mfe.append(float(path[1:].max() - 1.0))
                path_mdd.append(float((window / np.maximum.accumulate(window) - 1.0).min()))
                log_rets = np.diff(np.log(window))
                path_vol.append(
                    float(log_rets.std(ddof=1) * math.sqrt(252)) if len(log_rets) > 1 else 0.0
                )
            spy_col = (
                spy_fwd[f"fwd_{sessions}d"].to_numpy(dtype=float)[valid]
                if f"fwd_{sessions}d" in spy_fwd
                else np.full(n, np.nan)
            )
            sector_col = (
                sector_fwd[f"fwd_{sessions}d"].to_numpy(dtype=float)[valid]
                if f"fwd_{sessions}d" in sector_fwd
                else np.full(n, np.nan)
            )
            spy_ok = ~np.isnan(spy_col)
            sector_ok = ~np.isnan(sector_col)
            baseline_col = baseline_fwd[f"fwd_{sessions}d"].to_numpy(dtype=float)
            baseline_col = baseline_col[~np.isnan(baseline_col)]

            results[label] = HorizonOutcomes(
                horizon=label,
                sessions=sessions,
                n=n,
                mean_return=float(returns.mean()),
                median_return=float(np.median(returns)),
                weighted_mean_return=(
                    float(np.dot(weights, returns))
                    if weights is not None
                    else float(returns.mean())
                ),
                spy_relative_mean=(
                    float((returns[spy_ok] - spy_col[spy_ok]).mean()) if spy_ok.any() else None
                ),
                sector_relative_mean=(
                    float((returns[sector_ok] - sector_col[sector_ok]).mean())
                    if sector_ok.any()
                    else None
                ),
                p_positive=float((returns > 0).mean()),
                p_beat_spy=(
                    float((returns[spy_ok] > spy_col[spy_ok]).mean()) if spy_ok.any() else None
                ),
                median_max_drawdown=float(np.median(path_mdd)),
                median_adverse_excursion=float(np.median(path_mae)),
                median_favorable_excursion=float(np.median(path_mfe)),
                mean_forward_vol=float(np.mean(path_vol)),
                p10=float(np.percentile(returns, 10)),
                p25=float(np.percentile(returns, 25)),
                p75=float(np.percentile(returns, 75)),
                p90=float(np.percentile(returns, 90)),
                baseline_mean=(float(baseline_col.mean()) if len(baseline_col) else None),
            )
        return results

    # -- environment & catalyst snapshots (deterministic labels) -----------

    def _environment_labels(
        self, market: pd.DataFrame, ts: pd.Timestamp
    ) -> dict[str, str | float | None]:
        def latest(name: str) -> float | None:
            if name not in market.columns:
                return None
            series = market[name].loc[:ts].dropna()
            return float(series.iloc[-1]) if len(series) else None

        vix_pct = latest("vix_pctile_252d")
        breadth = latest("sector_breadth_ma50")
        labels: dict[str, str | float | None] = {
            "trend": {1.0: "bull", 0.0: "bear"}.get(latest("regime_bull") or -1.0),
            "rates": (
                "rising"
                if (latest("dgs10_chg_63d") or 0) > 0.25
                else "falling" if (latest("dgs10_chg_63d") or 0) < -0.25 else "stable"
            ),
            "fed_funds": latest("fedfunds_level"),
            "inflation": (
                "accelerating"
                if (latest("cpi_yoy_accel") or 0) > 0
                else "decelerating" if latest("cpi_yoy_accel") is not None else None
            ),
            "volatility": (
                "elevated"
                if (vix_pct or 0) >= 0.8
                else "low" if (vix_pct or 1) <= 0.2 else "normal"
            ),
            "vix": latest("vix_level"),
            "breadth": (
                (
                    "strong"
                    if (breadth or 0) >= 0.7
                    else "weak" if (breadth or 1) <= 0.3 else "mixed"
                )
                if breadth is not None
                else None
            ),
            "technology_leadership": None,
            "small_cap_leadership": None,
        }
        xlk = latest("XLK:rel_ret_spy_63d")
        if xlk is not None:
            labels["technology_leadership"] = "leading" if xlk > 0 else "lagging"
        iwm = latest("IWM:rel_ret_spy_63d")
        if iwm is not None:
            labels["small_cap_leadership"] = "leading" if iwm > 0 else "lagging"
        return labels

    def _catalyst_snapshot(
        self, catalysts: pd.DataFrame, ts: pd.Timestamp
    ) -> dict[str, float | None]:
        snapshot: dict[str, float | None] = {}
        for name in CATALYST_FEATURES:
            if name in catalysts.columns:
                series = catalysts[name].loc[:ts].dropna()
                value = float(series.iloc[-1]) if len(series) else None
                # stale "days until" values are meaningless once the date passed
                if name == "days_until_earnings" and len(series):
                    if series.index[-1] != ts:
                        value = None
                snapshot[name] = value
            else:
                snapshot[name] = None
        return snapshot
