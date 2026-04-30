# flake8: noqa: E501
"""Tests for batch extraction and engine build_messages/parse_response — offline, no API keys required."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from drift.pipeline.extraction.engine import ExtractionEngine, ExtractionResult
from drift.pipeline.extraction.providers.base import (
    BaseLLMProvider,
    LLMRateLimitError,
    LLMResponse,
)

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


MINIMAL_CARTRIDGE = {
    "name": {
        "value": "Hornady Precision Hunter 6.5 CM 143gr ELD-X",
        "source_text": "Precision Hunter",
        "confidence": 0.9,
    },
    "manufacturer": {"value": "Hornady", "source_text": "Hornady", "confidence": 1.0},
    "caliber": {"value": "6.5 Creedmoor", "source_text": "6.5 Creedmoor", "confidence": 0.95},
    "bullet_name": {"value": "ELD-X", "source_text": "ELD-X", "confidence": 0.9},
    "bullet_weight_grains": {"value": 143, "source_text": "143 gr", "confidence": 1.0},
    "bc_g1": {"value": 0.625, "source_text": ".625 G1", "confidence": 0.9},
    "bc_g7": {"value": 0.315, "source_text": ".315 G7", "confidence": 0.9},
    "bullet_length_inches": {"value": None, "source_text": "", "confidence": 0.0},
    "muzzle_velocity_fps": {"value": 2700, "source_text": "2700 fps", "confidence": 0.95},
    "test_barrel_length_inches": {"value": 24, "source_text": '24"', "confidence": 0.9},
    "round_count": {"value": 20, "source_text": "20 rounds", "confidence": 0.95},
    "product_line": {"value": "Precision Hunter", "source_text": "Precision Hunter", "confidence": 0.9},
    "sku": {"value": "81499", "source_text": "81499", "confidence": 1.0},
}

MINIMAL_BULLET = {
    "name": {"value": "Test Bullet", "source_text": "Test Bullet", "confidence": 0.9},
    "manufacturer": {"value": "Acme", "source_text": "Acme", "confidence": 0.9},
    "bullet_diameter_inches": {"value": 0.264, "source_text": ".264", "confidence": 0.9},
    "weight_grains": {"value": 140, "source_text": "140 gr", "confidence": 1.0},
    "bc_g1": {"value": 0.610, "source_text": ".610", "confidence": 0.9},
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


# ── build_messages / parse_response ────────────────────────────────────────


class TestBuildMessages:
    def test_returns_system_and_user(self):
        engine = ExtractionEngine(provider=_make_mock_provider())
        system, user = engine.build_messages("<html>data</html>", "bullet")
        assert "extraction specialist" in system
        assert "<html>data</html>" in user

    def test_unknown_entity_type_raises(self):
        engine = ExtractionEngine(provider=_make_mock_provider())
        with pytest.raises(ValueError, match="Unknown entity_type"):
            engine.build_messages("<html></html>", "grenade")

    @pytest.mark.parametrize("entity_type", ["bullet", "cartridge", "rifle"])
    def test_all_entity_types_produce_messages(self, entity_type):
        engine = ExtractionEngine(provider=_make_mock_provider())
        system, user = engine.build_messages("<html></html>", entity_type)
        assert len(system) > 0
        assert len(user) > 0


class TestParseResponse:
    def test_parses_valid_bullet_json(self):
        engine = ExtractionEngine(provider=_make_mock_provider())
        result = engine.parse_response(
            json.dumps([MINIMAL_BULLET]), "bullet", usage={"input_tokens": 100, "output_tokens": 50}
        )
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 1
        assert result.entities[0].name.value == "Test Bullet"
        assert len(result.bc_sources) == 1

    def test_parses_markdown_fenced_json(self):
        engine = ExtractionEngine(provider=_make_mock_provider())
        raw = f"```json\n{json.dumps([MINIMAL_BULLET])}\n```"
        result = engine.parse_response(raw, "bullet")
        assert len(result.entities) == 1

    def test_invalid_json_raises(self):
        engine = ExtractionEngine(provider=_make_mock_provider())
        with pytest.raises(json.JSONDecodeError):
            engine.parse_response("not valid json", "bullet")

    def test_unknown_entity_type_raises(self):
        engine = ExtractionEngine(provider=_make_mock_provider())
        with pytest.raises(ValueError, match="Unknown entity_type"):
            engine.parse_response("[]", "grenade")

    def test_range_warnings_included(self):
        bullet_with_bad_bc = {**MINIMAL_BULLET, "bc_g1": {"value": 5.0, "source_text": "5.0", "confidence": 0.9}}
        engine = ExtractionEngine(provider=_make_mock_provider())
        result = engine.parse_response(json.dumps([bullet_with_bad_bc]), "bullet")
        assert any("bc_g1" in w for w in result.warnings)

    def test_parses_cartridge_with_bc(self):
        engine = ExtractionEngine(provider=_make_mock_provider())
        result = engine.parse_response(json.dumps([MINIMAL_CARTRIDGE]), "cartridge")
        assert len(result.entities) == 1
        assert result.entities[0].bc_g1.value == 0.625
        assert result.entities[0].bc_g7.value == 0.315

    def test_cartridge_produces_bc_sources(self):
        engine = ExtractionEngine(provider=_make_mock_provider())
        result = engine.parse_response(json.dumps([MINIMAL_CARTRIDGE]), "cartridge")
        assert len(result.bc_sources) == 2
        assert result.bc_sources[0].source == "cartridge_page"
        assert result.bc_sources[0].bullet_name == "ELD-X"
        types = {s.bc_type for s in result.bc_sources}
        assert types == {"g1", "g7"}


# ── Retry logic in extract() ──────────────────────────────────────────────


class TestExtractRetryLogic:
    def test_rate_limit_retries_then_succeeds(self):
        provider = _make_mock_provider()
        provider.complete.side_effect = [
            LLMRateLimitError("rate limited"),
            LLMResponse(text=json.dumps([MINIMAL_BULLET]), input_tokens=100, output_tokens=50),
        ]
        engine = ExtractionEngine(provider=provider)

        with patch("drift.pipeline.extraction.engine.time.sleep"):
            result = engine.extract("<html>test</html>", "bullet")
        assert len(result.entities) == 1

    def test_rate_limit_exhaustion_raises(self):
        provider = _make_mock_provider()
        provider.complete.side_effect = LLMRateLimitError("rate limited")
        engine = ExtractionEngine(provider=provider)

        with patch("drift.pipeline.extraction.engine.time.sleep"):
            with pytest.raises(LLMRateLimitError):
                engine.extract("<html>test</html>", "bullet")

    def test_none_response_raises_runtime_error(self):
        """If somehow the loop exits without a response, we get RuntimeError not AssertionError."""
        provider = _make_mock_provider()
        # Simulate a scenario where no response is set (shouldn't happen, but defensive)
        provider.complete.side_effect = [LLMRateLimitError("rate limited")] * 6
        engine = ExtractionEngine(provider=provider)

        with patch("drift.pipeline.extraction.engine.time.sleep"):
            with pytest.raises(LLMRateLimitError):
                engine.extract("<html>test</html>", "bullet")


# ── BatchExtractor.submit() ───────────────────────────────────────────────


class TestBatchSubmit:
    def test_submit_sends_cache_control_on_system_block(self):
        """Every batch request must wrap system with cache_control: ephemeral."""
        from drift.pipeline.extraction.batch import BatchExtractor, BatchItem

        engine = ExtractionEngine(provider=_make_mock_provider())
        client = MagicMock()
        client.messages.batches.create.return_value = MagicMock(id="batch_abc", processing_status="in_progress")

        extractor = BatchExtractor(engine=engine, client=client)
        items = [
            BatchItem(url_hash="h1", url="http://a", entity_type="bullet", reduced_html="<html>a</html>"),
            BatchItem(url_hash="h2", url="http://b", entity_type="cartridge", reduced_html="<html>b</html>"),
        ]
        batch_id = extractor.submit(items)
        assert batch_id == "batch_abc"

        requests_arg = client.messages.batches.create.call_args.kwargs["requests"]
        assert len(requests_arg) == 2
        for req in requests_arg:
            system = req["params"]["system"]
            assert isinstance(system, list)
            assert len(system) == 1
            assert system[0]["type"] == "text"
            assert system[0]["cache_control"] == {"type": "ephemeral"}
            assert len(system[0]["text"]) > 0


# ── BatchExtractor.collect() ──────────────────────────────────────────────


class TestBatchCollect:
    def _make_extractor(self):
        from drift.pipeline.extraction.batch import BatchExtractor

        engine = ExtractionEngine(provider=_make_mock_provider())
        client = MagicMock()
        return BatchExtractor(engine=engine, client=client)

    def _make_succeeded_entry(self, custom_id: str, text: str):
        content_block = MagicMock()
        content_block.text = text
        message = MagicMock()
        message.content = [content_block]
        message.usage.input_tokens = 100
        message.usage.output_tokens = 50
        message.usage.cache_creation_input_tokens = 0
        message.usage.cache_read_input_tokens = 0
        # Make hasattr(content_block, "text") work
        type(content_block).text = text

        entry = MagicMock()
        entry.custom_id = custom_id
        entry.result.type = "succeeded"
        entry.result.message = message
        return entry

    def _make_errored_entry(self, custom_id: str):
        entry = MagicMock()
        entry.custom_id = custom_id
        entry.result.type = "errored"
        entry.result.error = "Some API error"
        return entry

    def test_missing_entity_type_errors(self):
        """Critical 1: unknown url_hash should produce an error, not silently default."""
        extractor = self._make_extractor()
        entry = self._make_succeeded_entry("unknown_hash", json.dumps([MINIMAL_BULLET]))
        extractor._client.messages.batches.results.return_value = [entry]

        results = extractor.collect("batch123", {})  # empty item_types
        assert results["unknown_hash"].status == "errored"
        assert "Missing entity_type" in results["unknown_hash"].error

    def test_succeeded_entries_parsed(self):
        extractor = self._make_extractor()
        entry = self._make_succeeded_entry("hash1", json.dumps([MINIMAL_BULLET]))
        extractor._client.messages.batches.results.return_value = [entry]

        results = extractor.collect("batch123", {"hash1": "bullet"})
        assert results["hash1"].status == "succeeded"
        assert results["hash1"].result is not None
        assert len(results["hash1"].result.entities) == 1

    def test_errored_entries_recorded(self):
        extractor = self._make_extractor()
        entry = self._make_errored_entry("hash1")
        extractor._client.messages.batches.results.return_value = [entry]

        results = extractor.collect("batch123", {"hash1": "bullet"})
        assert results["hash1"].status == "errored"

    def test_parse_failure_saves_debug_file(self, tmp_path):
        """Critical 4: parse failures should save raw text to debug file."""
        extractor = self._make_extractor()
        entry = self._make_succeeded_entry("hash1", "NOT VALID JSON AT ALL")
        extractor._client.messages.batches.results.return_value = [entry]

        with patch("drift.pipeline.extraction.batch.BATCH_DIR", tmp_path):
            results = extractor.collect("batch123", {"hash1": "bullet"})

        assert results["hash1"].status == "errored"
        assert "Parse error" in results["hash1"].error
        debug_file = tmp_path / "debug" / "batch123_hash1.txt"
        assert debug_file.exists()
        assert debug_file.read_text() == "NOT VALID JSON AT ALL"

    def test_non_text_content_block_handled(self):
        """Important 7: non-text content block shouldn't crash the loop."""
        extractor = self._make_extractor()

        # Create an entry where content[0] has no .text attribute
        entry = MagicMock()
        entry.custom_id = "hash1"
        entry.result.type = "succeeded"
        content_block = MagicMock(spec=[])  # empty spec = no attributes
        entry.result.message.content = [content_block]

        extractor._client.messages.batches.results.return_value = [entry]

        results = extractor.collect("batch123", {"hash1": "bullet"})
        assert results["hash1"].status == "errored"
        assert "Non-text" in results["hash1"].error

    def test_empty_content_handled(self):
        """Important 7: empty content list shouldn't crash."""
        extractor = self._make_extractor()

        entry = MagicMock()
        entry.custom_id = "hash1"
        entry.result.type = "succeeded"
        entry.result.message.content = []

        extractor._client.messages.batches.results.return_value = [entry]

        results = extractor.collect("batch123", {"hash1": "bullet"})
        assert results["hash1"].status == "errored"


