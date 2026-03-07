"""httpx-based fetcher — the primary backend for manufacturer sites."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone

import httpx

from drift.pipeline.config import (
    FETCH_MAX_RETRIES,
    FETCH_RETRY_BASE_SECONDS,
    HTTPX_CONNECT_TIMEOUT_SECONDS,
    HTTPX_HEADERS,
    HTTPX_TIMEOUT_SECONDS,
)
from drift.pipeline.fetching.base import BaseFetcher
from drift.pipeline.fetching.schemas import FetchResult

logger = logging.getLogger(__name__)


class HttpxFetcher(BaseFetcher):
    """Async HTTP fetcher using httpx with browser-like headers."""

    async def fetch(self, url: str) -> FetchResult:
        timeout = httpx.Timeout(HTTPX_TIMEOUT_SECONDS, connect=HTTPX_CONNECT_TIMEOUT_SECONDS)

        last_exc: Exception | None = None
        for attempt in range(FETCH_MAX_RETRIES + 1):
            try:
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
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exc = e
                if attempt < FETCH_MAX_RETRIES:
                    delay = FETCH_RETRY_BASE_SECONDS * (2**attempt)
                    logger.warning(
                        "Transient fetch error for %s (attempt %d/%d), retrying in %.0fs: %s",
                        url,
                        attempt + 1,
                        FETCH_MAX_RETRIES + 1,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted — re-raise the last exception
        raise last_exc  # type: ignore[misc]
