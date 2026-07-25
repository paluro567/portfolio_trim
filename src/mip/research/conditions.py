"""Versioned condition registry for the Conditional Probability Engine.

A *condition* is an explicit, explainable, versioned object — never an
anonymous lambda. A *template* is a predeclared generator that, given the
TARGET holding's current point-in-time state, resolves to a concrete
``Condition`` describing the notable bucket/side the target sits in today (or
to ``None`` when the feature is unavailable or the target is in an
uninformative middle state). The resolved condition is then applied across the
cross-sectional pool: each candidate ``(symbol, date)`` is judged against the
SAME qualitative template using that candidate's OWN data (own-history
percentile thresholds for ``own_percentile`` conditions, its own sector ETF for
``sector_etf`` conditions, the shared market series for ``market`` conditions).

This mirrors the momentum model's discipline (thresholds are a symbol's own
empirical percentiles at/before as_of, never technical-analysis constants) and
the feature registry's philosophy (one declared list, versioned, no ad-hoc
conditions scattered through model logic). The template set is frozen by
``TEMPLATE_SET_VERSION`` before any validation run.

Point-in-time: resolution reads only the target's values at/before as_of, and
own-percentile thresholds are computed from history to date. Per-candidate
threshold resolution (in the engine) uses each candidate's own history ≤ as_of.
No future information enters here or downstream.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

TEMPLATE_SET_VERSION = "cpe-v1"

# Families, in the fixed order used for the hierarchical fallback ladder.
FAMILIES = ("market", "sector", "company", "valuation", "catalyst")

# The fallback ladder: each rung is the set of families required at that level.
# Deterministic, versioned, disclosed in output; the engine descends only when
# a rung fails its sample-support thresholds, never by realized performance.
FALLBACK_LADDER: tuple[tuple[str, frozenset[str]], ...] = (
    ("market+sector+company+catalyst", frozenset({"market", "sector", "company", "catalyst"})),
    ("market+sector+company", frozenset({"market", "sector", "company"})),
    ("market+company+catalyst", frozenset({"market", "company", "catalyst"})),
    ("market+company", frozenset({"market", "company"})),
    ("market+sector", frozenset({"market", "sector"})),
    ("market", frozenset({"market"})),
)


class EvaluateOn(StrEnum):
    """Which series a condition is read from for each candidate symbol."""

    MARKET = "market"  # the shared market-scope feature series
    SELF = "self"  # the candidate instrument's own feature series
    SECTOR_ETF = "sector_etf"  # the candidate's sector-ETF feature series


class ThresholdKind(StrEnum):
    CONSTANT = "constant"  # a universe-shared fixed threshold value
    OWN_PERCENTILE = "own_percentile"  # per-symbol: the symbol's own p-quantile at as_of
    STRUCTURAL_ZERO = "structural_zero"  # compared against a natural zero boundary


class Mode(StrEnum):
    """How a template resolves the target's current state into a condition."""

    MARKET_FLAG = "market_flag"  # 0/1 regime flag -> match today's side
    MARKET_BUCKET = "market_bucket"  # a market percentile feature -> extreme bucket only
    MARKET_DIRECTION = "market_direction"  # a market change feature -> rising/falling only
    SELF_BUCKET = "self_bucket"  # own-history percentile extreme (top/bottom)
    SELF_STRUCTURAL = "self_structural"  # sign vs a natural zero (e.g. above/below MA)
    SECTOR_STRUCTURAL = "sector_structural"  # sign vs zero on the sector ETF or self-vs-sector
    CATALYST_WINDOW = "catalyst_window"  # within N sessions of a catalyst (only when near)


@dataclass(frozen=True)
class Condition:
    """A resolved, explainable historical condition. ``value`` is set for
    ``constant``/``structural_zero`` kinds; ``percentile`` is set for
    ``own_percentile`` (the engine resolves the concrete per-symbol threshold
    at match time). ``evaluate_on`` selects which candidate series is read."""

    name: str
    version: int
    family: str
    feature: str
    evaluate_on: str  # EvaluateOn value
    op: str  # OPERATORS key
    threshold_kind: str  # ThresholdKind value
    value: float | None  # resolved constant / structural threshold
    percentile: float | None  # own-percentile quantile (per-symbol threshold)
    min_history: int | None
    description: str  # prose incl. the resolved target state
    economic_rationale: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "family": self.family,
            "feature": self.feature,
            "evaluate_on": self.evaluate_on,
            "op": self.op,
            "threshold_kind": self.threshold_kind,
            "value": self.value,
            "percentile": self.percentile,
            "description": self.description,
        }


