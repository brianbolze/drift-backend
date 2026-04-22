# flake8: noqa: E501
"""Tests for pipeline_store auto-create weight variant logic."""

import importlib
import json
import sys
from pathlib import Path

import pytest

from drift.models import Bullet, Caliber, Cartridge, Chamber, EntityAlias, Manufacturer, RifleModel
from drift.pipeline.resolution.resolver import AlternativeMatch, MatchResult, ResolutionResult

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
_store_mod = importlib.import_module("pipeline_store")
_should_auto_create_weight_variant = _store_mod._should_auto_create_weight_variant
_build_alias_suggestion = _store_mod._build_alias_suggestion
_should_auto_promote_alias = _store_mod._should_auto_promote_alias
_create_pipeline_alias = _store_mod._create_pipeline_alias
_record_method_telemetry = _store_mod._record_method_telemetry
_make_cartridge = _store_mod._make_cartridge
AUTO_CREATE_CONFIDENCE_CEILING = _store_mod.AUTO_CREATE_CONFIDENCE_CEILING
ALIAS_AUTO_PROMOTE_THRESHOLD = _store_mod.ALIAS_AUTO_PROMOTE_THRESHOLD
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


# ---------------------------------------------------------------------------
# bullet_match_confidence / bullet_match_method persistence (finding #18)
# ---------------------------------------------------------------------------


class TestBulletMatchPersistence:
    """Both bullet_match_confidence and bullet_match_method must be written to Cartridge
    from every pipeline write path — create and match-updated FK refresh.

    Unblocks the "99 cartridges with wrong bullet_id" audit query (TODO.md).
    """

    def test_resolver_sets_bullet_match_method_for_cartridge(self, seeded, db):
        """EntityResolver.resolve(cartridge) should populate bullet_match_method
        alongside bullet_match_confidence. Without this, the match-updated branch
        and _make_cartridge have no method to persist."""
        from drift.pipeline.resolution.resolver import EntityResolver

        resolver = EntityResolver(db)
        # Bullet has no SKU in fixture, but its exact name + weight + diameter
        # will hit composite_key or product_line via name-based matching.
        entity = {
            "name": _ev("Barnes .308 Win 110gr TTSX load"),
            "bullet_name": _ev("30cal 110gr TTSX"),
            "bullet_weight_grains": _ev(110.0),
            "muzzle_velocity_fps": _ev(3100),
            "manufacturer": _ev("Barnes Bullets"),
            "caliber": _ev(".308 Winchester"),
        }
        result = resolver.resolve(entity, "cartridge")
        assert result.bullet_id == seeded["bullet"].id
        assert result.bullet_match_confidence is not None and result.bullet_match_confidence > 0.0
        assert result.bullet_match_method  # non-empty string

    def test_make_cartridge_persists_both_fields(self, seeded, db):
        """A pipeline-created Cartridge must have both columns populated."""
        entity = {
            "name": _ev("Barnes .308 Win 110gr TTSX"),
            "bullet_weight_grains": _ev(110.0),
            "muzzle_velocity_fps": _ev(3100),
        }
        cart = _make_cartridge(
            entity,
            manufacturer_id=seeded["mfr"].id,
            caliber_id=seeded["cal"].id,
            bullet_id=seeded["bullet"].id,
            source_url="https://example.com/load",
            bullet_match_confidence=0.93,
            bullet_match_method="product_line",
        )
        db.add(cart)
        db.flush()

        persisted = db.get(Cartridge, cart.id)
        assert persisted.bullet_match_confidence == pytest.approx(0.93)
        assert persisted.bullet_match_method == "product_line"

    def test_matched_updated_branch_persists_both_fields(self, seeded, db):
        """When the pipeline refreshes bullet_id on an existing cartridge,
        both bullet_match_confidence and bullet_match_method must be written too.

        Mirrors the assignment block in pipeline_store.main() under
        ``action == "matched_updated"``.
        """
        other_bullet = Bullet(
            manufacturer_id=seeded["mfr"].id,
            name="30cal 110gr TTSX BT",
            bullet_diameter_inches=0.308,
            weight_grains=110.0,
        )
        db.add(other_bullet)
        db.flush()

        existing_cart = seeded["cart"]
        assert existing_cart.bullet_match_confidence is None
        assert existing_cart.bullet_match_method is None

        resolution = _make_resolution(
            "cartridge",
            confidence=0.95,
            entity_id=existing_cart.id,
            manufacturer_id=seeded["mfr"].id,
            caliber_id=seeded["cal"].id,
            bullet_id=other_bullet.id,
        )
        resolution.bullet_match_confidence = 0.87
        resolution.bullet_match_method = "composite_key"

        # Simulate the match-updated write block in pipeline_store.main()
        existing_cart.bullet_id = resolution.bullet_id
        existing_cart.bullet_match_confidence = resolution.bullet_match_confidence
        existing_cart.bullet_match_method = resolution.bullet_match_method
        db.flush()

        db.refresh(existing_cart)
        assert existing_cart.bullet_id == other_bullet.id
        assert existing_cart.bullet_match_confidence == pytest.approx(0.87)
        assert existing_cart.bullet_match_method == "composite_key"


