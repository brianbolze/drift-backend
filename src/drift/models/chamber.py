"""Chamber entity — what a gun is machined for — and the chamber↔caliber join table."""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drift.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from drift.models import Caliber, RifleModel


class Chamber(TimestampMixin, Base):
    __tablename__ = "chamber"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    alt_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    caliber_links: Mapped[list["ChamberAcceptsCaliber"]] = relationship(
        back_populates="chamber",
    )
    rifle_models: Mapped[list["RifleModel"]] = relationship(back_populates="chamber")  # noqa: F821


class ChamberAcceptsCaliber(Base):
    __tablename__ = "chamber_accepts_caliber"

    chamber_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chamber.id"),
        primary_key=True,
    )
    caliber_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("caliber.id"),
        primary_key=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    # Relationships
    chamber: Mapped["Chamber"] = relationship(back_populates="caliber_links")
    caliber: Mapped["Caliber"] = relationship(back_populates="chamber_links")  # noqa: F821
