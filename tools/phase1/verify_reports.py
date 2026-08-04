#!/usr/bin/env python3
"""Phase 1 factual-integrity verifier.

Recomputes every participant-checkable derived figure from case_facts.py and
checks it against what the frozen packets actually state. Exits non-zero on any
discrepancy.

This is NOT a report generator. The frozen participant packets remain the
authoritative presentation artifacts; this tool only validates them.

Usage:  python3 tools/phase1/verify_reports.py [--verbose]
"""

from __future__ import annotations

import re
import sys
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from case_facts import (  # noqa: E402
    AUTHORED_NARRATIVE,
    CASES,
    MERIDIAN,
    NOT_RECOMPUTABLE,
)

ROOT = Path(__file__).resolve().parents[2]
PART = ROOT / "docs" / "phase1" / "01_participant"
VERBOSE = "--verbose" in sys.argv

failures: list[str] = []
checks = 0
skipped: list[str] = []


def read(case_id: str) -> str:
    return (PART / f"case_{case_id}.md").read_text()


def ok(msg: str) -> None:
    if VERBOSE:
        print(f"    ok      {msg}")


def fail(msg: str) -> None:
    failures.append(msg)
    print(f"    FAIL    {msg}")


def check(label: str, computed: D, stated: D | None, unit: str, tol: D = D("0.05")) -> None:
    """Compare a recomputed value against the value stated in the packet."""
    global checks
    checks += 1
    if stated is None:
        fail(f"{label}: value not found in packet (expected {computed}{unit})")
        return
    delta = abs(computed - stated)
    limit = tol * max(abs(stated), D("0.0001"))
    if delta <= limit:
        ok(f"{label}: {computed:.4f}{unit} == stated {stated}{unit}")
    else:
        fail(f"{label}: computed {computed:.6f}{unit} != stated {stated}{unit} "
             f"(delta {delta:.6f}{unit}, tol {limit:.6f}{unit})")


def find(text: str, pattern: str) -> D | None:
    m = re.search(pattern, text)
    return D(m.group(1).replace(",", "")) if m else None


# ---------------------------------------------------------------------------
print("=" * 72)
print("PHASE 1 FACTUAL-INTEGRITY VERIFIER")
print(f"policy: {MERIDIAN.name}  portfolio ${MERIDIAN.portfolio_value:,}  "
      f"cap {MERIDIAN.hard_cap_pct}%  liquidity limit {MERIDIAN.liquidity_limit_days} days")
print("=" * 72)

