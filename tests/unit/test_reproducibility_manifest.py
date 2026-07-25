"""Stage 2 — reproducibility manifest: determinism, round-trip, tiering, cache
compatibility."""

import pytest

from mip.core.exceptions import ConfigurationError
from mip.research.experiments.manifest import (
    ReproducibilityManifest,
    Unavailable,
    config_hash,
    git_state,
)


def _manifest(**overrides) -> ReproducibilityManifest:
    base = dict(
        experiment_id="conditional_probability",
        experiment_version=1,
        run_id="run-001",
        created_at="2026-07-24T00:00:00",
        harness_version="1.0",
        config_hash="abc123",
        scoring_window=("2013-01-02", "2026-07-01"),
        holdout_window=("2022-01-01", "2026-07-01"),
        walk_forward_schedule="monthly-first-trading-day",
        supported_horizons=("1w", "2w", "1m", "3m", "6m", "1y"),
        random_seeds={"block_bootstrap": 7},
        promotion_thresholds=({"id": "incremental_1m", "threshold": 0.0},),
        git_commit="deadbeef",
        git_dirty=False,
        dataset_versions={"prices_max": "2026-07-01"},
        feature_versions={"ret_63d": 1},
        universe_hash="uni123",
        runtime_environment={"python": "3.13.0"},
    )
    base.update(overrides)
    return ReproducibilityManifest(**base)


def test_validate_passes_when_complete() -> None:
    _manifest().validate()


def test_canonical_json_is_deterministic() -> None:
    a = _manifest().canonical_json()
    b = _manifest().canonical_json()
    assert a == b
    assert _manifest().digest() == _manifest().digest()


def test_round_trip_preserves_everything() -> None:
    m = _manifest()
    restored = ReproducibilityManifest.from_dict(m.to_dict())
    assert restored == m
    assert restored.canonical_json() == m.canonical_json()


def test_unavailable_round_trips() -> None:
    m = _manifest(git_commit=Unavailable("no git"), git_dirty=Unavailable("no git"))
    restored = ReproducibilityManifest.from_dict(m.to_dict())
    assert restored == m
    assert isinstance(restored.git_commit, Unavailable)
    assert restored.git_commit.reason == "no git"


def test_mandatory_field_none_fails_validation() -> None:
    with pytest.raises(ConfigurationError, match="run_id"):
        _manifest(run_id=None).validate()


def test_mandatory_field_unavailable_fails_validation() -> None:
    with pytest.raises(ConfigurationError, match="config_hash"):
        _manifest(config_hash=Unavailable("x")).validate()


def test_best_effort_unavailable_is_allowed() -> None:
    _manifest(git_commit=Unavailable("local dev"), git_dirty=Unavailable("local dev")).validate()


def test_best_effort_silent_none_fails() -> None:
    with pytest.raises(ConfigurationError, match="silent None"):
        _manifest(feature_versions=None).validate()


def test_compatible_with_identical() -> None:
    ok, reasons = _manifest().compatible_with(_manifest())
    assert ok, reasons


def test_incompatible_on_feature_version_change() -> None:
    ok, reasons = _manifest().compatible_with(_manifest(feature_versions={"ret_63d": 2}))
    assert not ok
    assert any("feature_versions" in r for r in reasons)


def test_incompatible_when_unavailable() -> None:
    ok, reasons = _manifest().compatible_with(_manifest(git_commit=Unavailable("no git")))
    assert not ok
    assert any("cannot prove equivalence" in r for r in reasons)


def test_incompatible_on_window_change() -> None:
    ok, reasons = _manifest().compatible_with(
        _manifest(scoring_window=("2015-01-01", "2026-07-01"))
    )
    assert not ok


def test_git_state_never_raises() -> None:
    commit, dirty = git_state()
    assert isinstance(commit, str | Unavailable)
    assert isinstance(dirty, bool | Unavailable)


def test_config_hash_stable_and_order_independent() -> None:
    assert config_hash({"a": 1, "b": 2}) == config_hash({"b": 2, "a": 1})
    assert config_hash({"a": 1}) != config_hash({"a": 2})
