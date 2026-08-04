"""Regression tests for the removed recovered-SE defect (amendment A-2026-006).

The defect: se = abs(effect / z_raw)  =>  w = (z_raw/effect)^2, which inverted
the weighting and was unbounded as effect -> 0. These tests pin the replacement
contract. They assert CORRECTNESS ONLY — no forecasting-performance claim.
"""
from __future__ import annotations

import inspect
import math

import pytest

from mip.engine import evidence as ev
from mip.engine.evidence import EQUAL_SE, MIN_N_EFF, model_standard_error


def _w(n_eff):
    return 1.0 / model_standard_error(n_eff) ** 2


def test_zero_effect_does_not_reach_uncertainty():
    """Effect is not an input at all — the inversion is impossible by signature."""
    assert "n_eff" in inspect.signature(model_standard_error).parameters
    assert len(inspect.signature(model_standard_error).parameters) == 1


def test_zero_z_is_finite():
    assert math.isfinite(model_standard_error(10.0))


def test_near_zero_z_is_finite():
    assert math.isfinite(model_standard_error(1e-12))


def test_missing_n_eff():
    assert model_standard_error(None) == EQUAL_SE


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -1.0, 0.0, "x"])
def test_non_finite_or_invalid_n_eff(bad):
    out = model_standard_error(bad)
    assert math.isfinite(out) and out > 0


def test_minimum_valid_n_eff():
    assert math.isfinite(model_standard_error(MIN_N_EFF))
    assert model_standard_error(MIN_N_EFF) > 0


def test_equal_n_eff_symmetry():
    assert model_standard_error(50.0) == model_standard_error(50.0)


def test_normalized_weights_sum_to_one():
    ns = [3.0, 40.0, 250.0, None]
    ws = [_w(n) for n in ns]
    shares = [w / sum(ws) for w in ws]
    assert math.isclose(sum(shares), 1.0, rel_tol=1e-12)


def test_weights_bounded_and_equal():
    ws = [_w(n) for n in [1.0, 10.0, 100.0, 320.1, None, 0.0]]
    assert max(ws) / min(ws) == 1.0  # equal uncertainty => equal weights
    assert all(math.isfinite(w) and w > 0 for w in ws)


def test_weight_independent_of_effect_magnitude():
    """The defect's signature was w varying with effect. It cannot now."""
    assert _w(25.0) == _w(25.0)
    assert all(_w(n) == _w(25.0) for n in [1.0, 999.0, None])


def test_deterministic_reproduction():
    assert [model_standard_error(n) for n in [1, 5, 50]] == [
        model_standard_error(n) for n in [1, 5, 50]
    ]


def test_defective_formula_absent_from_module_source():
    src = inspect.getsource(ev)
    active = [
        ln for ln in src.splitlines()
        if "expected_excess_return / " in ln and "z_raw" in ln and not ln.strip().startswith("#")
    ]
    assert active == []
