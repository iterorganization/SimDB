"""add ingestion_status_updated_at

Revision ID: 6fb9b8fbac38
Revises: b2c52ee8ff12
Create Date: 2026-07-29 14:34:12.166293

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6fb9b8fbac38"
down_revision: Union[str, Sequence[str], None] = "b2c52ee8ff12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # A server_default lets the database fill existing rows when the NOT NULL
    # column is added, so no separate backfill/alter step is needed.
    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "ingestion_status_updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.drop_column("ingestion_status_updated_at")
