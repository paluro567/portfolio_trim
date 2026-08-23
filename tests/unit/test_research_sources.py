"""Citation integrity and the probability policy.

These are the two guarantees that let an LLM near an investment report at all:

* a claim presented as FACT is traceable to a source the platform actually
  retrieved, and the model never authors a URL;
* no numeric probability or expected return can reach the reader.

Both are enforced here rather than requested in a prompt, because a prompt is a
request and code is a constraint.
"""

from __future__ import annotations

from datetime import UTC, datetime

from mip.research_assistant.contracts import (
    ClaimType,
    SourceType,
    numeric_probability_violations,
)
from mip.research_assistant.sources import (
    build_catalogue,
    classify_domain,
    validate_and_sanitise,
)
from tests.unit._research_support import claim, make_result

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def _cat(urls):
    return build_catalogue([{"url": u, "title": t} for u, t in urls], NOW)


# --------------------------------------------------------------- the catalogue
def test_ids_are_assigned_by_python_in_order():
    cat = _cat([("https://a.com/1", "A"), ("https://b.com/2", "B")])
    assert [s.id for s in cat.sources] == ["S1", "S2"]


def test_duplicate_urls_collapse_to_one_citation():
    cat = _cat([("https://a.com/1", "A"), ("https://a.com/1", "A again")])
    assert len(cat.sources) == 1


def test_sources_without_a_url_are_dropped():
    cat = build_catalogue([{"url": ""}, {"title": "no url"}, {"url": "https://a.com"}], NOW)
    assert [s.id for s in cat.sources] == ["S1"]


def test_prompt_table_shows_ids_and_titles_but_is_the_only_url_channel():
    cat = _cat([("https://www.sec.gov/f", "10-Q")])
    table = cat.prompt_table()
    assert "S1" in table and "10-Q" in table
    assert "https://" not in table, "the model must not be shown raw URLs to copy"


def test_empty_catalogue_says_so_rather_than_rendering_blank():
    assert "no sources" in build_catalogue([], NOW).prompt_table()


# ------------------------------------------------------------ domain classing
def test_regulatory_and_press_domains_are_ranked():
    assert classify_domain("https://www.sec.gov/x")[1] is SourceType.SEC_FILING
    assert classify_domain("https://www.reuters.com/x")[1] is SourceType.WIRE_NEWS
    assert classify_domain("https://www.bloomberg.com/x")[1] is SourceType.FINANCIAL_NEWS
    assert classify_domain("https://seekingalpha.com/x")[1] is SourceType.SECONDARY_COMMENTARY
    assert classify_domain("https://federalreserve.gov/x")[1] is SourceType.GOVERNMENT


def test_investor_relations_is_detected_by_convention_not_a_company_list():
    assert classify_domain("https://investor.acme.com/news")[1] is SourceType.COMPANY_IR
    assert classify_domain("https://acme.com/investors/results")[1] is SourceType.COMPANY_IR


def test_unknown_domains_are_labelled_not_assumed_good():
    assert classify_domain("https://random-blog.xyz/post")[1] is SourceType.UNKNOWN


def test_malformed_url_does_not_raise():
    assert classify_domain("not a url")[1] is SourceType.UNKNOWN


def test_quality_mix_is_ordered_best_first():
    cat = _cat([("https://seekingalpha.com/a", "x"), ("https://www.sec.gov/b", "y")])
    assert list(cat.quality_mix()) == ["SEC_FILING", "SECONDARY_COMMENTARY"]


# ------------------------------------------------------- citation enforcement
def test_a_fact_citing_an_unknown_source_is_downgraded_to_unverified():
    result = make_result(extra_claim=claim("fabricated", ClaimType.FACT, ["S99"]))
    report = validate_and_sanitise(result, _cat([("https://a.com", "A")]))

    assert "S99" in report.unknown_source_ids
    assert result.recent_developments[0].claim_type is ClaimType.UNVERIFIED
    assert result.recent_developments[0].source_ids == []
    assert not report.ok


