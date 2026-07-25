"""Reproducibility manifest for research runs.

Captures everything needed to regenerate an experiment's validation later: the
experiment identity, the code (git commit + dirty state), the data (dataset and
feature versions, universe hash), the plan (windows, schedule, horizons, seeds,
promotion thresholds), the environment, and the output artifact locations.

Two field tiers, enforced by ``validate``:
  - MANDATORY: must carry a real value (the run is not reproducible without it).
  - BEST_EFFORT: a real value OR an explicit ``Unavailable(reason)`` — never a
    silent ``None``. Local development legitimately lacks git or a database; the
    manifest records *that it is unavailable and why*, so a missing field is
    always visible, never assumed.

Serialization is deterministic (sorted keys) so a manifest hashes stably and
round-trips exactly.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from mip.core.exceptions import ConfigurationError

HARNESS_VERSION = "1.0"


@dataclass(frozen=True)
class Unavailable:
    """An explicitly-recorded missing value with a reason — never a silent None."""

    reason: str

    def to_dict(self) -> dict:
        return {"__unavailable__": self.reason}

    @staticmethod
    def is_unavailable(value: Any) -> bool:
        return isinstance(value, Unavailable)


def _encode(value: Any) -> Any:
    if isinstance(value, Unavailable):
        return value.to_dict()
    if isinstance(value, tuple):
        return [_encode(v) for v in value]
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items()}
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"__unavailable__"}:
        return Unavailable(value["__unavailable__"])
    if isinstance(value, dict):
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


MANDATORY = (
    "experiment_id",
    "experiment_version",
    "run_id",
    "created_at",
    "harness_version",
    "config_hash",
    "scoring_window",
    "holdout_window",
    "walk_forward_schedule",
    "supported_horizons",
    "random_seeds",
    "promotion_thresholds",
)
BEST_EFFORT = (
    "git_commit",
    "git_dirty",
    "dataset_versions",
    "feature_versions",
    "universe_hash",
    "runtime_environment",
)


@dataclass(frozen=True)
class ReproducibilityManifest:
    # identity (mandatory)
    experiment_id: str
    experiment_version: int
    run_id: str
    created_at: str  # ISO 8601; injectable for determinism
    harness_version: str
    # plan (mandatory)
    config_hash: str
    scoring_window: tuple[str, str]
    holdout_window: tuple[str, str]
    walk_forward_schedule: str
    supported_horizons: tuple[str, ...]
    random_seeds: dict[str, int]
    promotion_thresholds: tuple[dict, ...]
    # code + data + env (best-effort: value or Unavailable)
    git_commit: str | Unavailable
    git_dirty: bool | Unavailable
    dataset_versions: dict | Unavailable
    feature_versions: dict | Unavailable
    universe_hash: str | Unavailable
    runtime_environment: dict | Unavailable
    # context (optional, non-tiered)
    config_snapshot: dict = field(default_factory=dict)
    universe_definition: str = "universe.yaml"
    code_paths: tuple[str, ...] = ()
    artifact_locations: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        for name in MANDATORY:
            value = getattr(self, name)
            if value is None or Unavailable.is_unavailable(value):
                raise ConfigurationError(
                    f"manifest mandatory field {name!r} is missing or unavailable"
                )
        for name in BEST_EFFORT:
            value = getattr(self, name)
            if value is None:
                raise ConfigurationError(
                    f"manifest best-effort field {name!r} is a silent None; record a real "
                    f"value or Unavailable(reason)"
                )

    def to_dict(self) -> dict:
        # encode raw field values (NOT asdict, which would flatten the nested
        # Unavailable dataclass before _encode can tag it)
        return {f.name: _encode(getattr(self, f.name)) for f in fields(self)}

    def canonical_json(self) -> str:
        """Stable serialization: sorted keys, compact separators."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_dict(cls, payload: dict) -> ReproducibilityManifest:
        data = {k: _decode(v) for k, v in payload.items()}
        return cls(
            experiment_id=data["experiment_id"],
            experiment_version=data["experiment_version"],
            run_id=data["run_id"],
            created_at=data["created_at"],
            harness_version=data["harness_version"],
            config_hash=data["config_hash"],
            scoring_window=tuple(data["scoring_window"]),
            holdout_window=tuple(data["holdout_window"]),
            walk_forward_schedule=data["walk_forward_schedule"],
            supported_horizons=tuple(data["supported_horizons"]),
            random_seeds=data["random_seeds"],
            promotion_thresholds=tuple(data["promotion_thresholds"]),
            git_commit=data["git_commit"],
            git_dirty=data["git_dirty"],
            dataset_versions=data["dataset_versions"],
            feature_versions=data["feature_versions"],
            universe_hash=data["universe_hash"],
            runtime_environment=data["runtime_environment"],
            config_snapshot=data.get("config_snapshot", {}),
            universe_definition=data.get("universe_definition", "universe.yaml"),
            code_paths=tuple(data.get("code_paths", ())),
            artifact_locations=data.get("artifact_locations", {}),
        )

    def compatible_with(self, other: ReproducibilityManifest) -> tuple[bool, list[str]]:
        """Cache-reuse safety: two manifests may share captured baseline evidence
        only if the code, data, universe, and plan that produced it match. Any
        Unavailable on a compared field is treated as INCOMPATIBLE (we cannot
        prove equivalence), never silently accepted."""
        reasons: list[str] = []
        for name in ("git_commit", "feature_versions", "universe_hash", "dataset_versions"):
            a, b = getattr(self, name), getattr(other, name)
            if Unavailable.is_unavailable(a) or Unavailable.is_unavailable(b):
                reasons.append(f"{name}: unavailable on one side — cannot prove equivalence")
            elif a != b:
                reasons.append(f"{name}: differs")
        for name in ("scoring_window", "walk_forward_schedule", "supported_horizons"):
            if getattr(self, name) != getattr(other, name):
                reasons.append(f"{name}: differs")
        return (not reasons, reasons)


# -- capture helpers (each returns a value or Unavailable, never raises) ---------


def git_state(repo: Path | None = None) -> tuple[str | Unavailable, bool | Unavailable]:
    cwd = str(repo) if repo else None
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=cwd, check=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=cwd, check=True
        ).stdout
        return commit, bool(status.strip())
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        reason = f"git unavailable: {str(exc)[:80]}"
        return Unavailable(reason), Unavailable(reason)


def file_hash(path: Path) -> str | Unavailable:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        return Unavailable(f"cannot read {path}: {str(exc)[:80]}")


def runtime_environment() -> dict:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "implementation": platform.python_implementation(),
    }


def config_hash(snapshot: dict) -> str:
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
