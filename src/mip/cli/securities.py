"""`mip securities` — point-in-time security master & universe integrity (Phase 1).

Every identity lookup is *as of* a date: tickers change and are reused, so a
ticker resolves to a security only for a given day. Real vendor ingestion is
BLOCKED pending a survivorship-clean licensed feed; `ingest --fixture` loads a
small deterministic demo snapshot so the interfaces are exercisable end to end.
"""

from __future__ import annotations

from datetime import date, datetime

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope

app = typer.Typer(help="Point-in-time security master & universe (Phase 1).", no_args_is_help=True)
universe_app = typer.Typer(
    help="Versioned, reproducible point-in-time universe.", no_args_is_help=True
)
app.add_typer(universe_app, name="universe")


def _as_of(value: str | None) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date() if value else date.today()


# -- security master ---------------------------------------------------------


@app.command("ingest")
def ingest(
    fixture: bool = typer.Option(
        False, "--fixture", help="Load the built-in deterministic demo snapshot."
    ),
    data_version: str = typer.Option("demo-v1", "--data-version"),
) -> None:
    """Ingest a security-master snapshot. Real vendors are BLOCKED pending a
    licensed survivorship-clean feed — only `--fixture` is available today."""
    from mip.securities import SecurityMasterIngestor, blocked_source
    from mip.securities.demo import demo_source

    if not fixture:
        # Refuse to silently fall back to a survivor-only feed.
        blocked_source()  # raises ConfigurationError with guidance
        raise typer.Exit(1)

    src = demo_source(data_version)
    factory = open_session_factory()
    with session_scope(factory) as session:
        run, stats = SecurityMasterIngestor(session).ingest(src)
        typer.echo(
            f"run {run.id} [{run.status.value}] created={stats.created} "
            f"updated={stats.updated} quarantined={stats.quarantined}"
        )
        for reason in stats.quarantine_reasons:
            typer.echo(f"  quarantined: {reason}")


