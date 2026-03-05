"""Factory for creating LLM providers by name."""

from __future__ import annotations

from drift.pipeline.extraction.providers.base import BaseLLMProvider


def create_provider(name: str, *, api_key: str | None = None) -> BaseLLMProvider:
    """Create an LLM provider by name.

    Args:
        name: "anthropic" or "openai".
        api_key: Override the default API key from .env.

    Returns:
        A configured BaseLLMProvider instance.
    """
    if name == "anthropic":
        from drift.pipeline.extraction.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=api_key)
    elif name == "openai":
        from drift.pipeline.extraction.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=api_key)
    else:
        raise ValueError(f"Unknown LLM provider: {name!r}. Must be 'anthropic' or 'openai'.")
