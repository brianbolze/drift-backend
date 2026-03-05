"""OpenAI LLM provider — wraps the OpenAI Chat Completions API."""

from __future__ import annotations

from drift.pipeline.config import OPENAI_API_KEY
from drift.pipeline.extraction.providers.base import (
    BaseLLMProvider,
    LLMAuthenticationError,
    LLMRequestError,
    LLMResponse,
)


class OpenAIProvider(BaseLLMProvider):
    """LLM provider backed by the OpenAI Chat Completions API."""

    def __init__(self, api_key: str | None = None):
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package not installed. Install with: pip install 'drift-ballistics[openai]'"
            ) from None

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
            response = self._client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
            )
        except self._openai.AuthenticationError as e:
            raise LLMAuthenticationError(str(e)) from e
        except self._openai.BadRequestError as e:
            raise LLMRequestError(str(e)) from e

        choice = response.choices[0] if response.choices else None
        if not choice or not choice.message or not choice.message.content:
            raise LLMRequestError("OpenAI returned empty response")

        usage = response.usage
        if not usage:
            raise LLMRequestError("OpenAI returned no usage data")

        return LLMResponse(
            text=choice.message.content,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )
