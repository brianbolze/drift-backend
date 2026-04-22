"""Tests for priority-aware manifest ordering in pipeline_extract._load_pending_items.

These tests verify the core behavioral claim of the priority-aware pipeline:
that --limit applied after a priority sort picks high-priority items first.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def pipeline_env(tmp_path, monkeypatch):
    """Redirect pipeline cache dirs into tmp_path and reload pipeline_extract."""
    pipeline_data = tmp_path / "pipeline"
    reduced = pipeline_data / "reduced"
    extracted = pipeline_data / "extracted"
    review = pipeline_data / "review"
    for d in (reduced, extracted, review):
        d.mkdir(parents=True)

    import drift.pipeline.config as config
    import scripts.pipeline_extract as pe

    monkeypatch.setattr(config, "REDUCED_DIR", reduced)
    monkeypatch.setattr(config, "EXTRACTED_DIR", extracted)
    monkeypatch.setattr(config, "REVIEW_DIR", review)
    # pipeline_extract imports these names at module scope, so patch there too.
    importlib.reload(pe)

    return pe, reduced


def _write_reduced_pair(reduced_dir: Path, url: str, entity_type: str = "cartridge") -> str:
    """Write the JSON+HTML pair that _load_pending_items expects for a URL."""
    from drift.pipeline.utils import url_hash

    uhash = url_hash(url)
    (reduced_dir / f"{uhash}.json").write_text(
        json.dumps({"url": url, "url_hash": uhash, "entity_type": entity_type}),
        encoding="utf-8",
    )
    (reduced_dir / f"{uhash}.html").write_text("<html></html>", encoding="utf-8")
    return uhash


def _write_manifest(tmp_path: Path, entries: list[dict]) -> Path:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(entries), encoding="utf-8")
    return manifest_path


def test_priority_sort_respects_ascending_priority(pipeline_env, tmp_path):
    """Pending items are sorted by priority ascending (1 = highest)."""
    pe, reduced = pipeline_env
    urls = [
        ("https://example.com/a", 3),
        ("https://example.com/b", 1),
        ("https://example.com/c", 2),
    ]
    for url, _ in urls:
        _write_reduced_pair(reduced, url)
    manifest_path = _write_manifest(
        tmp_path,
        [{"url": url, "entity_type": "cartridge", "priority": p} for url, p in urls],
    )

    pending, _ = pe._load_pending_items(manifest_path, limit=0, reextract=False)

    assert [item["url"] for item in pending] == [
        "https://example.com/b",  # priority 1
        "https://example.com/c",  # priority 2
        "https://example.com/a",  # priority 3
    ]


def test_manifest_index_breaks_priority_ties(pipeline_env, tmp_path):
    """Ties on priority preserve original manifest order (stable)."""
    pe, reduced = pipeline_env
    urls = ["https://example.com/first", "https://example.com/second", "https://example.com/third"]
    for url in urls:
        _write_reduced_pair(reduced, url)
    manifest_path = _write_manifest(
        tmp_path,
        [{"url": url, "entity_type": "cartridge", "priority": 1} for url in urls],
    )

    pending, _ = pe._load_pending_items(manifest_path, limit=0, reextract=False)

    assert [item["url"] for item in pending] == urls


def test_limit_applied_after_priority_sort(pipeline_env, tmp_path):
    """--limit N picks the top-N by priority, not the first N by file order.

    This is the main behavioral claim of the priority-aware pipeline.
    """
    pe, reduced = pipeline_env
    # Three entries, manifest order is low→high→mid priority — so hash-sorted
    # or manifest-order slicing would pick the wrong items under --limit 1.
    urls = [
        ("https://example.com/low", 3),
        ("https://example.com/high", 1),
        ("https://example.com/mid", 2),
    ]
    for url, _ in urls:
        _write_reduced_pair(reduced, url)
    manifest_path = _write_manifest(
        tmp_path,
        [{"url": url, "entity_type": "cartridge", "priority": p} for url, p in urls],
    )

    pending, _ = pe._load_pending_items(manifest_path, limit=1, reextract=False)

    assert len(pending) == 1
    assert pending[0]["url"] == "https://example.com/high"


def test_priority_max_filters_low_priority(pipeline_env, tmp_path):
    """--priority-max N excludes entries with priority > N entirely."""
    pe, reduced = pipeline_env
    urls = [("https://example.com/p1", 1), ("https://example.com/p2", 2), ("https://example.com/p3", 3)]
    for url, _ in urls:
        _write_reduced_pair(reduced, url)
    manifest_path = _write_manifest(
        tmp_path,
        [{"url": url, "entity_type": "cartridge", "priority": p} for url, p in urls],
    )

    pending, _ = pe._load_pending_items(manifest_path, limit=0, reextract=False, priority_max=2)

    assert sorted(item["url"] for item in pending) == [
        "https://example.com/p1",
        "https://example.com/p2",
    ]


def test_priority_max_zero_is_noop(pipeline_env, tmp_path):
    """priority_max=0 disables the filter — all entries pass through."""
    pe, reduced = pipeline_env
    urls = [("https://example.com/p1", 1), ("https://example.com/p99", 99)]
    for url, _ in urls:
        _write_reduced_pair(reduced, url)
    manifest_path = _write_manifest(
        tmp_path,
        [{"url": url, "entity_type": "cartridge", "priority": p} for url, p in urls],
    )

    pending, _ = pe._load_pending_items(manifest_path, limit=0, reextract=False, priority_max=0)

    assert len(pending) == 2


def test_missing_priority_sorts_last(pipeline_env, tmp_path):
    """Entries without a priority field sort after all priority-tagged entries."""
    pe, reduced = pipeline_env
    urls = [("https://example.com/untagged", None), ("https://example.com/tagged", 5)]
    for url, _ in urls:
        _write_reduced_pair(reduced, url)
    entries: list[dict] = []
    for url, p in urls:
        entry = {"url": url, "entity_type": "cartridge"}
        if p is not None:
            entry["priority"] = p
        entries.append(entry)
    manifest_path = _write_manifest(tmp_path, entries)

    pending, _ = pe._load_pending_items(manifest_path, limit=0, reextract=False)

    assert [item["url"] for item in pending] == [
        "https://example.com/tagged",
        "https://example.com/untagged",
    ]
