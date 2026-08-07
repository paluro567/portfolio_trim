# P0-01 — Commit Plan (Part 4)

**Status: PREPARED, NOT EXECUTED.** The Part 5 baseline gate failed; Part 6 forbids committing until it passes.
Branch `v6-closure` already exists and is the dedicated implementation branch — no new branch is required.
No push. No merge. No amend or squash of the six existing commits.

## Commit series — smallest coherent set

### c1 · Scientific record: adversarial and external review
**Purpose:** land the three challenge documents that stress-tested the V6 closure.
**Files (3):** `docs/v6/V6_RED_TEAM_REVIEW.md` · `docs/v6/V6_SCIENTIFIC_ADJUDICATION.md` · `docs/v6/V6_EXTERNAL_PEER_REVIEW.md`
**Tests before commit:** full suite · manifest verification · secret scan
**Message:**
```
V6: red team, adjudication and external peer review

Three independent challenges to the V6 closure, recorded in full.
The adjudication decomposes the Brier failure into bias, dispersion
and discrimination and attributes 107-132% of the excess to score
dispersion at every horizon.
```
**Rollback:** documentation only; `git revert` is safe and lossless.

### c2 · Scientific record: post-review rebaseline and amendment A-2026-007
**Purpose:** land the corrections the reviews required, plus the frozen product and research boundaries.
**Files (5):** `docs/v6/V6_PEER_REVIEW_REBASELINE.md` · `docs/v6/V6_AMENDMENT_007_PEER_REVIEW.md` · `docs/v6/PRODUCT_EVIDENCE_BOUNDARY.md` · `docs/v6/FUTURE_PREDICTIVE_RESEARCH_GATE.md` · `docs/v6/REVISED_PROGRAM_SEQUENCE.md`
**Tests before commit:** as c1
**Message:**
```
V6: post-peer-review rebaseline and amendment A-2026-007

Narrows or withdraws every claim the peer review found unsupported.
Records the product evidence boundary (no calibrated probabilities,
no directional recommendations, no synthetic confidence) and the
G1-G10 gate on any future predictive study.
```
**Rollback:** documentation only. Reverting would restore unnarrowed claims — revert c2 only together with c1.

### c3 · V4 architecture-conforming engineering specification
**Purpose:** land the specification that maps the frozen architecture onto `src/mip/` under ADR-004 Option B.
**Files (7):** `docs/v4/ADR-004-V4-PHYSICAL-PACKAGING.md` · `ENGINEERING_SPECIFICATION.md` · `REPOSITORY_LAYOUT.md` · `MODULE_SPECIFICATIONS.md` · `IMPLEMENTATION_MILESTONES.md` · `TEST_PLAN.md` · `FROZEN_ARCHITECTURE_CONFORMANCE_MATRIX.md`
**Tests before commit:** as c1, plus canonical consistency check (Part 3)
**Message:**
```
V4: architecture-conforming engineering specification (ADR-004)

Maps the frozen V4 architecture onto the existing single-distribution
repository. Frozen pipeline order, domain names, module numbering
M1-M17, layer numbering L0-L10 and phase numbering P0-P6 are preserved
verbatim. ADR-004 defers multi-distribution packaging and records the
single deviation V-1 with its extraction triggers.
```
**Rollback:** revert removes the implementation blueprint; the frozen architecture set is unaffected.

### c4 · V4 implementation backlog
**Purpose:** land the executable backlog.
**Files (6):** `docs/v4/backlog/{IMPLEMENTATION_BACKLOG,TASK_BREAKDOWN,CRITICAL_PATH,SPRINT_PLAN,RISK_REGISTER,DEVELOPER_PLAYBOOK}.md`
**Tests before commit:** as c1
**Message:**
```
V4: implementation backlog, sprints, critical path and risk register

64 tasks, 115 engineer-days, P0-P4 to the frozen contract. Evidence
(M8, M9) and Forecast (M10) carry no tasks and remain prohibited
until Phase 1 PASS.
```
**Rollback:** documentation only.

### c5 · P0-01 execution record
**Purpose:** land the P0-01 evidence produced by this task.
**Files (4):** `docs/v4/p0/{P0_WORKING_TREE_INVENTORY,P0_SECRET_AND_ARTIFACT_SCAN,P0_BASELINE_TEST_REPORT,P0_COMMIT_PLAN}.md`
**Tests before commit:** as c1
**Message:**
```
P0-01: working tree inventory, secret scan and baseline test report

Records the baseline gate result. ruff and black fail on the current
branch; both were clean at main, so the failures were introduced by
the V6 closure commits. No fix applied - three of the four affected
files are hashed in MANIFEST.sha256 or declared frozen study-scope.
```
**Rollback:** documentation only.

## Excluded from every commit

| Files | Class | Reason |
|---|---|---|
| `docs/v4/_nonconforming_draft/*` (6) | **J** | Contradicts the frozen architecture. Part 1 forbids committing class J. Requires a human decision — see the blocker. |

## Not created

No commit is proposed for source code, tests, backup infrastructure, or manifests. P0-01 changes no source file. Backup infrastructure is **P0-02** and is out of scope for this task.
