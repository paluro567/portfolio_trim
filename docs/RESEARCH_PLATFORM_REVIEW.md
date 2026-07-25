# Research Platform — Architecture Review (PROPOSAL, pre-implementation)

**Status:** proposal for review. No implementation until reviewed and frozen.
**Goal:** make the rigorous, pre-registered validation the CPE received a
*reusable default* every future experimental model inherits, so adding a
research idea costs one model + one declarative spec — never bespoke validation
infrastructure — while the scientific standards (PIT, embargo, holdout,
block-bootstrap, calibration, confidence, ablation, pre-registration) become
impossible to skip.

The central observation: **most of this already exists and was proven twice**
(analogue v1, CPE). This is a *consolidation and generalization* of working
code, not a greenfield framework. The risk to manage is over-building — the
standing guardrails (no DSL, no plugin runtime, no generic rule engine) still
hold.

---

## 1. What already exists (the framework is 70% built)

**The universal model seam is already in place.** Any experiment that implements
one method is *already* pluggable into scoring, shadowing, and archival:

```
IntelligenceModel.evaluate(symbol, as_of) -> list[ModelScore]
    → normalize_scores → NormalizedEvidence      (the model-agnostic contract)
    → DecisionEvidenceEngine (SHADOW_MODELS routes shadow aside)
    → predictions.evidence JSONB                 (append-only archive)
```

**Model-agnostic validation assets already shipped** (`mip/validation/`):
- `metrics.py` — `accuracy_and_brier`, `calibration_bins`, `decile_table`,
  `block_bootstrap_delta` (paired combined−baseline CI), `confidence_split`,
  `turnover`. Pure, model-independent.
- `realized.py` — realized forward outcomes from prices only.
- `eligibility.py` — the per-horizon embargo rule (G2/G3), shared once.
- `systems.py::combine_rows(group, models)` — reconstructs any model subset via
  the *production* combiner (`combine_model_evidence` + `assess_trim`).

**Reference discipline already documented:** `docs/VALIDATION_GATES.md` (G1–G10),
`docs/CPE_VALIDATION_PLAN.md` (the pre-registration template), the CPE
`REPORT.md` (the report template).

**What was bespoke (and must be generalized):** the CPE study needed three
scratchpad drivers (`cpe_capture`, `cpe_analyze`, `cpe_ablate`) and a hand-written
report + hand-frozen pre-registration. The analogue study similarly hardcoded
itself into `walkforward.py` (`VARIANTS` dict, `self_check`) and
`systems.py::build_systems` (hardcodes `ANALOGUE`). **These bespoke pieces are
the prototype of the general harness** — the generalization is to promote them to
model-agnostic, registry-driven infrastructure.

**Friction discovered during the CPE build (real technical debt to fix):** a new
model is registered in **four** disconnected places — `models/__init__.ALL_MODELS`,
`models/evidence.KNOWN_MODELS` + `MODEL_NORMALIZERS`, and
`engine/evidence.SHADOW_MODELS` + `OVERLAPPING_PAIRS`. Nothing enforces they agree.
This is exactly what a registry fixes.

---

## 2. Proposed framework — components

Smallest coherent set. Each is grounded in something the CPE study actually did.

### 2.1 Research Registry (`mip/research/experiments/registry.py`)
A single `ExperimentSpec` (frozen dataclass) + an `EXPERIMENTS` list — the single
source of truth. The existing `ALL_MODELS` / `KNOWN_MODELS` / `SHADOW_MODELS` /
`OVERLAPPING_PAIRS` become **derived** from it (backward compatible; fixes §1's
four-place debt). Fields (grounded in the prompt + what validation needs):

- identity: `name`, `version`, `owner`, `date_introduced`
- science: `hypothesis`, `null_hypothesis`, `promotion_criteria` (structured,
  pre-registered thresholds), `model_family`, `information_family`
- wiring: `model_cls` (implements `IntelligenceModel`), `correlation_priors`
  (vs other experiments — replaces the hand-edited `OVERLAPPING_PAIRS` block),
  `horizons`, `required_features` / `required_sources`
- lifecycle: `stage` (enum, §2.2), `status` derived (`stage == PRODUCTION` ⇒
  scored; else shadow)
- optional: `ablation_components` (declared toggles, §2.6),
  `pre_registration_path`, `report_path`

**Not a DSL, not a plugin loader:** experiments are ordinary Python classes
imported and listed. The spec is metadata, not executable configuration.

### 2.2 Experiment Lifecycle (an enum + gates, not a workflow engine)
`PROPOSED → IMPLEMENTED → UNIT_TESTED → SHADOW → VALIDATING → REPORTED →
{PROMOTED→PRODUCTION→MONITORED→RETIRED | REJECTED}`. The stage is a field on the
spec; transitions are guarded (e.g. `SHADOW→PROMOTED` requires a report whose
promotion criteria all pass). `stage` drives whether the model participates in
the official score — replacing the manual `SHADOW_MODELS` set. CPE and analogue
enter at `REJECTED` (validated, not promoted); the seven officials at `PRODUCTION`.

