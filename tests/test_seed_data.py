"""Tests for the seed data script — validates counts, relationships, and idempotency."""

import sys
from pathlib import Path

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest  # noqa: E402
from seed_data import seed_all  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from rangefinder.models import (  # noqa: E402
    Base,
    Bullet,
    BulletBCSource,
    Caliber,
    Cartridge,
    Chamber,
    ChamberAcceptsCaliber,
    EntityAlias,
    Manufacturer,
    Optic,
    Reticle,
    RifleModel,
)


@pytest.fixture()
def seeded_db():
    """Fresh in-memory DB with all seed data applied."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_all(session)
        yield session


# ---------------------------------------------------------------------------
# Count tests — verify expected row counts for every table
# ---------------------------------------------------------------------------


def test_manufacturer_count(seeded_db):
    assert seeded_db.query(Manufacturer).count() == 38  # 32 original + 6 optic makers


def test_caliber_count(seeded_db):
    assert seeded_db.query(Caliber).count() == 25


def test_chamber_count(seeded_db):
    # 21 auto + 5 manual = 26
    assert seeded_db.query(Chamber).count() == 26


def test_chamber_accepts_caliber_count(seeded_db):
    # 21 auto (1 link each) + .223 Rem (1) + 5.56 NATO (2) + .223 Wylde (2) + .308 Win (2) + 7.62 NATO (2) = 30
    assert seeded_db.query(ChamberAcceptsCaliber).count() == 30


def test_bullet_count(seeded_db):
    assert seeded_db.query(Bullet).count() == 15


def test_bullet_bc_source_count(seeded_db):
    assert seeded_db.query(BulletBCSource).count() == 7


def test_cartridge_count(seeded_db):
    assert seeded_db.query(Cartridge).count() == 15


def test_rifle_model_count(seeded_db):
    assert seeded_db.query(RifleModel).count() == 15


def test_reticle_count(seeded_db):
    assert seeded_db.query(Reticle).count() == 13


def test_optic_count(seeded_db):
    assert seeded_db.query(Optic).count() == 16


def test_entity_alias_count(seeded_db):
    assert seeded_db.query(EntityAlias).count() == 115


# ---------------------------------------------------------------------------
# Chamber relationship tests (unchanged from original)
# ---------------------------------------------------------------------------


def test_wylde_chamber_accepts_both(seeded_db):
    """The .223 Wylde chamber should accept both .223 Rem and 5.56 NATO."""
    wylde = seeded_db.query(Chamber).filter_by(name=".223 Wylde").one()
    links = seeded_db.query(ChamberAcceptsCaliber).filter_by(chamber_id=wylde.id).all()
    caliber_names = {seeded_db.get(Caliber, link.caliber_id).name: link.is_primary for link in links}
    assert caliber_names == {".223 Remington": True, "5.56x45mm NATO": False}


def test_556_chamber_accepts_223(seeded_db):
    """5.56 NATO chamber accepts 5.56 (primary) and .223 Rem (secondary)."""
    chamber = seeded_db.query(Chamber).filter_by(name="5.56 NATO").one()
    links = seeded_db.query(ChamberAcceptsCaliber).filter_by(chamber_id=chamber.id).all()
    caliber_names = {seeded_db.get(Caliber, link.caliber_id).name: link.is_primary for link in links}
    assert caliber_names == {"5.56x45mm NATO": True, ".223 Remington": False}


def test_762_nato_chamber_accepts_308(seeded_db):
    """7.62 NATO chamber accepts 7.62 (primary) and .308 Win (secondary)."""
    chamber = seeded_db.query(Chamber).filter_by(name="7.62x51mm NATO").one()
    links = seeded_db.query(ChamberAcceptsCaliber).filter_by(chamber_id=chamber.id).all()
    caliber_names = {seeded_db.get(Caliber, link.caliber_id).name: link.is_primary for link in links}
    assert caliber_names == {"7.62x51mm NATO": True, ".308 Winchester": False}


def test_308_chamber_accepts_762(seeded_db):
    """.308 Win chamber accepts .308 (primary) and 7.62x51 NATO (secondary)."""
    chamber = seeded_db.query(Chamber).filter_by(name=".308 Winchester").one()
    links = seeded_db.query(ChamberAcceptsCaliber).filter_by(chamber_id=chamber.id).all()
    caliber_names = {seeded_db.get(Caliber, link.caliber_id).name: link.is_primary for link in links}
    assert caliber_names == {".308 Winchester": True, "7.62x51mm NATO": False}


def test_223_rem_chamber_only_accepts_223(seeded_db):
    """.223 Remington chamber should only accept .223 Rem — NOT 5.56 NATO."""
    chamber = seeded_db.query(Chamber).filter_by(name=".223 Remington").one()
    links = seeded_db.query(ChamberAcceptsCaliber).filter_by(chamber_id=chamber.id).all()
    assert len(links) == 1
    cal = seeded_db.get(Caliber, links[0].caliber_id)
    assert cal.name == ".223 Remington"
    assert links[0].is_primary is True


def test_auto_chambers_have_one_primary_link(seeded_db):
    """Every auto-generated chamber should have exactly one primary caliber link."""
    auto_names = [
        "6.5 Creedmoor",
        "6mm Dasher",
        "6mm GT",
        "6mm Creedmoor",
        ".300 Winchester Magnum",
        ".300 PRC",
        "6.5 PRC",
        ".338 Lapua Magnum",
        ".270 Winchester",
        "6mm ARC",
        "6.5-284 Norma",
    ]
    for name in auto_names:
        chamber = seeded_db.query(Chamber).filter_by(name=name).one()
        links = seeded_db.query(ChamberAcceptsCaliber).filter_by(chamber_id=chamber.id).all()
        assert len(links) == 1, f"{name} should have exactly 1 link, got {len(links)}"
        assert links[0].is_primary is True, f"{name} link should be primary"
        cal = seeded_db.get(Caliber, links[0].caliber_id)
        assert cal.name == name, f"{name} chamber should link to {name} caliber"


# ---------------------------------------------------------------------------
# Caliber-level tests
# ---------------------------------------------------------------------------


def test_caliber_popularity_ranks_unique(seeded_db):
    """All popularity ranks should be unique (no ties)."""
    ranks = [c.popularity_rank for c in seeded_db.query(Caliber).filter(Caliber.popularity_rank.isnot(None)).all()]
    assert len(ranks) == len(set(ranks)), f"Duplicate ranks: {ranks}"


def test_new_prs_calibers_exist(seeded_db):
    """6mm Dasher and 6mm GT must exist — they're the #1 and #2 PRS cartridges."""
    dasher = seeded_db.query(Caliber).filter_by(name="6mm Dasher").one()
    assert dasher.popularity_rank == 3
    assert dasher.is_common_lr is True

    gt = seeded_db.query(Caliber).filter_by(name="6mm GT").one()
    assert gt.popularity_rank == 4
    assert gt.is_common_lr is True


