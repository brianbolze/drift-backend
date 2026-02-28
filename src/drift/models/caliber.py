"""Caliber entity — a cartridge designation (the ammo side of the equation)."""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drift.models.base import Base, TimestampMixin, uuid_fk_nullable, uuid_pk

if TYPE_CHECKING:
    from drift.models import Bullet, Cartridge, CaliberPlatform, ChamberAcceptsCaliber


class Caliber(TimestampMixin, Base):
    __tablename__ = "caliber"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    alt_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    bullet_diameter_inches: Mapped[float] = mapped_column(Float, nullable=False)
    case_length_inches: Mapped[float | None] = mapped_column(Float, nullable=True)
    saami_designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Addendum fields
    overall_popularity_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lr_popularity_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coal_inches: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_pressure_psi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rim_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action_length: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parent_caliber_id: Mapped[str | None] = uuid_fk_nullable("caliber.id")
    year_introduced: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_common_lr: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    parent_caliber: Mapped["Caliber | None"] = relationship(
        remote_side="Caliber.id",
        foreign_keys=[parent_caliber_id],
    )
    bullets: Mapped[list["Bullet"]] = relationship(back_populates="caliber")  # noqa: F821
    cartridges: Mapped[list["Cartridge"]] = relationship(back_populates="caliber")  # noqa: F821
    chamber_links: Mapped[list["ChamberAcceptsCaliber"]] = relationship(  # noqa: F821
        back_populates="caliber",
    )
    platform_links: Mapped[list["CaliberPlatform"]] = relationship(  # noqa: F821
        back_populates="caliber",
    )