@app.command("list")
def list_(
    as_of: str = typer.Option(None, "--as-of", help="YYYY-MM-DD (default: today)."),
    include_delisted: bool = typer.Option(True, "--include-delisted/--active-only"),
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """List securities with their ticker as of a date. Delisted names are shown
    by default — dropping them would reintroduce survivorship bias."""
    from sqlalchemy import select

    from mip.domain.models import SecurityMaster
    from mip.repositories.securities import SecurityRepository

    day = _as_of(as_of)
    factory = open_session_factory()
    with session_scope(factory) as session:
        repo = SecurityRepository(session)
        stmt = select(SecurityMaster).order_by(SecurityMaster.security_id).limit(limit)
        if not include_delisted:
            stmt = stmt.where(SecurityMaster.delisted_flag.is_(False))
        rows = list(session.scalars(stmt))
        if not rows:
            typer.echo("No securities. Run `mip securities ingest --fixture`.")
            raise typer.Exit()
        typer.echo(f"{'SID':>5} {'TICKER':10} {'TYPE':14} {'EXCH':8} {'STATUS':10} NAME")
        for sec in rows:
            ticker = repo.ticker_as_of(sec.security_id, day) or "—"
            status = "delisted" if sec.delisted_flag else "active"
            typer.echo(
                f"{sec.security_id:5} {ticker:10} {sec.security_type.value:14} "
                f"{(sec.primary_exchange or '—'):8} {status:10} {sec.name or ''}"
            )


@app.command("show")
def show(
    security_id: int = typer.Argument(..., help="Internal security_id."),
    as_of: str = typer.Option(None, "--as-of"),
) -> None:
    """Full point-in-time picture of one security."""
    from mip.repositories.securities import SecurityRepository

    day = _as_of(as_of)
    factory = open_session_factory()
    with session_scope(factory) as session:
        repo = SecurityRepository(session)
        sec = repo.get(security_id)
        if sec is None:
            typer.echo(f"No security_id {security_id}.", err=True)
            raise typer.Exit(1)
        typer.echo(f"security_id : {sec.security_id}")
        typer.echo(f"name        : {sec.name}")
        typer.echo(f"type        : {sec.security_type.value}")
        typer.echo(f"source      : {sec.source}:{sec.source_security_id}")
        typer.echo(f"first_trade : {sec.first_trade_date}")
        typer.echo(f"delisted    : {sec.delisted_flag} ({sec.delisting_date or '—'})")
        typer.echo(f"data_version: {sec.data_version}")
        typer.echo(f"--- as of {day} ---")
        for i in repo.identifiers_as_of(security_id, day):
            typer.echo(
                f"  {i.identifier_type.value:8} {i.identifier_value:10} "
                f"exch={i.exchange or '—'} [{i.valid_from}..{i.valid_to or '∞'})"
            )
        cls = repo.classification_as_of(security_id, day)
        if cls is not None:
            typer.echo(f"  GICS sector: {cls.sector}")


@app.command("resolve")
def resolve(
    ticker: str = typer.Argument(..., help="Ticker to resolve."),
    as_of: str = typer.Option(None, "--as-of", help="YYYY-MM-DD (default: today)."),
) -> None:
    """Resolve a ticker to its internal security_id *as of* a date. Ticker reuse
    is disambiguated by the as-of interval, not by string equality."""
    from mip.repositories.securities import SecurityRepository

    day = _as_of(as_of)
    factory = open_session_factory()
    with session_scope(factory) as session:
        sid = SecurityRepository(session).resolve_ticker(ticker, day)
        if sid is None:
            typer.echo(f"'{ticker}' resolved to no security as of {day}.")
            raise typer.Exit(1)
        typer.echo(f"'{ticker}' -> security_id {sid} (as of {day})")


@app.command("lifecycle")
def lifecycle(
    security_id: int = typer.Argument(...),
    as_of: str = typer.Option(None, "--as-of"),
) -> None:
    """Point-in-time lifecycle events (listing, ticker change, delisting, ...)."""
    from mip.repositories.securities import SecurityRepository

    day = _as_of(as_of)
    factory = open_session_factory()
    with session_scope(factory) as session:
        events = SecurityRepository(session).lifecycle_as_of(security_id, day)
        if not events:
            typer.echo(f"No lifecycle events for security_id {security_id} as of {day}.")
            raise typer.Exit()
        for e in events:
            extra = ""
            if e.successor_security_id:
                extra = f" -> successor {e.successor_security_id}"
            elif e.predecessor_security_id:
                extra = f" <- predecessor {e.predecessor_security_id}"
            typer.echo(f"  {e.effective_date} {e.event_type.value}{extra}")


# -- universe ----------------------------------------------------------------


@universe_app.command("definitions")
def definitions() -> None:
    """List versioned universe definitions (immutable once frozen)."""
    from sqlalchemy import select

    from mip.domain.models import UniverseDefinition

    factory = open_session_factory()
    with session_scope(factory) as session:
        rows = list(
            session.scalars(
                select(UniverseDefinition).order_by(
                    UniverseDefinition.name, UniverseDefinition.version
                )
            )
        )
        if not rows:
            typer.echo("No universe definitions. Run `mip securities universe build`.")
            raise typer.Exit()
        for d in rows:
            typer.echo(
                f"  #{d.universe_definition_id} {d.name} v{d.version} "
                f"[{d.status.value}] frozen={d.frozen_at}"
            )


@universe_app.command("build")
def build(
    dates: list[str] = typer.Option(
        None, "--date", help="Membership date YYYY-MM-DD (repeatable)."
    ),
    data_version: str = typer.Option("demo-v1", "--data-version"),
) -> None:
    """Reconstruct point-in-time membership for the US common-equity policy and
    record a reproducible manifest (checksum). Re-running the same frozen
    definition and data version yields identical membership."""
    from mip.securities import US_COMMON_EQUITY_V1, UniverseBuilder

    if not dates:
        typer.echo("Provide at least one --date.", err=True)
        raise typer.Exit(1)
    days = [_as_of(d) for d in dates]
    factory = open_session_factory()
    with session_scope(factory) as session:
        run, manifest = UniverseBuilder(session, data_version=data_version).build(
            US_COMMON_EQUITY_V1, days
        )
        typer.echo(
            f"run {run.id} [{run.status.value}] definition #{manifest['universe_definition_id']}"
        )
        typer.echo(f"  included_members : {manifest['included_members']}")
        typer.echo(f"  excluded_by_reason: {manifest['excluded_by_reason']}")
        typer.echo(f"  checksum         : {manifest['checksum']}")


@universe_app.command("members")
def members(
    definition_id: int = typer.Argument(..., help="universe_definition_id."),
    as_of: str = typer.Option(None, "--as-of", help="YYYY-MM-DD (default: today)."),
) -> None:
    """Reconstruct universe membership as of a date (nearest reconstitution
    on/before the query). Membership never extends past a delisting."""
    from mip.repositories.securities import SecurityRepository

    day = _as_of(as_of)
    factory = open_session_factory()
    with session_scope(factory) as session:
        repo = SecurityRepository(session)
        rows = repo.members_as_of(definition_id, day)
        if not rows:
            typer.echo(f"No members for definition {definition_id} as of {day}.")
            raise typer.Exit()
        typer.echo(f"{len(rows)} members as of {day}:")
        for m in rows:
            ticker = repo.ticker_as_of(m.security_id, day) or "—"
            typer.echo(f"  security_id {m.security_id:5} {ticker:10} {m.exchange or '—'}")


@universe_app.command("validate")
def validate(
    definition_id: int = typer.Option(
        None, "--definition-id", help="Also validate this universe's membership."
    ),
) -> None:
    """Run data-quality checks over the security master (and, if given, a
    universe's membership). Exits non-zero if any integrity finding is present."""
    from mip.securities import check_security_master, check_universe_membership

    factory = open_session_factory()
    with session_scope(factory) as session:
        findings = check_security_master(session)
        if definition_id is not None:
            findings += check_universe_membership(session, definition_id)
        if not findings:
            typer.echo("No data-quality findings.")
            raise typer.Exit()
        for f in findings:
            typer.echo(f"  [{f.domain}] {f.rule} {f.entity}: {f.detail}")
        raise typer.Exit(1)
