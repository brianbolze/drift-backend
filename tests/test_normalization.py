"""Tests for the pipeline normalization step (unit-confusion + range guards).

Covers the Lapua G580 regression target from TODO.md and the four flag-don't-store
fields called out in docs/entity_resolution_review.md finding #19: BC, muzzle
velocity, bullet weight, bullet diameter.
"""

from __future__ import annotations

import pytest

from drift.pipeline.config import VALIDATION_RANGES
from drift.pipeline.normalization import (
    FPS_PER_MPS,
    GRAINS_PER_GRAM,
    MM_PER_INCH,
    normalize_entity,
)


def _ev(value, confidence=0.9):
    return {"value": value, "confidence": confidence}


def _val(entity, field):
    payload = entity[field]
    return payload["value"] if isinstance(payload, dict) else payload


# ── Unit-confusion heuristics ────────────────────────────────────────────────


class TestGramsToGrains:
    def test_lapua_g580_regression(self):
        """6.5 g (extracted into weight_grains) → 100.3 gr."""
        entity = {
            "name": _ev("Lapua Scenar-L 100gr"),
            "manufacturer": _ev("Lapua"),
            "bullet_diameter_inches": _ev(0.308),
            "weight_grains": _ev(6.5),
        }
        result = normalize_entity(entity, "bullet")
        assert not result.rejected
        assert len(result.events) == 1
        event = result.events[0]
        assert event.field == "weight_grains"
        assert event.reason == "grams_to_grains"
        assert event.original_value == 6.5
        assert event.normalized_value == pytest.approx(6.5 * GRAINS_PER_GRAM)
        assert _val(result.entity, "weight_grains") == pytest.approx(100.3, abs=0.1)

    def test_cartridge_bullet_weight_grams(self):
        """bullet_weight_grains in grams gets the same treatment."""
        entity = {
            "name": _ev("Lapua 6.5 Creedmoor 136gr Scenar-L"),
            "manufacturer": _ev("Lapua"),
            "caliber": _ev("6.5 Creedmoor"),
            "bullet_weight_grains": _ev(8.8),
        }
        result = normalize_entity(entity, "cartridge")
        assert not result.rejected
        assert _val(result.entity, "bullet_weight_grains") == pytest.approx(8.8 * GRAINS_PER_GRAM)

    def test_in_range_weight_untouched(self):
        entity = {"name": _ev("140gr ELD Match"), "weight_grains": _ev(140.0)}
        result = normalize_entity(entity, "bullet")
        assert result.events == []
        assert _val(result.entity, "weight_grains") == 140.0

    def test_european_decimal_comma_string(self):
        """Extractions sometimes leak '6,5' (strings with comma decimals)."""
        entity = {"name": _ev("Lapua"), "weight_grains": _ev("6,5")}
        result = normalize_entity(entity, "bullet")
        assert not result.rejected
        assert _val(result.entity, "weight_grains") == pytest.approx(6.5 * GRAINS_PER_GRAM)


class TestMpsToFps:
    def test_low_mv_converted(self):
        """305 m/s → ~1001 fps, inside valid range."""
        entity = {
            "name": _ev("Subsonic .300 BLK"),
            "muzzle_velocity_fps": _ev(305),
        }
        result = normalize_entity(entity, "cartridge")
        event = next(e for e in result.events if e.field == "muzzle_velocity_fps")
        assert event.reason == "m/s_to_fps"
        assert _val(result.entity, "muzzle_velocity_fps") == pytest.approx(305 * FPS_PER_MPS)

    def test_rifle_fps_preserved(self):
        entity = {"name": _ev("6.5 Creedmoor 140gr"), "muzzle_velocity_fps": _ev(2700)}
        result = normalize_entity(entity, "cartridge")
        assert result.events == []
        assert _val(result.entity, "muzzle_velocity_fps") == 2700

    def test_low_fps_unrecoverable_nulled(self):
        """50 fps is nonsense and 50 m/s → 164 fps (still out of range) → null + flag."""
        entity = {"name": _ev("Garbage"), "muzzle_velocity_fps": _ev(50)}
        result = normalize_entity(entity, "cartridge")
        assert _val(result.entity, "muzzle_velocity_fps") is None
        assert any("muzzle_velocity_fps" in w and "nulled" in w for w in result.warnings)


class TestMmToInches:
    def test_6p5_mm_to_inches(self):
        entity = {
            "name": _ev("140gr Hybrid"),
            "bullet_diameter_inches": _ev(6.5),
            "weight_grains": _ev(140.0),
        }
        result = normalize_entity(entity, "bullet")
        event = next(e for e in result.events if e.field == "bullet_diameter_inches")
        assert event.reason == "mm_to_inches"
        assert _val(result.entity, "bullet_diameter_inches") == pytest.approx(6.5 / MM_PER_INCH)

    def test_7p62_mm_to_inches(self):
        entity = {
            "name": _ev("7.62 NATO bullet"),
            "bullet_diameter_inches": _ev(7.62),
            "weight_grains": _ev(147.0),
        }
        result = normalize_entity(entity, "bullet")
        assert not result.rejected
        assert _val(result.entity, "bullet_diameter_inches") == pytest.approx(0.300, abs=0.001)

    def test_valid_inches_diameter_untouched(self):
        entity = {
            "name": _ev("30cal bullet"),
            "bullet_diameter_inches": _ev(0.308),
            "weight_grains": _ev(168.0),
        }
        result = normalize_entity(entity, "bullet")
        assert result.events == []

    def test_length_mm_conversion(self):
        """length_inches=30 (mm) → 1.18 in."""
        entity = {
            "name": _ev("Tall bullet"),
            "bullet_diameter_inches": _ev(0.308),
            "weight_grains": _ev(180.0),
            "length_inches": _ev(30.0),
        }
        result = normalize_entity(entity, "bullet")
        event = next(e for e in result.events if e.field == "length_inches")
        assert event.reason == "mm_to_inches"
        assert _val(result.entity, "length_inches") == pytest.approx(30.0 / MM_PER_INCH)


