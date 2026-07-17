"""Valuation Model: percentile-driven regime grammar, specificity selection,
verdict archetypes, insufficiency honesty, and architecture conformance —
all without a database.

Quantile stub convention: quantile(feature, p) == p, so a feature reading of
0.95 sits above its own p90 threshold (0.9), and so on."""

import ast
import inspect
from datetime import date

from mip.models.base import RegimeEvidence, select_active
from mip.models.valuation import (
    CORE_MULTIPLES,
    FAMILIES,
    HORIZONS,
    MIN_PERCENTILE_OBS,
    ValuationModel,
    regime_candidates,
    verdict,
)

AS_OF = date(2026, 7, 10)


def q_identity(feature: str, p: float) -> float:
    return p


def latest_from(values: dict[tuple[str, str | None], float]):
    return lambda feature, symbol: values.get((feature, symbol))


def labels(active) -> list[str]:
    return [r.label for r in active]


def make_evidence(label: str, excess: float) -> RegimeEvidence:
    return RegimeEvidence(
        label=label,
        description=label,
        feature="pe_trailing",
        n=20,
        n_eff=15.0,
        mean=0.01 + excess,
        hit_rate=0.6,
        baseline_mean=0.01,
        excess=excess,
        se=0.01,
        first_event=date(2020, 1, 1),
        last_event=date(2026, 1, 1),
    )


# -- regime grammar -----------------------------------------------------------


def test_regime_library_covers_spec() -> None:
    families = regime_candidates("AMD", q_identity)
    assert tuple(families) == FAMILIES
    all_labels = [r.label for candidates in families.values() for r in candidates]
    assert len(all_labels) == len(set(all_labels))
    assert set(HORIZONS.values()) == {5, 10, 21, 63, 126, 252}
    for family, candidates in families.items():
        assert candidates, family
        for regime in candidates:
            assert regime.family == family
            assert regime.description and regime.feature


def test_thresholds_come_from_the_stocks_own_percentiles() -> None:
    families = regime_candidates("AMD", lambda f, p: 100 * p)
    strong = families["abs_valuation"][1]  # 'trailing P/E ≥ p90'
    assert strong.filters[0].feature == "pe_trailing"
    assert strong.filters[0].op == ">=" and strong.filters[0].value == 90.0
    assert "90.00" in strong.description  # prose cites the actual value


def test_no_valuation_history_empties_the_whole_grammar() -> None:
    """Without snapshot depth there is NOTHING to activate — the honesty
    guarantee that real data cannot be scored until history accumulates."""
    families = regime_candidates("AMD", lambda feature, p: None)
    assert all(candidates == [] for candidates in families.values())


def test_partial_history_builds_only_supported_candidates() -> None:
    def only_ps(feature: str, p: float):
        return p if feature == "price_to_sales" else None

    families = regime_candidates("AMD", only_ps)
    assert labels(families["abs_valuation"]) == ["P/S ≥ p90", "P/S ≤ p10"]
    assert families["growth_adjusted"] == []  # anchored on P/E history
    assert families["rates_env"] == []


# -- specificity / no double-counting -------------------------------------------


def test_dual_expensive_beats_single_measure() -> None:
    values = {
        ("pe_trailing", None): 0.95,  # also satisfies ≥ p90
        ("price_to_sales", None): 0.85,
    }
    active = select_active(regime_candidates("AMD", q_identity), latest_from(values))
    family = [r for r in active if r.family == "abs_valuation"]
    assert labels(family) == ["expensive on P/E and P/S"]  # not stacked with p90


def test_one_active_regime_per_family_at_most() -> None:
    values = {
        ("pe_trailing", None): 0.95,
        ("pe_forward", None): 0.95,
        ("price_to_sales", None): 0.95,
        ("revenue_growth_yoy", None): 0.85,
        ("eps_growth_yoy", None): 0.85,
        ("pe_trailing_chg_63d", None): 0.9,
        ("pe_forward_chg_63d", None): 0.9,
        ("profit_margin", None): 0.9,
        ("ret_63d", None): 0.5,
        ("regime_rising_rates", None): 1.0,
        ("regime_falling_rates", None): 0.0,
    }
    active = select_active(regime_candidates("AMD", q_identity), latest_from(values))
    assert len({r.family for r in active}) == len(active)  # one per family
    assert len(active) == len(FAMILIES)
    assert labels(active) == [
        "expensive on P/E and P/S",
        "expensive, strong growth",
        "price up, fwd P/E expanding",
        "expensive, strong margins",
        "expensive, rising rates",
    ]


def test_growth_qualifiers_split_the_same_expensive_state() -> None:
    """High P/E is not bearish by fiat: strong-growth vs weak-growth select
    different regimes whose history decides direction."""
    base = {("pe_trailing", None): 0.85}
    strong = base | {("revenue_growth_yoy", None): 0.8}
    weak = base | {("revenue_growth_yoy", None): 0.1}
    grammar = regime_candidates("AMD", q_identity)

    assert "expensive, strong growth" in labels(select_active(grammar, latest_from(strong)))
    lit = labels(select_active(grammar, latest_from(weak)))
    assert "expensive, weak growth" in lit
    assert "expensive, strong growth" not in lit