@dataclass(frozen=True)
class ResolutionContext:
    """The target holding's point-in-time state, supplied to templates. The
    two callables read the TARGET's values at/before as_of: ``value(feature,
    evaluate_on)`` returns the latest stored value (or None), and
    ``quantile(feature, evaluate_on, p)`` returns the target's own p-quantile
    over its history to date (or None when history is insufficient). Market
    features ignore ``evaluate_on`` beyond MARKET."""

    target: str
    as_of: date
    sector_etf: str | None
    value: Callable[[str, EvaluateOn], float | None]
    quantile: Callable[[str, EvaluateOn, float], float | None]


@dataclass(frozen=True)
class ConditionTemplate:
    """A predeclared, versioned condition generator. Declarative — the
    resolution is driven by ``mode`` and the parameters below, never a
    free-form lambda, so every template is inspectable and stable."""

    name: str
    version: int
    family: str
    mode: Mode
    feature: str
    economic_rationale: str
    evaluate_on: EvaluateOn = EvaluateOn.SELF
    high_pct: float = 0.8  # bucket / market-bucket upper cut
    low_pct: float = 0.2  # bucket lower cut
    min_history: int = 252
    direction_band: float = 0.0  # |change| must exceed this to count as a direction
    catalyst_max: float = 10.0  # sessions/days window for catalyst templates

    def resolve(self, ctx: ResolutionContext) -> Condition | None:
        """Resolve the target's current state into a concrete condition, or
        None when unavailable / uninformative. Deterministic and PIT."""
        return _RESOLVERS[self.mode](self, ctx)

    # -- helpers for resolvers ------------------------------------------------

    def _condition(
        self,
        op: str,
        kind: ThresholdKind,
        value: float | None,
        percentile: float | None,
        state: str,
    ) -> Condition:
        return Condition(
            name=self.name,
            version=self.version,
            family=self.family,
            feature=self.feature,
            evaluate_on=self.evaluate_on.value,
            op=op,
            threshold_kind=kind.value,
            value=value,
            percentile=percentile,
            min_history=(self.min_history if kind is ThresholdKind.OWN_PERCENTILE else None),
            description=f"{self.feature} {state}",
            economic_rationale=self.economic_rationale,
        )


# -- resolvers (one per Mode; declarative dispatch) ----------------------------


def _resolve_market_flag(t: ConditionTemplate, ctx: ResolutionContext) -> Condition | None:
    current = ctx.value(t.feature, EvaluateOn.MARKET)
    if current is None:
        return None
    side = 1.0 if current >= 0.5 else 0.0
    label = "on" if side == 1.0 else "off"
    return t._condition("==", ThresholdKind.CONSTANT, side, None, f"regime {label} (== {side:g})")


def _resolve_market_bucket(t: ConditionTemplate, ctx: ResolutionContext) -> Condition | None:
    current = ctx.value(t.feature, EvaluateOn.MARKET)
    if current is None:
        return None
    if current >= t.high_pct:
        return t._condition(
            ">=", ThresholdKind.CONSTANT, t.high_pct, None, f"in upper bucket (>= {t.high_pct:g})"
        )
    if current <= t.low_pct:
        return t._condition(
            "<=", ThresholdKind.CONSTANT, t.low_pct, None, f"in lower bucket (<= {t.low_pct:g})"
        )
    return None  # mid-range: uninformative, no condition


def _resolve_market_direction(t: ConditionTemplate, ctx: ResolutionContext) -> Condition | None:
    current = ctx.value(t.feature, EvaluateOn.MARKET)
    if current is None:
        return None
    if current > t.direction_band:
        return t._condition(">", ThresholdKind.STRUCTURAL_ZERO, 0.0, None, "rising (> 0)")
    if current < -t.direction_band:
        return t._condition("<", ThresholdKind.STRUCTURAL_ZERO, 0.0, None, "falling (< 0)")
    return None


def _resolve_self_bucket(t: ConditionTemplate, ctx: ResolutionContext) -> Condition | None:
    current = ctx.value(t.feature, t.evaluate_on)
    if current is None:
        return None
    high = ctx.quantile(t.feature, t.evaluate_on, t.high_pct)
    low = ctx.quantile(t.feature, t.evaluate_on, t.low_pct)
    if high is None or low is None:  # insufficient own history -> honestly suppressed
        return None
    if current >= high:
        return t._condition(
            ">=",
            ThresholdKind.OWN_PERCENTILE,
            None,
            t.high_pct,
            f"in own top decile-band (p{int(t.high_pct * 100)})",
        )
    if current <= low:
        return t._condition(
            "<=",
            ThresholdKind.OWN_PERCENTILE,
            None,
            t.low_pct,
            f"in own bottom band (p{int(t.low_pct * 100)})",
        )
    return None


