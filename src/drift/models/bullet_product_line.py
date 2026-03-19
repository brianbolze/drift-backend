"""BulletProductLine — canonical product family for bullets (e.g., ELD Match, MatchKing, TSX).

Gives product lines a UUID identity so entity_alias can reference them.
Aliases (ELDM, SMK, ABLR, etc.) are stored in entity_alias with entity_type='bullet_product_line'.
At export time, aliases are flattened into bullet.alt_names JSON for iOS search.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drift.models.base import Base, TimestampMixin, uuid_fk, uuid_pk

if TYPE_CHECKING:
    from drift.models import Bullet, Manufacturer


class BulletProductLine(TimestampMixin, Base):
    __tablename__ = "bullet_product_line"

    id: Mapped[str] = uuid_pk()
    manufacturer_id: Mapped[str] = uuid_fk("manufacturer.id")
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # "ELD Match", "MatchKing", "TSX"
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # "eld-match", "matchking", "tsx"
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)  # match, hunting, varmint, tactical, etc.
    is_generic: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # Relationships
    manufacturer: Mapped["Manufacturer"] = relationship()
    bullets: Mapped[list["Bullet"]] = relationship(back_populates="product_line_rel")

    __table_args__ = (UniqueConstraint("manufacturer_id", "slug", name="uq_bpl_manufacturer_slug"),)
