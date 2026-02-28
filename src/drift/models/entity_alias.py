"""EntityAlias — pipeline-side alias metadata (not exported to bundled DB).

At export time, aliases are flattened into the alt_names JSON array on each entity.
This table preserves alias_type metadata for curation and debugging.
"""

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from drift.models.base import Base, TimestampMixin, uuid_pk


class EntityAlias(TimestampMixin, Base):
    __tablename__ = "entity_alias"

    id: Mapped[str] = uuid_pk()
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    alias: Mapped[str] = mapped_column(String(255))
    alias_type: Mapped[str] = mapped_column(String(50))

    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "alias", name="uq_entity_alias"),)
