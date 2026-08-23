"""Source capture and citation integrity.

The integrity guarantee rests on one structural decision: **the model never
writes a URL**. Python builds a catalogue from the web-search tool's own output,
assigns each source a deterministic ID (``S1``, ``S2``, ...), and the model may
only reference those IDs. A fabricated citation is therefore an ID that is not
in the catalogue, which is detected here rather than trusted.

Validation is not advisory. A FACT that cannot be traced to a real captured
source is DOWNGRADED to UNVERIFIED before rendering, so an unsupported
assertion can never reach the report wearing the authority of a fact.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel

from mip.research_assistant.contracts import (
    Claim,
    ClaimType,
    SourceType,
    numeric_probability_violations,
)

# Any URL-looking string emitted by the model is a policy violation: URLs are
# Python's to own. Detected, reported, and stripped from rendered text.
_URL_RE = re.compile(r"https?://\S+|\bwww\.\S+\.\S+", re.I)

_ID_RE = re.compile(r"^S\d+$")

# Domain -> source type. Ordered checks; first match wins.
_DOMAIN_RULES: tuple[tuple[tuple[str, ...], SourceType], ...] = (
    (("sec.gov",), SourceType.SEC_FILING),
    (
        (
            "federalreserve.gov",
            "bls.gov",
            "bea.gov",
            "treasury.gov",
            "census.gov",
            "stlouisfed.org",
            "ecb.europa.eu",
            "eia.gov",
            "fda.gov",
            "ftc.gov",
            "justice.gov",
            "europa.eu",
        ),
        SourceType.GOVERNMENT,
    ),
    (
        ("reuters.com", "apnews.com", "prnewswire.com", "businesswire.com", "globenewswire.com"),
        SourceType.WIRE_NEWS,
    ),
    (
        (
            "bloomberg.com",
            "wsj.com",
            "ft.com",
            "cnbc.com",
            "barrons.com",
            "marketwatch.com",
            "economist.com",
            "nytimes.com",
        ),
        SourceType.FINANCIAL_NEWS,
    ),
    (
        (
            "seekingalpha.com",
            "fool.com",
            "benzinga.com",
            "zacks.com",
            "investing.com",
            "thestreet.com",
            "insidermonkey.com",
            "simplywall.st",
        ),
        SourceType.SECONDARY_COMMENTARY,
    ),
    (
        (
            "techcrunch.com",
            "theinformation.com",
            "semianalysis.com",
            "stratechery.com",
            "arstechnica.com",
            "theverge.com",
            "endpts.com",
            "fiercepharma.com",
        ),
        SourceType.INDUSTRY_PUBLICATION,
    ),
)

# Rank for reporting source-mix quality. Lower is better.
_QUALITY_RANK: dict[SourceType, int] = {
    SourceType.SEC_FILING: 1,
    SourceType.COMPANY_IR: 2,
    SourceType.EARNINGS_CALL: 3,
    SourceType.GOVERNMENT: 4,
    SourceType.WIRE_NEWS: 5,
    SourceType.FINANCIAL_NEWS: 6,
    SourceType.INDUSTRY_PUBLICATION: 7,
    SourceType.SECONDARY_COMMENTARY: 8,
    SourceType.UNKNOWN: 9,
}


def classify_domain(url: str) -> tuple[str, SourceType]:
    """(registrable-ish domain, source type). Never raises on a malformed URL."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return "", SourceType.UNKNOWN
    host = host.removeprefix("www.")
    if not host:
        return "", SourceType.UNKNOWN

    path = ""
    try:
        path = (urlparse(url).path or "").lower()
    except ValueError:
        path = ""

    # Investor-relations pages live on the company's own domain; detect by the
    # conventional subdomain or path rather than by maintaining a company list.
    if host.startswith(("investor.", "investors.", "ir.")) or "/investor" in path:
        return host, SourceType.COMPANY_IR

    for domains, kind in _DOMAIN_RULES:
        if any(host == d or host.endswith("." + d) for d in domains):
            return host, kind
    return host, SourceType.UNKNOWN


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    url: str
    title: str | None
    domain: str
    source_type: SourceType
    published_date: str | None
    accessed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "accessed_at": self.accessed_at,
            "domain": self.domain,
            "id": self.id,
            "published_date": self.published_date,
            "source_type": self.source_type.value,
            "title": self.title,
            "url": self.url,
        }


@dataclass(slots=True)
class SourceCatalogue:
    sources: list[Source] = field(default_factory=list)

    def by_id(self, sid: str) -> Source | None:
        return next((s for s in self.sources if s.id == sid), None)

    @property
    def ids(self) -> set[str]:
        return {s.id for s in self.sources}

    def to_list(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.sources]

    def prompt_table(self) -> str:
        """The catalogue exactly as the model sees it. IDs and titles only."""
        if not self.sources:
            return "(no sources were returned by web search)"
        return "\n".join(
            f"{s.id} | {s.source_type.value} | {s.domain} | "
            f"{s.published_date or 'date unknown'} | {s.title or '(untitled)'}"
            for s in self.sources
        )

    def quality_mix(self) -> dict[str, int]:
        mix: dict[str, int] = {}
        for s in self.sources:
            mix[s.source_type.value] = mix.get(s.source_type.value, 0) + 1
        return dict(sorted(mix.items(), key=lambda kv: _QUALITY_RANK[SourceType(kv[0])]))


