# Final Architecture Review — Before Phase 2 Implementation

**Reviewer stance:** adversarial. The burden of proof is on *change*, not on the
status quo — but previous decisions are not protected. Every correction below is
additive; **no redesign is recommended.** Grounded in the live schema
(`src/mip/domain/models.py`), the Phase 1 delivery, the Phase 2 design
([PHASE2_DESIGN.md](PHASE2_DESIGN.md)), and the existing experiment registry
(`src/mip/research/experiments/registry.py`).

---

## Executive Verdict

**APPROVED WITH MINOR CORRECTIONS.**

The foundational decisions are correct and, in several cases, better than a
platform at this stage usually gets: a permanent non-ticker `security_id`,
immutable checksummed snapshots, a vendor-independent adapter Protocol with a
`blocked_source()` discipline, versioned immutable universe definitions, and a
*definition-level experiment registry* that already encodes hypotheses, null
hypotheses, machine-readable promotion criteria, lifecycle/role separation, and
overlap priors for multiple-comparison awareness. None of these needs rework.

There is exactly one architectural risk large enough to matter over a decade,
and it is a **scope-boundary** risk in Phase 2, not a design error in Phase 1.
It is correctable in days, additively, before implementation — so it does not
justify delaying Phase 2, only amending its scope contract.

---

## Primary Question — the single greatest remaining architectural risk

> **Phase 2 as designed cleans only one side of the regression.**

A stock-selection study is `rank(signal at as_of)` vs `forward return`. Phase 2
makes the **right-hand side** (outcomes) survivorship-clean, delisting-aware,
point-in-time, and keyed on `security_id`. But the **left-hand side** — the
signals — is produced by the nine registered models, which compute features from
`feature_store_daily` (**keyed on the legacy `instruments.id`**) over the
**survivor-biased yfinance price history**. `ExperimentSpec.required_data_sources`
for every model points at those legacy sources.

So after Phase 2 ships exactly as designed, the platform still **cannot produce
a single fully-clean study**: any research join marries clean `security_id`
outcomes to survivor-biased, legacy-identity signals *across the
`instrument_security_map` bridge* — and that bridge is precisely where
survivorship bias and identity ambiguity re-enter. The Phase 2 doc even labels
the bridge "reconciliation only," which understates that it is the load-bearing
seam of every future study.

Why this is *the* risk and not a lesser one:

- It defeats the stated purpose. The reason to build Phase 2 is to answer "does
  signal X have genuine OOS selection value." A half-clean pipeline cannot answer
  it cleanly — you would spend the engineering and still owe an asterisk on every
  result.
- It is silent. Nothing in the design *prevents* a researcher from joining
  `feature_store_daily` to `research_observation` and calling the result clean.
  The most dangerous failure is the one that looks like success.
- It compounds. Ten years of studies built on that seam inherit the bias; the
  registry would accumulate "validated" signals whose validation was confounded.

This is a **scope and guardrail** problem, not a foundations problem — which is
why the verdict is *minor corrections*, not *significant concerns*.

---

## Stage 1 — Major decisions, judged

| Decision | Correct? | Over-complex? | Too rigid? | Scales? | Key assumption / breaker |
|---|---|---|---|---|---|
| Permanent `security_id` (never ticker) | **Yes** | No | No | Yes | Assumes identity is monotonic; retroactive vendor "these two were always one entity" needs a merge-with-history flow (today: quarantine only) |
| Point-in-time security master | **Yes** | No | No | Yes | Sound |
| Research universe (versioned, immutable) | **Yes** | No | Slightly (version bump per rule change — intended) | Yes | Fine |
| Phase separation (identity → outcomes → …) | **Yes** | No | No | Yes | Correct *except* it left signals/features in an earlier, dirty world (the primary risk) |
| Canonical outcome model (raw + adj + factor) | **Yes** | No | No | Yes | Raw retained ⇒ adjustment policy reproducible |
| Provider strategy (Norgate + Sharadar, cross-checked) | **Yes** | No | No | Yes | Assumes two affordable survivorship-free sources remain available/licensable |
| Adapter Protocol + `blocked_source()` | **Yes** | No | No | Yes | Equity-shaped DTOs; multi-asset needs generalization later |
| Validation methodology (walk-forward, blocks, embargo, gates) | **Yes** | No | No | Yes | Assumes per-study discipline; no *program-level* FDR ledger yet |
| Research workflow (scratchpad drivers → reports) | **Partly** | No | No | **Weak at scale** | Runs aren't persisted as queryable, input-bound records |
| Experiment framework (definition registry) | **Yes, strong** | No | No | Definitions: yes. **Runs: no** | Registers experiment *definitions*, not *executions* |
| Promotion framework (status/role split, criteria) | **Yes** | No | No | Yes | Good; needs a persisted promotion-decision log |
| Knowledge base (docs + memory) | Adequate | No | No | Manual | Fine for now |
| Research snapshots (immutable, checksummed) | **Yes** | No | No | **Storage watch** | Full-universe materialization × thousands of snapshots ⇒ dedup/content-addressing needed |
| Versioning (data_version + definition version) | **Yes** | No | No | Yes | Sound; extend it to *signal* version in the run store |

