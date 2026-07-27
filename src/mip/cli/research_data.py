"""`mip research-data` — native survivorship-clean outcome foundation (Phase 2A).

Native prices/returns/forward-outcomes keyed on the permanent security_id, the
first-class identity bridge, execution-level experiment provenance, integrity
guardrails, and two-track parity. Real vendor ingestion is BLOCKED pending a
licensed survivorship-clean feed (Norgate + Sharadar); `ingest --fixture` loads a
small deterministic, delisting-inclusive demo so the interfaces are exercisable.
"""

from __future__ import annotations

from datetime import date, datetime

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope

app = typer.Typer(
    help="Native survivorship-clean outcome foundation (Phase 2A).", no_args_is_help=True
)
data_app = typer.Typer(help="Native price/market ingestion & status.", no_args_is_help=True)
outcomes_app = typer.Typer(help="Canonical returns & forward outcomes.", no_args_is_help=True)
snapshots_app = typer.Typer(help="Immutable research dataset snapshots.", no_args_is_help=True)
parity_app = typer.Typer(help="Two-track parity infrastructure.", no_args_is_help=True)
experiments_app = typer.Typer(help="Execution-level experiment provenance.", no_args_is_help=True)
app.add_typer(data_app, name="data")
app.add_typer(outcomes_app, name="outcomes")
app.add_typer(snapshots_app, name="snapshots")
app.add_typer(parity_app, name="parity")
app.add_typer(experiments_app, name="experiments")

_SNAPSHOT_NAME = "demo-native"


def _as_of(value: str | None) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date() if value else date.today()


# -- data ---------------------------------------------------------------------


@data_app.command("ingest")
def data_ingest(
    fixture: bool = typer.Option(False, "--fixture", help="Load the built-in demo snapshot."),
    data_version: str = typer.Option("demo-v1", "--data-version"),
) -> None:
    """Ingest native prices/market/benchmarks/terminals. Real vendors are BLOCKED
    pending a licensed survivorship-clean feed — only `--fixture` today."""
    from mip.research_data import OutcomeIngestor, blocked_outcome_source
    from mip.research_data.demo import demo_outcomes, demo_securities
    from mip.securities import SecurityMasterIngestor

    if not fixture:
        blocked_outcome_source().prices()  # raises ConfigurationError with guidance
        raise typer.Exit(1)

    factory = open_session_factory()
    with session_scope(factory) as s:
        SecurityMasterIngestor(s).ingest(demo_securities(data_version))
        run, stats = OutcomeIngestor(s).ingest(demo_outcomes(data_version))
        typer.echo(
            f"run {run.id} [{run.status.value}] prices={stats.prices} "
            f"market={stats.market_snapshots} benchmarks={stats.benchmarks} "
            f"terminals={stats.terminals} (unresolved={stats.terminals_unresolved}) "
            f"quarantined={stats.quarantined}"
        )


@data_app.command("status")
def data_status() -> None:
    """Row counts for the native outcome tables."""
    from sqlalchemy import func, select

    from mip.domain.models import (
        BenchmarkReturnDaily,
        ForwardReturn,
        SecurityMarketSnapshot,
        SecurityPriceDaily,
        SecurityReturnDaily,
        TerminalOutcome,
    )

    factory = open_session_factory()
    with session_scope(factory) as s:
        for model in (
            SecurityPriceDaily,
            SecurityMarketSnapshot,
            BenchmarkReturnDaily,
            SecurityReturnDaily,
            TerminalOutcome,
            ForwardReturn,
        ):
            n = s.scalar(select(func.count()).select_from(model))
            typer.echo(f"{model.__tablename__:28s} {n}")


# -- outcomes -----------------------------------------------------------------


@outcomes_app.command("build")
def outcomes_build(data_version: str = typer.Option("demo-v1", "--data-version")) -> None:
    """Derive canonical daily returns from native prices."""
    from mip.research_data import DailyReturnBuilder

    factory = open_session_factory()
    with session_scope(factory) as s:
        run, n = DailyReturnBuilder(s, source="fixture", data_version=data_version).build()
        typer.echo(f"run {run.id} [{run.status.value}] daily_returns={n}")


