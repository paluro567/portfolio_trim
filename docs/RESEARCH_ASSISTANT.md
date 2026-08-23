# Research Assistant — the OpenAI qualitative layer

**Status:** implemented, unit-tested against a mocked SDK, and **run live on AMZN**.
**Package:** `src/mip/research_assistant/`

## 1. Why this exists

The deterministic product answers "what does the measured state look like?" very
well and "what is happening at this company?" not at all. Every fact in a
long-form report is derived from price, plus two recent fundamental snapshots.
The strongest positive evidence for a holding can be `ret_21d = +0.3646` — a
number, not a reason.

This layer adds the missing half: current, sourced, qualitative research, and a
synthesis of it against the quantitative evidence. It does **not** attempt to
fix forecasting, survivorship bias, or calibration. Those remain separate,
untouched research tracks (see §9).

## 2. Architecture

```
data/current_holdings.csv ─┐
daily_prices              ─┤
feature_store_daily       ─┼─► mip.product (unchanged) ─► PositionState
company_fundamentals      ─┤                              Evidence[]
earnings_observations     ─┘                              Constraint[]
                                                          HorizonVerdict[]
                                                                │
                                    ┌───────────────────────────┘
                                    ▼
                          payload.build_payload()      ← pure, no I/O
                          the DETERMINISTIC PAYLOAD    ← given fact
                                    │
             ┌──────────────────────┴───────────────────────┐
             ▼                                              ▼
   CALL 1  responses.create                       (cache hit → no call)
     tools=[{"type":"web_search"}]
     include=["web_search_call.action.sources"]
     → prose + url_citation annotations + tool sources
             │
             ▼
   sources.build_catalogue()   ← PYTHON assigns S1..Sn. The model never sees
             │                    a raw URL and never writes one.
             ▼
   CALL 2  responses.parse
     text_format=InvestmentResearchResult   (no tools, no web access)
             │
             ▼
   sources.validate_and_sanitise()  ← citation integrity + probability policy,
             │                         enforced by MUTATING the result
             ▼
   thesis.build_thesis() + diff_thesis()   ← persisted memory, Python-computed diff
             │
             ▼
   render.render_brief()  ← every NUMBER read from PositionState/HorizonVerdict
```

### Why two calls, not one

OpenAI's guidance is explicit that citation annotations come back **empty** when
structured outputs are combined with the web-search tool in a single request.
Empty annotations would leave nothing to validate citations against, which would
defeat the entire integrity model. So call 1 searches and writes prose with live
annotations; call 2 converts that prose into the strict schema.

## 3. Configuration

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | — | Required. Read at call time; never stored, logged or serialised. |
| `OPENAI_MODEL` | `gpt-5.6-terra` | Any Responses-API model with web search + structured outputs. |
| `MIP_OPENAI_ENABLED` | `true` | Master switch. `false` disables every call even with a key. |
| `MIP_OPENAI_MAX_SEARCH_CALLS` | `8` | Cost control. |
| `MIP_OPENAI_RESEARCH_FRESHNESS_HOURS` | `18` | How long cached research stays reusable. |
| `MIP_OPENAI_TIMEOUT_SECONDS` | `300` | Web search is slow; this is per request. |
| `MIP_OPENAI_MAX_OUTPUT_TOKENS` | `16000` | Per call. |
| `MIP_RESEARCH_ROOT` | `data/investment_research` | Artifact store (gitignored). |

### Default model, and why

`gpt-5.6-terra` — a current Responses-API model supporting the built-in
`web_search` tool, structured outputs and strong reasoning, positioned to balance
intelligence against cost. A 53-holding run is ~107 calls, so cost per call
matters. `gpt-5.6-sol` is the higher-capability sibling and is a one-variable
change (`OPENAI_MODEL=gpt-5.6-sol`) when a single holding warrants it. The model
name appears in exactly one place in the source (`config.DEFAULT_MODEL`).

## 4. Secret handling

- The key is read **at call time** by `config.read_api_key()`: environment
  first, then `./.env`. The `.env` fallback exists because that is where the
  rest of the platform is configured and where this document tells you to put
  the key — reading only `os.environ` was a defect, since the key was then
  invisible unless separately exported.
- **Unit tests are isolated from it.** `tests/unit/conftest.py` neutralises the
  `.env` fallback and unsets the variable for every unit test, so a test
  exercising the "no key" path cannot find a real key and make a billable call.
  That happened once during development; the fixture exists so it cannot recur.
- `ResearchSettings` carries only `api_key_present: bool`. There is no field that
  could hold the key, pinned by `test_settings_dataclass_has_no_key_field`.
- The key never enters a prompt, an artifact, `inputs.json`, report metadata, or a
  log line. Pinned by `test_artifact_records_reproducibility_metadata_and_no_secret`
  and `test_payload_never_contains_a_secret`.
- `.env` is now gitignored **and untracked**. `.env.example` holds names only.

