"""Base interface for fetcher backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from drift.pipeline.fetching.schemas import FetchResult


class BaseFetcher(ABC):
    """Abstract base for URL fetchers."""

    @abstractmethod
    async def fetch(self, url: str) -> FetchResult:
        """Fetch a URL and return a FetchResult."""
        ...
