"""Cross-system consistency: curation and the pipeline resolver agree on names.

Both the YAML curation patches and the pipeline `EntityResolver` go through
`drift.resolution.aliases.lookup_entity` for deterministic name matching, so
an alias added by one path must be findable by the other.
"""

import pytest

from drift.curation import _resolve_entity
from drift.models import Caliber, EntityAlias, Manufacturer
from drift.pipeline.resolution.resolver import EntityResolver
from drift.resolution.aliases import lookup_entity


@pytest.fixture()
def seeded(db):
    hornady = Manufacturer(name="Hornady", alt_names=["Hornady Mfg"], country="USA")
    sierra = Manufacturer(name="Sierra Bullets", alt_names=["Sierra"], country="USA")
    cal_65 = Caliber(name="6.5 Creedmoor", alt_names=["6.5 CM"], bullet_diameter_inches=0.264)
    cal_308 = Caliber(name=".308 Winchester", alt_names=[".308 Win"], bullet_diameter_inches=0.308)
    db.add_all([hornady, sierra, cal_65, cal_308])
    db.flush()

    # Aliases that ONLY live in EntityAlias — neither model has them in alt_names.
    db.add_all(
        [
            EntityAlias(
                entity_type="manufacturer",
                entity_id=hornady.id,
                alias="Hornady Manufacturing",
                alias_type="long_name",
            ),
            EntityAlias(
                entity_type="caliber",
                entity_id=cal_308.id,
                alias="308 Win Mag",
                alias_type="abbreviation",
            ),
        ]
    )
    db.commit()
    return {"hornady": hornady, "sierra": sierra, "cal_65": cal_65, "cal_308": cal_308}


def test_manufacturer_entity_alias_visible_to_both_paths(seeded, db):
    """A manufacturer alias added to EntityAlias is findable by both curation and the resolver."""
    expected_id = seeded["hornady"].id

    # Curation path
    assert _resolve_entity(db, "manufacturer", "Hornady Manufacturing") == expected_id

    # Resolver path
    resolver = EntityResolver(db)
    match = resolver.resolve_manufacturer("Hornady Manufacturing")
    assert match.matched is True
    assert match.entity_id == expected_id
    assert match.method == "entity_alias"


def test_caliber_entity_alias_visible_to_both_paths(seeded, db):
    """A caliber alias in EntityAlias is findable by both curation and the resolver."""
    expected_id = seeded["cal_308"].id

    assert _resolve_entity(db, "caliber", "308 Win Mag") == expected_id

    resolver = EntityResolver(db)
    match = resolver.resolve_caliber("308 Win Mag")
    assert match.matched is True
    assert match.entity_id == expected_id


def test_caliber_alt_names_visible_to_both_paths(seeded, db):
    """An alt_name on the caliber row is findable by both paths."""
    expected_id = seeded["cal_65"].id

    assert _resolve_entity(db, "caliber", "6.5 CM") == expected_id

    resolver = EntityResolver(db)
    match = resolver.resolve_caliber("6.5 CM")
    assert match.matched is True
    assert match.entity_id == expected_id


def test_period_insensitive_caliber_visible_to_both_paths(seeded, db):
    """The "308 Winchester" ↔ ".308 Winchester" period flip is consistent across paths."""
    expected_id = seeded["cal_308"].id

    assert _resolve_entity(db, "caliber", "308 Winchester") == expected_id

    resolver = EntityResolver(db)
    match = resolver.resolve_caliber("308 Winchester")
    assert match.matched is True
    assert match.entity_id == expected_id


def test_manufacturer_alt_names_visible_to_both_paths(seeded, db):
    """An alt_name on the manufacturer row works on both paths."""
    expected_id = seeded["sierra"].id

    assert _resolve_entity(db, "manufacturer", "Sierra") == expected_id

    resolver = EntityResolver(db)
    match = resolver.resolve_manufacturer("Sierra")
    assert match.matched is True
    assert match.entity_id == expected_id


def test_unknown_name_is_unresolved_on_both_paths(seeded, db):
    """Names with no match raise/return cleanly on both paths."""
    with pytest.raises(ValueError):
        _resolve_entity(db, "manufacturer", "Wholly Made Up Co")

    assert lookup_entity(db, "manufacturer", "Wholly Made Up Co") is None

    resolver = EntityResolver(db)
    match = resolver.resolve_manufacturer("Wholly Made Up Co")
    assert match.matched is False


def test_lookup_entity_rejects_unknown_entity_type(db):
    with pytest.raises(ValueError, match="Unknown entity_type"):
        lookup_entity(db, "made_up_type", "anything")