> **Outstanding, and yours to decide:** `.env` was tracked in git until this
> change, so a real `MIP_FRED_API_KEY` remains in the history of commit
> `e218503`. Untracking does not remove it. Rotate that key, and rewrite history
> only if you want it gone from the repository permanently.

## 5. CLI

```bash
uv run mip product research --symbol AMZN --as-of 2026-08-21
```
```bash
uv run mip product report --symbol AMZN --as-of 2026-08-21 --with-research
```
```bash
uv run mip product portfolio --as-of 2026-08-21 --with-research --max-holdings 5
```

| Flag | Effect |
|---|---|
| `--with-research` | Opt in. Off by default, because every run costs money. |
| `--no-llm` | Hard override. Beats `--with-research` and any config. |
| `--refresh-research` | Ignore the cache and search the web again. |
| `--research-only` | Write only the brief, skip the long-form report. |
| `--max-holdings N` | Research at most N holdings (portfolio only). |
| `--show-payload` | Print the deterministic payload and make **no** API call. |

`--show-payload` is the cheapest way to see exactly what the model would be told.

## 6. Outputs

| Path | What |
|---|---|
| `<DATE>/<SYM>/<SYM>_<DATE>.md` | Long-form deterministic report — **unchanged**, still the audit artifact |
| `<DATE>/<SYM>/<SYM>_<DATE>_BRIEF.md` | **The primary human-facing product.** A timeframe-first decision brief |
| `<DATE>/<SYM>/<SYM>_<DATE>_RESEARCH_AUDIT.md` | Full research record: every source, every claim, validation, lineage |
| `<DATE>/<SYM>/inputs.json` | Deterministic inputs — unchanged |
| `<DATE>/PORTFOLIO.md` | Deterministic portfolio view — unchanged |
| `<DATE>/PORTFOLIO_RESEARCH.md` | **New.** Cross-position synthesis |
| `data/investment_research/<SYM>/<DATE>/research.json` | Hashed research artifact |
| `data/investment_research/<SYM>/thesis.json` | Persisted thesis + bounded history |

The long-form report keeps its existing filename deliberately: it is pinned by
committed test fixtures, and renaming it would break them for no benefit.

## 6a. The shape of the brief

The brief is organised as **TIMEFRAME → ACTION → CONVICTION → WHY → WHAT
CHANGES IT**, because the question it exists to answer is "what do I do about
this position, and does the answer differ by horizon?".

| Section | Purpose |
|---|---|
| 1. Decision summary | One paragraph, then the **timeframe decision matrix** — five rows, one per horizon |
| 2. Why the signals differ by timeframe | The mechanism: what governs short, medium and long horizons here |
| 3. Current setup | Quantitative / fundamental / market, capped at 4/4/3 bullets |
| 4. Position management | ADD if / HOLD while / TRIM if / EXIT if, ≤3 bullets each |
| 5. Key catalysts | ≤5 dated events, with **watch variables kept separate** |
| 6. What changed | ≤5 bullets, labelled IMPROVED / DETERIORATED / UNCHANGED |
| 7. Key risks and contradictions | Contradictions first, ≤5 total |
| 8. Bull / base / bear | One compact table |
| 9. Top sources | The 5–12 most-cited, not the full catalogue |
| 10. Position and deterministic verdicts | The numbers, unaltered |

**Three things are held apart and never collapsed**, because merging them is
what makes a recommendation unreadable:

* **Security view** — the platform's deterministic reading of the security
  (`POSITIVE` / `CONFLICTED` / …).
* **Action** — the platform's deterministic portfolio decision (`HOLD`).
* **Research interpretation** — `research_bias`, rendered as a prefix
  (`ADD-BIASED HOLD`) meaning the security case is good but something, usually
  sizing, argues against adding.

`_action_label` is pinned by test to **always end with the deterministic action
word**, so an `ADD-BIASED HOLD` can never quietly become an ADD. The bias
annotation is applied only to a HOLD — an ADD that research also likes is not an
"ADD-BIASED ADD".

Two things in the catalyst table come from Python, not the model: the **affected
horizons** (arithmetic on the catalyst date against the horizon windows) and the
**next scheduled earnings date**, which the platform's own event store knows and
the model is often rightly unwilling to assert without a source.

**Length.** Table cells and bullets are truncated to keep the brief scannable;
the untruncated text always survives in the research audit. A hard word cap is
not enforced in tests because prose length is the model's to choose — what is
enforced are the structural caps above. On the live AMZN run the brief came to
~1,800 words before sources against a 800–1,500 target; the overage is the
timeframe matrix (~480 words), which is the section the redesign exists to
create.

## 7. The two policies that make this safe

### Probability policy

This platform measured its own directional models and found they lose to a
constant-50% forecaster at every horizon (`docs/v6/V6_FINAL_SCIENTIFIC_DETERMINATION.md`).
It has not earned the right to emit calibrated probabilities, and neither has a
language model.

