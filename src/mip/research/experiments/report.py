"""Standardized scientific report generator (Stage 5).

One report shape for every experiment, filled from the ExperimentSpec, the
reproducibility manifest, the generalized results, and (optionally) ablation and
failure analyses. Promotion criteria are evaluated MECHANICALLY against the
results into four honest states — PASS / FAIL / INCONCLUSIVE / NOT_MEASURABLE —
and the recommendation promotes only when EVERY criterion passes. A single
improved standalone metric can never produce a promote recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mip.research.experiments.manifest import ReproducibilityManifest
from mip.research.experiments.registry import ExperimentSpec, PromotionCriterion

_UNMEASURABLE = object()


class CriterionStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"  # measurable in principle, but sample/interval undefined here
    NOT_MEASURABLE = "not_measurable"  # no machine mapping / no data captured for it


@dataclass(frozen=True)
class CriterionResult:
    id: str
    statement: str
    status: CriterionStatus
    observed: float | None
    detail: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "statement": self.statement,
            "status": self.status.value,
            "observed": self.observed,
            "detail": self.detail,
        }


def _holdout(results: dict) -> dict:
    return results.get("splits", {}).get("holdout", {})


def _resolve(results: dict, metric: str | None, horizon: str | None):
    """Map a criterion's metric name onto the generalized results. Returns
    ``_UNMEASURABLE`` when there is no mapping, or a value/None otherwise."""
    if metric is None or horizon is None:
        return _UNMEASURABLE
    h = _holdout(results)
    if metric == "delta_direction_accuracy":
        return h.get("incremental_combined_minus_baseline", {}).get(horizon)  # dict or None
    if metric == "ece":
        return h.get("calibration_experiment", {}).get(horizon, {}).get("ece")
    if metric == "confidence_delta":
        cs = h.get("confidence_experiment", {}).get(horizon, {})
        hi, lo = cs.get("high_confidence_accuracy"), cs.get("low_confidence_accuracy")
        return (hi - lo) if (hi is not None and lo is not None) else None
    return _UNMEASURABLE


def _compare(value: float, comparator: str, threshold: float) -> bool:
    return {
        ">": value > threshold,
        ">=": value >= threshold,
        "<": value < threshold,
        "<=": value <= threshold,
    }[comparator]


def evaluate_criterion(criterion: PromotionCriterion, results: dict) -> CriterionResult:
    resolved = _resolve(results, criterion.metric, criterion.horizon)
    if resolved is _UNMEASURABLE:
        return CriterionResult(
            criterion.id,
            criterion.statement,
            CriterionStatus.NOT_MEASURABLE,
            None,
            "no mechanical mapping / not captured",
        )
    # the CI-lower-bound family compares a bootstrap dict's ci_low
    if criterion.comparator == "ci_low>":
        if (
            not isinstance(resolved, dict)
            or resolved.get("ci_low") is None
            or resolved.get("n", 0) == 0
        ):
            return CriterionResult(
                criterion.id,
                criterion.statement,
                CriterionStatus.INCONCLUSIVE,
                None,
                "no bootstrap interval available",
            )
        ci_low = resolved["ci_low"]
        ok = ci_low > (criterion.threshold or 0.0)
        return CriterionResult(
            criterion.id,
            criterion.statement,
            CriterionStatus.PASS if ok else CriterionStatus.FAIL,
            ci_low,
            f"CI lower bound {ci_low:+.4f} vs threshold {criterion.threshold:+.4f} "
            f"(delta {resolved.get('delta'):+.4f})",
        )
    if resolved is None:
        return CriterionResult(
            criterion.id,
            criterion.statement,
            CriterionStatus.INCONCLUSIVE,
            None,
            "metric undefined (insufficient sample)",
        )
    if criterion.comparator is None or criterion.threshold is None:
        return CriterionResult(
            criterion.id,
            criterion.statement,
            CriterionStatus.NOT_MEASURABLE,
            float(resolved),
            "criterion lacks a comparator/threshold for mechanical evaluation",
        )
    ok = _compare(float(resolved), criterion.comparator, criterion.threshold)
    return CriterionResult(
        criterion.id,
        criterion.statement,
        CriterionStatus.PASS if ok else CriterionStatus.FAIL,
        float(resolved),
        f"observed {float(resolved):+.4f} {criterion.comparator} {criterion.threshold:+.4f}",
    )


def evaluate_promotion(spec: ExperimentSpec, results: dict) -> list[CriterionResult]:
    return [evaluate_criterion(c, results) for c in spec.promotion_criteria]


def promotion_recommendation(criteria: list[CriterionResult]) -> tuple[bool, str]:
    """Promote ONLY if every criterion passes. Any fail/inconclusive/
    not-measurable blocks promotion — a single improved metric never promotes."""
    if not criteria:
        return False, "no promotion criteria declared; cannot promote"
    passed = [c for c in criteria if c.status is CriterionStatus.PASS]
    if len(passed) == len(criteria):
        return True, "all promotion criteria passed"
    blockers = [
        f"{c.id}={c.status.value}" for c in criteria if c.status is not CriterionStatus.PASS
    ]
    return False, "blocked by: " + ", ".join(blockers)


# -- report rendering -----------------------------------------------------------


def _fmt_pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def _per_system_table(results: dict) -> str:
    h = _holdout(results)
    lines = ["| horizon | baseline | combined | experiment | Δhit CI |", "|---|---|---|---|---|"]
    for hz in ("1w", "2w", "1m", "3m", "6m", "1y"):
        ps = h.get("per_system", {}).get(hz, {})
        inc = h.get("incremental_combined_minus_baseline", {}).get(hz, {})
        b = ps.get("baseline", {}).get("direction_accuracy")
        c = ps.get("combined", {}).get("direction_accuracy")
        e = ps.get("experiment_only", {}).get("direction_accuracy")
        ci = (
            f"[{inc['ci_low']:+.4f}, {inc['ci_high']:+.4f}]"
            if inc.get("ci_low") is not None
            else "—"
        )
        lines.append(f"| {hz} | {_fmt_pct(b)} | {_fmt_pct(c)} | {_fmt_pct(e)} | {ci} |")
    return "\n".join(lines)


def _calib_line(h: dict) -> str:
    return " ".join(
        f"{hz}: ECE={h.get('calibration_experiment', {}).get(hz, {}).get('ece')}"
        for hz in ("1w", "2w", "1m", "3m")
    )


def _conf_line(h: dict) -> str:
    parts = []
    for hz in ("1w", "2w", "1m", "3m"):
        cs = h.get("confidence_experiment", {}).get(hz, {})
        parts.append(
            f"{hz}: hi={cs.get('high_confidence_accuracy')} lo={cs.get('low_confidence_accuracy')}"
        )
    return " ".join(parts)


def render_report(
    spec: ExperimentSpec,
    manifest: ReproducibilityManifest,
    results: dict,
    ablation: dict | None = None,
    failure: dict | None = None,
) -> str:
    criteria = evaluate_promotion(spec, results)
    recommend, reason = promotion_recommendation(criteria)
    h = _holdout(results)
    part = results.get("participation", {}).get("1m", {})
    crit_lines = (
        "\n".join(f"- **{c.status.value.upper()}** — {c.statement} ({c.detail})" for c in criteria)
        or "- (no promotion criteria declared)"
    )
    verdict = "PROMOTE" if recommend else "DO NOT PROMOTE — remain " + spec.role.value
    final = "PROMOTE" if recommend else "REMAIN " + spec.role.value.upper()
    identity = (
        f"`{spec.experiment_id}` v{spec.version} — owner {spec.owner}, "
        f"introduced {spec.introduction_date}"
    )
    run_line = (
        f"`{manifest.run_id}` @ {manifest.created_at} — git `{manifest.git_commit}` "
        f"(harness {manifest.harness_version})"
    )
    calib, conf = _calib_line(h), _conf_line(h)
    repro = f"`mip research experiment validate {spec.experiment_id}`"

    return f"""# {spec.display_name} — Research Report (v{spec.version})

