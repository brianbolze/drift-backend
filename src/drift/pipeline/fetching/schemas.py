"""Fetch result schema — the output of any fetcher backend."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class FetchResult(BaseModel):
    """Result of fetching a single URL."""

    model_config = ConfigDict(str_strip_whitespace=True)

    url: str
    html: str
    status_code: int
    fetched_at: datetime = Field(default_factory=_utcnow)
    fetcher_backend: str = Field(..., description="httpx or firecrawl")
    content_hash: str = Field(default="", description="SHA-256 hex digest of the HTML content")