| Concept | Allowed? | How it is labelled |
|---|---|---|
| Measured historical frequency supplied in the payload | Yes | `EMPIRICAL_HISTORICAL` — explicitly not a forecast |
| A future validated forecasting model | Reserved | `VALIDATED_MODEL` — **nothing qualifies today** |
| Scenario likelihood from the model | Yes, ordinal only | `QUALITATIVE_LLM` + LOW / MODERATE / HIGH |
| A numeric probability of a market outcome | **No** | — |
| An expected return or probability-weighted value | **No** | — |

Enforcement is in code, not prompt wording: `contracts.numeric_probability_violations`
screens every free-text field for forward-probability phrasing and records
violations in the artifact. It deliberately does **not** flag ordinary business
percentages ("revenue grew 12%", "gross margin 34%") — scrubbing those would gut
legitimate research.

### Citation integrity

**The model never writes a URL.** Python builds the source catalogue from the
web-search tool's own output, assigns IDs `S1..Sn`, and shows the model only
IDs, types, domains, dates and titles. Consequences:

- a fabricated citation is an ID that is not in the catalogue → detected;
- a fabricated URL is structurally impossible → the model has no URL channel;
- a claim marked `FACT` with no valid source is **downgraded to `UNVERIFIED`**
  before rendering, not merely flagged.

`validate_and_sanitise` mutates the result in place, precisely so a caller cannot
accidentally render the unsanitised version.

## 8. Fact vs inference

Every claim carries a `ClaimType`, rendered visibly:

| Type | Rendered as | Requires a source |
|---|---|---|
| `FACT` | plain, with `[S1]` citations | **yes** — enforced |
| `INFERENCE` | `_(inference)_` | no |
| `MODEL_JUDGMENT` | `_(judgment)_` | no |
| `HISTORICAL_STATISTIC` | `_(historical stat)_` | from the payload |
| `UNVERIFIED` | `**_(unverified)_**` | — |

An inference can never be rendered looking like a confirmed fact.

## 9. What this layer does NOT do

It improves current-information coverage, catalyst discovery, fundamental
interpretation, price-action explanation, qualitative scenario analysis,
synthesis, citations and report actionability.

It does **not** address survivorship bias, calibrated return forecasting,
expected-return estimation, historical signal validation, or position
optimisation. Those remain separate tracks, and this work makes no claim about
them. Sharadar / survivorship-clean historical research may be resumed later and
is unrelated to anything here.

## 10. Relationship to PRODUCT_EVIDENCE_BOUNDARY

`docs/v6/PRODUCT_EVIDENCE_BOUNDARY.md` governs what the product may assert. This
layer is built to comply with it, not around it:

| Boundary rule | How this layer complies |
|---|---|
| Prohibited: probabilities, expected returns | Ordinal likelihoods only; enforced by a screening function |
| Prohibited: directional recommendations presented as predictive | `llm_research_view` is qualitative judgment, held separate from the deterministic action, and both are shown |
| Prohibited: composite scores implying edge | No score is produced |
| Required: descriptive evidence labelled descriptive | Every claim carries a `ClaimType` |
| Required: absent directional reliability displayed, not buried | Stated in the Decision block and the Limitations of every brief |
| Catalysts: dates and facts only | `Catalyst.date_is_verified`; unverified dates flagged in the table |

## 11. Failure behaviour

Research is an enhancement, never a precondition. `run_research` **cannot raise**;
every path returns a `ResearchOutcome`.

| Failure | Result |
|---|---|
| No API key / disabled | `DISABLED`, brief explains which variable to set |
| API error, timeout, rate limit | `FAILED`, brief shows the reason |
| Model refusal | `FAILED` with the refusal text |
| Malformed / unparseable structured output | `FAILED`, revalidated before trusting |
| Citation validation finds problems | Research still renders; offending facts downgraded and disclosed |
| Artifact write fails | Research still returned; the failure is recorded |

A failed holding never disappears silently, and the deterministic report is never
affected.

## 12. Caching and cost

The cache key covers symbol, as-of date, **payload hash**, model, prompt version
and schema version. So research is re-run when the numbers change, when a prompt
is edited, or when the schema changes — and reused otherwise, within
`MIP_OPENAI_RESEARCH_FRESHNESS_HOURS`.

Cost observability is reported per run: calls made, cached, failed, token counts,
web-search count and elapsed time. Cost logic never affects correctness.

Rough shape of a full run: 53 holdings × 2 calls + 1 synthesis ≈ 107 calls.
Use `--max-holdings` while calibrating.

## 13. Prompt-injection posture

Retrieved web content is treated as untrusted data. The system prompt states
explicitly that web pages are sources and never instructions, that content
telling the model to change behaviour must be ignored and may be reported as a
quotation, and that no configuration or credential may be discussed. No local
credential, file path or environment value is ever placed in a prompt.

## 14. Versioning

`PROMPT_VERSION` (currently `1.1.1`) and `SCHEMA_VERSION` (currently `1.1.0`)
live in `mip/research_assistant/__init__.py`.
**Bump them whenever prompt text or the schema changes** — they are part of the
cache key and are recorded in every artifact, so a stale cached conclusion cannot
survive a prompt edit.
