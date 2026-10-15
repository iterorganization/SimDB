"""add ingestion_error

Revision ID: c4d8e2f7a913
Revises: a3f1c7d94e02
Create Date: 2026-10-15 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d8e2f7a913"
down_revision: Union[str, Sequence[str], None] = "a3f1c7d94e02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ingestion_error", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.drop_column("ingestion_error")
