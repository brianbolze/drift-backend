"""Cartridge entity — a factory-loaded round. References a specific Bullet in a specific Caliber."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drift.models.base import Base, TimestampMixin, uuid_fk, uuid_pk

if TYPE_CHECKING:
    from drift.models import Bullet, Caliber, Manufacturer


class Cartridge(TimestampMixin, Base):
    __tablename__ = "cartridge"

    id: Mapped[str] = uuid_pk()
    manufacturer_id: Mapped[str] = uuid_fk("manufacturer.id")
    product_line: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(500), index=True)
    alt_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    caliber_id: Mapped[str] = uuid_fk("caliber.id")
    bullet_id: Mapped[str] = uuid_fk("bullet.id")

    # Denormalized for search/display convenience
    bullet_weight_grains: Mapped[float] = mapped_column(Float, nullable=False)

    # Bullet BC values as published on the cartridge product page
    bc_g1: Mapped[float | None] = mapped_column(Float, nullable=True)
    bc_g7: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Bullet physical specs as published on the cartridge product page
    bullet_length_inches: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Velocity data
    muzzle_velocity_fps: Mapped[int] = mapped_column(Integer, nullable=False)
    test_barrel_length_inches: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Packaging
    round_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Entity resolution metadata (Doro pattern)
    bullet_match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    bullet_match_method: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Ranking
    popularity_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Provenance
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    manufacturer: Mapped["Manufacturer"] = relationship(back_populates="cartridges")  # noqa: F821
    caliber: Mapped["Caliber"] = relationship(back_populates="cartridges")  # noqa: F821
    bullet: Mapped["Bullet"] = relationship(back_populates="cartridges")  # noqa: F821
