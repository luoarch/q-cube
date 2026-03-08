"""Web search tool for council agents — external context enrichment.

Uses Brave Search API when configured. Web data never overwrites structured
internal data. Results are labeled with source_type='web' and must be cited.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from q3_ai_assistant.config import settings

logger = logging.getLogger(__name__)

MAX_RESULTS = 5
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


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
    """Search the web using Brave Search API.

    Requires Q3_AI_BRAVE_SEARCH_API_KEY to be set. Returns structured results
    with title, URL, and snippet for citation.
    """
    api_key = settings.brave_search_api_key
    if not api_key:
        logger.warning("Web search called but no API key configured")
        return WebSearchResponse(
            query=query,
            results=[],
            error="Web search provider not configured. Set Q3_AI_BRAVE_SEARCH_API_KEY to enable.",
        )

    logger.info("Web search: %r (max_results=%d)", query, max_results)

    try:
        response = httpx.get(
            BRAVE_SEARCH_URL,
            params={"q": query, "count": min(max_results, 20)},
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            timeout=settings.web_search_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        logger.warning("Web search timed out for query: %r", query)
        return WebSearchResponse(query=query, error="Search request timed out")
    except httpx.HTTPStatusError as exc:
        logger.warning("Web search HTTP error: %s", exc.response.status_code)
        return WebSearchResponse(
            query=query,
            error=f"Search API returned {exc.response.status_code}",
        )
    except httpx.HTTPError as exc:
        logger.warning("Web search failed: %s", exc)
        return WebSearchResponse(query=query, error=f"Search request failed: {exc}")

    results: list[WebSearchResult] = []
    web_results = data.get("web", {}).get("results", [])

    for item in web_results[:max_results]:
        results.append(WebSearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("description", ""),
        ))

    return WebSearchResponse(query=query, results=results)
