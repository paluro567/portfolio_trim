"""Product decision-support reports for one holding across five horizons.

Two artifacts per holding:

* ``<SYM>_<DATE>.md``       the long-form DETERMINISTIC report (unchanged; the
                            audit artifact, and still the only thing produced
                            when the research layer is off)
* ``<SYM>_<DATE>_BRIEF.md`` the concise INVESTMENT DECISION BRIEF, added by
                            ``--with-research``, combining the deterministic
                            evidence with current cited web research

The research layer is opt-in per run and degrades to "UNAVAILABLE" rather than
failing the report.
"""

from __future__ import annotations

import csv as _csv
import hashlib
import json
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope
from mip.product.contracts import Status
from mip.product.decide import decide
from mip.product.policy import DEFAULT_POLICY_PATH, PolicyArtifact, load_policy
from mip.product.portfolio_view import render_portfolio, summarise
from mip.product.render import render
from mip.product.slice import evaluate_constraints, gather_evidence, load_position

app = typer.Typer(help="Product decision-support reports (descriptive; no predictive claims).")

# The MUTABLE current holdings source, read on every run. It is not an opening
# balance and not a dated artifact: edit it when a position changes. Dated files
# under data/ and the report cohorts under data/product_reports/<date>/ are the
# immutable historical record and must not be edited in its place.
# Override per run with --balances.
DEFAULT_BALANCES = Path("data/current_holdings.csv")

# Recorded in the payload so the research layer can disclose the exposure gap.
UNSUPPORTED_POSITIONS = Path("data/unsupported_positions_2026-07-16.csv")


def _commit() -> str:
    return (
        subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        or "unknown"
    )


