"""split popularity_rank into overall and lr on bullet and cartridge

Replace the single popularity_rank column with overall_popularity_rank and
lr_popularity_rank on both bullet and cartridge tables, mirroring the pattern
already established on the caliber table.

Revision ID: f1a2b3c4d5e6
Revises: b3f4a5c6d7e8
Create Date: 2026-03-18 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "b3f4a5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bullet", schema=None) as batch_op:
        batch_op.add_column(sa.Column("overall_popularity_rank", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("lr_popularity_rank", sa.Integer(), nullable=True))
        batch_op.drop_column("popularity_rank")

    with op.batch_alter_table("cartridge", schema=None) as batch_op:
        batch_op.add_column(sa.Column("overall_popularity_rank", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("lr_popularity_rank", sa.Integer(), nullable=True))
        batch_op.drop_column("popularity_rank")


def downgrade() -> None:
    with op.batch_alter_table("cartridge", schema=None) as batch_op:
        batch_op.add_column(sa.Column("popularity_rank", sa.Integer(), nullable=True))
        batch_op.drop_column("lr_popularity_rank")
        batch_op.drop_column("overall_popularity_rank")

    with op.batch_alter_table("bullet", schema=None) as batch_op:
        batch_op.add_column(sa.Column("popularity_rank", sa.Integer(), nullable=True))
        batch_op.drop_column("lr_popularity_rank")
        batch_op.drop_column("overall_popularity_rank")