# ---------------------------------------------------------------------------
# Alias auto-promotion tests
# ---------------------------------------------------------------------------


def _match(confidence, method="fuzzy_name", *, entity_id="some-id", runner_up=None):
    """Build a MatchResult with optional runner-up for ambiguity gating."""
    alternatives = (
        [AlternativeMatch(entity_id="other", confidence=runner_up, method=method)] if runner_up is not None else []
    )
    return MatchResult(
        matched=True,
        entity_id=entity_id,
        confidence=confidence,
        method=method,
        alternatives=alternatives,
    )


class TestShouldAutoPromoteAlias:
    """Gate predicate: confidence strictly above threshold AND not ambiguous."""

    def test_above_threshold_no_alternatives_returns_true(self):
        assert _should_auto_promote_alias(_match(0.9)) is True

    def test_at_threshold_returns_false(self):
        """Strictly greater-than — equal confidence shouldn't auto-promote."""
        assert _should_auto_promote_alias(_match(ALIAS_AUTO_PROMOTE_THRESHOLD)) is False

    def test_below_threshold_returns_false(self):
        assert _should_auto_promote_alias(_match(0.75)) is False

    def test_ambiguous_match_returns_false(self):
        """Runner-up within ambiguity_gap_threshold → don't promote even above threshold."""
        m = _match(0.9, runner_up=0.88)
        assert m.is_ambiguous is True
        assert _should_auto_promote_alias(m) is False

    def test_above_threshold_with_wide_gap_returns_true(self):
        """Runner-up below ambiguity_gap_threshold distance → not ambiguous."""
        m = _match(0.9, runner_up=0.4)
        assert m.is_ambiguous is False
        assert _should_auto_promote_alias(m) is True


class TestCreatePipelineAlias:
    """Writes an EntityAlias row with the pipeline's alias_type marker."""

    def test_writes_entity_alias_row(self, seeded, db):
        suggestion = {
            "entity_type": "bullet",
            "entity_id": seeded["bullet"].id,
            "canonical_name": seeded["bullet"].name,
            "alias": "Barnes 30 Cal 110gr TTSX",
            "method": "fuzzy_name",
            "confidence": 0.91,
        }
        alias_id = _create_pipeline_alias(db, suggestion)
        persisted = db.get(EntityAlias, alias_id)
        assert persisted is not None
        assert persisted.entity_type == "bullet"
        assert persisted.entity_id == seeded["bullet"].id
        assert persisted.alias == "Barnes 30 Cal 110gr TTSX"
        assert persisted.alias_type == "extracted_fuzzy"


