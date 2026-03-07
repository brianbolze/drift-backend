# flake8: noqa: E501
"""Tests for fetcher retry and timeout behavior — offline, no network required."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from drift.pipeline.fetching.httpx_fetcher import HttpxFetcher

# ── HttpxFetcher retry tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_httpx_fetcher_succeeds_on_first_try():
    """Normal fetch — no retries needed."""
    fetcher = HttpxFetcher()

    mock_resp = MagicMock()
    mock_resp.text = "<html>OK</html>"
    mock_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("drift.pipeline.fetching.httpx_fetcher.httpx.AsyncClient", return_value=mock_client):
        result = await fetcher.fetch("https://example.com")

    assert result.status_code == 200
    assert result.html == "<html>OK</html>"
    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
async def test_httpx_fetcher_retries_on_timeout():
    """Retries on TimeoutException, then succeeds."""
    fetcher = HttpxFetcher()

    mock_resp = MagicMock()
    mock_resp.text = "<html>OK</html>"
    mock_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.get.side_effect = [httpx.ReadTimeout("timeout"), mock_resp]
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("drift.pipeline.fetching.httpx_fetcher.httpx.AsyncClient", return_value=mock_client),
        patch("drift.pipeline.fetching.httpx_fetcher.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        result = await fetcher.fetch("https://example.com")

    assert result.status_code == 200
    assert mock_client.get.call_count == 2
    mock_sleep.assert_called_once()


@pytest.mark.asyncio
async def test_httpx_fetcher_retries_on_connect_error():
    """Retries on ConnectError, then succeeds."""
    fetcher = HttpxFetcher()

    mock_resp = MagicMock()
    mock_resp.text = "<html>OK</html>"
    mock_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.get.side_effect = [httpx.ConnectError("refused"), mock_resp]
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("drift.pipeline.fetching.httpx_fetcher.httpx.AsyncClient", return_value=mock_client),
        patch("drift.pipeline.fetching.httpx_fetcher.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await fetcher.fetch("https://example.com")

    assert result.status_code == 200
    assert mock_client.get.call_count == 2


@pytest.mark.asyncio
async def test_httpx_fetcher_exhausts_retries():
    """Raises after all retries exhausted."""
    fetcher = HttpxFetcher()

    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("refused")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("drift.pipeline.fetching.httpx_fetcher.httpx.AsyncClient", return_value=mock_client),
        patch("drift.pipeline.fetching.httpx_fetcher.asyncio.sleep", new_callable=AsyncMock),
        patch("drift.pipeline.fetching.httpx_fetcher.FETCH_MAX_RETRIES", 2),
    ):
        with pytest.raises(httpx.ConnectError):
            await fetcher.fetch("https://example.com")

    # 1 initial + 2 retries = 3 total
    assert mock_client.get.call_count == 3


@pytest.mark.asyncio
async def test_httpx_fetcher_exponential_backoff_delays():
    """Verify backoff delays are exponential: 2s, 4s, 8s."""
    fetcher = HttpxFetcher()

    mock_resp = MagicMock()
    mock_resp.text = "<html>OK</html>"
    mock_resp.status_code = 200

    mock_client = AsyncMock()
    # Fail 3 times, succeed on 4th
    mock_client.get.side_effect = [
        httpx.ReadTimeout("t"),
        httpx.ReadTimeout("t"),
        httpx.ReadTimeout("t"),
        mock_resp,
    ]
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("drift.pipeline.fetching.httpx_fetcher.httpx.AsyncClient", return_value=mock_client),
        patch("drift.pipeline.fetching.httpx_fetcher.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        result = await fetcher.fetch("https://example.com")

    assert result.status_code == 200
    delays = [call.args[0] for call in mock_sleep.call_args_list]
    assert delays == [2.0, 4.0, 8.0]


@pytest.mark.asyncio
async def test_httpx_fetcher_no_retry_on_http_error():
    """Non-transient httpx errors (e.g., TooManyRedirects) should not be retried."""
    fetcher = HttpxFetcher()

    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.TooManyRedirects("too many redirects")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("drift.pipeline.fetching.httpx_fetcher.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(httpx.TooManyRedirects):
            await fetcher.fetch("https://example.com")

    # Only one attempt — no retries for non-transient errors
    assert mock_client.get.call_count == 1


# ── FirecrawlFetcher timeout tests ───────────────────────────────────────


@pytest.mark.asyncio
async def test_firecrawl_fetcher_timeout():
    """FirecrawlFetcher raises TimeoutError when scrape exceeds timeout."""
    import sys
    from types import ModuleType
    from unittest.mock import MagicMock

    # Stub out firecrawl module so the import inside fetch() works
    firecrawl_mod = ModuleType("firecrawl")
    firecrawl_mod.FirecrawlApp = MagicMock  # type: ignore[attr-defined]
    sys.modules["firecrawl"] = firecrawl_mod
    try:
        from drift.pipeline.fetching.firecrawl_fetcher import FirecrawlFetcher

        async def slow_to_thread(*args, **kwargs):
            await asyncio.sleep(10)

        fetcher = FirecrawlFetcher(api_key="test-key")

        with (
            patch("drift.pipeline.fetching.firecrawl_fetcher.asyncio.to_thread", side_effect=slow_to_thread),
            patch("drift.pipeline.fetching.firecrawl_fetcher.FIRECRAWL_TIMEOUT_SECONDS", 0.01),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await fetcher.fetch("https://example.com")
    finally:
        sys.modules.pop("firecrawl", None)
