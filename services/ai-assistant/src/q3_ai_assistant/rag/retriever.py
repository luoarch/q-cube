"""Retrieval from embedding store using cosine similarity."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from q3_ai_assistant.rag.embedder import Embedder

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5
SIMILARITY_THRESHOLD = 0.3


@dataclass(frozen=True)
class RetrievalResult:
    entity_type: str
    entity_id: str
    chunk_index: int
    chunk_text: str
    similarity: float
    metadata: dict | None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors (fallback when pgvector not available)."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class Retriever:
    """Retrieve relevant chunks from the embeddings table."""

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder

    def search(
        self,
        session: Session,
        query: str,
        *,
        top_k: int = DEFAULT_TOP_K,
        entity_type: str | None = None,
        threshold: float = SIMILARITY_THRESHOLD,
    ) -> list[RetrievalResult]:
        """Search for chunks similar to the query.

        Uses pgvector's cosine distance operator if the embedding column is VECTOR type,
        otherwise falls back to Python-side cosine similarity on JSONB arrays.
        """
        query_embedding = self._embedder.embed_single(query)

        # Try pgvector cosine distance first
        try:
            return self._search_pgvector(
                session, query_embedding.vector, top_k=top_k,
                entity_type=entity_type, threshold=threshold,
            )
        except Exception:
            logger.debug("pgvector not available, falling back to Python cosine similarity")
            return self._search_python(
                session, query_embedding.vector, top_k=top_k,
                entity_type=entity_type, threshold=threshold,
            )

    def _search_pgvector(
        self,
        session: Session,
        query_vec: list[float],
        *,
        top_k: int,
        entity_type: str | None,
        threshold: float,
    ) -> list[RetrievalResult]:
        """Search using pgvector's <=> cosine distance operator."""
        vec_literal = "[" + ",".join(str(v) for v in query_vec) + "]"

        where_clause = ""
        if entity_type:
            where_clause = f"AND entity_type = '{entity_type}'"

        sql = text(f"""
            SELECT entity_type, entity_id, chunk_index, chunk_text, metadata_json,
                   1 - (embedding::vector <=> :vec::vector) AS similarity
            FROM embeddings
            WHERE 1=1 {where_clause}
            ORDER BY embedding::vector <=> :vec::vector
            LIMIT :top_k
        """)

        rows = session.execute(sql, {"vec": vec_literal, "top_k": top_k}).fetchall()
        results = []
        for row in rows:
            sim = float(row[5])
            if sim >= threshold:
                results.append(RetrievalResult(
                    entity_type=row[0],
                    entity_id=row[1],
                    chunk_index=row[2],
                    chunk_text=row[3],
                    similarity=sim,
                    metadata=row[4],
                ))
        return results

    def _search_python(
        self,
        session: Session,
        query_vec: list[float],
        *,
        top_k: int,
        entity_type: str | None,
        threshold: float,
    ) -> list[RetrievalResult]:
        """Fallback: load all embeddings and compute similarity in Python."""
        from q3_shared_models.entities import Embedding

        query = session.query(Embedding)
        if entity_type:
            query = query.filter(Embedding.entity_type == entity_type)

        rows = query.all()
        scored: list[tuple[float, Embedding]] = []
        for row in rows:
            vec = row.embedding
            if isinstance(vec, list) and len(vec) == len(query_vec):
                sim = _cosine_similarity(query_vec, vec)
                if sim >= threshold:
                    scored.append((sim, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            RetrievalResult(
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                chunk_index=row.chunk_index,
                chunk_text=row.chunk_text,
                similarity=sim,
                metadata=row.metadata_json,
            )
            for sim, row in scored[:top_k]
        ]
