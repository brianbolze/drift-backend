# flake8: noqa: E501
"""Tests for the EntityResolver — bullet/cartridge/rifle resolution paths."""

# Import store-level rejection helper (script, but importable)
import importlib
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from drift.models import Base, Bullet, BulletProductLine, Caliber, Cartridge, EntityAlias, Manufacturer
from drift.pipeline.resolution.resolver import (
    AlternativeMatch,
    EntityResolver,
    MatchResult,
    ResolutionResult,
    _bc_weight_confidence_boost,
    _bullet_name_score,
    _expand_abbreviations,
    _name_similarity,
    _normalize,
    _normalize_caliber,
    _normalize_product_line,
    _pick_best_with_alternatives,
    _strip_trademarks,
)

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
_store_mod = importlib.import_module("pipeline_store")
_has_rejected_caliber = _store_mod._has_rejected_caliber
_load_rejected_calibers = _store_mod._load_rejected_calibers


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
        # bullet_id should be None — the only SST is 165gr, weight gate rejects 15gr diff
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

    def test_weight_gate_rejects_large_diff(self, setup_db):
        """Weight gate rejects bullet match when weight diff exceeds threshold (>5gr)."""
        session = setup_db["session"]
        # Add a product-line bullet that would otherwise match at high confidence (0.80+)
        bullet_cx = Bullet(
            manufacturer_id=setup_db["mfr"].id,
            name="30 Cal .308 150 gr CX®",
            bullet_diameter_inches=0.308,
            weight_grains=150.0,
            product_line="CX",
        )
        session.add(bullet_cx)
        session.flush()

        resolver = EntityResolver(session)
        # Cartridge wants 110gr CX but DB only has 150gr CX — 40gr diff, must be rejected
        result = resolver.resolve(
            {
                "manufacturer": {"value": "Hornady"},
                "name": {"value": "300 Blackout 110 gr CX® Custom™"},
                "caliber": {"value": ".308 Winchester"},
                "bullet_name": {"value": "CX"},
                "bullet_weight_grains": {"value": 110.0},
                "muzzle_velocity_fps": {"value": 2280},
            },
            "cartridge",
        )
        assert result.bullet_id is None
        assert any("weight mismatch" in ref for ref in result.unresolved_refs)

    def test_weight_gate_allows_small_diff(self, setup_db):
        """Weight gate allows bullet match when weight diff is within threshold (<=5gr)."""
        session = setup_db["session"]
        bullet = Bullet(
            manufacturer_id=setup_db["mfr"].id,
            name="30 Cal .308 168 gr BTHP Match",
            bullet_diameter_inches=0.308,
            weight_grains=168.0,
            product_line="BTHP Match",
        )
        session.add(bullet)
        session.flush()

        resolver = EntityResolver(session)
        # Cartridge weight 168.5gr vs bullet 168gr — 0.5gr diff, well within gate
        result = resolver.resolve(
            {
                "manufacturer": {"value": "Hornady"},
                "name": {"value": "308 Win 168 gr BTHP Match"},
                "caliber": {"value": ".308 Winchester"},
                "bullet_name": {"value": "BTHP Match"},
                "bullet_weight_grains": {"value": 168.5},
                "muzzle_velocity_fps": {"value": 2700},
            },
            "cartridge",
        )
        assert result.bullet_id == bullet.id


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


# ---------------------------------------------------------------------------
# Multi-candidate tracking: alternatives, methods_tried, is_ambiguous
# ---------------------------------------------------------------------------


class TestMatchCartridgeTier2BestNotFirst:
    """Tier 2 should pick the best-scored candidate, not the first weight match."""

    def test_picks_best_not_first(self, db):
        """Two cartridges with same weight — higher name score should win."""
        mfr = Manufacturer(name="TestMfr", country="US")
        db.add(mfr)
        db.flush()
        cal = Caliber(name=".308 Win", bullet_diameter_inches=0.308)
        db.add(cal)
        db.flush()
        bullet = Bullet(manufacturer_id=mfr.id, name="180gr Test", bullet_diameter_inches=0.308, weight_grains=180.0)
        db.add(bullet)
        db.flush()
        # Low name score cartridge (inserted first)
        c_low = Cartridge(
            manufacturer_id=mfr.id,
            caliber_id=cal.id,
            bullet_id=bullet.id,
            name="Generic 180gr Load",
            bullet_weight_grains=180.0,
            muzzle_velocity_fps=2600,
        )
        # High name score cartridge (inserted second)
        c_high = Cartridge(
            manufacturer_id=mfr.id,
            caliber_id=cal.id,
            bullet_id=bullet.id,
            name="Premium 180gr AccuBond",
            bullet_weight_grains=180.0,
            muzzle_velocity_fps=2600,
        )
        db.add_all([c_low, c_high])
        db.commit()

        resolver = EntityResolver(db)
        result = resolver.match_cartridge(
            {"name": {"value": "AccuBond"}, "bullet_weight_grains": {"value": 180.0}},
            manufacturer_id=mfr.id,
            caliber_id=cal.id,
        )
        assert result.matched is True
        assert result.entity_id == c_high.id