for cid, f in CASES.items():
    print(f"\nCASE {cid} — {f.name}")
    t = read(cid)

    # ---- internal consistency of the facts themselves -------------------
    implied_value = f.weight_pct / D("100") * MERIDIAN.portfolio_value
    check("weight vs stated position value", implied_value, f.position_value, " $",
          tol=D("0.01"))

    implied_unreal = f.position_value - f.cost_basis
    check("cost basis + unrealised == position value", implied_unreal, f.unrealised, " $",
          tol=D("0.02"))

    # ---- C5 position as % of ADV ---------------------------------------
    pct_adv = f.position_value / f.adv_20d * D("100")
    stated = find(t, r"Position as % of ADV \| ([\d.]+)%")
    if stated is not None:
        check("C5 position as % of ADV", pct_adv, stated, "%", tol=D("0.06"))

    # ---- C6 days to exit / to trade -------------------------------------
    days_exit = f.position_value / f.adv_20d
    stated_days = find(t, r"full exit is ([\d.]+) days")
    if stated_days is not None:
        check("C6 full exit in days of ADV", days_exit, stated_days, " days", tol=D("0.05"))
    stated_exit_pct = find(t, r"A full exit as % of ADV \| ([\d.]+)%")
    if stated_exit_pct is not None:
        check("C5b full exit as % of ADV", pct_adv, stated_exit_pct, "%", tol=D("0.06"))
    if days_exit > MERIDIAN.liquidity_limit_days and "liquidity" not in t.lower():
        fail(f"liquidity limit breached ({days_exit:.3f} days) but no liquidity claim in packet")

    # ---- C3 deviation from target / move to target ----------------------
    if f.target_pct is not None:
        dev = f.target_pct - f.weight_pct
        stated_dev = find(t, r"([\d.]+)pp (?:below|above)")
        if stated_dev is not None:
            check("C3 deviation from target", abs(dev), stated_dev, "pp", tol=D("0.06"))
        move_val = abs(dev) / D("100") * MERIDIAN.portfolio_value
        stated_move_pct = find(t, r"A move to target as % of ADV \| ([\d.]+)%")
        if stated_move_pct is not None:
            check("C5c move-to-target as % of ADV",
                  move_val / f.adv_20d * D("100"), stated_move_pct, "%", tol=D("0.10"))

    # ---- C1 / C2 excess over the binding limit --------------------------
    excess = None
    if f.mandate == "CAP":
        excess = f.weight_pct - MERIDIAN.hard_cap_pct
        stated_ex = find(t, r"Excess\s+([\d.]+)pp OVER")
        check("C1 excess over hard cap", excess, stated_ex, "pp", tol=D("0.02"))
    elif f.mandate == "BAND":
        ceiling = f.target_pct + MERIDIAN.band_pp
        excess = f.weight_pct - ceiling
        stated_ceil = find(t, r"Band ceiling\s+([\d.]+)%")
        check("C2a band ceiling", ceiling, stated_ceil, "%", tol=D("0.01"))
        stated_ex = find(t, r"Excess\s+([\d.]+)pp above the band ceiling")
        check("C2b excess over band ceiling", excess, stated_ex, "pp", tol=D("0.02"))

    # ---- C4 magnitude in dollars ----------------------------------------
    if excess is not None:
        mag = excess / D("100") * MERIDIAN.portfolio_value
        stated_mag = find(t, r"Reduce by [\d.]+pp of portfolio\s+\(~\$([\d,]+)\)")
        check("C4 magnitude $", mag, stated_mag, " $", tol=D("0.01"))

        # ---- C7 gain realised on the trim ------------------------------
        stated_gain = find(t, r"realises approximately \$([\d,]+)")
        if stated_gain is not None:
            gain_frac = D("1") - (f.cost_basis / f.position_value)
            check("C7 gain realised on trim", mag * gain_frac, stated_gain, " $", tol=D("0.04"))

        # ---- tax budget cross-check -------------------------------------
        stated_budget = find(t, r"against \$([\d,]+) of remaining")
        if stated_budget is not None:
            check("tax budget remaining", MERIDIAN.gains_remaining, stated_budget, " $",
                  tol=D("0.001"))

    # ---- C9-substitute: own concentration contribution -------------------
    w = f.weight_pct / D("100")
    own = w * w
    stated_own = find(t, r"concentration \(weight squared\)\s+([\d.]+)\s+→")
    if stated_own is not None:
        check("C9s own concentration contribution (before)", own, stated_own, "", tol=D("0.02"))
        after_w = (MERIDIAN.hard_cap_pct if f.mandate == "CAP"
                   else (f.target_pct + MERIDIAN.band_pp)) / D("100")
        stated_after = find(t, r"concentration \(weight squared\)\s+[\d.]+\s+→\s+([\d.]+)")
        check("C9s own concentration contribution (after)", after_w * after_w,
              stated_after, "", tol=D("0.02"))

    # ---- prohibited: total portfolio HHI ---------------------------------
    if "Portfolio HHI" in t:
        fail("packet states a total 'Portfolio HHI' — not computable from single-position "
             "facts (Amendment 002 D-02)")
    checks += 1

    # ---- sanity: any stated HHI must exceed the position's own w^2 -------
    for m in re.finditer(r"HHI\s+([\d.]+)", t):
        v = D(m.group(1))
        checks += 1
        if v < own:
            fail(f"stated HHI {v} < this position's own w^2 {own:.4f} — mathematically impossible")

    # ---- catalyst --------------------------------------------------------
    if f.catalyst_days is not None:
        stated_cat = find(t, r"(\d+) calendar days from today")
        check("catalyst days until", D(f.catalyst_days), stated_cat, " days", tol=D("0.001"))

    # ---- what changed ----------------------------------------------------
    stated_prior = find(t, r"Weight ([\d.]+)% →")
    if stated_prior is not None:
        check("prior weight (what changed)", f.prior_weight_pct, stated_prior, "%", tol=D("0.01"))

    # ---- report presence -------------------------------------------------
    checks += 1
    has = "PAGE 2 — POSITION REVIEW" in t
    if has != f.has_report:
        fail(f"report presence mismatch: packet has_report={has}, expected {f.has_report}")
    else:
        ok(f"report presence == {f.has_report}")

    # ---- terminal wealth: fixed text, no invented figures ---------------
    if f.has_report:
        checks += 1
        if "TERMINAL-WEALTH DISCLOSURE" not in t:
            fail("report is missing the TERMINAL-WEALTH DISCLOSURE section")
        elif re.search(r"would have produced [+-][\d.]+%", t):
            fail("terminal-wealth section states an invented empirical figure "
                 "(Amendment 001 A-004 requires the 'not available' text)")
        else:
            ok("terminal-wealth disclosure is the fixed 'not available' text")

    # ---- forecast contribution -------------------------------------------
    if f.has_report and cid != "G":
        checks += 1
        if "FORECAST CONTRIBUTION TO THIS RECOMMENDATION:  0.0" not in t:
            fail("report does not state forecast contribution 0.0")
        else:
            ok("forecast contribution stated as 0.0")

