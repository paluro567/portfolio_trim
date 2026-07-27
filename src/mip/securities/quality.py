"""Data-quality checks for the security master & universe membership.

Returns structured findings (severity, rule, entity) that the CLI surfaces and
that the ingestor's quarantine ledger complements. Read-only: these detect
integrity violations rather than fixing them.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mip.domain.models import (
    DelistingEvent,
    HistoricalClassification,
    SecurityIdentifierHistory,
    SecurityMaster,
    UniverseMembership,
)

_FAR_ORD = 3_652_058  # date(9999,12,31).toordinal()


@dataclass(frozen=True)
class Finding:
    domain: str
    rule: str
    entity: str
    detail: str

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "rule": self.rule,
            "entity": self.entity,
            "detail": self.detail,
        }


def _to_ord_date(d) -> int:
    """Ordinal of a date; open-ended (NULL valid_to) maps to +infinity."""
    return d.toordinal() if d is not None else _FAR_ORD


def check_security_master(session: Session) -> list[Finding]:
    findings: list[Finding] = []

    # identity: one identifier VALUE held by >1 security over overlapping dates
    rows = list(
        session.execute(
            select(
                SecurityIdentifierHistory.identifier_type,
                SecurityIdentifierHistory.identifier_value,
                SecurityIdentifierHistory.security_id,
                SecurityIdentifierHistory.valid_from,
                SecurityIdentifierHistory.valid_to,
            )
        )
    )
    by_value: dict[tuple, list] = {}
    for t, v, sid, vf, vt in rows:
        by_value.setdefault((t, v), []).append((sid, vf, vt))
    for (t, v), entries in by_value.items():
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                sid_a, vf_a, vt_a = entries[i]
                sid_b, vf_b, vt_b = entries[j]
                if sid_a == sid_b:
                    continue
                if _to_ord_date(vf_a) <= _to_ord_date(vt_b) and _to_ord_date(vf_b) <= _to_ord_date(
                    vt_a
                ):
                    findings.append(
                        Finding(
                            "security-master",
                            "identifier_shared_over_overlap",
                            f"{t.value}={v}",
                            f"held by security_id {sid_a} and {sid_b} over overlapping intervals",
                        )
                    )

    # delisting: delisted_flag set but no delisting_event row
    delisted_ids = set(
        session.scalars(
            select(SecurityMaster.security_id).where(SecurityMaster.delisted_flag.is_(True))
        )
    )
    event_ids = set(session.scalars(select(DelistingEvent.security_id)))
    for sid in sorted(delisted_ids - event_ids):
        findings.append(
            Finding(
                "security-master",
                "delisted_without_event",
                f"security_id={sid}",
                "delisted_flag=true but no delisting_event",
            )
        )
    # delisting before first trade
    for sec, ev in session.execute(
        select(SecurityMaster, DelistingEvent).join(
            DelistingEvent, DelistingEvent.security_id == SecurityMaster.security_id
        )
    ):
        if sec.first_trade_date and ev.delisting_date < sec.first_trade_date:
            findings.append(
                Finding(
                    "security-master",
                    "delisting_before_listing",
                    f"security_id={sec.security_id}",
                    f"delisted {ev.delisting_date} < first_trade {sec.first_trade_date}",
                )
            )

    # classification after delisting
    for cl, sec in session.execute(
        select(HistoricalClassification, SecurityMaster).join(
            SecurityMaster, SecurityMaster.security_id == HistoricalClassification.security_id
        )
    ):
        if sec.delisting_date and cl.valid_from > sec.delisting_date:
            findings.append(
                Finding(
                    "security-master",
                    "classification_after_delisting",
                    f"security_id={sec.security_id}",
                    f"classification valid_from {cl.valid_from} > delisting {sec.delisting_date}",
                )
            )
    return findings


def check_universe_membership(session: Session, universe_definition_id: int) -> list[Finding]:
    findings: list[Finding] = []
    rows = session.execute(
        select(UniverseMembership, SecurityMaster)
        .join(SecurityMaster, SecurityMaster.security_id == UniverseMembership.security_id)
        .where(
            UniverseMembership.universe_definition_id == universe_definition_id,
            UniverseMembership.included_flag.is_(True),
        )
    )
    for mem, sec in rows:
        if sec.delisting_date and mem.membership_date > sec.delisting_date:
            findings.append(
                Finding(
                    "universe-membership",
                    "membership_after_delisting",
                    f"security_id={sec.security_id}",
                    f"member on {mem.membership_date} > delisting {sec.delisting_date}",
                )
            )
        if sec.first_trade_date and mem.membership_date < sec.first_trade_date:
            findings.append(
                Finding(
                    "universe-membership",
                    "membership_before_listing",
                    f"security_id={sec.security_id}",
                    f"member on {mem.membership_date} < first_trade {sec.first_trade_date}",
                )
            )
    return findings


def membership_count(session: Session, universe_definition_id: int, membership_date) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(UniverseMembership)
            .where(
                UniverseMembership.universe_definition_id == universe_definition_id,
                UniverseMembership.membership_date == membership_date,
                UniverseMembership.included_flag.is_(True),
            )
        )
        or 0
    )
