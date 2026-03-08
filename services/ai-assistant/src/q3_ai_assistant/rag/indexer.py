"""Indexing pipeline: chunk → embed → persist to embeddings table."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from q3_ai_assistant.rag.chunker import Chunk, chunk_structured_data, chunk_text
from q3_ai_assistant.rag.embedder import Embedder

logger = logging.getLogger(__name__)


class Indexer:
    """Index text content into the embeddings table."""

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder

    def index_text(
        self,
        session: Session,
        entity_type: str,
        entity_id: str,
        text: str,
        *,
        metadata: dict | None = None,
    ) -> int:
        """Chunk and index a plain text document. Returns number of chunks indexed."""
        chunks = chunk_text(text, metadata=metadata)
        return self._persist_chunks(session, entity_type, entity_id, chunks)

    def index_structured(
        self,
        session: Session,
        entity_type: str,
        entity_id: str,
        sections: list[tuple[str, str]],
    ) -> int:
        """Chunk and index structured sections. Returns number of chunks indexed."""
        chunks = chunk_structured_data(entity_type, entity_id, sections)
        return self._persist_chunks(session, entity_type, entity_id, chunks)

    def delete_entity(self, session: Session, entity_type: str, entity_id: str) -> int:
        """Delete all embeddings for an entity. Returns number deleted."""
        from q3_shared_models.entities import Embedding

        count = (
            session.query(Embedding)
            .filter(Embedding.entity_type == entity_type, Embedding.entity_id == entity_id)
            .delete()
        )
        session.flush()
        logger.info("Deleted %d embeddings for %s/%s", count, entity_type, entity_id)
        return count

    def _persist_chunks(
        self,
        session: Session,
        entity_type: str,
        entity_id: str,
        chunks: list[Chunk],
    ) -> int:
        """Embed chunks and persist to database."""
        if not chunks:
            return 0

        from q3_shared_models.entities import Embedding

        # Delete existing embeddings for this entity (re-index)
        self.delete_entity(session, entity_type, entity_id)

        # Generate embeddings
        texts = [c.text for c in chunks]
        embeddings = self._embedder.embed_texts(texts)

        # Persist
        for chunk, emb in zip(chunks, embeddings):
            row = Embedding(
                id=uuid.uuid4(),
                entity_type=entity_type,
                entity_id=entity_id,
                chunk_index=chunk.index,
                chunk_text=chunk.text,
                embedding=emb.vector,
                model_used=emb.model,
                metadata_json=chunk.metadata,
            )
            session.add(row)

        session.flush()
        logger.info("Indexed %d chunks for %s/%s", len(chunks), entity_type, entity_id)
        return len(chunks)