Nothing here is over-engineered. The rigidities that exist (version-bump-to-change
rules, immutable registry rows) are the *good* kind — they protect
reproducibility.

---

## Stage 2 — Ten-Year Thought Experiment

**Becomes a liability:**
1. **Legacy `instruments.id` as production identity.** Ten years of
   features/predictions/portfolio keyed on the survivor-biased current-symbol id,
   diverging from the clean `security_id` research world. Eventually forces a
   migration; the longer it waits, the larger it grows.
2. **Code-only, definition-level experiment registry + scratchpad run workflow.**
   At "thousands of experiments, multiple researchers," a Python tuple of specs
   and a folder of `REPORT.md` files cannot answer "show every run of signal X on
   universe v3 / data v7" or "how many hypotheses have we tested" — comparison and
   false-discovery accounting break down.
3. **Full-universe snapshot copies.** Without content-addressed dedup, a decade of
   snapshots is a storage and governance burden.

**Remains excellent:** permanent `security_id`; immutable checksummed snapshots;
adapter Protocol + blocked-source honesty; versioned universe definitions;
definition-level registry with promotion criteria and overlap priors; the DQ
quarantine ledger; raw-price retention.

---

## Stage 3 — Assumptions challenged (what if each is wrong?)

- **"Signals can stay in the legacy world while outcomes go clean."** *Wrong.* If
  the signal is survivor-biased, a clean-outcome study is still confounded — the
  primary risk. Simpler correct design: compute the first study's signals from the
  same clean price series inside the snapshot.
- **"The instrument↔security bridge is reconciliation-only."** *Wrong.* It is the
  seam every study crosses; it must be PIT-correct and tested, or it silently
  reintroduces the bias Phase 1/2 removed.
- **"Definition-level registry = experiment governance."** *Partly wrong.* It
  governs *what* experiments exist; it does not record *executions* bound to their
  inputs, so reproducibility-audit, comparison, and FDR are not yet supported at
  program scale.
- **"Permanent identity never needs correction."** *Mostly right, edge exists.*
  Vendors sometimes reveal two ids were one entity; today that path is quarantine,
  not a history-preserving merge. Acceptable now; name it as future work.
- **"USD single-currency / equity DTOs generalize."** *Right but latent.* The
  `security_id` model generalizes to any asset; the *DTOs and outcome semantics*
  are equity-shaped. Fine until multi-asset, then extend (not redesign).
- **"Snapshots must materialize the full universe each time."** *Not necessarily.*
  Content-addressing / dedup achieves the same reproducibility at far less cost.

No assumption failure implies a redesign. Each has an additive fix.

---

## Stage 4 — Missing subsystems (genuinely absent)

1. **Experiment-RUN / results registry (execution-level).** The definition
   registry exists; a persisted, queryable store of *runs* — each bound to
   `(experiment_id, signal_version, universe_definition_version,
   research_snapshot_checksum, data_version, code_git_sha)` → metrics + verdict —
   does not. This is the anchor for reproducibility audit, experiment comparison,
   and program-level **multiple-testing / false-discovery accounting**. Cheap to
   seed now (a table + FKs to `research_snapshot`); near-impossible to retrofit
   over thousands of past runs.
2. **A named path to a survivorship-clean, `security_id`-keyed feature/signal
   layer** (the left-hand-side fix). Does not have to be *built* in Phase 2, but
   must be *declared* and *guard-railed* so no confounded study is run in the interim.
3. **Persisted promotion-decision log.** The framework models promotion; the
   decision events themselves should be immutable records (who/when/against which
   run), not just a status field.
4. **Program-level FDR / multiple-comparison ledger.** Overlap priors handle
   *model* redundancy; nothing yet counts *hypotheses tested* across the research
   program. At decade scale this is the dominant statistical threat to integrity.
5. **Model/signal drift monitoring** for `MONITORING`-status production components
   (detecting decay of a promoted signal). Lower priority; note it.

Partially present, adequate for now: lineage (`ingestion_run_id` + `data_version`
everywhere), data-quality governance (`data_quality_issues` + Phase 1 checks),
dataset registry (`research_snapshot` is close — needs a cross-snapshot catalog),
auditability (immutable predictions + snapshots).

---

## Stage 5 — Future evolution

