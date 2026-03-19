"""Bullet entity — the canonical ballistic unit — and BulletBCSource for multi-source BC tracking."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drift.models.base import Base, TimestampMixin, uuid_fk, uuid_fk_nullable, uuid_pk

if TYPE_CHECKING:
    from drift.models import Cartridge, Manufacturer
    from drift.models.bullet_product_line import BulletProductLine


class Bullet(TimestampMixin, Base):
    __tablename__ = "bullet"

    id: Mapped[str] = uuid_pk()
    manufacturer_id: Mapped[str] = uuid_fk("manufacturer.id")
    name: Mapped[str] = mapped_column(String(255), index=True)
    alt_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    bullet_diameter_inches: Mapped[float] = mapped_column(Float, nullable=False)
    weight_grains: Mapped[float] = mapped_column(Float, nullable=False)

    # BC values — published and estimated
    bc_g1_published: Mapped[float | None] = mapped_column(Float, nullable=True)
    bc_g1_estimated: Mapped[float | None] = mapped_column(Float, nullable=True)
    bc_g7_published: Mapped[float | None] = mapped_column(Float, nullable=True)
    bc_g7_estimated: Mapped[float | None] = mapped_column(Float, nullable=True)
    bc_source_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Physical properties
    length_inches: Mapped[float | None] = mapped_column(Float, nullable=True)
    sectional_density: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Classification tags (controlled vocabulary — see design proposal addendum §2)
    type_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    used_for: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Product family — three related fields:
    #   product_line      — human-readable string ("ELD-X"), used by display_name and extraction
    #   product_line_id   — FK to bullet_product_line entity, used for alias lookup and structured matching
    #   product_line_rel  — ORM relationship to BulletProductLine (navigational)
    product_line: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    product_line_id: Mapped[str | None] = uuid_fk_nullable("bullet_product_line.id")

    # Cleaned display name for iOS app UI (computed at export time)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Structured classification (nullable, V2 filtering)
    base_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tip_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    construction: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_lead_free: Mapped[bool] = mapped_column(default=False, server_default="0")

    # Ranking
    popularity_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Provenance & curation
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_source: Mapped[str] = mapped_column(String(50), default="pipeline", server_default="pipeline")
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # Relationships
    manufacturer: Mapped["Manufacturer"] = relationship(back_populates="bullets")  # noqa: F821
    cartridges: Mapped[list["Cartridge"]] = relationship(back_populates="bullet")  # noqa: F821
    bc_sources: Mapped[list["BulletBCSource"]] = relationship(back_populates="bullet")
    product_line_rel: Mapped["BulletProductLine | None"] = relationship(back_populates="bullets")  # noqa: F821


class BulletBCSource(TimestampMixin, Base):
    """Multi-source BC tracking. One row per BC observation from a specific source.

    The Bullet's bc_g1_*/bc_g7_* fields are the reconciled canonical values.
    This table stores the full picture for review and audit.
    """

    __tablename__ = "bullet_bc_source"

    id: Mapped[str] = uuid_pk()
    bullet_id: Mapped[str] = uuid_fk("bullet.id")
    bc_type: Mapped[str] = mapped_column(String(10))  # "g1" or "g7"
    bc_value: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(100))  # e.g. "manufacturer", "applied_ballistics"
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_methodology: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    bullet: Mapped["Bullet"] = relationship(back_populates="bc_sources")
