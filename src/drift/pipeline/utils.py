"""Shared pipeline utilities."""

from __future__ import annotations

import hashlib


def url_hash(url: str) -> str:
    """Deterministic short hash for a URL, used as cache key."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]