@outcomes_app.command("validate")
def outcomes_validate() -> None:
    """Data-quality checks over native returns."""
    from mip.research_data.quality import check_returns

    factory = open_session_factory()
    with session_scope(factory) as s:
        findings = check_returns(s)
        typer.echo(f"{len(findings)} finding(s)")
        for f in findings[:50]:
            typer.echo(f"  [{f.domain}] {f.rule}: {f.entity} — {f.detail}")


# -- snapshots ----------------------------------------------------------------


@snapshots_app.command("build")
def snapshots_build(
    data_version: str = typer.Option("demo-v1", "--data-version"),
    version: int = typer.Option(1, "--version"),
) -> None:
    """Materialize an immutable, checksummed research dataset snapshot."""
    from sqlalchemy import select

    from mip.domain.models import SecurityMaster
    from mip.research_data import ForwardOutcomeBuilder
    from mip.research_data.demo import DEMO_AS_OFS, DEMO_HORIZONS

    factory = open_session_factory()
    with session_scope(factory) as s:
        ids = list(s.scalars(select(SecurityMaster.security_id)))
        builder = ForwardOutcomeBuilder(
            s, source="fixture", data_version=data_version, horizons=DEMO_HORIZONS
        )
        snap, stats = builder.build_snapshot(
            snapshot_name=_SNAPSHOT_NAME,
            snapshot_version=version,
            as_of_dates=DEMO_AS_OFS,
            security_ids=ids,
            universe_version="US_COMMON_EQUITY_V1",
        )
        typer.echo(
            f"snapshot {snap.snapshot_id} '{snap.snapshot_name}' v{snap.snapshot_version} "
            f"[{snap.status.value}] rows={snap.row_count} checksum={snap.snapshot_checksum[:16]}…"
        )
        typer.echo(f"  outcome status: {stats.to_dict()}")


@snapshots_app.command("show")
def snapshots_show(snapshot_id: int = typer.Argument(...)) -> None:
    from mip.domain.models import ResearchDatasetSnapshot

    factory = open_session_factory()
    with session_scope(factory) as s:
        snap = s.get(ResearchDatasetSnapshot, snapshot_id)
        if snap is None:
            typer.echo("not found")
            raise typer.Exit(1)
        typer.echo(f"{snap.snapshot_name} v{snap.snapshot_version} [{snap.status.value}]")
        typer.echo(
            f"  identity/outcome world: {snap.identity_world.value}/{snap.outcome_world.value}"
        )
        typer.echo(f"  data_version: {snap.data_version}  universe: {snap.universe_version}")
        typer.echo(
            f"  rows={snap.row_count} securities={snap.security_count} dates={snap.date_count}"
        )
        typer.echo(f"  checksum: {snap.snapshot_checksum}")


@snapshots_app.command("verify")
def snapshots_verify(snapshot_id: int = typer.Argument(...)) -> None:
    """Recompute the checksum from persisted rows and confirm it matches (proves
    reproducibility/immutability)."""
    from mip.domain.models import ResearchDatasetSnapshot
    from mip.research_data import rebuild_checksum

    factory = open_session_factory()
    with session_scope(factory) as s:
        snap = s.get(ResearchDatasetSnapshot, snapshot_id)
        if snap is None or not snap.snapshot_checksum:
            typer.echo("not found / no checksum")
            raise typer.Exit(1)
        recomputed = rebuild_checksum(s, snap.snapshot_checksum)
        ok = recomputed == snap.snapshot_checksum
        label = "OK" if ok else "MISMATCH"
        typer.echo(f"{label}: stored={snap.snapshot_checksum[:16]}… recomputed={recomputed[:16]}…")
        if not ok:
            raise typer.Exit(1)


# -- parity -------------------------------------------------------------------