def _resolve_self_structural(t: ConditionTemplate, ctx: ResolutionContext) -> Condition | None:
    current = ctx.value(t.feature, t.evaluate_on)
    if current is None:
        return None
    if current >= 0.0:
        return t._condition(
            ">=", ThresholdKind.STRUCTURAL_ZERO, 0.0, None, "at/above zero boundary"
        )
    return t._condition("<", ThresholdKind.STRUCTURAL_ZERO, 0.0, None, "below zero boundary")


def _resolve_sector_structural(t: ConditionTemplate, ctx: ResolutionContext) -> Condition | None:
    if t.evaluate_on is EvaluateOn.SECTOR_ETF and ctx.sector_etf is None:
        return None
    return _resolve_self_structural(t, ctx)


def _resolve_catalyst_window(t: ConditionTemplate, ctx: ResolutionContext) -> Condition | None:
    current = ctx.value(t.feature, EvaluateOn.SELF)
    if current is None or current > t.catalyst_max:
        return None  # only condition on a catalyst when the target is actually near one
    return t._condition(
        "<=", ThresholdKind.CONSTANT, t.catalyst_max, None, f"within {t.catalyst_max:g} sessions"
    )


_RESOLVERS: dict[Mode, Callable[[ConditionTemplate, ResolutionContext], Condition | None]] = {
    Mode.MARKET_FLAG: _resolve_market_flag,
    Mode.MARKET_BUCKET: _resolve_market_bucket,
    Mode.MARKET_DIRECTION: _resolve_market_direction,
    Mode.SELF_BUCKET: _resolve_self_bucket,
    Mode.SELF_STRUCTURAL: _resolve_self_structural,
    Mode.SECTOR_STRUCTURAL: _resolve_sector_structural,
    Mode.CATALYST_WINDOW: _resolve_catalyst_window,
}


# -- the declared template set (frozen by TEMPLATE_SET_VERSION) -----------------


def build_condition_templates() -> tuple[ConditionTemplate, ...]:
    """The single declared list of condition templates. Adding a condition =
    add one entry here and bump TEMPLATE_SET_VERSION; never scatter conditions
    through model logic."""
    return (
        # -- market -----------------------------------------------------------
        ConditionTemplate(
            "market_trend",
            1,
            "market",
            Mode.MARKET_FLAG,
            "regime_bull",
            "broad market trend (SPY vs its 200-day average) conditions forward returns",
            evaluate_on=EvaluateOn.MARKET,
        ),
        ConditionTemplate(
            "market_volatility",
            1,
            "market",
            Mode.MARKET_BUCKET,
            "vix_pctile_252d",
            "volatility regime (VIX percentile) shapes the forward return distribution",
            evaluate_on=EvaluateOn.MARKET,
        ),
        ConditionTemplate(
            "rates_direction",
            1,
            "market",
            Mode.MARKET_DIRECTION,
            "dgs10_chg_63d",
            "the direction of 10y Treasury yields over a quarter is a macro tailwind/headwind",
            evaluate_on=EvaluateOn.MARKET,
            direction_band=0.25,
        ),
        ConditionTemplate(
            "inflation_direction",
            1,
            "market",
            Mode.MARKET_DIRECTION,
            "cpi_yoy_accel",
            "accelerating vs decelerating inflation is a distinct macro regime",
            evaluate_on=EvaluateOn.MARKET,
        ),
        # -- sector -----------------------------------------------------------
        ConditionTemplate(
            "sector_trend",
            1,
            "sector",
            Mode.SECTOR_STRUCTURAL,
            "price_to_ma50",
            "whether the holding's sector ETF is above/below its 50-day average",
            evaluate_on=EvaluateOn.SECTOR_ETF,
        ),
        ConditionTemplate(
            "sector_relative_strength",
            1,
            "sector",
            Mode.SECTOR_STRUCTURAL,
            "rel_ret_sector_63d",
            "whether the holding is leading or lagging its own sector over a quarter",
            evaluate_on=EvaluateOn.SELF,
        ),
        # -- company ----------------------------------------------------------
        ConditionTemplate(
            "own_momentum",
            1,
            "company",
            Mode.SELF_BUCKET,
            "ret_63d",
            "the stock's own quarterly-return extreme (top/bottom of its history)",
            evaluate_on=EvaluateOn.SELF,
        ),
        ConditionTemplate(
            "own_trend",
            1,
            "company",
            Mode.SELF_STRUCTURAL,
            "price_to_ma200",
            "whether the stock is above/below its own 200-day average (primary trend)",
            evaluate_on=EvaluateOn.SELF,
        ),
        ConditionTemplate(
            "own_extension",
            1,
            "company",
            Mode.SELF_BUCKET,
            "dist_52w_high",
            "proximity to the 52-week high vs deep-drawdown extreme (exhaustion state)",
            evaluate_on=EvaluateOn.SELF,
        ),
        # -- valuation (honestly suppressed until own history is adequate) ----
        ConditionTemplate(
            "valuation_pe",
            1,
            "valuation",
            Mode.SELF_BUCKET,
            "pe_forward",
            "forward P/E extreme within the stock's own history (valuation regime)",
            evaluate_on=EvaluateOn.SELF,
            min_history=252,
        ),
        ConditionTemplate(
            "valuation_ps",
            1,
            "valuation",
            Mode.SELF_BUCKET,
            "price_to_sales",
            "price/sales extreme within the stock's own history (valuation regime)",
            evaluate_on=EvaluateOn.SELF,
            min_history=252,
        ),
        # -- catalyst ---------------------------------------------------------
        ConditionTemplate(
            "pre_earnings",
            1,
            "catalyst",
            Mode.CATALYST_WINDOW,
            "days_until_earnings",
            "an upcoming earnings report within ~2 trading weeks is a known catalyst window",
            evaluate_on=EvaluateOn.SELF,
            catalyst_max=10.0,
        ),
        ConditionTemplate(
            "post_earnings",
            1,
            "catalyst",
            Mode.CATALYST_WINDOW,
            "days_since_earnings",
            "the post-earnings drift window (within ~2 trading weeks after a report)",
            evaluate_on=EvaluateOn.SELF,
            catalyst_max=10.0,
        ),
    )


