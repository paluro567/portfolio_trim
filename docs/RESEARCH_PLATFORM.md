# Research Platform

Permanent infrastructure under `mip/research/experiments/` for evaluating
experimental evidence models with the same rigor the Conditional Probability
Engine received. It is a **new layer built alongside** the shipped
`mip/validation` primitives (which it reuses) and **changes no production
scoring behavior**. See `docs/RESEARCH_PLATFORM_REVIEW.md` for the frozen
architecture decisions.

> **Scope, stated honestly:** this framework generalizes *scientific
> evaluation* — capture, reconstruction, metrics, calibration, confidence,
> ablation, reporting, pre-registration, reproducibility. It does **not**
> generalize *data acquisition*. A new information family (options, analyst
> revisions, sentiment, credit, …) still requires point-in-time ingestion and
> feature engineering before an experiment can use it. Adding the experiment is
> config + one model; adding the data is real engineering.

## Architecture

```
ExperimentSpec (registry.py)      the declarative record — single source of truth
   │  model_cls implements IntelligenceModel.evaluate -> ModelScore
   ▼
WalkForwardHarness (harness.py)   capture NormalizedEvidence per (symbol,as_of,horizon,model)
   │  reuses mip.models.normalize_scores + mip.validation.walkforward._row
   ▼
evaluate.py                       reconstruct baseline / experiment / combined
   │  reuses mip.validation.systems.combine_rows + realized + metrics (verbatim)
   ▼
report.py                         standardized report + mechanical promotion evaluation
ablation.py                       per-variant reconstruction (concept-free)
manifest.py / prereg.py           reproducibility + pre-registration integrity
mip/cli/experiment.py             `mip research experiment ...`
```

Every experiment already plugs into scoring, shadow routing, and archival through
the existing `IntelligenceModel` → `NormalizedEvidence` → decision-engine seam.
The framework adds the validation/lifecycle/registry layer around it.

## Registry schema (`ExperimentSpec`)

| field | meaning |
|---|---|
| `experiment_id` | unique; must equal `model_cls.name` |
| `display_name`, `version`, `owner`, `introduction_date` | identity |
| `model_cls` | the `IntelligenceModel` implementation |
| `hypothesis`, `null_hypothesis` | the science |
| `model_family`, `information_family` | classification enums |
| `required_data_sources`, `supported_horizons` | inputs |
| `status` (`LifecycleStatus`), `role` (`Role`) | lifecycle vs scoring participation |
| `overlaps` | partner ids sharing information (the correlation-prior declaration) |
| `promotion_criteria` | `PromotionCriterion`s, mechanically evaluable |
| `ablation_dimensions` | declared ablation variants |
| `validation_plan_reference`, `report_reference`, `notes`, `limitations` | record |

`role` governs scoring: `PRODUCTION` components define the official combined
score; `SHADOW` experiments are evaluated and reported but **excluded**. A
production role requires a production status (`promoted`/`monitoring`); a shadow
role forbids one — the structural guard against accidental self-promotion.

## Lifecycle & promotion

`proposed → approved → implemented → shadow → validating → rejected` OR
`→ promoted → monitoring → retired`. An experiment reaches production **only**
through a recorded promotion decision: `promotion_recommendation` promotes iff
**every** criterion `PASS`es (four states: PASS / FAIL / INCONCLUSIVE /
NOT_MEASURABLE). A single improved standalone metric never promotes. Promotion
also requires all `docs/VALIDATION_GATES.md` gates.

## Reproducibility manifest

Records experiment id/version, run id, timestamp, git commit + dirty state,
config hash, dataset/feature versions, universe hash, scoring/holdout windows,
schedule, horizons, seeds, promotion thresholds, code paths, runtime env, and
artifact locations. **Mandatory** fields must carry a real value; **best-effort**
fields (git, DB-derived versions, env) are a real value or an explicit
`Unavailable(reason)` — never a silent `None`. `compatible_with` gates cache
reuse: any `Unavailable` on a compared field ⇒ incompatible (equivalence cannot
be proven), never silently accepted.

## Walk-forward execution

`WalkForwardHarness.capture(plan, model_set)` runs the registry's production
models plus the experiment in shadow, per scoring date, capturing normalized
evidence. Resumable (pair-done markers), de-duplicated, failure-isolated (a
crashing model is recorded and skipped — never conflated with neutral evidence,
never aborts the run), and strictly PIT-checked (`evidence.as_of ≤ scoring date`,
else raises). `ModelSet.BASELINE` captures the shared seven-model baseline once
for reuse; `ModelSet.EXPERIMENT` captures only the experiment. Deterministic
ordering (sorted dates and targets).

## Report interpretation

