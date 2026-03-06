"""OpenAI LLM provider — wraps the OpenAI Chat Completions API."""

from __future__ import annotations

from drift.pipeline.config import OPENAI_API_KEY
from drift.pipeline.extraction.providers.base import (
    BaseLLMProvider,
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMRequestError,
    LLMResponse,
)


class OpenAIProvider(BaseLLMProvider):
    """LLM provider backed by the OpenAI Chat Completions API."""

    def __init__(self, api_key: str | None = None):
        try:
            import openai
        except ImportError as e:
            raise ImportError(
                f"Failed to import openai package ({e}). " f"Install with: pip install 'drift-ballistics[openai]'"
            ) from e

        self._api_key = api_key or OPENAI_API_KEY
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY not set. Export it or add to .env")
        self._client = openai.OpenAI(api_key=self._api_key)
        self._openai = openai  # Keep ref for exception classes

    @property
    def default_model(self) -> str:
        return "gpt-4.1-mini"

    def complete(
        self,
        *,
        system: str,
        user_message: str,
        model: str,
        max_tokens: int,
    ) -> LLMResponse:
        try:
            # Use max_completion_tokens for newer models (gpt-4o, gpt-5 series)
            # and max_tokens for older models
            params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
            }

            # Models that require max_completion_tokens instead of max_tokens
            if any(prefix in model.lower() for prefix in ["gpt-4o", "gpt-5", "o1"]):
                params["max_completion_tokens"] = max_tokens
            else:
                params["max_tokens"] = max_tokens

            response = self._client.chat.completions.create(**params)
        except self._openai.AuthenticationError as e:
            raise LLMAuthenticationError(str(e)) from e
        except self._openai.RateLimitError as e:
            raise LLMRateLimitError(str(e)) from e
        except self._openai.BadRequestError as e:
            raise LLMRequestError(str(e)) from e
        except self._openai.APIError as e:
            raise LLMProviderError(str(e)) from e

        choice = response.choices[0] if response.choices else None
        if not choice or not choice.message or not choice.message.content:
            raise LLMRequestError("OpenAI returned empty response")

        usage = response.usage
        if not usage:
            raise LLMRequestError("OpenAI returned no usage data")

        if choice.finish_reason == "length":
            raise LLMRequestError(f"Response truncated (finish_reason=length, {usage.completion_tokens} tokens).")

        return LLMResponse(
            text=choice.message.content,
            input_tokens=usage.prompt_tokens or 0,
            output_tokens=usage.completion_tokens or 0,
        )
