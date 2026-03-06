"""split caliber popularity_rank into overall and lr columns

The old `popularity_rank` was a single ranking that mixed overall popularity
with precision/LR relevance.  Split it into two explicit columns:

- `overall_popularity_rank` — how common the cartridge is across all use cases
- `lr_popularity_rank` — relevance in the precision / long-range community

During the migration the existing `popularity_rank` values are copied into
`lr_popularity_rank` (the original rankings were precision/LR-focused).
`overall_popularity_rank` starts as NULL — to be curated separately.

Revision ID: bdbb8bfc39ef
Revises: 71b236f2e2d0
Create Date: 2026-02-28 00:36:07.085209

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "bdbb8bfc39ef"
down_revision: Union[str, Sequence[str], None] = "71b236f2e2d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Add new columns alongside the old one
    with op.batch_alter_table("caliber", schema=None) as batch_op:
        batch_op.add_column(sa.Column("overall_popularity_rank", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("lr_popularity_rank", sa.Integer(), nullable=True))

    # Step 2: Copy existing popularity_rank -> lr_popularity_rank
    op.execute("UPDATE caliber SET lr_popularity_rank = popularity_rank")

    # Step 3: Drop old column
    with op.batch_alter_table("caliber", schema=None) as batch_op:
        batch_op.drop_column("popularity_rank")


def downgrade() -> None:
    """Downgrade schema."""
    # Step 1: Re-add the old column
    with op.batch_alter_table("caliber", schema=None) as batch_op:
        batch_op.add_column(sa.Column("popularity_rank", sa.INTEGER(), nullable=True))

    # Step 2: Copy lr_popularity_rank back
    op.execute("UPDATE caliber SET popularity_rank = lr_popularity_rank")

    # Step 3: Drop new columns
    with op.batch_alter_table("caliber", schema=None) as batch_op:
        batch_op.drop_column("lr_popularity_rank")
        batch_op.drop_column("overall_popularity_rank")
