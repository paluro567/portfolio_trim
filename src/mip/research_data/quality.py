"""Data-quality & integrity checks for the native outcome foundation (Stage 11).

Read-only detectors returning structured findings; the CLI surfaces them and the
ingestors' quarantine ledger complements them. Grouped as prices / returns /
market snapshots / research integrity.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mip.domain.enums import IdentityWorld, OutcomeStatus, ReturnStatus, SnapshotStatus
from mip.domain.models import (
    DelistingEvent,
    ForwardReturn,
    InstrumentSecurityMap,
    ResearchDatasetSnapshot,
    SecurityMarketSnapshot,
    SecurityPriceDaily,
    SecurityReturnDaily,
    TerminalOutcome,
)


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


def check_prices(session: Session, *, source: str, data_version: str) -> list[Finding]:
    findings: list[Finding] = []
    q = lambda *w: session.execute(  # noqa: E731
        select(SecurityPriceDaily).where(
            SecurityPriceDaily.source == source,
            SecurityPriceDaily.data_version == data_version,
            *w,
        )
    ).scalars()

    # duplicate (security, date) within one source+data_version
    dupes = session.execute(
        select(SecurityPriceDaily.security_id, SecurityPriceDaily.trade_date, func.count())
        .where(
            SecurityPriceDaily.source == source,
            SecurityPriceDaily.data_version == data_version,
        )
        .group_by(SecurityPriceDaily.security_id, SecurityPriceDaily.trade_date)
        .having(func.count() > 1)
    ).all()
    for sid, d, n in dupes:
        findings.append(Finding("prices", "duplicate_security_date", f"{sid}/{d}", f"{n} rows"))

    for bar in q():
        if bar.close is not None and bar.close < 0:
            findings.append(
                Finding(
                    "prices", "negative_price", f"{bar.security_id}/{bar.trade_date}", "close<0"
                )
            )
        hi, lo, op, cl = bar.high, bar.low, bar.open, bar.close
        if hi is not None and lo is not None and hi < lo:
            findings.append(
                Finding(
                    "prices", "impossible_ohlc", f"{bar.security_id}/{bar.trade_date}", "high<low"
                )
            )
        for name, v in (("open", op), ("close", cl)):
            if v is not None and hi is not None and lo is not None and not (lo <= v <= hi):
                findings.append(
                    Finding(
                        "prices",
                        "ohlc_out_of_range",
                        f"{bar.security_id}/{bar.trade_date}",
                        f"{name} outside [low,high]",
                    )
                )
        if not bar.source:
            findings.append(
                Finding(
                    "prices", "missing_lineage", f"{bar.security_id}/{bar.trade_date}", "no source"
                )
            )

    # trading AFTER a terminal delisting date
    terms = {t.security_id: t.event_date for t in session.scalars(select(TerminalOutcome))}
    for bar in q():
        term_date = terms.get(bar.security_id)
        if term_date is not None and bar.trade_date > term_date:
            findings.append(
                Finding(
                    "prices",
                    "trading_after_terminal",
                    f"{bar.security_id}/{bar.trade_date}",
                    f"after terminal {term_date}",
                )
            )
    return findings


def check_returns(session: Session) -> list[Finding]:
    findings: list[Finding] = []
    terms = {t.security_id for t in session.scalars(select(TerminalOutcome))}
    for r in session.scalars(select(SecurityReturnDaily)):
        if r.return_status is ReturnStatus.DELISTING and r.security_id not in terms:
            findings.append(
                Finding(
                    "returns",
                    "delisting_return_without_event",
                    f"{r.security_id}/{r.trade_date}",
                    "no terminal_outcome",
                )
            )
        if r.return_status is ReturnStatus.UNRESOLVED and r.total_return is not None:
            findings.append(
                Finding(
                    "returns",
                    "unresolved_with_value",
                    f"{r.security_id}/{r.trade_date}",
                    "unresolved but total_return set",
                )
            )
    return findings


def check_forward_returns(session: Session, snapshot_checksum: str) -> list[Finding]:
    findings: list[Finding] = []
    rows = list(
        session.scalars(
            select(ForwardReturn).where(ForwardReturn.snapshot_checksum == snapshot_checksum)
        )
    )
    delist = {d.security_id: d.delisting_date for d in session.scalars(select(DelistingEvent))}
    for f in rows:
        if f.exit_date and f.entry_date and f.exit_date < f.entry_date:
            findings.append(
                Finding(
                    "forward", "exit_before_entry", f"{f.security_id}/{f.as_of_date}", "exit<entry"
                )
            )
        # a delisting inside the window must be represented, not silently normal
        d = delist.get(f.security_id)
        if (
            d is not None
            and f.entry_date is not None
            and f.entry_date <= d <= (f.exit_date or d)
            and f.outcome_status is OutcomeStatus.NORMAL
        ):
            findings.append(
                Finding(
                    "forward",
                    "delisting_in_window_untreated",
                    f"{f.security_id}/{f.as_of_date}",
                    f"delisted {d} but status normal",
                )
            )
        if f.identity_world is not IdentityWorld.NATIVE_SECURITY:
            findings.append(
                Finding(
                    "forward",
                    "non_native_outcome",
                    f"{f.security_id}/{f.as_of_date}",
                    "outcome not native",
                )
            )
        if not f.snapshot_checksum:
            findings.append(
                Finding(
                    "forward",
                    "missing_snapshot_checksum",
                    f"{f.security_id}/{f.as_of_date}",
                    "no checksum",
                )
            )
    return findings


def check_market_snapshots(session: Session) -> list[Finding]:
    findings: list[Finding] = []
    for m in session.scalars(select(SecurityMarketSnapshot)):
        if m.market_cap is not None and m.market_cap < 0:
            findings.append(
                Finding(
                    "market", "negative_market_cap", f"{m.security_id}/{m.snapshot_date}", "cap<0"
                )
            )
        if m.market_cap is not None and m.shares_outstanding is None:
            findings.append(
                Finding(
                    "market",
                    "market_cap_without_shares",
                    f"{m.security_id}/{m.snapshot_date}",
                    "cap set, shares NULL",
                )
            )
    # snapshot dated AFTER a terminal delisting
    terms = {t.security_id: t.event_date for t in session.scalars(select(TerminalOutcome))}
    for m in session.scalars(select(SecurityMarketSnapshot)):
        t = terms.get(m.security_id)
        if t is not None and m.snapshot_date > t:
            findings.append(
                Finding(
                    "market",
                    "snapshot_after_delisting",
                    f"{m.security_id}/{m.snapshot_date}",
                    f"after terminal {t}",
                )
            )
    return findings


def check_research_integrity(session: Session) -> list[Finding]:
    findings: list[Finding] = []
    # unfrozen snapshots referenced by outcomes
    for snap in session.scalars(select(ResearchDatasetSnapshot)):
        if snap.status is not SnapshotStatus.FROZEN and snap.snapshot_checksum:
            findings.append(
                Finding(
                    "integrity",
                    "unfrozen_snapshot_with_checksum",
                    snap.snapshot_name,
                    "checksum on non-frozen snapshot",
                )
            )
        if snap.status is SnapshotStatus.FROZEN and not snap.snapshot_checksum:
            findings.append(
                Finding(
                    "integrity",
                    "frozen_without_checksum",
                    snap.snapshot_name,
                    "frozen snapshot missing checksum",
                )
            )
        # a native outcome world must not carry a legacy feature world (mixed)
        if (
            snap.outcome_world is IdentityWorld.NATIVE_SECURITY
            and snap.feature_world is IdentityWorld.LEGACY_INSTRUMENT
        ):
            findings.append(
                Finding(
                    "integrity",
                    "mixed_identity_world",
                    snap.snapshot_name,
                    "legacy features + native outcomes",
                )
            )
    # active bridge overlaps
    active = list(
        session.scalars(
            select(InstrumentSecurityMap).where(InstrumentSecurityMap.status == "active")
        )
    )
    by_instr: dict[int, list] = {}
    for r in active:
        by_instr.setdefault(r.instrument_id, []).append(r)
    for instr, group in by_instr.items():
        group.sort(key=lambda r: r.valid_from)
        for i in range(len(group) - 1):
            a, b = group[i], group[i + 1]
            a_to = a.valid_to
            if a_to is None or a_to >= b.valid_from:
                findings.append(
                    Finding(
                        "integrity",
                        "bridge_overlap",
                        f"instrument={instr}",
                        f"maps {a.map_id},{b.map_id} overlap",
                    )
                )
    return findings
