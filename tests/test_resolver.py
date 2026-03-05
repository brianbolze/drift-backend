# flake8: noqa: E501
"""Tests for the EntityResolver — bullet/cartridge/rifle resolution paths."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from drift.models import Base, Bullet, Caliber, Cartridge, Manufacturer
from drift.pipeline.resolution.resolver import EntityResolver, ResolutionResult


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def seeded(db):
    """Seed a minimal set of entities for resolver testing."""
    mfr = Manufacturer(name="Hornady", alt_names=["Hornady Mfg"], type_tags=["bullet_maker", "ammo_maker"], country="USA")
    db.add(mfr)
    db.flush()

    cal_65 = Caliber(name="6.5 Creedmoor", alt_names=["6.5 CM"], bullet_diameter_inches=0.264)
    cal_308 = Caliber(name=".308 Winchester", alt_names=[".308 Win"], bullet_diameter_inches=0.308)
    db.add_all([cal_65, cal_308])
    db.flush()

    b1 = Bullet(
        manufacturer_id=mfr.id, name="140 ELD Match", sku="26331",
        bullet_diameter_inches=0.264, weight_grains=140.0,
        bc_g7_published=0.326,
    )
    b2 = Bullet(
        manufacturer_id=mfr.id, name="178 ELD-X",
        bullet_diameter_inches=0.308, weight_grains=178.0,
        bc_g7_published=0.263,
    )
    b3 = Bullet(
        manufacturer_id=mfr.id, name="143 ELD-X",
        bullet_diameter_inches=0.264, weight_grains=143.0,
        bc_g7_published=0.315,
    )
    db.add_all([b1, b2, b3])
    db.flush()

    cart = Cartridge(
        manufacturer_id=mfr.id, caliber_id=cal_65.id, bullet_id=b1.id,
        name="Hornady 6.5 CM 140gr ELD Match", sku="81500",
        bullet_weight_grains=140.0, muzzle_velocity_fps=2710,
    )
    db.add(cart)
    db.commit()

    return {
        "mfr": mfr, "cal_65": cal_65, "cal_308": cal_308,
        "b1": b1, "b2": b2, "b3": b3, "cart": cart,
    }


# ---------------------------------------------------------------------------
# ResolutionResult defaults
# ---------------------------------------------------------------------------


def test_resolution_result_defaults():
    """bullet_diameter_inches defaults to None in a fresh ResolutionResult."""
    r = ResolutionResult(entity_type="bullet")
    assert r.bullet_diameter_inches is None
    assert r.unresolved_refs == []
    assert r.warnings == []
    assert r.match.matched is False


# ---------------------------------------------------------------------------
# resolve("bullet") — full path through resolve()
# ---------------------------------------------------------------------------


def test_resolve_bullet_exact_sku(seeded, db):
    """resolve('bullet') with SKU should find exact match."""
    resolver = EntityResolver(db)
    extracted = {
        "name": {"value": "140 ELD Match"},
        "manufacturer": {"value": "Hornady"},
        "bullet_diameter_inches": {"value": 0.264},
        "weight_grains": {"value": 140.0},
        "sku": {"value": "26331"},
    }
    result = resolver.resolve(extracted, "bullet")
    assert result.entity_type == "bullet"
    assert result.match.matched is True
    assert result.match.method == "exact_sku"
    assert result.match.entity_id == seeded["b1"].id
    assert result.bullet_diameter_inches == 0.264
    assert result.manufacturer_id == seeded["mfr"].id
    assert result.unresolved_refs == []


def test_resolve_bullet_composite_match(seeded, db):
    """resolve('bullet') without SKU falls back to composite key match."""
    resolver = EntityResolver(db)
    extracted = {
        "name": {"value": "ELD Match 140"},
        "manufacturer": {"value": "Hornady"},
        "bullet_diameter_inches": {"value": 0.264},
        "weight_grains": {"value": 140.0},
    }
    result = resolver.resolve(extracted, "bullet")
    assert result.match.matched is True
    assert result.match.method in ("composite_key", "fuzzy_name")
    assert result.match.entity_id == seeded["b1"].id


def test_resolve_bullet_no_diameter(seeded, db):
    """resolve('bullet') with missing diameter adds unresolved ref."""
    resolver = EntityResolver(db)
    extracted = {
        "name": {"value": "140 ELD Match"},
        "manufacturer": {"value": "Hornady"},
        "weight_grains": {"value": 140.0},
    }
    result = resolver.resolve(extracted, "bullet")
    assert "bullet_diameter_inches: not extracted" in result.unresolved_refs
    assert result.bullet_diameter_inches is None


def test_resolve_bullet_invalid_diameter(seeded, db):
    """resolve('bullet') with non-numeric diameter adds unresolved ref."""
    resolver = EntityResolver(db)
    extracted = {
        "name": {"value": "140 ELD Match"},
        "manufacturer": {"value": "Hornady"},
        "bullet_diameter_inches": {"value": "not-a-number"},
        "weight_grains": {"value": 140.0},
    }
    result = resolver.resolve(extracted, "bullet")
    assert any("invalid value" in ref for ref in result.unresolved_refs)
    assert result.bullet_diameter_inches is None


# ---------------------------------------------------------------------------
# Diameter tolerance: ±0.001"
# ---------------------------------------------------------------------------


def test_diameter_tolerance_within_range(seeded, db):
    """A diameter within ±0.001" of 0.264 should still match .264 bullets."""
    resolver = EntityResolver(db)
    # 0.265 is within tolerance of 0.264
    result = resolver.match_bullet(
        {"name": {"value": "140 ELD Match"}, "weight_grains": {"value": 140.0}},
        manufacturer_id=seeded["mfr"].id,
        bullet_diameter_inches=0.265,
    )
    assert result.matched is True
    assert result.entity_id == seeded["b1"].id