def test_260_rem_not_common_lr(seeded_db):
    """.260 Rem should be is_common_lr=False — displaced by 6.5 CM."""
    cal = seeded_db.query(Caliber).filter_by(name=".260 Remington").one()
    assert cal.is_common_lr is False


def test_308_762_bidirectional(seeded_db):
    """Both .308 Win and 7.62 NATO chambers should accept each other's caliber."""
    ch308 = seeded_db.query(Chamber).filter_by(name=".308 Winchester").one()
    ch762 = seeded_db.query(Chamber).filter_by(name="7.62x51mm NATO").one()

    links_308 = {
        seeded_db.get(Caliber, link.caliber_id).name: link.is_primary
        for link in seeded_db.query(ChamberAcceptsCaliber).filter_by(chamber_id=ch308.id).all()
    }
    links_762 = {
        seeded_db.get(Caliber, link.caliber_id).name: link.is_primary
        for link in seeded_db.query(ChamberAcceptsCaliber).filter_by(chamber_id=ch762.id).all()
    }

    assert links_308 == {".308 Winchester": True, "7.62x51mm NATO": False}
    assert links_762 == {"7.62x51mm NATO": True, ".308 Winchester": False}


# ---------------------------------------------------------------------------
# Bullet and Cartridge relationship tests
# ---------------------------------------------------------------------------


def test_hornady_140_eld_match_exists(seeded_db):
    """The flagship 6.5 CM bullet must exist with correct BC values."""
    bullet = seeded_db.query(Bullet).filter_by(sku="26331").first()
    assert bullet is not None
    assert bullet.weight_grains == 140.0
    assert bullet.bc_g7_published == 0.326
    assert bullet.bc_g7_estimated == 0.321


def test_cartridge_links_to_bullet(seeded_db):
    """Hornady 81500 cartridge should link to 26331 bullet."""
    cart = seeded_db.query(Cartridge).filter_by(sku="81500").one()
    bullet = seeded_db.query(Bullet).filter_by(sku="26331").first()
    assert cart.bullet_id == bullet.id
    assert cart.muzzle_velocity_fps == 2710
    assert cart.bullet_match_confidence == 1.0


def test_bullet_has_bc_sources(seeded_db):
    """The 140 ELD Match should have multiple BC source rows."""
    bullet = seeded_db.query(Bullet).filter_by(sku="26331").first()
    sources = seeded_db.query(BulletBCSource).filter_by(bullet_id=bullet.id).all()
    assert len(sources) >= 2
    source_names = {s.source for s in sources}
    assert "manufacturer" in source_names
    assert "applied_ballistics" in source_names


