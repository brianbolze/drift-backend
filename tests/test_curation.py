"""Tests for the YAML data curation system."""

import pytest
import yaml
from pydantic import ValidationError

from drift.curation import (
    PatchFile,
    apply_patch,
    load_and_validate,
)
from drift.models import (
    Bullet,
    BulletBCSource,
    Caliber,
    Chamber,
    ChamberAcceptsCaliber,
    EntityAlias,
    Manufacturer,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def seeded_db(db):
    """Seed DB with manufacturer, caliber, chamber, bullet for resolution tests."""
    mfr = Manufacturer(name="Sierra Bullets", alt_names=["Sierra"])
    db.add(mfr)
    db.flush()

    mfr2 = Manufacturer(name="Federal Premium")
    db.add(mfr2)
    db.flush()

    cal = Caliber(name=".308 Winchester", bullet_diameter_inches=0.308, alt_names=["308 Win"])
    db.add(cal)
    db.flush()

    chamber = Chamber(name=".308 Winchester")
    db.add(chamber)
    db.flush()

    link = ChamberAcceptsCaliber(chamber_id=chamber.id, caliber_id=cal.id)
    db.add(link)
    db.flush()

    # Add an EntityAlias for caliber
    db.add(EntityAlias(entity_type="caliber", entity_id=cal.id, alias="308 Win Mag", alias_type="abbreviation"))
    db.flush()

    return db


def _make_patch(operations: list[dict], patch_id: str = "001_test") -> PatchFile:
    """Create a PatchFile from a list of operation dicts."""
    raw = {
        "patch": {"id": patch_id, "author": "Test", "date": "2026-01-01", "description": "Test patch"},
        "operations": operations,
    }
    return PatchFile.model_validate(raw)


# ── Schema Validation ────────────────────────────────────────────────────────


class TestSchemaValidation:
    def test_valid_create_bullet(self):
        patch = _make_patch(
            [
                {
                    "action": "create_bullet",
                    "manufacturer": "Sierra Bullets",
                    "name": "Test Bullet",
                    "weight_grains": 150.0,
                    "bullet_diameter_inches": 0.308,
                }
            ]
        )
        assert len(patch.operations) == 1
        assert patch.operations[0].action == "create_bullet"

    def test_invalid_weight_range(self):
        with pytest.raises(ValidationError, match="weight_grains"):
            _make_patch(
                [
                    {
                        "action": "create_bullet",
                        "manufacturer": "Sierra Bullets",
                        "name": "Test",
                        "weight_grains": 5000.0,
                        "bullet_diameter_inches": 0.308,
                    }
                ]
            )

    def test_invalid_bc_range(self):
        with pytest.raises(ValidationError, match="bc_g1"):
            _make_patch(
                [
                    {
                        "action": "create_bullet",
                        "manufacturer": "Sierra Bullets",
                        "name": "Test",
                        "weight_grains": 150.0,
                        "bullet_diameter_inches": 0.308,
                        "bc_g1": 5.0,
                    }
                ]
            )

    def test_invalid_patch_id_format(self):
        with pytest.raises(ValidationError, match="id"):
            PatchFile.model_validate(
                {
                    "patch": {"id": "bad-id", "author": "Test", "date": "2026-01-01", "description": "Test"},
                    "operations": [
                        {
                            "action": "create_bullet",
                            "manufacturer": "X",
                            "name": "Y",
                            "weight_grains": 150,
                            "bullet_diameter_inches": 0.308,
                        }
                    ],
                }
            )

    def test_update_bullet_allowlist_enforcement(self):
        """Attempting to update disallowed fields raises ValidationError."""
        with pytest.raises(ValidationError, match="Cannot update fields"):
            _make_patch([{"action": "update_bullet", "manufacturer": "X", "name": "Y", "set": {"id": "bad"}}])

    def test_update_bullet_rejects_is_locked(self):
        with pytest.raises(ValidationError, match="Cannot update fields"):
            _make_patch([{"action": "update_bullet", "manufacturer": "X", "name": "Y", "set": {"is_locked": False}}])

    def test_update_cartridge_allowlist_enforcement(self):
        with pytest.raises(ValidationError, match="Cannot update fields"):
            _make_patch([{"action": "update_cartridge", "manufacturer": "X", "name": "Y", "set": {"name": "hacked"}}])

    def test_load_and_validate_from_file(self, tmp_path):
        patch_file = tmp_path / "001_test.yaml"
        patch_file.write_text(
            yaml.dump(
                {
                    "patch": {"id": "001_test", "author": "Test", "date": "2026-01-01", "description": "Test"},
                    "operations": [
                        {
                            "action": "create_bullet",
                            "manufacturer": "X",
                            "name": "Y",
                            "weight_grains": 150,
                            "bullet_diameter_inches": 0.308,
                        }
                    ],
                }
            )
        )
        result = load_and_validate(patch_file)
        assert result.patch.id == "001_test"


# ── Name Resolution ──────────────────────────────────────────────────────────


class TestNameResolution:
    def test_resolve_manufacturer_exact(self, seeded_db):
        patch = _make_patch(
            [
                {
                    "action": "create_bullet",
                    "manufacturer": "Sierra Bullets",
                    "name": "Test 150gr",
                    "weight_grains": 150.0,
                    "bullet_diameter_inches": 0.308,
                }
            ]
        )
        stats = apply_patch(seeded_db, patch)
        assert stats.created == 1

    def test_resolve_via_entity_alias(self, seeded_db):
        """Caliber resolved via EntityAlias fallback."""
        # First create a bullet for the cartridge to reference
        bullet = Bullet(
            manufacturer_id=seeded_db.query(Manufacturer).filter_by(name="Federal Premium").first().id,
            name="Test Bullet",
            bullet_diameter_inches=0.308,
            weight_grains=150.0,
        )
        seeded_db.add(bullet)
        seeded_db.flush()

        patch = _make_patch(
            [
                {
                    "action": "create_cartridge",
                    "manufacturer": "Federal Premium",
                    "name": "Test Cart",
                    "caliber": "308 Win Mag",  # resolved via EntityAlias
                    "bullet": "Test Bullet",
                    "bullet_weight_grains": 150.0,
                    "muzzle_velocity_fps": 2800,
                }
            ]
        )
        stats = apply_patch(seeded_db, patch)
        assert stats.created == 1

    def test_unknown_manufacturer_error(self, seeded_db):
        patch = _make_patch(
            [
                {
                    "action": "create_bullet",
                    "manufacturer": "Nonexistent Corp",
                    "name": "Test",
                    "weight_grains": 150.0,
                    "bullet_diameter_inches": 0.308,
                }
            ]
        )
        stats = apply_patch(seeded_db, patch)
        assert stats.errors == 1
        assert "not found" in stats.details[0].lower()


# ── Idempotency ──────────────────────────────────────────────────────────────


class TestIdempotency:
    def test_create_bullet_twice_skips(self, seeded_db):
        ops = [
            {
                "action": "create_bullet",
                "manufacturer": "Sierra Bullets",
                "name": "30 CAL 150 GR TEST",
                "weight_grains": 150.0,
                "bullet_diameter_inches": 0.308,
                "bc_g1": 0.417,
            }
        ]
        stats1 = apply_patch(seeded_db, _make_patch(ops))
        assert stats1.created == 1

        stats2 = apply_patch(seeded_db, _make_patch(ops))
        assert stats2.skipped == 1
        assert stats2.created == 0


# ── BC Source Auto-Creation ──────────────────────────────────────────────────


class TestBCSourceCreation:
    def test_create_bullet_generates_bc_sources(self, seeded_db):
        patch = _make_patch(
            [
                {
                    "action": "create_bullet",
                    "manufacturer": "Sierra Bullets",
                    "name": "BC Test Bullet",
                    "weight_grains": 155.0,
                    "bullet_diameter_inches": 0.308,
                    "bc_g1": 0.450,
                    "bc_g7": 0.221,
                    "bc_source": "manufacturer",
                    "bc_source_methodology": "published",
                    "bc_source_notes": "Test note",
                }
            ]
        )
        stats = apply_patch(seeded_db, patch)
        assert stats.created == 1

        bullet = seeded_db.query(Bullet).filter_by(name="BC Test Bullet").first()
        bc_sources = seeded_db.query(BulletBCSource).filter_by(bullet_id=bullet.id).all()
        assert len(bc_sources) == 2
        types = {s.bc_type for s in bc_sources}
        assert types == {"g1", "g7"}

    def test_create_bullet_no_bc_no_sources(self, seeded_db):
        patch = _make_patch(
            [
                {
                    "action": "create_bullet",
                    "manufacturer": "Sierra Bullets",
                    "name": "No BC Bullet",
                    "weight_grains": 100.0,
                    "bullet_diameter_inches": 0.308,
                }
            ]
        )
        apply_patch(seeded_db, patch)
        bullet = seeded_db.query(Bullet).filter_by(name="No BC Bullet").first()
        bc_sources = seeded_db.query(BulletBCSource).filter_by(bullet_id=bullet.id).all()
        assert len(bc_sources) == 0


# ── Update Operations ────────────────────────────────────────────────────────


class TestUpdateOperations:
    def test_update_bullet_fields(self, seeded_db):
        # Create a bullet first
        apply_patch(
            seeded_db,
            _make_patch(
                [
                    {
                        "action": "create_bullet",
                        "manufacturer": "Sierra Bullets",
                        "name": "Update Target",
                        "weight_grains": 168.0,
                        "bullet_diameter_inches": 0.308,
                    }
                ]
            ),
        )

        # Update it
        stats = apply_patch(
            seeded_db,
            _make_patch(
                [
                    {
                        "action": "update_bullet",
                        "manufacturer": "Sierra Bullets",
                        "name": "Update Target",
                        "set": {"bc_g1_published": 0.505, "tip_type": "hollow_point"},
                    }
                ],
                patch_id="002_update",
            ),
        )
        assert stats.updated == 1

        bullet = seeded_db.query(Bullet).filter_by(name="Update Target").first()
        assert bullet.bc_g1_published == 0.505
        assert bullet.tip_type == "hollow_point"
        # Original fields unchanged
        assert bullet.weight_grains == 168.0


# ── Intra-Patch Forward References ───────────────────────────────────────────


class TestForwardReferences:
    def test_create_bullet_then_cartridge_same_patch(self, seeded_db):
        """A cartridge can reference a bullet created earlier in the same patch."""
        patch = _make_patch(
            [
                {
                    "action": "create_bullet",
                    "manufacturer": "Sierra Bullets",
                    "name": "Forward Ref Bullet",
                    "weight_grains": 175.0,
                    "bullet_diameter_inches": 0.308,
                    "bc_g1": 0.505,
                },
                {
                    "action": "create_cartridge",
                    "manufacturer": "Federal Premium",
                    "name": "Federal Gold Medal 308 175gr SMK",
                    "caliber": ".308 Winchester",
                    "bullet": "Forward Ref Bullet",
                    "bullet_manufacturer": "Sierra Bullets",
                    "bullet_weight_grains": 175.0,
                    "muzzle_velocity_fps": 2600,
                },
            ]
        )
        stats = apply_patch(seeded_db, patch)
        assert stats.created == 2
        assert stats.errors == 0


# ── Partial Failure / Savepoint ──────────────────────────────────────────────


class TestPartialFailure:
    def test_middle_op_fails_others_succeed(self, seeded_db):
        """Op 2 of 3 fails; ops 1 and 3 still succeed via savepoints."""
        patch = _make_patch(
            [
                {
                    "action": "create_bullet",
                    "manufacturer": "Sierra Bullets",
                    "name": "Savepoint Bullet 1",
                    "weight_grains": 150.0,
                    "bullet_diameter_inches": 0.308,
                },
                {
                    "action": "create_bullet",
                    "manufacturer": "NONEXISTENT MFG",
                    "name": "Will Fail",
                    "weight_grains": 150.0,
                    "bullet_diameter_inches": 0.308,
                },
                {
                    "action": "create_bullet",
                    "manufacturer": "Sierra Bullets",
                    "name": "Savepoint Bullet 3",
                    "weight_grains": 190.0,
                    "bullet_diameter_inches": 0.308,
                },
            ]
        )
        stats = apply_patch(seeded_db, patch)
        assert stats.created == 2
        assert stats.errors == 1

        # Verify op 1 and 3 persisted
        assert seeded_db.query(Bullet).filter_by(name="Savepoint Bullet 1").first() is not None
        assert seeded_db.query(Bullet).filter_by(name="Savepoint Bullet 3").first() is not None


# ── Dry-Run Mode ─────────────────────────────────────────────────────────────


class TestDryRun:
    def test_rollback_prevents_persistence(self, seeded_db):
        """Simulates dry-run: apply patch then rollback — no records persist."""
        patch = _make_patch(
            [
                {
                    "action": "create_bullet",
                    "manufacturer": "Sierra Bullets",
                    "name": "Dry Run Bullet",
                    "weight_grains": 150.0,
                    "bullet_diameter_inches": 0.308,
                }
            ]
        )
        apply_patch(seeded_db, patch)
        # Simulate dry-run rollback
        seeded_db.rollback()

        assert seeded_db.query(Bullet).filter_by(name="Dry Run Bullet").first() is None


# ── Data Source & Locking ────────────────────────────────────────────────────


class TestCurationMetadata:
    def test_created_bullets_are_manual_and_locked(self, seeded_db):
        patch = _make_patch(
            [
                {
                    "action": "create_bullet",
                    "manufacturer": "Sierra Bullets",
                    "name": "Locked Bullet",
                    "weight_grains": 155.0,
                    "bullet_diameter_inches": 0.308,
                }
            ]
        )
        apply_patch(seeded_db, patch)
        bullet = seeded_db.query(Bullet).filter_by(name="Locked Bullet").first()
        assert bullet.data_source == "manual"
        assert bullet.is_locked is True
