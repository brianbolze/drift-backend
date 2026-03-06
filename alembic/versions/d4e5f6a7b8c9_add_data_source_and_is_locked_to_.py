"""add data_source and is_locked to bullet, cartridge, rifle_model

Adds curation protection fields so the pipeline store respects manually
curated records. `data_source` tracks provenance ("pipeline", "cowork",
"manual") and `is_locked` prevents the pipeline from overwriting a record.

Revision ID: d4e5f6a7b8c9
Revises: c3a7f9b2d1e4
Create Date: 2026-03-06 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3a7f9b2d1e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("bullet", "cartridge", "rifle_model"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("data_source", sa.String(50), nullable=False, server_default="pipeline"))
            batch_op.add_column(sa.Column("is_locked", sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    for table in ("bullet", "cartridge", "rifle_model"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("is_locked")
            batch_op.drop_column("data_source")
