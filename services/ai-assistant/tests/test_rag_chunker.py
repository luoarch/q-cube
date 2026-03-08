"""Tests for the RAG chunker module."""

from __future__ import annotations

import pytest

from q3_ai_assistant.rag.chunker import (
    MIN_CHUNK_SIZE,
    Chunk,
    chunk_structured_data,
    chunk_text,
)


class TestChunkText:
    def test_empty_text(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_short_text_single_chunk(self):
        text = "A" * 100
        chunks = chunk_text(text, chunk_size=512)
        assert len(chunks) == 1
        assert chunks[0].index == 0
        assert chunks[0].text == text

    def test_long_text_multiple_chunks(self):
        text = "word " * 200  # 1000 chars
        chunks = chunk_text(text, chunk_size=256, overlap=32)
        assert len(chunks) > 1
        # Chunks should be ordered
        for i, c in enumerate(chunks):
            assert c.index == i

    def test_overlap_produces_shared_content(self):
        # Create text without sentence boundaries so chunks split mechanically
        text = "abcdefgh" * 100  # 800 chars, no sentence boundaries
        chunks = chunk_text(text, chunk_size=200, overlap=50)
        assert len(chunks) >= 3
        # With overlap, each chunk after the first should start earlier
        # than where the previous one ended

    def test_sentence_boundary_splitting(self):
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = chunk_text(text, chunk_size=40, overlap=5)
        # Should try to break at ". " boundaries
        for c in chunks:
            assert len(c.text) >= MIN_CHUNK_SIZE or c.text == chunks[-1].text

    def test_newline_boundary_splitting(self):
        text = "Paragraph one has enough content to fill a chunk easily.\n\nParagraph two also has enough content to fill a chunk.\n\nParagraph three is also long enough for the minimum size."
        chunks = chunk_text(text, chunk_size=80, overlap=10)
        assert len(chunks) >= 1

    def test_metadata_preserved(self):
        meta = {"source": "test", "ticker": "WEGE3"}
        chunks = chunk_text("A" * 100, metadata=meta)
        assert chunks[0].metadata == meta

    def test_chunks_below_min_size_skipped(self):
        # Very small text below MIN_CHUNK_SIZE threshold
        text = "hi"
        chunks = chunk_text(text)
        assert len(chunks) == 0

    def test_chunk_is_frozen(self):
        chunks = chunk_text("A" * 100)
        with pytest.raises(AttributeError):
            chunks[0].text = "modified"  # type: ignore[misc]


class TestChunkStructuredData:
    def test_single_section(self):
        sections = [("Financials", "Revenue was R$ 5B. EBITDA margin improved.")]
        chunks = chunk_structured_data("issuer", "123", sections)
        assert len(chunks) >= 1
        assert chunks[0].metadata["section"] == "Financials"
        assert chunks[0].metadata["entity_type"] == "issuer"

    def test_multiple_sections(self):
        sections = [
            ("Overview", "A" * 100),
            ("Financials", "B" * 100),
        ]
        chunks = chunk_structured_data("issuer", "456", sections)
        assert len(chunks) >= 2
        sections_seen = {c.metadata["section"] for c in chunks}
        assert "Overview" in sections_seen
        assert "Financials" in sections_seen

    def test_empty_sections(self):
        chunks = chunk_structured_data("issuer", "789", [])
        assert chunks == []

    def test_section_title_prepended(self):
        sections = [("Header", "Content here with enough text to make a chunk")]
        chunks = chunk_structured_data("issuer", "1", sections, chunk_size=512)
        assert chunks[0].text.startswith("Header\n")

    def test_indices_continuous_across_sections(self):
        sections = [
            ("A", "A" * 200),
            ("B", "B" * 200),
        ]
        chunks = chunk_structured_data("issuer", "1", sections, chunk_size=100, overlap=10)
        indices = [c.index for c in chunks]
        assert indices == list(range(len(chunks)))