class TestMainLoopAutoPromotion:
    """End-to-end: invoke main() over a crafted extraction file and inspect the
    resulting store_report + DB state.

    We exercise the whole store loop (not just the helpers) because the gate
    decision lives inside main() and the real concern is the dry-run/commit
    divergence and the entry/stats shape."""

    @pytest.fixture()
    def _bullet_seed(self, db, monkeypatch, tmp_path):
        """Seed a bullet whose name will fuzzy-match an extracted variant
        strongly enough to auto-promote, plus enough supporting entities for
        normalize→resolve→store to make it all the way through."""
        mfr = Manufacturer(name="Hornady", type_tags=["bullet_maker"], country="USA")
        db.add(mfr)
        db.flush()

        cal = Caliber(name=".308 Winchester", alt_names=[".308 Win"], bullet_diameter_inches=0.308)
        db.add(cal)
        db.flush()

        bullet = Bullet(
            manufacturer_id=mfr.id,
            name="30 Cal .308 178 gr ELD-X",
            bullet_diameter_inches=0.308,
            weight_grains=178.0,
            bc_g1_published=0.552,
        )
        db.add(bullet)
        db.commit()

        return {"mfr": mfr, "cal": cal, "bullet": bullet}

    def _run_main(self, db, monkeypatch, tmp_path, extraction: dict, *, commit: bool) -> dict:
        """Run pipeline_store.main() with a single extraction JSON and return the report."""
        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        (extracted_dir / "test.json").write_text(json.dumps(extraction), encoding="utf-8")
        report_path = tmp_path / "store_report.json"
        rejected_path = tmp_path / "rejected_calibers.json"

        monkeypatch.setattr(_store_mod, "EXTRACTED_DIR", extracted_dir)
        monkeypatch.setattr(_store_mod, "STORE_REPORT_PATH", report_path)
        monkeypatch.setattr(_store_mod, "REJECTED_CALIBERS_PATH", rejected_path)

        # Patch the session factory so main() reuses the test db session.
        class _Factory:
            def __call__(self_inner):
                return _NoCloseSession(db)

        monkeypatch.setattr(_store_mod, "get_session_factory", lambda: _Factory())
        argv = ["pipeline_store.py"] + (["--commit"] if commit else [])
        monkeypatch.setattr(sys, "argv", argv)

        _store_mod.main()
        return json.loads(report_path.read_text(encoding="utf-8"))

    def test_commit_above_threshold_auto_promotes(self, db, monkeypatch, tmp_path, _bullet_seed):
        """Commit + high-confidence fuzzy win + unambiguous → alias written, row marked."""
        extraction = _fuzzy_bullet_extraction("Hornady 30 Cal 178gr ELDX Match")
        report = self._run_main(db, monkeypatch, tmp_path, extraction, commit=True)

        assert len(report["alias_auto_promoted"]) == 1
        promoted = report["alias_auto_promoted"][0]
        assert promoted["status"] == "alias_auto_promoted"
        assert promoted["alias_id"]
        assert promoted["entity_id"] == _bullet_seed["bullet"].id
        assert report["stats"]["bullet"]["alias_auto_promoted"] == 1
        assert report["alias_suggestions"] == []

        # The EntityAlias row exists in the DB and carries the pipeline marker.
        alias = db.get(EntityAlias, promoted["alias_id"])
        assert alias is not None
        assert alias.alias_type == "extracted_fuzzy"
        assert alias.alias == "Hornady 30 Cal 178gr ELDX Match"

    def test_dry_run_above_threshold_suggests_only(self, db, monkeypatch, tmp_path, _bullet_seed):
        """Dry-run never writes, even when the gate would pass on commit."""
        extraction = _fuzzy_bullet_extraction("Hornady 30 Cal 178gr ELDX Match")
        report = self._run_main(db, monkeypatch, tmp_path, extraction, commit=False)

        assert report["alias_auto_promoted"] == []
        assert len(report["alias_suggestions"]) == 1
        assert report["alias_suggestions"][0]["status"] == "suggested"
        assert report["stats"]["bullet"]["alias_auto_promoted"] == 0
        assert report["stats"]["bullet"]["alias_suggestions"] == 1
        # No EntityAlias rows were written.
        assert db.query(EntityAlias).count() == 0

    def test_commit_below_threshold_suggests_only(self, db, monkeypatch, tmp_path, _bullet_seed):
        """Gate below → suggestion only, even on commit. Threshold monkeypatched
        up to isolate this from resolver scoring drift."""
        monkeypatch.setattr(_store_mod, "ALIAS_AUTO_PROMOTE_THRESHOLD", 0.99)
        extraction = _fuzzy_bullet_extraction("Hornady 30 Cal 178gr ELDX Match")
        report = self._run_main(db, monkeypatch, tmp_path, extraction, commit=True)

        assert report["alias_auto_promoted"] == []
        assert len(report["alias_suggestions"]) == 1
        assert report["alias_suggestions"][0]["status"] == "suggested"
        assert report["stats"]["bullet"]["alias_auto_promoted"] == 0
        assert db.query(EntityAlias).count() == 0

    def test_commit_ambiguous_match_suggests_only(self, db, monkeypatch, tmp_path, _bullet_seed):
        """Ambiguous match (runner-up within gap) → suggestion only even above threshold.

        Simulated by stubbing the gate predicate — the end-to-end concern here is
        that main() consults the predicate, not that the predicate itself works
        (``TestShouldAutoPromoteAlias`` covers that)."""
        monkeypatch.setattr(_store_mod, "_should_auto_promote_alias", lambda match: False)
        extraction = _fuzzy_bullet_extraction("Hornady 30 Cal 178gr ELDX Match")
        report = self._run_main(db, monkeypatch, tmp_path, extraction, commit=True)

        assert report["alias_auto_promoted"] == []
        assert len(report["alias_suggestions"]) == 1
        assert report["alias_suggestions"][0]["status"] == "suggested"
        assert db.query(EntityAlias).count() == 0

    def test_preexisting_alias_is_noop(self, db, monkeypatch, tmp_path, _bullet_seed):
        """When the alias already exists, _build_alias_suggestion returns None
        and auto-promote has nothing to write."""
        db.add(
            EntityAlias(
                entity_type="bullet",
                entity_id=_bullet_seed["bullet"].id,
                alias="Hornady 30 Cal 178gr ELDX Match",
                alias_type="abbreviation",
            )
        )
        db.commit()
        before = db.query(EntityAlias).count()

        extraction = _fuzzy_bullet_extraction("Hornady 30 Cal 178gr ELDX Match")
        report = self._run_main(db, monkeypatch, tmp_path, extraction, commit=True)

        assert report["alias_auto_promoted"] == []
        assert report["alias_suggestions"] == []
        assert db.query(EntityAlias).count() == before


