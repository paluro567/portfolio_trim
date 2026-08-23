"""Calibration value objects.

Every field is an empirical statistic over a historical sample. None is a
forecast. The naming is deliberate — ``positive_return_rate`` is the realised
frequency in the sample, not "the probability of a gain" — and the renderer is
tested to present it that way.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

HORIZONS: tuple[str, ...] = ("1w", "1m", "3m", "6m", "1y")

# The deterministic security-view states this engine conditions on. Exactly the
# states `mip.product.decide.directional_view` can emit for a security.
SIGNAL_STATES: tuple[str, ...] = ("POSITIVE", "CONFLICTED", "NEGATIVE", "NEUTRAL")


class ValidationStatus(StrEnum):
    """How much weight a calibration reading may carry in the report."""

    VALIDATED = "VALIDATED"
    PROMISING_BUT_UNPROVEN = "PROMISING_BUT_UNPROVEN"
    INCONCLUSIVE = "INCONCLUSIVE"
    REJECTED = "REJECTED"
    UNAVAILABLE = "UNAVAILABLE"

    @property
    def presentable(self) -> bool:
        """Whether numbers may be shown at all.

        UNAVAILABLE and REJECTED carry no figures: showing frequencies for a
        rejected or absent calibration would give a discredited result the same
        visual authority as a supported one.
        """
        return self in (
            ValidationStatus.VALIDATED,
            ValidationStatus.PROMISING_BUT_UNPROVEN,
            ValidationStatus.INCONCLUSIVE,
        )

    @property
    def authoritative(self) -> bool:
        """Only a VALIDATED reading may be stated without a hedge."""
        return self is ValidationStatus.VALIDATED


@dataclass(frozen=True, slots=True)
class HorizonCalibration:
    """Empirical forward-outcome distribution for one (state, horizon) cell."""

    horizon: str
    signal_state: str
    validation_status: ValidationStatus
    unavailable_reason: str | None = None

    sample_n: int | None = None
    effective_n: int | None = None
    median_forward_return: float | None = None
    mean_forward_return: float | None = None
    positive_return_rate: float | None = None
    spy_outperformance_rate: float | None = None
    p25_forward_return: float | None = None
    p75_forward_return: float | None = None
    median_max_drawdown: float | None = None

    # Provenance of the underlying study; absent when unavailable.
    universe_version: str | None = None
    snapshot_checksum: str | None = None
    calibration_version: str | None = None
    generated_at: str | None = None

    @property
    def available(self) -> bool:
        return self.validation_status.presentable and self.sample_n is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "calibration_version": self.calibration_version,
            "effective_n": self.effective_n,
            "generated_at": self.generated_at,
            "horizon": self.horizon,
            "mean_forward_return": self.mean_forward_return,
            "median_forward_return": self.median_forward_return,
            "median_max_drawdown": self.median_max_drawdown,
            "p25_forward_return": self.p25_forward_return,
            "p75_forward_return": self.p75_forward_return,
            "positive_return_rate": self.positive_return_rate,
            "sample_n": self.sample_n,
            "signal_state": self.signal_state,
            "snapshot_checksum": self.snapshot_checksum,
            "spy_outperformance_rate": self.spy_outperformance_rate,
            "unavailable_reason": self.unavailable_reason,
            "universe_version": self.universe_version,
            "validation_status": self.validation_status.value,
        }

    def summary_line(self) -> str:
        """One compact cell for the report matrix.

        Returns an explicit unavailability statement rather than a blank when
        there is nothing defensible to show.
        """
        if not self.available:
            if self.validation_status is ValidationStatus.UNAVAILABLE:
                return "unavailable — validation data incomplete"
            if self.validation_status is ValidationStatus.REJECTED:
                return "REJECTED — not shown"
            return self.validation_status.value

        bits: list[str] = []
        if self.positive_return_rate is not None:
            bits.append(f"{self.positive_return_rate:.0%} positive")
        if self.spy_outperformance_rate is not None:
            bits.append(f"{self.spy_outperformance_rate:.0%} beat SPY")
        if self.median_forward_return is not None:
            bits.append(f"median {self.median_forward_return:+.1%}")
        if self.sample_n is not None:
            bits.append(f"N={self.sample_n:,}")
        bits.append(self.validation_status.value)
        return " · ".join(bits)


def unavailable(horizon: str, signal_state: str, reason: str) -> HorizonCalibration:
    """The honest empty result. Used wherever a statistic cannot be defended."""
    return HorizonCalibration(
        horizon=horizon,
        signal_state=signal_state,
        validation_status=ValidationStatus.UNAVAILABLE,
        unavailable_reason=reason,
    )
