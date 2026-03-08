"""Web browse tool — fetch and extract content from a URL.

Web data never overwrites structured internal data. Results must be cited.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 10_000


@dataclass(frozen=True)
class BrowseResult:
    url: str
    title: str
    content: str
    source_type: str = "web"
    error: str | None = None


def web_browse(url: str, *, max_length: int = MAX_CONTENT_LENGTH) -> BrowseResult:
    """Fetch a URL and extract text content.

    This is a gated tool — only fired when intent requires external context.
    Currently a stub; will use httpx + html extraction when configured.
    """
    logger.info("Web browse requested: %s", url)

    # Stub: return error until provider is configured
    return BrowseResult(
        url=url,
        title="",
        content="",
        error="Web browse not configured. Set Q3_AI_WEB_BROWSE_ENABLED=true to enable.",
    )
