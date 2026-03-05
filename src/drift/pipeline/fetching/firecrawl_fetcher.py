"""Firecrawl-based fetcher — optional fallback for JS-rendered SPAs."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone

from drift.pipeline.config import FIRECRAWL_API_KEY
from drift.pipeline.fetching.base import BaseFetcher
from drift.pipeline.fetching.schemas import FetchResult


class FirecrawlFetcher(BaseFetcher):
    """Fetcher using Firecrawl for JavaScript-rendered pages."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or FIRECRAWL_API_KEY
        if not self._api_key:
            raise ValueError("FIRECRAWL_API_KEY not set. Export it or add to .env")

    async def fetch(self, url: str) -> FetchResult:
        from firecrawl import FirecrawlApp

        app = FirecrawlApp(api_key=self._api_key)
        # FirecrawlApp.scrape() is synchronous — run in executor to avoid blocking the event loop
        doc = await asyncio.to_thread(app.scrape, url, formats=["html"])

        html = doc.html or ""
        status = getattr(doc.metadata, "statusCode", 200) if doc.metadata else 200

        return FetchResult(
            url=url,
            html=html,
            status_code=status,
            fetched_at=datetime.now(timezone.utc),
            fetcher_backend="firecrawl",
            content_hash=hashlib.sha256(html.encode()).hexdigest(),
        )
