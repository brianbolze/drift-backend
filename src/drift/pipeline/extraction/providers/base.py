"""Base interface for LLM providers and shared types."""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod


@dataclasses.dataclass(frozen=True, slots=True)
class LLMResponse:
    """Normalized LLM completion result."""

    text: str
    input_tokens: int
    output_tokens: int


class LLMProviderError(Exception):
    """Base exception for LLM provider errors (provider-agnostic)."""


class LLMAuthenticationError(LLMProviderError):
    """API key is invalid or missing."""


class LLMRateLimitError(LLMProviderError):
    """Provider rate limit exceeded — caller should back off and retry."""


class LLMRequestError(LLMProviderError):
    """Request was rejected (e.g., input too large, invalid model)."""


class BaseLLMProvider(ABC):
    """Abstract base for LLM providers."""

    @property
    @abstractmethod
    def default_model(self) -> str:
        """The default model string for this provider."""
        ...

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        user_message: str,
        model: str,
        max_tokens: int,
    ) -> LLMResponse:
        """Send a single system+user prompt and return the text response with token counts."""
        ...