| Direction | Naturally supported? | Note |
|---|---|---|
| Portfolio construction | **Yes** | `Portfolio/Transaction/Lot/LotClosure` tables already exist |
| Risk / factor models | **Yes (extensible)** | `security_id` + planned residual-return column; add factor tables later |
| Factor research | **Yes** | Snapshot + relative/residual returns are the right substrate |
| Alternative data | **Yes, by design** | New `InformationFamily` + new PIT ingestion + adapter; registry anticipates this ("a new information family needs new PIT data, not merely a registry entry") |
| Options research | Extend | New outcome semantics + DTOs; identity model already accommodates |
| International equities | Extend | `security_id` generalizes; DTOs/calendars/currency need widening |
| Fixed income | Extend | Same identity spine; different outcome model |
| Multi-asset forecasting | Extend | Foundations (permanent id, snapshots, registry) carry over; outcome/DTO layer generalizes |

The permanent-identity + adapter + snapshot + registry spine is the reason
expansion is *extension*, not *rework*. That is the architecture's biggest
long-term asset.

---

## Architecture Risk Register (ranked)

| # | Risk | Severity | Likelihood | 10-yr impact | Ease of correction | Fix window |
|---|---|---|---|---|---|---|
| R1 | **Half-clean pipeline**: clean outcomes joined to survivor-biased, legacy-identity signals across the bridge | **High** | **High** (default path) | High — confounds every study | **Easy** (scope contract + guardrail) | **Before Phase 2** |
| R2 | `instrument_security_map` treated as "reconciliation-only" rather than a tested, PIT-correct seam | High | High | High | Easy (elevate + test) | **Before Phase 2** |
| R3 | No execution-level experiment-run/results store → no comparison/FDR/repro-audit at scale | High | High (at scale) | High | Medium now / Hard later | **Seed schema before Phase 2** |
| R4 | Legacy `instruments.id` remains production identity indefinitely | Medium | High | Medium-High | Hard (migration) | Named Phase 3+ |
| R5 | Snapshot storage: full-universe copies × thousands | Medium | Medium | Medium | Easy (content-address) | Design guidance in Phase 2 |
| R6 | No program-level FDR ledger (only model-level overlap priors) | Medium | Medium | High | Medium | With R3 |
| R7 | Identity-merge correction path is quarantine-only | Low | Low | Low-Med | Medium | Future |
| R8 | Equity-shaped DTOs/single-currency assumptions | Low | Medium (if multi-asset) | Medium | Medium | When needed |
| R9 | No drift monitoring for promoted signals | Low | Medium | Medium | Medium | Post-first-promotion |

---

## Recommended Corrections (only what belongs *before* Phase 2)

All additive; none is a redesign. Estimated total ≈ **2–4 engineering days** of
schema/scope work folded into the existing Phase 2 plan.

1. **Amend the Phase 2 scope contract to close the left-hand side (R1).** Declare
   that the first validation study consumes **only signals recomputable from the
   clean `security_price_daily` / return series on the `security_id` universe**
   (the price-derived models — momentum, relative strength, sector rotation, etc.
   — qualify). Add a **guardrail** that refuses to run a study joining
   `feature_store_daily` (legacy identity) to `research_observation`. Name the
   full feature-store migration to `security_id` as **Phase 3**, explicitly out of
   Phase 2 scope but blocked-flagged like the vendor.
2. **Elevate `instrument_security_map` to a first-class, PIT-correct, tested
   bridge (R2)** with the same validity-interval + as-of semantics as Phase 1
   identity, and DQ checks for one-to-many / temporal-overlap violations. Drop the
   "reconciliation only" framing.
3. **Seed the execution-level experiment-run store now (R3/R6).** A single table
   (`experiment_run`) bound by FK to `research_snapshot` and by value to
   `(experiment_id, signal_version, universe_definition_version, data_version,
   code_git_sha)` → metrics + verdict, plus a nascent hypothesis-count field for
   later FDR. Building it *later* means losing the provenance of every run made in
   between; building the empty schema now costs a day.
4. **Record snapshot-storage guidance (R5):** content-address / dedup identical
   observation blocks so a decade of snapshots does not become a decade of copies.

Deferred by design (do **not** do before Phase 2): feature-store re-keying (R4,
Phase 3), multi-asset DTOs (R8), identity-merge flow (R7), drift monitoring (R9).

---

## Final Recommendation

**Yes — begin Phase 2 implementation tomorrow, with corrections 1–3 folded into
its first commit.**

The foundations earn a decade of confidence: permanent identity, immutable
reproducible snapshots, honest vendor discipline, versioned universes, and a
genuinely good experiment/promotion registry. None of that should be reopened —
reopening it would be exactly the churn this review is meant to prevent.

The single real risk (R1/R2) is that Phase 2, by cleaning outcomes only, would
ship a pipeline that *looks* clean end-to-end but is not, with the identity
bridge as the silent fault line. That is not a reason to delay Phase 2 — it is a
reason to spend two to four days making Phase 2's **scope boundary explicit and
guard-railed**, and to seed the experiment-run store before thousands of
un-provenanced runs accrue. Do those three things and Phase 2 is not only safe to
build — it becomes the piece that finally lets this platform answer its founding
question without an asterisk.
