"""Historical calibration: what happened after states like today's.

This package answers ONE question, and only from deterministic point-in-time
data:

    For a current deterministic security-view state, what did forward returns
    actually look like historically?

It is a SEPARATE EVIDENCE CHANNEL from the OpenAI research layer and never
mixes with it. Three prohibitions are structural, not stylistic:

* **No LLM input, ever.** No field here may originate from a language model —
  not a label, not a summary, not a conviction. Enforced by an AST test
  (``tests/unit/test_calibration_boundary.py``) that forbids this package from
  importing ``mip.research_assistant``.
* **No survivor-only backtests.** The readiness gate refuses to calibrate on a
  universe with no delisted securities, because a forward-return study over
  today's survivors measures selection, not signal.
* **No forecast language.** Outputs are empirical frequencies over a historical
  sample, carrying a validation status. They are never probabilities.

If the data cannot support calibration, the honest output is
``ValidationStatus.UNAVAILABLE`` with the reason — never a fabricated statistic.
"""

from mip.calibration.contracts import (
    HorizonCalibration,
    ValidationStatus,
)
from mip.calibration.readiness import ReadinessReport, assess_readiness

__all__ = [
    "HorizonCalibration",
    "ValidationStatus",
    "ReadinessReport",
    "assess_readiness",
]

# Bumped when the calibration methodology or artifact format changes.
CALIBRATION_VERSION = "0.1.0"
