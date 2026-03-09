"""Response builder with source precedence and citation tracking.

Source precedence (highest to lowest):
1. Structured internal data — computed_metrics, statement_lines, refinement_results, market_snapshots
2. Internal docs / RAG — strategy definitions, ADRs, approved AI notes
3. External web — news, sector context, macro data
4. Model prior knowledge — only for conceptual/educational explanations

Rules:
- Agents must not infer or fabricate financial facts outside the packet + tools
- Any factual claim must cite a source from the packet or a tool result
- Web data never overwrites structured internal data
- When web contradicts internal data: show divergence explicitly
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger(__name__)


class SourceType(IntEnum):
    """Source precedence — lower number = higher priority."""
    STRUCTURED_INTERNAL = 1
    INTERNAL_RAG = 2
    EXTERNAL_WEB = 3
    MODEL_PRIOR = 4


@dataclass
class Citation:
    """A citation referencing a data source."""
    source_type: SourceType
    entity_type: str  # e.g. "computed_metric", "statement_line", "embedding", "web"
    entity_id: str  # e.g. ticker, metric_code, chunk_id, URL
    snippet: str  # the relevant text/value
    label: str = ""  # human-readable label

    @property
    def precedence(self) -> int:
        return int(self.source_type)


@dataclass
class SourceBlock:
    """A block of context from a specific source."""
    source_type: SourceType
    content: str
    citations: list[Citation] = field(default_factory=list)


@dataclass
class BuiltResponse:
    """Final response with merged context and citations."""
    context: str
    citations: list[Citation]
    divergences: list[str]


def build_response_context(
    tool_blocks: list[SourceBlock] | None = None,
    rag_blocks: list[SourceBlock] | None = None,
    web_blocks: list[SourceBlock] | None = None,
) -> BuiltResponse:
    """Merge sources following precedence rules.

    Returns a combined context string with inline citation markers
    and a list of all citations ordered by precedence.
    """
    all_blocks: list[SourceBlock] = []

    if tool_blocks:
        all_blocks.extend(tool_blocks)
    if rag_blocks:
        all_blocks.extend(rag_blocks)
    if web_blocks:
        all_blocks.extend(web_blocks)

    # Sort by precedence (structured first)
    all_blocks.sort(key=lambda b: int(b.source_type))

    context_parts: list[str] = []
    all_citations: list[Citation] = []
    divergences: list[str] = []

    # Track internal facts for divergence detection
    internal_facts: dict[str, str] = {}

    for block in all_blocks:
        if block.source_type == SourceType.STRUCTURED_INTERNAL:
            context_parts.append(f"[Dados internos] {block.content}")
            # Track facts for divergence detection
            for citation in block.citations:
                internal_facts[citation.entity_id] = citation.snippet
        elif block.source_type == SourceType.INTERNAL_RAG:
            context_parts.append(f"[RAG] {block.content}")
        elif block.source_type == SourceType.EXTERNAL_WEB:
            context_parts.append(f"[Web] {block.content}")
            # Check for divergences with internal data
            for citation in block.citations:
                if citation.entity_id in internal_facts:
                    internal_val = internal_facts[citation.entity_id]
                    divergences.append(
                        f"Dados internos mostram {citation.entity_id}={internal_val}; "
                        f"fonte externa ({citation.label}) reporta: {citation.snippet}"
                    )
        else:
            context_parts.append(f"[Conceitual] {block.content}")

        all_citations.extend(block.citations)

    context = "\n\n".join(context_parts) if context_parts else ""

    # Add divergence notices
    if divergences:
        divergence_text = "\n".join(f"⚠ {d}" for d in divergences)
        context += f"\n\n--- Divergencias detectadas ---\n{divergence_text}"

    return BuiltResponse(
        context=context,
        citations=sorted(all_citations, key=lambda c: c.precedence),
        divergences=divergences,
    )


def enrich_packet_with_rag(
    db_session: object,
    ticker: str,
) -> list[str]:
    """Retrieve RAG context relevant to a ticker for council enrichment.

    Returns a list of context strings to add to the packet's rag_context field.
    """
    try:
        from q3_ai_assistant.config import settings
        from q3_ai_assistant.rag.embedder import Embedder
        from q3_ai_assistant.rag.retriever import Retriever

        if not settings.openai_api_key:
            return []

        embedder = Embedder(settings)
        retriever = Retriever(embedder)

        # Search for company-specific context
        query = f"{ticker} analysis fundamentals quality"
        results = retriever.search(db_session, query, top_k=3, threshold=0.4)

        if not results:
            return []

        return [
            f"[{r.entity_type}/{r.entity_id}] {r.chunk_text}"
            for r in results
        ]
    except Exception:
        logger.debug("RAG enrichment skipped for %s", ticker)
        return []
