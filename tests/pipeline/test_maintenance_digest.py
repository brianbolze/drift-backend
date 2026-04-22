"""Tests for scripts/pipeline_maintenance_digest.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DIGEST_PATH = _ROOT / "scripts" / "pipeline_maintenance_digest.py"


def _load_digest_module():
    spec = importlib.util.spec_from_file_location("pipeline_maintenance_digest", _DIGEST_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["pipeline_maintenance_digest"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


dg = _load_digest_module()


class TestParseWeek:
    def test_valid_format(self):
        assert dg._parse_week("2026-W17") == (2026, 17)

    def test_zero_padded_single_digit(self):
        assert dg._parse_week("2026-W05") == (2026, 5)

    def test_invalid_format_raises(self):
        with pytest.raises(SystemExit):
            dg._parse_week("2026/17")

    def test_non_numeric_raises(self):
        with pytest.raises(SystemExit):
            dg._parse_week("abc-Wxy")


class TestWeekBounds:
    def test_bounds_are_monday_to_next_monday(self):
        start, end = dg._week_bounds(2026, 17)
        # ISO week 17 of 2026 starts 2026-04-20 (Monday)
        assert start.date().isoformat() == "2026-04-20"
        assert end.date().isoformat() == "2026-04-27"
        assert start.tzinfo == timezone.utc


class TestRecordsInWeek:
    def test_filter_by_timestamp(self):
        start = datetime(2026, 4, 20, tzinfo=timezone.utc)
        end = datetime(2026, 4, 27, tzinfo=timezone.utc)
        records = [
            {"ts": "2026-04-19T23:59:59+00:00"},  # before
            {"ts": "2026-04-20T00:00:00+00:00"},  # inclusive start
            {"ts": "2026-04-23T12:00:00+00:00"},  # inside
            {"ts": "2026-04-27T00:00:00+00:00"},  # exclusive end
            {"ts": "2026-04-30T12:00:00+00:00"},  # after
        ]
        in_week = dg._records_in_week(records, "ts", start, end)
        assert len(in_week) == 2
        assert all("2026-04-2" in r["ts"] for r in in_week)

    def test_missing_key_skipped(self):
        start = datetime(2026, 4, 20, tzinfo=timezone.utc)
        end = datetime(2026, 4, 27, tzinfo=timezone.utc)
        records = [{"no_ts": "value"}, {"ts": "2026-04-22T12:00:00+00:00"}]
        assert len(dg._records_in_week(records, "ts", start, end)) == 1

    def test_malformed_ts_skipped(self):
        start = datetime(2026, 4, 20, tzinfo=timezone.utc)
        end = datetime(2026, 4, 27, tzinfo=timezone.utc)
        records = [{"ts": "not-a-timestamp"}]
        assert dg._records_in_week(records, "ts", start, end) == []


class TestReadJsonl:
    def test_reads_lines(self, tmp_path):
        path = tmp_path / "log.jsonl"
        path.write_text('{"a": 1}\n{"b": 2}\n', encoding="utf-8")
        records = dg._read_jsonl(path)
        assert records == [{"a": 1}, {"b": 2}]

    def test_missing_file_returns_empty(self, tmp_path):
        assert dg._read_jsonl(tmp_path / "nope.jsonl") == []

    def test_blank_lines_skipped(self, tmp_path):
        path = tmp_path / "log.jsonl"
        path.write_text('{"a": 1}\n\n{"b": 2}\n', encoding="utf-8")
        assert len(dg._read_jsonl(path)) == 2

    def test_corrupt_line_skipped(self, tmp_path):
        path = tmp_path / "log.jsonl"
        path.write_text('{"a": 1}\nnot json\n{"b": 2}\n', encoding="utf-8")
        records = dg._read_jsonl(path)
        assert len(records) == 2


class TestBuildDigest:
    def test_empty_state_renders_graceful_placeholders(self, monkeypatch, tmp_path):
        # Point all log paths at empty/nonexistent locations
        monkeypatch.setattr(dg, "DISCOVERED_LOG", tmp_path / "missing_discovered.jsonl")
        monkeypatch.setattr(dg, "REMOVED_LOG", tmp_path / "missing_removed.jsonl")
        monkeypatch.setattr(dg, "SITEMAPS_DIR", tmp_path / "sitemaps")
        monkeypatch.setattr(dg, "REVIEW_FLAGGED", tmp_path / "missing_flagged.json")
        monkeypatch.setattr(dg, "PATCHES_DRAFTS", tmp_path / "missing_drafts")

        content = dg.build_digest(2026, 17)
        assert "Pipeline Maintenance Digest — 2026-W17" in content
        assert "No sitemap activity this week" in content
        assert "No draft patches" in content
        assert "No flagged items file present" in content
        assert "Primitive 2" in content  # placeholder mentions future primitive
        assert "Primitive 3a" in content

    def test_populated_sitemap_section(self, monkeypatch, tmp_path):
        log = tmp_path / "discovered.jsonl"
        log.write_text(
            json.dumps(
                {
                    "discovered_at": "2026-04-22T12:00:00+00:00",
                    "manufacturer_slug": "hornady",
                    "entity_type": "bullet",
                }
            )
            + "\n"
            + json.dumps(
                {
                    "discovered_at": "2026-04-22T12:00:00+00:00",
                    "manufacturer_slug": "hornady",
                    "entity_type": "cartridge",
                }
            )
            + "\n"
            + json.dumps(
                {
                    "discovered_at": "2026-01-01T12:00:00+00:00",  # different week, excluded
                    "manufacturer_slug": "hornady",
                    "entity_type": "bullet",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(dg, "DISCOVERED_LOG", log)
        monkeypatch.setattr(dg, "REMOVED_LOG", tmp_path / "missing.jsonl")
        monkeypatch.setattr(dg, "SITEMAPS_DIR", tmp_path / "sitemaps_nodir")
        monkeypatch.setattr(dg, "REVIEW_FLAGGED", tmp_path / "missing.json")
        monkeypatch.setattr(dg, "PATCHES_DRAFTS", tmp_path / "missing_drafts")

        content = dg.build_digest(2026, 17)
        assert "New URLs discovered:** 2" in content
        assert "hornady" in content
        # Per-week filtering worked — the 2026-01-01 record did not contribute
        assert "**New URLs discovered:** 3" not in content

    def test_draft_patches_counted(self, monkeypatch, tmp_path):
        drafts = tmp_path / "drafts"
        drafts.mkdir()
        (drafts / "001_review.yaml").write_text("# stub", encoding="utf-8")
        (drafts / "002_review.yaml").write_text("# stub", encoding="utf-8")

        monkeypatch.setattr(dg, "DISCOVERED_LOG", tmp_path / "missing.jsonl")
        monkeypatch.setattr(dg, "REMOVED_LOG", tmp_path / "missing.jsonl")
        monkeypatch.setattr(dg, "SITEMAPS_DIR", tmp_path / "nodir")
        monkeypatch.setattr(dg, "REVIEW_FLAGGED", tmp_path / "missing.json")
        monkeypatch.setattr(dg, "PATCHES_DRAFTS", drafts)

        content = dg.build_digest(2026, 17)
        assert "2 patch(es) awaiting" in content
        assert "001_review.yaml" in content
