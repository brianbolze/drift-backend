"""Tests for LLM provider abstraction — offline, no API keys required."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from drift.pipeline.extraction.providers.base import (
    BaseLLMProvider,
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMRequestError,
    LLMResponse,
)
from drift.pipeline.extraction.providers.factory import create_provider

# ── LLMResponse ─────────────────────────────────────────────────────────────


class TestLLMResponse:
    def test_fields(self):
        r = LLMResponse(text="hello", input_tokens=10, output_tokens=5)
        assert r.text == "hello"
        assert r.input_tokens == 10
        assert r.output_tokens == 5
        assert r.cache_creation_input_tokens is None
        assert r.cache_read_input_tokens is None

    def test_cache_fields(self):
        r = LLMResponse(
            text="hello",
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=2000,
            cache_read_input_tokens=500,
        )
        assert r.cache_creation_input_tokens == 2000
        assert r.cache_read_input_tokens == 500

    def test_frozen(self):
        r = LLMResponse(text="hello", input_tokens=10, output_tokens=5)
        with pytest.raises(AttributeError):
            r.text = "changed"  # type: ignore[misc]


# ── Exception hierarchy ────────────────────────────────────────────────────


class TestExceptions:
    def test_auth_error_is_provider_error(self):
        assert issubclass(LLMAuthenticationError, LLMProviderError)

    def test_request_error_is_provider_error(self):
        assert issubclass(LLMRequestError, LLMProviderError)

    def test_rate_limit_error_is_provider_error(self):
        assert issubclass(LLMRateLimitError, LLMProviderError)

    def test_provider_error_is_exception(self):
        assert issubclass(LLMProviderError, Exception)


# ── AnthropicProvider ───────────────────────────────────────────────────────


class TestAnthropicProvider:
    def _make_provider(self):
        from drift.pipeline.extraction.providers.anthropic_provider import AnthropicProvider

        with patch("drift.pipeline.extraction.providers.anthropic_provider.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            provider = AnthropicProvider(api_key="test-key")
        return provider, mock_client, mock_anthropic

    def test_default_model(self):
        provider, _, _ = self._make_provider()
        assert provider.default_model == "claude-haiku-4-5-20251001"

    def test_complete_maps_response(self):
        provider, mock_client, _ = self._make_provider()

        mock_content = MagicMock()
        mock_content.text = '{"result": "ok"}'
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.usage.cache_creation_input_tokens = 2000
        mock_response.usage.cache_read_input_tokens = 0
        mock_client.messages.create.return_value = mock_response

        result = provider.complete(
            system="You are helpful.",
            user_message="Extract data.",
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
        )

        assert isinstance(result, LLMResponse)
        assert result.text == '{"result": "ok"}'
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.cache_creation_input_tokens == 2000
        assert result.cache_read_input_tokens == 0

        mock_client.messages.create.assert_called_once_with(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": "You are helpful.",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": "Extract data."}],
        )

    def test_complete_sends_cache_control_on_system_block(self):
        """System prompt must be wrapped with cache_control: ephemeral for prompt caching."""
        provider, mock_client, _ = self._make_provider()

        mock_content = MagicMock()
        mock_content.text = "[]"
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_response.usage.cache_creation_input_tokens = None
        mock_response.usage.cache_read_input_tokens = None
        mock_client.messages.create.return_value = mock_response

        provider.complete(system="sys prompt", user_message="msg", model="m", max_tokens=100)

        system_arg = mock_client.messages.create.call_args.kwargs["system"]
        assert isinstance(system_arg, list)
        assert len(system_arg) == 1
        assert system_arg[0]["type"] == "text"
        assert system_arg[0]["text"] == "sys prompt"
        assert system_arg[0]["cache_control"] == {"type": "ephemeral"}

    def test_auth_error_translated(self):
        import anthropic

        provider, mock_client, _ = self._make_provider()
        mock_client.messages.create.side_effect = anthropic.AuthenticationError(
            message="invalid key",
            response=MagicMock(status_code=401),
            body=None,
        )

        with pytest.raises(LLMAuthenticationError):
            provider.complete(system="sys", user_message="msg", model="test", max_tokens=100)

    def test_bad_request_error_translated(self):
        import anthropic

        provider, mock_client, _ = self._make_provider()
        mock_client.messages.create.side_effect = anthropic.BadRequestError(
            message="too large",
            response=MagicMock(status_code=400),
            body=None,
        )

        with pytest.raises(LLMRequestError):
            provider.complete(system="sys", user_message="msg", model="test", max_tokens=100)

    def test_rate_limit_error_translated(self):
        import anthropic

        provider, mock_client, _ = self._make_provider()
        mock_client.messages.create.side_effect = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )

        with pytest.raises(LLMRateLimitError):
            provider.complete(system="sys", user_message="msg", model="test", max_tokens=100)

    def test_generic_api_error_translated(self):
        import anthropic

        provider, mock_client, _ = self._make_provider()
        mock_client.messages.create.side_effect = anthropic.InternalServerError(
            message="server error",
            response=MagicMock(status_code=500),
            body=None,
        )

        with pytest.raises(LLMProviderError):
            provider.complete(system="sys", user_message="msg", model="test", max_tokens=100)

    def test_empty_response_raises(self):
        provider, mock_client, _ = self._make_provider()
        mock_response = MagicMock()
        mock_response.content = []
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response

        with pytest.raises(LLMRequestError, match="empty"):
            provider.complete(system="sys", user_message="msg", model="test", max_tokens=100)

    def test_missing_api_key_raises(self):
        from drift.pipeline.extraction.providers.anthropic_provider import AnthropicProvider

        with patch("drift.pipeline.extraction.providers.anthropic_provider.ANTHROPIC_API_KEY", ""):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                AnthropicProvider()


# ── OpenAIProvider ──────────────────────────────────────────────────────────


class TestOpenAIProvider:
    def _make_provider(self):
        from drift.pipeline.extraction.providers.openai_provider import OpenAIProvider

        with patch("drift.pipeline.extraction.providers.openai_provider.OPENAI_API_KEY", "test-key"):
            provider = OpenAIProvider(api_key="test-key")
        return provider

    def test_default_model(self):
        provider = self._make_provider()
        assert provider.default_model == "gpt-4.1-mini"

    def test_complete_maps_response(self):
        provider = self._make_provider()

        mock_choice = MagicMock()
        mock_choice.message.content = '{"result": "ok"}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 200
        mock_response.usage.completion_tokens = 80
        provider._client.chat.completions.create = MagicMock(return_value=mock_response)

        result = provider.complete(
            system="You are helpful.",
            user_message="Extract data.",
            model="gpt-4.1-mini",
            max_tokens=1024,
        )

        assert isinstance(result, LLMResponse)
        assert result.text == '{"result": "ok"}'
        assert result.input_tokens == 200
        assert result.output_tokens == 80

        provider._client.chat.completions.create.assert_called_once_with(
            model="gpt-4.1-mini",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Extract data."},
            ],
        )

    def test_auth_error_translated(self):
        provider = self._make_provider()
        import openai

        provider._client.chat.completions.create = MagicMock(
            side_effect=openai.AuthenticationError(
                message="invalid key",
                response=MagicMock(status_code=401),
                body=None,
            )
        )

        with pytest.raises(LLMAuthenticationError):
            provider.complete(system="sys", user_message="msg", model="test", max_tokens=100)

    def test_bad_request_error_translated(self):
        provider = self._make_provider()
        import openai

        provider._client.chat.completions.create = MagicMock(
            side_effect=openai.BadRequestError(
                message="too large",
                response=MagicMock(status_code=400),
                body=None,
            )
        )

        with pytest.raises(LLMRequestError):
            provider.complete(system="sys", user_message="msg", model="test", max_tokens=100)

    def test_rate_limit_error_translated(self):
        provider = self._make_provider()
        import openai

        provider._client.chat.completions.create = MagicMock(
            side_effect=openai.RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429),
                body=None,
            )
        )

        with pytest.raises(LLMRateLimitError):
            provider.complete(system="sys", user_message="msg", model="test", max_tokens=100)

    def test_generic_api_error_translated(self):
        provider = self._make_provider()
        import openai

        provider._client.chat.completions.create = MagicMock(
            side_effect=openai.InternalServerError(
                message="server error",
                response=MagicMock(status_code=500),
                body=None,
            )
        )

        with pytest.raises(LLMProviderError):
            provider.complete(system="sys", user_message="msg", model="test", max_tokens=100)

    def test_empty_response_raises(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.choices = []
        provider._client.chat.completions.create = MagicMock(return_value=mock_response)

        with pytest.raises(LLMRequestError, match="empty"):
            provider.complete(system="sys", user_message="msg", model="test", max_tokens=100)

    def test_missing_usage_raises(self):
        provider = self._make_provider()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"result": "ok"}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        provider._client.chat.completions.create = MagicMock(return_value=mock_response)

        with pytest.raises(LLMRequestError, match="no usage data"):
            provider.complete(system="sys", user_message="msg", model="test", max_tokens=100)

    def test_none_token_counts_default_to_zero(self):
        provider = self._make_provider()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"result": "ok"}'
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = None
        mock_usage.completion_tokens = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        provider._client.chat.completions.create = MagicMock(return_value=mock_response)

        result = provider.complete(system="sys", user_message="msg", model="test", max_tokens=100)

        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_missing_api_key_raises(self):
        from drift.pipeline.extraction.providers.openai_provider import OpenAIProvider

        with patch("drift.pipeline.extraction.providers.openai_provider.OPENAI_API_KEY", ""):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIProvider()


# ── Factory ─────────────────────────────────────────────────────────────────


class TestCreateProvider:
    def test_anthropic(self):
        from drift.pipeline.extraction.providers.anthropic_provider import AnthropicProvider

        with patch("drift.pipeline.extraction.providers.anthropic_provider.anthropic"):
            provider = create_provider("anthropic", api_key="test-key")
            assert isinstance(provider, AnthropicProvider)

    def test_openai(self):
        from drift.pipeline.extraction.providers.openai_provider import OpenAIProvider

        provider = create_provider("openai", api_key="test-key")
        assert isinstance(provider, OpenAIProvider)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_provider("gemini")


# ── ExtractionEngine with mock provider ─────────────────────────────────────


class TestExtractionEngineWithProvider:
    """Test that ExtractionEngine correctly delegates to a BaseLLMProvider."""

    def _make_mock_provider(self, response_json: list[dict]) -> BaseLLMProvider:
        """Create a mock provider that returns canned JSON."""
        provider = MagicMock(spec=BaseLLMProvider)
        provider.default_model = "mock-model-v1"
        provider.complete.return_value = LLMResponse(
            text=json.dumps(response_json),
            input_tokens=500,
            output_tokens=100,
        )
        return provider

    def test_extract_bullet_with_mock_provider(self):
        from drift.pipeline.extraction.engine import ExtractionEngine

        canned = [
            {
                "name": {"value": "ELD Match", "source_text": "ELD Match", "confidence": 0.95},
                "manufacturer": {"value": "Hornady", "source_text": "Hornady", "confidence": 1.0},
                "bullet_diameter_inches": {"value": 0.264, "source_text": "6.5mm .264", "confidence": 0.9},
                "weight_grains": {"value": 140, "source_text": "140 gr", "confidence": 1.0},
                "bc_g1": {"value": 0.610, "source_text": ".610", "confidence": 0.9},
                "bc_g7": {"value": 0.305, "source_text": ".305", "confidence": 0.9},
                "length_inches": {"value": None, "source_text": "", "confidence": 0.0},
                "sectional_density": {"value": 0.287, "source_text": ".287", "confidence": 0.9},
                "base_type": {"value": "boat_tail", "source_text": "BT", "confidence": 0.8},
                "tip_type": {"value": "polymer_tip", "source_text": "polymer", "confidence": 0.8},
                "type_tags": {"value": ["match"], "source_text": "match", "confidence": 0.7},
                "used_for": {"value": ["competition"], "source_text": "", "confidence": 0.5},
                "product_line": {"value": "ELD Match", "source_text": "ELD Match", "confidence": 0.9},
                "sku": {"value": "26331", "source_text": "#26331", "confidence": 0.95},
            }
        ]
        provider = self._make_mock_provider(canned)
        engine = ExtractionEngine(provider=provider)

        result = engine.extract("<html>test</html>", "bullet")

        assert len(result.entities) == 1
        assert result.entities[0].name.value == "ELD Match"
        assert result.model == "mock-model-v1"
        assert result.usage["input_tokens"] == 500
        assert result.usage["output_tokens"] == 100
        assert len(result.bc_sources) == 2

        # Verify provider was called with correct args
        provider.complete.assert_called_once()
        call_kwargs = provider.complete.call_args.kwargs
        assert call_kwargs["model"] == "mock-model-v1"
        assert "HTML content to extract from" in call_kwargs["user_message"]

    def test_extract_uses_explicit_model(self):
        from drift.pipeline.extraction.engine import ExtractionEngine

        canned = [
            {
                "name": {"value": "Test", "source_text": "Test", "confidence": 0.9},
                "manufacturer": {"value": "Test", "source_text": "Test", "confidence": 0.9},
                "caliber": {"value": "Test", "source_text": "Test", "confidence": 0.9},
                "weight_grains": {"value": 140, "source_text": "140", "confidence": 0.9},
                "bc_g1": {"value": None, "source_text": "", "confidence": 0.0},
                "bc_g7": {"value": None, "source_text": "", "confidence": 0.0},
                "length_inches": {"value": None, "source_text": "", "confidence": 0.0},
                "sectional_density": {"value": None, "source_text": "", "confidence": 0.0},
                "base_type": {"value": None, "source_text": "", "confidence": 0.0},
                "tip_type": {"value": None, "source_text": "", "confidence": 0.0},
                "type_tags": {"value": [], "source_text": "", "confidence": 0.0},
                "used_for": {"value": [], "source_text": "", "confidence": 0.0},
                "product_line": {"value": None, "source_text": "", "confidence": 0.0},
                "sku": {"value": None, "source_text": "", "confidence": 0.0},
            }
        ]
        provider = self._make_mock_provider(canned)
        engine = ExtractionEngine(provider=provider, model="custom-model-v2")

        result = engine.extract("<html>test</html>", "bullet")

        assert result.model == "custom-model-v2"
        call_kwargs = provider.complete.call_args.kwargs
        assert call_kwargs["model"] == "custom-model-v2"

    def test_extract_auth_error_propagates(self):
        from drift.pipeline.extraction.engine import ExtractionEngine

        provider = MagicMock(spec=BaseLLMProvider)
        provider.default_model = "mock-model"
        provider.complete.side_effect = LLMAuthenticationError("bad key")

        engine = ExtractionEngine(provider=provider)

        with pytest.raises(LLMAuthenticationError):
            engine.extract("<html>test</html>", "bullet")

    def test_extract_request_error_becomes_value_error(self):
        from drift.pipeline.extraction.engine import ExtractionEngine

        provider = MagicMock(spec=BaseLLMProvider)
        provider.default_model = "mock-model"
        provider.complete.side_effect = LLMRequestError("input too large")

        engine = ExtractionEngine(provider=provider)

        with pytest.raises(ValueError, match="LLM request failed"):
            engine.extract("<html>test</html>", "bullet")

    def test_default_provider_is_anthropic(self):
        """When no provider is given, ExtractionEngine defaults to Anthropic."""
        from drift.pipeline.extraction.engine import ExtractionEngine

        with patch("drift.pipeline.extraction.providers.anthropic_provider.anthropic"):
            with patch("drift.pipeline.extraction.providers.anthropic_provider.ANTHROPIC_API_KEY", "test-key"):
                engine = ExtractionEngine()

        from drift.pipeline.extraction.providers.anthropic_provider import AnthropicProvider

        assert isinstance(engine._provider, AnthropicProvider)