def resolve_active(
    templates: tuple[ConditionTemplate, ...], ctx: ResolutionContext
) -> dict[str, list[Condition]]:
    """All conditions that resolve active today, grouped by family (families
    with no active condition are absent). Deterministic order = template order.
    Unavailable/mid-range templates are simply absent (never zero-filled)."""
    active: dict[str, list[Condition]] = {}
    for template in templates:
        condition = template.resolve(ctx)
        if condition is not None:
            active.setdefault(condition.family, []).append(condition)
    return active


# -- per-candidate threshold resolution (the matcher-facing evaluator registry) --
#
# Reservation 1: the matcher must never switch on threshold semantics. It calls
# resolve_threshold() once per (condition, candidate); dispatch is a registry
# keyed by ThresholdKind. A future kind (cross-sectional percentile, z-band,
# external regime) is a new entry here, not an edit to the matcher.

# (condition, candidate_symbol) -> that symbol's own p-quantile threshold, or
# None when its history is insufficient. Supplied by the matcher (port-backed);
# only own_percentile conditions consult it.
OwnQuantileFn = Callable[[Condition, str], float | None]


def _threshold_constant(condition: Condition, symbol: str, own_quantile: OwnQuantileFn) -> float:
    return condition.value  # type: ignore[return-value]  # non-None for these kinds


def _threshold_own_percentile(
    condition: Condition, symbol: str, own_quantile: OwnQuantileFn
) -> float | None:
    return own_quantile(condition, symbol)


_THRESHOLD_RESOLVERS: dict[
    ThresholdKind, Callable[[Condition, str, OwnQuantileFn], float | None]
] = {
    ThresholdKind.CONSTANT: _threshold_constant,
    ThresholdKind.STRUCTURAL_ZERO: _threshold_constant,
    ThresholdKind.OWN_PERCENTILE: _threshold_own_percentile,
}


def resolve_threshold(
    condition: Condition, symbol: str, own_quantile: OwnQuantileFn
) -> float | None:
    """The concrete numeric threshold to compare a candidate's feature value
    against for this condition. None => the condition is not evaluable for this
    candidate (insufficient own history) and the candidate is excluded for it —
    never zero-filled. Dispatched by ThresholdKind via the registry above."""
    return _THRESHOLD_RESOLVERS[ThresholdKind(condition.threshold_kind)](
        condition, symbol, own_quantile
    )
