"""Tests for the RAG retriever module."""

from __future__ import annotations



from q3_ai_assistant.rag.retriever import _cosine_similarity


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_similarity(a, b)) < 1e-6

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(_cosine_similarity(a, b) + 1.0) < 1e-6

    def test_similar_vectors(self):
        a = [1.0, 1.0, 0.0]
        b = [1.0, 1.0, 0.1]
        sim = _cosine_similarity(a, b)
        assert sim > 0.95

    def test_zero_vector(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
        assert _cosine_similarity([1.0, 1.0], [0.0, 0.0]) == 0.0

    def test_high_dimensional(self):
        # Simulate embedding dimensions
        a = [float(i % 7) for i in range(1536)]
        b = [float(i % 7) for i in range(1536)]
        assert abs(_cosine_similarity(a, b) - 1.0) < 1e-6

    def test_normalized_result(self):
        a = [3.0, 4.0]
        b = [4.0, 3.0]
        sim = _cosine_similarity(a, b)
        assert -1.0 <= sim <= 1.0
