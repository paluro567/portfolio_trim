# ADR-004 — V4 Physical Packaging

**Status:** ACCEPTED · **Date:** 2026-08-04 · **Supersedes:** nothing · **Amends:** nothing

## Context

`REPOSITORY_STRUCTURE.md` specifies four package roots — `mip`, `mip_evidence`, `mip_forecast`,
`mip_proto` — and a CI job that runs `pip uninstall mip_evidence mip_forecast`. That job requires the
optional layers to be **separately installable distributions**.

The repository today is a single hatchling distribution (`name = "mip"`, `packages = ["src/mip"]`,
Python ≥3.13) with 20 sub-packages and a green 551-test suite. Phase 1 — the human study that decides
whether the product is wanted at all — has not run.

## Decision

**The frozen architecture is unchanged and remains authoritative.** Multi-distribution packaging remains
the long-term target. **Physical separation into distributions is deferred.**

`mip_evidence`, `mip_forecast` and `mip_proto` are created **now** as separate package roots under
`src/`, exactly as the frozen structure names them, inside the single `mip` distribution. The logical
boundary is created immediately; only the packaging boundary is deferred.

## Why immediate migration is disproportionate before Phase 1

1. **The decision it serves may be cancelled.** A Phase 1 KILL cancels evidence and forecast work
   outright. Splitting distributions to isolate layers that may never be built spends effort on a
   boundary with nothing behind it — `mip_forecast` is dormant and no source has ever reached
   DIRECTIONAL tier.
2. **It buys no property that is unavailable more cheaply.** The property required is P1: `mip` must not
   depend on the optional layers. Directory removal plus import-linter plus AST tests prove that
   mechanically today.
3. **It costs the regression suite.** 551 passing tests and 11 migrations move with a split. That risk
   is unjustified before the product is validated.
4. **The seams are what matter, and they are created now.** Deferring packaging does not defer the
   boundary.

## Risks of remaining in one distribution

| # | Risk | Severity |
|---|---|---|
| R1 | A developer imports `mip_evidence` from `mip/`; it works locally because both roots are on the path | **HIGH** |
| R2 | `pip uninstall` cannot express absence, so the zero-signal job is an approximation | **HIGH** |
| R3 | Optional layers accumulate hard dependencies in the shared `[project].dependencies` | MEDIUM |
| R4 | Shared version number couples release cadence | MEDIUM |
| R5 | Ownership blurs; no packaging boundary signals "different owner" | LOW |
| R6 | Later extraction is harder the longer coupling accrues | MEDIUM |

## Controls (each a merge blocker)

| Control | Mitigates | Mechanism |
|---|---|---|
| C-1 `zero-signal` CI job **physically deletes** `src/mip_evidence/` and `src/mip_forecast/` from the checkout, then runs the suite | R1, R2 | absence, not a flag — import raises `ModuleNotFoundError` |
| C-2 import-linter contracts: `mip` is forbidden from importing `mip_evidence`, `mip_forecast`, `mip_proto` | R1 | `lint-imports` in CI |
| C-3 `tests/invariants/test_ast_boundaries.py` — AST scan of every module under `src/mip/` | R1 | frozen structure §4 |
| C-4 Optional layers' third-party dependencies live in extras `[evidence]`, `[forecast]`, never in `[project].dependencies` | R3 | pyproject review |
| C-5 `mip_proto` importable only from `tests/acceptance/` | R1 | AST test |
| C-6 Protocol-based interfaces: `mip/` declares `EvidenceProvider`/`ForecastProvider` Protocols; optional layers implement them; no concrete import crosses the boundary | R1, R6 | typing + AST |
| C-7 Every new cross-root call site recorded in `FROZEN_ARCHITECTURE_CONFORMANCE_MATRIX.md` | R6 | review |

**C-1 is the load-bearing control.** If it passes, P1 holds regardless of packaging.

## Extraction triggers — any ONE forces the split

| # | Trigger |
|---|---|
| T1 | **Phase 1 PASS and authorization of production V4** |
| T2 | The evidence package begins an independent release cadence |
| T3 | A dependency conflict emerges between core and an optional layer |
| T4 | Separate ownership becomes necessary |
| T5 | Import-boundary enforcement proves insufficient — any C-1/C-2/C-3 escape reaching `main` |
| T6 | Deployment requires independent artifacts |

On any trigger, execute `ENGINEERING_SPECIFICATION.md` §9 (deferred extraction plan). Until then this
ADR governs.

## Consequences

- Frozen architecture: unchanged.
- Frozen pipeline order, domain names, module numbering (M1–M17), layer numbering (L0–L10), phase
  numbering (P0–P6): unchanged.
- The zero-signal contract is enforced by directory absence rather than package uninstallation. This is
  an approximation, and it is recorded as such.