@parity_app.command("computation")
def parity_computation(feature: str = typer.Option(None, "--feature")) -> None:
    """Show computation-equivalence parity results (track 1)."""
    from sqlalchemy import select

    from mip.domain.models import FeatureParityRecord

    factory = open_session_factory()
    with session_scope(factory) as s:
        stmt = select(FeatureParityRecord)
        if feature:
            stmt = stmt.where(FeatureParityRecord.feature_name == feature)
        rows = list(s.scalars(stmt))
        passed = sum(1 for r in rows if r.passed)
        typer.echo(f"{passed}/{len(rows)} computation-equivalence cases passed")
        for r in rows:
            if not r.passed:
                typer.echo(f"  FAIL {r.feature_name}/{r.fixture_key} diff={r.absolute_difference}")


@parity_app.command("divergence")
def parity_divergence() -> None:
    """Show data-divergence characterization (track 2) and blocking status."""
    from sqlalchemy import select

    from mip.domain.models import DataDivergenceRecord
    from mip.research_data.guardrails import count_blocking_divergences

    factory = open_session_factory()
    with session_scope(factory) as s:
        rows = list(s.scalars(select(DataDivergenceRecord)))
        blocking = count_blocking_divergences(s)
        typer.echo(f"{len(rows)} divergence record(s); {blocking} BLOCKING promotion")
        for r in rows:
            typer.echo(
                f"  [{r.divergence_class.value}] {r.review_status.value}: "
                f"{r.feature_name} {r.explanation or ''}"
            )


# -- experiments --------------------------------------------------------------


@experiments_app.command("list")
def experiments_list(experiment_id: str = typer.Argument(None)) -> None:
    from sqlalchemy import select

    from mip.domain.models import ExperimentRun

    factory = open_session_factory()
    with session_scope(factory) as s:
        stmt = select(ExperimentRun).order_by(ExperimentRun.experiment_id, ExperimentRun.run_number)
        if experiment_id:
            stmt = stmt.where(ExperimentRun.experiment_id == experiment_id)
        for r in s.scalars(stmt):
            typer.echo(
                f"{r.experiment_id}#{r.run_number} [{r.status.value}] "
                f"world={r.identity_world.value} checksum={(r.snapshot_checksum or '')[:12]}"
            )


@experiments_app.command("show")
def experiments_show(experiment_run_id: int = typer.Argument(...)) -> None:
    from sqlalchemy import select

    from mip.domain.models import ExperimentRun, ExperimentRunDecision, ExperimentRunMetric

    factory = open_session_factory()
    with session_scope(factory) as s:
        run = s.get(ExperimentRun, experiment_run_id)
        if run is None:
            typer.echo("not found")
            raise typer.Exit(1)
        typer.echo(f"{run.experiment_id}#{run.run_number} [{run.status.value}]")
        typer.echo(f"  identity_world={run.identity_world.value} data_version={run.data_version}")
        typer.echo(f"  snapshot_checksum={run.snapshot_checksum} universe={run.universe_version}")
        typer.echo(
            f"  signal/feature/outcome="
            f"{run.signal_version}/{run.feature_version}/{run.outcome_version}"
        )
        for m in s.scalars(
            select(ExperimentRunMetric).where(
                ExperimentRunMetric.experiment_run_id == run.experiment_run_id
            )
        ):
            typer.echo(f"  metric {m.metric_name}@{m.horizon}={m.value} (n={m.sample_size})")
        dec = s.get(ExperimentRunDecision, run.experiment_run_id)
        if dec:
            typer.echo(f"  decision: {dec.decision.value} — {dec.decision_reason or ''}")


# -- integrity ----------------------------------------------------------------


@app.command("integrity")
def integrity_validate() -> None:
    """Run every research-integrity data-quality check and report findings."""
    from mip.research_data.quality import (
        check_market_snapshots,
        check_prices,
        check_research_integrity,
        check_returns,
    )

    factory = open_session_factory()
    with session_scope(factory) as s:
        findings = (
            check_prices(s, source="fixture", data_version="demo-v1")
            + check_returns(s)
            + check_market_snapshots(s)
            + check_research_integrity(s)
        )
        typer.echo(f"{len(findings)} integrity finding(s)")
        for f in findings[:100]:
            typer.echo(f"  [{f.domain}] {f.rule}: {f.entity} — {f.detail}")
