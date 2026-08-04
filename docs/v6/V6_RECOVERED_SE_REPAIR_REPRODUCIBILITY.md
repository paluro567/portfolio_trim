# V6 — Recovered-SE Repair Reproducibility

| Item | Value |
|---|---|
| Harness | `tools/v6/recovered_se_repair.py` (preserved; nothing overwritten) |
| Substrate | `data/validation/analogue_v1/embargoed_revalidation` |
| `merged.csv` | md5 `aa1c82bd1203b17b68a353656bef3ff4`, 51,025 rows |
| Predictions | 7 files, 63,535 lines |
| Models | 7 official (`SHADOW_MODELS` excluded); 6 participate |
| Cohort cells | 3,252 total — 1259 / 1259 / 419 / 178 / 92 / 45 |
| Seed | `SEED_BASE = 20260801` |
| Bootstrap | circular block, per-symbol, block = 4, 1000 draws, **identical indices across all arms** |
| Determinism | no RNG outside the bootstrap; `recover_se` and `combine` are pure |
| Replication fidelity | 2.842e-14 vs archived canonical `baseline` |
| Runtime | 4 s end to end |
| Unit tests | 11 / 11 pass |
| Outputs | `V6_RECOVERED_SE_REPAIR_PAIRED_RESULTS.csv`, `V6_RECOVERED_SE_REPAIR_WEIGHT_DIAGNOSTICS.csv` |

**Nothing overwritten.** `src/` unmodified; all prior V6 artifacts intact; production still contains the defect, pending a separate decision.

**Open:** the working tree is dirty (uncommitted paths at HEAD `1b2aec9f`), so no artifact hash is recorded — a hash over an uncommitted tree binds nothing.