def test_value_trap_vs_improving_fundamentals() -> None:
    grammar = regime_candidates("AMD", q_identity)
    improving = {("pe_trailing", None): 0.1, ("revenue_growth_yoy", None): 0.7}
    trap = {("pe_trailing", None): 0.1, ("revenue_growth_yoy", None): 0.1}

    assert "cheap, improving growth" in labels(select_active(grammar, latest_from(improving)))
    assert "cheap, weak growth" in labels(select_active(grammar, latest_from(trap)))


def test_valuation_change_detection() -> None:
    grammar = regime_candidates("AMD", q_identity)
    expanding = {("pe_trailing_chg_63d", None): 0.9}
    compressing = {("pe_trailing_chg_63d", None): 0.1}
    estimates_lag = {("ret_63d", None): 0.05, ("pe_forward_chg_63d", None): 0.9}
    normalizing = {("ret_63d", None): -0.05, ("pe_trailing_chg_63d", None): 0.1}

    assert "multiple expansion" in labels(select_active(grammar, latest_from(expanding)))
    assert "multiple compression" in labels(select_active(grammar, latest_from(compressing)))
    assert "price up, fwd P/E expanding" in labels(
        select_active(grammar, latest_from(estimates_lag))
    )
    lit = labels(select_active(grammar, latest_from(normalizing)))
    assert "price down, multiple normalizing" in lit
    assert "multiple compression" not in lit  # more specific wins


def test_rate_conditioned_valuation() -> None:
    grammar = regime_candidates("AMD", q_identity)
    rising = {("pe_trailing", None): 0.85, ("regime_rising_rates", None): 1.0}
    falling = {
        ("pe_trailing", None): 0.85,
        ("regime_rising_rates", None): 0.0,
        ("regime_falling_rates", None): 1.0,
    }
    assert "expensive, rising rates" in labels(select_active(grammar, latest_from(rising)))
    assert "expensive, falling rates" in labels(select_active(grammar, latest_from(falling)))


# -- verdict archetypes ----------------------------------------------------------


def test_verdicts_distinguish_the_four_archetypes() -> None:
    assert verdict(make_evidence("expensive, strong growth", +0.02)).startswith(
        "Expensive but historically justified by growth"
    )
    assert verdict(make_evidence("expensive, weak growth", -0.02)) == (
        "Expensive and historically vulnerable"
    )
    assert verdict(make_evidence("cheap, improving growth", +0.02)) == (
        "Cheap with improving fundamentals"
    )
    assert "value-trap" in verdict(make_evidence("cheap, weak growth", -0.02))
    assert verdict(make_evidence("trailing P/E ≥ p90", -0.02)) == (
        "Expensive and historically vulnerable"
    )


# -- neutral paths ------------------------------------------------------------


def make_model() -> ValuationModel:
    model = ValuationModel.__new__(ValuationModel)  # no DB on these paths
    model.half_life_years, model.min_events, model.prior_events = 10.0, 5, 30.0
    model.min_history = MIN_PERCENTILE_OBS
    return model


def test_insufficient_history_is_honestly_neutral() -> None:
    model = make_model()
    model._detect = lambda symbol, as_of: ([], AS_OF, {name: 3 for name in CORE_MULTIPLES})

    scores = model.evaluate("AMD")

    assert [s.horizon for s in scores] == list(HORIZONS)
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert s.expected_return is None and s.sample_size == 0
        assert "Insufficient historical valuation evidence" in s.explanation
        assert "never backfilled" in s.explanation


def test_no_active_regimes_yields_neutral_scores() -> None:
    model = make_model()
    spans = {name: MIN_PERCENTILE_OBS + 100 for name in CORE_MULTIPLES}
    model._detect = lambda symbol, as_of: ([], AS_OF, spans)

    scores = model.evaluate("AMD")

    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert "No valuation regime is currently active" in s.explanation


def test_no_data_at_as_of_yields_neutral_scores() -> None:
    model = make_model()
    spans = {name: MIN_PERCENTILE_OBS + 100 for name in CORE_MULTIPLES}
    model._detect = lambda symbol, as_of: ([], None, spans)

    scores = model.evaluate("AMD", as_of=AS_OF)

    for s in scores:
        assert s.as_of == AS_OF
        assert s.score == 50.0 and s.confidence == 0.0
        assert "insufficient data" in s.explanation.lower()


# -- architecture conformance ---------------------------------------------------


def test_model_imports_no_providers_or_raw_ingestion() -> None:
    import mip.models.valuation as module

    tree = ast.parse(inspect.getsource(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = ("mip.providers", "mip.ingestion", "yfinance", "fredapi", "requests", "urllib")
    for name in imported:
        assert not name.startswith(forbidden), f"forbidden import in valuation model: {name}"
