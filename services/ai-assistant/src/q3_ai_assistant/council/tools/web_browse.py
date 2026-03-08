"""Web browse tool — fetch and extract text content from a URL.

Uses httpx for HTTP requests and BeautifulSoup for HTML text extraction.
Web data never overwrites structured internal data. Results must be cited.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from q3_ai_assistant.config import settings

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 10_000

# Tags that typically contain noise rather than article content
_NOISE_TAGS = {"script", "style", "nav", "header", "footer", "aside", "iframe", "noscript"}

_USER_AGENT = (
    "Mozilla/5.0 (compatible; Q3Bot/1.0; +https://q3.dev) "
    "AppleWebKit/537.36 (KHTML, like Gecko)"
)


@dataclass(frozen=True)
class BrowseResult:
    url: str
    title: str
    content: str
    source_type: str = "web"
    error: str | None = None


def web_browse(url: str, *, max_length: int = MAX_CONTENT_LENGTH) -> BrowseResult:
    """Fetch a URL and extract readable text content.

    Requires Q3_AI_WEB_BROWSE_ENABLED=true (default). Strips HTML tags
    and returns plain text truncated to max_length characters.
    """
    if not settings.web_browse_enabled:
        return BrowseResult(
            url=url,
            title="",
            content="",
            error="Web browse not configured. Set Q3_AI_WEB_BROWSE_ENABLED=true to enable.",
        )

    logger.info("Web browse: %s", url)

    try:
        response = httpx.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=settings.web_browse_timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.TimeoutException:
        logger.warning("Web browse timed out for: %s", url)
        return BrowseResult(url=url, title="", content="", error="Request timed out")
    except httpx.HTTPStatusError as exc:
        logger.warning("Web browse HTTP error: %s for %s", exc.response.status_code, url)
        return BrowseResult(
            url=url, title="", content="",
            error=f"HTTP {exc.response.status_code}",
        )
    except httpx.HTTPError as exc:
        logger.warning("Web browse failed for %s: %s", url, exc)
        return BrowseResult(url=url, title="", content="", error=f"Request failed: {exc}")

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type and "text" not in content_type:
        return BrowseResult(
            url=url, title="", content="",
            error=f"Unsupported content type: {content_type}",
        )

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract title
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    # Remove noise elements
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    # Extract text from body (or whole doc if no body)
    body = soup.find("body") or soup
    text = body.get_text(separator="\n", strip=True)

    # Collapse excessive whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)

    # Truncate
    if len(clean_text) > max_length:
        clean_text = clean_text[:max_length] + "\n[truncated]"

    return BrowseResult(url=url, title=title, content=clean_text)