## Executive summary
Recommendation: **{verdict}**.
{reason}. Status: `{spec.status.value}`. Model family: {spec.model_family.value};
information family: {spec.information_family.value}.

## Identity
- experiment: {identity}
- run: {run_line}

## Hypothesis
{spec.hypothesis}

## Null hypothesis
{spec.null_hypothesis}

## Methodology
Walk-forward capture ({manifest.walk_forward_schedule}); production baseline =
the seven-model frozen benchmark; experiment evaluated in shadow via the
identical NormalizedEvidence → decision → trim path. Metrics reuse the shipped
validation suite; combined−baseline uses a paired circular block bootstrap
(seed {manifest.random_seeds}).

## Universe & windows
- scoring window: {manifest.scoring_window[0]} … {manifest.scoring_window[1]}
- holdout: {manifest.holdout_window[0]} … {manifest.holdout_window[1]}
- horizons: {", ".join(spec.supported_horizons)}
- universe: {manifest.universe_definition} (hash {manifest.universe_hash})

## Point-in-time safeguards
Every feature/threshold uses data ≤ as_of; forward outcomes truncated at as_of;
per-horizon embargo enforced; capture asserts no evidence resolves after its
scoring date (strict). Data sources: {", ".join(spec.required_data_sources)}.

## Benchmark
Seven-model production ensemble (frozen). The experiment is compared *against*
it, never merged into it while shadow.

## Participation coverage (1m)
cells {part.get("cells")}, neutral {part.get("neutral")}, participation
{_fmt_pct(part.get("participation_rate"))}.

## Standalone & incremental results (holdout)
{_per_system_table(results)}

## Calibration (experiment, holdout)
{calib}

## Confidence (experiment, holdout)
{conf}

## Failure analysis
{failure or "(not supplied)"}

## Ablation results
{ablation or "(not supplied)"}

## Statistical uncertainty
All combined−baseline comparisons carry block-bootstrap 95% CIs (never
independence-assuming intervals); cells below the sample floor are reported as
unresolved.

## Promotion-criteria evaluation (mechanical)
{crit_lines}

## Final recommendation
**{final}** — {reason}.

## Limitations
{spec.limitations or "(none recorded)"}

## Reproduction
Manifest digest `{manifest.digest()}`. Re-run: {repro}
then `... report {spec.experiment_id}` (see docs/RESEARCH_PLATFORM.md).

## Artifact inventory
{chr(10).join(f"- {k}: {v}" for k, v in manifest.artifact_locations.items()) or "- (none recorded)"}
"""