def build_catalogue(
    raw_sources: list[dict[str, Any]],
    accessed_at: datetime,
) -> SourceCatalogue:
    """Build the catalogue from web-search output.

    ``raw_sources`` are dicts with at least a ``url``; ``title`` and
    ``published_date`` are used when present. Duplicate URLs collapse to one ID
    so a source referenced twice is still one citation.
    """
    stamp = accessed_at.isoformat()
    seen: dict[str, Source] = {}
    ordered: list[Source] = []
    for raw in raw_sources:
        url = (raw.get("url") or "").strip()
        if not url:
            continue
        if url in seen:
            continue
        domain, kind = classify_domain(url)
        source = Source(
            id=f"S{len(ordered) + 1}",
            url=url,
            title=(raw.get("title") or None),
            domain=domain,
            source_type=kind,
            published_date=(raw.get("published_date") or None),
            accessed_at=stamp,
        )
        seen[url] = source
        ordered.append(source)
    return SourceCatalogue(sources=ordered)


# ------------------------------------------------------------------ validation
@dataclass(slots=True)
class ValidationReport:
    unknown_source_ids: list[str] = field(default_factory=list)
    facts_downgraded: list[str] = field(default_factory=list)
    urls_emitted_by_model: list[str] = field(default_factory=list)
    probability_violations: list[str] = field(default_factory=list)
    claims_total: int = 0
    claims_cited: int = 0

    @property
    def ok(self) -> bool:
        """True when nothing had to be rewritten to make the output safe."""
        return not (
            self.unknown_source_ids
            or self.facts_downgraded
            or self.urls_emitted_by_model
            or self.probability_violations
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "claims_cited": self.claims_cited,
            "claims_total": self.claims_total,
            "facts_downgraded": self.facts_downgraded,
            "ok": self.ok,
            "probability_violations": self.probability_violations,
            "unknown_source_ids": self.unknown_source_ids,
            "urls_emitted_by_model": self.urls_emitted_by_model,
        }

    def summary(self) -> str:
        if self.ok:
            return f"{self.claims_cited}/{self.claims_total} claims cited; no violations"
        parts = []
        if self.unknown_source_ids:
            parts.append(f"{len(self.unknown_source_ids)} unknown source ID(s)")
        if self.facts_downgraded:
            parts.append(f"{len(self.facts_downgraded)} fact(s) downgraded to UNVERIFIED")
        if self.urls_emitted_by_model:
            parts.append(f"{len(self.urls_emitted_by_model)} model-authored URL(s) stripped")
        if self.probability_violations:
            parts.append(f"{len(self.probability_violations)} probability-policy violation(s)")
        return "; ".join(parts)


def _iter_models(obj: Any) -> Iterator[BaseModel]:
    if isinstance(obj, BaseModel):
        yield obj
        for name in type(obj).model_fields:
            yield from _iter_models(getattr(obj, name, None))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _iter_models(item)


def validate_and_sanitise(result: BaseModel, catalogue: SourceCatalogue) -> ValidationReport:
    """Enforce citation integrity and the probability policy, IN PLACE.

    Mutating is deliberate: a caller cannot then accidentally render the
    unsanitised object. Returns the report of what had to be corrected.
    """
    report = ValidationReport()
    known = catalogue.ids

    for model in _iter_models(result):
        # -- 1. citation integrity on Claim objects
        if isinstance(model, Claim):
            report.claims_total += 1
            valid = [sid for sid in model.source_ids if sid in known]
            unknown = [sid for sid in model.source_ids if sid not in known]
            if unknown:
                report.unknown_source_ids.extend(unknown)
            model.source_ids = valid
            if valid:
                report.claims_cited += 1
            if model.claim_type is ClaimType.FACT and not valid:
                report.facts_downgraded.append(model.text[:160])
                model.claim_type = ClaimType.UNVERIFIED

        # -- 2. model-authored URLs and forward-probability language in any text
        for name in type(model).model_fields:
            value = getattr(model, name, None)
            if isinstance(value, str):
                cleaned = _scrub_text(value, name, report)
                if cleaned != value:
                    setattr(model, name, cleaned)
            elif isinstance(value, list) and value and all(isinstance(v, str) for v in value):
                setattr(
                    model,
                    name,
                    [_scrub_text(v, name, report) for v in value],
                )

    # Source IDs referenced anywhere else (e.g. Catalyst.source_ids) also checked.
    for model in _iter_models(result):
        raw = getattr(model, "source_ids", None)
        if isinstance(raw, list) and not isinstance(model, Claim):
            valid = [sid for sid in raw if sid in known]
            unknown = [sid for sid in raw if sid not in known]
            if unknown:
                report.unknown_source_ids.extend(unknown)
            model.source_ids = valid

    cited = getattr(result, "cited_source_ids", None)
    if isinstance(cited, list):
        result.cited_source_ids = [sid for sid in cited if sid in known]  # type: ignore[attr-defined]

    report.unknown_source_ids = sorted(set(report.unknown_source_ids))
    report.probability_violations = sorted(set(report.probability_violations))
    return report


def _scrub_text(text: str, field_name: str, report: ValidationReport) -> str:
    for url in _URL_RE.findall(text):
        report.urls_emitted_by_model.append(url)
    cleaned = _URL_RE.sub("[url removed — cite by source ID]", text)

    for violation in numeric_probability_violations(cleaned):
        report.probability_violations.append(f"{field_name}:{violation}")
    return cleaned


def looks_like_source_id(value: str) -> bool:
    return bool(_ID_RE.match(value))
