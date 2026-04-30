"""Tests for scripts/sitemap_watch.py — pure-function coverage.

Network-dependent paths are exercised via fetch-stub fixtures; real HTTP is
never made in tests.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SITEMAP_WATCH_PATH = _ROOT / "scripts" / "sitemap_watch.py"


def _load_sitemap_watch():
    spec = importlib.util.spec_from_file_location("sitemap_watch", _SITEMAP_WATCH_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["sitemap_watch"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


sw = _load_sitemap_watch()


# ── Classification ───────────────────────────────────────────────────────────


class TestMatchAny:
    def test_matches_single_pattern(self):
        assert sw._match_any("https://example.com/bullets/eld-match", [r"/bullets/"])

    def test_no_match(self):
        assert not sw._match_any("https://example.com/blog/article", [r"/bullets/"])

    def test_multiple_patterns_any_match(self):
        assert sw._match_any("https://example.com/ammunition/eld-x", [r"/bullets/", r"/ammunition/"])

    def test_empty_patterns(self):
        assert not sw._match_any("https://example.com/bullets/x", [])


class TestClassifyEntityType:
    def test_matches_bullet_rule(self):
        rules = [(r"/bullets/", "bullet", "high"), (r"/ammunition/", "cartridge", "high")]
        assert sw._classify_entity_type("https://example.com/bullets/eld-match", rules) == ("bullet", "high")

    def test_matches_cartridge_rule(self):
        rules = [(r"/bullets/", "bullet", "high"), (r"/ammunition/", "cartridge", "high")]
        assert sw._classify_entity_type("https://example.com/ammunition/eld-x", rules) == ("cartridge", "high")

    def test_first_rule_wins(self):
        rules = [(r"/products/", "bullet", "medium"), (r"/products/ammo", "cartridge", "high")]
        # /products/ matches first even for ammo URLs if it comes first in list
        assert sw._classify_entity_type("https://example.com/products/ammo/x", rules) == ("bullet", "medium")

    def test_unclassified_fallback(self):
        rules = [(r"/bullets/", "bullet", "high")]
        assert sw._classify_entity_type("https://example.com/mystery/x", rules) == ("unclassified", "low")

    def test_empty_rules(self):
        assert sw._classify_entity_type("https://example.com/anything", []) == ("unclassified", "low")


class TestHasRejectedCaliber:
    def test_detects_pistol_caliber(self):
        assert sw._has_rejected_caliber("https://example.com/products/9mm-luger-124gr", ["9mm Luger"])

    def test_case_insensitive(self):
        assert sw._has_rejected_caliber("https://example.com/PRODUCTS/9MM-LUGER", ["9mm Luger"])

    def test_no_match(self):
        assert not sw._has_rejected_caliber("https://example.com/products/6.5-creedmoor", ["9mm Luger", "12 GA"])

    def test_empty_rejected_list(self):
        assert not sw._has_rejected_caliber("https://example.com/anything", [])


# ── XML parsing ──────────────────────────────────────────────────────────────


_URLSET_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/bullets/a</loc></url>
  <url><loc>https://example.com/bullets/b</loc></url>
  <url><loc>https://example.com/blog/post</loc></url>
</urlset>
"""

_URLSET_XML_NO_NS = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset>
  <url><loc>https://example.com/bullets/a</loc></url>
  <url><loc>https://example.com/bullets/b</loc></url>
</urlset>
"""

_SITEMAP_INDEX_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap_products.xml</loc></sitemap>
</sitemapindex>
"""


class _StubClient:
    """Minimal httpx.Client stand-in returning canned bodies per URL."""

    def __init__(self, responses: dict[str, bytes]):
        self._responses = responses

    def get(self, url: str):
        if url not in self._responses:
            raise RuntimeError(f"unexpected URL {url!r}")

        class _Resp:
            def __init__(self, content: bytes):
                self.content = content
                self.headers = {}

            def raise_for_status(self):
                pass

        return _Resp(self._responses[url])