def _iso(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(f"--as-of must be ISO YYYY-MM-DD: {exc}") from exc


def _unsupported_note() -> str | None:
    if not UNSUPPORTED_POSITIONS.is_file():
        return None
    return (
        f"The broker export excludes listed options. {UNSUPPORTED_POSITIONS} records "
        f"positions that are NOT represented anywhere in this report, so portfolio "
        f"exposure is understated wherever that file lists this symbol."
    )


def _meta(commit: str, evidence, balances: Path, policy) -> dict:
    # Catalyst events are intentionally FUTURE-dated (a scheduled earnings
    # release). They must not be reported as the latest observed data date.
    dates = [e.as_of for e in evidence if e.as_of and e.domain != "catalysts"]
    return {
        "commit": commit,
        "feature_date": max(dates).isoformat() if dates else "unavailable",
        "generated_at": datetime.now(UTC).isoformat(),
        "balances_sha256": hashlib.sha256(balances.read_bytes()).hexdigest(),
        "balances_path": str(balances),
        "policy": policy.to_dict(),
    }


# --------------------------------------------------------------- assembled unit
class _Holding:
    """Everything gathered for one holding inside the DB session."""

    __slots__ = (
        "symbol",
        "pos",
        "evidence",
        "constraints",
        "verdicts",
        "meta",
        "markdown",
        "payload",
        "stale",
    )

    def __init__(
        self, symbol, pos, evidence, constraints, verdicts, meta, markdown, payload, stale
    ):
        self.symbol = symbol
        self.pos = pos
        self.evidence = evidence
        self.constraints = constraints
        self.verdicts = verdicts
        self.meta = meta
        self.markdown = markdown
        self.payload = payload
        self.stale = stale


def _gather(
    session, symbol: str, as_of: date, balances: Path, policy, commit: str, *, want_payload: bool
) -> _Holding:
    """Build one holding's deterministic bundle. All DB work happens here."""
    from mip.research_assistant.payload import build_payload, load_identity, load_market_context

    pos = load_position(session, symbol, as_of, balances)
    evidence = gather_evidence(session, symbol, as_of)
    constraints = evaluate_constraints(pos, policy)
    verdicts = decide(evidence, constraints, pos)
    meta = _meta(commit, evidence, balances, policy)
    markdown = render(pos, evidence, constraints, verdicts, meta)

    payload = None
    if want_payload:
        identity = load_identity(session, symbol)
        payload = build_payload(
            pos,
            evidence,
            constraints,
            verdicts,
            policy=policy,
            company_name=identity["company_name"],
            sector=identity["sector"],
            industry=identity["industry"],
            market_context=load_market_context(session, as_of),
            unsupported_positions_note=_unsupported_note(),
        )

    stale = (as_of - pos.price_date).days if pos.price_date else None
    return _Holding(symbol, pos, evidence, constraints, verdicts, meta, markdown, payload, stale)


def _write_deterministic(stamp: Path, h: _Holding, as_of: date) -> Path:
    d = stamp / h.symbol
    d.mkdir(parents=True, exist_ok=True)
    report_path = d / f"{h.symbol}_{as_of.isoformat()}.md"
    report_path.write_text(h.markdown)

    bundle = {
        "meta": h.meta,
        "position": h.pos.to_dict(),
        "constraints": [c.to_dict() for c in h.constraints],
        "evidence": [e.to_dict() for e in h.evidence],
        "verdicts": [v.to_dict() for v in h.verdicts],
    }
    inputs_path = d / "inputs.json"
    inputs_path.write_text(json.dumps(bundle, indent=2, sort_keys=True))
    (d / "report.sha256").write_text(
        f"{hashlib.sha256(h.markdown.encode()).hexdigest()}  {report_path.name}\n"
        f"{hashlib.sha256(inputs_path.read_bytes()).hexdigest()}  inputs.json\n"
    )
    return report_path


def _research_one(h: _Holding, *, settings, store, refresh: bool):
    """Run research for one holding. Returns a ResearchOutcome; never raises."""
    from mip.research_assistant.research import run_research

    actions = {v.horizon: v.action.value for v in h.verdicts}
    return run_research(
        h.payload,
        actions,
        settings=settings,
        store=store,
        deterministic_report_hash=hashlib.sha256(h.markdown.encode()).hexdigest(),
        refresh=refresh,
    )


def _write_brief(stamp: Path, h: _Holding, outcome, as_of: date) -> Path:
    from mip.research_assistant.render import render_brief

    d = stamp / h.symbol
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{h.symbol}_{as_of.isoformat()}_BRIEF.md"
    path.write_text(render_brief(h.pos, h.verdicts, outcome, h.meta))
    return path


def _usage_summary(usages: list[Any]) -> str:
    totals = {"input": 0, "output": 0, "searches": 0, "seconds": 0.0}
    counted = 0
    for u in usages:
        if u is None:
            continue
        counted += 1
        totals["input"] += u.input_tokens or 0
        totals["output"] += u.output_tokens or 0
        totals["searches"] += u.web_search_calls
        totals["seconds"] += u.elapsed_seconds
    if not counted:
        return "no API usage recorded"
    return (
        f"{counted} researched · {totals['input']:,} in / {totals['output']:,} out tokens "
        f"· {totals['searches']} web searches · {totals['seconds']:.1f}s"
    )


def _echo_research_summary(outcomes: list[Any]) -> None:
    from mip.research_assistant.contracts import ResearchStatus

    ok = sum(1 for o in outcomes if o.status is ResearchStatus.OK)
    cached = sum(1 for o in outcomes if o.status is ResearchStatus.CACHED)
    failed = [o for o in outcomes if o.status is ResearchStatus.FAILED]
    disabled = [o for o in outcomes if o.status is ResearchStatus.DISABLED]

    typer.echo(
        f"research  : {ok} new, {cached} cached, {len(failed)} failed, " f"{len(disabled)} disabled"
    )
    typer.echo(f"api usage : {_usage_summary([o.usage for o in outcomes])}")
    for o in failed[:5]:
        typer.echo(f"  FAILED {o.symbol}: {o.failure_reason}")
    if disabled:
        typer.echo(f"  DISABLED: {disabled[0].failure_reason}")
    for o in outcomes:
        if o.validation is not None and not o.validation.ok:
            typer.echo(f"  citations {o.symbol}: {o.validation.summary()}")


def _research_context(no_llm: bool):
    """(settings, store) or (None, None) when the layer must not run."""
    from mip.research_assistant.cache import ArtifactStore
    from mip.research_assistant.config import load_research_settings

    settings = load_research_settings()
    if no_llm:
        return None, None
    return settings, ArtifactStore(root=settings.research_root)


# ------------------------------------------------------------------- commands
@app.command("report")
def report(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Ticker, e.g. AMZN"),
    as_of: str = typer.Option(..., "--as-of", help="ISO date, e.g. 2026-07-16"),
    balances: Path = typer.Option(DEFAULT_BALANCES, "--balances", help="Holdings CSV"),
    out_dir: Path = typer.Option(Path("data/product_reports"), "--out-dir"),
    policy_path: Path = typer.Option(DEFAULT_POLICY_PATH, "--policy"),
    with_research: bool = typer.Option(
        False, "--with-research", help="Add the cited investment decision brief."
    ),
    no_llm: bool = typer.Option(
        False, "--no-llm", help="Hard override: never call OpenAI, whatever the config says."
    ),
    refresh_research: bool = typer.Option(
        False, "--refresh-research", help="Ignore cached research and search the web again."
    ),
    research_only: bool = typer.Option(
        False, "--research-only", help="Write only the brief; skip the long-form report."
    ),
) -> None:
    """Generate one decision-support report and archive its inputs."""
    symbol = symbol.strip().upper()
    as_of_d = _iso(as_of)
    if not balances.exists():
        raise typer.BadParameter(f"balances file not found: {balances}")
    want_research = with_research and not no_llm

    factory = open_session_factory()
    with session_scope(factory) as session:
        policy = load_policy(policy_path)
        try:
            holding = _gather(
                session,
                symbol,
                as_of_d,
                balances,
                policy,
                _commit(),
                want_payload=want_research,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

    stamp = out_dir / as_of_d.isoformat()
    if not research_only:
        report_path = _write_deterministic(stamp, holding, as_of_d)
        typer.echo(f"report:  {report_path}")
        typer.echo(f"inputs:  {stamp / symbol / 'inputs.json'}")

    if want_research:
        settings, store = _research_context(no_llm)
        outcome = _research_one(holding, settings=settings, store=store, refresh=refresh_research)
        brief_path = _write_brief(stamp, holding, outcome, as_of_d)
        typer.echo(f"brief:   {brief_path}")
        _echo_research_summary([outcome])
    elif research_only:
        raise typer.BadParameter("--research-only requires --with-research (and not --no-llm)")

    avail = sum(1 for e in holding.evidence if e.status is not Status.UNAVAILABLE)
    typer.echo(f"evidence: {avail} available / {len(holding.evidence)} total")
    if isinstance(policy, PolicyArtifact):
        typer.echo(
            f"policy:   {policy.policy_version} (cap {policy.hard_cap_pct}%, "
            f"target {policy.core_target_pct}%)"
        )
    else:
        typer.echo(f"policy:   NOT SUPPLIED - required and unset: {', '.join(policy.missing)}")
        typer.echo(f"          supply them in {policy.path} to make concentration evaluable")
    for v in holding.verdicts:
        typer.echo(
            f"  {v.horizon:>3}  {v.action.value:<8} {v.direction.value:<11} {v.confidence.value}"
        )


@app.command("research")
def research(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Ticker, e.g. AMZN"),
    as_of: str = typer.Option(..., "--as-of", help="ISO date"),
    balances: Path = typer.Option(DEFAULT_BALANCES, "--balances"),
    out_dir: Path = typer.Option(Path("data/product_reports"), "--out-dir"),
    policy_path: Path = typer.Option(DEFAULT_POLICY_PATH, "--policy"),
    refresh_research: bool = typer.Option(False, "--refresh-research"),
    no_llm: bool = typer.Option(False, "--no-llm"),
    show_payload: bool = typer.Option(
        False, "--show-payload", help="Print the deterministic payload and make no API call."
    ),
) -> None:
    """Research ONE holding and write its investment decision brief."""
    symbol = symbol.strip().upper()
    as_of_d = _iso(as_of)
    if not balances.exists():
        raise typer.BadParameter(f"balances file not found: {balances}")

    factory = open_session_factory()
    with session_scope(factory) as session:
        policy = load_policy(policy_path)
        try:
            holding = _gather(
                session, symbol, as_of_d, balances, policy, _commit(), want_payload=True
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

    if show_payload:
        typer.echo(holding.payload.as_prompt_json())
        typer.echo(f"\npayload_hash: {holding.payload.content_hash()}", err=True)
        return

    settings, store = _research_context(no_llm)
    if no_llm:
        typer.echo("--no-llm: no research performed")
        return

    outcome = _research_one(holding, settings=settings, store=store, refresh=refresh_research)
    stamp = out_dir / as_of_d.isoformat()
    brief_path = _write_brief(stamp, holding, outcome, as_of_d)
    typer.echo(f"brief:    {brief_path}")
    if outcome.available and outcome.catalogue is not None:
        typer.echo(
            f"sources:  {len(outcome.catalogue.sources)} "
            f"({', '.join(f'{k} {v}' for k, v in outcome.catalogue.quality_mix().items())})"
        )
    _echo_research_summary([outcome])


@app.command("portfolio")
def portfolio(
    as_of: str = typer.Option(..., "--as-of", help="ISO date"),
    balances: Path = typer.Option(DEFAULT_BALANCES, "--balances"),
    out_dir: Path = typer.Option(Path("data/product_reports"), "--out-dir"),
    policy_path: Path = typer.Option(DEFAULT_POLICY_PATH, "--policy"),
    with_research: bool = typer.Option(
        False, "--with-research", help="Add per-holding briefs and the portfolio synthesis."
    ),
    no_llm: bool = typer.Option(False, "--no-llm", help="Hard override: never call OpenAI."),
    refresh_research: bool = typer.Option(False, "--refresh-research"),
    max_holdings: int = typer.Option(
        0, "--max-holdings", help="Research at most N holdings (0 = all). Cost control."
    ),
) -> None:
    """Evaluate EVERY holding and build the portfolio command centre."""
    as_of_d = _iso(as_of)
    symbols = [r["symbol"].strip().upper() for r in _csv.DictReader(balances.open())]
    commit = _commit()
    want_research = with_research and not no_llm

    factory = open_session_factory()
    holdings: list[_Holding] = []
    rows = []
    latest_price = None
    stamp = out_dir / as_of_d.isoformat()

    with session_scope(factory) as session:
        policy = load_policy(policy_path)
        for sym in symbols:
            try:
                h = _gather(
                    session, sym, as_of_d, balances, policy, commit, want_payload=want_research
                )
            except Exception as exc:  # noqa: BLE001 - one bad holding must not stop the run
                typer.echo(f"  {sym}: SKIPPED ({type(exc).__name__}: {exc})")
                continue
            if h.pos.price_date and (latest_price is None or h.pos.price_date > latest_price):
                latest_price = h.pos.price_date
            rows.append(summarise(sym, h.pos, h.evidence, h.verdicts, h.stale))
            holdings.append(h)

    for h in holdings:
        _write_deterministic(stamp, h, as_of_d)

    stamp.mkdir(parents=True, exist_ok=True)
    summary = stamp / "PORTFOLIO.md"
    summary.write_text(
        render_portfolio(
            rows,
            {
                "as_of": as_of_d.isoformat(),
                "commit": commit,
                "latest_price": latest_price.isoformat() if latest_price else "unavailable",
            },
        )
    )
    typer.echo(f"holdings evaluated: {len(rows)}")
    typer.echo(f"portfolio summary : {summary}")
    typer.echo(f"individual reports: {stamp}/<TICKER>/")

    if not want_research:
        return

    from mip.research_assistant.render import render_portfolio_research
    from mip.research_assistant.research import run_portfolio_synthesis, summarise_for_portfolio

    settings, store = _research_context(no_llm)
    targets = holdings[:max_holdings] if max_holdings > 0 else holdings
    if max_holdings > 0:
        typer.echo(f"researching {len(targets)} of {len(holdings)} holdings (--max-holdings)")

    outcomes = []
    summaries = []
    for h in targets:
        typer.echo(f"  researching {h.symbol} ...")
        outcome = _research_one(h, settings=settings, store=store, refresh=refresh_research)
        _write_brief(stamp, h, outcome, as_of_d)
        outcomes.append(outcome)
        summaries.append(summarise_for_portfolio(outcome, h.payload))

    _echo_research_summary(outcomes)

    result, usage, error = run_portfolio_synthesis(
        as_of_d, summaries, settings=settings, store=store
    )
    research_path = stamp / "PORTFOLIO_RESEARCH.md"
    research_path.write_text(
        render_portfolio_research(result, as_of_d.isoformat(), {"commit": commit}, error=error)
    )
    typer.echo(f"portfolio research: {research_path}")
    if usage is not None:
        typer.echo(f"synthesis usage   : {_usage_summary([usage])}")
    if error:
        typer.echo(f"synthesis         : UNAVAILABLE ({error})")
