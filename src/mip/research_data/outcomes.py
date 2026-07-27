"""Native canonical returns, delist-aware forward outcomes, and reproducible
research snapshots (Stages 3.3, 3.4, 3.5, 4, 10).

Non-negotiable rule: the forward-outcome generator NEVER discards an observation
because a security lacks a normal exit price. A delisting inside the window is
valued via its terminal outcome; an unknown terminal is recorded as ``unresolved``
(never assumed to be -100%); a still-listed name at the data edge is ``truncated``.
Every outcome carries the full integrity stamp set and a deterministic checksum
so that rebuilding from the same inputs reproduces the same snapshot.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.domain.enums import (
    IdentityWorld,
    OutcomeStatus,
    ReturnStatus,
    RunStatus,
    RunType,
    SnapshotStatus,
    TerminalRule,
)
from mip.domain.models import (
    BenchmarkReturnDaily,
    ForwardReturn,
    IngestionRun,
    ResearchDatasetSnapshot,
    SecurityMarketSnapshot,
    SecurityMaster,
    SecurityPriceDaily,
    SecurityReturnDaily,
    TerminalOutcome,
)

RETURN_CALC_VERSION = "return-v1"
FORWARD_CALC_VERSION = "forward-v1"
DEFAULT_HORIZONS: dict[str, int] = {"1m": 30, "3m": 91, "1y": 365}


def _f(x) -> float | None:
    return float(x) if x is not None else None


# -- daily canonical returns ---------------------------------------------------


class DailyReturnBuilder:
    """Derives per-day total returns from native prices, marking the nature of
    each day (normal / corporate_action / delisting / missing)."""

    def __init__(self, session: Session, *, source: str, data_version: str) -> None:
        self._s = session
        self._source = source
        self._data_version = data_version

    def build(self) -> tuple[IngestionRun, int]:
        run = IngestionRun(
            run_type=RunType.RESEARCH_OUTCOMES,
            provider=self._source,
            scope=f"{self._data_version}/{RETURN_CALC_VERSION}",
            status=RunStatus.RUNNING,
        )
        self._s.add(run)
        self._s.flush()

        terminals = {t.security_id: t for t in self._s.scalars(select(TerminalOutcome))}
        written = 0
        for sid in self._s.scalars(
            select(SecurityMaster.security_id).order_by(SecurityMaster.security_id)
        ):
            bars = list(
                self._s.scalars(
                    select(SecurityPriceDaily)
                    .where(
                        SecurityPriceDaily.security_id == sid,
                        SecurityPriceDaily.source == self._source,
                        SecurityPriceDaily.data_version == self._data_version,
                    )
                    .order_by(SecurityPriceDaily.trade_date)
                )
            )
            prev = None
            for bar in bars:
                price_ret = None
                status = ReturnStatus.NORMAL
                if prev is not None and prev.adjusted_close and bar.adjusted_close:
                    price_ret = (bar.adjusted_close / prev.adjusted_close) - Decimal(1)
                    if bar.split_factor or bar.dividend_amount:
                        status = ReturnStatus.CORPORATE_ACTION
                elif prev is not None:
                    status = ReturnStatus.MISSING
                self._upsert_return(run, sid, bar.trade_date, price_ret, status)
                written += 1
                prev = bar
            # delisting day return, if a terminal exists
            term = terminals.get(sid)
            if term is not None:
                if term.resolved and term.terminal_return is not None:
                    self._upsert_return(
                        run,
                        sid,
                        term.event_date,
                        None,
                        ReturnStatus.DELISTING,
                        delisting_return=term.terminal_return,
                    )
                else:
                    self._upsert_return(run, sid, term.event_date, None, ReturnStatus.UNRESOLVED)
                written += 1

        run.completed_at = datetime.now(UTC)
        run.status = RunStatus.SUCCESS
        run.rows_inserted = written
        self._s.flush()
        return run, written

    def _upsert_return(
        self, run, sid, trade_date, price_ret, status, *, delisting_return=None
    ) -> None:
        total = None
        if price_ret is not None:
            total = price_ret
        if delisting_return is not None:
            total = delisting_return
        existing = self._s.scalar(
            select(SecurityReturnDaily).where(
                SecurityReturnDaily.security_id == sid,
                SecurityReturnDaily.trade_date == trade_date,
                SecurityReturnDaily.source == self._source,
                SecurityReturnDaily.data_version == self._data_version,
                SecurityReturnDaily.calculation_version == RETURN_CALC_VERSION,
            )
        )
        if existing is None:
            self._s.add(
                SecurityReturnDaily(
                    security_id=sid,
                    trade_date=trade_date,
                    price_return=price_ret,
                    dividend_return=None,
                    delisting_return=delisting_return,
                    total_return=total,
                    return_status=status,
                    source=self._source,
                    ingestion_run_id=run.id,
                    data_version=self._data_version,
                    calculation_version=RETURN_CALC_VERSION,
                )
            )
        else:
            existing.price_return = price_ret
            existing.delisting_return = delisting_return
            existing.total_return = total
            existing.return_status = status
            existing.ingestion_run_id = run.id


# -- forward outcomes + snapshot ----------------------------------------------


@dataclass
class ForwardStats:
    written: int = 0
    normal: int = 0
    delisted_in_window: int = 0
    terminated: int = 0
    truncated: int = 0
    unresolved: int = 0
    no_entry_price: int = 0

    def to_dict(self) -> dict:
        return {
            "written": self.written,
            "normal": self.normal,
            "delisted_in_window": self.delisted_in_window,
            "terminated": self.terminated,
            "truncated": self.truncated,
            "unresolved": self.unresolved,
            "no_entry_price": self.no_entry_price,
        }


@dataclass
class _Computed:
    """A forward outcome computed in memory before the checksum is known."""

    security_id: int
    as_of: date
    horizon: str
    entry_date: date | None
    exit_date: date | None
    absolute_return: Decimal | None
    benchmark_relative: Decimal | None
    sector_relative: Decimal | None
    terminal_event: bool
    delisting_in_window: bool
    status: OutcomeStatus


class ForwardOutcomeBuilder:
    """Builds delist-aware forward returns and materializes an immutable,
    reproducible research snapshot. `security_ids` restricts to a universe."""

    def __init__(
        self,
        session: Session,
        *,
        source: str,
        data_version: str,
        horizons: dict[str, int] | None = None,
        benchmark_source: str | None = None,
    ) -> None:
        self._s = session
        self._source = source
        self._data_version = data_version
        self._horizons = horizons or DEFAULT_HORIZONS
        self._benchmark_source = benchmark_source or source

    # -- price/benchmark helpers --

    def _prices(self, sid: int) -> list[SecurityPriceDaily]:
        return list(
            self._s.scalars(
                select(SecurityPriceDaily)
                .where(
                    SecurityPriceDaily.security_id == sid,
                    SecurityPriceDaily.source == self._source,
                    SecurityPriceDaily.data_version == self._data_version,
                )
                .order_by(SecurityPriceDaily.trade_date)
            )
        )

    def _benchmark(self, key: str) -> list[tuple[date, Decimal]]:
        rows = self._s.execute(
            select(BenchmarkReturnDaily.trade_date, BenchmarkReturnDaily.total_return)
            .where(
                BenchmarkReturnDaily.benchmark_key == key,
                BenchmarkReturnDaily.source == self._benchmark_source,
                BenchmarkReturnDaily.total_return.is_not(None),
            )
            .order_by(BenchmarkReturnDaily.trade_date)
        ).all()
        return [(d, r) for d, r in rows]

    @staticmethod
    def _cum(series: list[tuple[date, Decimal]], entry: date, exit_: date) -> Decimal | None:
        if entry is None or exit_ is None:
            return None
        acc = Decimal(1)
        seen = False
        for d, r in series:
            if entry < d <= exit_:
                acc *= Decimal(1) + r
                seen = True
        return (acc - Decimal(1)) if seen else Decimal(0)

    def _sector_as_of(self, sid: int, as_of: date) -> str | None:
        return self._s.scalar(
            select(SecurityMarketSnapshot.sector)
            .where(
                SecurityMarketSnapshot.security_id == sid,
                SecurityMarketSnapshot.snapshot_date <= as_of,
                SecurityMarketSnapshot.sector.is_not(None),
            )
            .order_by(SecurityMarketSnapshot.snapshot_date.desc())
            .limit(1)
        )

    def _compute_one(
        self,
        sid: int,
        as_of: date,
        horizon: str,
        bars: list[SecurityPriceDaily],
        term: TerminalOutcome | None,
        market: list[tuple[date, Decimal]],
    ) -> _Computed:
        target = as_of + timedelta(days=self._horizons[horizon])
        entry = next((b for b in bars if b.trade_date >= as_of), None)
        if entry is None or not entry.adjusted_close:
            return _Computed(
                sid,
                as_of,
                horizon,
                None,
                None,
                None,
                None,
                None,
                False,
                False,
                OutcomeStatus.NO_ENTRY_PRICE,
            )

        term_in_window = (
            term is not None and term.event_date <= target and term.event_date >= entry.trade_date
        )

        if term_in_window:
            last = max(
                (b for b in bars if b.trade_date <= term.event_date and b.adjusted_close),
                key=lambda b: b.trade_date,
                default=entry,
            )
            if not term.resolved or term.terminal_return is None:
                # terminal event but no known value -> UNRESOLVED (never dropped)
                return _Computed(
                    sid,
                    as_of,
                    horizon,
                    entry.trade_date,
                    term.event_date,
                    None,
                    None,
                    None,
                    True,
                    True,
                    OutcomeStatus.UNRESOLVED,
                )
            price_leg = (
                (last.adjusted_close / entry.adjusted_close) if last.adjusted_close else Decimal(1)
            )
            total = price_leg * (Decimal(1) + term.terminal_return) - Decimal(1)
            status = (
                OutcomeStatus.TERMINATED
                if term.rule
                in (
                    TerminalRule.CASH_ACQUISITION,
                    TerminalRule.STOCK_ACQUISITION,
                    TerminalRule.MERGER,
                )
                else OutcomeStatus.DELISTED_IN_WINDOW
            )
            bench = self._cum(market, entry.trade_date, term.event_date)
            return _Computed(
                sid,
                as_of,
                horizon,
                entry.trade_date,
                term.event_date,
                total,
                (total - bench) if bench is not None else None,
                None,
                True,
                True,
                status,
            )

        # normal / truncated
        priced = [b for b in bars if b.trade_date <= target and b.adjusted_close]
        exit_bar = max(priced, key=lambda b: b.trade_date, default=entry)
        last_overall = bars[-1].trade_date if bars else exit_bar.trade_date
        truncated = last_overall < target and term is None
        total = (exit_bar.adjusted_close / entry.adjusted_close) - Decimal(1)
        bench = self._cum(market, entry.trade_date, exit_bar.trade_date)
        status = OutcomeStatus.TRUNCATED if truncated else OutcomeStatus.NORMAL
        return _Computed(
            sid,
            as_of,
            horizon,
            entry.trade_date,
            exit_bar.trade_date,
            total,
            (total - bench) if bench is not None else None,
            None,
            False,
            False,
            status,
        )

    def build_snapshot(
        self,
        *,
        snapshot_name: str,
        snapshot_version: int,
        as_of_dates: list[date],
        security_ids: list[int],
        universe_definition_id: int | None = None,
        universe_version: str | None = None,
        code_sha: str | None = None,
    ) -> tuple[ResearchDatasetSnapshot, ForwardStats]:
        run = IngestionRun(
            run_type=RunType.RESEARCH_SNAPSHOT,
            provider=self._source,
            scope=f"{snapshot_name} v{snapshot_version}",
            status=RunStatus.RUNNING,
        )
        self._s.add(run)
        self._s.flush()

        market = self._benchmark("MARKET")
        terminals = {t.security_id: t for t in self._s.scalars(select(TerminalOutcome))}
        computed: list[_Computed] = []
        for sid in sorted(security_ids):
            bars = self._prices(sid)
            term = terminals.get(sid)
            for as_of in sorted(as_of_dates):
                for horizon in self._horizons:
                    computed.append(self._compute_one(sid, as_of, horizon, bars, term, market))

        # deterministic checksum over the fully-ordered computed outcome tuples
        payload = "|".join(
            f"{c.security_id}:{c.as_of.isoformat()}:{c.horizon}:{c.status.value}:"
            f"{'' if c.absolute_return is None else format(c.absolute_return, '.10f')}"
            for c in sorted(computed, key=lambda c: (c.security_id, c.as_of, c.horizon))
        )
        checksum = hashlib.sha256(payload.encode()).hexdigest()

        stats = ForwardStats()
        for c in computed:
            self._persist(run, c, checksum, universe_version, stats)
            stats.written += 1
            _bump(stats, c.status)

        snapshot = ResearchDatasetSnapshot(
            snapshot_name=snapshot_name,
            snapshot_version=snapshot_version,
            universe_definition_id=universe_definition_id,
            universe_version=universe_version,
            identity_world=IdentityWorld.NATIVE_SECURITY,
            feature_world=None,  # Phase 2A: no native features yet (Phase 2B)
            outcome_world=IdentityWorld.NATIVE_SECURITY,
            data_version=self._data_version,
            code_sha=code_sha,
            row_count=stats.written,
            security_count=len(set(c.security_id for c in computed)),
            date_count=len(set(c.as_of for c in computed)),
            snapshot_checksum=checksum,
            status=SnapshotStatus.FROZEN,
            frozen_at=datetime.now(UTC),
            manifest_json={
                "as_of_dates": [d.isoformat() for d in sorted(as_of_dates)],
                "horizons": self._horizons,
                "source": self._source,
                "data_version": self._data_version,
                "included_securities": sorted(set(c.security_id for c in computed)),
                "outcome_status_counts": stats.to_dict(),
                "checksum": checksum,
            },
        )
        self._s.add(snapshot)
        run.completed_at = datetime.now(UTC)
        run.status = RunStatus.SUCCESS
        run.rows_inserted = stats.written
        run.error_detail = {"checksum": checksum, **stats.to_dict()}
        self._s.flush()
        return snapshot, stats

    def _persist(self, run, c: _Computed, checksum, universe_version, stats) -> None:
        self._s.add(
            ForwardReturn(
                security_id=c.security_id,
                as_of_date=c.as_of,
                horizon=c.horizon,
                entry_date=c.entry_date,
                exit_date=c.exit_date,
                absolute_return=c.absolute_return,
                benchmark_relative_return=c.benchmark_relative,
                sector_relative_return=c.sector_relative,
                residual_return=None,
                terminal_event_flag=c.terminal_event,
                delisting_in_window_flag=c.delisting_in_window,
                outcome_status=c.status,
                identity_world=IdentityWorld.NATIVE_SECURITY,
                calculation_version=FORWARD_CALC_VERSION,
                universe_version=universe_version,
                snapshot_checksum=checksum,
                source_data_version=self._data_version,
                ingestion_run_id=run.id,
            )
        )


def _bump(stats: ForwardStats, status: OutcomeStatus) -> None:
    setattr(stats, status.value, getattr(stats, status.value) + 1)


def rebuild_checksum(session: Session, snapshot_checksum: str) -> str:
    """Recompute the checksum from the PERSISTED forward_return rows of a
    snapshot — used to verify reproducibility/immutability."""
    rows = session.execute(
        select(
            ForwardReturn.security_id,
            ForwardReturn.as_of_date,
            ForwardReturn.horizon,
            ForwardReturn.outcome_status,
            ForwardReturn.absolute_return,
        )
        .where(ForwardReturn.snapshot_checksum == snapshot_checksum)
        .order_by(ForwardReturn.security_id, ForwardReturn.as_of_date, ForwardReturn.horizon)
    ).all()
    payload = "|".join(
        f"{sid}:{d.isoformat()}:{h}:{st.value}:" f"{'' if ar is None else format(ar, '.10f')}"
        for sid, d, h, st, ar in rows
    )
    return hashlib.sha256(payload.encode()).hexdigest()
