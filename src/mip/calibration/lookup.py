"""Phase D — the calibration lookup interface.

The report asks this module "what happened historically after states like
today's?" and gets back a ``HorizonCalibration`` for every horizon, always.
When no defensible artifact exists the answer is UNAVAILABLE carrying the
reason — never a blank, and never an invented number.

The lookup is deliberately dumb. It reads frozen artifacts produced by a
calibration study; it does not compute statistics itself. That separation is
what stops a report run from quietly becoming a backtest.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mip.calibration.contracts import (
    HORIZONS,
    HorizonCalibration,
    ValidationStatus,
    unavailable,
)

DEFAULT_STORE = Path("data/calibration")

_NO_ARTIFACT = "no calibration study has been run: the historical data-quality gate has not passed"


@dataclass(frozen=True, slots=True)
class CalibrationLookup:
    """Reads frozen calibration artifacts. Computes nothing."""

    cells: dict[str, dict[str, Any]]
    signal_signature: str | None = None
    unavailable_reason: str | None = None

    @classmethod
    def unavailable_because(cls, reason: str) -> CalibrationLookup:
        return cls(cells={}, unavailable_reason=reason)

    @classmethod
    def load(
        cls,
        signal_signature: str,
        *,
        root: Path = DEFAULT_STORE,
        gate_reason: str | None = None,
    ) -> CalibrationLookup:
        """Load artifacts for a signal signature, if any exist and match.

        A signature mismatch is treated as absence, not as an approximation: a
        calibration computed against different thresholds describes a different
        signal.
        """
        if gate_reason:
            return cls.unavailable_because(gate_reason)

        path = root / signal_signature / "calibration.json"
        if not path.is_file():
            return cls.unavailable_because(_NO_ARTIFACT)
        try:
            body = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            return cls.unavailable_because(f"calibration artifact unreadable: {exc}")

        if body.get("signal_signature") != signal_signature:
            return cls.unavailable_because(
                "calibration artifact was computed against a different signal definition"
            )
        return cls(
            cells=body.get("cells", {}),
            signal_signature=signal_signature,
        )

    @property
    def available(self) -> bool:
        return bool(self.cells) and self.unavailable_reason is None

    def lookup(self, signal_state: str, horizon: str) -> HorizonCalibration:
        """The calibration for one (state, horizon). Never raises, never invents."""
        if not self.available:
            return unavailable(horizon, signal_state, self.unavailable_reason or _NO_ARTIFACT)

        cell = self.cells.get(f"{signal_state}|{horizon}")
        if not cell:
            return unavailable(
                horizon,
                signal_state,
                f"no calibrated cell for state {signal_state} at {horizon}",
            )
        try:
            status = ValidationStatus(cell["validation_status"])
        except (KeyError, ValueError):
            return unavailable(horizon, signal_state, "calibration cell has no validation status")

        if not status.presentable:
            return HorizonCalibration(
                horizon=horizon,
                signal_state=signal_state,
                validation_status=status,
                unavailable_reason=cell.get("unavailable_reason"),
            )

        return HorizonCalibration(
            horizon=horizon,
            signal_state=signal_state,
            validation_status=status,
            sample_n=cell.get("sample_n"),
            effective_n=cell.get("effective_n"),
            median_forward_return=cell.get("median_forward_return"),
            mean_forward_return=cell.get("mean_forward_return"),
            positive_return_rate=cell.get("positive_return_rate"),
            spy_outperformance_rate=cell.get("spy_outperformance_rate"),
            p25_forward_return=cell.get("p25_forward_return"),
            p75_forward_return=cell.get("p75_forward_return"),
            median_max_drawdown=cell.get("median_max_drawdown"),
            universe_version=cell.get("universe_version"),
            snapshot_checksum=cell.get("snapshot_checksum"),
            calibration_version=cell.get("calibration_version"),
            generated_at=cell.get("generated_at"),
        )

    def for_all_horizons(self, states_by_horizon: dict[str, str]) -> dict[str, HorizonCalibration]:
        """One calibration per horizon, given the deterministic state at each."""
        return {hz: self.lookup(states_by_horizon.get(hz, "UNAVAILABLE"), hz) for hz in HORIZONS}
