"""Momentum continuation vs overextension: a low-dimensional conditional-bucket study.

RESEARCH ONLY. Nothing here may be imported by ``mip.product``. This module
emits no recommendation, no score and no production artifact; it answers one
pre-registered question (``data/validation/momentum_state_v1/prereg.json``):

    when a stock sits in an extreme momentum state, does its own point-in-time
    history support CONTINUATION or OVEREXTENSION, conditional on market state?

Deliberately NOT a similarity engine. No nearest neighbours, no learned
distance, no feature weighting, no clustering. A state is a pair of integers:
a momentum bucket and a market-regime cell. That is the whole model, and it is
the point -- the two prior engines failed partly through high-dimensional
matching that could not be interpreted or falsified cleanly.

Point-in-time discipline (all three are load-bearing):

* momentum percentile at t uses ONLY observations up to and including t, so a
  stock's "extreme" is judged against the history a reader would have had;
* the forward window is taken from the instrument's own realised sessions, so
  holidays and sparse histories are handled by construction;
* an observation at t is admitted to a split only when its complete outcome
  window closed inside that split -- the embargo rule of
  ``mip.validation.eligibility`` applied to a split boundary rather than a
  scoring date.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
from sqlalchemy import text

from mip.research.outcomes import (
    calendar_episodes,
    distinct_years,
    herfindahl,
    path_excursions,
    wilson_interval,
)

# ---- frozen design constants (see prereg.json; changing one is a version bump)
BUCKET_EDGES: tuple[float, ...] = (0.0, 0.20, 0.40, 0.60, 0.80, 0.90, 0.95, 0.99, 1.0)
BUCKET_LABELS: tuple[str, ...] = (
    "0-20",
    "20-40",
    "40-60",
    "60-80",
    "80-90",
    "90-95",
    "95-99",
    "99-100",
)
HORIZONS: dict[str, int] = {"1w": 5, "1m": 21}
MIN_OWN_HISTORY = 252  # observations required before a percentile is defined
MIN_EPISODES = 30  # prereg floor for any bucket used in a conclusion
SPLIT = date(2022, 1, 1)  # design < SPLIT <= holdout
BOOTSTRAP_BLOCK = 4
BOOTSTRAP_DRAWS = 1000
BOOTSTRAP_SEED = 7
BENCHMARK = "SPY"


def bucket_of(pct: float) -> int:
    """Index of the momentum bucket holding ``pct`` (percentile in [0,1])."""
    for i in range(len(BUCKET_EDGES) - 1):
        hi = BUCKET_EDGES[i + 1]
        if pct < hi or (i == len(BUCKET_EDGES) - 2 and pct <= hi):
            return i
    return len(BUCKET_LABELS) - 1


@dataclass(frozen=True, slots=True)
class Observation:
    """One (symbol, date) state with its realised forward outcomes."""

    symbol: str
    obs_date: date
    momentum_pct: float
    bucket: int
    regime_bull: int
    regime_high_vol: int
    rel_spy_63d_positive: int
    fwd: dict[str, float]  # horizon -> raw forward return
    excess: dict[str, float]  # horizon -> forward return minus SPY's
    mae: dict[str, float]
    mfe: dict[str, float]
    outcome_end: dict[str, date]  # horizon -> date the window closed

    @property
    def regime(self) -> int:
        return self.regime_bull * 2 + self.regime_high_vol


REGIME_LABELS = {0: "BEAR/NORMVOL", 1: "BEAR/HIGHVOL", 2: "BULL/NORMVOL", 3: "BULL/HIGHVOL"}


# ---------------------------------------------------------------- data loading
def load_price_series(
    session, symbols: Sequence[str] | None = None
) -> dict[str, tuple[list[date], np.ndarray]]:
    """Adjusted closes per symbol, ascending. Sole price source for the study."""
    sql = (
        "select i.symbol, p.price_date, p.adj_close from daily_prices p "
        "join instruments i on i.id = p.instrument_id "
        + ("where i.symbol = any(:syms) " if symbols else "")
        + "order by i.symbol, p.price_date"
    )
    params = {"syms": list(symbols)} if symbols else {}
    out: dict[str, tuple[list[date], list[float]]] = {}
    for sym, d, close in session.execute(text(sql), params):
        if close is None:
            continue
        dd, cc = out.setdefault(sym, ([], []))
        dd.append(d)
        cc.append(float(close))
    return {s: (dd, np.asarray(cc, dtype=float)) for s, (dd, cc) in out.items()}


def eligible_symbols(session, first_price_on_or_before: date, min_sessions: int) -> list[str]:
    """Universe rule, frozen in the pre-registration."""
    rows = session.execute(
        text(
            "select i.symbol from daily_prices p join instruments i on i.id = p.instrument_id "
            "group by i.symbol having min(p.price_date) <= :cut and count(*) >= :n "
            "order by i.symbol"
        ),
        {"cut": first_price_on_or_before, "n": min_sessions},
    ).scalars()
    return list(rows)


def load_market_regime(session) -> dict[date, tuple[int, int]]:
    """``{date: (regime_bull, regime_high_vol)}`` from the market feature store.

    Both are pre-existing versioned features (SPY>200MA; VIX>25). The study
    invents no threshold of its own.
    """
    rows = session.execute(
        text(
            "select f.feature_date, d.name, f.value from feature_store_market_daily f "
            "join feature_definitions d on d.id = f.feature_id "
            "where d.name in ('regime_bull','regime_high_vol') and f.value is not null"
        )
    ).all()
    acc: dict[date, dict[str, float]] = {}
    for fdate, name, value in rows:
        acc.setdefault(fdate, {})[name] = float(value)
    return {
        d: (int(v["regime_bull"]), int(v["regime_high_vol"]))
        for d, v in acc.items()
        if "regime_bull" in v and "regime_high_vol" in v
    }


# --------------------------------------------------------- observation building
def _pit_percentile_series(returns: np.ndarray, min_history: int) -> np.ndarray:
    """Expanding-window percentile of each value within the values seen so far.

    Strictly point-in-time: index i is ranked against 0..i only, and the value
    is the fraction STRICTLY BELOW it (so a new all-time high scores (k-1)/k,
    never 1.0). NaN until ``min_history`` observations exist.

    Implemented with a Fenwick tree over the pre-sorted rank space: O(n log n).
    A naive ordered-insert is O(n^2) and does not finish on a 443-symbol
    universe.

    TIE SEMANTICS ARE PART OF THE SPECIFICATION, not an accident of the
    implementation. This counts values STRICTLY BELOW x. An earlier
    ordered-insert draft used ``bisect_right``, which counts values <= x, so the
    two disagree wherever exact ties occur (~0.6% of real ret_21d values, but up
    to 54% for symbols with long flat-price stretches). That draft was abandoned
    on performance grounds before it produced any result: every authoritative
    artifact under data/validation/momentum_state_v1/ was generated by THIS
    function. The behaviour is locked by
    tests/unit/test_momentum_state.py::test_percentile_tie_semantics_are_strictly_below.
    """
    n = returns.size
    out = np.full(n, np.nan)
    finite = ~np.isnan(returns)
    if not finite.any():
        return out
    # dense ranks over the whole series: rank space only, never a value lookahead
    vals = returns[finite]
    order = np.argsort(vals, kind="mergesort")
    ranks_sorted = np.empty(order.size, dtype=np.int64)
    ranks_sorted[order] = np.arange(order.size)
    uniq, inv = np.unique(vals, return_inverse=True)
    size = uniq.size + 1
    tree = np.zeros(size + 1, dtype=np.int64)

    def add(i: int) -> None:
        i += 1
        while i <= size:
            tree[i] += 1
            i += i & (-i)

    def prefix(i: int) -> int:
        i += 1
        total = 0
        while i > 0:
            total += tree[i]
            i -= i & (-i)
        return int(total)

    seen = 0
    k = 0
    for i in range(n):
        if not finite[i]:
            continue
        r = int(inv[k])
        k += 1
        below = prefix(r - 1) if r > 0 else 0
        add(r)
        seen += 1
        if seen >= min_history:
            out[i] = below / seen
    return out


def build_observations(
    prices: dict[str, tuple[list[date], np.ndarray]],
    regime: dict[date, tuple[int, int]],
    momentum_window: int = 21,
) -> list[Observation]:
    """Every (symbol, date) with a defined PIT momentum percentile, a known
    market regime, and at least one realised forward window."""
    bench = prices.get(BENCHMARK)
    if bench is None:
        raise ValueError(f"{BENCHMARK} prices are required for excess returns")
    bench_dates, bench_close = bench
    bench_index = {d: i for i, d in enumerate(bench_dates)}

    max_h = max(HORIZONS.values())
    observations: list[Observation] = []

    for symbol, (dates, close) in sorted(prices.items()):
        n = close.size
        if n < MIN_OWN_HISTORY + momentum_window + max_h:
            continue
        ret = np.full(n, np.nan)
        ret[momentum_window:] = close[momentum_window:] / close[:-momentum_window] - 1.0
        pct = _pit_percentile_series(ret, MIN_OWN_HISTORY)

        rel = np.full(n, np.nan)
        if n > 63:
            rel[63:] = close[63:] / close[:-63] - 1.0

        for i in range(n - 1):
            p = pct[i]
            if math.isnan(p):
                continue
            d = dates[i]
            reg = regime.get(d)
            if reg is None:
                continue
            bi = bench_index.get(d)
            if bi is None:
                continue

            fwd: dict[str, float] = {}
            excess: dict[str, float] = {}
            mae: dict[str, float] = {}
            mfe: dict[str, float] = {}
            end: dict[str, date] = {}
            for label, h in HORIZONS.items():
                if i + h >= n or bi + h >= bench_close.size:
                    continue
                r = close[i + h] / close[i] - 1.0
                b = bench_close[bi + h] / bench_close[bi] - 1.0
                _, a_exc, f_exc = path_excursions(close[i : i + h + 1])
                fwd[label] = float(r)
                excess[label] = float(r - b)
                mae[label] = float(a_exc)
                mfe[label] = float(f_exc)
                end[label] = dates[i + h]
            if not fwd:
                continue

            rel_pos = 0
            if not math.isnan(rel[i]):
                bench_rel = (
                    bench_close[bi] / bench_close[bi - 63] - 1.0 if bi >= 63 else float("nan")
                )
                if not math.isnan(bench_rel):
                    rel_pos = int(rel[i] - bench_rel > 0)

            observations.append(
                Observation(
                    symbol=symbol,
                    obs_date=d,
                    momentum_pct=float(p),
                    bucket=bucket_of(float(p)),
                    regime_bull=reg[0],
                    regime_high_vol=reg[1],
                    rel_spy_63d_positive=rel_pos,
                    fwd=fwd,
                    excess=excess,
                    mae=mae,
                    mfe=mfe,
                    outcome_end=end,
                )
            )
    return observations


# ------------------------------------------------------------------ PIT splits
def split_observations(
    observations: Sequence[Observation], horizon: str, boundary: date = SPLIT
) -> tuple[list[Observation], list[Observation]]:
    """Design / holdout partition under the embargo rule.

    An observation belongs to DESIGN only when its whole outcome window closed
    strictly before the boundary; to HOLDOUT only when the observation itself is
    on or after the boundary. Observations straddling the boundary are dropped
    from both -- that gap is the embargo, and it is why no design-period label
    can contain post-boundary information.
    """
    design: list[Observation] = []
    holdout: list[Observation] = []
    for o in observations:
        end = o.outcome_end.get(horizon)
        if end is None:
            continue
        if end < boundary:
            design.append(o)
        elif o.obs_date >= boundary:
            holdout.append(o)
    return design, holdout


def leakage_violations(
    design: Sequence[Observation],
    holdout: Sequence[Observation],
    horizon: str,
    boundary: date = SPLIT,
) -> list[str]:
    """Any design label reaching past the boundary, or any holdout observation
    dated before it. Must be empty."""
    bad: list[str] = []
    for o in design:
        end = o.outcome_end.get(horizon)
        if end is not None and end >= boundary:
            bad.append(f"design {o.symbol}@{o.obs_date} outcome closes {end} >= {boundary}")
    for o in holdout:
        if o.obs_date < boundary:
            bad.append(f"holdout {o.symbol}@{o.obs_date} predates {boundary}")
    return bad


# ------------------------------------------------------------------ statistics
@dataclass(frozen=True, slots=True)
class CellStats:
    label: str
    n_raw: int
    n_episodes: int
    n_years: int
    n_symbols: int
    year_hhi: float
    acc_excess_positive: float  # = P(excess > 0), the directional target
    wilson: tuple[float, float]
    median_raw: float
    mean_raw: float
    p_raw_positive: float
    median_excess: float
    mean_excess: float
    p_raw_gt_5: float
    p_raw_lt_neg5: float
    median_mae: float
    median_mfe: float

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "n_raw": self.n_raw,
            "n_episodes": self.n_episodes,
            "n_years": self.n_years,
            "n_symbols": self.n_symbols,
            "year_concentration": round(self.year_hhi, 4),
            "p_excess_positive": round(self.acc_excess_positive, 4),
            "wilson_low": round(self.wilson[0], 4),
            "wilson_high": round(self.wilson[1], 4),
            "median_raw": round(self.median_raw, 5),
            "mean_raw": round(self.mean_raw, 5),
            "p_raw_positive": round(self.p_raw_positive, 4),
            "median_excess": round(self.median_excess, 5),
            "mean_excess": round(self.mean_excess, 5),
            "p_raw_gt_5pct": round(self.p_raw_gt_5, 4),
            "p_raw_lt_neg5pct": round(self.p_raw_lt_neg5, 4),
            "median_mae": round(self.median_mae, 5),
            "median_mfe": round(self.median_mfe, 5),
            "meets_episode_floor": self.n_episodes >= MIN_EPISODES,
        }


def summarise(observations: Sequence[Observation], horizon: str, label: str) -> CellStats:
    """All pre-registered statistics for one pooled cell."""
    obs = [o for o in observations if horizon in o.fwd]
    if not obs:
        return CellStats(label, 0, 0, 0, 0, 0.0, float("nan"), (0.0, 1.0), *(float("nan"),) * 8)
    raw = np.array([o.fwd[horizon] for o in obs])
    exc = np.array([o.excess[horizon] for o in obs])
    mae = np.array([o.mae[horizon] for o in obs])
    mfe = np.array([o.mfe[horizon] for o in obs])
    dates = [o.obs_date for o in obs]
    episodes = calendar_episodes(dates, HORIZONS[horizon])
    n_eps = len(set(episodes))
    p_exc = float((exc > 0).mean())
    return CellStats(
        label=label,
        n_raw=len(obs),
        n_episodes=n_eps,
        n_years=distinct_years(dates),
        n_symbols=len({o.symbol for o in obs}),
        year_hhi=herfindahl([d.year for d in dates]),
        acc_excess_positive=p_exc,
        wilson=wilson_interval(p_exc, float(n_eps)),
        median_raw=float(np.median(raw)),
        mean_raw=float(raw.mean()),
        p_raw_positive=float((raw > 0).mean()),
        median_excess=float(np.median(exc)),
        mean_excess=float(exc.mean()),
        p_raw_gt_5=float((raw > 0.05).mean()),
        p_raw_lt_neg5=float((raw < -0.05).mean()),
        median_mae=float(np.median(mae)),
        median_mfe=float(np.median(mfe)),
    )


# ---------------------------------------------------- predictors and evaluation
def _rate_map(observations: Sequence[Observation], horizon: str, key) -> dict:
    """P(excess > 0) per key, learned on the DESIGN period only."""
    acc: dict[object, list[float]] = {}
    for o in observations:
        if horizon in o.excess:
            acc.setdefault(key(o), []).append(o.excess[horizon])
    return {k: float(np.mean([v > 0 for v in vs])) for k, vs in acc.items() if vs}


K_MOM = lambda o: o.bucket  # noqa: E731
K_REG = lambda o: o.regime  # noqa: E731
K_BOTH = lambda o: (o.bucket, o.regime)  # noqa: E731
K_BOTH_REL = lambda o: (o.bucket, o.regime, o.rel_spy_63d_positive)  # noqa: E731

SYSTEMS = {
    "momentum_only": K_MOM,
    "regime_only": K_REG,
    "momentum_plus_regime": K_BOTH,
    "momentum_regime_relstrength": K_BOTH_REL,
}


def evaluate(
    design: Sequence[Observation], holdout: Sequence[Observation], horizon: str, key
) -> tuple[float, list[int], list[date]]:
    """Fit P(excess>0) per state on design, predict sign on holdout.

    Returns ``(accuracy, correct_flags, dates)``. A state unseen in design, or
    one whose design rate is exactly 0.5, abstains and is scored as the
    prior-free coin flip -- it is excluded rather than silently credited.
    """
    rates = _rate_map(design, horizon, key)
    flags: list[int] = []
    dates: list[date] = []
    for o in holdout:
        if horizon not in o.excess:
            continue
        r = rates.get(key(o))
        if r is None or r == 0.5:
            continue
        predicted_up = r > 0.5
        actual_up = o.excess[horizon] > 0
        flags.append(int(predicted_up == actual_up))
        dates.append(o.obs_date)
    if not flags:
        return float("nan"), [], []
    return float(np.mean(flags)), flags, dates


def paired_delta_bootstrap(
    design: Sequence[Observation],
    holdout: Sequence[Observation],
    horizon: str,
    key_a,
    key_b,
) -> dict:
    """Circular block bootstrap of (accuracy_a - accuracy_b) on PAIRED cells.

    Only observations both systems score are used, so the delta is not
    contaminated by differing abstention. Blocks are contiguous runs of the
    date-ordered cohort, which is how serial and cross-sectional dependence
    enters -- same-day rows sit in the same block.
    """
    rates_a = _rate_map(design, horizon, key_a)
    rates_b = _rate_map(design, horizon, key_b)
    paired: list[tuple[date, int, int]] = []
    for o in holdout:
        if horizon not in o.excess:
            continue
        ra, rb = rates_a.get(key_a(o)), rates_b.get(key_b(o))
        if ra is None or rb is None or ra == 0.5 or rb == 0.5:
            continue
        actual = o.excess[horizon] > 0
        paired.append((o.obs_date, int((ra > 0.5) == actual), int((rb > 0.5) == actual)))
    if not paired:
        return {"n": 0, "delta": float("nan"), "ci_low": float("nan"), "ci_high": float("nan")}

    paired.sort(key=lambda t: t[0])
    a = np.array([p[1] for p in paired], dtype=float)
    b = np.array([p[2] for p in paired], dtype=float)
    diff = a - b
    point = float(diff.mean())

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    n = diff.size
    n_blocks = max(1, n // BOOTSTRAP_BLOCK)
    offsets = np.arange(BOOTSTRAP_BLOCK)
    draws = np.empty(BOOTSTRAP_DRAWS)
    for k in range(BOOTSTRAP_DRAWS):
        starts = rng.integers(0, n, size=n_blocks)
        idx = (starts[:, None] + offsets) % n
        draws[k] = float(diff[idx].mean())
    low, high = np.percentile(draws, [2.5, 97.5])
    return {
        "n": n,
        "delta": point,
        "ci_low": float(low),
        "ci_high": float(high),
        "accuracy_a": float(a.mean()),
        "accuracy_b": float(b.mean()),
    }


def expected_calibration_error(
    design: Sequence[Observation], holdout: Sequence[Observation], horizon: str, key, bins: int = 10
) -> float:
    """ECE of the design-fitted P(excess>0) against holdout frequency."""
    rates = _rate_map(design, horizon, key)
    pairs = [
        (rates[key(o)], float(o.excess[horizon] > 0))
        for o in holdout
        if horizon in o.excess and key(o) in rates
    ]
    if not pairs:
        return float("nan")
    p = np.array([x[0] for x in pairs])
    y = np.array([x[1] for x in pairs])
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for i in range(bins):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= edges[i + 1])
        if m.sum() == 0:
            continue
        ece += (m.sum() / p.size) * abs(y[m].mean() - p[m].mean())
    return float(ece)


def confidence_inversion(
    design: Sequence[Observation], holdout: Sequence[Observation], horizon: str, key
) -> dict:
    """Accuracy split by the episode count backing each state's design estimate.

    The pre-declared disqualifier from both prior engines: if states with MORE
    supporting evidence predict WORSE, the confidence notion is inverted.
    """
    counts: dict[object, list[date]] = {}
    for o in design:
        if horizon in o.excess:
            counts.setdefault(key(o), []).append(o.obs_date)
    episodes = {k: len(set(calendar_episodes(ds, HORIZONS[horizon]))) for k, ds in counts.items()}
    rates = _rate_map(design, horizon, key)
    hi: list[int] = []
    lo: list[int] = []
    if not episodes:
        return {"high_conf_acc": float("nan"), "low_conf_acc": float("nan"), "inverted": False}
    median_eps = float(np.median(list(episodes.values())))
    for o in holdout:
        if horizon not in o.excess:
            continue
        k = key(o)
        r = rates.get(k)
        if r is None or r == 0.5:
            continue
        ok = int((r > 0.5) == (o.excess[horizon] > 0))
        (hi if episodes.get(k, 0) >= median_eps else lo).append(ok)
    h = float(np.mean(hi)) if hi else float("nan")
    l = float(np.mean(lo)) if lo else float("nan")  # noqa: E741
    return {
        "high_conf_acc": h,
        "low_conf_acc": l,
        "n_high": len(hi),
        "n_low": len(lo),
        "median_design_episodes": median_eps,
        "inverted": bool(not math.isnan(h) and not math.isnan(l) and h < l),
    }


def per_symbol_delta(
    design: Sequence[Observation], holdout: Sequence[Observation], horizon: str, key_a, key_b
) -> dict:
    """Per-symbol (a - b) accuracy delta; guards against a few winners carrying
    an aggregate that conceals per-symbol degradation."""
    rates_a = _rate_map(design, horizon, key_a)
    rates_b = _rate_map(design, horizon, key_b)
    per: dict[str, list[tuple[int, int]]] = {}
    for o in holdout:
        if horizon not in o.excess:
            continue
        ra, rb = rates_a.get(key_a(o)), rates_b.get(key_b(o))
        if ra is None or rb is None or ra == 0.5 or rb == 0.5:
            continue
        actual = o.excess[horizon] > 0
        per.setdefault(o.symbol, []).append((int((ra > 0.5) == actual), int((rb > 0.5) == actual)))
    deltas = {
        s: float(np.mean([x[0] for x in v]) - np.mean([x[1] for x in v]))
        for s, v in per.items()
        if len(v) >= MIN_EPISODES
    }
    if not deltas:
        return {"n_symbols": 0, "median_delta": float("nan"), "share_positive": float("nan")}
    vals = list(deltas.values())
    return {
        "n_symbols": len(vals),
        "median_delta": float(np.median(vals)),
        "mean_delta": float(np.mean(vals)),
        "share_positive": float(np.mean([v > 0 for v in vals])),
        "worst": min(deltas.items(), key=lambda kv: kv[1]),
        "best": max(deltas.items(), key=lambda kv: kv[1]),
    }


def interpret(cell: CellStats, baseline: CellStats, threshold: float = 0.02) -> str:
    """Research-only label. Never a recommendation, never ADD/TRIM."""
    if cell.n_episodes < MIN_EPISODES or math.isnan(cell.median_excess):
        return "INCONCLUSIVE"
    delta = cell.median_excess - baseline.median_excess
    low, high = cell.wilson
    if high - low > 0.25:
        return "INCONCLUSIVE"
    if delta > threshold:
        return "CONTINUATION"
    if delta < -threshold:
        return "OVEREXTENSION"
    return "INCONCLUSIVE"
