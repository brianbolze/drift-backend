# flake8: noqa: E501
"""Tests for pipeline_store auto-create weight variant logic."""

import importlib
import sys
from pathlib import Path

import pytest

from drift.models import Bullet, Caliber, Cartridge, Chamber, EntityAlias, Manufacturer, RifleModel
from drift.pipeline.resolution.resolver import MatchResult, ResolutionResult

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
_store_mod = importlib.import_module("pipeline_store")
_should_auto_create_weight_variant = _store_mod._should_auto_create_weight_variant
_build_alias_suggestion = _store_mod._build_alias_suggestion
_record_method_telemetry = _store_mod._record_method_telemetry
AUTO_CREATE_CONFIDENCE_CEILING = _store_mod.AUTO_CREATE_CONFIDENCE_CEILING
_LOW_CONFIDENCE_REPORT_THRESHOLD = _store_mod._LOW_CONFIDENCE_REPORT_THRESHOLD


def _ev(value, confidence=0.9):
    """Helper: build an ExtractedValue dict."""
    return {"value": value, "confidence": confidence}


@pytest.fixture()
def seeded(db):
    """Seed entities for auto-create testing."""
    mfr = Manufacturer(name="Barnes Bullets", type_tags=["bullet_maker"], country="USA")
    db.add(mfr)
    db.flush()

    cal = Caliber(name=".308 Winchester", alt_names=[".308 Win"], bullet_diameter_inches=0.308)
    db.add(cal)
    db.flush()

    bullet = Bullet(
        manufacturer_id=mfr.id,
        name="30cal 110gr TTSX",
        bullet_diameter_inches=0.308,
        weight_grains=110.0,
    )
    db.add(bullet)
    db.flush()

    cart = Cartridge(
        manufacturer_id=mfr.id,
        caliber_id=cal.id,
        bullet_id=bullet.id,
        name="Barnes .308 Win 110gr TTSX",
        bullet_weight_grains=110.0,
        muzzle_velocity_fps=3100,
    )
    db.add(cart)
    db.commit()

    return {"mfr": mfr, "cal": cal, "bullet": bullet, "cart": cart}


