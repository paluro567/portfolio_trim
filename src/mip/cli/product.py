"""Product decision-support report for one holding across five horizons."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope
from mip.product.contracts import Status
from mip.product.decide import decide
from mip.product.policy import DEFAULT_POLICY_PATH, PolicyArtifact, load_policy
from mip.product.render import render
from mip.product.slice import evaluate_constraints, gather_evidence, load_position

app = typer.Typer(help="Product decision-support reports (descriptive; no predictive claims).")

DEFAULT_BALANCES = Path("data/peter_real_opening_balances_2026-07-16.csv")


@app.command("report")
def report(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Ticker, e.g. AMZN"),
    as_of: str = typer.Option(..., "--as-of", help="ISO date, e.g. 2026-07-16"),
    balances: Path = typer.Option(DEFAULT_BALANCES, "--balances", help="Holdings CSV"),
    out_dir: Path = typer.Option(Path("data/product_reports"), "--out-dir"),
    policy_path: Path = typer.Option(DEFAULT_POLICY_PATH, "--policy"),
) -> None:
    """Generate one decision-support report and archive its inputs."""
    symbol = symbol.strip().upper()
    try:
        as_of_d = date.fromisoformat(as_of)
    except ValueError as exc:
        raise typer.BadParameter(f"--as-of must be ISO YYYY-MM-DD: {exc}") from exc
    if not balances.exists():
        raise typer.BadParameter(f"balances file not found: {balances}")

    commit = (
        subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        or "unknown"
    )

    factory = open_session_factory()
    with session_scope(factory) as session:
        try:
            pos = load_position(session, symbol, as_of_d, balances)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        evidence = gather_evidence(session, symbol, as_of_d)
        policy = load_policy(policy_path)
        constraints = evaluate_constraints(pos, policy)
        verdicts = decide(evidence, constraints, pos)
        # Catalyst events are intentionally FUTURE-dated (a scheduled earnings
        # release). They must not be reported as the latest observed data date.
        feature_dates = [e.as_of for e in evidence if e.as_of and e.domain != "catalysts"]
        meta = {
            "commit": commit,
            "feature_date": max(feature_dates).isoformat() if feature_dates else "unavailable",
            "generated_at": datetime.now(UTC).isoformat(),
            "balances_sha256": hashlib.sha256(balances.read_bytes()).hexdigest(),
            "balances_path": str(balances),
            "policy": policy.to_dict(),
        }
        markdown = render(pos, evidence, constraints, verdicts, meta)

    stamp = out_dir / as_of_d.isoformat() / symbol
    stamp.mkdir(parents=True, exist_ok=True)
    report_path = stamp / f"{symbol}_{as_of_d.isoformat()}.md"
    report_path.write_text(markdown)

    bundle = {
        "meta": meta,
        "position": pos.to_dict(),
        "constraints": [c.to_dict() for c in constraints],
        "evidence": [e.to_dict() for e in evidence],
        "verdicts": [v.to_dict() for v in verdicts],
    }
    inputs_path = stamp / "inputs.json"
    inputs_path.write_text(json.dumps(bundle, indent=2, sort_keys=True))
    (stamp / "report.sha256").write_text(
        f"{hashlib.sha256(markdown.encode()).hexdigest()}  {report_path.name}\n"
        f"{hashlib.sha256(inputs_path.read_bytes()).hexdigest()}  inputs.json\n"
    )

    avail = sum(1 for e in evidence if e.status is not Status.UNAVAILABLE)
    typer.echo(f"report:  {report_path}")
    typer.echo(f"inputs:  {inputs_path}")
    typer.echo(f"evidence: {avail} available / {len(evidence)} total")
    if isinstance(policy, PolicyArtifact):
        typer.echo(
            f"policy:   {policy.policy_version} (cap {policy.hard_cap_pct}%, "
            f"target {policy.core_target_pct}%)"
        )
    else:
        typer.echo(f"policy:   NOT SUPPLIED - required and unset: {', '.join(policy.missing)}")
        typer.echo(f"          supply them in {policy.path} to make concentration evaluable")
    for v in verdicts:
        typer.echo(
            f"  {v.horizon:>3}  {v.action.value:<8} {v.direction.value:<11} {v.confidence.value}"
        )