def test_bullets_span_both_calibers(seeded_db):
    """Bullets should cover both 6.5 CM and .308 Win."""
    cal_65 = seeded_db.query(Caliber).filter_by(name="6.5 Creedmoor").one()
    cal_308 = seeded_db.query(Caliber).filter_by(name=".308 Winchester").one()
    count_65 = seeded_db.query(Bullet).filter_by(caliber_id=cal_65.id).count()
    count_308 = seeded_db.query(Bullet).filter_by(caliber_id=cal_308.id).count()
    assert count_65 >= 5, f"Expected >= 5 6.5 CM bullets, got {count_65}"
    assert count_308 >= 5, f"Expected >= 5 .308 Win bullets, got {count_308}"


# ---------------------------------------------------------------------------
# Rifle model tests
# ---------------------------------------------------------------------------


def test_rifle_model_has_model_family(seeded_db):
    """Rifle models should have model_family for grouping."""
    bergara_65 = seeded_db.query(RifleModel).filter(RifleModel.model.contains("B-14 HMR 6.5")).first()
    bergara_308 = seeded_db.query(RifleModel).filter(RifleModel.model.contains("B-14 HMR .308")).first()
    assert bergara_65 is not None
    assert bergara_308 is not None
    assert bergara_65.model_family == "Bergara B-14 HMR"
    assert bergara_308.model_family == "Bergara B-14 HMR"
    assert bergara_65.id != bergara_308.id


# ---------------------------------------------------------------------------
# Optic and Reticle tests
# ---------------------------------------------------------------------------


def test_optic_links_to_reticle(seeded_db):
    """Viper PST Mil variant should link to EBR-7C MRAD reticle."""
    optic = seeded_db.query(Optic).filter_by(sku="PST-5258").one()
    reticle = seeded_db.query(Reticle).filter_by(name="EBR-7C MRAD").one()
    assert optic.reticle_id == reticle.id
    assert optic.click_unit == "mil"
    assert optic.click_value == 0.1


def test_optic_model_family_groups_variants(seeded_db):
    """Mil and MOA variants of Viper PST should share model_family."""
    mil = seeded_db.query(Optic).filter_by(sku="PST-5258").one()
    moa = seeded_db.query(Optic).filter_by(sku="PST-5259").one()
    assert mil.model_family == moa.model_family
    assert mil.click_unit == "mil"
    assert moa.click_unit == "moa"


def test_optic_manufacturers_have_optic_maker_tag(seeded_db):
    """All 6 optic manufacturers should have the optic_maker type_tag."""
    optic_makers = (
        seeded_db.query(Manufacturer)
        .filter(
            Manufacturer.name.in_(
                [
                    "Vortex Optics",
                    "Nightforce Optics",
                    "Leupold",
                    "Kahles",
                    "Sig Sauer",
                    "Zero Compromise Optics",
                ]
            )
        )
        .all()
    )
    assert len(optic_makers) == 6
    for m in optic_makers:
        assert "optic_maker" in m.type_tags, f"{m.name} missing optic_maker tag"


def test_reticle_links_to_manufacturer(seeded_db):
    """Reticles should have valid manufacturer FKs."""
    for reticle in seeded_db.query(Reticle).all():
        mfr = seeded_db.get(Manufacturer, reticle.manufacturer_id)
        assert mfr is not None, f"Reticle {reticle.name} has invalid manufacturer_id"


# ---------------------------------------------------------------------------
# Entity alias validation tests
# ---------------------------------------------------------------------------


def test_alias_types_are_valid(seeded_db):
    valid_types = {
        "abbreviation",
        "misspelling",
        "alternate_name",
        "sku",
        "military_designation",
        "nickname",
        "discontinued_predecessor",
    }
    actual = {a.alias_type for a in seeded_db.query(EntityAlias).all()}
    assert actual.issubset(valid_types), f"Unexpected alias types: {actual - valid_types}"


def test_all_aliases_reference_existing_entities(seeded_db):
    """Every alias should point to an entity that exists in the DB."""
    entity_ids: dict[str, set[str]] = {
        "manufacturer": {m.id for m in seeded_db.query(Manufacturer).all()},
        "caliber": {c.id for c in seeded_db.query(Caliber).all()},
        "bullet": {b.id for b in seeded_db.query(Bullet).all()},
        "cartridge": {c.id for c in seeded_db.query(Cartridge).all()},
        "reticle": {r.id for r in seeded_db.query(Reticle).all()},
        "optic": {o.id for o in seeded_db.query(Optic).all()},
    }

    for alias in seeded_db.query(EntityAlias).all():
        ids = entity_ids.get(alias.entity_type, set())
        assert (
            alias.entity_id in ids
        ), f"Alias {alias.alias!r} references {alias.entity_type} {alias.entity_id} which doesn't exist"
