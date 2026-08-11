"""The fundamentals REFERENCE UNIVERSE: comparison distributions only.

These securities exist so that a holding's margin, leverage and valuation
multiples can be placed against economically similar companies. They are NOT
owned, NOT recommended, and NOT part of any portfolio calculation. Portfolio
membership is defined solely by the holdings file; nothing here can create a
position, a weight, or a concentration figure.

Membership is mechanical. For each of the eleven GICS sectors the provider's
sector page supplies its top companies by market weight; those are the members.
No security is chosen by hand and none is chosen for its effect on a
recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass

# Provider taxonomy -> the GICS sector names already used by this repository.
PROVIDER_SECTOR_KEY = {
    "Information Technology": "technology",
    "Financials": "financial-services",
    "Consumer Discretionary": "consumer-cyclical",
    "Consumer Staples": "consumer-defensive",
    "Health Care": "healthcare",
    "Materials": "basic-materials",
    "Energy": "energy",
    "Industrials": "industrials",
    "Real Estate": "real-estate",
    "Utilities": "utilities",
    "Communication Services": "communication-services",
}


@dataclass(frozen=True, slots=True)
class Candidate:
    symbol: str
    name: str
    sector: str


def eligible(symbol: str, name: str) -> tuple[bool, str]:
    """Deterministic eligibility. Reasons are recorded, never silently dropped."""
    s = symbol.strip().upper()
    if not s:
        return False, "empty symbol"
    if not s.isalpha():
        # BRK-B, BF-B and similar: a second share class of a company whose
        # primary line is already a candidate. Keeping both would double-count
        # one business in its own peer distribution.
        return False, "secondary share class or non-common line"
    if len(s) > 5:
        return False, "symbol longer than a US common-stock ticker"
    low = (name or "").lower()
    for token in (" etf", " fund", " trust", " index", "spdr", "ishares", "vanguard"):
        if token in low:
            return False, "fund, trust or index vehicle rather than an operating company"
    for token in ("acquisition corp", "acquisition co"):
        if token in low:
            return False, "blank-cheque acquisition vehicle"
    return True, "eligible"


def collect(limit_per_sector: int = 50) -> tuple[list[Candidate], list[tuple[str, str, str]]]:
    """(members, rejected). Deterministic given the provider's response."""
    import yfinance as yf

    members: list[Candidate] = []
    rejected: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for gics, key in sorted(PROVIDER_SECTOR_KEY.items()):
        try:
            top = yf.Sector(key).top_companies
        except Exception as exc:  # noqa: BLE001 - one bad sector must not stop the build
            rejected.append(("*", gics, f"provider error: {type(exc).__name__}: {exc}"))
            continue
        if top is None or len(top) == 0:
            rejected.append(("*", gics, "provider returned no companies"))
            continue
        for symbol in list(top.index)[:limit_per_sector]:
            sym = str(symbol).strip().upper()
            name = str(top.loc[symbol, "name"]) if "name" in top.columns else ""
            ok, why = eligible(sym, name)
            if not ok:
                rejected.append((sym, gics, why))
                continue
            if sym in seen:
                rejected.append((sym, gics, "already assigned to another sector"))
                continue
            seen.add(sym)
            members.append(Candidate(sym, name, gics))
    return members, rejected
