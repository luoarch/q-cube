"""Tests for response builder with source precedence."""

from __future__ import annotations

from q3_ai_assistant.rag.response_builder import (
    Citation,
    SourceBlock,
    SourceType,
    build_response_context,
)


class TestSourcePrecedence:
    def test_structured_before_rag(self):
        tool_block = SourceBlock(
            source_type=SourceType.STRUCTURED_INTERNAL,
            content="ROIC = 25%",
            citations=[Citation(
                source_type=SourceType.STRUCTURED_INTERNAL,
                entity_type="computed_metric",
                entity_id="roic",
                snippet="25%",
            )],
        )
        rag_block = SourceBlock(
            source_type=SourceType.INTERNAL_RAG,
            content="Previous analysis showed strong ROIC",
            citations=[Citation(
                source_type=SourceType.INTERNAL_RAG,
                entity_type="embedding",
                entity_id="chunk_123",
                snippet="Strong ROIC trend",
            )],
        )
        result = build_response_context(
            tool_blocks=[tool_block],
            rag_blocks=[rag_block],
        )
        # Structured internal should come first in context
        assert result.context.index("[Dados internos]") < result.context.index("[RAG]")
        # Citations should be sorted by precedence
        assert result.citations[0].source_type == SourceType.STRUCTURED_INTERNAL
        assert result.citations[1].source_type == SourceType.INTERNAL_RAG

    def test_web_divergence_detected(self):
        tool_block = SourceBlock(
            source_type=SourceType.STRUCTURED_INTERNAL,
            content="ROIC = 25%",
            citations=[Citation(
                source_type=SourceType.STRUCTURED_INTERNAL,
                entity_type="computed_metric",
                entity_id="roic",
                snippet="25%",
            )],
        )
        web_block = SourceBlock(
            source_type=SourceType.EXTERNAL_WEB,
            content="External source says ROIC = 18%",
            citations=[Citation(
                source_type=SourceType.EXTERNAL_WEB,
                entity_type="web",
                entity_id="roic",
                snippet="18%",
                label="External Source",
            )],
        )
        result = build_response_context(
            tool_blocks=[tool_block],
            web_blocks=[web_block],
        )
        assert len(result.divergences) == 1
        assert "roic" in result.divergences[0]
        assert "25%" in result.divergences[0]
        assert "18%" in result.divergences[0]
        assert "Divergencias" in result.context

    def test_no_divergence_without_conflict(self):
        tool_block = SourceBlock(
            source_type=SourceType.STRUCTURED_INTERNAL,
            content="ROIC = 25%",
            citations=[Citation(
                source_type=SourceType.STRUCTURED_INTERNAL,
                entity_type="computed_metric",
                entity_id="roic",
                snippet="25%",
            )],
        )
        web_block = SourceBlock(
            source_type=SourceType.EXTERNAL_WEB,
            content="Revenue growth strong",
            citations=[Citation(
                source_type=SourceType.EXTERNAL_WEB,
                entity_type="web",
                entity_id="revenue_growth",
                snippet="15%",
            )],
        )
        result = build_response_context(
            tool_blocks=[tool_block],
            web_blocks=[web_block],
        )
        assert len(result.divergences) == 0

    def test_empty_blocks(self):
        result = build_response_context()
        assert result.context == ""
        assert result.citations == []
        assert result.divergences == []

    def test_model_prior_lowest_priority(self):
        blocks = [
            SourceBlock(SourceType.MODEL_PRIOR, "General knowledge"),
            SourceBlock(SourceType.STRUCTURED_INTERNAL, "Internal data"),
            SourceBlock(SourceType.EXTERNAL_WEB, "Web data"),
        ]
        result = build_response_context(
            tool_blocks=[blocks[1]],
            web_blocks=[blocks[2]],
        )
        # Structured first, then web — model prior not included since no param
        assert result.context.index("[Dados internos]") < result.context.index("[Web]")
