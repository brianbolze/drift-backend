"""add bullet_product_line table and bullet.product_line_id FK

New table gives product lines (ELD Match, MatchKing, TSX, etc.) a UUID identity
so entity_alias can reference them for abbreviation aliases (ELDM, SMK, etc.).
Also adds nullable FK on bullet for structured cartridge->bullet resolution.

Revision ID: b3f4a5c6d7e8
Revises: 94fc26fd30ce
Create Date: 2026-03-18 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3f4a5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "94fc26fd30ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create bullet_product_line table (idempotent for partial-migration recovery)
    op.create_table(
        "bullet_product_line",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("manufacturer_id", sa.String(36), sa.ForeignKey("manufacturer.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, index=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("is_generic", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("manufacturer_id", "slug", name="uq_bpl_manufacturer_slug"),
        if_not_exists=True,
    )

    # Add product_line_id to bullet.
    # Note: FK constraint omitted from migration because SQLite batch_alter_table
    # raises "Constraint must have a name" when adding ForeignKey inline. The ORM
    # model declares the FK via uuid_fk_nullable("bullet_product_line.id"), so
    # referential integrity is enforced at the application layer. SQLite doesn't
    # enforce FK constraints by default anyway (requires PRAGMA foreign_keys = ON).
    with op.batch_alter_table("bullet", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("product_line_id", sa.String(36), nullable=True),
        )

    # Create index separately (batch_alter_table FK handling is fragile in SQLite)
    op.create_index("ix_bullet_product_line_id", "bullet", ["product_line_id"])


def downgrade() -> None:
    op.drop_index("ix_bullet_product_line_id", table_name="bullet")

    with op.batch_alter_table("bullet", schema=None) as batch_op:
        batch_op.drop_column("product_line_id")

    op.drop_table("bullet_product_line")
