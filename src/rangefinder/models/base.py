"""SQLAlchemy declarative base with common column patterns."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all models. Does NOT define any columns — subclasses opt in."""

    pass


class TimestampMixin:
    """Mixin that adds created_at / updated_at server-defaulted timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )


def uuid_pk() -> Mapped[str]:
    """UUID primary key stored as a 36-char string (SQLite has no native UUID)."""
    return mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )


def uuid_fk(target: str, nullable: bool = False) -> Mapped[str | None]:
    """UUID foreign key column."""
    from sqlalchemy import ForeignKey

    if nullable:
        return mapped_column(String(36), ForeignKey(target), nullable=True)
    return mapped_column(String(36), ForeignKey(target), nullable=False)