class _NoCloseSession:
    """Wrap a test db session so main() can call session.close() without
    actually closing the fixture-owned session.

    Also swallows commit/rollback so test assertions can still inspect the
    session state after main() runs."""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def close(self):  # no-op — outer fixture owns lifecycle
        pass

    def commit(self):
        self._inner.flush()

    def rollback(self):
        pass


def _fuzzy_bullet_extraction(name: str, *, weight: float = 178.0) -> dict:
    """Build a minimal extraction JSON that the pipeline store can process end-to-end.

    The bullet diameter (.308") is set so the diameter gate passes against the
    seeded Hornady ELD-X test bullet."""
    return {
        "url": "https://example.com/hornady/eldx-178",
        "entity_type": "bullet",
        "entities": [
            {
                "name": {"value": name, "confidence": 0.9},
                "manufacturer": {"value": "Hornady", "confidence": 0.95},
                "bullet_diameter_inches": {"value": 0.308, "confidence": 0.95},
                "weight_grains": {"value": weight, "confidence": 0.95},
            }
        ],
        "bc_sources": [],
        "data_source": "pipeline",
    }


# ---------------------------------------------------------------------------
# Cross-diameter guard (v6 compound fix, 2026-04-22)
#
# When the store considers overwriting a cartridge's bullet_id (matched_updated
# action), it must refuse to write a bullet whose diameter disagrees with the
# existing cartridge's caliber diameter. This is the last-line defense against
# resolver bugs that pair cross-diameter entities. See forensic:
# data/forensic/v6-resolver-regression-2026-04-22/relinks.tsv
# ---------------------------------------------------------------------------


