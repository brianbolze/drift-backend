# flake8: noqa: E501
"""Tests for pipeline_store auto-create weight variant logic."""

import importlib
import sys
from pathlib import Path

import pytest

from drift.models import Bullet, Caliber, Cartridge, Manufacturer
from drift.pipeline.resolution.resolver import MatchResult, ResolutionResult

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
_store_mod = importlib.import_module("pipeline_store")
_should_auto_create_weight_variant = _store_mod._should_auto_create_weight_variant
AUTO_CREATE_CONFIDENCE_CEILING = _store_mod.AUTO_CREATE_CONFIDENCE_CEILING


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