### 2.3 Generalized walk-forward harness (`.../harness.py`)
The model-agnostic generalization of `cpe_capture.py`: given an experiment name +
a `WalkForwardPlan` (grid, targets, window, split), capture the production
baseline models' + the experiment's `NormalizedEvidence` to JSONL, resumable,
with the shared port pattern for universe-pooling models. **Baseline capture is
shared across experiments** (capture the seven officials once per grid; reuse for
every experiment's incremental test) — the key compute-scaling design (§4).
Emits the leakage diagnostic (`eligibility.py`) with a strict `violations==0`
assertion (G3) for every experiment, not just the analogue.

### 2.4 Reconstruction + metrics (`.../evaluate.py`)
Generalizes `cpe_analyze.py`: reconstruct `baseline` / `baseline+experiment` /
`experiment_only` via `combine_rows` (already model-agnostic), join `realized`,
and run the full `metrics.py` suite on the pre-declared design/holdout split.
`systems.py::build_systems` (analogue-hardcoded) is superseded by a generic
`build_systems(frame, experiment_name)`.

### 2.5 Standardized reporting (`.../report.py`)
Generalizes the CPE `REPORT.md` into a template filled from the metrics
artifacts + the spec. Every experiment auto-produces: executive summary,
hypothesis/null, methodology, statistical results, calibration, confidence,
failure strata, ablation, promotion recommendation (criteria checked
mechanically against the pre-registered thresholds), conclusion. Identical shape
regardless of model — so results are comparable across experiments.

### 2.6 Ablation protocol (`.../ablation.py`)
Generalizes `cpe_ablate.py`. An experiment declares `ablation_components`
(named toggles — e.g. the CPE's condition-domain scopes). The harness runs each
variant through the same capture→metrics path. Experiments with no declared
components simply skip ablation (no forced abstraction).

### 2.7 Reproducibility manifest (`.../manifest.py`)
Captured with every validation run: git commit, `ExperimentSpec` snapshot,
`feature_definitions` versions in play, universe.yaml hash, price/data max dates,
validation window + grid + split, random seed, promotion thresholds, harness
version. Written beside the artifacts so any published number regenerates
exactly. Ties into existing `ingestion_runs` / `feature_definitions` versioning.

### 2.8 CLI + pre-registration template
`mip research experiment list|show|validate|report|promote-check <name>`.
`validate` freezes the pre-registration (refuses to run if criteria aren't
declared, and refuses to re-freeze after results exist — enforcing the discipline
the CPE followed by hand).

---

## 3. Integration with the existing system

- **Scoring path unchanged.** The decision/trim/attribution/report/archive chain
  already consumes `NormalizedEvidence` and already excludes `SHADOW_MODELS`.
  The registry only changes *where the shadow set comes from* (derived from
  lifecycle stage). No production scoring behavior changes.
- **Registry derives the existing constants**, so `from mip.models import
  ALL_MODELS` etc. keep working; imports untouched.
- **Validation reuses `mip/validation/` internals** (`metrics`, `realized`,
  `eligibility`, `combine_rows`) — the harness orchestrates them generically
  instead of via per-study scratchpad scripts.
- **Archive/evaluation unchanged**: experiments already archive via
  `predictions.evidence`; the outcome-evaluation framework already scores matured
  predictions.

## 4. Required refactoring (and its risks)

1. **Registry consolidation** (moderate): make `ALL_MODELS`/`KNOWN_MODELS`/
   `SHADOW_MODELS`/`OVERLAPPING_PAIRS` derived from `EXPERIMENTS`. Touches
   `models/__init__`, `models/evidence`, `engine/evidence`. Backward-compatible
   (same values, new source). Fully covered by the existing 682-test suite +
   new registry tests. **Risk:** an import cycle (registry ↔ models); mitigated
   by putting the spec dataclass low and the concrete list high.
2. **Generalize `systems.build_systems` + `walkforward`** (moderate): replace
   analogue-hardcoding with the experiment-name-parameterized versions. The
   analogue study's frozen artifacts must remain reproducible — so the general
   path must reproduce `build_systems`'s numbers on the analogue cache (a
   regression pin).
3. **Baseline-capture sharing** (design, not just refactor): capture the seven
   officials once per grid and reuse across experiments. **Risk:** if a model's
   code changes, cached baseline evidence is stale — the manifest's feature/commit
   versions must gate reuse.
4. **Compute** is the dominant real risk. The CPE walk-forward took ~4.7 h for one
   experiment over ~5k pairs. "Hundreds of experiments" is only tractable with
   shared baseline capture, resumable runs, and per-experiment incremental
   capture — all designed in, but this caps how casually experiments run.

## 5. Risks & anti-goals

- **Over-abstraction / the framework becomes the product.** Mitigation: every
  component maps to something the CPE study actually did; `ExperimentSpec` holds
  only fields a consumer reads; no speculative extension points. **No DSL, no
  plugin runtime, no rule engine** (standing guardrails reaffirmed).
- **"Configuration-driven future families" is only half true — state it plainly.**
  The *validation, reporting, lifecycle, and scoring* layers become config-driven
  (spec + one contract). But a genuinely new **information family** (analyst
  revisions, options, sentiment, credit, news) requires a **new provider +
  ingestion + PIT features** — real data engineering, not configuration. The
  framework makes the *science* reusable, not the data acquisition. Over-promising
  this is the biggest conceptual risk.
- **Rigor-as-default is the actual payoff, and its own risk.** A framework that
  makes experiments *easy* to run also makes bad experiments easy to over-claim.
  Mitigation: bake the guardrails in — pre-registration freeze before results,
  mandatory holdout, sample floors, block-bootstrap-only intervals, strict
  leakage assertion, and mechanical promotion-criteria checking. Rigor must be the
  path of least resistance, not an optional add-on.
- **Registry/stage drift** from real behavior (a model marked PRODUCTION that
  isn't scored, or vice versa). Mitigation: an AST/registry conformance test
  asserting the derived sets equal the registry — the same test style already
  guarding import boundaries.
- **Survivorship and universe bias** (from the CPE) are platform-level and remain;
  the framework should *surface* them in every report's limitations, not pretend
  to solve them.

## 6. Backward compatibility

- Public imports (`ALL_MODELS`, `SHADOW_MODELS`, `KNOWN_MODELS`) preserved as
  derived values. The seven officials + analogue + CPE behave identically.
- The frozen analogue and CPE artifacts stay valid; the general harness must
  reproduce their headline numbers (regression pins) before the old scratchpad
  paths are retired.
- No schema change required initially (experiments still archive via
  `predictions.evidence` JSONB). A first-class `experiments` / `experiment_runs`
  table is a *possible later* addition (registry-in-DB), explicitly out of scope
  for v1 to avoid migration/`REFERENCE_TABLES` coupling.

## 7. Migration of existing experiments

- **Seven officials** → `ExperimentSpec(stage=PRODUCTION)`, exempt from shadow;
  they define the frozen benchmark.
- **Historical analogues** → `ExperimentSpec(stage=REJECTED)`, with its
  pre-registration + RCA + report linked; scratchpad retired once the general
  harness reproduces its numbers.
- **CPE** → `ExperimentSpec(stage=REJECTED)`, linking `CPE_VALIDATION_PLAN.md`
  and `conditional_v1/REPORT.md`; `cpe_capture/analyze/ablate` retired, replaced
  by `mip research experiment validate conditional_probability`.
- Migration is a *documentation + registration* exercise, not a code rewrite of
  the models.

## 8. How future experiments get dramatically easier

**Today (what the CPE cost):** implement the model; hand-write ~600 lines of
capture/analyze/ablate scratchpad; hand-freeze a pre-registration; hand-write the
report; manually wire four registration points.

**With the framework:** implement the model (the *one* `evaluate` contract) +
declare an `ExperimentSpec` (metadata + pre-registered promotion criteria) + run
`mip research experiment validate <name>`. Capture, leakage assertion,
reconstruction, metrics, calibration, confidence, failure strata, ablation,
manifest, and a standardized report are produced automatically. The ~600 lines of
bespoke scaffolding collapse to one spec.

---

## 9. Resolved decisions (FROZEN 2026-07-24)

- **A — Build-alongside.** `mip/research/experiments/` is a new layer that *calls*
  the existing `mip/validation` primitives generically. The analogue-specific
  `walkforward`/`systems` paths stay untouched until the general harness
  reproduces their numbers and they are retired deliberately.
- **B — Additive-first registry.** The registry initially wraps and
  *asserts-equal* against the existing `ALL_MODELS`/`KNOWN_MODELS`/`SHADOW_MODELS`/
  `OVERLAPPING_PAIRS` (a conformance test catches drift). Single-source
  consolidation follows once the harness is proven.
- **C — Module home** `mip/research/experiments/`.
- **D — Code-only registry** for v1 (no DB table, no migration).

## 10. Proposed implementation sequence (each stage gated by tests)

1. **Registry (additive) + conformance test.** `ExperimentSpec`, `EXPERIMENTS`,
   lifecycle enum; assert derived sets equal today's four constants. No behavior
   change. Register the 7 officials (PRODUCTION), analogue + CPE (REJECTED).
2. **Reproducibility manifest.** Pure capture util + tests.
3. **Generalized harness (capture).** Model-agnostic, resumable, shared baseline
   capture, strict leakage assertion. Reproduce the CPE capture as a regression.
4. **Reconstruction + metrics + splits.** Generic `build_systems(frame, name)`;
   reuse `metrics`/`realized`. Reproduce CPE headline numbers as a pin.
5. **Standardized report generator.** Fill the template from artifacts; reproduce
   the CPE report's numbers.
6. **Ablation protocol.** Declared components; reproduce the CPE domain ablation.
7. **CLI + pre-registration enforcement** (`mip research experiment …`).
8. **Migrate CPE + analogue specs; retire the scratchpad drivers** once 3–6 pin
   their numbers.

Gate discipline: each stage lands with tests green (the 682-suite stays green
throughout, since the scoring path is untouched) before the next begins.
