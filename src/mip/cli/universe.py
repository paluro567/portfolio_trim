"""`mip universe` — seed and inspect the instrument universe."""

from pathlib import Path

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope

app = typer.Typer(help="Instrument universe (seed from universe.yaml, list).", no_args_is_help=True)


@app.command("seed")
def seed(
    file: Path = typer.Option(
        Path("universe.yaml"), "--file", "-f", help="Universe definition YAML."
    ),
) -> None:
    """Idempotently seed sectors, industries, and instruments."""
    from mip.reference.universe import parse_universe, seed_universe

    definition = parse_universe(file)
    factory = open_session_factory()
    with session_scope(factory) as session:
        result = seed_universe(session, definition)

    for kind in sorted(set(result.created) | set(result.existing)):
        typer.echo(
            f"{kind:12} created={result.created.get(kind, 0):3}  "
            f"existing={result.existing.get(kind, 0):3}"
        )


@app.command("list")
def list_() -> None:
    """List all instruments with their classification."""
    from mip.repositories.instruments import InstrumentRepository

    factory = open_session_factory()
    with session_scope(factory) as session:
        repo = InstrumentRepository(session)
        instruments = repo.list_instruments()
        if not instruments:
            typer.echo("No instruments. Run: mip universe seed")
            raise typer.Exit()

        typer.echo(f"{'SYMBOL':8} {'TYPE':6} {'SECTOR':24} {'INDUSTRY':26} NAME")
        for inst in instruments:
            sector = inst.sector or (inst.industry.sector if inst.industry else None)
            typer.echo(
                f"{inst.symbol:8} {inst.instrument_type.value:6} "
                f"{(sector.name if sector else '-'):24} "
                f"{(inst.industry.name if inst.industry else '-'):26} "
                f"{inst.name or '-'}"
            )


@app.command("reference")
def reference(
    limit: int = typer.Option(50, "--limit", help="Max companies per sector."),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Build the fundamentals REFERENCE UNIVERSE (comparison only, never owned)."""
    from sqlalchemy import text

    from mip.cli._deps import open_session_factory
    from mip.core.db import session_scope
    from mip.reference_universe import collect

    members, rejected = collect(limit_per_sector=limit)
    typer.echo(f"candidates: {len(members)} eligible, {len(rejected)} rejected")

    factory = open_session_factory()
    added = existing = unmapped = 0
    with session_scope(factory) as session:
        sectors = {n: i for i, n in session.execute(text("select id, name from sectors")).all()}
        have = {r[0] for r in session.execute(text("select symbol from instruments")).all()}
        for m in members:
            if m.symbol in have:
                existing += 1
                continue
            sid = sectors.get(m.sector)
            if sid is None:
                unmapped += 1
                continue
            if dry_run:
                added += 1
                continue
            session.execute(
                text(
                    "insert into instruments (symbol, name, instrument_type, sector_id, "
                    "currency, is_active, created_at) values (:s, :n, 'stock', :sid, "
                    "'USD', true, now())"
                ),
                {"s": m.symbol, "n": m.name[:120], "sid": sid},
            )
            added += 1
    typer.echo(
        f"reference universe: {added} added, {existing} already present "
        f"(portfolio/benchmark), {unmapped} unmapped sector"
    )
    for sym, sec, why in rejected:
        typer.echo(f"  rejected {sym} ({sec}): {why}")
