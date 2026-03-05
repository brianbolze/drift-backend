"""Smoke tests for pipeline components — offline, no API keys required."""

from __future__ import annotations

import json

from drift.pipeline.extraction.engine import _extract_bc_sources, _parse_json_response, validate_ranges
from drift.pipeline.extraction.schemas import (
    ExtractedBullet,
    ExtractedCartridge,
    ExtractedRifleModel,
    ExtractedValue,
)
from drift.pipeline.reduction.reducer import HtmlReducer
from drift.pipeline.resolution.resolver import (
    EntityResolver,
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
    def test_normalize_strips_punctuation_preserves_periods(self):
        assert _normalize("6.5 Creedmoor") == "6.5 creedmoor"
        assert _normalize("  Hornady  ") == "hornady"
        assert _normalize(".308 Winchester") == ".308 winchester"
        assert _normalize("ELD-X (Hunting)") == "eld x hunting"

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


# ── _parse_json_response ───────────────────────────────────────────────────


class TestParseJsonResponse:
    def test_plain_json_array(self):
        result = _parse_json_response('[{"name": "test"}]')
        assert len(result) == 1
        assert result[0]["name"] == "test"

    def test_single_object_wrapped_in_list(self):
        result = _parse_json_response('{"name": "test"}')
        assert len(result) == 1
        assert result[0]["name"] == "test"

    def test_markdown_fenced_json(self):
        raw = '```json\n[{"name": "test"}]\n```'
        result = _parse_json_response(raw)
        assert len(result) == 1
        assert result[0]["name"] == "test"

    def test_markdown_fenced_no_lang(self):
        raw = '```\n[{"name": "test"}]\n```'
        result = _parse_json_response(raw)
        assert len(result) == 1

    def test_surrounding_text_with_fenced_json(self):
        raw = 'Here are the results:\n```json\n[{"name": "bullet"}]\n```\nDone.'
        result = _parse_json_response(raw)
        assert result[0]["name"] == "bullet"

    def test_invalid_json_raises(self):
        import pytest

        with pytest.raises(json.JSONDecodeError):
            _parse_json_response("this is not json at all")

    def test_multiple_entities(self):
        raw = '[{"name": "a"}, {"name": "b"}, {"name": "c"}]'
        result = _parse_json_response(raw)
        assert len(result) == 3


# ── _extract_bc_sources ──────────────────────────────────────────────────────


class TestExtractBCSources:
    def test_both_g1_and_g7(self):
        entity = {
            "name": {"value": "ELD Match", "source_text": "ELD Match", "confidence": 0.9},
            "bc_g1": {"value": 0.610, "source_text": ".610", "confidence": 0.9},
            "bc_g7": {"value": 0.305, "source_text": ".305", "confidence": 0.9},
        }
        sources = _extract_bc_sources(entity)
        assert len(sources) == 2
        assert sources[0].bc_type == "g1"
        assert sources[0].bc_value == 0.610
        assert sources[0].bullet_name == "ELD Match"
        assert sources[1].bc_type == "g7"
        assert sources[1].bc_value == 0.305

    def test_only_g1(self):
        entity = {
            "name": {"value": "Test"},
            "bc_g1": {"value": 0.5},
        }
        sources = _extract_bc_sources(entity)
        assert len(sources) == 1
        assert sources[0].bc_type == "g1"

    def test_null_bc_values_skipped(self):
        entity = {
            "name": {"value": "Test"},
            "bc_g1": {"value": None},
            "bc_g7": {"value": None},
        }
        sources = _extract_bc_sources(entity)
        assert len(sources) == 0

    def test_no_bc_fields(self):
        entity = {"name": {"value": "No BCs"}}
        sources = _extract_bc_sources(entity)
        assert len(sources) == 0

    def test_unparseable_bc_value_skipped(self):
        entity = {
            "name": {"value": "Bad BC"},
            "bc_g1": {"value": "not-a-number"},
        }
        sources = _extract_bc_sources(entity)
        assert len(sources) == 0

    def test_plain_value_not_wrapped(self):
        entity = {
            "name": "Plain Name",
            "bc_g1": 0.450,
        }
        sources = _extract_bc_sources(entity)
        assert len(sources) == 1
        assert sources[0].bc_value == 0.450
        assert sources[0].bullet_name == "Plain Name"


# ── Store script helpers ─────────────────────────────────────────────────────


class TestStoreHelpers:
    """Test the _safe_float, _safe_int, and _avg_confidence helpers from pipeline_store."""

    def test_safe_float_valid(self):
        from scripts.pipeline_store import _safe_float

        assert _safe_float(1.5) == 1.5
        assert _safe_float("2.5") == 2.5
        assert _safe_float(0) == 0.0

    def test_safe_float_none(self):
        from scripts.pipeline_store import _safe_float

        assert _safe_float(None) is None

    def test_safe_float_invalid(self):
        from scripts.pipeline_store import _safe_float

        assert _safe_float("not_a_number") is None

    def test_safe_int_valid(self):
        from scripts.pipeline_store import _safe_int

        assert _safe_int(5) == 5
        assert _safe_int("10") == 10

    def test_safe_int_none(self):
        from scripts.pipeline_store import _safe_int

        assert _safe_int(None) is None

    def test_safe_int_invalid(self):
        from scripts.pipeline_store import _safe_int

        assert _safe_int("not_a_number") is None

    def test_avg_confidence(self):
        from scripts.pipeline_store import _avg_confidence

        entity = {
            "name": {"value": "Test", "confidence": 0.9},
            "sku": {"value": "123", "confidence": 0.8},
            "plain_field": "not a dict",
        }
        assert _avg_confidence(entity) == 0.85

    def test_avg_confidence_empty(self):
        from scripts.pipeline_store import _avg_confidence

        assert _avg_confidence({}) == 0.0
        assert _avg_confidence({"plain": "val"}) == 0.0


# ── Fuzzy match confidence penalties (DR-115) ─────────────────────────────────


def _seed_for_fuzzy(db):
    """Create DB fixtures for fuzzy match tests: two bullets, two cartridges, two rifles."""
    from drift.models import Bullet, Caliber, Cartridge, Chamber, ChamberAcceptsCaliber, Manufacturer, RifleModel

    mfr = Manufacturer(name="Hornady", type_tags=["bullet_maker"], country="USA")
    db.add(mfr)
    db.flush()

    cal_65 = Caliber(name="6.5 Creedmoor", bullet_diameter_inches=0.264, lr_popularity_rank=1, is_common_lr=True)
    cal_30 = Caliber(name=".308 Winchester", bullet_diameter_inches=0.308, lr_popularity_rank=2, is_common_lr=True)
    db.add_all([cal_65, cal_30])
    db.flush()

    chamber_65 = Chamber(name="6.5 Creedmoor")
    chamber_30 = Chamber(name=".308 Winchester")
    db.add_all([chamber_65, chamber_30])
    db.flush()

    db.add_all([
        ChamberAcceptsCaliber(chamber_id=chamber_65.id, caliber_id=cal_65.id, is_primary=True),
        ChamberAcceptsCaliber(chamber_id=chamber_30.id, caliber_id=cal_30.id, is_primary=True),
    ])
    db.flush()

    bullet_140 = Bullet(
        manufacturer_id=mfr.id, caliber_id=cal_65.id, name="ELD Match", weight_grains=140.0,
    )
    db.add(bullet_140)
    db.flush()

    cart_140 = Cartridge(
        manufacturer_id=mfr.id, caliber_id=cal_65.id, bullet_id=bullet_140.id,
        name="Hornady 6.5 CM 140gr ELD Match", bullet_weight_grains=140.0, muzzle_velocity_fps=2710,
    )
    db.add(cart_140)

    rifle_65 = RifleModel(
        manufacturer_id=mfr.id, model="B-14 HMR", chamber_id=chamber_65.id, barrel_length_inches=22.0,
    )
    rifle_30 = RifleModel(
        manufacturer_id=mfr.id, model="B-14 HMR", chamber_id=chamber_30.id, barrel_length_inches=24.0,
    )
    db.add_all([rifle_65, rifle_30])
    db.commit()

    return mfr, cal_65, cal_30, chamber_65, chamber_30, bullet_140, cart_140, rifle_65, rifle_30


class TestFuzzyMatchConfidence:
    """DR-115: Fuzzy matches with disagreeing weight/caliber/chamber should have low confidence."""

    def test_bullet_fuzzy_weight_disagrees_low_confidence(self, db):
        mfr, cal_65, *_ = _seed_for_fuzzy(db)
        resolver = EntityResolver(db)

        # 225gr ELD Match should fuzzy-match 140gr ELD Match but at LOW confidence
        extracted = {"name": {"value": "ELD Match"}, "weight_grains": {"value": 225}}
        result = resolver.match_bullet(extracted, mfr.id, cal_65.id)

        assert result.matched is True
        assert result.method == "fuzzy_name"
        assert result.confidence < 0.7  # Below threshold → flagged, not auto-skipped

    def test_bullet_fuzzy_weight_agrees_high_confidence(self, db):
        mfr, cal_65, *_ = _seed_for_fuzzy(db)
        resolver = EntityResolver(db)

        # 140gr ELD Match should fuzzy-match 140gr ELD Match at HIGH confidence
        extracted = {"name": {"value": "ELD Match"}, "weight_grains": {"value": 140}}
        result = resolver.match_bullet(extracted, mfr.id, cal_65.id)

        assert result.matched is True
        assert result.confidence >= 0.7  # Above threshold → auto-matched

    def test_bullet_fuzzy_no_weight_low_confidence(self, db):
        mfr, cal_65, *_ = _seed_for_fuzzy(db)
        resolver = EntityResolver(db)

        # No weight → low confidence (can't verify it's the same product)
        extracted = {"name": {"value": "ELD Match"}}
        result = resolver.match_bullet(extracted, mfr.id, cal_65.id)

        assert result.matched is True
        assert result.confidence < 0.7

    def test_cartridge_fuzzy_weight_disagrees_low_confidence(self, db):
        mfr, cal_65, *_ = _seed_for_fuzzy(db)
        resolver = EntityResolver(db)

        extracted = {"name": {"value": "Hornady 6.5 CM 225gr ELD Match"}, "bullet_weight_grains": {"value": 225}}
        result = resolver.match_cartridge(extracted, mfr.id, cal_65.id)

        assert result.matched is True
        assert result.method == "fuzzy_name"
        assert result.confidence < 0.7

    def test_rifle_fuzzy_chamber_disagrees_low_confidence(self, db):
        fixtures = _seed_for_fuzzy(db)
        mfr = fixtures[0]
        resolver = EntityResolver(db)

        # Match "B-14 HMR" with a non-existent chamber to simulate disagreement
        extracted = {"model": {"value": "B-14 HMR"}}
        result = resolver.match_rifle(extracted, mfr.id, "nonexistent-chamber-id")

        assert result.matched is True
        assert result.confidence < 0.7

    def test_rifle_fuzzy_chamber_agrees_high_confidence(self, db):
        fixtures = _seed_for_fuzzy(db)
        mfr, chamber_65 = fixtures[0], fixtures[3]
        resolver = EntityResolver(db)

        extracted = {"model": {"value": "B-14 HMR"}}
        result = resolver.match_rifle(extracted, mfr.id, chamber_65.id)

        assert result.matched is True
        assert result.confidence >= 0.7
