"""httpx-based fetcher — the primary backend for manufacturer sites."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import httpx

from drift.pipeline.config import HTTPX_CONNECT_TIMEOUT_SECONDS, HTTPX_HEADERS, HTTPX_TIMEOUT_SECONDS
from drift.pipeline.fetching.base import BaseFetcher
from drift.pipeline.fetching.schemas import FetchResult


class HttpxFetcher(BaseFetcher):
    """Async HTTP fetcher using httpx with browser-like headers."""

    async def fetch(self, url: str) -> FetchResult:
        timeout = httpx.Timeout(HTTPX_TIMEOUT_SECONDS, connect=HTTPX_CONNECT_TIMEOUT_SECONDS)

        async with httpx.AsyncClient(
            headers=HTTPX_HEADERS,
            timeout=timeout,
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            resp = await client.get(url)
            html = resp.text

        return FetchResult(
            url=url,
            html=html,
            status_code=resp.status_code,
            fetched_at=datetime.now(timezone.utc),
            fetcher_backend="httpx",
            content_hash=hashlib.sha256(html.encode()).hexdigest(),
        )
