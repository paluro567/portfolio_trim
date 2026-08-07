# Vertical Slice — Test Report

## New tests: `tests/unit/test_product_slice.py` — 25 passed

| Area | Tests |
|---|---|
| PositionState construction | frozen, `Decimal`-safe, JSON-serialisable, no `float` in output |
| Missing-input handling | absent price → `None` + explicit `unavailable` entry |
| Evidence-status serialization | round-trips; status and direction preserved |
| Unavailable evidence | must carry a `missing_reason` |
| Directional-view rules | UNAVAILABLE with no evidence · NEUTRAL with no signed evidence · **CONFLICTED surfaces both sides** · POSITIVE/NEGATIVE agreement |
| Confidence caps | `HIGH` absent from the enum · VERY LOW when direction unavailable · LOW on conflict · LOW on missing portfolio input · LOW because all readings are EXPERIMENTAL |
| Action override | **BREACH forces TRIM even with POSITIVE directional evidence** |
| HOLD / ABSTAIN fallback | ABSTAIN when portfolio info missing · HOLD when nothing missing and no breach |
| Elimination trace | every unselected action explained; selected action never in the rejected set |
| Five horizons | all present, in order |
| No probability language | 9 prohibited claim phrases absent (disclaimer sentences excluded from the scan) |
| No predictive score | no "trim score", no `/100`, "No item is VALIDATED" present |
| Unavailable-section rendering | renders explicitly with its reason |
| Deterministic report | two renders byte-identical |
| Required sections | 15 headings asserted present |
| Archived provenance | bundle has meta/position/constraints/evidence/verdicts; commit + balances sha256 present; 5 verdicts; every status in the legal set |

## Suite and gates

| Check | Command | Result |
|---|---|---|
| Full regression suite | `uv run python -m pytest -q` | **576 passed, 252 skipped** (551 baseline + 25 new; **no test removed or weakened**) |
| Lint | `uv run ruff check .` | **exit 0 — All checks passed** |
| Format | `uv run black --check src tests` | **exit 0** |
| Determinism (end-to-end) | regenerate report, compare sha256 | **identical** |
| Invalid date | `--as-of not-a-date` | clean Typer error |
| Unknown symbol | `--symbol ZZZZ` | `Invalid value: ZZZZ not present in …` |

## Frozen and hashed artifacts

`tools/v6/`, `tools/phase1/` and `tests/test_evidence_recovered_se.py` are lint-excluded and were **not modified**. Their `MANIFEST.sha256` entries still verify.

## Correction made during testing

`test_generated_report_makes_no_probability_claim` initially failed. The cause was the **test**, not the report: the disclosure sentence Part 7 mandates verbatim contains the words "probability of", and the standing disclaimer contains "expected return" while explicitly denying both. The test now strips those two disclaimer sentences before scanning, so it detects *claims* rather than *denials*. The mandated wording was not altered.