class TestMatchCartridgeTier2ContainmentScoring:
    """Tier 2 should use containment scoring for asymmetric names."""

    def test_short_name_matches_via_containment(self, db):
        """'ELD-X' should match '6.5 CM 143gr ELD-X®' via containment, not Jaccard."""
        mfr = Manufacturer(name="Hornady", country="US")
        db.add(mfr)
        db.flush()
        cal = Caliber(name="6.5 Creedmoor", bullet_diameter_inches=0.264)
        db.add(cal)
        db.flush()
        bullet = Bullet(manufacturer_id=mfr.id, name="143 ELD-X", bullet_diameter_inches=0.264, weight_grains=143.0)
        db.add(bullet)
        db.flush()
        cart = Cartridge(
            manufacturer_id=mfr.id,
            caliber_id=cal.id,
            bullet_id=bullet.id,
            name="6.5 Creedmoor 143gr ELD-X®",
            bullet_weight_grains=143.0,
            muzzle_velocity_fps=2700,
        )
        db.add(cart)
        db.commit()

        resolver = EntityResolver(db)
        result = resolver.match_cartridge(
            {"name": {"value": "ELD-X"}, "bullet_weight_grains": {"value": 143.0}},
            manufacturer_id=mfr.id,
            caliber_id=cal.id,
        )
        assert result.matched is True
        assert result.entity_id == cart.id
        assert result.method == "composite_key"


class TestMatchCartridgeTier2Threshold055:
    """Tier 2 threshold should be 0.55 — names scoring 0.3-0.55 should NOT match."""

    def test_low_name_score_rejected(self, db):
        """A name with low similarity (0.3-0.55) should not match at Tier 2."""
        mfr = Manufacturer(name="TestMfr", country="US")
        db.add(mfr)
        db.flush()
        cal = Caliber(name=".308 Win", bullet_diameter_inches=0.308)
        db.add(cal)
        db.flush()
        bullet = Bullet(manufacturer_id=mfr.id, name="150gr Test", bullet_diameter_inches=0.308, weight_grains=150.0)
        db.add(bullet)
        db.flush()
        cart = Cartridge(
            manufacturer_id=mfr.id,
            caliber_id=cal.id,
            bullet_id=bullet.id,
            name="Very Different Product Name XYZ",
            bullet_weight_grains=150.0,
            muzzle_velocity_fps=2800,
        )
        db.add(cart)
        db.commit()

        resolver = EntityResolver(db)
        result = resolver.match_cartridge(
            {"name": {"value": "Totally Unrelated ABC"}, "bullet_weight_grains": {"value": 150.0}},
            manufacturer_id=mfr.id,
            caliber_id=cal.id,
        )
        # Even though weight matches, name score should be too low for Tier 2
        if result.matched:
            assert result.confidence < 0.85  # If it matched, it should be via fuzzy (lower confidence)


class TestAlternativesPopulated:
    """After matching, alternatives list should contain runner-up candidates."""

    def test_bullet_alternatives_populated(self, db):
        """With multiple scored bullets, alternatives should be non-empty."""
        mfr = Manufacturer(name="TestMfr", country="US")
        db.add(mfr)
        db.flush()
        # Two bullets with same weight, both matching "Match" in name
        b1 = Bullet(manufacturer_id=mfr.id, name="308 Match Target", bullet_diameter_inches=0.308, weight_grains=175.0)
        b2 = Bullet(
            manufacturer_id=mfr.id, name="308 Match Competition", bullet_diameter_inches=0.308, weight_grains=175.0
        )
        db.add_all([b1, b2])
        db.commit()

        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "Match"}, "weight_grains": {"value": 175.0}},
            manufacturer_id=mfr.id,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        # Both should score — one is best, one is alternative
        assert len(result.alternatives) > 0
        assert all(isinstance(a, AlternativeMatch) for a in result.alternatives)


class TestMatchResultIsAmbiguous:
    """is_ambiguous should be True when gap to next-best is < 0.2."""

    def test_close_scores_are_ambiguous(self):
        """Two candidates with close scores should be flagged as ambiguous."""
        result = MatchResult(
            matched=True,
            entity_id="a",
            confidence=0.85,
            method="composite_key",
            alternatives=[AlternativeMatch(entity_id="b", confidence=0.80, method="composite_key")],
        )
        assert result.is_ambiguous is True

    def test_distant_scores_not_ambiguous(self):
        """Two candidates with distant scores should NOT be ambiguous."""
        result = MatchResult(
            matched=True,
            entity_id="a",
            confidence=0.95,
            method="composite_key",
            alternatives=[AlternativeMatch(entity_id="b", confidence=0.60, method="fuzzy_name")],
        )
        assert result.is_ambiguous is False

    def test_high_confidence_not_ambiguous(self):
        """Very high confidence (>= 0.97) is never ambiguous regardless of gap."""
        result = MatchResult(
            matched=True,
            entity_id="a",
            confidence=0.98,
            method="exact_sku",
            alternatives=[AlternativeMatch(entity_id="b", confidence=0.96, method="composite_key")],
        )
        assert result.is_ambiguous is False

    def test_no_alternatives_not_ambiguous(self):
        """No alternatives means not ambiguous."""
        result = MatchResult(matched=True, entity_id="a", confidence=0.85, method="composite_key")
        assert result.is_ambiguous is False