# ── Range flag-don't-store guards ────────────────────────────────────────────


class TestRangeGuards:
    def test_out_of_range_bc_nulled_non_rejected(self):
        """BC G1 of 5.0 is absurd; null it but don't reject the cartridge."""
        entity = {
            "name": _ev("Some cartridge"),
            "bc_g1": _ev(5.0),
            "bc_g7": _ev(0.25),
        }
        result = normalize_entity(entity, "cartridge")
        assert not result.rejected
        assert _val(result.entity, "bc_g1") is None
        assert _val(result.entity, "bc_g7") == 0.25
        assert any("bc_g1" in w and "nulled" in w for w in result.warnings)

    def test_zero_bc_nulled(self):
        """BC of 0.01 is below the 0.05 floor; nulled."""
        entity = {"name": _ev("cart"), "bc_g1": _ev(0.01)}
        result = normalize_entity(entity, "cartridge")
        assert _val(result.entity, "bc_g1") is None

    def test_bullet_diameter_out_of_range_rejects_bullet(self):
        """A 50mm diameter doesn't recover via mm→inches (50/25.4=1.97); reject the bullet."""
        entity = {
            "name": _ev("Bogus"),
            "bullet_diameter_inches": _ev(50.0),
            "weight_grains": _ev(180.0),
        }
        result = normalize_entity(entity, "bullet")
        assert result.rejected
        assert result.rejection_reason is not None
        assert "bullet_diameter_inches" in result.rejection_reason

    def test_bullet_weight_out_of_range_rejects_bullet(self):
        """Weight of 0.3 (grams or not) doesn't recover; reject the bullet."""
        entity = {
            "name": _ev("Bogus"),
            "bullet_diameter_inches": _ev(0.308),
            "weight_grains": _ev(0.3),
        }
        result = normalize_entity(entity, "bullet")
        assert result.rejected
        assert "weight_grains" in (result.rejection_reason or "")

    def test_cartridge_bad_weight_is_nulled_not_rejected(self):
        """Cartridge-level bad weight is NOT critical — null it but keep processing."""
        entity = {
            "name": _ev("Cart"),
            "manufacturer": _ev("Mfr"),
            "bullet_weight_grains": _ev(0.1),
        }
        result = normalize_entity(entity, "cartridge")
        assert not result.rejected
        assert _val(result.entity, "bullet_weight_grains") is None

    def test_muzzle_velocity_out_of_range_nulled_for_cartridge(self):
        """MV of 99999 can't be an m/s (99999*3.28=too high); null + flag."""
        entity = {"name": _ev("Cart"), "muzzle_velocity_fps": _ev(99999)}
        result = normalize_entity(entity, "cartridge")
        assert _val(result.entity, "muzzle_velocity_fps") is None
        assert not result.rejected  # MV not critical to cartridge identity


# ── Identity and robustness ──────────────────────────────────────────────────


class TestInvariants:
    def test_original_entity_not_mutated(self):
        entity = {
            "name": _ev("Lapua"),
            "weight_grains": _ev(6.5),
            "bullet_diameter_inches": _ev(0.308),
        }
        result = normalize_entity(entity, "bullet")
        assert _val(result.entity, "weight_grains") != 6.5  # normalized copy changed
        assert _val(entity, "weight_grains") == 6.5  # original untouched

    def test_missing_fields_no_op(self):
        entity = {"name": _ev("Minimal")}
        result = normalize_entity(entity, "bullet")
        assert result.events == []
        assert not result.rejected

    def test_none_values_no_op(self):
        entity = {
            "name": _ev("Partial"),
            "bullet_diameter_inches": _ev(None),
            "weight_grains": _ev(None),
            "bc_g1": _ev(None),
        }
        result = normalize_entity(entity, "bullet")
        assert result.events == []
        assert not result.rejected

    def test_unparseable_string_ignored(self):
        entity = {"name": _ev("Garbage in"), "weight_grains": _ev("not-a-number")}
        result = normalize_entity(entity, "bullet")
        assert result.events == []

    def test_rifle_entity_type_has_no_critical_fields(self):
        """Rifles don't have bullet identity fields; range violations don't reject."""
        entity = {
            "model": _ev("Some rifle"),
            "barrel_length_inches": _ev(100.0),
            "weight_lbs": _ev(100.0),
        }
        result = normalize_entity(entity, "rifle")
        assert not result.rejected

    def test_in_range_string_value_coerced_to_float(self):
        """An in-range string value still gets silently coerced to a numeric type."""
        entity = {
            "name": _ev("Normal bullet"),
            "weight_grains": _ev("168"),
            "bullet_diameter_inches": _ev("0.308"),
        }
        result = normalize_entity(entity, "bullet")
        # No conversion event (value was already in range), just cleanup
        assert all(e.field not in {"weight_grains", "bullet_diameter_inches"} for e in result.events)
        assert _val(result.entity, "weight_grains") == 168.0
        assert _val(result.entity, "bullet_diameter_inches") == 0.308

    def test_validation_ranges_have_conversion_or_are_dimensionless(self):
        """Sanity check: every conversion target in VALIDATION_RANGES is consistent."""
        # This doesn't enforce anything new; it's a guard against future drift.
        assert "bullet_diameter_inches" in VALIDATION_RANGES
        assert "weight_grains" in VALIDATION_RANGES
        assert "muzzle_velocity_fps" in VALIDATION_RANGES
        assert "bc_g1" in VALIDATION_RANGES
        assert "bc_g7" in VALIDATION_RANGES
