"""Tests for the parser-first extraction tier.

Covers two layers:
  - Engine fallthrough: the ExtractionEngine's cascade from parser → LLM.
  - Golden-set driver: per-parser fixture loading that individual parser PRs
    plug into.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pydantic
import pytest

from drift.pipeline.extraction.engine import ExtractionEngine
from drift.pipeline.extraction.parsers import (
    BaseParser,
    ParserError,
    ParserResult,
)
from drift.pipeline.extraction.providers.base import BaseLLMProvider, LLMResponse
from drift.pipeline.extraction.schemas import (
    ExtractedBCSource,
    ExtractedBullet,
    ExtractedValue,
)

FIXTURES_ROOT = Path(__file__).parent.parent / "fixtures" / "parsers"


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_mock_provider(response_json: list[dict] | None = None) -> BaseLLMProvider:
    provider = MagicMock(spec=BaseLLMProvider)
    provider.default_model = "mock-model-v1"
    if response_json is not None:
        provider.complete.return_value = LLMResponse(
            text=json.dumps(response_json),
            input_tokens=500,
            output_tokens=100,
        )
    return provider


def _make_bullet(**overrides) -> ExtractedBullet:
    """Build a valid ExtractedBullet with sensible defaults."""
    base = {
        "name": ExtractedValue(value="Test Bullet", source_text="Test Bullet", confidence=1.0),
        "manufacturer": ExtractedValue(value="Acme", source_text="Acme", confidence=1.0),
        "bullet_diameter_inches": ExtractedValue(value=0.264, source_text=".264", confidence=1.0),
        "weight_grains": ExtractedValue(value=140, source_text="140 gr", confidence=1.0),
        "bc_g1": ExtractedValue(value=0.610, source_text=".610", confidence=1.0),
        "bc_g7": ExtractedValue(value=None, source_text="", confidence=0.0),
        "length_inches": ExtractedValue(value=None, source_text="", confidence=0.0),
        "sectional_density": ExtractedValue(value=None, source_text="", confidence=0.0),
        "base_type": ExtractedValue(value=None, source_text="", confidence=0.0),
        "tip_type": ExtractedValue(value=None, source_text="", confidence=0.0),
        "type_tags": ExtractedValue(value=[], source_text="", confidence=0.0),
        "used_for": ExtractedValue(value=[], source_text="", confidence=0.0),
        "product_line": ExtractedValue(value=None, source_text="", confidence=0.0),
        "sku": ExtractedValue(value=None, source_text="", confidence=0.0),
    }
    base.update(overrides)
    return ExtractedBullet(**base)


def _llm_bullet_dict() -> dict:
    """Minimal raw-JSON bullet payload for the LLM mock."""
    return {
        "name": {"value": "LLM Bullet", "source_text": "LLM Bullet", "confidence": 0.9},
        "manufacturer": {"value": "Acme", "source_text": "Acme", "confidence": 0.9},
        "bullet_diameter_inches": {"value": 0.264, "source_text": ".264", "confidence": 0.9},
        "weight_grains": {"value": 140, "source_text": "140 gr", "confidence": 1.0},
        "bc_g1": {"value": 0.6, "source_text": ".6", "confidence": 0.9},
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


class _FakeParser(BaseParser):
    """Configurable parser for driving the engine cascade under test."""

    name = "fake"
    supported_entity_types = frozenset({"bullet"})

    def __init__(
        self,
        *,
        result: ParserResult | None = None,
        raise_parser_error: bool = False,
        raise_unexpected: bool = False,
        return_none: bool = False,
    ):
        self.result = result
        self.raise_parser_error = raise_parser_error
        self.raise_unexpected = raise_unexpected
        self.return_none = return_none
        self.parse_calls: list[tuple[str, str]] = []

    def parse(self, raw_html: str, url: str, entity_type: str) -> ParserResult | None:
        self.parse_calls.append((url, entity_type))
        if self.raise_parser_error:
            raise ParserError("simulated failure")
        if self.raise_unexpected:
            raise RuntimeError("totally unexpected")
        if self.return_none:
            return None
        return self.result


def _install_fake_parser(parser: BaseParser):
    """Return a context manager-style patch that makes ``parser`` resolve for example.com."""

    def _resolver(domain: str):
        return parser if domain == "example.com" else None

    return patch(
        "drift.pipeline.extraction.parsers.get_parser_for_domain",
        side_effect=_resolver,
    )


# ── Engine cascade ─────────────────────────────────────────────────────────


class TestEngineParserCascade:
    def test_parser_hit_short_circuits_llm(self):
        parser = _FakeParser(result=ParserResult(entities=[_make_bullet()], bc_sources=[]))
        provider = _make_mock_provider()
        engine = ExtractionEngine(provider=provider)

        with _install_fake_parser(parser):
            result = engine.extract(
                "<html>reduced</html>",
                "bullet",
                url="https://example.com/a",
                raw_html="<html>raw</html>",
            )

        assert result.extraction_method == "parser"
        assert result.parser_name == "fake"
        assert len(result.entities) == 1
        provider.complete.assert_not_called()
        assert result.usage == {"input_tokens": 0, "output_tokens": 0}

    def test_parser_returns_none_falls_through(self):
        parser = _FakeParser(return_none=True)
        provider = _make_mock_provider([_llm_bullet_dict()])
        engine = ExtractionEngine(provider=provider)

        with _install_fake_parser(parser):
            result = engine.extract(
                "<html>reduced</html>",
                "bullet",
                url="https://example.com/a",
                raw_html="<html>raw</html>",
            )

        assert result.extraction_method == "parser_fellthrough_to_llm"
        assert result.parser_name is None
        provider.complete.assert_called_once()

    def test_parser_error_falls_through(self):
        parser = _FakeParser(raise_parser_error=True)
        provider = _make_mock_provider([_llm_bullet_dict()])
        engine = ExtractionEngine(provider=provider)

        with _install_fake_parser(parser):
            result = engine.extract(
                "<html>reduced</html>",
                "bullet",
                url="https://example.com/a",
                raw_html="<html>raw</html>",
            )
        assert result.extraction_method == "parser_fellthrough_to_llm"
        provider.complete.assert_called_once()

    def test_unexpected_exception_falls_through(self):
        parser = _FakeParser(raise_unexpected=True)
        provider = _make_mock_provider([_llm_bullet_dict()])
        engine = ExtractionEngine(provider=provider)

        with _install_fake_parser(parser):
            result = engine.extract(
                "<html>reduced</html>",
                "bullet",
                url="https://example.com/a",
                raw_html="<html>raw</html>",
            )
        assert result.extraction_method == "parser_fellthrough_to_llm"
        provider.complete.assert_called_once()

    def test_out_of_range_parser_output_falls_through(self):
        # BC 5.0 is way outside 0.05..1.2 — should fail validate_ranges and fall through.
        bad = _make_bullet(bc_g1=ExtractedValue(value=5.0, source_text="5.0", confidence=1.0))
        parser = _FakeParser(result=ParserResult(entities=[bad], bc_sources=[]))
        provider = _make_mock_provider([_llm_bullet_dict()])
        engine = ExtractionEngine(provider=provider)

        with _install_fake_parser(parser):
            result = engine.extract(
                "<html>reduced</html>",
                "bullet",
                url="https://example.com/a",
                raw_html="<html>raw</html>",
            )
        assert result.extraction_method == "parser_fellthrough_to_llm"
        provider.complete.assert_called_once()

    def test_unsupported_entity_type_skips_parser(self):
        """Parser only declares bullet support — cartridge requests never reach parse()."""
        parser = _FakeParser(result=ParserResult(entities=[_make_bullet()], bc_sources=[]))
        provider = _make_mock_provider()
        provider.complete.return_value = LLMResponse(
            text=json.dumps(
                [
                    {
                        "name": {"value": "X", "source_text": "X", "confidence": 1.0},
                        "manufacturer": {"value": "Y", "source_text": "Y", "confidence": 1.0},
                        "caliber": {"value": "6.5 Creedmoor", "source_text": "6.5 CM", "confidence": 1.0},
                        "bullet_name": {"value": "ELD-X", "source_text": "ELD-X", "confidence": 1.0},
                        "bullet_weight_grains": {"value": 143, "source_text": "143", "confidence": 1.0},
                        "bc_g1": {"value": 0.6, "source_text": ".6", "confidence": 1.0},
                        "bc_g7": {"value": None, "source_text": "", "confidence": 0.0},
                        "bullet_length_inches": {"value": None, "source_text": "", "confidence": 0.0},
                        "muzzle_velocity_fps": {"value": 2700, "source_text": "2700", "confidence": 1.0},
                        "test_barrel_length_inches": {"value": None, "source_text": "", "confidence": 0.0},
                        "round_count": {"value": 20, "source_text": "20", "confidence": 1.0},
                        "product_line": {"value": None, "source_text": "", "confidence": 0.0},
                        "sku": {"value": None, "source_text": "", "confidence": 0.0},
                    }
                ]
            ),
            input_tokens=500,
            output_tokens=100,
        )
        engine = ExtractionEngine(provider=provider)

        with _install_fake_parser(parser):
            result = engine.extract(
                "<html>reduced</html>",
                "cartridge",
                url="https://example.com/a",
                raw_html="<html>raw</html>",
            )
        assert result.extraction_method == "llm"
        assert parser.parse_calls == []  # parser never invoked
        provider.complete.assert_called_once()

    def test_no_parser_registered_pure_llm(self):
        provider = _make_mock_provider([_llm_bullet_dict()])
        engine = ExtractionEngine(provider=provider)

        # No parser patch — registry returns None for this domain.
        result = engine.extract(
            "<html>reduced</html>",
            "bullet",
            url="https://no-parser.example/a",
            raw_html="<html>raw</html>",
        )
        assert result.extraction_method == "llm"
        assert result.parser_name is None

    def test_missing_raw_html_falls_through_without_labeling(self):
        """If raw HTML isn't available, the parser can't run — behave exactly as today."""
        parser = _FakeParser(result=ParserResult(entities=[_make_bullet()], bc_sources=[]))
        provider = _make_mock_provider([_llm_bullet_dict()])
        engine = ExtractionEngine(provider=provider)

        with _install_fake_parser(parser):
            result = engine.extract(
                "<html>reduced</html>",
                "bullet",
                url="https://example.com/a",
                raw_html=None,
            )
        # Parser never ran; label as pure llm rather than fellthrough.
        assert result.extraction_method == "llm"
        assert parser.parse_calls == []

    def test_no_url_bypasses_parser(self):
        """Legacy callers passing only (reduced_html, entity_type) keep LLM behavior."""
        provider = _make_mock_provider([_llm_bullet_dict()])
        engine = ExtractionEngine(provider=provider)

        result = engine.extract("<html>reduced</html>", "bullet")
        assert result.extraction_method == "llm"
        provider.complete.assert_called_once()

    def test_try_parse_short_circuits_pydantic_drift(self):
        """If a parser ever returns a payload that won't revalidate (future schema drift),
        the engine falls through rather than propagating the failure."""
        parser = _FakeParser(result=ParserResult(entities=[_make_bullet()], bc_sources=[]))
        provider = _make_mock_provider()
        engine = ExtractionEngine(provider=provider)

        with _install_fake_parser(parser):
            # Force the pydantic revalidation step to fail — simulates a parser
            # emitting a model-valid object whose dump fails to re-import.
            with patch.object(
                ExtractedBullet,
                "model_validate",
                side_effect=pydantic.ValidationError.from_exception_data("ExtractedBullet", []),
            ):
                provider.complete.return_value = LLMResponse(
                    text=json.dumps([_llm_bullet_dict()]), input_tokens=10, output_tokens=5
                )
                result = engine.extract(
                    "<html>reduced</html>",
                    "bullet",
                    url="https://example.com/a",
                    raw_html="<html>raw</html>",
                )
        # Should not blow up — should have gone to LLM.
        assert result.extraction_method == "parser_fellthrough_to_llm"


class TestTryParseDirect:
    def test_try_parse_no_parser_returns_none(self):
        engine = ExtractionEngine(provider=_make_mock_provider())
        assert engine.try_parse("https://unknown.example/a", "bullet", "<html>x</html>") is None

    def test_try_parse_no_raw_html_returns_none(self):
        parser = _FakeParser(result=ParserResult(entities=[_make_bullet()], bc_sources=[]))
        engine = ExtractionEngine(provider=_make_mock_provider())
        with _install_fake_parser(parser):
            assert engine.try_parse("https://example.com/a", "bullet", None) is None
            assert engine.try_parse("https://example.com/a", "bullet", "") is None

    def test_try_parse_passes_bc_sources_through(self):
        bc = ExtractedBCSource(bullet_name="Test", bc_type="g1", bc_value=0.5, source="manufacturer")
        parser = _FakeParser(result=ParserResult(entities=[_make_bullet()], bc_sources=[bc], warnings=["note"]))
        engine = ExtractionEngine(provider=_make_mock_provider())
        with _install_fake_parser(parser):
            result = engine.try_parse("https://example.com/a", "bullet", "<html></html>")
        assert result is not None
        assert result.bc_sources == [bc]
        assert result.warnings == ["note"]


# ── Golden-set driver ──────────────────────────────────────────────────────


def _discover_cases(parser_name: str) -> list[Path]:
    """Discover (html, expected.json) fixture pairs for a named parser.

    Returns a list of HTML paths; the matching .expected.json is alongside.
    """
    folder = FIXTURES_ROOT / parser_name
    if not folder.exists():
        return []
    return sorted(folder.glob("*.html"))


def run_golden_case(parser: BaseParser, html_path: Path) -> tuple[list[dict], list[dict]]:
    """Run a parser against a fixture and return (actual_entities_dump, expected_entities).

    Expected JSON format:
        {
          "url": "...",
          "entity_type": "bullet",
          "entities": [<ExtractedBullet.model_dump()>, ...],
          "bc_sources": [<ExtractedBCSource.model_dump()>, ...]  # optional
        }
    """
    expected_path = html_path.with_suffix(".expected.json")
    if not expected_path.exists():
        raise FileNotFoundError(f"Missing expected fixture: {expected_path}")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))

    html = html_path.read_text(encoding="utf-8")
    result = parser.parse(html, expected["url"], expected["entity_type"])

    if expected.get("expect_none", False):
        assert result is None, f"{html_path.name}: expected parser to decline (None), got result"
        return [], []

    assert result is not None, f"{html_path.name}: parser returned None unexpectedly"
    actual = [e.model_dump() for e in result.entities]
    return actual, expected["entities"]


def test_golden_driver_discovers_fixtures():
    """Sanity check: the helper handles absent parser directories gracefully."""
    assert _discover_cases("nonexistent_parser") == []


# ── Hornady parser golden set ──────────────────────────────────────────────


_HORNADY_CASES = _discover_cases("hornady")


@pytest.mark.skipif(not _HORNADY_CASES, reason="No Hornady fixtures present")
@pytest.mark.parametrize("html_path", _HORNADY_CASES, ids=lambda p: p.stem)
def test_hornady_parser_matches_golden(html_path):
    from drift.pipeline.extraction.parsers.hornady import HornadyParser

    actual, expected = run_golden_case(HornadyParser(), html_path)
    assert actual == expected, f"Golden mismatch in {html_path.name}"


# ── Sierra parser golden set ──────────────────────────────────────────────


_SIERRA_CASES = _discover_cases("sierra")


@pytest.mark.skipif(not _SIERRA_CASES, reason="No Sierra fixtures present")
@pytest.mark.parametrize("html_path", _SIERRA_CASES, ids=lambda p: p.stem)
def test_sierra_parser_matches_golden(html_path):
    from drift.pipeline.extraction.parsers.sierra import SierraParser

    actual, expected = run_golden_case(SierraParser(), html_path)
    assert actual == expected, f"Golden mismatch in {html_path.name}"
