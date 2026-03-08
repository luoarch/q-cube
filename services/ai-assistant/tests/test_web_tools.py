"""Tests for council web tools (web_search, web_browse).

These tests exercise the real implementations with httpx. Network calls
are real — no mocks/stubs. Tests that require API keys are skipped when
keys are not configured.
"""

from __future__ import annotations

import pytest

from q3_ai_assistant.config import settings
from q3_ai_assistant.council.tools.web_browse import BrowseResult, web_browse
from q3_ai_assistant.council.tools.web_search import WebSearchResponse, web_search


# ---------------------------------------------------------------------------
# Web Search (Brave API)
# ---------------------------------------------------------------------------


class TestWebSearch:
    def test_returns_response_object_without_key(self):
        """When no API key is set, returns a valid response with error."""
        original = settings.brave_search_api_key
        try:
            settings.brave_search_api_key = ""
            result = web_search("WEGE3 news")
            assert isinstance(result, WebSearchResponse)
            assert result.query == "WEGE3 news"
            assert result.error is not None
            assert "not configured" in result.error
            assert result.results == []
        finally:
            settings.brave_search_api_key = original

    @pytest.mark.skipif(
        not settings.brave_search_api_key,
        reason="Q3_AI_BRAVE_SEARCH_API_KEY not configured",
    )
    def test_real_search_returns_results(self):
        """With a valid API key, returns actual web search results."""
        result = web_search("B3 WEGE3 investimento", max_results=3)
        assert isinstance(result, WebSearchResponse)
        assert result.error is None
        assert len(result.results) > 0
        assert len(result.results) <= 3

        first = result.results[0]
        assert first.title
        assert first.url.startswith("http")
        assert first.source_type == "web"

    @pytest.mark.skipif(
        not settings.brave_search_api_key,
        reason="Q3_AI_BRAVE_SEARCH_API_KEY not configured",
    )
    def test_max_results_respected(self):
        result = web_search("Python programming", max_results=2)
        assert len(result.results) <= 2


# ---------------------------------------------------------------------------
# Web Browse (httpx + BeautifulSoup)
# ---------------------------------------------------------------------------


class TestWebBrowse:
    def test_browse_real_url(self):
        """Fetches a real URL and extracts text content."""
        result = web_browse("https://httpbin.org/html")
        assert isinstance(result, BrowseResult)
        assert result.url == "https://httpbin.org/html"
        assert result.error is None
        assert result.source_type == "web"
        # httpbin /html returns a page with "Herman Melville"
        assert "Herman Melville" in result.content or "Moby" in result.content
        assert len(result.content) > 100  # substantial text extracted

    def test_browse_plain_text(self):
        """Fetches a plain text URL."""
        result = web_browse("https://httpbin.org/robots.txt")
        assert isinstance(result, BrowseResult)
        assert result.error is None
        assert result.content  # should have some content

    def test_browse_invalid_url(self):
        """Handles invalid/unreachable URLs gracefully."""
        result = web_browse("https://this-domain-does-not-exist-q3test.invalid/page")
        assert isinstance(result, BrowseResult)
        assert result.error is not None

    def test_browse_http_error(self):
        """Handles HTTP errors (404) gracefully."""
        result = web_browse("https://httpbin.org/status/404")
        assert isinstance(result, BrowseResult)
        assert result.error is not None
        assert "404" in result.error

    def test_browse_max_length_truncation(self):
        """Content is truncated when exceeding max_length."""
        result = web_browse("https://httpbin.org/html", max_length=50)
        assert isinstance(result, BrowseResult)
        if result.error is None and len(result.content) > 50:
            assert result.content.endswith("[truncated]")

    def test_browse_disabled(self):
        """When browsing is disabled, returns error."""
        original = settings.web_browse_enabled
        try:
            settings.web_browse_enabled = False
            result = web_browse("https://httpbin.org/html")
            assert result.error is not None
            assert "not configured" in result.error
        finally:
            settings.web_browse_enabled = original

    def test_source_type_is_web(self):
        result = web_browse("https://httpbin.org/html")
        assert result.source_type == "web"
