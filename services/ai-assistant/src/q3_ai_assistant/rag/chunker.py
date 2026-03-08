"""Text chunking for RAG indexing."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_CHUNK_SIZE = 512
DEFAULT_OVERLAP = 64
MIN_CHUNK_SIZE = 50


@dataclass(frozen=True)
class Chunk:
    text: str
    index: int
    metadata: dict


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
    metadata: dict | None = None,
) -> list[Chunk]:
    """Split text into overlapping chunks for embedding.

    Uses sentence-boundary-aware splitting: tries to break at periods/newlines
    within the chunk window to avoid cutting mid-sentence.
    """
    if not text or not text.strip():
        return []

    base_meta = metadata or {}
    chunks: list[Chunk] = []
    pos = 0
    idx = 0

    while pos < len(text):
        end = min(pos + chunk_size, len(text))
        segment = text[pos:end]

        # Try to break at a sentence boundary if not at end of text
        if end < len(text):
            # Look for last period, newline, or semicolon in the segment
            for sep in ("\n\n", "\n", ". ", "; "):
                last_sep = segment.rfind(sep)
                if last_sep > chunk_size // 2:
                    segment = segment[: last_sep + len(sep)]
                    end = pos + len(segment)
                    break

        trimmed = segment.strip()
        if len(trimmed) >= MIN_CHUNK_SIZE:
            chunks.append(Chunk(text=trimmed, index=idx, metadata=base_meta))
            idx += 1

        # Advance with overlap
        pos = end - overlap if end < len(text) else end

    return chunks


def chunk_structured_data(
    entity_type: str,
    entity_id: str,
    sections: list[tuple[str, str]],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """Chunk structured data (e.g., company financials) with section context.

    Each section is a (title, content) tuple. Section title is prepended to
    each chunk for context.
    """
    all_chunks: list[Chunk] = []
    base_idx = 0

    for title, content in sections:
        prefixed = f"{title}\n{content}" if title else content
        meta = {"entity_type": entity_type, "entity_id": entity_id, "section": title}
        section_chunks = chunk_text(
            prefixed,
            chunk_size=chunk_size,
            overlap=overlap,
            metadata=meta,
        )
        for c in section_chunks:
            all_chunks.append(Chunk(text=c.text, index=base_idx + c.index, metadata=c.metadata))
        base_idx += len(section_chunks)

    return all_chunks