class TestMethodsTried:
    """methods_tried should be populated after resolve()."""

    def test_bullet_methods_tried(self, seeded, db):
        """resolve('bullet') should populate methods_tried on the result."""
        resolver = EntityResolver(db)
        result = resolver.resolve(
            {
                "name": {"value": "140 ELD Match"},
                "manufacturer": {"value": "Hornady"},
                "bullet_diameter_inches": {"value": 0.264},
                "weight_grains": {"value": 140.0},
                "sku": {"value": "26331"},
            },
            "bullet",
        )
        assert len(result.methods_tried) > 0
        assert "exact_sku" in result.methods_tried

    def test_cartridge_methods_tried(self, seeded, db):
        """resolve('cartridge') without SKU should have composite_key and/or fuzzy_name."""
        resolver = EntityResolver(db)
        result = resolver.resolve(
            {
                "name": {"value": "Hornady 6.5 CM 140gr ELD Match"},
                "manufacturer": {"value": "Hornady"},
                "caliber": {"value": "6.5 Creedmoor"},
                "bullet_name": {"value": "140 ELD Match"},
                "bullet_weight_grains": {"value": 140.0},
            },
            "cartridge",
        )
        assert len(result.methods_tried) > 0


class TestPickBestWithAlternatives:
    """Unit tests for _pick_best_with_alternatives helper."""

    def test_empty_returns_no_match(self):
        result = _pick_best_with_alternatives([], ["composite_key"], "no match")
        assert result.matched is False
        assert result.methods_tried == ["composite_key"]

    def test_single_candidate(self):
        result = _pick_best_with_alternatives(
            [("id-1", 0.9, "composite_key", "details")], ["composite_key"], "no match"
        )
        assert result.matched is True
        assert result.entity_id == "id-1"
        assert result.confidence == 0.9
        assert result.alternatives == []

    def test_deduplicates_by_entity_id(self):
        """Same entity_id appearing twice — keep highest confidence."""
        result = _pick_best_with_alternatives(
            [("id-1", 0.7, "fuzzy_name", "low"), ("id-1", 0.9, "composite_key", "high")],
            ["composite_key", "fuzzy_name"],
            "no match",
        )
        assert result.entity_id == "id-1"
        assert result.confidence == 0.9
        assert result.alternatives == []

    def test_alternatives_capped_at_3(self):
        """Only top 3 runner-ups should be in alternatives."""
        scored = [(f"id-{i}", 0.9 - i * 0.05, "test", f"details-{i}") for i in range(6)]
        result = _pick_best_with_alternatives(scored, ["test"], "no match")
        assert result.entity_id == "id-0"
        assert len(result.alternatives) == 3
        assert result.alternatives[0].entity_id == "id-1"
        assert result.alternatives[2].entity_id == "id-3"


# ---------------------------------------------------------------------------
# Trademark stripping
# ---------------------------------------------------------------------------


class TestStripTrademarks:
    """_strip_trademarks removes ®, ™, © symbols."""

    def test_strips_registered(self):
        assert _strip_trademarks("ELD-X®") == "ELD-X"

    def test_strips_trademark(self):
        assert _strip_trademarks("SST™") == "SST"

    def test_strips_copyright(self):
        assert _strip_trademarks("©Hornady") == "Hornady"

    def test_strips_all_three(self):
        assert _strip_trademarks("©ELD-X® SST™") == "ELD-X SST"

    def test_no_symbols_unchanged(self):
        assert _strip_trademarks("MatchKing") == "MatchKing"


class TestNormalizeStripsTrademarks:
    """_normalize should strip ® ™ © before further processing."""

    def test_normalize_strips_registered(self):
        assert "eld" in _normalize("ELD-X®")

    def test_normalize_cx_registered(self):
        # CX® should normalize without the registered symbol
        result = _normalize("CX®")
        assert "cx" in result


# ---------------------------------------------------------------------------
# _normalize_product_line
# ---------------------------------------------------------------------------