_bullet_diameter_compatible = _store_mod._bullet_diameter_compatible


class TestCrossDiameterGuard:
    """Regression tests for the pipeline_store cross-diameter overwrite guard."""

    def test_3a_compatible_diameter_accepts(self):
        """Same diameter within tolerance → compatible."""
        assert _bullet_diameter_compatible(0.308, 0.308) is True
        assert _bullet_diameter_compatible(0.3085, 0.308) is True  # within 0.005
        assert _bullet_diameter_compatible(0.308, 0.3095) is True  # within 0.005

    def test_3b_cross_diameter_rejects(self):
        """Different diameters outside tolerance → incompatible."""
        assert _bullet_diameter_compatible(0.308, 0.277) is False  # .30 vs .270 Win
        assert _bullet_diameter_compatible(0.308, 0.338) is False  # .30 vs .338
        assert _bullet_diameter_compatible(0.224, 0.243) is False  # .22 vs 6mm
        assert _bullet_diameter_compatible(0.308, 0.357) is False  # .30 vs .357 pistol

    def test_3c_none_values_reject(self):
        """Missing diameter on either side → incompatible (conservative default)."""
        assert _bullet_diameter_compatible(None, 0.308) is False
        assert _bullet_diameter_compatible(0.308, None) is False
        assert _bullet_diameter_compatible(None, None) is False

    def test_3d_store_blocks_cross_diameter_overwrite_end_to_end(self, db, monkeypatch, tmp_path):
        """End-to-end: seed an existing .308 Win cartridge pointing to a correct .308
        bullet. Feed an extraction whose resolved bullet has .277 diameter. The store
        must NOT overwrite bullet_id, must record action=blocked_cross_diameter, and
        must increment stats[cartridge][blocked_cross_diameter]."""
        # Seed scenario
        nosler = Manufacturer(name="Nosler", type_tags=["ammo_maker"], country="USA")
        db.add(nosler)
        db.flush()

        cal_308 = Caliber(name=".308 Winchester", bullet_diameter_inches=0.308)
        db.add(cal_308)
        db.flush()

        correct_bullet = Bullet(
            manufacturer_id=nosler.id,
            name="30 Caliber 180gr AccuBond",
            bullet_diameter_inches=0.308,
            weight_grains=180.0,
        )
        wrong_bullet = Bullet(
            manufacturer_id=nosler.id,
            name="270 Caliber 180gr Partition",
            bullet_diameter_inches=0.277,
            weight_grains=180.0,
        )
        db.add_all([correct_bullet, wrong_bullet])
        db.flush()

        existing_cart = Cartridge(
            manufacturer_id=nosler.id,
            caliber_id=cal_308.id,
            bullet_id=correct_bullet.id,
            name="308 Win 180gr AccuBond",
            sku="TG-180",
            bullet_weight_grains=180.0,
            muzzle_velocity_fps=2750,
        )
        db.add(existing_cart)
        db.commit()

        # Monkeypatch the resolver so resolve() returns a ResolutionResult pairing
        # the existing cartridge with the WRONG-diameter bullet.
        from drift.pipeline.resolution.resolver import EntityResolver as _EntityResolver
        from drift.pipeline.resolution.resolver import (
            MatchResult,
            ResolutionResult,
        )

        original_resolve = _EntityResolver.resolve

        def stub_resolve(self, extracted, entity_type):
            if entity_type != "cartridge":
                return original_resolve(self, extracted, entity_type)
            return ResolutionResult(
                entity_type="cartridge",
                manufacturer_id=nosler.id,
                caliber_id=cal_308.id,
                bullet_id=wrong_bullet.id,
                bullet_match_confidence=0.95,
                bullet_match_method="composite_key",
                match=MatchResult(
                    matched=True,
                    entity_id=existing_cart.id,
                    confidence=1.0,
                    method="exact_sku",
                ),
            )

        monkeypatch.setattr(_EntityResolver, "resolve", stub_resolve)

        # Build a minimal cartridge extraction
        extraction = {
            "url": "https://example.com/nosler/308win-180gr-accubond",
            "entity_type": "cartridge",
            "entities": [
                {
                    "name": {"value": "308 Win 180gr AccuBond", "confidence": 0.9},
                    "manufacturer": {"value": "Nosler", "confidence": 0.95},
                    "caliber": {"value": ".308 Winchester", "confidence": 0.95},
                    "sku": {"value": "TG-180", "confidence": 0.95},
                    "bullet_name": {"value": "270 Caliber 180gr Partition", "confidence": 0.9},
                    "bullet_weight_grains": {"value": 180.0, "confidence": 0.95},
                    "muzzle_velocity_fps": {"value": 2750, "confidence": 0.9},
                }
            ],
            "bc_sources": [],
            "data_source": "pipeline",
        }

        # Plumb into pipeline_store main
        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        (extracted_dir / "test.json").write_text(json.dumps(extraction), encoding="utf-8")
        report_path = tmp_path / "store_report.json"
        rejected_path = tmp_path / "rejected_calibers.json"

        monkeypatch.setattr(_store_mod, "EXTRACTED_DIR", extracted_dir)
        monkeypatch.setattr(_store_mod, "STORE_REPORT_PATH", report_path)
        monkeypatch.setattr(_store_mod, "REJECTED_CALIBERS_PATH", rejected_path)

        class _Factory:
            def __call__(self_inner):
                return _NoCloseSession(db)

        monkeypatch.setattr(_store_mod, "get_session_factory", lambda: _Factory())
        monkeypatch.setattr(sys, "argv", ["pipeline_store.py", "--commit"])

        _store_mod.main()

        report = json.loads(report_path.read_text(encoding="utf-8"))
        blocked_entries = [e for e in report["entries"] if e.get("action") == "blocked_cross_diameter"]
        assert len(blocked_entries) == 1, (
            f"Expected 1 blocked_cross_diameter entry; got {len(blocked_entries)}. "
            f"Actions seen: {[e.get('action') for e in report['entries']]}"
        )
        entry = blocked_entries[0]
        assert entry["proposed_bullet_id"] == wrong_bullet.id
        assert abs(entry["proposed_bullet_diameter_inches"] - 0.277) < 1e-6
        assert abs(entry["existing_caliber_diameter_inches"] - 0.308) < 1e-6
        assert any("cross-diameter" in w for w in entry.get("warnings", []))
        assert report["stats"]["cartridge"]["blocked_cross_diameter"] == 1

        # Critically: the existing cartridge's bullet_id must NOT have been overwritten.
        db.refresh(existing_cart)
        assert (
            existing_cart.bullet_id == correct_bullet.id
        ), "Store wrote the cross-diameter bullet_id despite the guard"

    def test_4_forensic_replay_no_cross_diameter_matched_updated(self, db, monkeypatch, tmp_path):
        """Integration: run the full pipeline_store against 5 representative bad
        pairs drawn from the v6 forensic (see
        data/forensic/v6-resolver-regression-2026-04-22/relinks.tsv). Assert the
        resulting store_report contains ZERO ``matched_updated`` actions whose
        proposed bullet diameter disagrees with the existing cartridge's
        caliber diameter. Cross-diameter proposals may still occur at the
        resolver layer — the store guard converts them to
        ``blocked_cross_diameter`` instead of committing."""
        # Seed DB
        nosler = Manufacturer(name="Nosler", type_tags=["ammo_maker"], country="USA")
        hornady = Manufacturer(name="Hornady", type_tags=["ammo_maker"], country="USA")
        db.add_all([nosler, hornady])
        db.flush()

        cal_308 = Caliber(name=".308 Winchester", bullet_diameter_inches=0.308)
        cal_375 = Caliber(name=".375 H&H Magnum", bullet_diameter_inches=0.375)
        cal_6arc = Caliber(name="6mm ARC", bullet_diameter_inches=0.243)
        cal_257 = Caliber(name=".257 Roberts", bullet_diameter_inches=0.257)
        db.add_all([cal_308, cal_375, cal_6arc, cal_257])
        db.flush()

        b_308_180 = Bullet(
            manufacturer_id=nosler.id,
            name="30 Caliber 180gr AccuBond",
            bullet_diameter_inches=0.308,
            weight_grains=180.0,
        )
        b_6arc_80 = Bullet(
            manufacturer_id=hornady.id,
            name="6mm .243 80 gr ELD-VT",
            bullet_diameter_inches=0.243,
            weight_grains=80.0,
        )
        b_224_80 = Bullet(
            manufacturer_id=hornady.id,
            name="22 Cal .224 80 gr ELD-X",
            bullet_diameter_inches=0.224,
            weight_grains=80.0,
        )
        db.add_all([b_308_180, b_6arc_80, b_224_80])
        db.flush()

        # Existing cartridges in DB
        cart_308 = Cartridge(
            manufacturer_id=nosler.id,
            caliber_id=cal_308.id,
            bullet_id=b_308_180.id,
            name="308 Win 180gr AccuBond",
            sku="TG-180",
            bullet_weight_grains=180.0,
            muzzle_velocity_fps=2750,
        )
        cart_6arc = Cartridge(
            manufacturer_id=hornady.id,
            caliber_id=cal_6arc.id,
            bullet_id=b_6arc_80.id,
            name="6mm ARC 80 gr ELD-VT V-Match",
            sku="81611",
            bullet_weight_grains=80.0,
            muzzle_velocity_fps=3100,
        )
        db.add_all([cart_308, cart_6arc])
        db.commit()

        # 5 cartridge extractions drawn from forensic patterns
        extraction = {
            "url": "https://example.com/forensic-replay",
            "entity_type": "cartridge",
            "entities": [
                # 1. .375 H&H with SKU collision — must not cross-match .308 cart
                {
                    "name": {"value": "375 H&H Mag 300gr AccuBond", "confidence": 0.95},
                    "manufacturer": {"value": "Nosler", "confidence": 0.95},
                    "caliber": {"value": ".375 H&H Magnum", "confidence": 0.95},
                    "sku": {"value": "TG-180", "confidence": 0.95},
                    "bullet_name": {"value": "30 Caliber 300gr AccuBond", "confidence": 0.9},
                    "bullet_weight_grains": {"value": 300.0, "confidence": 0.95},
                    "muzzle_velocity_fps": {"value": 2600, "confidence": 0.9},
                },
                # 2. .22 ARC — caliber absent → fuzzy-resolves to 6mm ARC. Store
                #    guard should prevent the .224 bullet pairing from writing to
                #    the existing 6mm ARC cartridge.
                {
                    "name": {"value": "22 ARC 80 gr ELD-X Precision Hunter", "confidence": 0.9},
                    "manufacturer": {"value": "Hornady", "confidence": 0.95},
                    "caliber": {"value": ".22 ARC", "confidence": 0.9},
                    "bullet_name": {"value": "22 Cal .224 80 gr ELD-X", "confidence": 0.9},
                    "bullet_weight_grains": {"value": 80.0, "confidence": 0.95},
                    "muzzle_velocity_fps": {"value": 3100, "confidence": 0.9},
                },
                # 3. Legitimate .308 Win 180gr match — should update cleanly
                {
                    "name": {"value": "308 Win 180gr AccuBond Trophy Grade", "confidence": 0.95},
                    "manufacturer": {"value": "Nosler", "confidence": 0.95},
                    "caliber": {"value": ".308 Winchester", "confidence": 0.95},
                    "sku": {"value": "TG-180", "confidence": 0.95},
                    "bullet_name": {"value": "30 Caliber 180gr AccuBond", "confidence": 0.95},
                    "bullet_weight_grains": {"value": 180.0, "confidence": 0.95},
                    "muzzle_velocity_fps": {"value": 2750, "confidence": 0.9},
                },
                # 4. .257 Roberts with .224 bullet in extract — cross-diameter pairing
                {
                    "name": {"value": "Nosler Obscure Load 80gr", "confidence": 0.9},
                    "manufacturer": {"value": "Nosler", "confidence": 0.95},
                    "caliber": {"value": ".257 Roberts", "confidence": 0.95},
                    "bullet_name": {"value": "22 Cal .224 80 gr ELD-X", "confidence": 0.9},
                    "bullet_weight_grains": {"value": 80.0, "confidence": 0.95},
                    "muzzle_velocity_fps": {"value": 3200, "confidence": 0.9},
                },
                # 5. Weight-only collision: same weight exists in 6mm and .22, bullet
                #    name matches .224. Resolver might find a match; store guard
                #    must reject cross-diameter write.
                {
                    "name": {"value": "Weight Collision Cart 80gr", "confidence": 0.9},
                    "manufacturer": {"value": "Hornady", "confidence": 0.95},
                    "caliber": {"value": "6mm ARC", "confidence": 0.95},
                    "bullet_name": {"value": "22 Cal .224 80 gr ELD-X", "confidence": 0.9},
                    "bullet_weight_grains": {"value": 80.0, "confidence": 0.95},
                    "muzzle_velocity_fps": {"value": 3100, "confidence": 0.9},
                },
            ],
            "bc_sources": [],
            "data_source": "pipeline",
        }

        # Set up pipeline_store paths
        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        (extracted_dir / "test.json").write_text(json.dumps(extraction), encoding="utf-8")
        report_path = tmp_path / "store_report.json"
        rejected_path = tmp_path / "rejected_calibers.json"

        monkeypatch.setattr(_store_mod, "EXTRACTED_DIR", extracted_dir)
        monkeypatch.setattr(_store_mod, "STORE_REPORT_PATH", report_path)
        monkeypatch.setattr(_store_mod, "REJECTED_CALIBERS_PATH", rejected_path)

        class _Factory:
            def __call__(self_inner):
                return _NoCloseSession(db)

        monkeypatch.setattr(_store_mod, "get_session_factory", lambda: _Factory())
        monkeypatch.setattr(sys, "argv", ["pipeline_store.py"])  # dry-run

        _store_mod.main()

        report = json.loads(report_path.read_text(encoding="utf-8"))

        # Assertion: no matched_updated entry has cross-diameter pairing.
        cross_diameter_matched_updates = []
        for e in report["entries"]:
            if e.get("action") != "matched_updated":
                continue
            cart_id = e.get("match_entity_id")
            new_bid = e.get("bullet_id")
            if not cart_id or not new_bid:
                continue
            existing_cart = db.get(Cartridge, cart_id)
            new_bullet = db.get(Bullet, new_bid)
            if existing_cart and new_bullet:
                cal = db.get(Caliber, existing_cart.caliber_id)
                if cal and abs(cal.bullet_diameter_inches - new_bullet.bullet_diameter_inches) > 0.005:
                    cross_diameter_matched_updates.append(
                        f"cart={existing_cart.name[:40]} (cal={cal.bullet_diameter_inches})  "
                        f"← bullet={new_bullet.name[:40]} ({new_bullet.bullet_diameter_inches})"
                    )

        assert (
            not cross_diameter_matched_updates
        ), "Store produced cross-diameter matched_updated entries:\n  " + "\n  ".join(cross_diameter_matched_updates)
