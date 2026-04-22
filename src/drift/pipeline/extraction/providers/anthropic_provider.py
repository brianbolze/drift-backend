"""Anthropic LLM provider — wraps the Anthropic Messages API."""

from __future__ import annotations

import anthropic

from drift.pipeline.config import ANTHROPIC_API_KEY
from drift.pipeline.extraction.providers.base import (
    BaseLLMProvider,
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMRequestError,
    LLMResponse,
)


class AnthropicProvider(BaseLLMProvider):
    """LLM provider backed by the Anthropic Messages API."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or ANTHROPIC_API_KEY
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY not set. Export it or add to .env")
        self._client = anthropic.Anthropic(api_key=self._api_key)

    @property
    def client(self) -> anthropic.Anthropic:
        """Expose the underlying Anthropic client (needed for batch API access)."""
        return self._client

    @property
    def default_model(self) -> str:
        return "claude-haiku-4-5-20251001"

    def complete(
        self,
        *,
        system: str,
        user_message: str,
        model: str,
        max_tokens: int,
    ) -> LLMResponse:
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.AuthenticationError as e:
            raise LLMAuthenticationError(str(e)) from e
        except anthropic.RateLimitError as e:
            raise LLMRateLimitError(str(e)) from e
        except anthropic.BadRequestError as e:
            raise LLMRequestError(str(e)) from e
        except anthropic.APIError as e:
            raise LLMProviderError(str(e)) from e

        if not response.content or not hasattr(response.content[0], "text"):
            raise LLMRequestError(f"Anthropic returned empty/non-text response (stop_reason={response.stop_reason})")

        if response.stop_reason == "max_tokens":
            raise LLMRequestError(
                f"Response truncated (stop_reason=max_tokens, {response.usage.output_tokens} tokens). "
                "Input may be too large for max_tokens budget."
            )

        return LLMResponse(
            text=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_creation_input_tokens=getattr(response.usage, "cache_creation_input_tokens", None),
            cache_read_input_tokens=getattr(response.usage, "cache_read_input_tokens", None),
        )