class TestNormalizeProductLine:
    """Tests for _normalize_product_line — preserves hyphens, strips prefixes."""

    def test_basic_product_line(self):
        assert _normalize_product_line("ELD-X") == "eld-x"

    def test_strips_trademark(self):
        assert _normalize_product_line("ELD-X®") == "eld-x"

    def test_strips_manufacturer_prefix(self):
        assert _normalize_product_line("Hornady ELD-X") == "eld-x"

    def test_strips_barnes_prefix(self):
        assert _normalize_product_line("Barnes TSX") == "tsx"

    def test_strips_sierra_prefix(self):
        assert _normalize_product_line("Sierra MatchKing") == "matchking"

    def test_extracts_parenthetical_abbreviation(self):
        """Should prefer the shorter parenthetical abbreviation."""
        assert _normalize_product_line("Barnes Triple-Shock X Bullet (TSX)") == "tsx"

    def test_keeps_parenthetical_when_longer(self):
        """When parenthetical is longer than the main text, keep the main text."""
        result = _normalize_product_line("TSX (Triple-Shock X Bullet)")
        assert result == "tsx"

    def test_unicode_dash_normalized(self):
        """Unicode dashes (U+2013 en-dash, etc.) should become ASCII hyphens."""
        assert _normalize_product_line("ELD\u2013X") == "eld-x"

    def test_lowercase(self):
        assert _normalize_product_line("MatchKing") == "matchking"

    def test_fusion_soft_point_strips_suffix(self):
        """'Fusion Soft Point' → 'fusion' after stripping generic suffix."""
        assert _normalize_product_line("Fusion Soft Point") == "fusion"

    def test_sst_super_shock_tip(self):
        """'SST (Super Shock Tip)' → 'sst' (parenthetical is shorter)."""
        assert _normalize_product_line("SST (Super Shock Tip)") == "sst"

    def test_nosler_partition(self):
        assert _normalize_product_line("Nosler Partition") == "partition"

    def test_hybrid_target(self):
        assert _normalize_product_line("Hybrid Target") == "hybrid target"

    def test_numeric_parenthetical_ignored(self):
        """Numeric parenthetical like '(50ct)' should not be preferred."""
        result = _normalize_product_line("Partition (50ct)")
        assert result == "partition"

    def test_empty_string(self):
        assert _normalize_product_line("") == ""

    def test_generic_bullet_suffix_stripped(self):
        """'Component Bullet' suffix should be stripped."""
        assert _normalize_product_line("Fusion Component Bullet") == "fusion"


# ---------------------------------------------------------------------------
# Product-line matching in match_bullet
# ---------------------------------------------------------------------------