def test_diameter_tolerance_outside_range(seeded, db):
    """A diameter outside ±0.001" should NOT match."""
    resolver = EntityResolver(db)
    # 0.266 is outside tolerance of 0.264
    result = resolver.match_bullet(
        {"name": {"value": "140 ELD Match"}, "weight_grains": {"value": 140.0}},
        manufacturer_id=seeded["mfr"].id,
        bullet_diameter_inches=0.266,
    )
    assert result.matched is False


def test_diameter_tolerance_exact_boundary(seeded, db):
    """Exactly ±0.001" from the stored value should match (inclusive)."""
    resolver = EntityResolver(db)
    # 0.264 + 0.001 = 0.265 — should match (between is inclusive)
    result_upper = resolver.match_bullet(
        {"name": {"value": "ELD Match"}, "weight_grains": {"value": 140.0}},
        manufacturer_id=seeded["mfr"].id,
        bullet_diameter_inches=0.264 + 0.001,
    )
    assert result_upper.matched is True

    # 0.264 - 0.001 = 0.263 — should match
    result_lower = resolver.match_bullet(
        {"name": {"value": "ELD Match"}, "weight_grains": {"value": 140.0}},
        manufacturer_id=seeded["mfr"].id,
        bullet_diameter_inches=0.264 - 0.001,
    )
    assert result_lower.matched is True


# ---------------------------------------------------------------------------
# Diameter filter prevents cross-caliber matching
# ---------------------------------------------------------------------------


def test_diameter_prevents_cross_caliber_match(seeded, db):
    """A .308 diameter should NOT match a .264 bullet even if name is similar."""
    resolver = EntityResolver(db)
    result = resolver.match_bullet(
        {"name": {"value": "140 ELD Match"}, "weight_grains": {"value": 140.0}},
        manufacturer_id=seeded["mfr"].id,
        bullet_diameter_inches=0.308,
    )
    # Should not match the .264 bullet
    if result.matched:
        assert result.entity_id != seeded["b1"].id


