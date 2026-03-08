"""Tests for council web tools (web_search, web_browse)."""

from __future__ import annotations

from q3_ai_assistant.council.tools.web_search import WebSearchResponse, web_search
from q3_ai_assistant.council.tools.web_browse import BrowseResult, web_browse


class TestWebSearch:
    def test_returns_response_object(self):
        result = web_search("WEGE3 news")
        assert isinstance(result, WebSearchResponse)
        assert result.query == "WEGE3 news"

    def test_stub_returns_error(self):
        result = web_search("test query")
        assert result.error is not None
        assert "not configured" in result.error

    def test_stub_returns_empty_results(self):
        result = web_search("anything")
        assert result.results == []

    def test_max_results_param(self):
        result = web_search("test", max_results=3)
        assert isinstance(result, WebSearchResponse)


class TestWebBrowse:
    def test_returns_browse_result(self):
        result = web_browse("https://example.com")
        assert isinstance(result, BrowseResult)
        assert result.url == "https://example.com"

    def test_stub_returns_error(self):
        result = web_browse("https://example.com")
        assert result.error is not None
        assert "not configured" in result.error

    def test_stub_returns_empty_content(self):
        result = web_browse("https://example.com")
        assert result.content == ""
        assert result.title == ""

    def test_source_type_is_web(self):
        result = web_browse("https://example.com")
        assert result.source_type == "web"
