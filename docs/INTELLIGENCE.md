# Portfolio Intelligence Engine

The synthesis layer: one coherent, explainable research evaluation per
holding, built entirely from evidence the platform already produces.
Interpretation only — no prediction, no features, no ingestion, no new
statistics.

## Where it sits (architecture)

    8 evidence models  ──►  NormalizedEvidence        (the standard evidence
        │                    (per model, per horizon)   interface: name,
        │ one gather pass                               confidence, direction,
        ▼                                               observations,
    DecisionEvidenceEngine.gather()                     uncertainty, explanation)
        │
        ├─► combine_model_evidence  ──►  DecisionEvidence   (official score:
        │        (SHADOW_MODELS excluded)                    shadow evidence
        ▼                                                    routed aside)
    assess_symbol  ──►  TrimAssessment      (frozen trim transformation)
        │
    attribute      ──►  AttributionReport   (exact accounting)
        │
        ▼
    PortfolioIntelligenceEngine  ──►  HoldingIntelligence
        sections · bull/bear theses · key drivers · what changed ·
        unknowns · recommendation · shadow evidence · traceability
        │
        ├─► render_institutional()          (research report)
        ├─► existing decision/trim/report surfaces (unchanged)
        └─► future dashboards / APIs / research interfaces

The prompt-level concepts map onto existing components: `EvidenceResult`
IS `NormalizedEvidence` (unchanged); the aggregation framework IS the
decision engine's correlated meta-analysis (unchanged); the Trim Score
already consumed structured evidence, never raw data — this phase did
not change its algorithm, weights, or thresholds.

## Shadow evidence discipline

`mip.engine.evidence.SHADOW_MODELS` (currently `historical_analogues`,
per its failed out-of-sample validation and the hardened leakage-free
revalidation) is evaluated and reported as information but excluded
from participating evidence, scores, theses, drivers, and
recommendations. `DecisionEvidence.shadow_models` records it; the
validation harness opts out (`shadow=frozenset()`) to preserve its
study semantics. Promotion out of shadow requires passing every gate in
`docs/VALIDATION_GATES.md`.

## Point-in-time correctness

The engine adds no new data access: models are PIT by construction
(hardened, poison-tested), what-changed diffs read only the immutable
prediction archive (strictly earlier as_of), and every statement in the
report is rendered from fields of the intelligence object.

## Adding a future evidence source

Implement the model contract — `name`, `version`,
`evaluate(symbol, as_of) -> list[ModelScore]` (six horizons, honest
neutrals, `ScoreDiagnostics`) — register it in `mip.models.ALL_MODELS`
and `KNOWN_MODELS`, and declare correlation priors if it shares
information with existing models. Everything downstream — decision
combination, trim, attribution, reports, archive, evaluation, and this
engine — consumes it without change. New sources start in
`SHADOW_MODELS` until they pass the validation gates. Planned examples:
Market State Representation, Conditional Historical Outcome Engine,
factor/options/positioning/sentiment research.

## Migration notes (what changed for consumers)

- The official combined score is again a SEVEN-model combination
  (analogue demoted to shadow). Archived predictions record their
  participating sets, so eras remain distinguishable; no reinterpretation
  of old rows.
- `DecisionEvidence` gained `shadow_models` (additive).
- `DecisionEvidenceEngine.gather()` exposes the per-model evidence map
  (used by the intelligence engine; `assess()` behavior unchanged).
- `PredictionRepository.latest_before()` supports what-changed diffs.
- New CLI: `mip report institutional SYMBOL [--portfolio] [--json]`.
- Existing commands, the daily update pipeline, trim formula, thresholds,
  weights, and validation infrastructure are unchanged.