# ---------------------------------------------------------------------------
# Cartridge → bullet via caliber diameter lookup
# ---------------------------------------------------------------------------


def test_resolve_cartridge_resolves_bullet_via_diameter(seeded, db):
    """resolve('cartridge') should look up caliber diameter to match bullets."""
    resolver = EntityResolver(db)
    extracted = {
        "name": {"value": "Hornady 6.5 CM 140gr ELD Match"},
        "manufacturer": {"value": "Hornady"},
        "caliber": {"value": "6.5 Creedmoor"},
        "bullet_name": {"value": "140 ELD Match"},
        "bullet_weight_grains": {"value": 140.0},
        "sku": {"value": "81500"},
    }
    result = resolver.resolve(extracted, "cartridge")
    assert result.caliber_id == seeded["cal_65"].id
    assert result.bullet_id == seeded["b1"].id


def test_resolve_cartridge_no_bullet_name(seeded, db):
    """resolve('cartridge') without bullet_name should still resolve caliber."""
    resolver = EntityResolver(db)
    extracted = {
        "name": {"value": "Some 6.5 CM Load"},
        "manufacturer": {"value": "Hornady"},
        "caliber": {"value": "6.5 Creedmoor"},
        "bullet_weight_grains": {"value": 140.0},
    }
    result = resolver.resolve(extracted, "cartridge")
    assert result.caliber_id == seeded["cal_65"].id
    # No bullet_name provided, so bullet_id resolution is skipped
    assert result.bullet_id is None


# ---------------------------------------------------------------------------
# resolve("cartridge") regression — full path
# ---------------------------------------------------------------------------


def test_resolve_cartridge_full_path(seeded, db):
    """Full cartridge resolution including manufacturer, caliber, and entity match."""
    resolver = EntityResolver(db)
    extracted = {
        "name": {"value": "Hornady 6.5 CM 140gr ELD Match"},
        "manufacturer": {"value": "Hornady"},
        "caliber": {"value": "6.5 CM"},
        "bullet_name": {"value": "140 ELD Match"},
        "bullet_weight_grains": {"value": 140.0},
        "sku": {"value": "81500"},
    }
    result = resolver.resolve(extracted, "cartridge")
    assert result.match.matched is True
    assert result.match.method == "exact_sku"
    assert result.manufacturer_id == seeded["mfr"].id
    assert result.caliber_id == seeded["cal_65"].id


# ---------------------------------------------------------------------------
# Validation range (config.py)
# ---------------------------------------------------------------------------


def test_validation_range_covers_standard_diameters():
    """The bullet_diameter_inches range should cover .17 HMR through .50 BMG."""
    from drift.pipeline.config import VALIDATION_RANGES

    lo, hi = VALIDATION_RANGES["bullet_diameter_inches"]
    assert lo == 0.172  # .17 HMR
    assert hi == 0.510  # .50 BMG

    # Common diameters should be within range
    common_diameters = [0.172, 0.224, 0.243, 0.264, 0.277, 0.284, 0.308, 0.338, 0.375, 0.416, 0.458, 0.510]
    for d in common_diameters:
        assert lo <= d <= hi, f"Diameter {d} outside validation range ({lo}, {hi})"


# ---------------------------------------------------------------------------
# match_bullet diameter filter warning
# ---------------------------------------------------------------------------


def test_match_bullet_warns_on_none_diameter(seeded, db, caplog):
    """match_bullet with None diameter should log a warning."""
    import logging
    with caplog.at_level(logging.WARNING, logger="drift.pipeline.resolution.resolver"):
        resolver = EntityResolver(db)
        resolver.match_bullet(
            {"name": {"value": "140 ELD Match"}, "weight_grains": {"value": 140.0}},
            manufacturer_id=seeded["mfr"].id,
            bullet_diameter_inches=None,
        )
    assert any("diameter filter" in msg for msg in caplog.messages)