# ---------------------------------------------------------------------------
# CROSS-ARTIFACT AGREEMENT
# ---------------------------------------------------------------------------
print("\nCROSS-ARTIFACT AGREEMENT")

ca_kit = (ROOT / "docs/phase1/03_constraint_author/constraint_author_kit.md").read_text()
ev_kit = (ROOT / "docs/phase1/04_evaluator/evaluator_kit.md").read_text()
mod_kit = (ROOT / "docs/phase1/02_moderator/moderator_kit.md").read_text()

for cid in ["A", "B", "C", "D", "E", "G"]:
    checks += 1
    if f"CASE {cid}" not in ca_kit:
        fail(f"constraint-author kit has no template for case {cid}")
checks += 1
if "CASE F" in ca_kit.split("§4")[-1]:
    fail("constraint-author kit includes Case F (sham) — it must not be evaluated")
else:
    ok("constraint-author kit correctly excludes Case F")

checks += 1
if "Portfolio HHI" in ca_kit or "Portfolio HHI" in ev_kit:
    fail("HHI leaked into constraint-author or evaluator materials")
else:
    ok("no HHI reference in constraint-author or evaluator materials")

checks += 1
order_rows = re.findall(r"\*\*P\d\*\*\s*\|([^\n]+)", mod_kit)
if len(order_rows) != 5:
    fail(f"moderator kit case-order table has {len(order_rows)} rows, expected 5")
else:
    bad = [r for r in order_rows if r.split("|")[0].strip() in ("F", "G")
           or r.split("|")[-1].strip() in ("F", "G")]
    if bad:
        fail("F or G appears in position 1 or 7 of a participant sequence")
    else:
        ok("case order: F and G never in position 1 or 7, 5 rows present")

checks += 1
if "warmup.md" in mod_kit:
    ok("moderator kit references the warm-up sheet")
else:
    fail("moderator kit does not reference warmup.md (Amendment 001 A-001)")

# ---------------------------------------------------------------------------
print("\nNON-RECOMPUTABLE FIGURES (declared, not checked)")
for k, why in NOT_RECOMPUTABLE.items():
    print(f"    SKIP    {k}: {why}")
    skipped.append(k)

print("\nAUTHORED NARRATIVE (not arithmetic, never verified)")
print("    " + ", ".join(sorted(AUTHORED_NARRATIVE)))

# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print(f"checks run: {checks}    failures: {len(failures)}    "
      f"declared non-recomputable: {len(skipped)}")
if failures:
    print("\nFAILURES")
    for x in failures:
        print(f"  - {x}")
    print("=" * 72)
    sys.exit(1)
print("ALL PARTICIPANT-CHECKABLE FIGURES CONSISTENT")
print("=" * 72)
sys.exit(0)
