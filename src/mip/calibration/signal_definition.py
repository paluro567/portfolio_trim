"""Phase B — the frozen deterministic horizon definition.

Calibration conditions on a signal. If the signal's definition changes, every
prior calibration silently becomes a statistic about a different thing. So the
definition is captured here and hashed, and each calibration artifact records
the hash it was computed against.

The signature is DERIVED from the live product constants rather than
transcribed, so it cannot drift: change a threshold in ``mip.product`` and the
signature changes with it, invalidating stale artifacts by construction.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from mip.product.decide import ADD_DISCOURAGE_MULTIPLE, NON_DIRECTIONAL_GROUPS, SECURITY_DOMAINS
from mip.product.slice import (
    DELIVERY_BOTTOM,
    DELIVERY_HORIZONS,
    DELIVERY_TOP,
    OWN_HISTORY_BOTTOM,
    OWN_HISTORY_TOP,
    QUALITY_VOTING_HORIZONS,
    VALUATION_HORIZONS,
)


@dataclass(frozen=True, slots=True)
class SignalDefinition:
    """The exact rules producing the deterministic security view."""

    body: dict[str, Any]

    @property
    def signature(self) -> str:
        canonical = json.dumps(self.body, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {"definition": self.body, "signature": self.signature}


def current_signal_definition() -> SignalDefinition:
    """Snapshot the live definition of the deterministic security view."""
    return SignalDefinition(
        body={
            "aggregation": (
                "Evidence is grouped by phenomenon; each group casts one vote equal to the "
                "majority direction of its members. The security view is POSITIVE when every "
                "signed group agrees positive, NEGATIVE when every signed group agrees "
                "negative, CONFLICTED when both signs are present, NEUTRAL when no group "
                "signs, UNAVAILABLE when no evidence exists."
            ),
            "add_discourage_multiple": str(ADD_DISCOURAGE_MULTIPLE),
            "delivery_horizons": list(DELIVERY_HORIZONS),
            "delivery_peer_bottom": DELIVERY_BOTTOM,
            "delivery_peer_top": DELIVERY_TOP,
            "non_directional_groups": sorted(NON_DIRECTIONAL_GROUPS),
            "own_history_bottom": OWN_HISTORY_BOTTOM,
            "own_history_top": OWN_HISTORY_TOP,
            "quality_voting_horizons": list(QUALITY_VOTING_HORIZONS),
            "security_domains": sorted(SECURITY_DOMAINS),
            "valuation_horizons": list(VALUATION_HORIZONS),
        }
    )
