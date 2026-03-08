"""Web search tool for council agents — external context enrichment.

Web data never overwrites structured internal data. Results are labeled
with source_type='web' and must be cited when used.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MAX_RESULTS = 5


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str
    source_type: str = "web"


@dataclass
class WebSearchResponse:
    query: str
    results: list[WebSearchResult] = field(default_factory=list)
    error: str | None = None


def web_search(query: str, *, max_results: int = MAX_RESULTS) -> WebSearchResponse:
    """Search the web for external context.

    This is a gated tool — only used when intent requires external context.
    Currently a stub that returns no results; will be connected to a search
    API (e.g., SerpAPI, Tavily, Brave Search) when configured.
    """
    logger.info("Web search requested: %r (max_results=%d)", query, max_results)

    # Stub: return empty results until a search provider is configured
    return WebSearchResponse(
        query=query,
        results=[],
        error="Web search provider not configured. Set Q3_AI_WEB_SEARCH_PROVIDER to enable.",
    )