class TestParseSitemapUrls:
    def test_urlset_namespaced(self):
        client = _StubClient({})
        urls = sw._parse_sitemap_urls(_URLSET_XML, client)
        assert urls == {
            "https://example.com/bullets/a",
            "https://example.com/bullets/b",
            "https://example.com/blog/post",
        }

    def test_urlset_no_namespace(self):
        client = _StubClient({})
        urls = sw._parse_sitemap_urls(_URLSET_XML_NO_NS, client)
        assert urls == {
            "https://example.com/bullets/a",
            "https://example.com/bullets/b",
        }

    def test_sitemap_index_recurses(self):
        client = _StubClient({"https://example.com/sitemap_products.xml": _URLSET_XML})
        urls = sw._parse_sitemap_urls(_SITEMAP_INDEX_XML, client)
        assert "https://example.com/bullets/a" in urls
        assert "https://example.com/bullets/b" in urls

    def test_depth_limit(self):
        # Construct a sitemap index that recurses to itself — _parse_sitemap_urls
        # must stop before blowing the stack.
        client = _StubClient({"https://example.com/self.xml": _SITEMAP_INDEX_XML})
        # Rewrite _SITEMAP_INDEX_XML child to point back to itself
        looping = _SITEMAP_INDEX_XML.replace(
            b"https://example.com/sitemap_products.xml",
            b"https://example.com/self.xml",
        )
        client = _StubClient({"https://example.com/self.xml": looping})
        urls = sw._parse_sitemap_urls(looping, client)
        # Depth cap kicks in and returns an empty set once recursion deep enough
        assert urls == set()

    def test_malformed_xml_returns_empty(self):
        client = _StubClient({})
        urls = sw._parse_sitemap_urls(b"not xml", client)
        assert urls == set()


# ── Snapshot I/O ─────────────────────────────────────────────────────────────


class TestSnapshotIO:
    def test_load_missing_returns_empty_shape(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sw, "SITEMAPS_DIR", tmp_path)
        snap = sw._load_snapshot("nonexistent")
        assert snap == {"slug": "nonexistent", "urls": [], "last_run_at": None}

    def test_save_then_load_roundtrip(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sw, "SITEMAPS_DIR", tmp_path)
        sw._save_snapshot("test", {"https://a.com", "https://b.com"}, "https://a.com/sitemap.xml")
        snap = sw._load_snapshot("test")
        assert set(snap["urls"]) == {"https://a.com", "https://b.com"}
        assert snap["sitemap_url"] == "https://a.com/sitemap.xml"
        assert snap["url_count"] == 2
        assert snap["last_run_at"] is not None

    def test_corrupt_snapshot_treated_as_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sw, "SITEMAPS_DIR", tmp_path)
        (tmp_path / "broken.json").write_text("{ not json", encoding="utf-8")
        snap = sw._load_snapshot("broken")
        assert snap["urls"] == []


# ── Entry construction ───────────────────────────────────────────────────────


class TestBuildEntry:
    def test_entry_shape_matches_cowork_format(self):
        config = {"expected_manufacturer": "Hornady"}
        rules = [(r"/bullets/", "bullet", "high")]
        entry = sw._build_entry("https://www.hornady.com/bullets/eld-match-140gr", "hornady", config, rules)

        assert entry["url"] == "https://www.hornady.com/bullets/eld-match-140gr"
        assert entry["entity_type"] == "bullet"
        assert entry["expected_manufacturer"] == "Hornady"
        assert entry["expected_caliber"] is None
        assert entry["confidence"] == "high"
        assert "Discovered via sitemap" in entry["notes"]

    def test_unclassified_fallback(self):
        config = {"expected_manufacturer": "Hornady"}
        rules = [(r"/bullets/", "bullet", "high")]
        entry = sw._build_entry("https://www.hornady.com/mystery/x", "hornady", config, rules)

        assert entry["entity_type"] == "unclassified"
        assert entry["confidence"] == "low"


# ── End-to-end run (stubbed fetcher) ─────────────────────────────────────────


