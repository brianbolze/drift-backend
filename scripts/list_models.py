#!/usr/bin/env python3
"""List available LLM models for each provider by querying their APIs."""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path so we can import drift modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from drift.pipeline.config import ANTHROPIC_API_KEY, OPENAI_API_KEY


def get_openai_models():
    """Fetch available models from OpenAI API."""
    if not OPENAI_API_KEY:
        return None, "OPENAI_API_KEY not set"

    try:
        import openai

        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        models = client.models.list()

        # Filter for only GPT models and sort by capability
        gpt_models = [m.id for m in models if m.id.startswith(("gpt-5", "gpt-4", "gpt-3.5"))]

        # Define priority order for most relevant models (2026)
        priority_models = [
            "gpt-5-pro",  # Most capable
            "gpt-5",  # Standard GPT-5
            "gpt-5-mini",  # Balanced
            "gpt-5-nano",  # Small & fast
            "gpt-5-codex",  # Code-optimized
            "gpt-5.3-chat-latest",
            "gpt-5.2-pro",
            "gpt-5.1",
            "gpt-4.1-nano",
            "gpt-4.1-mini",
            "gpt-4o",
            "gpt-4o-mini",
        ]

        # Get models in priority order if they exist
        available_priority = [m for m in priority_models if m in gpt_models]

        # Add any other GPT-5 or GPT-4.1 models not in priority list (up to 10 total)
        other_models = [m for m in sorted(gpt_models) if m not in priority_models and ("gpt-5" in m or "gpt-4.1" in m)]

        all_models = available_priority + other_models[: max(0, 10 - len(available_priority))]

        return all_models[:10], None

    except ImportError:
        return None, "OpenAI package not installed (pip install openai)"
    except Exception as e:
        return None, f"Error fetching OpenAI models: {e}"


def get_anthropic_models():
    """Fetch available models from Anthropic API."""
    if not ANTHROPIC_API_KEY:
        return None, "ANTHROPIC_API_KEY not set"

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        # Try to use the models.list() API if available (2026)
        if hasattr(client, "models") and hasattr(client.models, "list"):
            try:
                models_response = client.models.list()
                # Extract model IDs from the response
                model_ids = [m.id for m in models_response]

                # Priority order for Claude models
                priority_order = [
                    "claude-opus-4-6",  # Latest Opus
                    "claude-sonnet-4-6",  # Latest Sonnet
                    "claude-opus-4-5",  # Previous Opus
                    "claude-haiku-4-5",  # Fast & efficient
                    "claude-sonnet-4-5",  # Previous Sonnet
                ]

                # Sort by priority, then add any other 4.x models
                available_priority = [m for m in priority_order if m in model_ids]
                other_models = [m for m in model_ids if m not in priority_order and "claude" in m and "4" in m]

                all_models = available_priority + other_models[: max(0, 8 - len(available_priority))]
                return all_models[:8], None

            except Exception as e:
                # Fall back to hardcoded list if API fails
                pass

        # Fallback: hardcoded list if models API not available
        models = [
            "claude-4-opus",
            "claude-4-sonnet",
            "claude-4-haiku",
            "claude-haiku-4-5-20251001",
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
        ]

        return models, None

    except ImportError:
        return None, "Anthropic package not installed (pip install anthropic)"
    except Exception as e:
        return None, f"Error: {e}"


def format_model_description(model: str) -> str:
    """Add helpful descriptions to model names."""
    descriptions = {
        # OpenAI GPT-5 series (2026)
        "gpt-5-pro": "Most capable GPT-5 model",
        "gpt-5": "Standard GPT-5 model",
        "gpt-5-mini": "Balanced cost/performance",
        "gpt-5-nano": "Small, fast, cost-effective",
        "gpt-5-codex": "Optimized for code generation",
        "gpt-5.3-chat-latest": "Latest GPT-5.3 chat model",
        "gpt-5.2-pro": "GPT-5.2 Pro variant",
        "gpt-5.1": "GPT-5.1 standard",
        "gpt-4.1-nano": "Smallest GPT-4.1 model",
        "gpt-4.1-mini": "Small, fast, cost-effective",
        "gpt-4o": "GPT-4 optimized for speed",
        "gpt-4o-mini": "Smaller GPT-4o variant",
        # Anthropic Claude 4.x series (2026)
        "claude-opus-4-6": "Most capable Claude 4.6",
        "claude-sonnet-4-6": "Balanced Claude 4.6",
        "claude-opus-4-5-20251101": "Claude Opus 4.5",
        "claude-haiku-4-5-20251001": "Fast & efficient 4.5",
        "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
        "claude-opus-4-1-20250805": "Claude Opus 4.1",
        "claude-opus-4-20250514": "Claude Opus 4.0",
        "claude-sonnet-4-20250514": "Claude Sonnet 4.0",
        "claude-3-haiku-20240307": "Legacy Claude 3 Haiku",
        # Generic fallbacks
        "claude-4-opus": "Most capable Claude 4",
        "claude-4-sonnet": "Balanced Claude 4",
        "claude-4-haiku": "Fast Claude 4",
    }

    desc = descriptions.get(model, "")
    return f"  {model:<35} # {desc}" if desc else f"  {model}"


def main():
    print("═══════════════════════════════════════════════════════════════════════════")
    print(" Available LLM Models for Data Extraction")
    print("═══════════════════════════════════════════════════════════════════════════")
    print()

    # Try to get current defaults from the providers
    default_anthropic = None
    default_openai = None
    try:
        from drift.pipeline.extraction.providers.anthropic_provider import AnthropicProvider
        from drift.pipeline.extraction.providers.openai_provider import OpenAIProvider

        default_anthropic = AnthropicProvider.__dict__["default_model"].fget(None)
        default_openai = OpenAIProvider.__dict__["default_model"].fget(None)
    except Exception:
        pass

    # Anthropic Models
    print("Anthropic (Claude) Models:")
    anthropic_models, error = get_anthropic_models()

    if error:
        print(f"  ⚠ {error}")
    elif anthropic_models:
        for model in anthropic_models:
            line = format_model_description(model)
            if default_anthropic and model == default_anthropic:
                print(f"{line} [DEFAULT]")
            else:
                print(line)
    else:
        print("  No models available")

    print()

    # OpenAI Models
    print("OpenAI (GPT) Models:")
    openai_models, error = get_openai_models()

    if error:
        print(f"  ⚠ {error}")
    elif openai_models:
        for model in openai_models:
            line = format_model_description(model)
            if default_openai and model == default_openai:
                print(f"{line} [DEFAULT]")
            else:
                print(line)
    else:
        print("  No models available")

    print()
    print("Usage Examples:")

    # Show examples with actual available models
    if anthropic_models and len(anthropic_models) > 0:
        print(f"  make pipeline-extract PIPELINE_MODEL={anthropic_models[0]}")

    if openai_models and len(openai_models) > 0:
        print(f"  make pipeline-extract-openai PIPELINE_MODEL={openai_models[0]}")

    print()
    print("Note: Model availability depends on your API access level.")
    print("      Set OPENAI_API_KEY and ANTHROPIC_API_KEY environment variables.")
    print()
    print("═══════════════════════════════════════════════════════════════════════════")


if __name__ == "__main__":
    main()