# ── BatchExtractor.poll() ─────────────────────────────────────────────────


class TestBatchPoll:
    def _make_extractor(self):
        from drift.pipeline.extraction.batch import BatchExtractor

        engine = ExtractionEngine(provider=_make_mock_provider())
        client = MagicMock()
        return BatchExtractor(engine=engine, client=client), client

    def test_poll_returns_on_ended(self):
        extractor, client = self._make_extractor()

        batch = MagicMock()
        batch.processing_status = "ended"
        batch.request_counts.succeeded = 5
        batch.request_counts.processing = 0
        batch.request_counts.errored = 0
        batch.request_counts.expired = 0
        batch.request_counts.canceled = 0
        client.messages.batches.retrieve.return_value = batch

        result = extractor.poll("batch123", timeout=60, interval=1)
        assert result["status"] == "ended"
        assert result["succeeded"] == 5

    def test_poll_timeout_raises(self):
        extractor, client = self._make_extractor()

        batch = MagicMock()
        batch.processing_status = "in_progress"
        batch.request_counts.succeeded = 0
        batch.request_counts.processing = 5
        batch.request_counts.errored = 0
        batch.request_counts.expired = 0
        batch.request_counts.canceled = 0
        client.messages.batches.retrieve.return_value = batch

        with patch("drift.pipeline.extraction.batch.time.sleep"):
            with patch("drift.pipeline.extraction.batch.time.monotonic") as mock_time:
                # Simulate: first call at t=0, second at t=61 (past timeout)
                mock_time.side_effect = [0.0, 61.0]
                with pytest.raises(TimeoutError):
                    extractor.poll("batch123", timeout=60, interval=10)

    def test_poll_retries_transient_errors(self):
        """Important 8: transient API errors should be retried."""
        import anthropic

        extractor, client = self._make_extractor()

        batch_ok = MagicMock()
        batch_ok.processing_status = "ended"
        batch_ok.request_counts.succeeded = 1
        batch_ok.request_counts.processing = 0
        batch_ok.request_counts.errored = 0
        batch_ok.request_counts.expired = 0
        batch_ok.request_counts.canceled = 0

        client.messages.batches.retrieve.side_effect = [
            anthropic.APIConnectionError(request=MagicMock()),
            batch_ok,
        ]

        with patch("drift.pipeline.extraction.batch.time.sleep"):
            result = extractor.poll("batch123", timeout=300, interval=30)
        assert result["status"] == "ended"