class TestWatchManufacturer:
    @pytest.fixture
    def tmp_sitemaps_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sw, "SITEMAPS_DIR", tmp_path / "sitemaps")
        monkeypatch.setattr(sw, "DISCOVERED_DIR", tmp_path / "sitemaps" / "discovered")
        monkeypatch.setattr(sw, "DISCOVERED_LOG", tmp_path / "sitemaps" / "discovered_urls.jsonl")
        monkeypatch.setattr(sw, "REMOVED_LOG", tmp_path / "sitemaps" / "removed_urls.jsonl")
        return tmp_path / "sitemaps"

    def test_first_run_flags_all_as_new(self, tmp_sitemaps_dir):
        client = _StubClient({"https://example.com/sitemap.xml": _URLSET_XML})
        config = {
            "sitemap_url": "https://example.com/sitemap.xml",
            "expected_manufacturer": "Example",
            "include_patterns": [r"/bullets/"],
            "exclude_patterns": [],
            "entity_type_rules": [(r"/bullets/", "bullet", "high")],
        }
        stats = sw.watch_manufacturer("example", config, set(), [], client, dry_run=False)

        assert stats["status"] == "ok"
        assert stats["sitemap_urls"] == 3
        assert stats["filtered"] == 2
        assert stats["new"] == 2
        assert stats["removed"] == 0

        # Snapshot written
        snap_path = tmp_sitemaps_dir / "example.json"
        assert snap_path.exists()
        snap = json.loads(snap_path.read_text())
        assert len(snap["urls"]) == 2

        # Discovered file written in cowork format
        discovered_files = list((tmp_sitemaps_dir / "discovered").glob("example_*.json"))
        assert len(discovered_files) == 1
        entries = json.loads(discovered_files[0].read_text())
        assert len(entries) == 2
        assert all(e["entity_type"] == "bullet" for e in entries)

    def test_second_run_no_changes(self, tmp_sitemaps_dir):
        # Prime snapshot
        (tmp_sitemaps_dir).mkdir(parents=True, exist_ok=True)
        sw._save_snapshot(
            "example",
            {"https://example.com/bullets/a", "https://example.com/bullets/b"},
            "https://example.com/sitemap.xml",
        )

        client = _StubClient({"https://example.com/sitemap.xml": _URLSET_XML})
        config = {
            "sitemap_url": "https://example.com/sitemap.xml",
            "expected_manufacturer": "Example",
            "include_patterns": [r"/bullets/"],
            "exclude_patterns": [],
            "entity_type_rules": [(r"/bullets/", "bullet", "high")],
        }
        stats = sw.watch_manufacturer("example", config, set(), [], client, dry_run=False)

        assert stats["new"] == 0
        assert stats["removed"] == 0

    def test_manifest_urls_excluded_from_new(self, tmp_sitemaps_dir):
        client = _StubClient({"https://example.com/sitemap.xml": _URLSET_XML})
        config = {
            "sitemap_url": "https://example.com/sitemap.xml",
            "expected_manufacturer": "Example",
            "include_patterns": [r"/bullets/"],
            "exclude_patterns": [],
            "entity_type_rules": [(r"/bullets/", "bullet", "high")],
        }
        manifest_urls = {"https://example.com/bullets/a"}
        stats = sw.watch_manufacturer("example", config, manifest_urls, [], client, dry_run=False)

        assert stats["new"] == 1  # only b is new; a is already in manifest

    def test_removed_urls_tracked(self, tmp_sitemaps_dir):
        # Prime snapshot with an extra URL that's no longer in sitemap
        (tmp_sitemaps_dir).mkdir(parents=True, exist_ok=True)
        sw._save_snapshot(
            "example",
            {"https://example.com/bullets/a", "https://example.com/bullets/b", "https://example.com/bullets/gone"},
            "https://example.com/sitemap.xml",
        )

        client = _StubClient({"https://example.com/sitemap.xml": _URLSET_XML})
        config = {
            "sitemap_url": "https://example.com/sitemap.xml",
            "expected_manufacturer": "Example",
            "include_patterns": [r"/bullets/"],
            "exclude_patterns": [],
            "entity_type_rules": [(r"/bullets/", "bullet", "high")],
        }
        stats = sw.watch_manufacturer("example", config, set(), [], client, dry_run=False)

        assert stats["new"] == 0
        assert stats["removed"] == 1

        removed_log = tmp_sitemaps_dir / "removed_urls.jsonl"
        assert removed_log.exists()
        lines = removed_log.read_text().strip().split("\n")
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["url"] == "https://example.com/bullets/gone"
        assert rec["manufacturer_slug"] == "example"

    def test_dry_run_writes_nothing(self, tmp_sitemaps_dir):
        client = _StubClient({"https://example.com/sitemap.xml": _URLSET_XML})
        config = {
            "sitemap_url": "https://example.com/sitemap.xml",
            "expected_manufacturer": "Example",
            "include_patterns": [r"/bullets/"],
            "exclude_patterns": [],
            "entity_type_rules": [(r"/bullets/", "bullet", "high")],
        }
        stats = sw.watch_manufacturer("example", config, set(), [], client, dry_run=True)

        assert stats["new"] == 2
        assert not (tmp_sitemaps_dir / "example.json").exists()
        assert not (tmp_sitemaps_dir / "discovered").exists()

    def test_rejected_caliber_filter(self, tmp_sitemaps_dir):
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/bullets/6-5-creedmoor-140gr</loc></url>
  <url><loc>https://example.com/bullets/9mm-luger-124gr</loc></url>
</urlset>"""
        client = _StubClient({"https://example.com/sitemap.xml": xml})
        config = {
            "sitemap_url": "https://example.com/sitemap.xml",
            "expected_manufacturer": "Example",
            "include_patterns": [r"/bullets/"],
            "exclude_patterns": [],
            "entity_type_rules": [(r"/bullets/", "bullet", "high")],
        }
        stats = sw.watch_manufacturer("example", config, set(), ["9mm Luger"], client, dry_run=False)

        # 9mm Luger URL rejected; only the Creedmoor survives
        assert stats["filtered"] == 1
        assert stats["new"] == 1
