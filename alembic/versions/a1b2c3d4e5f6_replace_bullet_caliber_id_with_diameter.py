"""replace bullet.caliber_id FK with bullet.bullet_diameter_inches

Bullets are physical projectiles defined by diameter, not by a specific
cartridge caliber. A .308" bullet works in .308 Win, .30-06, .300 Win Mag,
etc. This migration:
  1. Adds bullet.bullet_diameter_inches (populated from caliber table)
  2. Drops bullet.caliber_id FK

Cartridge.caliber_id is unchanged — a factory-loaded cartridge IS a
specific caliber.

Revision ID: a1b2c3d4e5f6
Revises: e015cb9c96e8
Create Date: 2026-03-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e015cb9c96e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add bullet_diameter_inches as nullable (for data migration)
    # Check if column already exists (in case of partial migration run)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('bullet')]

    if 'bullet_diameter_inches' not in columns:
        with op.batch_alter_table('bullet', schema=None) as batch_op:
            batch_op.add_column(sa.Column('bullet_diameter_inches', sa.Float(), nullable=True))

    # Step 2: Populate from caliber table
    op.execute(
        "UPDATE bullet SET bullet_diameter_inches = "
        "(SELECT caliber.bullet_diameter_inches FROM caliber WHERE caliber.id = bullet.caliber_id)"
    )

    # Step 3: Drop caliber_id and make bullet_diameter_inches NOT NULL.
    # SQLite requires batch mode to drop columns and alter nullability.
    # Note: In SQLite with batch operations, foreign keys are automatically handled
    # when dropping the column, so we don't need to explicitly drop the constraint.
    with op.batch_alter_table('bullet', schema=None) as batch_op:
        batch_op.alter_column('bullet_diameter_inches', nullable=False)
        # Skip the explicit drop_constraint for SQLite - it will be handled automatically
        # when we drop the column
        batch_op.drop_column('caliber_id')


def downgrade() -> None:
    # Re-add caliber_id as nullable (data link is lost — manual re-assignment needed)
    with op.batch_alter_table('bullet', schema=None) as batch_op:
        batch_op.add_column(sa.Column('caliber_id', sa.String(length=36), nullable=True))
        # For SQLite, the foreign key name isn't critical - just ensure it's created
        batch_op.create_foreign_key(None, 'caliber', ['caliber_id'], ['id'])

    # Best-effort: assign each bullet to the first caliber with matching diameter
    op.execute(
        "UPDATE bullet SET caliber_id = "
        "(SELECT caliber.id FROM caliber "
        "WHERE caliber.bullet_diameter_inches = bullet.bullet_diameter_inches LIMIT 1)"
    )

    with op.batch_alter_table('bullet', schema=None) as batch_op:
        batch_op.alter_column('caliber_id', nullable=False)
        batch_op.drop_column('bullet_diameter_inches')
