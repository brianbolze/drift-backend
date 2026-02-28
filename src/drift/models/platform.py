"""Platform entity — the action/receiver type a rifle is built on (e.g. Bolt Action, AR-15, AR-10).

Also contains the CaliberPlatform junction table that captures which calibers
are available on which platforms and their relative popularity.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drift.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from drift.models import Caliber


class Platform(TimestampMixin, Base):
    __tablename__ = "platform"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    short_name: Mapped[str] = mapped_column(String(20), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    caliber_links: Mapped[list["CaliberPlatform"]] = relationship(
        back_populates="platform",
    )


class CaliberPlatform(Base):
    __tablename__ = "caliber_platform"

    caliber_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("caliber.id"),
        primary_key=True,
    )
    platform_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("platform.id"),
        primary_key=True,
    )
    popularity_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    caliber: Mapped["Caliber"] = relationship(back_populates="platform_links")
    platform: Mapped["Platform"] = relationship(back_populates="caliber_links")