def test_a_fact_with_no_source_at_all_is_downgraded():
    result = make_result(extra_claim=claim("unsourced assertion", ClaimType.FACT, []))
    report = validate_and_sanitise(result, _cat([("https://a.com", "A")]))
    assert result.recent_developments[0].claim_type is ClaimType.UNVERIFIED
    assert report.facts_downgraded


def test_a_valid_fact_survives_untouched():
    result = make_result(extra_claim=claim("real fact", ClaimType.FACT, ["S1"]))
    report = validate_and_sanitise(result, _cat([("https://a.com", "A")]))
    assert result.recent_developments[0].claim_type is ClaimType.FACT
    assert result.recent_developments[0].source_ids == ["S1"]
    assert report.claims_cited >= 1


def test_inference_is_allowed_to_be_uncited_and_is_not_downgraded():
    result = make_result()
    validate_and_sanitise(result, _cat([("https://a.com", "A")]))
    likely = result.price_action_analysis.likely_drivers[0]
    assert likely.claim_type is ClaimType.INFERENCE
    assert likely.source_ids == []


def test_model_authored_urls_are_stripped_and_reported():
    result = make_result()
    result.company_summary = "See https://evil.example.com/fake for details."
    report = validate_and_sanitise(result, _cat([("https://a.com", "A")]))

    assert "https://evil.example.com/fake" in report.urls_emitted_by_model
    assert "https://" not in result.company_summary
    assert "[url removed" in result.company_summary


def test_unknown_ids_are_stripped_from_non_claim_objects_too():
    result = make_result()
    result.catalysts[0].source_ids = ["S1", "S42"]
    report = validate_and_sanitise(result, _cat([("https://a.com", "A")]))
    assert result.catalysts[0].source_ids == ["S1"]
    assert "S42" in report.unknown_source_ids


def test_cited_source_ids_summary_is_filtered_to_reality():
    result = make_result()
    result.cited_source_ids = ["S1", "S77"]
    validate_and_sanitise(result, _cat([("https://a.com", "A")]))
    assert result.cited_source_ids == ["S1"]


def test_report_summarises_cleanly_when_nothing_was_wrong():
    result = make_result()
    report = validate_and_sanitise(result, _cat([("https://a.com", "A")]))
    assert report.ok
    assert "no violations" in report.summary()


# ------------------------------------------------------- probability policy
def test_forward_probability_phrasings_are_detected():
    for text in (
        "There is a 63% chance the stock rises.",
        "Probability of a beat is 70%.",
        "the probability of upside is 0.62",
        "expected return of +8.4% over the year",
        "a probability-weighted view suggests",
        "p(up) is elevated",
        "roughly a 2 in 3 chance of a beat",
    ):
        assert numeric_probability_violations(text), text


def test_ordinary_business_percentages_are_not_flagged():
    for text in (
        "Revenue grew 12% year over year.",
        "Gross margin was 34%, up 120 basis points.",
        "The company beat consensus by 3%.",
        "Guidance implies 8% to 10% growth.",
        "The stock fell 4% over 21 sessions.",
        "It sits at the 23rd percentile of its own history.",
    ):
        assert numeric_probability_violations(text) == [], text


def test_probability_language_in_the_result_is_recorded_as_a_violation():
    result = make_result()
    result.base_case.likelihood_rationale = "roughly a 70% chance of this outcome"
    report = validate_and_sanitise(result, _cat([("https://a.com", "A")]))
    assert report.probability_violations
    assert not report.ok


def test_violations_inside_list_fields_are_caught():
    result = make_result()
    result.what_matters_now = ["expected return of +12% next quarter"]
    report = validate_and_sanitise(result, _cat([("https://a.com", "A")]))
    assert any("expected-return" in v for v in report.probability_violations)


def test_empty_text_is_compliant():
    assert numeric_probability_violations("") == []
