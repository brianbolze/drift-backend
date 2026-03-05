"""Smoke tests for pipeline components — offline, no API keys required."""

from __future__ import annotations

from drift.pipeline.extraction.engine import validate_ranges
from drift.pipeline.extraction.schemas import (
    ExtractedBullet,
    ExtractedCartridge,
    ExtractedRifleModel,
    ExtractedValue,
)
from drift.pipeline.reduction.reducer import HtmlReducer
from drift.pipeline.resolution.resolver import (
    MatchResult,
    ResolutionResult,
    _get_value,
    _name_similarity,
    _normalize,
)

# ── HtmlReducer ─────────────────────────────────────────────────────────────


class TestHtmlReducer:
    def test_preserves_product_content(self):
        html = """<html><head><style>body{color:red}</style></head>
        <body><h1>Product Name</h1><p>Weight: 130gr</p></body></html>"""
        reducer = HtmlReducer()
        result, meta = reducer.reduce(html)
        assert "Product Name" in result
        assert "130gr" in result

    def test_removes_styles(self):
        html = """<html><head>
        <style>.big{font-size:99px}</style>
        <link rel="stylesheet" href="theme.css">
        </head><body><p>Content</p></body></html>"""
        reducer = HtmlReducer()
        result, meta = reducer.reduce(html)
        assert "font-size" not in result
        assert "theme.css" not in result

    def test_preserves_json_ld(self):
        html = """<html><body>
        <script type="application/ld+json">{"@type":"Product","name":"Test"}</script>
        <p>Content</p></body></html>"""
        reducer = HtmlReducer()
        result, meta = reducer.reduce(html)
        assert "Product" in result
        assert "Test" in result

    def test_removes_tracking_scripts(self):
        html = """<html><body>
        <script>gtag('event', 'page_view');</script>
        <script>fbq('track', 'PageView');</script>
        <p>Content</p></body></html>"""
        reducer = HtmlReducer(target_size=50)
        result, meta = reducer.reduce(html)
        assert "gtag" not in result
        assert "fbq" not in result

    def test_progressive_reduction_stops_at_target(self):
        html = "<html><body><p>Short content</p></body></html>"
        reducer = HtmlReducer(target_size=100_000)
        _, meta = reducer.reduce(html)
        # Should stop early since already under target
        assert meta["under_target"] is True
        assert meta["steps_applied"] == 1  # Only first step needed

    def test_metadata_structure(self):
        html = "<html><body><p>Test</p></body></html>"
        reducer = HtmlReducer()
        _, meta = reducer.reduce(html)
        assert "original_size" in meta
        assert "reduced_size" in meta
        assert "reduction_ratio" in meta
        assert "steps_applied" in meta
        assert "steps" in meta
        assert "under_target" in meta
        assert isinstance(meta["steps"], list)


# ── Extraction schemas ───────────────────────────────────────────────────────


class TestExtractionSchemas:
    def test_extracted_value_basic(self):
        ev = ExtractedValue[str](value="test", source_text="test text", confidence=0.9)
        assert ev.value == "test"
        assert ev.confidence == 0.9

    def test_extracted_value_nullable(self):
        ev = ExtractedValue[float | None](value=None, source_text="", confidence=0.0)
        assert ev.value is None

    def test_extracted_bullet_full(self):
        data = {
            "name": {"value": "ELD Match", "source_text": "ELD Match", "confidence": 0.95},
            "manufacturer": {"value": "Hornady", "source_text": "Hornady", "confidence": 1.0},
            "caliber": {"value": "6.5 Creedmoor", "source_text": "6.5 Creedmoor", "confidence": 0.9},
            "weight_grains": {"value": 140, "source_text": "140 gr", "confidence": 1.0},
            "bc_g1": {"value": 0.610, "source_text": ".610", "confidence": 0.9},
            "bc_g7": {"value": 0.305, "source_text": ".305", "confidence": 0.9},
            "length_inches": {"value": None, "source_text": "", "confidence": 0.0},
            "sectional_density": {"value": 0.287, "source_text": ".287", "confidence": 0.9},
            "base_type": {"value": "boat_tail", "source_text": "boat tail", "confidence": 0.8},
            "tip_type": {"value": "polymer_tip", "source_text": "polymer tip", "confidence": 0.8},
            "type_tags": {"value": ["match", "long_range"], "source_text": "match", "confidence": 0.7},
            "used_for": {"value": ["competition"], "source_text": "", "confidence": 0.5},
            "sku": {"value": "26331", "source_text": "#26331", "confidence": 0.95},
        }
        bullet = ExtractedBullet.model_validate(data)
        assert bullet.name.value == "ELD Match"
        assert bullet.weight_grains.value == 140
        assert bullet.bc_g1.value == 0.610

    def test_extracted_cartridge(self):
        data = {
            "name": {"value": "Gold Medal Match", "source_text": "Gold Medal", "confidence": 0.9},
            "manufacturer": {"value": "Federal", "source_text": "Federal", "confidence": 1.0},
            "caliber": {"value": ".308 Winchester", "source_text": ".308 Win", "confidence": 0.9},
            "bullet_name": {"value": "Sierra MatchKing", "source_text": "Sierra", "confidence": 0.8},
            "bullet_weight_grains": {"value": 175, "source_text": "175 gr", "confidence": 1.0},
            "muzzle_velocity_fps": {"value": 2600, "source_text": "2600 fps", "confidence": 0.95},
            "test_barrel_length_inches": {"value": 24, "source_text": "24 in", "confidence": 0.9},
            "round_count": {"value": 20, "source_text": "20 rounds", "confidence": 0.95},
            "product_line": {"value": "Gold Medal", "source_text": "Gold Medal", "confidence": 0.9},
            "sku": {"value": "GM308M", "source_text": "GM308M", "confidence": 1.0},
        }
        cart = ExtractedCartridge.model_validate(data)
        assert cart.muzzle_velocity_fps.value == 2600
        assert cart.round_count.value == 20

    def test_extracted_rifle_model(self):
        data = {
            "model": {"value": "T3x Tac A1", "source_text": "T3x Tac A1", "confidence": 0.95},
            "manufacturer": {"value": "Tikka", "source_text": "Tikka", "confidence": 1.0},
            "caliber": {"value": ".308 Winchester", "source_text": ".308 Win", "confidence": 0.9},
            "barrel_length_inches": {"value": 24, "source_text": '24"', "confidence": 0.9},
            "twist_rate": {"value": "1:11", "source_text": "1:11", "confidence": 0.9},
            "weight_lbs": {"value": 10.3, "source_text": "10.3 lbs", "confidence": 0.9},
            "barrel_material": {"value": "stainless steel", "source_text": "stainless", "confidence": 0.7},
            "barrel_finish": {"value": None, "source_text": "", "confidence": 0.0},
            "model_family": {"value": "Tikka T3x", "source_text": "T3x", "confidence": 0.8},
        }
        rifle = ExtractedRifleModel.model_validate(data)
        assert rifle.model.value == "T3x Tac A1"
        assert rifle.weight_lbs.value == 10.3


