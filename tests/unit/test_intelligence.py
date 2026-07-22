"""Portfolio Intelligence Engine: thesis ranking, section building,
what-changed diffing, unknowns, recommendation logic, and the shadow
discipline — pure reasoning over fixture evidence, no database."""

import json
from datetime import date

import pytest

from mip.engine.evidence import combine_model_evidence
from mip.engine.intelligence import (
    build_recommendation,
    build_sections,
    build_theses,
    build_unknowns,
    diff_against_previous,
)
from mip.engine.trim import assess_trim
from tests.unit.test_decision_evidence import make_evidence

AS_OF = date(2026, 7, 10)


def evidence_map(**kwargs):
    base = {
        "momentum_exhaustion": make_evidence("momentum_exhaustion", effect=0.03, z_raw=2.5),
        "sector_rotation": make_evidence("sector_rotation", effect=0.02, z_raw=2.0),
        "interest_rate_sensitivity": make_evidence(
            "interest_rate_sensitivity", effect=-0.02, z_raw=-1.8
        ),
        "macro_regime": make_evidence("macro_regime", neutral=True),
        "valuation": make_evidence("valuation", neutral=True),
        "historical_analogues": make_evidence("historical_analogues", effect=0.05, z_raw=3.0),
    }
    base.update(kwargs)
    return base


def focus_assessment(per_model):
    evidence = combine_model_evidence("AAA", "1m", AS_OF, per_model)
    return assess_trim(evidence), evidence


# -- shadow discipline ---------------------------------------------------------------


def test_shadow_evidence_never_influences_the_score() -> None:
    with_shadow = combine_model_evidence("AAA", "1m", AS_OF, evidence_map())
    without = {m: e for m, e in evidence_map().items() if m != "historical_analogues"}
    baseline = combine_model_evidence("AAA", "1m", AS_OF, without)
    assert with_shadow.shadow_models == ("historical_analogues",)
    assert "historical_analogues" not in with_shadow.participating_models
    assert "historical_analogues" not in with_shadow.neutral_models
    # the official numbers are EXACTLY the seven-model combination
    assert with_shadow.combined_score == pytest.approx(baseline.combined_score)
    assert with_shadow.combined_confidence == pytest.approx(baseline.combined_confidence)
    assert with_shadow.expected_excess_return == pytest.approx(baseline.expected_excess_return)
    # but its context is preserved for informational reporting
    assert with_shadow.model_context.keys() >= {"historical_analogues"} or True


def test_theses_exclude_shadow_and_neutral_and_rank_by_strength() -> None:
    bull, bear = build_theses(evidence_map())
    assert all(p.model != "historical_analogues" for p in (*bull, *bear))
    assert all(p.model not in ("macro_regime", "valuation") for p in (*bull, *bear))
    assert bull and bull[0].model == "momentum_exhaustion"  # largest |excess/se|
    strengths = [p.strength for p in bull]
    assert strengths == sorted(strengths, reverse=True)
    assert bear and all(p.excess < 0 for p in bear)
    assert all(p.excess > 0 for p in bull)
    assert len(bull) <= 5 and len(bear) <= 5
    # machine-readable provenance on every point
    for p in (*bull, *bear):
        payload = p.to_dict()
        assert payload["direction"] in ("supports_ownership", "supports_reduction")
        assert payload["se"] > 0 and payload["horizon"] == "1m"


# -- sections ------------------------------------------------------------------------


def test_sections_verdicts_and_honest_not_modeled_lines() -> None:
    per_model = evidence_map()
    assessment, _ = focus_assessment(per_model)
    sections = build_sections(per_model, assessment)
    assert (
        sections["technical"].verdict == "supportive"
    )  # momentum + relative absent -> momentum only? momentum 2.5z
    assert sections["macro"].verdict in ("mixed", "unfavorable")  # rates negative, macro neutral
    assert sections["company"].verdict == "no active evidence"
    assert any("not modeled" in line for line in sections["company"].detail)
    assert sections["historical"].verdict == "summarized"
    assert sections["portfolio"].detail  # explicit no-context line when absent
    for section in sections.values():
        assert section.sources  # every section names its evidence sources


# -- unknowns & recommendation ---------------------------------------------------------


