"""Evidence Normalization against real model outputs: three different
intelligence models evaluate the same stock in the same database, and every
score — evidence-backed or honestly neutral — must normalize into one
valid, deterministic, losslessly-serializable contract."""

import json

import pytest

from mip.core.db import session_scope
from mip.models.evidence import NormalizedEvidence, normalize_scores
from mip.models.momentum import MomentumExhaustionModel
from mip.models.relative import RelativeStrengthModel
from mip.models.sector import SectorRotationModel
from mip.models.valuation import ValuationModel
from tests.integration.test_intelligence_relative import relative_env  # noqa: F401

pytestmark = pytest.mark.integration

MODELS = (SectorRotationModel, MomentumExhaustionModel, RelativeStrengthModel, ValuationModel)


def all_scores(factory, symbol: str):
    with session_scope(factory) as session:
        return {model_cls: model_cls(session).evaluate(symbol) for model_cls in MODELS}


def test_every_model_normalizes_into_one_valid_contract(relative_env) -> None:
    by_model = all_scores(relative_env, "RS1")
    schemas = set()
    for scores in by_model.values():
        batch = normalize_scores(scores)  # validates every item internally
        assert len(batch) == 6
        for score, evidence in zip(scores, batch, strict=True):
            assert evidence.model_name == score.model
            assert evidence.score == score.score
            assert evidence.diagnostics == score.diagnostics  # preserved verbatim
            schemas.add(tuple(sorted(evidence.to_dict())))
    assert len(schemas) == 1  # identical schema across all models


def test_neutral_and_backed_evidence_coexist(relative_env) -> None:
    by_model = all_scores(relative_env, "RS1")
    relative = normalize_scores(by_model[RelativeStrengthModel])
    valuation = normalize_scores(by_model[ValuationModel])  # no fundamentals here
    assert any(not e.neutral for e in relative)  # deep leadership regime
    assert all(e.neutral for e in valuation)  # honest insufficiency survives
    backed = next(e for e in relative if not e.neutral)
    assert backed.expected_volatility is not None and backed.expected_volatility > 0
    assert backed.downside_risk < backed.expected_return < backed.upside_potential
    assert backed.supporting_reasons or backed.opposing_reasons


def test_normalization_is_deterministic_and_lossless_end_to_end(relative_env) -> None:
    by_model = all_scores(relative_env, "RS1")
    for scores in by_model.values():
        first = [e.to_dict() for e in normalize_scores(scores)]
        second = [e.to_dict() for e in normalize_scores(scores)]
        assert first == second
        for payload in first:
            restored = NormalizedEvidence.from_dict(json.loads(json.dumps(payload)))
            assert restored.to_dict() == payload  # JSON round trip loses nothing
