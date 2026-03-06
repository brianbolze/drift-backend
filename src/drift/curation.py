"""YAML-based data curation: schemas, name resolution, and patch applier.

Numbered YAML patch files in data/patches/ are validated against Pydantic
schemas, then applied idempotently to the database. All created records get
data_source="manual" and is_locked=True automatically.

Usage (via Makefile):
    make curate           # dry-run preview
    make curate-commit    # write to DB
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from pydantic import BaseModel, ConfigDict, Discriminator, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from drift.models import (
    Bullet,
    BulletBCSource,
    Caliber,
    Cartridge,
    Chamber,
    EntityAlias,
    Manufacturer,
    RifleModel,
)

logger = logging.getLogger(__name__)

# ── Allowlisted update fields ────────────────────────────────────────────────

_BULLET_UPDATE_FIELDS = frozenset(
    {
        "name",
        "alt_names",
        "sku",
        "weight_grains",
        "bullet_diameter_inches",
        "bc_g1_published",
        "bc_g7_published",
        "bc_g1_estimated",
        "bc_g7_estimated",
        "length_inches",
        "sectional_density",
        "base_type",
        "tip_type",
        "construction",
        "type_tags",
        "used_for",
        "is_lead_free",
        "source_url",
    }
)

_CARTRIDGE_UPDATE_FIELDS = frozenset(
    {
        "bc_g1",
        "bc_g7",
        "bullet_length_inches",
        "muzzle_velocity_fps",
        "test_barrel_length_inches",
        "round_count",
        "product_line",
        "source_url",
        "sku",
    }
)


# ── Pydantic Schemas ─────────────────────────────────────────────────────────


class PatchMetadata(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(..., pattern=r"^\d{3}_[a-z0-9_]+$")
    author: str = Field(..., min_length=1)
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    description: str = Field(..., min_length=1, max_length=500)


class CreateCaliberOp(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    action: Literal["create_caliber"]
    name: str = Field(..., min_length=1, max_length=255)
    bullet_diameter_inches: float = Field(..., ge=0.172, le=0.700)
    alt_names: list[str] | None = None
    case_length_inches: float | None = Field(None, ge=0.5, le=5.0)
    coal_inches: float | None = Field(None, ge=0.5, le=6.0)
    max_pressure_psi: int | None = Field(None, ge=10000, le=100000)
    rim_type: str | None = None
    action_length: str | None = None
    year_introduced: int | None = Field(None, ge=1800, le=2030)
    is_common_lr: bool = False
    source_url: str | None = Field(None, max_length=500)


class CreateBulletOp(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    action: Literal["create_bullet"]
    manufacturer: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=255)
    sku: str | None = Field(None, max_length=100)
    weight_grains: float = Field(..., ge=15, le=750)
    bullet_diameter_inches: float = Field(..., ge=0.172, le=0.510)
    bc_g1: float | None = Field(None, ge=0.05, le=1.2)
    bc_g7: float | None = Field(None, ge=0.05, le=1.2)
    length_inches: float | None = Field(None, ge=0.2, le=3.0)
    sectional_density: float | None = Field(None, ge=0.05, le=0.500)
    base_type: str | None = None
    tip_type: str | None = None
    construction: str | None = None
    is_lead_free: bool = False
    type_tags: list[str] | None = None
    used_for: list[str] | None = None
    source_url: str | None = Field(None, max_length=500)
    bc_source: str = "manufacturer"
    bc_source_methodology: str | None = None
    bc_source_notes: str | None = None


class CreateCartridgeOp(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    action: Literal["create_cartridge"]
    manufacturer: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=500)
    sku: str | None = Field(None, max_length=100)
    caliber: str = Field(..., min_length=1)
    bullet: str = Field(..., min_length=1)
    bullet_manufacturer: str | None = None
    bullet_weight_grains: float = Field(..., ge=15, le=750)
    bc_g1: float | None = Field(None, ge=0.05, le=1.2)
    bc_g7: float | None = Field(None, ge=0.05, le=1.2)
    muzzle_velocity_fps: int = Field(..., ge=400, le=4000)
    test_barrel_length_inches: float | None = Field(None, ge=10, le=34)
    product_line: str | None = None
    round_count: int | None = None
    source_url: str | None = Field(None, max_length=500)


class CreateRifleOp(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    action: Literal["create_rifle"]
    manufacturer: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1, max_length=255)
    chamber: str = Field(..., min_length=1)
    barrel_length_inches: float | None = Field(None, ge=10, le=34)
    twist_rate: str | None = None
    weight_lbs: float | None = Field(None, ge=2, le=20)
    barrel_material: str | None = None
    barrel_finish: str | None = None
    model_family: str | None = None
    source_url: str | None = Field(None, max_length=500)


class UpdateBulletOp(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    action: Literal["update_bullet"]
    manufacturer: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    set: dict = Field(..., min_length=1)

    @field_validator("set")
    @classmethod
    def validate_set_keys(cls, v: dict) -> dict:
        invalid = set(v.keys()) - _BULLET_UPDATE_FIELDS
        if invalid:
            raise ValueError(f"Cannot update fields: {sorted(invalid)}. Allowed: {sorted(_BULLET_UPDATE_FIELDS)}")
        return v


class UpdateCartridgeOp(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    action: Literal["update_cartridge"]
    manufacturer: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    set: dict = Field(..., min_length=1)

    @field_validator("set")
    @classmethod
    def validate_set_keys(cls, v: dict) -> dict:
        invalid = set(v.keys()) - _CARTRIDGE_UPDATE_FIELDS
        if invalid:
            raise ValueError(f"Cannot update fields: {sorted(invalid)}. Allowed: {sorted(_CARTRIDGE_UPDATE_FIELDS)}")
        return v


class AddBCSourceOp(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    action: Literal["add_bc_source"]
    manufacturer: str = Field(..., min_length=1)
    bullet_name: str = Field(..., min_length=1)
    bc_type: Literal["g1", "g7"]
    bc_value: float = Field(..., ge=0.05, le=1.2)
    source: str = "manufacturer"
    source_url: str | None = Field(None, max_length=500)
    source_methodology: str | None = None
    notes: str | None = None


class DeleteBulletOp(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    action: Literal["delete_bullet"]
    manufacturer: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    id: str | None = Field(
        None, description="Exact bullet ID for disambiguation when multiple bullets share the same name"
    )
    reason: str = Field(..., min_length=1, max_length=500)


class DeleteCartridgeOp(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    action: Literal["delete_cartridge"]
    manufacturer: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    id: str | None = Field(
        None, description="Exact cartridge ID for disambiguation when multiple cartridges share the same name"
    )
    reason: str = Field(..., min_length=1, max_length=500)


class AddEntityAliasOp(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    action: Literal["add_entity_alias"]
    entity_type: Literal["manufacturer", "caliber", "chamber", "bullet", "cartridge"]
    entity_name: str = Field(..., min_length=1)
    alias: str = Field(..., min_length=1, max_length=255)
    alias_type: str = Field(..., min_length=1, max_length=50)


Operation = Annotated[
    Union[
        CreateCaliberOp,
        CreateBulletOp,
        CreateCartridgeOp,
        CreateRifleOp,
        UpdateBulletOp,
        UpdateCartridgeOp,
        DeleteBulletOp,
        DeleteCartridgeOp,
        AddBCSourceOp,
        AddEntityAliasOp,
    ],
    Discriminator("action"),
]


class PatchFile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    patch: PatchMetadata
    operations: list[Operation] = Field(..., min_length=1)


# ── Name Resolution ──────────────────────────────────────────────────────────
# All lookups: exact name match (case-insensitive) → EntityAlias fallback.

_ENTITY_TYPE_MODEL = {
    "manufacturer": Manufacturer,
    "caliber": Caliber,
    "chamber": Chamber,
    "bullet": Bullet,
    "cartridge": Cartridge,
}


def _resolve_entity(session: Session, entity_type: str, name: str, *, manufacturer_id: str | None = None) -> str:
    """Resolve an entity name to its ID.

    1. Exact match on the model's name field (case-insensitive).
    2. Fallback: query EntityAlias table for (entity_type, alias) → entity_id.
    3. For bullets: optionally filter by manufacturer_id for disambiguation.

    Raises ValueError if not found.
    """
    model = _ENTITY_TYPE_MODEL[entity_type]
    name_col = model.model if entity_type == "rifle" else model.name if hasattr(model, "name") else model.model

    # Step 1: exact name match (case-insensitive)
    query = session.query(model).filter(func.lower(name_col) == name.lower().strip())
    if manufacturer_id and hasattr(model, "manufacturer_id"):
        query = query.filter(model.manufacturer_id == manufacturer_id)
    entity = query.first()
    if entity:
        return entity.id

    # Step 2: EntityAlias fallback
    alias_row = (
        session.query(EntityAlias)
        .filter(
            EntityAlias.entity_type == entity_type,
            func.lower(EntityAlias.alias) == name.lower().strip(),
        )
        .first()
    )
    if alias_row:
        return alias_row.entity_id

    raise ValueError(f"{entity_type} not found: {name!r}")


def _resolve_manufacturer(session: Session, name: str) -> str:
    return _resolve_entity(session, "manufacturer", name)


def _resolve_caliber(session: Session, name: str) -> str:
    return _resolve_entity(session, "caliber", name)


def _resolve_chamber(session: Session, name: str) -> str:
    return _resolve_entity(session, "chamber", name)


def _resolve_bullet(session: Session, manufacturer_id: str, name: str) -> str:
    return _resolve_entity(session, "bullet", name, manufacturer_id=manufacturer_id)


# ── Idempotency Checks ──────────────────────────────────────────────────────


def _caliber_exists(session: Session, name: str) -> Caliber | None:
    return session.query(Caliber).filter(func.lower(Caliber.name) == name.lower()).first()


def _bullet_exists(session: Session, manufacturer_id: str, name: str, sku: str | None) -> Bullet | None:
    if sku:
        existing = session.query(Bullet).filter(func.lower(Bullet.sku) == sku.lower()).first()
        if existing:
            return existing
    return (
        session.query(Bullet)
        .filter(Bullet.manufacturer_id == manufacturer_id, func.lower(Bullet.name) == name.lower())
        .first()
    )


def _cartridge_exists(session: Session, manufacturer_id: str, name: str, sku: str | None) -> Cartridge | None:
    if sku:
        existing = session.query(Cartridge).filter(func.lower(Cartridge.sku) == sku.lower()).first()
        if existing:
            return existing
    return (
        session.query(Cartridge)
        .filter(Cartridge.manufacturer_id == manufacturer_id, func.lower(Cartridge.name) == name.lower())
        .first()
    )


def _rifle_exists(session: Session, manufacturer_id: str, model_name: str) -> RifleModel | None:
    return (
        session.query(RifleModel)
        .filter(RifleModel.manufacturer_id == manufacturer_id, func.lower(RifleModel.model) == model_name.lower())
        .first()
    )


def _bc_source_exists(session: Session, bullet_id: str, bc_type: str, bc_value: float, source: str) -> bool:
    return (
        session.query(BulletBCSource)
        .filter(
            BulletBCSource.bullet_id == bullet_id,
            BulletBCSource.bc_type == bc_type,
            BulletBCSource.bc_value == bc_value,
            BulletBCSource.source == source,
        )
        .first()
        is not None
    )


# ── Stats ────────────────────────────────────────────────────────────────────


@dataclass
class ApplyStats:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    details: list[str] = field(default_factory=list)


# ── Operation Handlers ───────────────────────────────────────────────────────


def _apply_create_caliber(session: Session, op: CreateCaliberOp, stats: ApplyStats, index: int) -> None:
    existing = _caliber_exists(session, op.name)
    if existing:
        stats.skipped += 1
        stats.details.append(f"  [{index}] SKIP create_caliber: {op.name!r} (id={existing.id})")
        return

    caliber = Caliber(
        id=str(uuid.uuid4()),
        name=op.name,
        bullet_diameter_inches=op.bullet_diameter_inches,
        alt_names=op.alt_names,
        case_length_inches=op.case_length_inches,
        coal_inches=op.coal_inches,
        max_pressure_psi=op.max_pressure_psi,
        rim_type=op.rim_type,
        action_length=op.action_length,
        year_introduced=op.year_introduced,
        is_common_lr=op.is_common_lr,
        source_url=op.source_url,
    )
    session.add(caliber)
    session.flush()
    stats.created += 1
    stats.details.append(f"  [{index}] CREATE caliber: {op.name!r} (id={caliber.id})")


def _apply_create_bullet(session: Session, op: CreateBulletOp, stats: ApplyStats, index: int) -> None:
    mfr_id = _resolve_manufacturer(session, op.manufacturer)
    existing = _bullet_exists(session, mfr_id, op.name, op.sku)
    if existing:
        stats.skipped += 1
        stats.details.append(f"  [{index}] SKIP create_bullet: {op.name!r} (id={existing.id})")
        return

    bullet_id = str(uuid.uuid4())
    bullet = Bullet(
        id=bullet_id,
        manufacturer_id=mfr_id,
        name=op.name,
        sku=op.sku,
        weight_grains=op.weight_grains,
        bullet_diameter_inches=op.bullet_diameter_inches,
        bc_g1_published=op.bc_g1,
        bc_g7_published=op.bc_g7,
        length_inches=op.length_inches,
        sectional_density=op.sectional_density,
        base_type=op.base_type,
        tip_type=op.tip_type,
        construction=op.construction,
        is_lead_free=op.is_lead_free,
        type_tags=op.type_tags,
        used_for=op.used_for,
        source_url=op.source_url,
        data_source="manual",
        is_locked=True,
    )
    session.add(bullet)

    for bc_type_key, bc_val in [("g1", op.bc_g1), ("g7", op.bc_g7)]:
        if bc_val is not None:
            session.add(
                BulletBCSource(
                    id=str(uuid.uuid4()),
                    bullet_id=bullet_id,
                    bc_type=bc_type_key,
                    bc_value=bc_val,
                    source=op.bc_source,
                    source_url=op.source_url,
                    source_methodology=op.bc_source_methodology,
                    notes=op.bc_source_notes,
                )
            )

    session.flush()
    stats.created += 1
    stats.details.append(f"  [{index}] CREATE bullet: {op.name!r} (id={bullet_id})")


def _apply_create_cartridge(session: Session, op: CreateCartridgeOp, stats: ApplyStats, index: int) -> None:
    mfr_id = _resolve_manufacturer(session, op.manufacturer)
    existing = _cartridge_exists(session, mfr_id, op.name, op.sku)
    if existing:
        stats.skipped += 1
        stats.details.append(f"  [{index}] SKIP create_cartridge: {op.name!r} (id={existing.id})")
        return

    caliber_id = _resolve_caliber(session, op.caliber)
    bullet_mfr_id = _resolve_manufacturer(session, op.bullet_manufacturer) if op.bullet_manufacturer else mfr_id
    bullet_id = _resolve_bullet(session, bullet_mfr_id, op.bullet)

    cartridge = Cartridge(
        id=str(uuid.uuid4()),
        manufacturer_id=mfr_id,
        name=op.name,
        sku=op.sku,
        caliber_id=caliber_id,
        bullet_id=bullet_id,
        bullet_weight_grains=op.bullet_weight_grains,
        bc_g1=op.bc_g1,
        bc_g7=op.bc_g7,
        muzzle_velocity_fps=op.muzzle_velocity_fps,
        test_barrel_length_inches=op.test_barrel_length_inches,
        product_line=op.product_line,
        round_count=op.round_count,
        source_url=op.source_url,
        data_source="manual",
        is_locked=True,
    )
    session.add(cartridge)
    session.flush()
    stats.created += 1
    stats.details.append(f"  [{index}] CREATE cartridge: {op.name!r} (id={cartridge.id})")


def _apply_create_rifle(session: Session, op: CreateRifleOp, stats: ApplyStats, index: int) -> None:
    mfr_id = _resolve_manufacturer(session, op.manufacturer)
    existing = _rifle_exists(session, mfr_id, op.model)
    if existing:
        stats.skipped += 1
        stats.details.append(f"  [{index}] SKIP create_rifle: {op.model!r} (id={existing.id})")
        return

    chamber_id = _resolve_chamber(session, op.chamber)

    rifle = RifleModel(
        id=str(uuid.uuid4()),
        manufacturer_id=mfr_id,
        model=op.model,
        chamber_id=chamber_id,
        barrel_length_inches=op.barrel_length_inches,
        twist_rate=op.twist_rate,
        weight_lbs=op.weight_lbs,
        barrel_material=op.barrel_material,
        barrel_finish=op.barrel_finish,
        model_family=op.model_family,
        source_url=op.source_url,
        data_source="manual",
        is_locked=True,
    )
    session.add(rifle)
    session.flush()
    stats.created += 1
    stats.details.append(f"  [{index}] CREATE rifle: {op.model!r} (id={rifle.id})")


def _apply_update_bullet(session: Session, op: UpdateBulletOp, stats: ApplyStats, index: int) -> None:
    mfr_id = _resolve_manufacturer(session, op.manufacturer)
    bullet = (
        session.query(Bullet)
        .filter(Bullet.manufacturer_id == mfr_id, func.lower(Bullet.name) == op.name.lower())
        .first()
    )
    if not bullet:
        raise ValueError(f"Bullet not found: {op.name!r} (manufacturer={op.manufacturer})")

    changed = {k: v for k, v in op.set.items() if getattr(bullet, k) != v}
    if not changed:
        stats.skipped += 1
        stats.details.append(f"  [{index}] SKIP update_bullet: {op.name!r} (already up to date)")
        return

    for key, value in changed.items():
        setattr(bullet, key, value)
    session.flush()
    stats.updated += 1
    stats.details.append(f"  [{index}] UPDATE bullet: {op.name!r} — {list(changed.keys())}")


def _apply_update_cartridge(session: Session, op: UpdateCartridgeOp, stats: ApplyStats, index: int) -> None:
    mfr_id = _resolve_manufacturer(session, op.manufacturer)
    cartridge = (
        session.query(Cartridge)
        .filter(Cartridge.manufacturer_id == mfr_id, func.lower(Cartridge.name) == op.name.lower())
        .first()
    )
    if not cartridge:
        raise ValueError(f"Cartridge not found: {op.name!r} (manufacturer={op.manufacturer})")

    changed = {k: v for k, v in op.set.items() if getattr(cartridge, k) != v}
    if not changed:
        stats.skipped += 1
        stats.details.append(f"  [{index}] SKIP update_cartridge: {op.name!r} (already up to date)")
        return

    for key, value in changed.items():
        setattr(cartridge, key, value)
    session.flush()
    stats.updated += 1
    stats.details.append(f"  [{index}] UPDATE cartridge: {op.name!r} — {list(changed.keys())}")


def _apply_delete_bullet(session: Session, op: DeleteBulletOp, stats: ApplyStats, index: int) -> None:
    mfr_id = _resolve_manufacturer(session, op.manufacturer)
    if op.id:
        bullet = session.query(Bullet).filter(Bullet.id == op.id, Bullet.manufacturer_id == mfr_id).first()
    else:
        bullet = (
            session.query(Bullet)
            .filter(Bullet.manufacturer_id == mfr_id, func.lower(Bullet.name) == op.name.lower())
            .first()
        )
    if not bullet:
        stats.skipped += 1
        stats.details.append(f"  [{index}] SKIP delete_bullet: {op.name!r} not found")
        return

    # Refuse to delete if cartridges reference this bullet
    cartridge_refs = session.query(Cartridge).filter(Cartridge.bullet_id == bullet.id).count()
    if cartridge_refs > 0:
        raise ValueError(
            f"Cannot delete bullet {op.name!r}: {cartridge_refs} cartridge(s) reference it. "
            "Delete or re-link cartridges first."
        )

    # Cascade to BulletBCSource (no ondelete cascade in schema yet)
    bc_deleted = session.query(BulletBCSource).filter(BulletBCSource.bullet_id == bullet.id).delete()
    session.delete(bullet)
    session.flush()
    stats.updated += 1  # "updated" in the sense of a destructive change
    stats.details.append(
        f"  [{index}] DELETE bullet: {op.name!r} (id={bullet.id}, {bc_deleted} BC sources removed). "
        f"Reason: {op.reason}"
    )


def _apply_delete_cartridge(session: Session, op: DeleteCartridgeOp, stats: ApplyStats, index: int) -> None:
    mfr_id = _resolve_manufacturer(session, op.manufacturer)
    if op.id:
        cartridge = session.query(Cartridge).filter(Cartridge.id == op.id, Cartridge.manufacturer_id == mfr_id).first()
    else:
        cartridge = (
            session.query(Cartridge)
            .filter(Cartridge.manufacturer_id == mfr_id, func.lower(Cartridge.name) == op.name.lower())
            .first()
        )
    if not cartridge:
        stats.skipped += 1
        stats.details.append(f"  [{index}] SKIP delete_cartridge: {op.name!r} not found")
        return

    session.delete(cartridge)
    session.flush()
    stats.updated += 1
    stats.details.append(f"  [{index}] DELETE cartridge: {op.name!r} (id={cartridge.id}). Reason: {op.reason}")


def _apply_add_bc_source(session: Session, op: AddBCSourceOp, stats: ApplyStats, index: int) -> None:
    mfr_id = _resolve_manufacturer(session, op.manufacturer)
    bullet_id = _resolve_bullet(session, mfr_id, op.bullet_name)

    if _bc_source_exists(session, bullet_id, op.bc_type, op.bc_value, op.source):
        stats.skipped += 1
        stats.details.append(f"  [{index}] SKIP add_bc_source: {op.bc_type}={op.bc_value} already exists")
        return

    session.add(
        BulletBCSource(
            id=str(uuid.uuid4()),
            bullet_id=bullet_id,
            bc_type=op.bc_type,
            bc_value=op.bc_value,
            source=op.source,
            source_url=op.source_url,
            source_methodology=op.source_methodology,
            notes=op.notes,
        )
    )
    session.flush()
    stats.created += 1
    stats.details.append(f"  [{index}] CREATE bc_source: {op.bullet_name} {op.bc_type}={op.bc_value}")


def _apply_add_entity_alias(session: Session, op: AddEntityAliasOp, stats: ApplyStats, index: int) -> None:
    entity_id = _resolve_entity(session, op.entity_type, op.entity_name)

    try:
        session.add(
            EntityAlias(
                id=str(uuid.uuid4()),
                entity_type=op.entity_type,
                entity_id=entity_id,
                alias=op.alias,
                alias_type=op.alias_type,
            )
        )
        session.flush()
        stats.created += 1
        stats.details.append(f"  [{index}] CREATE alias: {op.entity_type} {op.entity_name!r} → {op.alias!r}")
    except IntegrityError:
        session.rollback()
        stats.skipped += 1
        stats.details.append(f"  [{index}] SKIP alias: {op.alias!r} already exists for {op.entity_type}")


_HANDLERS = {
    "create_caliber": _apply_create_caliber,
    "create_bullet": _apply_create_bullet,
    "create_cartridge": _apply_create_cartridge,
    "create_rifle": _apply_create_rifle,
    "update_bullet": _apply_update_bullet,
    "update_cartridge": _apply_update_cartridge,
    "delete_bullet": _apply_delete_bullet,
    "delete_cartridge": _apply_delete_cartridge,
    "add_bc_source": _apply_add_bc_source,
    "add_entity_alias": _apply_add_entity_alias,
}


# ── Patch Loading & Application ──────────────────────────────────────────────


def discover_patches(patches_dir: Path) -> list[Path]:
    """Find all YAML patch files, sorted by filename (numeric prefix)."""
    return sorted(patches_dir.glob("*.yaml"))


def load_and_validate(patch_path: Path) -> PatchFile:
    """Load a YAML file and validate against the PatchFile schema."""
    raw = yaml.safe_load(patch_path.read_text(encoding="utf-8"))
    return PatchFile.model_validate(raw)


def apply_patch(session: Session, patch: PatchFile) -> ApplyStats:
    """Apply all operations in a validated patch. Uses savepoints for per-operation isolation."""
    stats = ApplyStats()

    for i, op in enumerate(patch.operations):
        sp = session.begin_nested()
        try:
            handler = _HANDLERS[op.action]
            handler(session, op, stats, i)
            sp.commit()
        except Exception as e:
            sp.rollback()
            stats.errors += 1
            stats.details.append(f"  [{i}] ERROR ({op.action}): {e}")
            logger.warning("Operation %d failed in patch %s: %s", i, patch.patch.id, e)

    return stats