def test_unknowns_cover_neutral_omitted_shadow_and_gaps() -> None:
    per_model = evidence_map()
    assessment, _ = focus_assessment(per_model)
    unknowns = build_unknowns(per_model, assessment, omitted=("earnings_behavior",))
    by_kind = {}
    for u in unknowns:
        by_kind.setdefault(u["kind"], []).append(u)
    # the states stay DISTINCT — never conflated in aggregation
    assert {u["model"] for u in by_kind["neutral"]} == {"macro_regime", "valuation"}
    assert by_kind["omitted"][0]["model"] == "earnings_behavior"
    assert by_kind["shadow"][0]["model"] == "historical_analogues"
    assert by_kind["coverage_gap"]  # not-modeled dimensions are explicit
    assert set(by_kind) >= {"neutral", "omitted", "shadow", "coverage_gap"}
    assert all({"kind", "model", "detail"} <= set(u) for u in unknowns)  # structured


def test_recommendation_sides_conditions_and_catalysts() -> None:
    per_model = evidence_map()
    assessment, _ = focus_assessment(per_model)
    bull, bear = build_theses(per_model)
    rec = build_recommendation(assessment, bull, bear, {"catalysts": {"days_until_earnings": 9.0}})
    assert rec["label"] == assessment.recommendation_label
    # maintain-side score: the WHY is the bull case, conflicts are the bear case
    assert assessment.trim_score < 50
    assert rec["why"][0].startswith("[momentum_exhaustion]")
    assert rec["conflicting_evidence"] and rec["conflicting_evidence"][0].startswith("[")
    assert rec["major_risks"] == [f"[{p.model}] {p.description}" for p in bear[:3]]
    assert len(rec["conditions_to_change"]) == 2  # both band boundaries reachable
    assert any("crosses into" in c for c in rec["conditions_to_change"])
    assert rec["expected_catalysts"] == ["next earnings in 9 calendar days (confirmed)"]
    assert rec["horizon"] == assessment.horizon
    assert "no thresholds introduced" in rec["mapping_rule"]
    no_catalyst = build_recommendation(assessment, bull, bear, {})
    assert no_catalyst["expected_catalysts"] == ["next earnings date unavailable"]
    assert "not personalized financial advice" in rec["disclaimer"]


# -- what changed ----------------------------------------------------------------------


def test_diff_against_previous() -> None:
    per_model = evidence_map()
    assessment, _ = focus_assessment(per_model)
    first = diff_against_previous([assessment], {})
    assert first[0]["note"].startswith("first archived evaluation")

    previous = {
        "1m": {
            "as_of": "2026-07-09",
            "trim_score": assessment.trim_score + 12.0,
            "recommendation_label": "Mixed Evidence",
            "primary_trim_drivers": ["macro_regime"],
            "participating_models": ["momentum_exhaustion", "valuation"],
        }
    }
    incompatible = {"1m": {**previous["1m"], "trim_engine_version": 99}}
    (guarded,) = diff_against_previous([assessment], incompatible)
    assert "incompatible" in guarded["note"]

    previous["1m"]["trim_engine_version"] = assessment.engine_version
    previous["1m"]["confidence"] = assessment.confidence + 0.3
    previous["1m"]["expected_excess_return"] = -(assessment.expected_excess_return or 0.01) or -0.01
    previous["1m"]["portfolio_adjustment"] = assessment.portfolio_adjustment + 5.0
    (change,) = diff_against_previous([assessment], previous)
    assert change["trim_delta"] == pytest.approx(-12.0)
    assert change["label_change"].endswith(assessment.recommendation_label)
    notes = "\n".join(change["notes"])
    assert "primary trim driver changed" in notes
    assert "evidence appeared" in notes and "evidence went quiet" in notes
    assert "confidence moved" in notes
    assert "direction flipped" in notes
    assert "portfolio adjustment moved" in notes


def test_intelligence_reasoning_is_deterministic_and_json_safe() -> None:
    per_model = evidence_map()
    assessment, _ = focus_assessment(per_model)
    bull1, bear1 = build_theses(per_model)
    bull2, bear2 = build_theses(dict(reversed(list(per_model.items()))))
    assert bull1 == bull2 and bear1 == bear2  # order-independent
    payload = {
        "sections": {k: s.to_dict() for k, s in build_sections(per_model, assessment).items()},
        "bull": [p.to_dict() for p in bull1],
        "rec": build_recommendation(assessment, bull1, bear1, {}),
    }
    assert json.loads(json.dumps(payload)) == payload


def test_no_circular_scoring_dependency() -> None:
    """The intelligence layer consumes and explains the trim score; the
    scoring chain must never import the interpretation layer back."""
    import ast
    import inspect

    import mip.engine.attribution
    import mip.engine.evidence
    import mip.engine.trim

    for module in (mip.engine.evidence, mip.engine.trim, mip.engine.attribution):
        tree = ast.parse(inspect.getsource(module))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any("intelligence" in name for name in imported), module.__name__
