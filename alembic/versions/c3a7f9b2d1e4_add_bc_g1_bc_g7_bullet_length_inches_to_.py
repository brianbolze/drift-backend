"""add bc_g1, bc_g7, bullet_length_inches to cartridge

Cartridge product pages typically republish the bullet's G1/G7 ballistic
coefficients and sometimes the bullet length. Collecting these at extraction
provides a validation layer against the bullet's own published values and
an additional signal for bullet matching during entity resolution.

Revision ID: c3a7f9b2d1e4
Revises: a1b2c3d4e5f6
Create Date: 2026-03-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a7f9b2d1e4'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("cartridge", schema=None) as batch_op:
        batch_op.add_column(sa.Column("bc_g1", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("bc_g7", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("bullet_length_inches", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cartridge", schema=None) as batch_op:
        batch_op.drop_column("bullet_length_inches")
        batch_op.drop_column("bc_g7")
        batch_op.drop_column("bc_g1")
