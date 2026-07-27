"""Point-in-time repository for the security master & universe membership.

Every lookup where identity or classification can change through time REQUIRES
an as-of date. There is deliberately no "current ticker" accessor for historical
research: a ticker resolves to a security only *as of* a date, because tickers
change and are reused.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from mip.domain.enums import IdentifierType
from mip.domain.models import (
    DelistingEvent,
    HistoricalClassification,
    SecurityIdentifierHistory,
    SecurityLifecycleEvent,
    SecurityMaster,
    UniverseMembership,
)


def _as_of(col_from, col_to, as_of: date):
    """valid_from <= as_of < valid_to (NULL valid_to = still current)."""
    return and_(col_from <= as_of, or_(col_to.is_(None), col_to > as_of))


class SecurityRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    # -- identity ----------------------------------------------------------

    def get(self, security_id: int) -> SecurityMaster | None:
        return self._s.get(SecurityMaster, security_id)

    def resolve_identifier(
        self, identifier_type: IdentifierType, value: str, as_of: date
    ) -> int | None:
        """The security that held this identifier ON `as_of`. Ticker reuse is
        resolved by the as-of interval; None if nothing held it then."""
        return self._s.scalar(
            select(SecurityIdentifierHistory.security_id).where(
                SecurityIdentifierHistory.identifier_type == identifier_type,
                SecurityIdentifierHistory.identifier_value == value,
                _as_of(
                    SecurityIdentifierHistory.valid_from,
                    SecurityIdentifierHistory.valid_to,
                    as_of,
                ),
            )
        )

    def resolve_ticker(self, ticker: str, as_of: date) -> int | None:
        return self.resolve_identifier(IdentifierType.TICKER, ticker, as_of)

    def identifiers_as_of(self, security_id: int, as_of: date) -> list[SecurityIdentifierHistory]:
        return list(
            self._s.scalars(
                select(SecurityIdentifierHistory)
                .where(
                    SecurityIdentifierHistory.security_id == security_id,
                    _as_of(
                        SecurityIdentifierHistory.valid_from,
                        SecurityIdentifierHistory.valid_to,
                        as_of,
                    ),
                )
                .order_by(SecurityIdentifierHistory.identifier_type)
            )
        )

    def ticker_as_of(self, security_id: int, as_of: date) -> str | None:
        row = self._s.scalar(
            select(SecurityIdentifierHistory.identifier_value).where(
                SecurityIdentifierHistory.security_id == security_id,
                SecurityIdentifierHistory.identifier_type == IdentifierType.TICKER,
                _as_of(
                    SecurityIdentifierHistory.valid_from,
                    SecurityIdentifierHistory.valid_to,
                    as_of,
                ),
            )
        )
        return row

    # -- lifecycle & classification ---------------------------------------

    def lifecycle_as_of(self, security_id: int, as_of: date) -> list[SecurityLifecycleEvent]:
        return list(
            self._s.scalars(
                select(SecurityLifecycleEvent)
                .where(
                    SecurityLifecycleEvent.security_id == security_id,
                    SecurityLifecycleEvent.effective_date <= as_of,
                )
                .order_by(SecurityLifecycleEvent.effective_date)
            )
        )

    def classification_as_of(
        self, security_id: int, as_of: date, scheme: str = "GICS"
    ) -> HistoricalClassification | None:
        return self._s.scalar(
            select(HistoricalClassification).where(
                HistoricalClassification.security_id == security_id,
                HistoricalClassification.classification_scheme == scheme,
                _as_of(
                    HistoricalClassification.valid_from,
                    HistoricalClassification.valid_to,
                    as_of,
                ),
            )
        )

    def delisted_between(self, start: date, end: date) -> list[DelistingEvent]:
        return list(
            self._s.scalars(
                select(DelistingEvent)
                .where(DelistingEvent.delisting_date.between(start, end))
                .order_by(DelistingEvent.delisting_date)
            )
        )

    # -- universe membership ----------------------------------------------

    def members_as_of(self, universe_definition_id: int, as_of: date) -> list[UniverseMembership]:
        """Included members reconstructed for `as_of` (the nearest membership
        date <= as_of, i.e. the last reconstitution on/before the query)."""
        latest = self._s.scalar(
            select(UniverseMembership.membership_date)
            .where(
                UniverseMembership.universe_definition_id == universe_definition_id,
                UniverseMembership.membership_date <= as_of,
            )
            .order_by(UniverseMembership.membership_date.desc())
            .limit(1)
        )
        if latest is None:
            return []
        return list(
            self._s.scalars(
                select(UniverseMembership)
                .where(
                    UniverseMembership.universe_definition_id == universe_definition_id,
                    UniverseMembership.membership_date == latest,
                    UniverseMembership.included_flag.is_(True),
                )
                .order_by(UniverseMembership.security_id)
            )
        )

    def is_eligible(self, universe_definition_id: int, security_id: int, as_of: date) -> bool:
        return any(
            m.security_id == security_id for m in self.members_as_of(universe_definition_id, as_of)
        )
