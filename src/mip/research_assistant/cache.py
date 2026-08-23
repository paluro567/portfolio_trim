"""Artifact store, cache key and freshness.

Research is expensive, so it is re-run only when something that could change the
answer has changed. The cache key covers the deterministic payload hash, the
model, the prompt version and the schema version — so editing a prompt or
altering a feature invalidates cached research automatically rather than
silently serving stale conclusions.

Freshness is a separate axis: even an unchanged key goes stale with wall-clock
time, because the world moves whether or not the numbers did.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any


def cache_key(
    *,
    symbol: str,
    as_of: date,
    payload_hash: str,
    model: str,
    prompt_version: str,
    schema_version: str,
) -> str:
    material = "|".join(
        [symbol.upper(), as_of.isoformat(), payload_hash, model, prompt_version, schema_version]
    )
    return hashlib.sha256(material.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ArtifactStore:
    root: Path

    def symbol_dir(self, symbol: str) -> Path:
        return self.root / symbol.upper()

    def research_path(self, symbol: str, as_of: date) -> Path:
        return self.symbol_dir(symbol) / as_of.isoformat() / "research.json"

    def thesis_path(self, symbol: str) -> Path:
        return self.symbol_dir(symbol) / "thesis.json"

    def portfolio_path(self, as_of: date) -> Path:
        return self.root / "_portfolio" / as_of.isoformat() / "portfolio_research.json"

    # ------------------------------------------------------------------ read
    def load_research(self, symbol: str, as_of: date) -> dict[str, Any] | None:
        return _read_json(self.research_path(symbol, as_of))

    def load_thesis(self, symbol: str) -> dict[str, Any] | None:
        return _read_json(self.thesis_path(symbol))

    def latest_prior_research(
        self, symbol: str, before: date
    ) -> tuple[date, dict[str, Any]] | None:
        """The most recent research artifact strictly before ``before``."""
        base = self.symbol_dir(symbol)
        if not base.is_dir():
            return None
        candidates: list[tuple[date, Path]] = []
        for child in base.iterdir():
            if not child.is_dir():
                continue
            try:
                stamp = date.fromisoformat(child.name)
            except ValueError:
                continue
            if stamp >= before:
                continue
            path = child / "research.json"
            if path.is_file():
                candidates.append((stamp, path))
        if not candidates:
            return None
        stamp, path = max(candidates, key=lambda pair: pair[0])
        body = _read_json(path)
        return None if body is None else (stamp, body)

    # ----------------------------------------------------------------- write
    def write_research(self, symbol: str, as_of: date, body: dict[str, Any]) -> Path:
        return _write_json(self.research_path(symbol, as_of), body)

    def write_thesis(self, symbol: str, body: dict[str, Any]) -> Path:
        return _write_json(self.thesis_path(symbol), body)

    def write_portfolio(self, as_of: date, body: dict[str, Any]) -> Path:
        return _write_json(self.portfolio_path(as_of), body)


def is_fresh(artifact: dict[str, Any], *, key: str, freshness_hours: int, now: datetime) -> bool:
    """Reusable when the key matches AND the artifact is inside the window."""
    if artifact.get("cache_key") != key:
        return False
    if artifact.get("status") != "OK":
        return False
    raw = artifact.get("generated_at")
    if not isinstance(raw, str):
        return False
    try:
        generated = datetime.fromisoformat(raw)
    except ValueError:
        return False
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=UTC)
    age_hours = (now - generated).total_seconds() / 3600.0
    return 0 <= age_hours <= freshness_hours


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _write_json(path: Path, body: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(body, indent=2, sort_keys=True, default=str)
    # Write-then-replace so a crash cannot leave a half-written artifact behind.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)
    return path


def artifact_hash(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