class TestProductLineMatching:
    """Tests for product_line-based bullet matching."""

    @pytest.fixture()
    def product_line_db(self, db):
        """Seed bullets with product_line populated."""
        mfr_hornady = Manufacturer(name="Hornady", country="US")
        mfr_sierra = Manufacturer(name="Sierra", country="US")
        mfr_nosler = Manufacturer(name="Nosler", country="US")
        db.add_all([mfr_hornady, mfr_sierra, mfr_nosler])
        db.flush()

        cal = Caliber(name=".308 Winchester", bullet_diameter_inches=0.308)
        db.add(cal)
        db.flush()

        bullets = {}
        bullet_data = [
            ("178 gr ELD-X", mfr_hornady, 0.308, 178.0, "ELD-X"),
            ("178 gr ELD Match", mfr_hornady, 0.308, 178.0, "ELD Match"),
            ("150 gr SST", mfr_hornady, 0.308, 150.0, "SST"),
            ("165 gr SST", mfr_hornady, 0.308, 165.0, "SST"),
            ("175 gr MatchKing HPBT", mfr_sierra, 0.308, 175.0, "MatchKing"),
            ("200 gr Partition", mfr_nosler, 0.308, 200.0, "Partition"),
            ("165 gr SP Boattail", mfr_hornady, 0.308, 165.0, None),  # generic, no product_line
        ]
        for name, mfr, dia, wt, pl in bullet_data:
            b = Bullet(
                manufacturer_id=mfr.id,
                name=name,
                bullet_diameter_inches=dia,
                weight_grains=wt,
                product_line=pl,
            )
            db.add(b)
            bullets[name] = b
        db.commit()

        return {"bullets": bullets, "cal": cal}

    def test_product_line_match_with_weight(self, product_line_db, db):
        """product_line + weight should give high-confidence match.

        Note: "ELD-X" also matches via composite_key (0.95) since bullet name
        contains "ELD-X". The resolver correctly picks the highest-confidence method.
        """
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "ELD-X"}, "weight_grains": {"value": 178.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == product_line_db["bullets"]["178 gr ELD-X"].id
        assert result.confidence >= 0.93
        assert result.method in ("product_line", "composite_key")

    def test_product_line_match_without_weight(self, product_line_db, db):
        """product_line without weight should still match but with lower confidence."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "Partition"}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == product_line_db["bullets"]["200 gr Partition"].id
        assert result.confidence == 0.80
        assert result.method == "product_line"

    def test_product_line_weight_disambiguates(self, product_line_db, db):
        """When multiple bullets share a product_line, weight should pick the right one.

        With token_set_ratio-based name scoring, composite_key may tie or beat the
        product_line tier when the extracted name ("SST") matches the full DB name
        cleanly. The important guarantee is that the right-weight bullet wins.
        """
        resolver = EntityResolver(db)
        # Two SSTs: 150gr and 165gr
        result = resolver.match_bullet(
            {"name": {"value": "SST"}, "weight_grains": {"value": 150.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == product_line_db["bullets"]["150 gr SST"].id
        assert result.confidence >= 0.93
        assert result.method in ("product_line", "composite_key")

    def test_product_line_distinguishes_eld_x_from_eld_match(self, product_line_db, db):
        """ELD-X and ELD Match are different product lines — should not cross-match."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "ELD-X"}, "weight_grains": {"value": 178.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.entity_id == product_line_db["bullets"]["178 gr ELD-X"].id

    def test_product_line_with_manufacturer_prefix(self, product_line_db, db):
        """'Sierra MatchKing' should match bullet with product_line='MatchKing'."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "Sierra MatchKing"}, "weight_grains": {"value": 175.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == product_line_db["bullets"]["175 gr MatchKing HPBT"].id
        assert result.method == "product_line"

    def test_product_line_with_trademark_symbol(self, product_line_db, db):
        """'SST®' should match bullet with product_line='SST'."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "SST\u00ae"}, "weight_grains": {"value": 165.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == product_line_db["bullets"]["165 gr SST"].id

    def test_generic_bullet_skips_product_line_tier(self, product_line_db, db):
        """Generic bullet (no product_line) should not match via product_line."""
        resolver = EntityResolver(db)
        # "SP Boattail" has no product_line — should fall through to Tier 2/3
        result = resolver.match_bullet(
            {"name": {"value": "SP Boattail"}, "weight_grains": {"value": 165.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        # Should match the "165 gr SP Boattail" bullet via composite_key or fuzzy, not product_line
        assert result.matched is True
        assert result.method != "product_line"

    def test_explicit_product_line_field(self, product_line_db, db):
        """When extracted entity has an explicit product_line field, use it."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {
                "name": {"value": "Nosler Partition"},
                "weight_grains": {"value": 200.0},
                "product_line": {"value": "Partition"},
            },
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == product_line_db["bullets"]["200 gr Partition"].id
        assert result.method == "product_line"

    def test_product_line_methods_tried(self, product_line_db, db):
        """product_line should appear in methods_tried."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "ELD-X"}, "weight_grains": {"value": 178.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert "product_line" in result.methods_tried


# ---------------------------------------------------------------------------
# Hyphen preservation in _normalize (finding #7)
# ---------------------------------------------------------------------------


class TestNormalizeHyphenPreservation:
    """_normalize must keep hyphens so identifier strings stay distinct.

    Before the fix, ``_normalize("ELD-X")`` returned ``"eld x"``, which meant
    Jaccard matched {eld, x} against any DB name containing the letter "X"
    alone — noise that pulled unrelated bullets into fuzzy matches.
    """

    def test_hyphen_preserved_in_single_identifier(self):
        assert _normalize("ELD-X") == "eld-x"

    def test_hyphen_preserved_among_other_tokens(self):
        assert _normalize("30 Cal .308 178 gr ELD-X") == "30 cal .308 178 gr eld-x"

    def test_unicode_dash_normalized_to_ascii_hyphen(self):
        # U+2013 EN DASH is common in web-scraped product names.
        assert _normalize("ELD\u2013X") == "eld-x"

    def test_eldx_does_not_collapse_to_match_at_name_similarity(self):
        """The regression target: "ELD-X" vs "ELD Match" must not score as high as "ELD-X" vs "ELD-X"."""
        exact = _name_similarity("ELD-X", "30 Cal .308 178 gr ELD-X")
        conflated = _name_similarity("ELD-X", "30 Cal .308 178 gr ELD Match")
        assert exact == 1.0
        assert conflated < 0.7
        assert exact - conflated > 0.3


# ---------------------------------------------------------------------------
# bullet_product_line EntityAlias integration (finding #2, step 3)
# ---------------------------------------------------------------------------


class TestBulletProductLineAlias:
    """match_bullet should resolve curator-added abbreviations via EntityAlias.

    The TODO.md line 49 cases — ELDM → ELD Match, SMK → MatchKing,
    ABLR → AccuBond Long Range — previously required code changes. After wiring
    ``lookup_entity("bullet_product_line", ...)`` into ``match_bullet``, adding
    a YAML ``add_entity_alias`` patch is all it takes.
    """

    @pytest.fixture()
    def aliased_db(self, db):
        hornady = Manufacturer(name="Hornady", country="US")
        sierra = Manufacturer(name="Sierra Bullets", alt_names=["Sierra"], country="US")
        nosler = Manufacturer(name="Nosler", country="US")
        db.add_all([hornady, sierra, nosler])
        db.flush()

        # Canonical product lines with curator-visible names.
        pl_eld_match = BulletProductLine(manufacturer_id=hornady.id, name="ELD Match", slug="eld-match")
        pl_matchking = BulletProductLine(manufacturer_id=sierra.id, name="MatchKing", slug="matchking")
        pl_ablr = BulletProductLine(manufacturer_id=nosler.id, name="AccuBond Long Range", slug="accubond-long-range")
        db.add_all([pl_eld_match, pl_matchking, pl_ablr])
        db.flush()

        # Bullets linked to the product_line FK. Note: product_line string is
        # intentionally left NULL on some rows to prove the FK path works
        # independently of the legacy string column.
        bullets = {
            "eld_match_178": Bullet(
                manufacturer_id=hornady.id,
                name="30 Cal .308 178 gr ELD® Match",
                bullet_diameter_inches=0.308,
                weight_grains=178.0,
                product_line_id=pl_eld_match.id,
                product_line=None,
            ),
            "matchking_175": Bullet(
                manufacturer_id=sierra.id,
                name="30 CAL 175 GR HPBT MATCHKING",
                bullet_diameter_inches=0.308,
                weight_grains=175.0,
                product_line_id=pl_matchking.id,
                product_line=None,
            ),
            "ablr_190": Bullet(
                manufacturer_id=nosler.id,
                name="30 Caliber 190gr AccuBond Long Range",
                bullet_diameter_inches=0.308,
                weight_grains=190.0,
                product_line_id=pl_ablr.id,
                product_line=None,
            ),
        }
        db.add_all(bullets.values())
        db.flush()

        # Curator-added aliases — the whole point of this tier.
        db.add_all(
            [
                EntityAlias(
                    entity_type="bullet_product_line",
                    entity_id=pl_eld_match.id,
                    alias="ELDM",
                    alias_type="abbreviation",
                ),
                EntityAlias(
                    entity_type="bullet_product_line",
                    entity_id=pl_matchking.id,
                    alias="SMK",
                    alias_type="abbreviation",
                ),
                EntityAlias(
                    entity_type="bullet_product_line",
                    entity_id=pl_ablr.id,
                    alias="ABLR",
                    alias_type="abbreviation",
                ),
            ]
        )
        db.commit()

        return {
            "hornady": hornady,
            "sierra": sierra,
            "nosler": nosler,
            "pl_eld_match": pl_eld_match,
            "pl_matchking": pl_matchking,
            "pl_ablr": pl_ablr,
            "bullets": bullets,
        }

    def test_eldm_alias_resolves_to_eld_match(self, aliased_db, db):
        """ELDM alias → ELD Match product line → correct bullet at matching weight."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "ELDM"}, "weight_grains": {"value": 178.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == aliased_db["bullets"]["eld_match_178"].id
        assert result.method == "product_line_alias"
        assert result.confidence == 0.93

    def test_smk_alias_resolves_to_matchking(self, aliased_db, db):
        """SMK alias → MatchKing product line."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "SMK"}, "weight_grains": {"value": 175.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == aliased_db["bullets"]["matchking_175"].id
        assert result.method == "product_line_alias"

    def test_ablr_alias_resolves_to_accubond_long_range(self, aliased_db, db):
        """ABLR alias → AccuBond Long Range — three-word expansion via EntityAlias."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "ABLR"}, "weight_grains": {"value": 190.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == aliased_db["bullets"]["ablr_190"].id
        assert result.method == "product_line_alias"

    def test_alias_with_weight_mismatch_still_matches_but_lower_conf(self, aliased_db, db):
        """Alias hits the FK even without a weight match, scoring 0.80 instead of 0.93."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "ELDM"}},  # no weight
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == aliased_db["bullets"]["eld_match_178"].id
        assert result.confidence == 0.80
        assert result.method == "product_line_alias"

    def test_explicit_product_line_field_uses_alias(self, aliased_db, db):
        """The explicit ``product_line`` extraction field also feeds the alias lookup."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {
                "name": {"value": "30 Cal 178gr"},
                "weight_grains": {"value": 178.0},
                "product_line": {"value": "ELDM"},
            },
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == aliased_db["bullets"]["eld_match_178"].id
        assert result.method == "product_line_alias"

    def test_canonical_name_also_resolves_via_fk(self, aliased_db, db):
        """Exact canonical name "ELD Match" also resolves via the FK tier (lookup_entity Tier 1)."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "ELD Match"}, "weight_grains": {"value": 178.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert result.matched is True
        assert result.entity_id == aliased_db["bullets"]["eld_match_178"].id
        # Could be product_line_alias or product_line — both are high-confidence and correct.
        assert result.confidence >= 0.93

    def test_unknown_abbreviation_does_not_match(self, aliased_db, db):
        """An abbreviation with no EntityAlias row should not false-match at the alias tier."""
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "XYZZY"}, "weight_grains": {"value": 178.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        # Either no match, or not via the alias tier.
        if result.matched:
            assert result.method != "product_line_alias"

    def test_alias_tier_appears_in_methods_tried(self, aliased_db, db):
        resolver = EntityResolver(db)
        result = resolver.match_bullet(
            {"name": {"value": "ELDM"}, "weight_grains": {"value": 178.0}},
            manufacturer_id=None,
            bullet_diameter_inches=0.308,
        )
        assert "product_line_alias" in result.methods_tried


# ---------------------------------------------------------------------------
# Relaxed-diameter fallback — v6 regression suite (2026-04-22)
#
# The fallback was introduced in 1875a00 to recover cartridges whose caliber
# fuzzy-matched to a wrong-diameter variant. In the v6 dry-run it over-matched
# 21 cartridges to wrong-caliber bullets (e.g. 30-06 165gr → .357 Handgun Solid)
# because its ``fallback_min_name_confidence`` gate was applied to the
# composite-inflated ``MatchResult.confidence`` — whose 0.85 floor equals the
# gate. Fix adds ``fallback_min_raw_name_similarity`` gated on the extracted
# name vs matched bullet name (raw similarity, not the composite-inflated
# confidence). These 5 tests lock both the over-match reject (3, 5) and the
# legitimate recovery path (4).
# ---------------------------------------------------------------------------


class TestRelaxedDiameterFallback:
    """Regression tests pinning the v6 fix for fallback over-matching."""

    @pytest.fixture()
    def fallback_db(self, db):
        """Seed minimal DB exercising the fallback path across multiple calibers."""
        nosler = Manufacturer(name="Nosler", type_tags=["bullet_maker", "ammo_maker"], country="USA")
        federal = Manufacturer(name="Federal", type_tags=["ammo_maker"], country="USA")
        db.add_all([nosler, federal])
        db.flush()

        cal_308 = Caliber(name=".30-06 Springfield", bullet_diameter_inches=0.308)
        cal_375 = Caliber(name=".375 H&H Magnum", bullet_diameter_inches=0.375)
        cal_357 = Caliber(name=".357 Magnum", bullet_diameter_inches=0.357)
        cal_458 = Caliber(name=".458 Winchester Magnum", bullet_diameter_inches=0.458)
        # A caliber missing from DB: ".30-378 Weatherby" — fixture doesn't insert
        # it. The resolver will fuzzy-match it to ".30-06 Springfield" (same .308)
        # OR ".338-378" (different diameter) depending on what's available. For
        # test 4 we want the resolver to land on a wrong-diameter caliber so the
        # fallback path actually fires. Seed ".338-378 Weatherby Magnum" to win
        # that fuzzy match.
        cal_338_378 = Caliber(name=".338-378 Weatherby Magnum", bullet_diameter_inches=0.338)
        db.add_all([cal_308, cal_375, cal_357, cal_458, cal_338_378])
        db.flush()

        # Bullets used by each test. Names chosen to expose the over-match pattern
        # observed in the v6 regression — wrong-caliber bullet with matching weight
        # but dissimilar name should be rejected; right-caliber bullet with matching
        # weight and very similar name should be picked.
        bullets = {
            # Test 1: cross-caliber weight collision (180gr in .308 and .338)
            "bt_hunting_308_180": Bullet(
                manufacturer_id=nosler.id,
                name="30 Caliber 180gr Ballistic Tip Hunting",
                bullet_diameter_inches=0.308,
                weight_grains=180.0,
            ),
            "accubond_338_180": Bullet(
                manufacturer_id=nosler.id,
                name="338 Caliber 180gr AccuBond",
                bullet_diameter_inches=0.338,
                weight_grains=180.0,
            ),
            # Test 2: .375 H&H 300gr Trophy Bonded Sledgehammer vs .458 JHP decoy
            "sledgehammer_375_300": Bullet(
                manufacturer_id=federal.id,
                name="Trophy Bonded Sledgehammer Solid, .375, 300 Grain",
                bullet_diameter_inches=0.375,
                weight_grains=300.0,
            ),
            "jhp_458_300": Bullet(
                manufacturer_id=federal.id,
                name="Jacketed Hollow Point Rifle Bullet, .458, 300 Grain",
                bullet_diameter_inches=0.458,
                weight_grains=300.0,
            ),
            # Test 3: no right-caliber BT bullet exists at 165gr; decoys in wrong
            # calibers (.357 Handgun Solid + .308 InterLock SP at 165gr).
            "handgun_357_165": Bullet(
                manufacturer_id=nosler.id,
                name=".357 165gr Handgun Solid",
                bullet_diameter_inches=0.357,
                weight_grains=165.0,
            ),
            "interlock_308_165": Bullet(
                manufacturer_id=nosler.id,
                name="30 Caliber 165gr InterLock SP",
                bullet_diameter_inches=0.308,
                weight_grains=165.0,
            ),
            # Test 4: .30-378 Wby bullet lives at .308, caliber table only has
            # .338-378 at 0.338 (so cartridge's caliber_id resolves to wrong
            # diameter and the primary match returns nothing usable — fallback
            # must kick in and pick the .308 bullet with matching name).
            "legit_308_210": Bullet(
                manufacturer_id=nosler.id,
                name="30 Caliber 210gr AccuBond Long Range",
                bullet_diameter_inches=0.308,
                weight_grains=210.0,
            ),
            # Test 5: decoy bullet with inflated composite confidence but low raw
            # name similarity. Name "Foo Bar" vs extracted "Ballistic Tip Hunting"
            # will produce name_score ≈ 0.55 (just above composite_name_score_threshold)
            # → confidence ≈ 0.85 + 0.1×0.55 ≈ 0.905 via composite_key. Passes
            # the old confidence gate, fails the new raw-name gate.
            "decoy_composite_trap": Bullet(
                manufacturer_id=nosler.id,
                name="30 Caliber 165gr Foo Bar Tip",
                bullet_diameter_inches=0.277,
                weight_grains=165.0,
            ),
        }
        db.add_all(bullets.values())
        db.commit()
        return {
            "mfrs": {"nosler": nosler, "federal": federal},
            "calibers": {
                "308": cal_308,
                "375": cal_375,
                "357": cal_357,
                "458": cal_458,
                "338_378": cal_338_378,
            },
            "bullets": bullets,
        }

    def test_1_cross_caliber_weight_collision_picks_right_diameter(self, fallback_db, db):
        """Primary diameter-filtered path must pick .308 when caliber resolves correctly,
        even though a same-weight .338 bullet exists. This doesn't exercise the fallback
        — it validates the non-fallback baseline before the fallback even fires."""
        resolver = EntityResolver(db)
        result = resolver.resolve(
            {
                "name": {"value": "Nosler 30-06 180gr Ballistic Tip Hunting"},
                "manufacturer": {"value": "Nosler"},
                "caliber": {"value": ".30-06 Springfield"},
                "bullet_name": {"value": "30 Caliber 180gr Ballistic Tip Hunting"},
                "bullet_weight_grains": {"value": 180.0},
            },
            "cartridge",
        )
        assert (
            result.bullet_id == fallback_db["bullets"]["bt_hunting_308_180"].id
        ), "Expected .308 180gr Ballistic Tip Hunting, got wrong bullet"

    def test_2_sledgehammer_375_not_458_jhp(self, fallback_db, db):
        """.375 H&H 300gr Sledgehammer must not resolve to .458 JHP via fallback."""
        resolver = EntityResolver(db)
        result = resolver.resolve(
            {
                "name": {"value": "Federal Safari 375 H&H Magnum 300gr Trophy Bonded Sledgehammer Solid"},
                "manufacturer": {"value": "Federal"},
                "caliber": {"value": ".375 H&H Magnum"},
                "bullet_name": {"value": "Trophy Bonded Sledgehammer Solid, .375, 300 Grain"},
                "bullet_weight_grains": {"value": 300.0},
            },
            "cartridge",
        )
        assert (
            result.bullet_id == fallback_db["bullets"]["sledgehammer_375_300"].id
        ), "Expected .375 Sledgehammer; .458 JHP leakage indicates fallback over-match"

    def test_3_no_right_bullet_fallback_must_not_pick_357_handgun(self, fallback_db, db):
        """When the extracted bullet name "Ballistic Tip Hunting" has no .308 match at
        165gr, the fallback must NOT accept ".357 165gr Handgun Solid". Either it picks
        a correct-caliber bullet (not seeded here) or returns unmatched — but the .357
        Handgun Solid has raw_name_sim ≪ 0.90 to "Ballistic Tip Hunting" and must be
        rejected. This pins the exact failure mode observed in the v6 regression."""
        resolver = EntityResolver(db)
        result = resolver.resolve(
            {
                "name": {"value": "Nosler 30-06 Springfield 165gr Ballistic Tip Hunting"},
                "manufacturer": {"value": "Nosler"},
                "caliber": {"value": ".30-06 Springfield"},
                "bullet_name": {"value": "30 Caliber 165gr Ballistic Tip Hunting"},
                "bullet_weight_grains": {"value": 165.0},
            },
            "cartridge",
        )
        assert (
            result.bullet_id != fallback_db["bullets"]["handgun_357_165"].id
        ), ".357 Handgun Solid selected for a .308 cartridge — fallback gate failed"

    def test_4_legitimate_recovery_wrong_caliber_resolved(self, fallback_db, db):
        """Legitimate use case: extracted caliber ".30-378 Wby Mag" isn't in the caliber
        table, so the resolver fuzzy-matches it to ".338-378 Weatherby Magnum" (wrong
        diameter). Primary match filters to .338 and finds nothing. The fallback then
        searches unfiltered, finds the .308 bullet whose name matches the extracted
        bullet name nearly perfectly, and should recover it."""
        resolver = EntityResolver(db)
        result = resolver.resolve(
            {
                "name": {"value": "Nosler 30-378 Weatherby Magnum 210gr AccuBond Long Range"},
                "manufacturer": {"value": "Nosler"},
                "caliber": {"value": ".30-378 Weatherby Magnum"},
                "bullet_name": {"value": "30 Caliber 210gr AccuBond Long Range"},
                "bullet_weight_grains": {"value": 210.0},
            },
            "cartridge",
        )
        assert result.bullet_id == fallback_db["bullets"]["legit_308_210"].id, (
            "Fallback failed to recover the .308 bullet when caliber fuzzy-resolved " "to wrong-diameter .338-378"
        )

    def test_5_composite_inflation_does_not_bypass_raw_name_gate(self, fallback_db, db):
        """Direct regression pin: fallback candidate produces confidence ≈0.89 via the
        composite_key base (0.85 + name_score*0.1) with name_score just above the
        composite_name_score_threshold (0.55). Old gate ``fallback.confidence >= 0.85``
        accepts; new raw-name gate rejects. This test MUST fail before the fix and
        pass after."""
        resolver = EntityResolver(db)
        # Point the cartridge at a caliber whose primary lookup returns nothing so
        # fallback fires. Decoy bullet has matching weight (165gr) but a dissimilar
        # name ("Foo Bar Tip" vs "Ballistic Tip Hunting") that produces low raw
        # name similarity despite clearing composite_name_score_threshold.
        result = resolver.resolve(
            {
                "name": {"value": "Nosler 30-378 Weatherby Magnum 165gr Ballistic Tip Hunting"},
                "manufacturer": {"value": "Nosler"},
                "caliber": {"value": ".30-378 Weatherby Magnum"},
                "bullet_name": {"value": "30 Caliber 165gr Ballistic Tip Hunting"},
                "bullet_weight_grains": {"value": 165.0},
            },
            "cartridge",
        )
        assert (
            result.bullet_id != fallback_db["bullets"]["decoy_composite_trap"].id
        ), "Decoy bullet accepted via composite-inflated confidence — raw-name gate failed"