# ── Validation ───────────────────────────────────────────────────────────────


class TestValidation:
    def test_valid_ranges_pass(self):
        entities = [
            {
                "name": {"value": "Test Bullet"},
                "bc_g1": {"value": 0.5},
                "weight_grains": {"value": 140},
                "muzzle_velocity_fps": {"value": 2700},
            }
        ]
        warnings = validate_ranges(entities)
        assert len(warnings) == 0

    def test_bc_out_of_range(self):
        entities = [{"name": {"value": "Bad BC"}, "bc_g1": {"value": 5.0}}]
        warnings = validate_ranges(entities)
        assert len(warnings) == 1
        assert "bc_g1=5.0" in warnings[0]

    def test_weight_out_of_range(self):
        entities = [{"name": {"value": "Too Heavy"}, "weight_grains": {"value": 1000}}]
        warnings = validate_ranges(entities)
        assert len(warnings) == 1

    def test_null_values_ignored(self):
        entities = [{"name": {"value": "Null"}, "bc_g1": {"value": None}}]
        warnings = validate_ranges(entities)
        assert len(warnings) == 0


# ── Resolver utilities ───────────────────────────────────────────────────────


class TestResolverUtils:
    def test_normalize_strips_punctuation(self):
        assert _normalize("6.5 Creedmoor") == "6 5 creedmoor"
        assert _normalize("  Hornady  ") == "hornady"
        assert _normalize(".308 Winchester") == "308 winchester"

    def test_name_similarity_identical(self):
        assert _name_similarity("Hornady ELD Match", "Hornady ELD Match") == 1.0

    def test_name_similarity_reordered(self):
        score = _name_similarity("Hornady ELD Match", "ELD Match Hornady")
        assert score == 1.0  # Same words, just reordered

    def test_name_similarity_partial(self):
        score = _name_similarity("ELD Match", "ELD Match 140gr Hornady")
        assert 0.3 < score < 0.8  # Partial overlap

    def test_name_similarity_no_overlap(self):
        score = _name_similarity("Hornady", "Federal")
        assert score == 0.0

    def test_get_value_from_extracted_value(self):
        assert _get_value({"name": {"value": "Test", "confidence": 0.9}}, "name") == "Test"

    def test_get_value_from_plain(self):
        assert _get_value({"weight": 130}, "weight") == 130

    def test_get_value_missing(self):
        assert _get_value({}, "name", "default") == "default"

    def test_get_value_none(self):
        assert _get_value({"sku": None}, "sku") is None

    def test_match_result_defaults(self):
        mr = MatchResult(matched=False)
        assert mr.entity_id is None
        assert mr.confidence == 0.0
        assert mr.method == ""

    def test_resolution_result_defaults(self):
        rr = ResolutionResult(entity_type="bullet")
        assert rr.manufacturer_id is None
        assert rr.unresolved_refs == []
        assert rr.warnings == []
        assert rr.match.matched is False
