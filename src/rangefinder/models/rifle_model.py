"""RifleModel entity — factory rifle specifications."""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rangefinder.models.base import Base, TimestampMixin, uuid_fk, uuid_pk

if TYPE_CHECKING:
    from rangefinder.models import Chamber, Manufacturer


class RifleModel(TimestampMixin, Base):
    __tablename__ = "rifle_model"

    id: Mapped[str] = uuid_pk()
    manufacturer_id: Mapped[str] = uuid_fk("manufacturer.id")
    model: Mapped[str] = mapped_column(String(255), index=True)
    manufacturer_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    alt_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    chamber_id: Mapped[str] = uuid_fk("chamber.id")
    barrel_length_inches: Mapped[float | None] = mapped_column(Float, nullable=True)
    twist_rate: Mapped[str | None] = mapped_column(String(20), nullable=True)
    weight_lbs: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    barrel_material: Mapped[str | None] = mapped_column(String(100), nullable=True)
    barrel_finish: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    manufacturer: Mapped["Manufacturer"] = relationship(back_populates="rifle_models")  # noqa: F821
    chamber: Mapped["Chamber"] = relationship(back_populates="rifle_models")  # noqa: F821
