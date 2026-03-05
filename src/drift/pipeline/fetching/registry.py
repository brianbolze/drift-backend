"""Fetcher registry — tries httpx first, falls back to Firecrawl."""

from __future__ import annotations

import logging

from drift.pipeline.fetching.base import BaseFetcher
from drift.pipeline.fetching.firecrawl_fetcher import FirecrawlFetcher
from drift.pipeline.fetching.httpx_fetcher import HttpxFetcher
from drift.pipeline.fetching.schemas import FetchResult

logger = logging.getLogger(__name__)


class FetcherRegistry:
    """Tries httpx first. Falls back to Firecrawl if httpx returns empty/error content."""

    def __init__(self, *, enable_firecrawl: bool = True):
        self._httpx = HttpxFetcher()
        self._firecrawl: BaseFetcher | None = None
        if enable_firecrawl:
            try:
                self._firecrawl = FirecrawlFetcher()
            except ValueError:
                logger.info("Firecrawl API key not configured — firecrawl fallback disabled")

    async def fetch(self, url: str) -> FetchResult:
        """Fetch a URL, trying httpx first and falling back to Firecrawl on failure."""
        result = await self._httpx.fetch(url)

        if result.status_code >= 400 or len(result.html.strip()) < 500:
            if self._firecrawl:
                logger.info(
                    "httpx returned %d / %d chars for %s — trying firecrawl", result.status_code, len(result.html), url
                )
                result = await self._firecrawl.fetch(url)
            else:
                logger.warning(
                    "httpx returned %d / %d chars for %s — no firecrawl fallback",
                    result.status_code,
                    len(result.html),
                    url,
                )

        return result
