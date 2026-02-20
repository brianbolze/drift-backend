"""Manufacturer entity — companies that produce bullets, cartridges, rifles, or retail ammunition."""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rangefinder.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from rangefinder.models import Bullet, Cartridge, RifleModel
    from rangefinder.models.optic import Optic, Reticle


class Manufacturer(TimestampMixin, Base):
    __tablename__ = "manufacturer"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    alt_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    type_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    bullets: Mapped[list["Bullet"]] = relationship(back_populates="manufacturer")  # noqa: F821
    cartridges: Mapped[list["Cartridge"]] = relationship(back_populates="manufacturer")  # noqa: F821
    rifle_models: Mapped[list["RifleModel"]] = relationship(back_populates="manufacturer")  # noqa: F821
    optics: Mapped[list["Optic"]] = relationship(back_populates="manufacturer")  # noqa: F821
    reticles: Mapped[list["Reticle"]] = relationship(back_populates="manufacturer")  # noqa: F821
