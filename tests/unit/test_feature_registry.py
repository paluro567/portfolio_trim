from datetime import date

import pandas as pd
import pytest

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import FeatureScope
from mip.features.base import FeatureCalculator, FeatureContext, FeatureSpec
from mip.features.registry import build_registry, topological_order


class Stub(FeatureCalculator):
    def __init__(self, name: str, depends_on: tuple[str, ...] = ()) -> None:
        super().__init__(
            FeatureSpec(
                name=name,
                version=1,
                scope=FeatureScope.MARKET,
                description="stub",
                depends_on=depends_on,
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        return pd.Series(dtype=float)


def test_registry_has_unique_names_and_expected_size() -> None:
    registry = build_registry()
    names = [c.spec.name for c in registry]

    assert len(names) == len(set(names))
    assert 30 <= len(names) <= 60  # Phase 5 band, widened for Phase 9 model features
    for calc in registry:
        assert calc.spec.description  # explanations need prose (D7)


def test_dependencies_resolve_within_registry() -> None:
    ordered = topological_order(build_registry())
    seen: set[str] = set()
    for calc in ordered:
        for dep in calc.spec.depends_on:
            assert dep in seen, f"{calc.spec.name} computed before its dependency {dep}"
        seen.add(calc.spec.name)


def test_dependents_come_after_dependencies() -> None:
    calcs = [Stub("c", depends_on=("b",)), Stub("b", depends_on=("a",)), Stub("a")]
    ordered = [c.spec.name for c in topological_order(calcs)]
    assert ordered == ["a", "b", "c"]


def test_unknown_dependency_fails_loudly() -> None:
    with pytest.raises(ConfigurationError, match="unknown feature 'ghost'"):
        topological_order([Stub("a", depends_on=("ghost",))])


def test_cycle_fails_loudly() -> None:
    with pytest.raises(ConfigurationError, match="cycle"):
        topological_order([Stub("a", depends_on=("b",)), Stub("b", depends_on=("a",))])


def test_duplicate_names_fail_loudly() -> None:
    with pytest.raises(ConfigurationError, match="duplicate"):
        topological_order([Stub("a"), Stub("a")])


def test_regime_features_consume_dependencies() -> None:
    from mip.features.regime import RegimeRates

    index = pd.DatetimeIndex(pd.to_datetime([date(2026, 6, 1), date(2026, 6, 2)]))
    ctx = FeatureContext(
        dates=index,
        features={"dgs10_chg_63d": pd.Series([0.30, -0.30], index=index)},
    )
    rising = RegimeRates("rising").compute(ctx)
    falling = RegimeRates("falling").compute(ctx)

    assert list(rising) == [1.0, 0.0]
    assert list(falling) == [0.0, 1.0]
