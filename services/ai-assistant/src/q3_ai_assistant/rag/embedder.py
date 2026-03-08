"""Embedding generation using OpenAI embeddings API."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from q3_ai_assistant.config import Settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
MAX_BATCH_SIZE = 100


@dataclass(frozen=True)
class EmbeddingResult:
    text: str
    vector: list[float]
    model: str
    tokens_used: int


class Embedder:
    """Generate embeddings using OpenAI's text-embedding-3-small model."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.openai_api_key
        self._model = EMBEDDING_MODEL

    def embed_texts(self, texts: list[str]) -> list[EmbeddingResult]:
        """Embed a batch of texts. Returns vectors in same order as input."""
        if not texts:
            return []

        import openai

        client = openai.OpenAI(api_key=self._api_key)
        results: list[EmbeddingResult] = []

        # Process in batches to stay within API limits
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i : i + MAX_BATCH_SIZE]
            response = client.embeddings.create(model=self._model, input=batch)

            total_tokens = response.usage.total_tokens if response.usage else 0
            per_text_tokens = total_tokens // len(batch) if batch else 0

            for j, item in enumerate(response.data):
                results.append(
                    EmbeddingResult(
                        text=batch[j],
                        vector=item.embedding,
                        model=self._model,
                        tokens_used=per_text_tokens,
                    )
                )

        logger.info("Embedded %d texts using %s", len(results), self._model)
        return results

    def embed_single(self, text: str) -> EmbeddingResult:
        """Embed a single text."""
        results = self.embed_texts([text])
        return results[0]
