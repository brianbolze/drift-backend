"""Smoke tests for the schema: create one of everything, verify relationships."""

from drift.models import (
    Bullet,
    BulletBCSource,
    Caliber,
    Cartridge,
    Chamber,
    ChamberAcceptsCaliber,
    EntityAlias,
    Manufacturer,
    RifleModel,
)


def _seed(db):
    """Insert a minimal connected graph and return the objects."""
    mfr = Manufacturer(name="Hornady", type_tags=["bullet_maker", "ammo_maker"], country="USA")
    db.add(mfr)
    db.flush()

    cal = Caliber(
        name="6.5 Creedmoor",
        alt_names=["6.5 CM", "6.5 Creed"],
        bullet_diameter_inches=0.264,
        popularity_rank=1,
        is_common_lr=True,
    )
    db.add(cal)
    db.flush()

    chamber = Chamber(name="6.5 Creedmoor")
    db.add(chamber)
    db.flush()

    link = ChamberAcceptsCaliber(chamber_id=chamber.id, caliber_id=cal.id, is_primary=True)
    db.add(link)
    db.flush()

    bullet = Bullet(
        manufacturer_id=mfr.id,
        name="ELD Match",
        sku="26331",
        caliber_id=cal.id,
        weight_grains=140.0,
        bc_g7_published=0.326,
        type_tags=["boat-tail", "polymer-tip"],
        used_for=["match"],
    )
    db.add(bullet)
    db.flush()

    bc = BulletBCSource(
        bullet_id=bullet.id,
        bc_type="g7",
        bc_value=0.326,
        source="manufacturer",
        source_quality=0.85,
    )
    db.add(bc)

    cart = Cartridge(
        manufacturer_id=mfr.id,
        name="Hornady 6.5 CM 140gr ELD Match",
        sku="81500",
        caliber_id=cal.id,
        bullet_id=bullet.id,
        bullet_weight_grains=140.0,
        muzzle_velocity_fps=2710,
        test_barrel_length_inches=24.0,
        bullet_match_confidence=0.98,
        bullet_match_method="exact_sku",
    )
    db.add(cart)

    rifle = RifleModel(
        manufacturer_id=mfr.id,
        model="B-14 HMR",
        chamber_id=chamber.id,
        barrel_length_inches=22.0,
        twist_rate="1:8",
    )
    db.add(rifle)

    alias = EntityAlias(
        entity_type="caliber",
        entity_id=cal.id,
        alias="6.5 Creedmore",
        alias_type="misspelling",
    )
    db.add(alias)

    db.commit()
    return mfr, cal, chamber, bullet, cart, rifle


def test_full_graph(db):
    mfr, cal, chamber, bullet, cart, rifle = _seed(db)

    # Manufacturer → children
    db.refresh(mfr)
    assert bullet in mfr.bullets
    assert cart in mfr.cartridges
    assert rifle in mfr.rifle_models

    # Caliber → children
    db.refresh(cal)
    assert bullet in cal.bullets
    assert cart in cal.cartridges

    # Chamber ↔ Caliber via join table
    db.refresh(chamber)
    assert len(chamber.caliber_links) == 1
    assert chamber.caliber_links[0].caliber.name == "6.5 Creedmoor"
    assert chamber.caliber_links[0].is_primary is True

    # Bullet → Cartridge, BC sources
    db.refresh(bullet)
    assert cart in bullet.cartridges
    assert len(bullet.bc_sources) == 1
    assert bullet.bc_sources[0].bc_value == 0.326

    # Cartridge → Bullet back-reference
    db.refresh(cart)
    assert cart.bullet.name == "ELD Match"
    assert cart.caliber.name == "6.5 Creedmoor"

    # RifleModel → Chamber
    db.refresh(rifle)
    assert rifle.chamber.name == "6.5 Creedmoor"


def test_json_fields_round_trip(db):
    mfr = Manufacturer(name="Test Mfr", alt_names=["TM", "Test"], type_tags=["ammo_maker"])
    db.add(mfr)
    db.commit()
    db.refresh(mfr)

    assert mfr.alt_names == ["TM", "Test"]
    assert mfr.type_tags == ["ammo_maker"]


def test_caliber_self_referential_fk(db):
    parent = Caliber(name=".308 Winchester", bullet_diameter_inches=0.308)
    db.add(parent)
    db.flush()

    child = Caliber(
        name="6.5 Creedmoor",
        bullet_diameter_inches=0.264,
        parent_caliber_id=parent.id,
    )
    db.add(child)
    db.commit()
    db.refresh(child)

    assert child.parent_caliber.name == ".308 Winchester"
