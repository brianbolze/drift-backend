# flake8: noqa: E501
"""Tests for the EntityResolver — bullet/cartridge/rifle resolution paths."""

# Import store-level rejection helper (script, but importable)
import importlib
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from drift.models import Base, Bullet, Caliber, Cartridge, Manufacturer
from drift.pipeline.resolution.resolver import (
    EntityResolver,
    ResolutionResult,
    _bc_weight_confidence_boost,
    _bullet_name_score,
    _expand_abbreviations,
    _name_similarity,
    _normalize,
    _normalize_caliber,
)

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
_store_mod = importlib.import_module("pipeline_store")
_has_rejected_caliber = _store_mod._has_rejected_caliber
_load_rejected_calibers = _store_mod._load_rejected_calibers


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def seeded(db):
    """Seed a minimal set of entities for resolver testing."""
    mfr = Manufacturer(
        name="Hornady", alt_names=["Hornady Mfg"], type_tags=["bullet_maker", "ammo_maker"], country="USA"
    )
    db.add(mfr)
    db.flush()

    cal_65 = Caliber(name="6.5 Creedmoor", alt_names=["6.5 CM"], bullet_diameter_inches=0.264)
    cal_308 = Caliber(name=".308 Winchester", alt_names=[".308 Win"], bullet_diameter_inches=0.308)
    db.add_all([cal_65, cal_308])
    db.flush()

    b1 = Bullet(
        manufacturer_id=mfr.id,
        name="140 ELD Match",
        sku="26331",
        bullet_diameter_inches=0.264,
        weight_grains=140.0,
        bc_g7_published=0.326,
    )
    b2 = Bullet(
        manufacturer_id=mfr.id,
        name="178 ELD-X",
        bullet_diameter_inches=0.308,
        weight_grains=178.0,
        bc_g7_published=0.263,
    )
    b3 = Bullet(
        manufacturer_id=mfr.id,
        name="143 ELD-X",
        bullet_diameter_inches=0.264,
        weight_grains=143.0,
        bc_g7_published=0.315,
    )
    db.add_all([b1, b2, b3])
    db.flush()

    cart = Cartridge(
        manufacturer_id=mfr.id,
        caliber_id=cal_65.id,
        bullet_id=b1.id,
        name="Hornady 6.5 CM 140gr ELD Match",
        sku="81500",
        bullet_weight_grains=140.0,
        muzzle_velocity_fps=2710,
    )
    db.add(cart)
    db.commit()

    return {
        "mfr": mfr,
        "cal_65": cal_65,
        "cal_308": cal_308,
        "b1": b1,
        "b2": b2,
        "b3": b3,
        "cart": cart,
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


# ---------------------------------------------------------------------------
# _bullet_name_score — unit tests for containment-based scoring
# ---------------------------------------------------------------------------


class TestBulletNameScore:
    """Tests for the containment-based bullet name scoring function."""

    def test_short_type_name_matches_long_db_name(self):
        """'ELD-X' should score highly against '30 Cal .308 178 gr ELD-X®'."""
        score = _bullet_name_score("ELD-X", "30 Cal .308 178 gr ELD-X®")
        assert score > 0.5

    def test_single_keyword_match(self):
        """Single keyword like 'CX®' should match '6.5mm .264 120 gr CX®'."""
        score = _bullet_name_score("CX®", "6.5mm .264 120 gr CX®")
        assert score > 0.3

    def test_multi_word_type_name(self):
        """'ELD® Match' should score high against '30 Cal .308 178 gr ELD® Match'."""
        score = _bullet_name_score("ELD® Match", "30 Cal .308 178 gr ELD® Match")
        assert score > 0.7

    def test_manufacturer_prefix_in_extracted_name(self):
        """'Nosler Partition' should match '30 Caliber 200gr Partition (50ct)'."""
        score = _bullet_name_score("Nosler Partition", "30 Caliber 200gr Partition (50ct)")
        # "nosler" won't appear in DB name, but "partition" will — partial match
        assert score > 0.3

    def test_no_overlap_returns_zero(self):
        """Completely unrelated names should score 0."""
        score = _bullet_name_score("Jacketed Soft Point", "ELD-X Match Target")
        assert score == 0.0

    def test_empty_names(self):
        """Empty strings should return 0."""
        assert _bullet_name_score("", "some bullet") == 0.0
        assert _bullet_name_score("ELD-X", "") == 0.0

    def test_abbreviation_expansion_sp_matches_soft_point(self):
        """SP in DB name should match 'Soft Point' via abbreviation expansion."""
        score = _bullet_name_score("Soft Point", "30 Cal .308 150 gr InterLock® SP")
        # SP expands to {soft, point} so this is a valid match
        assert score > 0.3

    def test_trademark_symbols_stripped(self):
        """Trademark symbols (®, ™) should not affect matching."""
        score_with = _bullet_name_score("SST®", "6.5mm .264 123 gr SST®")
        score_without = _bullet_name_score("SST", "6.5mm .264 123 gr SST®")
        assert score_with == score_without

    def test_higher_score_for_more_keywords(self):
        """Multi-word matches should score higher than single-word."""
        score_1 = _bullet_name_score("CX", "30 Cal .308 165 gr CX®")
        score_2 = _bullet_name_score("ELD Match", "30 Cal .308 178 gr ELD® Match")
        assert score_2 > score_1

    def test_noise_words_ignored(self):
        """Numeric tokens and noise words (gr, cal, bullet) shouldn't inflate scores."""
        # "140" is numeric, "grain" is noise — only "eld" and "match" are meaningful
        score = _bullet_name_score("140 Grain ELD Match", "30 Cal .308 178 gr ELD® Match")
        assert score > 0.5


# ---------------------------------------------------------------------------
# _normalize_caliber — unit tests
# ---------------------------------------------------------------------------


class TestNormalizeCaliber:
    def test_strips_leading_period(self):
        assert _normalize_caliber(".308 Winchester") == "308 winchester"

    def test_no_period_unchanged(self):
        assert _normalize_caliber("308 Win") == "308 win"

    def test_both_forms_equal(self):
        assert _normalize_caliber(".308 Win") == _normalize_caliber("308 Win")

    def test_metric_caliber(self):
        assert _normalize_caliber("6.5 Creedmoor") == "6.5 creedmoor"


# ---------------------------------------------------------------------------
# Asymmetric bullet matching — integration tests via match_bullet
# ---------------------------------------------------------------------------


@pytest.fixture()
def cartridge_bullets(db):
    """Seed DB with realistic bullet names (long product strings) for cartridge matching tests."""
    hornady = Manufacturer(name="Hornady", alt_names=["Hornady Mfg"], type_tags=["bullet_maker"], country="USA")
    federal = Manufacturer(name="Federal", alt_names=[], type_tags=["ammo_maker"], country="USA")
    nosler = Manufacturer(name="Nosler", alt_names=[], type_tags=["bullet_maker"], country="USA")
    sierra = Manufacturer(name="Sierra Bullets", alt_names=["Sierra"], type_tags=["bullet_maker"], country="USA")
    berger = Manufacturer(name="Berger Bullets", alt_names=["Berger"], type_tags=["bullet_maker"], country="USA")
    db.add_all([hornady, federal, nosler, sierra, berger])
    db.flush()

    cal_308 = Caliber(name=".308 Winchester", alt_names=[".308 Win"], bullet_diameter_inches=0.308)
    cal_65 = Caliber(name="6.5 Creedmoor", alt_names=["6.5 CM"], bullet_diameter_inches=0.264)
    cal_270 = Caliber(name=".270 Winchester", alt_names=[".270 Win"], bullet_diameter_inches=0.277)
    db.add_all([cal_308, cal_65, cal_270])
    db.flush()

    bullets = [
        # Hornady — long product names with caliber/weight prefixes
        Bullet(
            manufacturer_id=hornady.id,
            name="30 Cal .308 178 gr ELD-X®",
            bullet_diameter_inches=0.308,
            weight_grains=178.0,
        ),
        Bullet(
            manufacturer_id=hornady.id, name="30 Cal .308 165 gr CX®", bullet_diameter_inches=0.308, weight_grains=165.0
        ),
        Bullet(
            manufacturer_id=hornady.id,
            name="30 Cal .308 150 gr SST®",
            bullet_diameter_inches=0.308,
            weight_grains=150.0,
        ),
        Bullet(
            manufacturer_id=hornady.id,
            name="30 Cal .308 160 gr FTX® (30-30 Win)",
            bullet_diameter_inches=0.308,
            weight_grains=160.0,
        ),
        Bullet(
            manufacturer_id=hornady.id,
            name="6.5mm .264 143 gr ELD-X®",
            bullet_diameter_inches=0.264,
            weight_grains=143.0,
        ),
        Bullet(
            manufacturer_id=hornady.id, name="6.5mm .264 120 gr CX®", bullet_diameter_inches=0.264, weight_grains=120.0
        ),
        Bullet(
            manufacturer_id=hornady.id,
            name="30 Cal .308 178 gr ELD® Match",
            bullet_diameter_inches=0.308,
            weight_grains=178.0,
        ),
        Bullet(
            manufacturer_id=hornady.id,
            name="30 Cal .308 220 gr InterLock® RN",
            bullet_diameter_inches=0.308,
            weight_grains=220.0,
        ),
        # Sierra — ALL CAPS names
        Bullet(
            manufacturer_id=sierra.id,
            name="30 CAL 175 GR HPBT MATCHKING (SMK)",
            bullet_diameter_inches=0.308,
            weight_grains=175.0,
        ),
        # Nosler — "(50ct)" suffix pattern
        Bullet(
            manufacturer_id=nosler.id,
            name="30 Caliber 200gr Partition (50ct)",
            bullet_diameter_inches=0.308,
            weight_grains=200.0,
        ),
        Bullet(
            manufacturer_id=nosler.id,
            name="270 Caliber 150gr Ballistic Tip Hunting (50ct)",
            bullet_diameter_inches=0.277,
            weight_grains=150.0,
        ),
        # Federal — comma-separated product names
        Bullet(
            manufacturer_id=federal.id,
            name="Fusion Component Bullet, .308, 180 Grain",
            bullet_diameter_inches=0.308,
            weight_grains=180.0,
        ),
        # Berger — long descriptive names
        Bullet(
            manufacturer_id=berger.id,
            name="30 Caliber 220 Grain Long Range Hybrid Target Rifle Bullet",
            bullet_diameter_inches=0.308,
            weight_grains=220.0,
        ),
    ]
    db.add_all(bullets)
    db.commit()

    return {
        "hornady": hornady,
        "federal": federal,
        "nosler": nosler,
        "sierra": sierra,
        "berger": berger,
        "cal_308": cal_308,
        "cal_65": cal_65,
        "cal_270": cal_270,
        "bullets": {b.name: b for b in bullets},
    }


class TestAsymmetricBulletMatching:
    """Tests for matching short cartridge-extracted bullet names to long DB product names."""

    def test_eldx_matches_with_weight(self, cartridge_bullets, db):
        """'ELD-X' + weight=178 should match '30 Cal .308 178 gr ELD-X®'."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "ELD-X"}, "weight_grains": {"value": 178.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == cartridge_bullets["bullets"]["30 Cal .308 178 gr ELD-X®"].id

    def test_cx_matches_with_weight(self, cartridge_bullets, db):
        """'CX®' + weight=165 should match '30 Cal .308 165 gr CX®'."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "CX®"}, "weight_grains": {"value": 165.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == cartridge_bullets["bullets"]["30 Cal .308 165 gr CX®"].id

    def test_sst_matches_with_weight(self, cartridge_bullets, db):
        """'SST (Super Shock Tip)' + weight=150 should match '30 Cal .308 150 gr SST®'."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "SST (Super Shock Tip)"}, "weight_grains": {"value": 150.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == cartridge_bullets["bullets"]["30 Cal .308 150 gr SST®"].id

    def test_eld_match_with_weight(self, cartridge_bullets, db):
        """'ELD® Match' + weight=178 should match '30 Cal .308 178 gr ELD® Match'."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "ELD® Match"}, "weight_grains": {"value": 178.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == cartridge_bullets["bullets"]["30 Cal .308 178 gr ELD® Match"].id

    def test_interlock_matches_with_weight(self, cartridge_bullets, db):
        """'InterLock®' + weight=220 should match '30 Cal .308 220 gr InterLock® RN'."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "InterLock®"}, "weight_grains": {"value": 220.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == cartridge_bullets["bullets"]["30 Cal .308 220 gr InterLock® RN"].id

    def test_matchking_short_name_matches(self, cartridge_bullets, db):
        """'MatchKing' (short form) + weight should match Sierra MatchKing."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "MatchKing"}, "weight_grains": {"value": 175.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == cartridge_bullets["bullets"]["30 CAL 175 GR HPBT MATCHKING (SMK)"].id

    def test_matchking_verbose_name_matches_via_abbreviation(self, cartridge_bullets, db):
        """Verbose expanded name now matches abbreviated DB name via abbreviation expansion.

        'Sierra Matchking Boat-Tail Hollow Point' has HPBT/BTHP/SMK abbreviations
        auto-expanded, matching 'HPBT MATCHKING (SMK)' with high confidence.
        """
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "Sierra Matchking Boat-Tail Hollow Point"}, "weight_grains": {"value": 175.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched
        assert result.entity_id == cartridge_bullets["bullets"]["30 CAL 175 GR HPBT MATCHKING (SMK)"].id

    def test_partition_matches_with_weight(self, cartridge_bullets, db):
        """'Nosler Partition' + weight=200 should match Nosler Partition."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "Nosler Partition"}, "weight_grains": {"value": 200.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == cartridge_bullets["bullets"]["30 Caliber 200gr Partition (50ct)"].id

    def test_berger_hybrid_matches_with_weight(self, cartridge_bullets, db):
        """'Berger Hybrid' + weight=220 should match Berger Hybrid Target."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "Berger Hybrid"}, "weight_grains": {"value": 220.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert (
            result.entity_id
            == cartridge_bullets["bullets"]["30 Caliber 220 Grain Long Range Hybrid Target Rifle Bullet"].id
        )

    def test_diameter_still_prevents_cross_caliber(self, cartridge_bullets, db):
        """Even with containment matching, diameter must still constrain results."""
        resolver = EntityResolver(db)
        # ELD-X at .264 should NOT match the .308 ELD-X
        result = resolver.match_bullet(
            {"name": {"value": "ELD-X"}, "weight_grains": {"value": 143.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.264,
        )
        if result.matched:
            assert result.entity_id == cartridge_bullets["bullets"]["6.5mm .264 143 gr ELD-X®"].id

    def test_weight_disambiguates_same_type(self, cartridge_bullets, db):
        """When multiple bullets of the same type exist, weight should pick the right one."""
        resolver = EntityResolver(db)
        # CX at .264 with weight=120 should match 6.5mm CX, not .308 CX
        result = resolver.match_bullet(
            {"name": {"value": "CX®"}, "weight_grains": {"value": 120.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.264,
        )
        assert result.matched is True
        assert result.entity_id == cartridge_bullets["bullets"]["6.5mm .264 120 gr CX®"].id

    def test_no_match_for_genuinely_missing_bullet(self, cartridge_bullets, db):
        """A bullet type not in DB should not match."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "Trophy Copper"}, "weight_grains": {"value": 130.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.277,
        )
        assert result.matched is False


# ---------------------------------------------------------------------------
# BC/weight confidence boost for cartridge → bullet matching
# ---------------------------------------------------------------------------


class TestBCWeightConfidenceBoost:
    """Tests for _bc_weight_confidence_boost when matching cartridge BC/weight to bullet."""

    def test_exact_weight_match_boosts(self, seeded, db):
        """Exact weight agreement (±0.5 gr) should boost confidence."""
        b1 = seeded["b1"]  # weight=140.0, bc_g7_published=0.326
        extracted = {"bullet_weight_grains": {"value": 140.0}}
        boost, warnings = _bc_weight_confidence_boost(extracted, b1.id, db)
        assert boost == 0.05
        assert warnings == []

    def test_exact_bc_g7_match_boosts(self, seeded, db):
        """Exact BC G7 match should boost confidence by 0.05."""
        b1 = seeded["b1"]  # bc_g7_published=0.326
        extracted = {"bc_g7": {"value": 0.326}}
        boost, warnings = _bc_weight_confidence_boost(extracted, b1.id, db)
        assert boost == 0.05
        assert warnings == []

    def test_bc_g7_disagreement_warns(self, seeded, db):
        """BC G7 mismatch should produce a warning but no boost."""
        b1 = seeded["b1"]  # bc_g7_published=0.326
        extracted = {"bc_g7": {"value": 0.310}}
        boost, warnings = _bc_weight_confidence_boost(extracted, b1.id, db)
        assert boost == 0.0
        assert len(warnings) == 1
        assert "bc_g7 mismatch" in warnings[0]

    def test_all_signals_match_cumulative_boost(self, seeded, db):
        """Weight + BC G7 agreement should stack boosts."""
        b1 = seeded["b1"]  # weight=140.0, bc_g7_published=0.326
        extracted = {
            "bullet_weight_grains": {"value": 140.0},
            "bc_g7": {"value": 0.326},
        }
        boost, warnings = _bc_weight_confidence_boost(extracted, b1.id, db)
        assert boost == 0.10  # 0.05 (weight) + 0.05 (g7)
        assert warnings == []

    def test_no_bc_on_bullet_no_boost(self, seeded, db):
        """If bullet has no published BC, no boost or warning for BC fields."""
        b1 = seeded["b1"]
        # b1 has bc_g7_published=0.326 but no bc_g1_published
        extracted = {"bc_g1": {"value": 0.500}}
        boost, warnings = _bc_weight_confidence_boost(extracted, b1.id, db)
        assert boost == 0.0
        assert warnings == []

    def test_missing_bullet_returns_zero(self, db):
        """Non-existent bullet_id should return zero boost."""
        extracted = {"bullet_weight_grains": {"value": 140.0}}
        boost, warnings = _bc_weight_confidence_boost(extracted, "nonexistent-id", db)
        assert boost == 0.0
        assert warnings == []


class TestResolveCartridgeBCBoost:
    """Integration: resolve('cartridge') applies BC/weight boost to bullet match confidence."""

    def test_resolve_cartridge_bc_match_boosts_bullet_confidence(self, seeded, db):
        """When cartridge BC matches bullet BC, bullet match confidence gets boosted."""
        resolver = EntityResolver(db)
        extracted = {
            "name": {"value": "Hornady 6.5 CM 140gr ELD Match"},
            "manufacturer": {"value": "Hornady"},
            "caliber": {"value": "6.5 Creedmoor"},
            "bullet_name": {"value": "140 ELD Match"},
            "bullet_weight_grains": {"value": 140.0},
            "bc_g7": {"value": 0.326},
            "sku": {"value": "81500"},
        }
        result = resolver.resolve(extracted, "cartridge")
        assert result.bullet_id == seeded["b1"].id
        # Should have no BC warnings since G7 matches within tolerance
        assert not any("bc_g7 mismatch" in w for w in result.warnings)
        # Boosted confidence should be persisted on result (weight + G7 = +0.10)
        assert result.bullet_match_confidence is not None
        assert result.bullet_match_confidence > 0.5

    def test_resolve_cartridge_bc_mismatch_adds_warning(self, seeded, db):
        """When cartridge BC disagrees with bullet BC, a warning is added."""
        resolver = EntityResolver(db)
        extracted = {
            "name": {"value": "Hornady 6.5 CM 140gr ELD Match"},
            "manufacturer": {"value": "Hornady"},
            "caliber": {"value": "6.5 Creedmoor"},
            "bullet_name": {"value": "140 ELD Match"},
            "bullet_weight_grains": {"value": 140.0},
            "bc_g7": {"value": 0.999},  # Clearly wrong
            "sku": {"value": "81500"},
        }
        result = resolver.resolve(extracted, "cartridge")
        assert result.bullet_id == seeded["b1"].id
        assert any("bc_g7 mismatch" in w for w in result.warnings)

    def test_ftx_matches_with_weight(self, cartridge_bullets, db):
        """'FTX®' + weight=160 should match '30 Cal .308 160 gr FTX® (30-30 Win)'."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "FTX®"}, "weight_grains": {"value": 160.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == cartridge_bullets["bullets"]["30 Cal .308 160 gr FTX® (30-30 Win)"].id

    def test_cross_manufacturer_bullet_match(self, cartridge_bullets, db):
        """Cartridge from Federal should match a Nosler bullet (cross-manufacturer)."""
        resolver = EntityResolver(db)
        # Federal loads Nosler Ballistic Tips — manufacturer_id=None for cross-mfr search
        result = resolver.match_bullet(
            {"name": {"value": "Nosler Ballistic Tip"}, "weight_grains": {"value": 150.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.277,
        )
        assert result.matched is True
        assert result.entity_id == cartridge_bullets["bullets"]["270 Caliber 150gr Ballistic Tip Hunting (50ct)"].id

    def test_eldx_does_not_match_eld_match_at_same_weight(self, cartridge_bullets, db):
        """ELD-X should NOT fuzzy-match ELD Match when both exist at .308 178gr.

        Both share 'eld' keyword but 'x' vs 'match' should differentiate them.
        With the 0.55 Tier 2 threshold, 'ELD-X' scores 1.0 against ELD-X® but
        only 0.5 against ELD® Match (below threshold).
        """
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "ELD-X"}, "weight_grains": {"value": 178.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        # Should match the actual ELD-X, not the ELD Match
        assert result.entity_id == cartridge_bullets["bullets"]["30 Cal .308 178 gr ELD-X®"].id

    def test_eld_match_does_not_match_eldx_at_same_weight(self, cartridge_bullets, db):
        """ELD Match should NOT fuzzy-match ELD-X when both exist at .308 178gr."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "ELD Match"}, "weight_grains": {"value": 178.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == cartridge_bullets["bullets"]["30 Cal .308 178 gr ELD® Match"].id


class TestAbbreviationExpansion:
    """Tests for _expand_abbreviations and its integration with _bullet_name_score."""

    def test_hpbt_expands_to_hollow_point_boat_tail(self):
        assert {"hollow", "point", "boat", "tail"} <= _expand_abbreviations({"hpbt"})

    def test_reverse_expansion_adds_abbreviation(self):
        """If all expansion words present, abbreviation is added."""
        expanded = _expand_abbreviations({"hollow", "point", "boat", "tail"})
        assert "hpbt" in expanded
        assert "bthp" in expanded  # same expansion
        assert "hp" in expanded
        assert "bt" in expanded

    def test_smk_expands_to_sierra_matchking(self):
        expanded = _expand_abbreviations({"smk"})
        assert "sierra" in expanded
        assert "matchking" in expanded

    def test_fmj_expands_to_full_metal_jacket(self):
        expanded = _expand_abbreviations({"fmj"})
        assert {"full", "metal", "jacket"} <= expanded

    def test_no_expansion_for_unknown(self):
        """Words without known abbreviations pass through unchanged."""
        expanded = _expand_abbreviations({"eld", "match"})
        assert expanded == {"eld", "match"}

    def test_hpbt_matchking_vs_verbose_name(self):
        """The key case: 'HPBT MatchKing (SMK)' should match 'Sierra Matchking Boat-Tail Hollow Point'."""
        score = _bullet_name_score("Sierra Matchking Boat-Tail Hollow Point", "30 CAL 175 GR HPBT MATCHKING (SMK)")
        assert score > 0.8

    def test_hpbt_vs_hollow_point_boat_tail(self):
        """'Hollow Point Boat Tail' should match 'HPBT' via expansion."""
        score = _bullet_name_score("Hollow Point Boat Tail", "6.5mm 140 gr HPBT Custom Competition")
        assert score > 0.3

    def test_abbreviation_doesnt_cause_false_positives(self):
        """Abbreviation expansion shouldn't make unrelated bullets match."""
        # "Sierra Matchking Boat-Tail Hollow Point" should NOT match a Cutting Edge bullet
        score = _bullet_name_score(
            "Sierra Matchking Boat-Tail Hollow Point",
            ".264/6.5 140gr SINGLE FEED-Tipped Hollow Point - 50ct",
        )
        assert score < 0.35  # some overlap (hollow, point) but much less than correct match

    def test_otm_expands_to_open_tip_match(self):
        """OTM abbreviation should match 'Open Tip Match'."""
        score = _bullet_name_score("Open Tip Match", "6.5mm 140gr OTM Tactical")
        assert score > 0.3


class TestBulletFKConfidenceThreshold:
    """Tests for the bullet FK confidence threshold in cartridge resolution."""

    @pytest.fixture()
    def setup_db(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = Session(engine)

        mfr = Manufacturer(name="Hornady")
        session.add(mfr)
        session.flush()

        cal = Caliber(name=".308 Winchester", alt_names=[".308 Win"], bullet_diameter_inches=0.308)
        session.add(cal)
        session.flush()

        # Only a 165gr SST — no 150gr SST in DB
        bullet = Bullet(
            manufacturer_id=mfr.id,
            name="30 Cal .308 165 gr SST®",
            bullet_diameter_inches=0.308,
            weight_grains=165.0,
        )
        session.add(bullet)
        session.flush()

        yield {"session": session, "mfr": mfr, "cal": cal, "bullet": bullet}
        session.close()

    def test_weight_mismatch_bullet_not_assigned(self, setup_db):
        """A weight-mismatched fuzzy bullet match (low confidence) should NOT be assigned."""
        resolver = EntityResolver(setup_db["session"])
        # Cartridge has weight=150 but DB only has 165gr SST → fuzzy match with weight_agrees=False
        result = resolver.resolve(
            {
                "manufacturer": {"value": "Hornady"},
                "name": {"value": "308 Win 150 gr SST®"},
                "caliber": {"value": ".308 Winchester"},
                "bullet_name": {"value": "SST"},
                "bullet_weight_grains": {"value": 150.0},
                "muzzle_velocity_fps": {"value": 2820},
            },
            "cartridge",
        )
        # bullet_id should be None — the only SST is 165gr, confidence should be below threshold
        assert result.bullet_id is None
        assert any("bullet" in ref.lower() for ref in result.unresolved_refs)

    def test_weight_match_bullet_assigned(self, setup_db):
        """A weight-matched bullet should be assigned normally."""
        resolver = EntityResolver(setup_db["session"])
        result = resolver.resolve(
            {
                "manufacturer": {"value": "Hornady"},
                "name": {"value": "308 Win 165 gr SST®"},
                "caliber": {"value": ".308 Winchester"},
                "bullet_name": {"value": "SST"},
                "bullet_weight_grains": {"value": 165.0},
                "muzzle_velocity_fps": {"value": 2700},
            },
            "cartridge",
        )
        assert result.bullet_id == setup_db["bullet"].id


# ---------------------------------------------------------------------------
# Caliber rejection — pipeline_store helpers
# ---------------------------------------------------------------------------


class TestCalibreRejection:
    """Tests for _has_rejected_caliber and _load_rejected_calibers from pipeline_store."""

    def test_rejects_matching_caliber(self):
        """An unresolved caliber in the rejection set should be detected."""
        result = ResolutionResult(entity_type="cartridge")
        result.unresolved_refs = ["caliber: 9mm Luger"]
        assert _has_rejected_caliber(result, {"9mm luger"}) is True

    def test_allows_non_rejected_caliber(self):
        """An unresolved caliber NOT in the rejection set should pass."""
        result = ResolutionResult(entity_type="cartridge")
        result.unresolved_refs = ["caliber: 338 ARC"]
        assert _has_rejected_caliber(result, {"9mm luger", "12 ga"}) is False

    def test_ignores_non_caliber_refs(self):
        """Non-caliber unresolved refs should not trigger rejection."""
        result = ResolutionResult(entity_type="cartridge")
        result.unresolved_refs = ["bullet: ELD-X", "manufacturer: Unknown"]
        assert _has_rejected_caliber(result, {"9mm luger"}) is False

    def test_empty_rejection_set(self):
        """Empty rejection set should never reject."""
        result = ResolutionResult(entity_type="cartridge")
        result.unresolved_refs = ["caliber: 9mm Luger"]
        assert _has_rejected_caliber(result, set()) is False

    def test_no_unresolved_refs(self):
        """Entity with no unresolved refs should not be rejected."""
        result = ResolutionResult(entity_type="cartridge")
        result.unresolved_refs = []
        assert _has_rejected_caliber(result, {"9mm luger"}) is False

    def test_case_insensitive(self):
        """Rejection matching should be case-insensitive."""
        result = ResolutionResult(entity_type="cartridge")
        result.unresolved_refs = ["caliber: 9MM Luger +P"]
        assert _has_rejected_caliber(result, {"9mm luger +p"}) is True

    def test_multiple_unresolved_one_rejected(self):
        """If any caliber ref matches rejection set, entity is rejected."""
        result = ResolutionResult(entity_type="cartridge")
        result.unresolved_refs = ["bullet: ELD-X", "caliber: 40 S&W"]
        assert _has_rejected_caliber(result, {"40 s&w"}) is True

    def test_load_rejected_calibers_from_file(self, tmp_path):
        """Loading from a valid JSON file returns lowercased caliber set."""
        import json
        from unittest.mock import patch

        test_file = tmp_path / "rejected_calibers.json"
        test_file.write_text(json.dumps({"calibers": ["9mm Luger", "12 GA"]}))

        with patch.object(_store_mod, "REJECTED_CALIBERS_PATH", test_file):
            result = _load_rejected_calibers()
        assert result == {"9mm luger", "12 ga"}

    def test_load_rejected_calibers_missing_file(self, tmp_path):
        """Missing file returns empty set (no rejections)."""
        from unittest.mock import patch

        with patch.object(_store_mod, "REJECTED_CALIBERS_PATH", tmp_path / "nonexistent.json"):
            result = _load_rejected_calibers()
        assert result == set()
