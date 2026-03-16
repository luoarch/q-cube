"""Tests for the rubric_suggester module."""

from __future__ import annotations

import json
import uuid

import pytest

from q3_ai_assistant.llm.adapter import LLMResponse
from q3_ai_assistant.models.entities import (
    AIModule,
    AIResearchNote,
    AISuggestion,
    ConfidenceLevel,
    NoteType,
)
from q3_ai_assistant.modules.rubric_suggester import (
    SUPPORTED_DIMENSIONS,
    _clamp_confidence,
    _validate_score,
    compute_input_hash,
    suggest_dimension,
    suggest_usd_debt_exposure,
)


MOCK_RUBRIC_OUTPUT = json.dumps({
    "score": 45,
    "confidence": "medium",
    "rationale": "Moderate USD debt from infrastructure bonds. Debt/EBITDA at 3.2x suggests manageable but notable exposure.",
    "evidence_ref": "short_term_debt=500M, long_term_debt=2.1B, financial_result=-180M",
    "key_signals": ["high long-term debt", "negative financial result suggests USD interest"],
    "uncertainty_factors": ["no currency breakdown available", "hedging status unknown"],
})


class RubricMockAdapter:
    """Mock adapter that returns rubric-shaped JSON."""

    def __init__(self, output: str = MOCK_RUBRIC_OUTPUT) -> None:
        self._output = output
        self._call_count = 0

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        self._call_count += 1
        return LLMResponse(
            text=self._output,
            model="mock-rubric-v1",
            model_version="mock-rubric-v1.0",
            tokens_used=200,
            prompt_tokens=150,
            completion_tokens=50,
            latency_ms=10.0,
            cost_usd=0.001,
        )


SAMPLE_ISSUER_DATA = {
    "ticker": "TEST3",
    "company_name": "Test Corp",
    "sector": "Energia",
    "subsector": "Petróleo e Gás",
    "issuer_id": str(uuid.uuid4()),
    "financials": {
        "short_term_debt": 500_000_000,
        "long_term_debt": 2_100_000_000,
        "cash_and_equivalents": 800_000_000,
        "financial_result": -180_000_000,
    },
    "computed_metrics": {
        "debt_to_ebitda": 3.2,
        "interest_coverage": 2.5,
    },
    "sector_context": "Commodity exporter — typically has significant USD-denominated debt and revenue.",
}


class TestClampConfidence:
    def test_medium_stays_medium(self):
        assert _clamp_confidence("medium") == ConfidenceLevel.medium

    def test_low_stays_low(self):
        assert _clamp_confidence("low") == ConfidenceLevel.low

    def test_high_clamped_to_low(self):
        assert _clamp_confidence("high") == ConfidenceLevel.low

    def test_unknown_clamped_to_low(self):
        assert _clamp_confidence("unknown") == ConfidenceLevel.low


class TestValidateScore:
    def test_valid_score(self):
        assert _validate_score(45) == 45

    def test_string_score(self):
        assert _validate_score("72") == 72

    def test_above_100_clamped(self):
        assert _validate_score(150) == 100

    def test_below_0_clamped(self):
        assert _validate_score(-10) == 0

    def test_none_returns_default(self):
        assert _validate_score(None) == 30

    def test_garbage_returns_default(self):
        assert _validate_score("not_a_number") == 30


class TestComputeInputHash:
    def test_deterministic(self):
        h1 = compute_input_hash({"a": 1, "b": 2})
        h2 = compute_input_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        h1 = compute_input_hash({"a": 1})
        h2 = compute_input_hash({"a": 2})
        assert h1 != h2


class TestSuggestUsdDebtExposure:
    def test_creates_suggestion(self, session):
        adapter = RubricMockAdapter()
        tenant_id = uuid.uuid4()
        issuer_id = uuid.uuid4()

        result = suggest_usd_debt_exposure(
            session, adapter, cache=None,
            tenant_id=tenant_id, issuer_id=issuer_id,
            issuer_data=SAMPLE_ISSUER_DATA,
        )

        assert isinstance(result, AISuggestion)
        assert result.module == AIModule.rubric_suggester
        assert result.confidence == ConfidenceLevel.medium
        assert result.model_used == "mock-rubric-v1"

    def test_structured_output_shape(self, session):
        adapter = RubricMockAdapter()
        result = suggest_usd_debt_exposure(
            session, adapter, cache=None,
            tenant_id=uuid.uuid4(), issuer_id=uuid.uuid4(),
            issuer_data=SAMPLE_ISSUER_DATA,
        )

        out = result.structured_output
        assert out["dimension_key"] == "usd_debt_exposure"
        assert out["suggested_score"] == 45
        assert out["confidence"] == "medium"
        assert out["source_type"] == "AI_ASSISTED"
        assert len(out["key_signals"]) == 2
        assert len(out["uncertainty_factors"]) == 2

    def test_research_note_created(self, session):
        adapter = RubricMockAdapter()
        suggest_usd_debt_exposure(
            session, adapter, cache=None,
            tenant_id=uuid.uuid4(), issuer_id=uuid.uuid4(),
            issuer_data=SAMPLE_ISSUER_DATA,
        )

        notes = session.query(AIResearchNote).all()
        assert len(notes) == 1
        assert notes[0].note_type == NoteType.recommendation
        assert "usd_debt_exposure" in notes[0].content

    def test_high_confidence_clamped(self, session):
        """Even if LLM returns high confidence, it's clamped to low."""
        high_output = json.dumps({
            "score": 80,
            "confidence": "high",
            "rationale": "Very confident",
            "evidence_ref": "direct data",
            "key_signals": [],
            "uncertainty_factors": [],
        })
        adapter = RubricMockAdapter(output=high_output)

        result = suggest_usd_debt_exposure(
            session, adapter, cache=None,
            tenant_id=uuid.uuid4(), issuer_id=uuid.uuid4(),
            issuer_data=SAMPLE_ISSUER_DATA,
        )

        assert result.confidence == ConfidenceLevel.low
        assert result.structured_output["confidence"] == "low"

    def test_malformed_llm_output_uses_defaults(self, session):
        """If LLM returns garbage, we get conservative defaults."""
        adapter = RubricMockAdapter(output="not valid json at all")

        result = suggest_usd_debt_exposure(
            session, adapter, cache=None,
            tenant_id=uuid.uuid4(), issuer_id=uuid.uuid4(),
            issuer_data=SAMPLE_ISSUER_DATA,
        )

        out = result.structured_output
        assert out["suggested_score"] == 30  # conservative default
        assert out["confidence"] == "low"
        assert out["rationale"] == "No rationale provided"

    def test_score_clamped_to_range(self, session):
        """Score outside 0-100 is clamped."""
        extreme_output = json.dumps({
            "score": 200,
            "confidence": "medium",
            "rationale": "Extreme",
            "evidence_ref": "",
            "key_signals": [],
            "uncertainty_factors": [],
        })
        adapter = RubricMockAdapter(output=extreme_output)

        result = suggest_usd_debt_exposure(
            session, adapter, cache=None,
            tenant_id=uuid.uuid4(), issuer_id=uuid.uuid4(),
            issuer_data=SAMPLE_ISSUER_DATA,
        )

        assert result.structured_output["suggested_score"] == 100

    def test_prompt_version_persisted(self, session):
        adapter = RubricMockAdapter()
        result = suggest_usd_debt_exposure(
            session, adapter, cache=None,
            tenant_id=uuid.uuid4(), issuer_id=uuid.uuid4(),
            issuer_data=SAMPLE_ISSUER_DATA,
        )

        from q3_ai_assistant.prompts.rubric import PROMPT_VERSION
        assert result.prompt_version == PROMPT_VERSION
        assert result.structured_output["prompt_version"] == PROMPT_VERSION


