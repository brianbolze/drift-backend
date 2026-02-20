"""Optic and Reticle entities — riflescope specifications and reticle patterns."""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rangefinder.models.base import Base, TimestampMixin, uuid_fk, uuid_pk

if TYPE_CHECKING:
    from rangefinder.models import Manufacturer


class Reticle(TimestampMixin, Base):
    """A reticle pattern (e.g. EBR-7C MRAD, Tremor3).

    Reticles have independent identity — the same reticle can appear in multiple
    optic models across manufacturers (e.g. Horus Tremor3 is licensed to
    Nightforce, Sig, etc.).
    """

    __tablename__ = "reticle"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    alt_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    unit: Mapped[str] = mapped_column(String(10))  # "mil" | "moa"
    manufacturer_id: Mapped[str] = uuid_fk("manufacturer.id")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    manufacturer: Mapped["Manufacturer"] = relationship(back_populates="reticles")  # noqa: F821
    optics: Mapped[list["Optic"]] = relationship(back_populates="reticle")


class Optic(TimestampMixin, Base):
    """A riflescope configuration — one row per buyable SKU.

    Mil and MOA variants of the same model are separate rows sharing the
    same ``model_family`` string for display grouping.
    """

    __tablename__ = "optic"

    id: Mapped[str] = uuid_pk()
    manufacturer_id: Mapped[str] = uuid_fk("manufacturer.id")
    name: Mapped[str] = mapped_column(String(500), index=True)
    alt_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model_family: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_line: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    reticle_id: Mapped[str] = uuid_fk("reticle.id")

    # Turret / click specs (what the wizard auto-fills)
    click_unit: Mapped[str] = mapped_column(String(10))  # "mil" | "moa"
    click_value: Mapped[float] = mapped_column(Float, nullable=False)

    # Optical specs
    magnification_min: Mapped[float] = mapped_column(Float, nullable=False)
    magnification_max: Mapped[float] = mapped_column(Float, nullable=False)
    objective_diameter_mm: Mapped[float] = mapped_column(Float, nullable=False)
    tube_diameter_mm: Mapped[float] = mapped_column(Float, nullable=False)
    focal_plane: Mapped[str] = mapped_column(String(10))  # "ffp" | "sfp"

    # Adjustment range (normalized to mils)
    elevation_travel_mils: Mapped[float | None] = mapped_column(Float, nullable=True)
    windage_travel_mils: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Physical
    weight_oz: Mapped[float | None] = mapped_column(Float, nullable=True)
    length_inches: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Provenance
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    manufacturer: Mapped["Manufacturer"] = relationship(back_populates="optics")  # noqa: F821
    reticle: Mapped["Reticle"] = relationship(back_populates="optics")