# ── _process_batch_results ─────────────────────────────────────────────────


class TestProcessBatchResults:
    def test_missing_entity_type_in_meta_errors(self):
        """Important 11: missing entity_type in metadata should be treated as error."""
        from scripts.pipeline_extract import _process_batch_results

        result_item = MagicMock()
        result_item.status = "succeeded"
        result_item.result = MagicMock()

        results = {"hash1": result_item}
        item_meta = {"hash1": {"url": "http://example.com"}}  # no entity_type
        flagged: list[dict] = []

        stats = _process_batch_results(results, item_meta, flagged)
        assert stats["errored"] == 1
        assert stats["succeeded"] == 0


# ── _write_flagged backup ────────────────────────────────────────────────


class TestWriteFlagged:
    def test_corrupt_flagged_file_backed_up(self, tmp_path):
        """Important 10: corrupt flagged.json should be backed up."""
        from scripts.pipeline_extract import REVIEW_DIR, _write_flagged

        flagged_path = tmp_path / "flagged.json"
        flagged_path.write_text("NOT JSON {{{", encoding="utf-8")

        with patch("scripts.pipeline_extract.REVIEW_DIR", tmp_path):
            result = _write_flagged(
                [
                    {
                        "url": "http://example.com",
                        "url_hash": "abc123",
                        "entity_type": "bullet",
                        "reason": "test",
                        "warnings": ["w1"],
                    }
                ]
            )

        backup_path = tmp_path / "flagged.json.bak"
        assert backup_path.exists()
        assert backup_path.read_text() == "NOT JSON {{{"
        # Original should now have valid JSON
        parsed = json.loads(flagged_path.read_text())
        assert len(parsed) == 1
