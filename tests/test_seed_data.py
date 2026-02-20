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
    Caliber,
    Chamber,
    ChamberAcceptsCaliber,
    EntityAlias,
    Manufacturer,
)


@pytest.fixture()
def seeded_db():
    """Fresh in-memory DB with all seed data applied."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_all(session)
        yield session


def test_manufacturer_count(seeded_db):
    assert seeded_db.query(Manufacturer).count() == 32


def test_caliber_count(seeded_db):
    assert seeded_db.query(Caliber).count() == 25


def test_chamber_count(seeded_db):
    # 21 auto + 5 manual = 26
    assert seeded_db.query(Chamber).count() == 26


def test_chamber_accepts_caliber_count(seeded_db):
    # 21 auto (1 link each) + .223 Rem (1) + 5.56 NATO (2) + .223 Wylde (2) + .308 Win (2) + 7.62 NATO (2) = 30
    assert seeded_db.query(ChamberAcceptsCaliber).count() == 30


def test_entity_alias_count(seeded_db):
    assert seeded_db.query(EntityAlias).count() == 83


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
    mfr_ids = {m.id for m in seeded_db.query(Manufacturer).all()}
    cal_ids = {c.id for c in seeded_db.query(Caliber).all()}
    entity_ids = {"manufacturer": mfr_ids, "caliber": cal_ids}

    for alias in seeded_db.query(EntityAlias).all():
        ids = entity_ids.get(alias.entity_type, set())
        assert (
            alias.entity_id in ids
        ), f"Alias {alias.alias!r} references {alias.entity_type} {alias.entity_id} which doesn't exist"