`render_report` produces one shape for every experiment: executive summary,
identity, hypothesis/null, methodology, universe/windows, PIT safeguards,
benchmark, participation coverage, standalone + incremental results, calibration,
confidence, failure analysis, ablation, uncertainty, **mechanical
promotion-criteria evaluation**, recommendation, limitations, reproduction, and
artifact inventory. The recommendation is `PROMOTE` only when every criterion
passes; otherwise `REMAIN {role}`.

## Ablation authoring

Declare `ablation_dimensions` on the spec. An experiment-specific adapter emits
evidence tagged with a `scope`/`variant` column; the core `analyze_ablation`
groups by that tag and reconstructs each variant with the identical combiner,
realized outcomes, metrics, split, and statistics. **The core knows no domain
concepts** — "market"/"sector"/"company"/"catalyst" live only in the CPE adapter
and its tags.

## CLI commands (`mip research experiment ...`)

`list`, `show <id> [--json]`, `conformance`, `freeze <id> --start --end
--holdout-start`, `prereg-check <id>`, `capture <id> [--model-set]`,
`analyze <id>`, `promotion <id> --results-file`, `reproduce <manifest>`.
`capture` refuses to run without a verified frozen pre-registration.

## Pre-registration

`freeze` stamps a content hash over the scientific fields (hypothesis, metrics,
windows, criteria, biases, assumptions, degrees of freedom, ablations,
limitations). `verify_integrity` recomputes and rejects any post-freeze edit, so
a confirmatory run's plan cannot be silently modified. Re-freezing a frozen plan
is refused.

## Authoring a new experiment

1. Implement an `IntelligenceModel` (`evaluate(symbol, as_of) -> list[ModelScore]`,
   six horizons, honest neutrals, `ScoreDiagnostics`). New models start shadow.
2. Register it in `mip.models.ALL_MODELS` / `KNOWN_MODELS` / `MODEL_NORMALIZERS`
   and (if it shares information) `engine.evidence.OVERLAPPING_PAIRS`, then add an
   `ExperimentSpec` to `EXPERIMENTS` — the conformance test enforces they agree.
3. `freeze` a pre-registration; `capture`; `analyze`; declare + run ablations;
   `report`; check `promotion`. Everything downstream is automatic and
   standardized.

## Migration of legacy experiments (Stage 8)

The seven official models are registered `PRODUCTION`/`monitoring` (the frozen
benchmark). The **historical analogue** and **Conditional Probability Engine**
are registered `REJECTED`/`shadow` — their scientifically accurate final status,
never production — with their full records preserved (hypothesis, null,
validation-plan and report references, key metrics, calibration failure,
inverted-confidence finding, forced-scope ablation conclusion, promotion
criteria). The CPE-specific scratchpad drivers (`cpe_capture/analyze/ablate`)
were never committed to the repository (research scripts live in scratchpad);
they are **superseded** by `mip/research/experiments/*` and the CLI, which
reproduce their outputs exactly (see the reproduction commands). No irreplaceable
research artifact under `data/validation/` is deleted.

**Parity evidence (generalized framework reproduces the CPE conclusions):**
- Capture: harness output byte-identical to direct model calls (24 cells, 0
  mismatches); resume no-op; 0 PIT violations.
- Metrics: `evaluate()` reproduces the archived `results.json` with **0.0**
  maximum absolute difference (1m: baseline 0.4994, combined 0.5060, CPE 0.5531,
  incremental CI [−0.0081, +0.0145]).
- Ablation: `analyze_ablation` reproduces the forced-scope table exactly
  (market-only 0.641 → full conjunction 0.545 — the monotonic decrease showing
  the CPE's edge is era persistence, not conditional skill).
- Promotion: mechanical evaluation reproduces "fail every gate → stay shadow."

## Stage 9 — consolidation decision & technical debt

**Decision: retain the additive registry; do NOT consolidate the legacy
registration constants at this time.** Rationale (correctness over purity, per
the frozen plan):

- Full consolidation would derive `ALL_MODELS` / `KNOWN_MODELS` / `SHADOW_MODELS`
  / `OVERLAPPING_PAIRS` from `EXPERIMENTS`. But `registry.py` imports the model
  **classes** from `mip.models`, so having `mip.models.__init__` /
  `mip.models.evidence` / `mip.engine.evidence` import their constants back from
  the registry creates an **import cycle**. Breaking it requires restructuring
  the model-import graph (registry importing each model module directly) — a
  non-trivial refactor of core scoring modules for zero behavioral gain.
- The **remaining technical debt** is therefore the pre-existing four-place
  registration (`ALL_MODELS`, `KNOWN_MODELS`, `SHADOW_MODELS`,
  `OVERLAPPING_PAIRS`). It is now **drift-protected**: `conformance_report` and
  `test_experiment_registry` assert the registry-derived views equal the legacy
  constants, so any future divergence fails the suite loudly.
- **Rollback:** none required — the additive layer added no dependency to the
  scoring path. If consolidation is later pursued, the conformance test is the
  safety net that proves equivalence before and after.
