"""`mip research experiment` — the research-framework CLI.

Workflows over the generalized framework: inspect the registry, verify
conformance, freeze a pre-registration (integrity-protected), run walk-forward
capture (refused without a frozen pre-registration), analyze, ablate, report,
check promotion, and reproduce a run from its manifest. Uses the project's Typer
conventions; adds no second CLI framework.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope
from mip.core.exceptions import ConfigurationError
from mip.research.experiments.evaluate import evaluate
from mip.research.experiments.harness import ModelSet, WalkForwardHarness, monthly_plan
from mip.research.experiments.prereg import PreRegistration, draft_from_spec
from mip.research.experiments.registry import EXPERIMENTS, conformance_report, get_experiment
from mip.research.experiments.report import evaluate_promotion, promotion_recommendation

app = typer.Typer(
    help="Research experiments: registry, validation, reporting.", no_args_is_help=True
)

DEFAULT_ARTIFACTS = Path("data/validation")


def _prereg_path(artifacts: Path, experiment_id: str) -> Path:
    return artifacts / experiment_id / "prereg.json"


@app.command("list")
def list_experiments(json_out: bool = typer.Option(False, "--json")) -> None:
    """List every registered experiment with its lifecycle status and role."""
    rows = [
        {
            "id": s.experiment_id,
            "version": s.version,
            "status": s.status.value,
            "role": s.role.value,
            "model_family": s.model_family.value,
            "information_family": s.information_family.value,
        }
        for s in EXPERIMENTS
    ]
    if json_out:
        typer.echo(json.dumps(rows, indent=2))
        return
    for r in rows:
        typer.echo(
            f"{r['id']:26} v{r['version']}  {r['status']:11} "
            f"{r['role']:10} {r['information_family']}"
        )


@app.command("show")
def show(experiment_id: str, json_out: bool = typer.Option(False, "--json")) -> None:
    """Show one experiment's full declarative record."""
    spec = get_experiment(experiment_id)
    payload = {
        "id": spec.experiment_id,
        "version": spec.version,
        "status": spec.status.value,
        "role": spec.role.value,
        "hypothesis": spec.hypothesis,
        "null_hypothesis": spec.null_hypothesis,
        "model_family": spec.model_family.value,
        "information_family": spec.information_family.value,
        "required_data_sources": list(spec.required_data_sources),
        "overlaps": sorted(spec.overlaps),
        "promotion_criteria": [c.statement for c in spec.promotion_criteria],
        "ablation_dimensions": list(spec.ablation_dimensions),
        "validation_plan_reference": spec.validation_plan_reference,
        "report_reference": spec.report_reference,
        "notes": spec.notes,
        "limitations": spec.limitations,
    }
    typer.echo(json.dumps(payload, indent=2))


@app.command("conformance")
def conformance() -> None:
    """Verify the registry's derived views equal the legacy registration constants."""
    report = conformance_report()
    typer.echo(json.dumps(report["checks"], indent=2))
    if not report["conformant"]:
        raise typer.Exit(1)
    typer.echo("registry conformant with legacy constants.")


@app.command("freeze")
def freeze(
    experiment_id: str,
    start: str = typer.Option(..., help="Scoring window start (YYYY-MM-DD)."),
    end: str = typer.Option(..., help="Scoring window end (YYYY-MM-DD)."),
    holdout_start: str = typer.Option(..., help="Holdout start (YYYY-MM-DD)."),
    artifacts: Path = typer.Option(DEFAULT_ARTIFACTS),
) -> None:
    """Freeze a pre-registration for the experiment (integrity-protected).
    Refuses to overwrite an already-frozen plan."""
    spec = get_experiment(experiment_id)
    path = _prereg_path(artifacts, experiment_id)
    if path.exists() and PreRegistration.load(path).is_frozen:
        raise ConfigurationError(
            f"a frozen pre-registration already exists at {path}; refusing to overwrite"
        )
    prereg = draft_from_spec(spec, (start, end), (holdout_start, end)).freeze(
        datetime.now(UTC).isoformat()
    )
    prereg.save(path)
    typer.echo(f"frozen pre-registration written to {path} (digest {prereg.content_hash[:12]}…)")


@app.command("prereg-check")
def prereg_check(experiment_id: str, artifacts: Path = typer.Option(DEFAULT_ARTIFACTS)) -> None:
    """Verify a frozen pre-registration has not been modified since freezing."""
    prereg = PreRegistration.load(_prereg_path(artifacts, experiment_id))
    prereg.verify_integrity()
    typer.echo(f"pre-registration integrity OK (frozen {prereg.frozen_at}).")


@app.command("capture")
def capture(
    experiment_id: str,
    start: str = typer.Option("2013-01-01"),
    holdout_start: str = typer.Option("2022-01-01"),
    model_set: str = typer.Option("all", help="all | baseline | experiment"),
    artifacts: Path = typer.Option(DEFAULT_ARTIFACTS),
) -> None:
    """Run (or resume) walk-forward capture. REFUSES without a verified frozen
    pre-registration."""
    prereg = PreRegistration.load(_prereg_path(artifacts, experiment_id))
    prereg.verify_integrity()  # frozen + unmodified, else raises
    factory = open_session_factory()
    with session_scope(factory) as session:
        plan = monthly_plan(
            session, experiment_id, date.fromisoformat(start), date.fromisoformat(holdout_start)
        )
    harness = WalkForwardHarness(factory, artifacts)
    stats = harness.capture(plan, ModelSet(model_set))
    typer.echo(json.dumps(stats.to_dict(), indent=2))


@app.command("analyze")
def analyze(
    experiment_id: str,
    holdout_start: str = typer.Option("2022-01-01"),
    artifacts: Path = typer.Option(DEFAULT_ARTIFACTS),
) -> None:
    """Reconstruct systems and compute metrics from captured predictions."""
    factory = open_session_factory()
    predictions = artifacts / experiment_id / "predictions_all.jsonl"
    results = evaluate(factory, predictions, experiment_id, date.fromisoformat(holdout_start))
    out = artifacts / experiment_id / "results.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    typer.echo(f"wrote {out}")


@app.command("promotion")
def promotion(
    experiment_id: str,
    results_file: Path = typer.Option(..., help="results.json from analyze."),
) -> None:
    """Evaluate promotion criteria mechanically against a results file."""
    spec = get_experiment(experiment_id)
    results = json.loads(results_file.read_text())
    criteria = evaluate_promotion(spec, results)
    for c in criteria:
        typer.echo(f"{c.status.value.upper():15} {c.id}: {c.detail}")
    recommend, reason = promotion_recommendation(criteria)
    typer.echo(f"\nrecommendation: {'PROMOTE' if recommend else 'DO NOT PROMOTE'} — {reason}")
    if not recommend:
        raise typer.Exit(1)


@app.command("reproduce")
def reproduce(manifest_file: Path) -> None:
    """Load and validate a reproducibility manifest for a prior run."""
    from mip.research.experiments.manifest import ReproducibilityManifest

    manifest = ReproducibilityManifest.from_dict(json.loads(manifest_file.read_text()))
    manifest.validate()
    typer.echo(f"manifest valid — digest {manifest.digest()}")
    typer.echo(json.dumps(manifest.to_dict(), indent=2, default=str))