class TestSuggestImportDependence:
    """Tests for usd_import_dependence dimension via suggest_dimension."""

    def test_creates_suggestion(self, session):
        adapter = RubricMockAdapter()
        result = suggest_dimension(
            session, adapter, cache=None,
            dimension_key="usd_import_dependence",
            tenant_id=uuid.uuid4(), issuer_id=uuid.uuid4(),
            issuer_data=SAMPLE_ISSUER_DATA,
        )

        assert isinstance(result, AISuggestion)
        assert result.structured_output["dimension_key"] == "usd_import_dependence"
        assert result.structured_output["source_type"] == "AI_ASSISTED"

    def test_research_note_tagged(self, session):
        adapter = RubricMockAdapter()
        suggest_dimension(
            session, adapter, cache=None,
            dimension_key="usd_import_dependence",
            tenant_id=uuid.uuid4(), issuer_id=uuid.uuid4(),
            issuer_data=SAMPLE_ISSUER_DATA,
        )

        notes = session.query(AIResearchNote).all()
        assert len(notes) == 1
        assert "usd_import_dependence" in notes[0].content

    def test_guard_rails_same(self, session):
        """Import dependence uses the same guard rails: no high confidence."""
        high_output = json.dumps({
            "score": 90,
            "confidence": "high",
            "rationale": "Very import dependent",
            "evidence_ref": "sector analysis",
            "key_signals": ["pharma APIs"],
            "uncertainty_factors": [],
        })
        adapter = RubricMockAdapter(output=high_output)

        result = suggest_dimension(
            session, adapter, cache=None,
            dimension_key="usd_import_dependence",
            tenant_id=uuid.uuid4(), issuer_id=uuid.uuid4(),
            issuer_data=SAMPLE_ISSUER_DATA,
        )

        assert result.confidence == ConfidenceLevel.low
        assert result.structured_output["confidence"] == "low"

    def test_unsupported_dimension_raises(self, session):
        adapter = RubricMockAdapter()
        with pytest.raises(ValueError, match="Unsupported dimension"):
            suggest_dimension(
                session, adapter, cache=None,
                dimension_key="nonexistent_dimension",
                tenant_id=uuid.uuid4(), issuer_id=uuid.uuid4(),
                issuer_data=SAMPLE_ISSUER_DATA,
            )

    def test_supported_dimensions_set(self):
        assert "usd_debt_exposure" in SUPPORTED_DIMENSIONS
        assert "usd_import_dependence" in SUPPORTED_DIMENSIONS
        assert "usd_revenue_offset" in SUPPORTED_DIMENSIONS
        assert len(SUPPORTED_DIMENSIONS) == 3


class TestSuggestRevenueOffset:
    """Tests for usd_revenue_offset dimension."""

    def test_creates_suggestion(self, session):
        adapter = RubricMockAdapter()
        result = suggest_dimension(
            session, adapter, cache=None,
            dimension_key="usd_revenue_offset",
            tenant_id=uuid.uuid4(), issuer_id=uuid.uuid4(),
            issuer_data=SAMPLE_ISSUER_DATA,
        )

        assert isinstance(result, AISuggestion)
        assert result.structured_output["dimension_key"] == "usd_revenue_offset"

    def test_research_note_tagged(self, session):
        adapter = RubricMockAdapter()
        suggest_dimension(
            session, adapter, cache=None,
            dimension_key="usd_revenue_offset",
            tenant_id=uuid.uuid4(), issuer_id=uuid.uuid4(),
            issuer_data=SAMPLE_ISSUER_DATA,
        )

        notes = session.query(AIResearchNote).all()
        assert len(notes) == 1
        assert "usd_revenue_offset" in notes[0].content