def _make_resolution(entity_type, confidence, entity_id=None, matched=True, **kwargs):
    """Build a ResolutionResult with a MatchResult at given confidence."""
    return ResolutionResult(
        entity_type=entity_type,
        match=MatchResult(matched=matched, entity_id=entity_id, confidence=confidence),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Bullet auto-create tests
# ---------------------------------------------------------------------------


class TestAutoCreateBullet:
    """Tests for _should_auto_create_weight_variant with entity_type='bullet'."""

    def test_weight_mismatch_below_ceiling_returns_true(self, seeded, db):
        """New weight variant (130gr vs existing 110gr) at low confidence → auto-create."""
        entity = {"name": _ev("30cal 130gr TTSX"), "weight_grains": _ev(130.0)}
        res = _make_resolution(
            "bullet",
            confidence=0.35,
            entity_id=seeded["bullet"].id,
            manufacturer_id=seeded["mfr"].id,
            bullet_diameter_inches=0.308,
        )
        assert _should_auto_create_weight_variant(entity, "bullet", res, db) is True

    def test_weight_match_within_tolerance_returns_false(self, seeded, db):
        """Same weight (110.5gr vs 110gr, within ±1gr) at low confidence → do NOT create."""
        entity = {"name": _ev("30cal 110gr TTSX"), "weight_grains": _ev(110.5)}
        res = _make_resolution(
            "bullet",
            confidence=0.35,
            entity_id=seeded["bullet"].id,
            manufacturer_id=seeded["mfr"].id,
            bullet_diameter_inches=0.308,
        )
        assert _should_auto_create_weight_variant(entity, "bullet", res, db) is False

    def test_exact_tolerance_boundary_returns_false(self, seeded, db):
        """Weight diff of exactly 1.0gr → within tolerance, do NOT create."""
        entity = {"name": _ev("30cal 111gr TTSX"), "weight_grains": _ev(111.0)}
        res = _make_resolution(
            "bullet",
            confidence=0.35,
            entity_id=seeded["bullet"].id,
            manufacturer_id=seeded["mfr"].id,
            bullet_diameter_inches=0.308,
        )
        assert _should_auto_create_weight_variant(entity, "bullet", res, db) is False

    def test_just_over_tolerance_returns_true(self, seeded, db):
        """Weight diff of 1.01gr → outside tolerance, create."""
        entity = {"name": _ev("30cal 111.01gr TTSX"), "weight_grains": _ev(111.01)}
        res = _make_resolution(
            "bullet",
            confidence=0.35,
            entity_id=seeded["bullet"].id,
            manufacturer_id=seeded["mfr"].id,
            bullet_diameter_inches=0.308,
        )
        assert _should_auto_create_weight_variant(entity, "bullet", res, db) is True

    def test_confidence_at_ceiling_returns_false(self, seeded, db):
        """Confidence exactly at ceiling (0.5) → do NOT auto-create."""
        entity = {"name": _ev("30cal 130gr TTSX"), "weight_grains": _ev(130.0)}
        res = _make_resolution(
            "bullet",
            confidence=AUTO_CREATE_CONFIDENCE_CEILING,
            entity_id=seeded["bullet"].id,
            manufacturer_id=seeded["mfr"].id,
            bullet_diameter_inches=0.308,
        )
        assert _should_auto_create_weight_variant(entity, "bullet", res, db) is False

    def test_confidence_above_ceiling_returns_false(self, seeded, db):
        """High confidence → do NOT auto-create (even with weight mismatch)."""
        entity = {"name": _ev("30cal 130gr TTSX"), "weight_grains": _ev(130.0)}
        res = _make_resolution(
            "bullet",
            confidence=0.65,
            entity_id=seeded["bullet"].id,
            manufacturer_id=seeded["mfr"].id,
            bullet_diameter_inches=0.308,
        )
        assert _should_auto_create_weight_variant(entity, "bullet", res, db) is False

    def test_missing_manufacturer_id_returns_false(self, seeded, db):
        """No manufacturer_id resolved → cannot create."""
        entity = {"name": _ev("30cal 130gr TTSX"), "weight_grains": _ev(130.0)}
        res = _make_resolution(
            "bullet",
            confidence=0.35,
            entity_id=seeded["bullet"].id,
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert _should_auto_create_weight_variant(entity, "bullet", res, db) is False

    def test_missing_diameter_returns_false(self, seeded, db):
        """No bullet_diameter_inches resolved → cannot create."""
        entity = {"name": _ev("30cal 130gr TTSX"), "weight_grains": _ev(130.0)}
        res = _make_resolution(
            "bullet",
            confidence=0.35,
            entity_id=seeded["bullet"].id,
            manufacturer_id=seeded["mfr"].id,
            bullet_diameter_inches=None,
        )
        assert _should_auto_create_weight_variant(entity, "bullet", res, db) is False

    def test_missing_weight_returns_false(self, seeded, db):
        """No weight in extracted entity → cannot create."""
        entity = {"name": _ev("30cal TTSX")}
        res = _make_resolution(
            "bullet",
            confidence=0.35,
            entity_id=seeded["bullet"].id,
            manufacturer_id=seeded["mfr"].id,
            bullet_diameter_inches=0.308,
        )
        assert _should_auto_create_weight_variant(entity, "bullet", res, db) is False

    def test_zero_weight_returns_false(self, seeded, db):
        """Zero weight → cannot create."""
        entity = {"name": _ev("30cal TTSX"), "weight_grains": _ev(0.0)}
        res = _make_resolution(
            "bullet",
            confidence=0.35,
            entity_id=seeded["bullet"].id,
            manufacturer_id=seeded["mfr"].id,
            bullet_diameter_inches=0.308,
        )
        assert _should_auto_create_weight_variant(entity, "bullet", res, db) is False

    def test_no_entity_id_returns_true(self, seeded, db):
        """Matched but no entity_id (unusual state) → safe to create."""
        entity = {"name": _ev("30cal 130gr TTSX"), "weight_grains": _ev(130.0)}
        res = _make_resolution(
            "bullet",
            confidence=0.35,
            entity_id=None,
            manufacturer_id=seeded["mfr"].id,
            bullet_diameter_inches=0.308,
        )
        assert _should_auto_create_weight_variant(entity, "bullet", res, db) is True


# ---------------------------------------------------------------------------
# Cartridge auto-create tests
# ---------------------------------------------------------------------------


class TestAutoCreateCartridge:
    """Tests for _should_auto_create_weight_variant with entity_type='cartridge'."""

    def test_weight_mismatch_below_ceiling_returns_true(self, seeded, db):
        """New cartridge weight variant (150gr vs 110gr) at low confidence → auto-create."""
        entity = {"name": _ev(".308 Win 150gr TTSX"), "bullet_weight_grains": _ev(150.0)}
        res = _make_resolution(
            "cartridge",
            confidence=0.35,
            entity_id=seeded["cart"].id,
            manufacturer_id=seeded["mfr"].id,
            caliber_id=seeded["cal"].id,
            bullet_id=seeded["bullet"].id,
        )
        assert _should_auto_create_weight_variant(entity, "cartridge", res, db) is True

    def test_weight_within_2gr_tolerance_returns_false(self, seeded, db):
        """Weight diff within ±2gr → same cartridge, do NOT create."""
        entity = {"name": _ev(".308 Win 111gr TTSX"), "bullet_weight_grains": _ev(111.5)}
        res = _make_resolution(
            "cartridge",
            confidence=0.35,
            entity_id=seeded["cart"].id,
            manufacturer_id=seeded["mfr"].id,
            caliber_id=seeded["cal"].id,
            bullet_id=seeded["bullet"].id,
        )
        assert _should_auto_create_weight_variant(entity, "cartridge", res, db) is False

    def test_exact_2gr_boundary_returns_false(self, seeded, db):
        """Weight diff of exactly 2.0gr → within tolerance."""
        entity = {"name": _ev(".308 Win 112gr TTSX"), "bullet_weight_grains": _ev(112.0)}
        res = _make_resolution(
            "cartridge",
            confidence=0.35,
            entity_id=seeded["cart"].id,
            manufacturer_id=seeded["mfr"].id,
            caliber_id=seeded["cal"].id,
            bullet_id=seeded["bullet"].id,
        )
        assert _should_auto_create_weight_variant(entity, "cartridge", res, db) is False

    def test_missing_bullet_id_returns_false(self, seeded, db):
        """No bullet_id resolved → cannot create cartridge (NOT NULL FK)."""
        entity = {"name": _ev(".308 Win 150gr TTSX"), "bullet_weight_grains": _ev(150.0)}
        res = _make_resolution(
            "cartridge",
            confidence=0.35,
            entity_id=seeded["cart"].id,
            manufacturer_id=seeded["mfr"].id,
            caliber_id=seeded["cal"].id,
            bullet_id=None,
        )
        assert _should_auto_create_weight_variant(entity, "cartridge", res, db) is False

    def test_missing_caliber_id_returns_false(self, seeded, db):
        """No caliber_id resolved → cannot create."""
        entity = {"name": _ev(".308 Win 150gr TTSX"), "bullet_weight_grains": _ev(150.0)}
        res = _make_resolution(
            "cartridge",
            confidence=0.35,
            entity_id=seeded["cart"].id,
            manufacturer_id=seeded["mfr"].id,
            caliber_id=None,
            bullet_id=seeded["bullet"].id,
        )
        assert _should_auto_create_weight_variant(entity, "cartridge", res, db) is False


# ---------------------------------------------------------------------------
# Entity type edge cases
# ---------------------------------------------------------------------------


class TestAutoCreateEdgeCases:
    """Edge cases that apply across entity types."""

    def test_rifle_type_always_returns_false(self, seeded, db):
        """Rifles do not support auto-create."""
        entity = {"name": _ev("Some Rifle"), "weight_grains": _ev(100.0)}
        res = _make_resolution(
            "rifle",
            confidence=0.35,
            manufacturer_id=seeded["mfr"].id,
        )
        assert _should_auto_create_weight_variant(entity, "rifle", res, db) is False

    def test_unknown_type_returns_false(self, seeded, db):
        """Unknown entity type → False."""
        entity = {"name": _ev("Something"), "weight_grains": _ev(100.0)}
        res = _make_resolution("optic", confidence=0.35, manufacturer_id=seeded["mfr"].id)
        assert _should_auto_create_weight_variant(entity, "optic", res, db) is False

    def test_plain_value_format(self, seeded, db):
        """Weight as plain value (not ExtractedValue dict) also works."""
        entity = {"name": "30cal 130gr TTSX", "weight_grains": 130.0}
        res = _make_resolution(
            "bullet",
            confidence=0.35,
            entity_id=seeded["bullet"].id,
            manufacturer_id=seeded["mfr"].id,
            bullet_diameter_inches=0.308,
        )
        assert _should_auto_create_weight_variant(entity, "bullet", res, db) is True

    def test_unparseable_weight_returns_false(self, seeded, db):
        """Weight that can't be parsed as float → False."""
        entity = {"name": _ev("30cal TTSX"), "weight_grains": _ev("N/A")}
        res = _make_resolution(
            "bullet",
            confidence=0.35,
            entity_id=seeded["bullet"].id,
            manufacturer_id=seeded["mfr"].id,
            bullet_diameter_inches=0.308,
        )
        assert _should_auto_create_weight_variant(entity, "bullet", res, db) is False


# ---------------------------------------------------------------------------
# Alias suggestion tests (finding #9 — learning loop)
# ---------------------------------------------------------------------------


class TestAliasSuggestion:
    """Tests for _build_alias_suggestion: candidates EntityAlias promotion for fuzzy matches."""

    def test_fuzzy_name_match_returns_suggestion(self, seeded, db):
        """A fuzzy_name match with a distinct extracted name → suggest alias."""
        match = MatchResult(
            matched=True,
            entity_id=seeded["bullet"].id,
            confidence=0.76,
            method="fuzzy_name",
        )
        suggestion = _build_alias_suggestion(db, "bullet", match, seeded["bullet"], "Barnes 30 Cal 110gr TTSX")
        assert suggestion is not None
        assert suggestion["entity_type"] == "bullet"
        assert suggestion["entity_id"] == seeded["bullet"].id
        assert suggestion["canonical_name"] == seeded["bullet"].name
        assert suggestion["alias"] == "Barnes 30 Cal 110gr TTSX"
        assert suggestion["method"] == "fuzzy_name"
        assert suggestion["confidence"] == 0.76

    def test_composite_key_match_returns_suggestion(self, seeded, db):
        """composite_key is also a fuzzy method (uses name similarity)."""
        match = MatchResult(
            matched=True,
            entity_id=seeded["bullet"].id,
            confidence=0.91,
            method="composite_key",
        )
        suggestion = _build_alias_suggestion(db, "bullet", match, seeded["bullet"], "Barnes TTSX 110 grain")
        assert suggestion is not None
        assert suggestion["method"] == "composite_key"

    def test_exact_sku_returns_none(self, seeded, db):
        """Deterministic SKU match → no alias suggestion."""
        match = MatchResult(
            matched=True,
            entity_id=seeded["bullet"].id,
            confidence=1.0,
            method="exact_sku",
        )
        suggestion = _build_alias_suggestion(db, "bullet", match, seeded["bullet"], "some alt name")
        assert suggestion is None

    def test_product_line_returns_none(self, seeded, db):
        """product_line match is deterministic (normalized exact match) → no suggestion."""
        match = MatchResult(
            matched=True,
            entity_id=seeded["bullet"].id,
            confidence=0.93,
            method="product_line",
        )
        suggestion = _build_alias_suggestion(db, "bullet", match, seeded["bullet"], "some alt name")
        assert suggestion is None

    def test_identical_normalized_name_returns_none(self, seeded, db):
        """Extracted name equals canonical name after normalization → no suggestion."""
        match = MatchResult(
            matched=True,
            entity_id=seeded["bullet"].id,
            confidence=0.8,
            method="fuzzy_name",
        )
        suggestion = _build_alias_suggestion(db, "bullet", match, seeded["bullet"], seeded["bullet"].name.upper())
        assert suggestion is None

    def test_existing_alias_returns_none(self, seeded, db):
        """If EntityAlias already has this alias for this entity → no duplicate suggestion."""
        db.add(
            EntityAlias(
                entity_type="bullet",
                entity_id=seeded["bullet"].id,
                alias="Barnes 30 Cal 110gr TTSX",
                alias_type="extracted_fuzzy",
            )
        )
        db.flush()
        match = MatchResult(
            matched=True,
            entity_id=seeded["bullet"].id,
            confidence=0.76,
            method="fuzzy_name",
        )
        suggestion = _build_alias_suggestion(db, "bullet", match, seeded["bullet"], "Barnes 30 Cal 110gr TTSX")
        assert suggestion is None

    def test_missing_existing_returns_none(self, seeded, db):
        """No existing entity → cannot suggest alias."""
        match = MatchResult(matched=True, entity_id="some-id", confidence=0.8, method="fuzzy_name")
        assert _build_alias_suggestion(db, "bullet", match, None, "foo") is None

    def test_empty_extracted_name_returns_none(self, seeded, db):
        """Empty extracted name → no suggestion."""
        match = MatchResult(
            matched=True,
            entity_id=seeded["bullet"].id,
            confidence=0.8,
            method="fuzzy_name",
        )
        assert _build_alias_suggestion(db, "bullet", match, seeded["bullet"], "") is None

    def test_rifle_uses_model_as_canonical(self, seeded, db):
        """Rifles have .model (not .name) — suggestion picks the right attribute."""
        chamber = Chamber(name=".308 Win chamber")
        db.add(chamber)
        db.flush()
        rifle = RifleModel(manufacturer_id=seeded["mfr"].id, chamber_id=chamber.id, model="Model 700 SPS Varmint")
        db.add(rifle)
        db.flush()
        match = MatchResult(
            matched=True,
            entity_id=rifle.id,
            confidence=0.72,
            method="fuzzy_name",
        )
        suggestion = _build_alias_suggestion(db, "rifle", match, rifle, "Remington 700 SPS Varmint")
        assert suggestion is not None
        assert suggestion["canonical_name"] == "Model 700 SPS Varmint"
        assert suggestion["alias"] == "Remington 700 SPS Varmint"


# ---------------------------------------------------------------------------
# Method telemetry tests (finding #17 — end-of-run breakdown)
# ---------------------------------------------------------------------------


def _fresh_stats():
    """Empty stats shape matching pipeline_store main()."""
    return {
        "bullet": {"methods": {}},
        "cartridge": {"methods": {}},
        "rifle": {"methods": {}},
    }


class TestMethodTelemetry:
    """Tests for _record_method_telemetry: winning-method counts and confidence buckets."""

    def test_records_winning_method(self):
        stats = _fresh_stats()
        _record_method_telemetry(stats, "bullet", MatchResult(matched=True, confidence=0.95, method="exact_sku"))
        assert stats["bullet"]["methods"] == {"exact_sku": {"count": 1, "confidence_sum": 0.95, "low_confidence": 0}}

    def test_accumulates_counts_and_confidence(self):
        stats = _fresh_stats()
        for conf in (0.9, 0.8, 0.7):
            _record_method_telemetry(stats, "bullet", MatchResult(matched=True, confidence=conf, method="fuzzy_name"))
        bucket = stats["bullet"]["methods"]["fuzzy_name"]
        assert bucket["count"] == 3
        assert bucket["confidence_sum"] == pytest.approx(0.9 + 0.8 + 0.7)
        assert bucket["low_confidence"] == 0

    def test_low_confidence_counted(self):
        stats = _fresh_stats()
        # Below threshold
        _record_method_telemetry(stats, "bullet", MatchResult(matched=True, confidence=0.3, method="fuzzy_name"))
        # At threshold — not counted as low
        _record_method_telemetry(
            stats,
            "bullet",
            MatchResult(matched=True, confidence=_LOW_CONFIDENCE_REPORT_THRESHOLD, method="fuzzy_name"),
        )
        bucket = stats["bullet"]["methods"]["fuzzy_name"]
        assert bucket["count"] == 2
        assert bucket["low_confidence"] == 1

    def test_unmatched_not_recorded(self):
        stats = _fresh_stats()
        _record_method_telemetry(stats, "bullet", MatchResult(matched=False, confidence=0.0, method=""))
        assert stats["bullet"]["methods"] == {}

    def test_methods_separated_per_entity_type(self):
        stats = _fresh_stats()
        _record_method_telemetry(stats, "bullet", MatchResult(matched=True, confidence=1.0, method="exact_sku"))
        _record_method_telemetry(stats, "cartridge", MatchResult(matched=True, confidence=0.8, method="composite_key"))
        assert "exact_sku" in stats["bullet"]["methods"]
        assert "exact_sku" not in stats["cartridge"]["methods"]
        assert "composite_key" in stats["cartridge"]["methods"]

    def test_empty_method_recorded_as_unknown(self):
        stats = _fresh_stats()
        _record_method_telemetry(stats, "bullet", MatchResult(matched=True, confidence=0.9, method=""))
        assert stats["bullet"]["methods"]["unknown"]["count"] == 1


class TestMethodBreakdownOutput:
    """_print_method_breakdown renders a concise per-entity-type summary."""

    def test_prints_nothing_when_empty(self, capsys):
        _store_mod._print_method_breakdown(_fresh_stats())
        assert capsys.readouterr().out == ""

    def test_prints_summary_sorted_by_count(self, capsys):
        stats = _fresh_stats()
        stats["bullet"]["methods"] = {
            "exact_sku": {"count": 10, "confidence_sum": 10.0, "low_confidence": 0},
            "fuzzy_name": {"count": 3, "confidence_sum": 1.2, "low_confidence": 2},
        }
        _store_mod._print_method_breakdown(stats)
        out = capsys.readouterr().out
        assert "Match method breakdown:" in out
        assert "bullet (13 matched):" in out
        # exact_sku (higher count) should print before fuzzy_name
        assert out.index("exact_sku") < out.index("fuzzy_name")
        assert "2 < 0.5" in out  # low-confidence count for fuzzy_name
